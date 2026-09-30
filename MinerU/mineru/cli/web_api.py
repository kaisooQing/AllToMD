# Copyright (c) Opendatalab. All rights reserved.
"""Vue Web UI 专用 API 扩展。

为替换 Gradio Web UI 提供：
- 前端配置接口
- URL/HTML 直接转换接口
- 结果文件访问接口
- 输出目录打开接口
"""

import os
import json
import re
import sys
import time
import uuid
import zipfile
from html import unescape
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urljoin

import asyncio

import httpx
import markdownify
from bs4 import BeautifulSoup
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from loguru import logger

# --- Anti-bot bypass: curl_cffi for browser TLS fingerprint impersonation ---
try:
    from curl_cffi import requests as curl_requests
    _CURL_CFFI_AVAILABLE = True
except ImportError:
    _CURL_CFFI_AVAILABLE = False
    logger.warning("curl_cffi not available, using httpx fallback for URL fetching")

# --- Playwright for JavaScript-rendered pages (SPA / dynamic content fallback) ---
_PLAYWRIGHT_AVAILABLE = False
try:
    # Set browsers path to local ms-playwright directory (relative to project root)
    _project_root = Path(__file__).resolve().parents[3]
    _ms_playwright_path = _project_root / "ms-playwright"
    if _ms_playwright_path.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(_ms_playwright_path))
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.info("Playwright not available, JS-rendered pages will not be supported")

from mineru.cli.backend_options import DEFAULT_BACKEND, DEFAULT_HYBRID_EFFORT
from mineru.cli.common import image_suffixes, office_suffixes, pdf_suffixes
from mineru.utils.ocr_language import PUBLIC_OCR_LANGUAGE_CHOICES

router = APIRouter(prefix="/api")

SUPPORTED_UPLOAD_SUFFIXES = pdf_suffixes + image_suffixes + office_suffixes
STATUS_PREPARING_REQUEST = "Preparing request..."
STATUS_COMPLETED = "Completed"

# 保存 URL/HTML 转换结果目录映射，供 /api/files/{task_id} 使用。
_url_html_output_dirs: dict[str, Path] = {}


def _get_output_root() -> Path:
    root = Path(os.getenv("MINERU_API_OUTPUT_ROOT", "./output")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def safe_stem(file_path: str) -> str:
    stem = Path(file_path).stem
    return re.sub(r"[^\w.]", "_", stem)


def safe_stem_from_text(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return "untitled"
    candidate = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", text)
    candidate = candidate.split("/")[0] if "/" in candidate else candidate
    candidate = candidate.split("?")[0] if "?" in candidate else candidate
    candidate = candidate.split("#")[0] if "#" in candidate else candidate
    candidate = re.sub(r"[^\w.]", "_", candidate)
    candidate = candidate.strip("._")
    if not candidate:
        return "untitled"
    return candidate[:80]


def directory_has_images(directory_path: Path) -> bool:
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
    for root, _dirs, files in os.walk(directory_path):
        for file in files:
            if Path(file).suffix.lower() in image_extensions:
                return True
    return False


def resolve_output_path_for_download(
    local_md_dir: Path, archive_zip_path: Path, file_name: str
) -> str:
    if directory_has_images(local_md_dir):
        return str(archive_zip_path)
    md_path = local_md_dir / f"{file_name}.md"
    if md_path.is_file():
        return str(md_path)
    return str(archive_zip_path)


def compress_directory_to_zip(directory_path: Path, output_zip_path: Path) -> bool:
    try:
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _dirs, files in os.walk(directory_path):
                for file in files:
                    # Skip temporary input files and hidden files
                    if file.startswith("__") or file.startswith("."):
                        continue
                    file_path = Path(root) / file
                    arcname = str(file_path.relative_to(directory_path)).replace("\\", "/")
                    zipf.write(file_path, arcname)
        return True
    except Exception as e:
        logger.exception(e)
        return False


def build_http_timeout() -> httpx.Timeout:
    return httpx.Timeout(30.0, connect=10.0)


# --- Browser-like headers for anti-bot bypass ---
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


def _create_anti_bot_session():
    """创建带浏览器 TLS 指纹的请求会话。

    使用 curl_cffi 模拟 Chrome 浏览器的 TLS 指纹，
    绕过基于 TLS 指纹检测的反爬虫机制（如 Cloudflare、百度文库等）。
    如果 curl_cffi 不可用则返回 None，调用方回退到 httpx。
    """
    if not _CURL_CFFI_AVAILABLE:
        return None
    return curl_requests.AsyncSession(impersonate="chrome")


def _get_root_domain_url(url: str) -> Optional[str]:
    """从 URL 中提取根域名首页地址，用于会话预热。

    例如:
      https://wenku.baidu.com/view/xxx.html → https://www.baidu.com/
      https://blog.csdn.net/user/article/123 → https://www.csdn.net/
      https://www.zhihu.com/question/123 → https://www.zhihu.com/
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not host:
        return None

    # 提取最后两段作为根域名 (e.g., baidu.com, csdn.net)
    parts = host.rsplit(".", 2)
    if len(parts) < 2:
        return None

    root_domain = ".".join(parts[-2:])
    # 构造 www.根域名 首页 URL
    return f"https://www.{root_domain}/"


async def _warmup_anti_bot_session(session, target_url: str, headers: dict) -> bool:
    """会话预热：先访问根域名首页获取必要的 cookies。

    部分网站（如百度文库）的反爬机制要求请求中携带从根域名获取的
    BAIDUID 等 cookies，否则会返回 403 "百度安全验证" 页面。

    策略：
    1. 从目标 URL 提取根域名
    2. 先访问根域名首页（如 https://www.baidu.com/）获取 cookies
    3. 再访问目标子域名首页（如 https://wenku.baidu.com/）传递 cookies
    4. 最后访问目标 URL

    Returns: True if warmup was performed, False if not needed/failed.
    """
    from urllib.parse import urlparse

    root_url = _get_root_domain_url(target_url)
    if not root_url:
        return False

    target_host = urlparse(target_url).hostname or ""

    try:
        # Step 1: Visit root domain homepage to seed cookies
        logger.info(f"Anti-bot warmup: visiting root domain {root_url}")
        r1 = await session.get(
            root_url,
            headers=headers,
            timeout=15,
            allow_redirects=True,
        )
        logger.info(f"Anti-bot warmup: root domain status={r1.status_code}")

        # Step 2: If target subdomain differs from root, visit it too
        root_host = urlparse(root_url).hostname or ""
        if target_host and target_host != root_host:
            subdomain_url = f"https://{target_host}/"
            logger.info(f"Anti-bot warmup: visiting subdomain {subdomain_url}")
            r2 = await session.get(
                subdomain_url,
                headers={**headers, "Referer": root_url},
                timeout=15,
                allow_redirects=True,
            )
            logger.info(f"Anti-bot warmup: subdomain status={r2.status_code}")

        return True
    except Exception as e:
        logger.warning(f"Anti-bot warmup failed: {e}")
        return False


async def _dismiss_cookie_consent(page) -> None:
    """尝试关闭常见的 Cookie 同意弹窗，避免遮挡正文内容。"""
    consent_texts = [
        "我接受", "接受全部", "全部接受", "同意", "Accept all", "Accept All",
        "I Accept", "Accept", "Got it", "OK", "同意并继续", "全部拒绝", "拒绝",
    ]
    for text in consent_texts:
        try:
            btn = page.locator(f"button:has-text(\"{text}\")").first
            if await btn.is_visible(timeout=1000):
                await btn.click(timeout=2000)
                logger.info(f"Playwright: dismissed cookie consent with '{text}'")
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue

    # 尝试常见的 Cookie 弹窗 ID/选择器
    consent_selectors = [
        "#onetrust-accept-btn-handler",
        "#accept-button",
        "[data-testid='accept-all']",
        ".cookie-accept",
        ".cc-accept",
    ]
    for sel in consent_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=2000)
                logger.info(f"Playwright: dismissed cookie consent via '{sel}'")
                await page.wait_for_timeout(1000)
                return
        except Exception:
            continue


async def _extract_shadow_dom_content(page) -> Optional[str]:
    """Extract article content from pages using Shadow DOM (e.g. MSN).

    MSN and similar sites encapsulate ALL article content inside custom
    elements with Shadow DOM (e.g. <cp-article>, <cp-article-image>).
    Standard HTML parsing and page.content() cannot access Shadow DOM
    content, so we use page.evaluate() to traverse Shadow DOMs and
    extract text + images.

    Returns HTML string with article content, or None if extraction failed.
    """
    try:
        result = await page.evaluate("""() => {
            // Check if page has custom elements with Shadow DOM
            const hasCustomShadow = Array.from(document.querySelectorAll('*'))
                .some(el => el.tagName.includes('-') && el.shadowRoot);
            if (!hasCustomShadow) return null;

            let title = '';
            let bodyHTML = '';

            // --- MSN-specific: extract from <cp-article> Shadow DOM ---
            const cpArticle = document.querySelector('cp-article');
            if (cpArticle && cpArticle.shadowRoot) {
                const shadow = cpArticle.shadowRoot;

                // Build a map of entity ID -> image URL from <cp-article-image>
                // elements within the first <msn-article-page> (the main article)
                const firstArticlePage = document.querySelector('msn-article-page');
                const imageMap = {};
                if (firstArticlePage) {
                    const imageComps = firstArticlePage.querySelectorAll('cp-article-image');
                    for (const comp of imageComps) {
                        if (comp.shadowRoot) {
                            const img = comp.shadowRoot.querySelector('img');
                            if (img) {
                                const src = img.src || img.getAttribute('src') || '';
                                // Extract entity ID from URL: .../entityid/AA28TQep.img?...
                                const match = src.match(/entityid\\/([A-Za-z0-9]+)/);
                                if (match) {
                                    imageMap[match[1]] = {src, alt: img.alt || ''};
                                }
                            }
                        }
                    }
                }

                // Replace image-related <slot> elements with actual <img> tags
                // Slot names like "AA28UqbY-image-cms/api/amp/image/AA28TQep"
                // contain the image entity ID that maps to imageMap
                const slots = shadow.querySelectorAll('slot');
                for (const slot of slots) {
                    const slotName = slot.name || '';
                    if (slotName.includes('image/')) {
                        const match = slotName.match(/image\\/([A-Za-z0-9]+)/);
                        if (match && imageMap[match[1]]) {
                            const imgInfo = imageMap[match[1]];
                            const newImg = document.createElement('img');
                            newImg.src = imgInfo.src;
                            newImg.alt = imgInfo.alt;
                            slot.replaceWith(newImg);
                        } else {
                            slot.remove();
                        }
                    } else {
                        // Non-image slot, remove it
                        slot.remove();
                    }
                }

                // Extract body HTML from Shadow DOM
                const bodyEl = shadow.querySelector('.article-body, body, article');
                if (bodyEl) {
                    bodyHTML = bodyEl.innerHTML;
                }

                // Append any images not placed in slots (fallback)
                const placedSrcs = new Set();
                if (bodyEl) {
                    const placedImgs = bodyEl.querySelectorAll('img');
                    for (const img of placedImgs) {
                        if (img.src) placedSrcs.add(img.src);
                    }
                }
                for (const key in imageMap) {
                    const imgInfo = imageMap[key];
                    if (!placedSrcs.has(imgInfo.src)) {
                        bodyHTML += '<img src="' + imgInfo.src + '" alt="' + imgInfo.alt + '">';
                    }
                }
            }

            // Extract title
            title = document.title || '';
            const ogTitle = document.querySelector('meta[property="og:title"]');
            if (ogTitle && ogTitle.content) {
                title = ogTitle.content;
            }

            // --- General Shadow DOM fallback (for non-MSN sites) ---
            if (!bodyHTML || bodyHTML.length < 100) {
                const textParts = [];
                function extractTextFromShadow(root, depth) {
                    if (depth > 5) return;
                    const elements = root.querySelectorAll('*');
                    for (const el of elements) {
                        if (el.shadowRoot) {
                            const paras = el.shadowRoot.querySelectorAll(
                                'p, h1, h2, h3, h4, h5, h6, li, blockquote'
                            );
                            for (const p of paras) {
                                const text = p.innerText.trim();
                                if (text.length > 10) {
                                    const tag = p.tagName.toLowerCase();
                                    textParts.push('<' + tag + '>' + text + '</' + tag + '>');
                                }
                            }
                            extractTextFromShadow(el.shadowRoot, depth + 1);
                        }
                    }
                }
                extractTextFromShadow(document, 0);
                if (textParts.length > 0) {
                    bodyHTML = textParts.join('');
                }
            }

            // General Shadow DOM image extraction (if no MSN images found)
            if (bodyHTML && (bodyHTML.match(/<img/g) || []).length === 0) {
                const images = [];
                function extractImagesFromShadow(root, depth) {
                    if (depth > 5) return;
                    const elements = root.querySelectorAll('*');
                    for (const el of elements) {
                        if (el.shadowRoot) {
                            const imgs = el.shadowRoot.querySelectorAll('img');
                            for (const img of imgs) {
                                const src = img.src || img.getAttribute('src') || '';
                                if (src && src.startsWith('http') && !src.startsWith('data:')) {
                                    if (src.includes('img-s.msn.cn/tenant/amp/entityid/') ||
                                        src.includes('img-s-msn-com.akamaized.net/tenant/amp/entityid/') ||
                                        (img.alt && img.alt.length > 5 &&
                                         !src.includes('icon') && !src.includes('logo') &&
                                         !src.includes('avatar') && !src.includes('assets.msn'))) {
                                        images.push({src, alt: img.alt || ''});
                                    }
                                }
                            }
                            extractImagesFromShadow(el.shadowRoot, depth + 1);
                        }
                    }
                }
                extractImagesFromShadow(document, 0);

                // Deduplicate and append images
                const seenUrls = new Set();
                for (const img of images) {
                    if (!seenUrls.has(img.src)) {
                        seenUrls.add(img.src);
                        bodyHTML += '<img src="' + img.src + '" alt="' + img.alt + '">';
                    }
                }
            }

            if (!bodyHTML) return null;

            // Build article HTML
            let html = '<article>';
            if (title) {
                html += '<h1>' + title + '</h1>';
            }
            html += bodyHTML;
            html += '</article>';

            return html;
        }""")

        if result and len(result) > 100:
            img_count = result.count("<img")
            logger.info(f"Shadow DOM extraction: {len(result)} chars, {img_count} images")
            return result
        return None
    except Exception as e:
        logger.warning(f"Shadow DOM extraction failed: {e}")
        return None


async def _fetch_with_playwright(url: str, timeout_ms: int = 30000) -> Optional[str]:
    """Use headless Chromium to render JavaScript-heavy pages and return full HTML.

    This is a fallback for SPA / dynamically rendered pages where the static
    HTML source contains little or no article text (e.g. MSN, Zhihu, etc.).

    Returns the rendered page HTML, or None if Playwright is unavailable / fails.
    """
    if not _PLAYWRIGHT_AVAILABLE:
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            page = await context.new_page()

            logger.info(f"Playwright: navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Wait for network activity to settle (SPA content loading)
            try:
                await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            except Exception:
                pass

            # 尝试关闭 Cookie 同意弹窗（如 MSN、知乎等）
            await _dismiss_cookie_consent(page)

            # 关闭弹窗后重新等待网络空闲（MSN 等会在关闭弹窗后加载正文）
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass

            # Extra wait for late-rendering JS frameworks
            await page.wait_for_timeout(3000)

            # Scroll down to trigger lazy-loaded content
            for scroll_step in [0.3, 0.6, 1.0]:
                await page.evaluate(f"window.scrollTo(0, document.body.scrollHeight * {scroll_step})")
                await page.wait_for_timeout(800)

            # 尝试提取文章正文区域
            article_selectors = [
                "article",
                "[data-testid='article-body']",
                ".article-body",
                ".article-content",
                ".content-body",
                "#article-body",
                ".post-content",
                ".entry-content",
                "main",
                "#main-content",
                ".main-content",
            ]

            def _extract_text(html_fragment: str) -> str:
                """从 HTML 片段中提取纯文本，用于判断内容是否有效。"""
                try:
                    soup = BeautifulSoup(html_fragment, "html.parser")
                    for tag in soup(["script", "style", "noscript"]):
                        tag.decompose()
                    return soup.get_text(strip=True)
                except Exception:
                    return ""

            article_html = None
            best_text_len = 0
            for sel in article_selectors:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=1000):
                        raw = await el.inner_html()
                        if raw:
                            text_len = len(_extract_text(raw))
                            if text_len > best_text_len:
                                best_text_len = text_len
                                article_html = raw
                                logger.info(f"Playwright: article candidate '{sel}' ({text_len} text chars)")
                                if text_len > 200:
                                    break
                except Exception:
                    continue

            # 回退到整个页面 HTML
            if article_html and best_text_len > 80:
                html = article_html
            else:
                html = None

            # Always try Shadow DOM extraction for sites with custom elements
            # (e.g. MSN encapsulates images in <cp-article-image> Shadow DOM,
            # which standard inner_html() cannot access)
            shadow_html = await _extract_shadow_dom_content(page)
            if shadow_html:
                shadow_img_count = shadow_html.count("<img")
                std_img_count = html.count("<img") if html else 0
                # Use Shadow DOM result if it has more images or standard
                # extraction found nothing
                if shadow_img_count > std_img_count or not html:
                    html = shadow_html
                    logger.info(
                        f"Playwright: using Shadow DOM extraction "
                        f"({shadow_img_count} images vs {std_img_count})"
                    )

            if not html:
                html = await page.content()
                # 最后检查整个页面是否有足够文本
                full_text = _extract_text(html)
                if len(full_text) < 80:
                    logger.warning(f"Playwright: page has only {len(full_text)} text chars, content may be empty")

            logger.info(f"Playwright: fetched {len(html)} chars from {url}")

            await context.close()
            await browser.close()

            return html
    except Exception as e:
        logger.warning(f"Playwright fetch failed for {url}: {e}")
        return None


def extract_js_object_after_assignment(raw_text: str, assignment: str) -> Optional[str]:
    """按括号配对截取 JS 赋值后的对象字面量，避免同一 script 内后续代码被误抓。"""
    start = raw_text.find(assignment)
    if start < 0:
        return None

    brace_start = raw_text.find("{", start + len(assignment))
    if brace_start < 0:
        return None

    # Safety cap: avoid scanning huge/invalid HTML indefinitely
    MAX_SCAN = 2_000_000  # 2 MB max
    scan_end = min(len(raw_text), brace_start + MAX_SCAN)

    depth = 0
    in_string: Optional[str] = None
    escaped = False

    for index in range(brace_start, scan_end):
        char = raw_text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue

        if char in ('"', "'"):
            in_string = char
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw_text[brace_start : index + 1]

    return None


def extract_article_html_from_page(raw_html: str) -> Optional[str]:
    """从常见新闻页的结构化脚本数据中提取正文 HTML。"""
    if not raw_html:
        return None

    data_json = extract_js_object_after_assignment(raw_html, "window.DATA")
    if not data_json:
        return None

    try:
        data = json.loads(data_json)
    except Exception as exc:
        logger.warning(f"Failed to parse window.DATA article payload: {exc}")
        return None

    origin_content = data.get("originContent") or {}
    article_body = origin_content.get("text") or data.get("content") or ""
    if not article_body:
        return None

    title = data.get("title") or ""
    media = data.get("media") or ""
    pubtime = data.get("pubtime") or ""

    meta_parts = []
    if media:
        meta_parts.append(str(media))
    if pubtime:
        meta_parts.append(str(pubtime))

    title_html = f"<h1>{title}</h1>" if title else ""
    meta_html = f"<p>{' · '.join(meta_parts)}</p>" if meta_parts else ""
    return f"<article>{title_html}{meta_html}{article_body}</article>"


def extract_textarea_article_html(raw_html: str) -> Optional[str]:
    """兼容环球网等将正文 HTML 转义后放入 textarea.article-content 的页面。"""
    if not raw_html:
        return None

    soup = BeautifulSoup(raw_html, "html.parser")
    content_node = soup.select_one("textarea.article-content")
    if content_node is None:
        return None

    article_body = unescape(content_node.get_text("", strip=False) or "")
    if not article_body.strip():
        return None

    title_node = soup.select_one("textarea.article-title")
    author_node = soup.select_one("textarea.article-author")
    host_node = soup.select_one("textarea.article-host")
    title = title_node.get_text(" ", strip=True) if title_node else ""
    author = author_node.get_text(" ", strip=True) if author_node else ""
    host = host_node.get_text(" ", strip=True) if host_node else ""

    meta_parts = [part for part in [author, host] if part]
    title_html = f"<h1>{title}</h1>" if title else ""
    meta_html = f"<p>{' · '.join(meta_parts)}</p>" if meta_parts else ""
    return f"<article>{title_html}{meta_html}{article_body}</article>"


def _remove_noise_elements(soup: BeautifulSoup) -> None:
    """移除页面中的导航、侧边栏、广告、评论等噪音元素。
    
    通过标签名、class/id 关键词匹配，清理非正文内容。
    """
    # 1. 按标签名移除语义标签
    for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer", "aside", "header"]):
        tag.decompose()

    # 2. 按 class/id 关键词移除噪音元素
    noise_keywords = [
        "nav", "menu", "navbar", "navigation", "breadcrumb", "crumb",
        "sidebar", "side-bar", "aside",
        "footer", "header", "topbar", "top-bar", "toolbar", "tool-bar",
        "related", "recommend", "hot", "ranking", "rank-list", "popular",
        "comment", "comments", "review", "reviews",
        "share", "social", "follow", "subscribe",
        "ad", "advert", "adsense", "banner",
        "widget", "modal", "popup", "overlay",
        "copyright", "license", "disclaimer",
        "channel", "category", "tag-list", "tagcloud",
        "login", "register", "signup", "search-box", "searchbar",
    ]

    for el in soup.find_all(True):
        if not el.name:
            continue
        # 已经被 decompose 的父节点会自动跳过
        if el.parent is None and el.name != "html":
            continue
        # 跳过标题标签内部的元素（如 VuePress/Docusaurus 的 <a class="header-anchor">）
        # 否则 "header" 关键词会误删标题锚点链接，导致标题文字丢失
        if el.find_parent(["h1", "h2", "h3", "h4", "h5", "h6"]):
            continue
        classes = el.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        el_id = el.get("id", "") or ""
        check_str = " ".join(classes).lower() + " " + el_id.lower()
        for kw in noise_keywords:
            if kw in check_str:
                el.decompose()
                break

    # 3. 移除"短链接列表"型导航（<ul> 中全是短文本链接，典型导航栏特征）
    for ul in soup.find_all("ul"):
        links = ul.find_all("a")
        if len(links) < 3:
            continue
        # 计算链接文本平均长度
        link_texts = [a.get_text(" ", strip=True) for a in links]
        avg_len = sum(len(t) for t in link_texts) / max(len(link_texts), 1)
        # 如果平均链接文本 < 12 字符，且链接数 >= 4，判定为导航列表
        if avg_len < 12 and len(links) >= 4:
            ul.decompose()
            continue
        # 如果整个 ul 的文本几乎全是链接文本（链接密度 > 80%），也是导航
        total_text = ul.get_text(" ", strip=True)
        link_total = sum(len(t) for t in link_texts)
        if len(total_text) > 0 and link_total / len(total_text) > 0.8:
            ul.decompose()


def _flatten_nested_format_tags(soup: BeautifulSoup) -> None:
    """展平嵌套的格式标签（<strong>/<b>/<em>/<i>），避免 markdownify 生成混乱的 ** 标记。

    某些网站（如 MSN）使用不规范的多层嵌套 <strong> 标签：
      <strong>文本A<strong>文本B<strong>文本C</strong></strong></strong>
    markdownify 会为每层生成 **，导致输出中 ** 数量不配对。
    此函数将嵌套的同类型标签展平为单层。
    """
    format_tags = {"strong": "strong", "b": "strong", "em": "em", "i": "em"}

    for tag_name in list(format_tags.keys()):
        for tag in soup.find_all(tag_name):
            # 检查是否有相同类型的嵌套子标签
            nested = tag.find(tag_name)
            if not nested:
                # 也检查等价标签（b↔strong, i↔em）
                equiv = "b" if tag_name == "strong" else ("strong" if tag_name == "b" else ("i" if tag_name == "em" else "em"))
                nested = tag.find(equiv)
            if nested:
                # 将嵌套子标签的子内容提升到当前标签
                # 即移除嵌套标签但保留其文本内容
                for child_nested in tag.find_all(tag_name):
                    child_nested.unwrap()
                # 也处理等价标签
                equiv_tags = {"strong": ["b"], "b": ["strong"], "em": ["i"], "i": ["em"]}
                for equiv in equiv_tags.get(tag_name, []):
                    for child_nested in tag.find_all(equiv):
                        child_nested.unwrap()


def _cleanup_navigation_from_markdown(md_text: str) -> str:
    """对 Markdown 输出进行后处理，移除残留的导航菜单行。
    
    策略：
    1. 移除连续的"纯链接短行"（典型导航菜单：[经济](url) [科技](url) ...）
    2. 移除单独成行的短链接列表项（1. [xxx](url) 或 - [xxx](url)）
    3. 移除"更多" "返回" 等导航文字行
    """
    lines = md_text.split('\n')
    cleaned = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            cleaned.append(line)
            i += 1
            continue

        # 检查是否是"纯链接短行" —— 行内只有链接和分隔符，没有实质文本
        # 匹配: [text](url) [text](url) ... 或 1. [text](url) 等
        link_only_pattern = re.compile(
            r'^(?:\d+\.?\s*|[-*]\s*)*'  # 可选的列表标记
            r'(?:\[.{0,20}\]\([^)]+\)\s*)+$'  # 一个或多个短链接
        )

        # 检查是否是导航性短文字行
        nav_text_patterns = [
            r'^更多.{0,5}$',
            r'^返回.{0,5}$',
            r'^更多新闻>$',
            r'^返回>>$',
            r'^跳过导航栏$',
            r'^\[?\d{1,2}[:：]\d{2}\]?$.*',  # 纯时间
        ]

        is_nav_link_line = bool(link_only_pattern.match(stripped))
        is_nav_text = any(re.match(p, stripped) for p in nav_text_patterns)

        # 统计行内链接数和纯文本比例
        links_in_line = re.findall(r'\[([^\]]*)\]\([^)]+\)', stripped)
        if links_in_line:
            link_text_total = sum(len(t) for t in links_in_line)
            # 去掉链接后的纯文本
            non_link_text = re.sub(r'\[[^\]]*\]\([^)]+\)', '', stripped)
            non_link_text = re.sub(r'[\d\.\-\*\s|·>]+', '', non_link_text)
            # 如果去掉链接和分隔符后几乎没剩什么文本，且链接文本都很短
            if len(non_link_text) < 5 and link_text_total > 0:
                avg_link_len = link_text_total / len(links_in_line)
                if avg_link_len < 15 and len(links_in_line) >= 2:
                    is_nav_link_line = True

        if is_nav_link_line or is_nav_text:
            # 跳过这一行（不加入 cleaned）
            i += 1
            continue

        cleaned.append(line)
        i += 1

    result = '\n'.join(cleaned)
    # 清理可能产生的连续空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def extract_main_content_html(raw_html: str) -> Optional[str]:
    """从普通网页中尽量提取正文区域，作为智能正文的通用兜底。"""
    if not raw_html:
        return None

    soup = BeautifulSoup(raw_html, "html.parser")
    _remove_noise_elements(soup)

    selectors = [
        "article",
        "main",
        ".article",
        ".article-content",
        ".article_body",
        ".article-body",
        ".post-content",
        ".post-body",
        ".entry-content",
        ".rich_media_content",
        ".news-content",
        ".news_body",
        ".detail-content",
        ".text-content",
        "#article",
        "#content",
        "#main",
        "#article-content",
    ]

    candidates = []
    for selector in selectors:
        found = soup.select(selector)
        for node in found:
            # 排除太小的节点
            if len(node.get_text(" ", strip=True)) >= 80:
                candidates.append(node)

    if not candidates:
        candidates = soup.find_all(["section", "div"], limit=300)

    best = None
    best_score = 0
    for node in candidates:
        # 跳过已被 decompose 的节点
        if node.parent is None and node.name not in ("html", "body"):
            continue
        text = node.get_text(" ", strip=True)
        if len(text) < 80:
            continue

        # 统计段落和链接
        paragraphs = node.find_all(["p", "h1", "h2", "h3", "h4", "blockquote"])
        paragraph_count = len(paragraphs)
        links = node.find_all("a")
        link_text_len = sum(len(a.get_text(" ", strip=True)) for a in links)
        text_len = len(text)
        link_penalty = link_text_len / max(text_len, 1)

        # 段落平均文本长度（正文段落通常较长，导航通常较短）
        para_avg_len = 0
        if paragraphs:
            para_avg_len = sum(len(p.get_text(" ", strip=True)) for p in paragraphs) / paragraph_count

        # 评分：文本长度 + 段落数权重 + 段落平均长度奖励 - 链接密度惩罚
        score = (
            text_len
            + paragraph_count * 100
            + int(para_avg_len) * 5
            - int(link_penalty * 500)
            - len(links) * 10  # 链接越多越可能是导航
        )
        if score > best_score:
            best = node
            best_score = score

    if best is None:
        return None

    # 对选中的节点再做一次噪音清理（可能有嵌套的导航）
    best_copy = BeautifulSoup(str(best), "html.parser")
    _remove_noise_elements(best_copy)

    title = soup.find("h1") or soup.find("title")
    title_html = ""
    if title:
        title_text = title.get_text(" ", strip=True)
        best_text = best_copy.get_text(" ", strip=True)
        if title_text and title_text not in best_text[:300]:
            title_html = f"<h1>{title_text}</h1>"

    return f"<article>{title_html}{str(best_copy)}</article>"


def _replace_image_urls_for_web(
    markdown_text: str, task_id: str, output_dir: Path
) -> str:
    """将 Markdown 中的本地图片路径替换为 /api/files/{task_id}/... 可访问链接。"""
    if not isinstance(markdown_text, str) or not task_id:
        return markdown_text

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}

    def _path_to_public_url(image_src: str) -> Optional[str]:
        image_src = image_src.strip()
        if not image_src:
            return None
        suffix = Path(image_src.split("?")[0]).suffix.lower()
        if suffix not in image_extensions:
            return None
        resolved = (output_dir / image_src).resolve(strict=False)
        if not resolved.is_file():
            return None
        rel = str(resolved.relative_to(output_dir)).replace("\\", "/")
        return f"/api/files/{task_id}/{quote(rel, safe='/:')}"

    def replace_md(match: re.Match) -> str:
        alt_text = match.group("alt")
        image_src = match.group("src")
        public_url = _path_to_public_url(image_src)
        if public_url:
            return f"![{alt_text}]({public_url})"
        return match.group(0)

    return re.sub(
        r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)",
        replace_md,
        markdown_text,
    )


def _resolve_task_output_dir(request: Request, task_id: str) -> Path:
    """先从 URL/HTML 内存映射查找，再从 FastAPI task_manager 查找，
    最后回退到磁盘输出根目录。"""
    if task_id in _url_html_output_dirs:
        return _url_html_output_dirs[task_id]

    task_manager = getattr(request.app.state, "task_manager", None)
    if task_manager is not None:
        task = task_manager.get(task_id)
        if task is not None:
            return Path(task.output_dir)

    # 服务重启后 task_manager 为空，从磁盘回退查找
    fallback = _get_output_root() / task_id
    if fallback.is_dir():
        return fallback

    raise HTTPException(
        status_code=404,
        detail=(
            "任务不存在或已过期。\n\n"
            f"任务 ID：{task_id}\n\n"
            "可能原因：任务结果已被清理或服务已重启。\n\n"
            "建议：请重新进行转换。"
        ),
    )


@router.get("/config")
async def get_config() -> dict[str, Any]:
    output_root = _get_output_root()
    return {
        "output_root": str(output_root),
        "supported_suffixes": SUPPORTED_UPLOAD_SUFFIXES,
        "default_backend": DEFAULT_BACKEND,
        "default_effort": DEFAULT_HYBRID_EFFORT,
        "default_parse_method": "auto",
        "default_lang_list": ["ch"],
        "ocr_language_choices": PUBLIC_OCR_LANGUAGE_CHOICES,
        "default_max_pages": 99999,
    }


@router.post("/convert/url_html")
async def convert_url_html(
    source_url: Optional[str] = Form(None),
    html_content: Optional[str] = Form(None),
    html_file: Optional[UploadFile] = File(None),
    conversion_scope: str = Form("smart"),
) -> JSONResponse:
    """将 URL、HTML 片段或本地 HTML 文件转换为 Markdown。"""
    task_id = f"web_{time.strftime('%y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    run_root = _get_output_root() / "web" / task_id
    extract_root = run_root / "result"

    source_url = (source_url or "").strip()
    html_content = (html_content or "").strip()
    conversion_scope = conversion_scope if conversion_scope in {"smart", "full"} else "smart"
    html_file_path: Optional[Path] = None

    # Anti-bot session for TLS fingerprint impersonation (shared across page + image requests)
    anti_bot_session = _create_anti_bot_session()
    try:
        if html_file is not None and html_file.filename:
            safe_name = safe_stem(html_file.filename)
            local_md_dir = extract_root / safe_name
            local_md_dir.mkdir(parents=True, exist_ok=True)
            html_file_path = local_md_dir / "__input__.html"
            html_file_path.write_bytes(await html_file.read())
            raw_html = html_file_path.read_text(encoding="utf-8", errors="replace")
        elif html_content:
            safe_name = "html_snippet"
            local_md_dir = extract_root / safe_name
            local_md_dir.mkdir(parents=True, exist_ok=True)
            raw_html = html_content
        elif source_url:
            if source_url.startswith("<"):
                safe_name = "html_snippet"
                local_md_dir = extract_root / safe_name
                local_md_dir.mkdir(parents=True, exist_ok=True)
                raw_html = source_url
            else:
                safe_name = safe_stem_from_text(source_url)
                local_md_dir = extract_root / safe_name
                local_md_dir.mkdir(parents=True, exist_ok=True)

                # --- Anti-bot URL fetch: curl_cffi with Chrome TLS fingerprint ---
                response = None
                if anti_bot_session:
                    try:
                        response = await anti_bot_session.get(
                            source_url,
                            headers=_BROWSER_HEADERS,
                            timeout=30,
                            allow_redirects=True,
                        )
                        logger.info(f"curl_cffi fetch: status={response.status_code}, len={len(response.text)}")

                        # --- Anti-bot warmup: if 403, try session warming strategy ---
                        if response.status_code == 403:
                            logger.info("Got 403, attempting anti-bot session warmup...")
                            warmed = await _warmup_anti_bot_session(
                                anti_bot_session, source_url, _BROWSER_HEADERS
                            )
                            if warmed:
                                # Retry the original URL with warmed cookies
                                response = await anti_bot_session.get(
                                    source_url,
                                    headers={**_BROWSER_HEADERS, "Referer": f"https://{source_url.split('/')[2]}/"},
                                    timeout=30,
                                    allow_redirects=True,
                                )
                                logger.info(f"curl_cffi retry after warmup: status={response.status_code}, len={len(response.text)}")
                    except Exception as curl_exc:
                        logger.warning(f"curl_cffi request failed, falling back to httpx: {curl_exc}")
                        response = None

                if response is None:
                    # Fallback to httpx
                    async with httpx.AsyncClient(
                        timeout=build_http_timeout(),
                        follow_redirects=True,
                        headers=_BROWSER_HEADERS,
                    ) as client:
                        response = await client.get(source_url)

                # --- Friendly error for HTTP error status codes ---
                if response.status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"目标网站拒绝了访问（403 Forbidden）。\n\n"
                            f"URL: {source_url}\n\n"
                            f"常见原因：\n"
                            f"1. 该网站有反爬虫机制（如百度文库、知网等需要登录的网站）\n"
                            f"2. 该页面需要登录后才能查看\n"
                            f"3. 访问频率过高被临时限制\n\n"
                            f"建议：\n"
                            f"- 在浏览器中打开该页面，手动保存为 HTML 文件后上传转换\n"
                            f"- 或复制页面内容粘贴到输入框中转换"
                        ),
                    )
                elif response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail=(
                            f"目标页面需要登录才能访问（401 Unauthorized）。\n\n"
                            f"URL: {source_url}\n\n"
                            f"建议：请在浏览器中登录该网站后，手动保存页面为 HTML 文件再上传转换。"
                        ),
                    )
                elif response.status_code == 404:
                    raise HTTPException(
                        status_code=404,
                        detail=f"页面不存在（404 Not Found）。\n\nURL: {source_url}\n\n请检查 URL 是否正确。",
                    )
                elif response.status_code >= 400:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"目标网站返回错误（HTTP {response.status_code}）。\n\nURL: {source_url}\n\n建议：请尝试在浏览器中打开该页面，确认页面是否可正常访问。如可访问，请保存为 HTML 文件后上传转换。",
                    )

                # --- Playwright pre-check for JS-rendered / blocked pages ---
                # If the static HTML has very little visible text, the page is
                # likely JavaScript-rendered (SPA). Try Playwright to get the
                # fully rendered DOM before proceeding with extraction.
                _response_text = response.text
                _soup_check = BeautifulSoup(_response_text, "html.parser")
                for _tag in _soup_check(["script", "style", "noscript"]):
                    _tag.decompose()
                _visible_text = _soup_check.get_text(" ", strip=True)
                _blocked_markers = [
                    "百度安全验证", "安全验证", "人机验证", "验证码",
                    "Just a moment", "Checking your browser",
                    "Access Denied", "访问被拒绝",
                ]
                _needs_playwright = len(_visible_text) < 80 or any(
                    p in _response_text for p in _blocked_markers
                )

                _pw_used = False
                if _needs_playwright and source_url:
                    logger.info(
                        f"Static HTML has only {len(_visible_text)} chars of visible text, "
                        f"trying Playwright for JS rendering..."
                    )
                    _pw_html = await _fetch_with_playwright(source_url)
                    if _pw_html and len(_pw_html) > 1000:
                        logger.info(f"Playwright returned {len(_pw_html)} chars, using rendered HTML")
                        response_text = _pw_html
                        _pw_used = True
                    else:
                        response_text = _response_text
                else:
                    response_text = _response_text

                if conversion_scope == "smart":
                    # Playwright 已经提取了正文区域（.article-body 等），
                    # 跳过 extract_main_content_html 避免二次提取选错子区域
                    if _pw_used:
                        raw_html = (
                            extract_article_html_from_page(response_text)
                            or extract_textarea_article_html(response_text)
                            or response_text
                        )
                    else:
                        raw_html = (
                            extract_article_html_from_page(response_text)
                            or extract_textarea_article_html(response_text)
                            or extract_main_content_html(response_text)
                            or response_text
                        )
                else:
                    raw_html = response_text
        else:
            raise HTTPException(status_code=400, detail="No URL or HTML provided")

        images_dir = local_md_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        soup = BeautifulSoup(raw_html, "html.parser")
        remove_tags = ["script", "style", "noscript", "iframe"]
        if conversion_scope == "smart":
            remove_tags.extend(["nav", "footer", "aside", "header"])
        for tag in soup(remove_tags):
            tag.decompose()
        # 智能正文模式：额外清理导航、侧边栏、广告等噪音元素
        if conversion_scope == "smart":
            _remove_noise_elements(soup)

        # 展平嵌套的格式标签（<strong>/<b>/<em>/<i>），避免 markdownify 生成混乱的 ** 标记
        _flatten_nested_format_tags(soup)

        # --- Unwrap textarea-embedded article HTML ---
        # Some sites (e.g. huanqiu.com mobile) store the entire article body
        # as escaped HTML inside <textarea class="article-content">. Because
        # BeautifulSoup treats textarea content as plain text, the <img> tags
        # inside are invisible to find_all("img") and markdownify outputs them
        # as literal text. Decode and inject them back into the DOM so images
        # are picked up by the download logic.
        for textarea in soup.find_all("textarea"):
            classes = textarea.get("class", [])
            if isinstance(classes, str):
                classes = classes.split()
            cls_str = " ".join(classes).lower()
            if not any(kw in cls_str for kw in ("article-content", "article-body", "content")):
                continue
            raw_inner = textarea.get_text("", strip=False)
            if not raw_inner or "<" not in raw_inner:
                continue
            decoded = unescape(raw_inner)
            try:
                inner_soup = BeautifulSoup(decoded, "html.parser")
            except Exception:
                continue
            # Only replace if the decoded content actually contains tags
            if inner_soup.find(True) is not None:
                textarea.replace_with(inner_soup)

        # --- Resolve lazy-loaded image URLs ---
        # Many sites store the real image URL in data-src / data-original /
        # data-lazy-src and keep `src` as a tiny placeholder. Move the real
        # URL back into `src` so the downstream image download can fetch it.
        _LAZY_SRC_ATTRS = (
            "data-src",
            "data-original",
            "data-lazy-src",
            "data-echo",
            "data-url",
            "data-img",
            "data-srcset",
        )
        for img_tag in soup.find_all("img"):
            current_src = (img_tag.get("src") or "").strip()
            # Skip if src is already a valid http(s) URL
            if current_src.startswith(("http://", "https://")):
                continue
            for attr in _LAZY_SRC_ATTRS:
                lazy_value = (img_tag.get(attr) or "").strip()
                if lazy_value:
                    # data-srcset may be "url 1x, url 2x" — take first
                    first_url = lazy_value.split(",")[0].strip().split(" ")[0].strip()
                    if first_url:
                        img_tag["src"] = first_url
                        break

        # --- Concurrent image download with limits ---
        # Collect all img tags first
        all_imgs = soup.find_all("img")
        MAX_IMAGES = 100  # safety cap to prevent runaway downloads
        img_semaphore = asyncio.Semaphore(5)  # max 5 concurrent downloads
        img_counter = {"n": 0}  # mutable counter for naming
        img_timeout = httpx.Timeout(10.0, connect=5.0)  # per-image timeout (shorter)

        async def _download_one(img_tag):
            """Download a single image; returns (img_tag, local_filename) on success."""
            src = img_tag.get("src")
            if not src:
                return None
            img_url = src
            base_url = source_url or ""
            if base_url:
                img_url = urljoin(base_url, src)
            if not img_url:
                return None
            # Skip data URIs
            if img_url.startswith("data:"):
                return None
            img_ext = Path(img_url.split("?")[0]).suffix.lower()
            if img_ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
                img_ext = ".png"
            async with img_semaphore:
                try:
                    if img_url.startswith("http://") or img_url.startswith("https://"):
                        img_headers = {**_IMAGE_HEADERS, "Referer": source_url or ""}
                        img_response = None
                        # Use anti-bot session (shared cookies + TLS fingerprint) if available
                        if anti_bot_session:
                            try:
                                img_response = await anti_bot_session.get(
                                    img_url,
                                    headers=img_headers,
                                    timeout=10,
                                    allow_redirects=True,
                                )
                                img_response.raise_for_status()
                            except Exception:
                                img_response = None
                        # Fallback to httpx
                        if img_response is None:
                            async with httpx.AsyncClient(
                                timeout=img_timeout,
                                follow_redirects=True,
                                headers=img_headers,
                            ) as img_client:
                                img_response = await img_client.get(img_url)
                                img_response.raise_for_status()
                    elif html_file_path and Path(img_url).is_absolute() and Path(img_url).is_file():
                        local_bytes = Path(img_url).read_bytes()
                    elif html_file_path:
                        candidate = html_file_path.parent / img_url
                        if candidate.is_file():
                            local_bytes = candidate.read_bytes()
                        else:
                            return None
                    else:
                        return None
                    img_counter["n"] += 1
                    img_name = f"img_{img_counter['n']:04d}{img_ext}"
                    local_img_path = images_dir / img_name
                    if img_url.startswith("http"):
                        local_img_path.write_bytes(img_response.content)
                    else:
                        local_img_path.write_bytes(local_bytes)
                    return (img_tag, f"images/{img_name}")
                except Exception as img_exc:
                    logger.warning(f"Failed to download image {img_url}: {img_exc}")
                    return None

        # Process images with cap
        download_tasks = [_download_one(img) for img in all_imgs[:MAX_IMAGES]]
        if download_tasks:
            results = await asyncio.gather(*download_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception) or r is None:
                    continue
                img_tag, local_src = r
                img_tag["src"] = local_src
        if len(all_imgs) > MAX_IMAGES:
            logger.warning(f"Image cap reached: {len(all_imgs)} images found, only first {MAX_IMAGES} downloaded")

        md_content = markdownify.markdownify(str(soup), heading_style="ATX")

        # --- Clean VitePress / doc-framework artifacts from Markdown output ---

        # 1. Clean anchor links in headings.
        #    VuePress/Docusaurus wrap heading text in <a class="header-anchor">,
        #    which markdownify converts to "## [Title](#id)".
        #    We need to unwrap the link text, not delete it.

        # 1a. Heading is ENTIRELY a link: "## [Title](#id)" → "## Title"
        md_content = re.sub(
            r'^(#{1,6}\s+)\[(.+?)\]\(#[^)]*\)\s*$',
            r'\1\2',
            md_content,
            flags=re.MULTILINE,
        )
        # 1b. Invisible prefix link: "## ​[](id) Title" → "## Title"
        #     Only strip if link content is empty/zero-width chars
        md_content = re.sub(
            r'^(#{1,6}\s+)\[[\u200b\u200d\ufeff\s]*\]\(#[^)]*\)\s+(?=\S)',
            r'\1',
            md_content,
            flags=re.MULTILINE,
        )
        # 1c. Invisible suffix link: "## Title ​[](id)" → "## Title"
        #     Only strip if link content is empty/zero-width chars
        md_content = re.sub(
            r'^(#{1,6}\s+.+?)\s+\[[\u200b\u200d\ufeff\s]*\]\(#[^)]*\)\s*$',
            r'\1',
            md_content,
            flags=re.MULTILINE,
        )

        # 2. Remove stray zero-width characters from entire document.
        md_content = md_content.replace('\u200b', '').replace('\u200d', '').replace('\ufeff', '')

        # 3. Remove "Edit this page" / "Edit on GitHub" links (doc site UI).
        md_content = re.sub(
            r'^\[Edit this .+?\]\(https?://[^)]+\)\s*$',
            '',
            md_content,
            flags=re.MULTILINE,
        )

        # 4. Remove trailing keyboard shortcut hints (e.g. "⌘I" on a line by itself).
        md_content = re.sub(
            r'^(?:[⌘⇧⌥⎋]\w)\s*$',
            '',
            md_content,
            flags=re.MULTILINE,
        )

        # 5. Clean up excessive blank lines (3+ → 2).
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)

        # 6. Strip trailing whitespace on every line.
        md_content = '\n'.join(line.rstrip() for line in md_content.split('\n'))

        # 7. Remove trailing single-line site-internal navigation links
        #    (e.g. "[Next Page](/docs/next)" alone at the end of the document).
        md_content = re.sub(
            r'\n\n\[.*?\]\(/[^)]+\)\s*$',
            '',
            md_content,
        )

        # 8. Smart mode: post-Markdown navigation cleanup
        if conversion_scope == "smart":
            md_content = _cleanup_navigation_from_markdown(md_content)

        # 9. Remove leaked HTML style/script/pre blocks (belt-and-suspenders)
        md_content = re.sub(r'<style[^>]*>.*?</style>', '', md_content, flags=re.DOTALL | re.IGNORECASE)
        md_content = re.sub(r'<script[^>]*>.*?</script>', '', md_content, flags=re.DOTALL | re.IGNORECASE)

        # 10. Fix malformed bold markers from nested <strong> tags
        #     e.g. "**text1**text2**text3******" → "**text1** **text2** **text3**"
        #     Collapse 3+ consecutive asterisks to 2
        md_content = re.sub(r'\*{3,}', '**', md_content)
        #     Clean up "****" empty bold markers
        md_content = md_content.replace('****', '')
        #     Merge adjacent bold segments: "**text1** **text2**" → "**text1 text2**"
        md_content = re.sub(r'\*\*\s*\*\*', ' ', md_content)
        #     Remove ** that spans across paragraphs (bold should not cross blank lines)
        #     Pattern: ** at end of a line, followed by blank line(s) → remove the **
        md_content = re.sub(r'\*\*(\s*\n\s*\n)', r'\1', md_content)
        #     Pattern: ** at start of a line that follows a blank line → remove the **
        md_content = re.sub(r'(\n\s*\n)\*\*', r'\1', md_content)
        #     Remove orphan ** at the very start or end of the document
        md_content = re.sub(r'^\*\*', '', md_content)
        md_content = re.sub(r'\*\*$', '', md_content)

        # 11. Final cleanup of excessive blank lines
        md_content = re.sub(r'\n{3,}', '\n\n', md_content)
        md_content = md_content.strip() + '\n'

        # 11. Content validation — detect empty / JS-rendered / blocked pages
        _plain_text = re.sub(r'[\s#>*\-\[\]()!|`]', '', md_content)

        # Detect anti-bot / security verification pages (e.g. Baidu Wenku)
        _blocked_patterns = [
            "百度安全验证", "安全验证", "人机验证", "验证码",
            "Just a moment", "Checking your browser",
            "Access Denied", "访问被拒绝",
        ]
        _is_blocked = any(p in md_content for p in _blocked_patterns)

        if len(_plain_text) < 80 or _is_blocked:
            if source_url:
                _pw_note = ""
                if _PLAYWRIGHT_AVAILABLE:
                    _pw_note = (
                        f"\n\n系统已尝试使用浏览器引擎渲染页面，但仍未能提取到有效内容。\n"
                        f"这通常意味着该页面需要登录、有较强的反爬虫机制、或内容确实为空。"
                    )
                else:
                    _pw_note = (
                        f"\n\n提示：系统未安装浏览器引擎（Playwright），无法渲染 JavaScript 动态页面。"
                    )
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"未能从页面中提取到有效内容。\n\n"
                        f"URL: {source_url}\n\n"
                        f"常见原因：\n"
                        f"1. 该页面是 JavaScript 动态渲染的（如 MSN、知乎等 SPA 网站），正文不在 HTML 源码中\n"
                        f"2. 该页面需要登录才能查看完整内容\n"
                        f"3. 该页面被反爬虫机制拦截（如百度文库、知网等）\n"
                        f"{_pw_note}\n\n"
                        f"建议：\n"
                        f"- 在浏览器中打开该页面，手动保存为 HTML 文件后上传转换\n"
                        f"- 或复制页面内容粘贴到输入框中转换"
                    ),
                )
            else:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"未能从 HTML 中提取到有效内容。\n\n"
                        f"可能原因：\n"
                        f"1. HTML 内容为空或仅包含脚本/样式代码\n"
                        f"2. 正文内容被 JavaScript 动态渲染\n\n"
                        f"建议：请确认 HTML 内容包含正文，或尝试使用完整页面 HTML。"
                    ),
                )

        md_path = local_md_dir / f"{safe_name}.md"
        md_path.write_text(md_content, encoding="utf-8")

        archive_zip_path = run_root / f"{safe_name}.zip"
        output_path = resolve_output_path_for_download(local_md_dir, archive_zip_path, safe_name)
        if output_path == str(archive_zip_path):
            compress_directory_to_zip(local_md_dir, archive_zip_path)

        _url_html_output_dirs[task_id] = local_md_dir

        preview_md_content = _replace_image_urls_for_web(md_content, task_id, local_md_dir)

        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": "completed",
                "message": STATUS_COMPLETED,
                "md_content": preview_md_content,
                "txt_content": md_content,
                "content_list_json": "",
                "output_path": output_path,
                "output_dir": str(local_md_dir),
                "has_images": directory_has_images(local_md_dir),
                "safe_name": safe_name,
                "conversion_scope": conversion_scope,
            },
        )
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail=(
                f"请求目标网站超时。\n\nURL: {source_url}\n\n"
                f"可能原因：网站响应过慢或网络连接不稳定。\n"
                f"建议：请稍后重试，或在浏览器中打开页面后保存为 HTML 文件上传转换。"
            ),
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail=(
                f"无法连接到目标网站。\n\nURL: {source_url}\n\n"
                f"可能原因：网址错误、网站已下线、或网络不通。\n"
                f"建议：请检查 URL 是否正确，或确认网络连接正常后重试。"
            ),
        )
    except Exception as exc:
        logger.exception(exc)
        # Check if it's an httpx HTTPStatusError from image download
        exc_str = str(exc)
        if "403" in exc_str or "Forbidden" in exc_str:
            raise HTTPException(
                status_code=403,
                detail=f"部分资源被目标网站拒绝访问（403）。\n\nURL: {source_url}\n\n建议：请在浏览器中打开该页面，保存为 HTML 文件后上传转换。",
            )
        raise HTTPException(status_code=500, detail=f"URL/HTML conversion failed: {exc}")
    finally:
        # Clean up anti-bot session
        if anti_bot_session:
            try:
                await anti_bot_session.close()
            except Exception:
                pass


@router.get("/files/{task_id}/{path:path}")
async def get_result_file(task_id: str, path: str, request: Request) -> FileResponse:
    """安全地返回任务结果目录中的文件，主要用于 Markdown 图片预览。"""
    output_dir = _resolve_task_output_dir(request, task_id)
    target = (output_dir / path).resolve(strict=False)
    # 防止越界访问
    try:
        target.relative_to(output_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="禁止访问该路径。") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在或已被清理。")
    return FileResponse(path=target)


@router.get("/download/{task_id}")
async def download_url_html_result(task_id: str, request: Request) -> FileResponse:
    """下载 URL/HTML 转换结果；有图片时返回扁平化 ZIP，无图片时返回单个 Markdown。"""
    output_dir = _resolve_task_output_dir(request, task_id)
    md_files = sorted(output_dir.glob("*.md"))
    if not md_files:
        raise HTTPException(
            status_code=404,
            detail=(
                "未找到可下载的 Markdown 文件。\n\n"
                f"任务 ID：{task_id}\n\n"
                "可能原因：转换结果已被清理或转换未完成。\n\n"
                "建议：请重新转换后再次尝试下载。"
            ),
        )

    if directory_has_images(output_dir):
        archive_zip_path = output_dir.parent.parent / f"{output_dir.name}.zip"
        temp_zip_path = archive_zip_path.with_suffix(".tmp.zip")
        if temp_zip_path.exists():
            temp_zip_path.unlink()
        if not compress_directory_to_zip(output_dir, temp_zip_path):
            raise HTTPException(
                status_code=500,
                detail=(
                    "创建下载压缩包失败。\n\n"
                    "可能原因：磁盘空间不足或文件被占用。\n\n"
                    "建议：请关闭可能占用该文件的程序后重试，或检查磁盘空间。"
                ),
            )
        temp_zip_path.replace(archive_zip_path)
        return FileResponse(path=archive_zip_path, filename=archive_zip_path.name)

    return FileResponse(path=md_files[0], filename=md_files[0].name)


@router.get("/preview/{task_id}")
async def get_preview_pdf(task_id: str, request: Request) -> FileResponse:
    """返回任务结果目录中的 layout PDF 或 origin PDF 用于预览。"""
    output_dir = _resolve_task_output_dir(request, task_id)

    # 尝试推断 stem：递归查找 .md 文件
    md_files = list(output_dir.rglob("*.md"))
    if not md_files:
        raise HTTPException(status_code=404, detail="未找到 Markdown 文件，无法预览。")
    md_file = md_files[0]
    stem = md_file.stem
    md_dir = md_file.parent

    for suffix in ("_layout.pdf", "_origin.pdf"):
        candidate = md_dir / f"{stem}{suffix}"
        if candidate.is_file():
            return FileResponse(path=candidate)

    return Response(status_code=204)


@router.post("/open-output-dir")
async def open_output_dir(payload: dict[str, str]) -> PlainTextResponse:
    """在系统文件管理器中打开输出目录（仅本地可用）。"""
    dir_path = payload.get("output_dir", "").strip()
    if not dir_path:
        raise HTTPException(status_code=400, detail="输出目录参数为空，无法打开。")
    target = Path(dir_path)
    if target.is_file():
        target = target.parent
    if not target.is_dir():
        raise HTTPException(
            status_code=404,
            detail=(
                "输出目录不存在。\n\n"
                f"目录路径：{dir_path}\n\n"
                "可能原因：目录已被删除或移动。\n\n"
                "建议：请重新转换文件生成新的输出目录。"
            ),
        )
    abs_path = str(target.resolve())
    try:
        if sys.platform == "win32":
            os.startfile(abs_path)
        else:
            import subprocess

            subprocess.run(["xdg-open", abs_path], check=False)
    except Exception as exc:
        logger.warning(f"Failed to open output directory {abs_path}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=(
                f"打开目录失败。\n\n"
                f"目录路径：{abs_path}\n\n"
                f"错误详情：{exc}\n\n"
                "建议：请手动复制路径到文件管理器中打开。"
            ),
        )
    return PlainTextResponse(content=abs_path)
