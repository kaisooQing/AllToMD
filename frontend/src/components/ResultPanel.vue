<template>
  <section class="result-panel">
    <div class="panel-header">{{ $t('result.title') }}</div>

    <div v-if="!store.currentMdContent && !store.currentOutputPath" class="empty-result">
      {{ $t('result.noResult') }}
    </div>

    <template v-else>
      <el-tabs v-model="activeTab" type="border-card" class="result-tabs">
        <el-tab-pane :label="$t('result.mdRender')" name="render">
          <div class="tab-content markdown-body" v-html="renderedMd" />
        </el-tab-pane>
        <el-tab-pane :label="$t('result.mdText')" name="text">
          <el-input
            v-model="store.currentTxtContent"
            type="textarea"
            readonly
            resize="none"
            class="tab-content raw-text"
          />
        </el-tab-pane>
        <el-tab-pane :label="$t('result.contentList')" name="json">
          <el-input
            v-model="displayJson"
            type="textarea"
            readonly
            resize="none"
            class="tab-content raw-text"
          />
        </el-tab-pane>
      </el-tabs>

      <div class="result-actions">
        <el-button type="primary" :icon="Download" @click="downloadResult">
          {{ downloadButtonText }}
        </el-button>
        <el-button :icon="CopyDocument" @click="copyCurrentContent">
          {{ copyButtonText }}
        </el-button>
      </div>

      <div v-if="store.currentOutputDir" class="output-dir">
        <span class="dir-label">{{ $t('result.outputDir') }}：</span>
        <span class="dir-path" :title="store.currentOutputDir">{{ store.currentOutputDir }}</span>
        <el-button size="small" link :icon="FolderOpened" @click="openDir">
          {{ $t('result.openDir') }}
        </el-button>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue'
import JSZip from 'jszip'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, CopyDocument, FolderOpened } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { renderMarkdown } from '@/utils/markdown'
import { getTaskResult, getUrlHtmlResultDownload, openOutputDir } from '@/api/mineru'

const store = useAppStore()
const activeTab = ref('render')

const renderedMd = computed(() => renderMarkdown(store.currentMdContent))

const displayJson = computed(() => {
  if (!store.currentContentListJson) return ''
  try {
    return JSON.stringify(JSON.parse(store.currentContentListJson), null, 2)
  } catch {
    return store.currentContentListJson
  }
})

const currentBaseName = computed(() => {
  const name = store.currentFileName || 'result'
  return name.replace(/\.[^.]+$/, '') || 'result'
})

const hasPackageResources = computed(() =>
  store.currentHasImages || hasLocalResourceRefs(store.currentTxtContent || store.currentMdContent)
)

const currentDownload = computed(() => {
  if (activeTab.value === 'json') {
    return {
      label: '下载 JSON',
      copyLabel: '复制 JSON',
      content: displayJson.value,
      filename: `${currentBaseName.value}_content_list.json`,
      mimeType: 'application/json;charset=utf-8',
      emptyMessage: '当前没有 JSON 内容',
      copiedMessage: 'JSON 已复制',
    }
  }

  if (activeTab.value === 'text') {
    return {
      label: '下载 Markdown 原文',
      copyLabel: '复制 Markdown 原文',
      content: store.currentTxtContent || store.currentMdContent,
      filename: `${currentBaseName.value}.md`,
      mimeType: 'text/markdown;charset=utf-8',
      emptyMessage: '当前没有 Markdown 原文内容',
      copiedMessage: 'Markdown 原文已复制',
    }
  }

  if (hasPackageResources.value) {
    return {
      label: '下载完整 Markdown',
      copyLabel: '复制 Markdown',
      content: store.currentTxtContent || store.currentMdContent,
      filename: `${currentBaseName.value}_完整Markdown.zip`,
      mimeType: 'application/zip',
      emptyMessage: '当前没有可下载的转换结果',
      copiedMessage: 'Markdown 已复制',
      packageDownload: true,
    }
  }

  return {
    label: '下载 Markdown',
    copyLabel: '复制 Markdown',
    content: store.currentTxtContent || store.currentMdContent,
    downloadContent: normalizeMarkdownForDownload(store.currentTxtContent || store.currentMdContent),
    filename: `${currentBaseName.value}.md`,
    mimeType: 'text/markdown;charset=utf-8',
    emptyMessage: '当前没有 Markdown 内容',
    copiedMessage: 'Markdown 已复制',
  }
})

const downloadButtonText = computed(() => currentDownload.value.label)
const copyButtonText = computed(() => currentDownload.value.copyLabel)

function isLocalResourceUrl(src) {
  const cleanSrc = String(src || '')
    .trim()
    .replace(/^['"]|['"]$/g, '')
    .split('?')[0]
    .split('#')[0]

  if (!cleanSrc || cleanSrc.startsWith('#')) return false
  if (/^(https?:|mailto:|tel:|data:|blob:)/i.test(cleanSrc)) return false
  // Absolute paths starting with / are website paths (e.g. /zh-Hans/docs/cid7), not local files
  if (cleanSrc.startsWith('/')) return false
  if (/^\.{1,2}\//.test(cleanSrc)) return true
  // Relative paths like images/img_001.jpg (no leading /, ., or protocol)
  if (cleanSrc.includes('/')) return true
  return /\.(png|jpe?g|gif|webp|svg|bmp|tiff?|pdf|docx?|pptx?|xlsx?|csv|json|zip|html?|md)$/i.test(cleanSrc)
}

function hasLocalResourceRefs(markdown) {
  if (!markdown) return false
  const mdRefReg = /!\[[^\]]*]\(([^)]+)\)|\[[^\]]+]\(([^)]+)\)/g
  const htmlRefReg = /<(?:img|a)\b[^>]*(?:src|href)=["']([^"']+)["']/gi
  let match

  while ((match = mdRefReg.exec(markdown))) {
    if (isLocalResourceUrl(match[1] || match[2])) return true
  }

  while ((match = htmlRefReg.exec(markdown))) {
    if (isLocalResourceUrl(match[1])) return true
  }

  return false
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function downloadTextFile(content, filename, mimeType) {
  downloadBlob(new Blob([content], { type: mimeType }), filename)
}

function escapeMarkdownTableCell(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/\|/g, '\\|')
    .trim()
}

function unwrapFencedHtmlTables(content) {
  return String(content || '').replace(
    /```(?:html)?\s*([\s\S]*?)```/gi,
    (match, html) => {
      if (/<table[\s>]|<tr[\s>]/i.test(html)) {
        return `\n\n${html.trim()}\n\n`
      }
      return match
    }
  )
}

function tableElementToMarkdown(table) {
  const rows = Array.from(table.querySelectorAll('tr'))
    .map((row) => Array.from(row.querySelectorAll('th,td')).map((cell) => escapeMarkdownTableCell(cell.textContent)))
    .filter((cells) => cells.length)

  if (!rows.length) return ''

  const columnCount = Math.max(...rows.map((row) => row.length))
  const normalizedRows = rows.map((row) => {
    const nextRow = [...row]
    while (nextRow.length < columnCount) nextRow.push('')
    return nextRow
  })

  const header = normalizedRows[0]
  const body = normalizedRows.slice(1)
  const separator = Array.from({ length: columnCount }, () => '---')
  const toLine = (cells) => `| ${cells.join(' | ')} |`
  return [toLine(header), toLine(separator), ...body.map(toLine)].join('\n')
}

function normalizeMarkdownForDownload(content) {
  if (!content || !/<table[\s>]|<tr[\s>]|```html/i.test(content)) return content || ''

  const htmlContent = unwrapFencedHtmlTables(content)
  const container = document.createElement('div')
  container.innerHTML = htmlContent
  const tables = Array.from(container.querySelectorAll('table'))
  if (!tables.length && /<tr[\s>]/i.test(content)) {
    const wrapper = document.createElement('table')
    wrapper.innerHTML = htmlContent
    const markdownTable = tableElementToMarkdown(wrapper)
    return markdownTable || htmlContent
  }
  if (!tables.length) return htmlContent

  tables.forEach((table) => {
    const markdownTable = tableElementToMarkdown(table)
    if (markdownTable) {
      table.replaceWith(document.createTextNode(`\n\n${markdownTable}\n\n`))
    }
  })

  return container.innerHTML
}

function normalizeMarkdownForRenderedHtml(content) {
  return unwrapFencedHtmlTables(content || '')
}

function buildRenderedHtmlDocument(markdownContent, title = 'Markdown Render') {
  const html = renderMarkdown(normalizeMarkdownForRenderedHtml(markdownContent || ''))
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${String(title).replace(/[<>&"]/g, '')}</title>
  <style>
    body { margin: 0; padding: 24px; font-family: "Microsoft YaHei", Arial, sans-serif; color: #0f172a; }
    .markdown-body { max-width: none; overflow-x: auto; }
    .markdown-body img { max-width: 100%; border-radius: 8px; }
    .markdown-body table { border-collapse: collapse; width: max-content; min-width: 100%; max-width: none; margin: 12px 0; }
    .markdown-body th, .markdown-body td { border: 1px solid #e2e8f0; padding: 8px 12px; min-width: 120px; max-width: 720px; vertical-align: top; line-height: 1.6; white-space: normal; word-break: normal; overflow-wrap: break-word; }
    .markdown-body th { font-weight: 700; }
    .markdown-body pre { padding: 12px; border-radius: 8px; overflow-x: auto; }
    .markdown-body code { font-family: Consolas, monospace; font-size: 12px; }
  </style>
</head>
<body>
  <div class="markdown-body">${html}</div>
</body>
</html>`
}

async function isZipBlob(blob) {
  const header = new Uint8Array(await blob.slice(0, 4).arrayBuffer())
  return header[0] === 0x50 && header[1] === 0x4b
}

async function flattenMarkdownZip(sourceBlob) {
  const inputZip = await JSZip.loadAsync(sourceBlob)
  const outputZip = new JSZip()
  const files = inputZip.files
  const mdPath = Object.keys(files).find((path) => path.toLowerCase().endsWith('.md'))

  if (!mdPath) return sourceBlob

  const mdDir = mdPath.includes('/') ? mdPath.slice(0, mdPath.lastIndexOf('/')) : ''
  const mdDirPrefix = mdDir ? `${mdDir}/` : ''
  let hasAddedFile = false

  for (const [relativePath, file] of Object.entries(files)) {
    if (file.dir) continue
    if (mdDirPrefix && !relativePath.startsWith(mdDirPrefix)) continue

    const targetPath = mdDirPrefix ? relativePath.slice(mdDirPrefix.length) : relativePath
    if (!targetPath) continue

    if (targetPath.toLowerCase().endsWith('.md')) {
      // 优先使用当前 store 中保存的文本内容，确保和历史记录显示的一致
      const mdText = store.currentTxtContent || store.currentMdContent || await file.async('text')
      outputZip.file(targetPath, normalizeMarkdownForDownload(mdText))
    } else {
      outputZip.file(targetPath, await file.async('blob'))
    }
    hasAddedFile = true
  }

  const normalizedMdPath = mdDirPrefix ? mdPath.slice(mdDirPrefix.length) : mdPath
  const renderedHtmlPath = normalizedMdPath.replace(/\.md$/i, '_渲染版.html')
  // 优先使用当前 store 中保存的文本内容，确保和历史记录显示的一致
  const renderedMdSource = store.currentTxtContent || store.currentMdContent || await files[mdPath].async('text')
  outputZip.file(renderedHtmlPath, buildRenderedHtmlDocument(renderedMdSource, currentBaseName.value))

  if (!hasAddedFile) return sourceBlob
  return outputZip.generateAsync({ type: 'blob' })
}

async function downloadResult() {
  const current = currentDownload.value
  if (current.packageDownload) {
    if (!store.currentTaskId) {
      ElMessage.warning('当前没有可下载的完整 Markdown')
      return
    }
    try {
      const response = store.currentTaskId.startsWith('web_')
        ? await getUrlHtmlResultDownload(store.currentTaskId)
        : await getTaskResult(store.currentTaskId)
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: current.mimeType })
      if (!(await isZipBlob(blob))) {
        // Backend returned a .md file instead of ZIP (no images on disk).
        // Fall back to downloading as a single .md file.
        const mdFilename = `${currentBaseName.value}.md`
        const mdContent = current.content
          ? normalizeMarkdownForDownload(current.content)
          : await blob.text()
        downloadTextFile(mdContent, mdFilename, 'text/markdown;charset=utf-8')
        ElMessage.info('当前结果无图片，已下载为单个 Markdown 文件')
        return
      }
      const downloadBlobData = store.currentTaskId.startsWith('web_')
        ? blob
        : await flattenMarkdownZip(blob)
      downloadBlob(downloadBlobData, current.filename)
    } catch (e) {
      const status = e?.response?.status
      const msg = _extractDownloadError(e)
      // 任务不存在或已过期时，降级为下载当前保存的文本内容
      if (status === 404 || msg.includes('任务不存在') || msg.includes('已过期') || msg.includes('not found')) {
        const mdContent = store.currentTxtContent || store.currentMdContent
        if (mdContent) {
          const mdFilename = `${currentBaseName.value}.md`
          downloadTextFile(normalizeMarkdownForDownload(mdContent), mdFilename, 'text/markdown;charset=utf-8')
          ElMessage.info('服务器端文件已清理，已下载当前保存的 Markdown 文本')
          return
        }
      }
      if (msg.includes('\n')) {
        ElMessageBox.alert(msg.replace(/\n/g, '<br>'), '下载失败', {
          dangerouslyUseHTMLString: true,
          confirmButtonText: '知道了',
          customClass: 'error-detail-msgbox',
        })
      } else {
        ElMessage.error(msg)
      }
    }
    return
  }

  if (!current.content) {
    ElMessage.warning(current.emptyMessage)
    return
  }
  downloadTextFile(current.downloadContent ?? current.content, current.filename, current.mimeType)
}

async function copyCurrentContent() {
  const current = currentDownload.value
  if (!current.content) {
    ElMessage.warning(current.emptyMessage)
    return
  }
  try {
    await navigator.clipboard.writeText(current.content)
    ElMessage.success(current.copiedMessage)
  } catch {
    ElMessage.error('复制失败')
  }
}

async function openDir() {
  if (!store.currentOutputDir) return
  try {
    await openOutputDir(store.currentOutputDir)
  } catch (e) {
    const msg = _extractDownloadError(e, '打开目录')
    if (msg.includes('\n')) {
      ElMessageBox.alert(msg.replace(/\n/g, '<br>'), '打开目录失败', {
        dangerouslyUseHTMLString: true,
        confirmButtonText: '知道了',
        customClass: 'error-detail-msgbox',
      })
    } else {
      ElMessage.error(msg)
    }
  }
}

function _extractDownloadError(e, action = '下载') {
  // 网络错误
  if (e?.code === 'ERR_NETWORK' || e?.message?.includes('Network Error')) {
    return `无法连接到转换服务，${action}失败。\n\n可能原因：服务未启动或网络异常。\n建议：请检查软件是否正常运行。`
  }
  if (e?.code === 'ECONNABORTED' || e?.message?.includes('timeout')) {
    return `${action}请求超时。\n\n可能原因：文件较大或服务器负载过高。\n建议：请稍后重试。`
  }

  const status = e?.response?.status
  const data = e?.response?.data
  let detail = ''
  if (data) {
    if (data.detail) detail = String(data.detail)
    else if (data.message) detail = String(data.message)
    else { try { detail = JSON.stringify(data) } catch { detail = String(data) } }
  }

  if (status === 404) {
    return `${action}失败：文件不存在或已过期。\n\n可能原因：结果文件已被清理或服务已重启。\n建议：请重新转换后再次尝试${action}。`
  }
  if (status === 500) {
    return `${action}失败：服务器内部错误。\n\n${detail}\n\n建议：请稍后重试，如持续报错请重启软件。`
  }
  if (status === 503) {
    return `${action}失败：服务暂时不可用。\n\n${detail}\n\n建议：请稍后重试。`
  }
  if (detail) return `${action}失败：${detail}`

  return `${action}失败，请稍后重试`
}
</script>

<style scoped>
.result-panel {
  flex: 1;
  background: #fff;
  border-left: 1px solid var(--mineru-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 320px;
}

.panel-header {
  padding: 12px 16px;
  font-weight: 700;
  border-bottom: 1px solid var(--mineru-border);
  flex: none;
}

.empty-result {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--mineru-text-tertiary);
}

.result-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.result-tabs :deep(.el-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.result-tabs :deep(.el-tabs__header) {
  flex: none;
}

.result-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
}

.result-tabs :deep(.el-tab-pane) {
  height: 100%;
}

.tab-content {
  height: 100%;
  overflow: auto;
  padding: 12px;
  background: #fff;
}

.raw-text :deep(textarea) {
  height: 100%;
  background: #f8fafc;
}

.result-actions {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--mineru-border);
  flex: none;
}

.output-dir {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px 12px;
  border-top: 1px solid var(--mineru-border);
  font-size: 12px;
  flex: none;
}

.dir-label {
  color: var(--mineru-text-secondary);
  flex: none;
}

.dir-path {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--mineru-text-primary);
}
</style>
