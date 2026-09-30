<div align="center">

<img src="logo.png" width="128" height="128" alt="AllToMD" />

# AllToMD

### All-in-One Document to Markdown Converter

Convert PDF, Word, Excel, PPT, images, and web pages to Markdown with one click. Automatically extracts images, formulas, and tables.

Powered by [MinerU](https://github.com/opendatalab/MinerU) engine. Runs locally — your data never leaves your device.

**English** · **[简体中文](README_zh-CN.md)**

<br/>

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg?style=flat-square)](LICENSE)
[![MinerU](https://img.shields.io/badge/MinerU-v3.4.4-22A5F7.svg?style=flat-square)](https://github.com/opendatalab/MinerU)
[![Vue](https://img.shields.io/badge/Vue-3.5-42b883.svg?style=flat-square)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg?style=flat-square)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB.svg?style=flat-square)](https://www.python.org/)
[![Element Plus](https://img.shields.io/badge/Element%20Plus-2.14-409EFF.svg?style=flat-square)](https://element-plus.org/)

[Features](#-features) · [Screenshots](#-screenshots) · [Quick Start](#-quick-start) · [Architecture](#-architecture) · [API Docs](#-api-docs) · [FAQ](#-faq)

</div>

<br/>

> ## Download Portable Build
> 
> No environment setup needed — download, extract, and run: [Releases v1.0.0](https://github.com/kaisooQing/AllToMD/releases/tag/v1.0.0)
> 
> To run from source, see [Quick Start](#-quick-start) below.

<br/>

## ✨ Features

<table>
<tr>
<td width="50%">

### 📄 Multi-Format Support

PDF · Word · Excel · PPT · Images · HTML

Drag-and-drop upload, batch processing, auto file type detection

</td>
<td width="50%">

### 🌐 URL to Markdown

Enter a URL and get Markdown automatically

Supports JS-rendered pages (SPA, Shadow DOM)

</td>
</tr>
<tr>
<td width="50%">

### 🔬 Formula & Table Recognition

LaTeX math formula auto-recognition

Structured table extraction preserving row/column layout

</td>
<td width="50%">

### 🖼️ Image Auto-Extraction

Document images extracted and localized

Markdown image links rewritten to local paths

</td>
</tr>
<tr>
<td width="50%">

### ⚡ Four Parsing Backends

Pipeline · VLM · Hybrid · Office

Choose the optimal strategy per document type

</td>
<td width="50%">

### 📊 Real-Time Progress Tracking

Stage-by-stage: layout → formula → table → OCR

Per-page updates, smooth progress with no regressions

</td>
</tr>
<tr>
<td width="50%">

### 🌍 Bilingual UI

Auto-detect language interface

One-click switch between Chinese / English

</td>
<td width="50%">

### 🖥️ Three-Panel Layout

Left: history · Center: upload · Right: preview

Markdown render / source / JSON views

</td>
</tr>
</table>

---

## 📸 Screenshots

<div align="center">

**Main Interface**

<img src="AllToMD使用说明/assets/01_主界面.png" width="800" alt="Main Interface" />

<br/><br/>

**Conversion Result**

<img src="AllToMD使用说明/assets/05_转换结果.jpg" width="800" alt="Conversion Result" />

<br/><br/>

**Launcher Window**

<img src="AllToMD使用说明/assets/04_启动窗口.jpg" width="480" alt="Launcher Window" />

</div>

---

## 🚀 Quick Start

### Prerequisites

| Dependency | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |
| CUDA (optional) | 11.8+ (GPU acceleration) |

### 1 · Clone the Repository

```bash
git clone https://github.com/kaisooQing/AllToMD.git
cd AllToMD
```

### 2 · Set Up Backend Environment

```bash
# Create conda virtual environment
conda create -n alltomd python=3.10
conda activate alltomd

# Install MinerU dependencies
cd MinerU
pip install -e ".[core]"

# Install additional dependencies
pip install curl_cffi markdownify httpx
```

<details>
<summary>📖 Full dependency list</summary>

```bash
# core includes: pipeline + vlm + gradio
# pipeline: PyTorch, torchvision, transformers, onnxruntime
# vlm: torch, transformers, accelerate
# gradio: gradio, gradio-pdf

# Additional dependencies (URL/HTML conversion)
pip install curl_cffi markdownify httpx

# Optional: S3 storage
pip install -e ".[s3]"

# Optional: vLLM inference (Linux only)
pip install -e ".[vllm]"

# Optional: LMDeploy inference (Windows only)
pip install -e ".[lmdeploy]"
```
</details>

### 3 · Set Up Frontend

```bash
cd ../frontend
npm install
```

### 4 · Install Playwright Browser

```bash
# Set browser path (recommended to avoid downloading to C: drive)
set PLAYWRIGHT_BROWSERS_PATH=..\ms-playwright

# Install Chromium
python -m playwright install chromium
```

### 5 · Start Development Services

**Option A**: One-click start (Windows)

```
.\启动Web_Dev.bat
```

**Option B**: Manual start

```bash
# Terminal 1 — Backend service (port 7860)
set MODELSCOPE_CACHE=..\model_cache
set MINERU_MODEL_SOURCE=modelscope
set MINERU_WEB_UI_DIR=..\frontend\dist
python -m mineru.cli.fast_api --port 7860

# Terminal 2 — Frontend dev server (port 5173)
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser to start using.

> ⚠️ On first run, AI models (~1 GB) are automatically downloaded from ModelScope to `model_cache/`. Ensure a stable network connection.

### 6 · Build for Production

```bash
cd frontend
npm run build
```

Build output is in `frontend/dist/`.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    User Input                        │
│            File / URL / HTML fragment                │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           Vue 3 Frontend (Element Plus)              │
│                                                     │
│  History   │  Upload     │  Preview   │  Advanced   │
│  Panel     │  Panel      │  Panel     │  Options    │
│  Pinia     │  Drag-drop  │  Markdown  │  i18n       │
└──────────────────────┬──────────────────────────────┘
                       │  REST API
                       ▼
┌─────────────────────────────────────────────────────┐
│           FastAPI Backend (port 7860)               │
│                                                     │
│  Task Queue │  Progress  │  Timeout  │  Packaging   │
│             │  Callback  │  Manager  │              │
└──────┬─────────────┬────────────────────────────────┘
       │             │
       ▼             ▼
┌──────────────┐   ┌──────────────────────────────────┐
│  MinerU      │   │    URL/HTML Conversion Path       │
│  Engine      │   │                                  │
│              │   │  curl_cffi (TLS fingerprint)     │
│ ┌──────────┐ │   │       ↓                          │
│ │ Pipeline │ │   │  Playwright (JS render fallback)  │
│ │Layout→FX │ │   │       ↓                          │
│ │→Table→OCR│ │   │  Content extraction + cleanup    │
│ └──────────┘ │   │       ↓                          │
│ ┌──────────┐ │   │  HTML → Markdown (markdownify)   │
│ │   VLM    │ │   │       ↓                          │
│ │ Vision   │ │   │  Concurrent image download       │
│ └──────────┘ │   └──────────────────────────────────┘
│ ┌──────────┐ │
│ │  Hybrid  │ │
│ │ Mixed    │ │
│ └──────────┘ │
│ ┌──────────┐ │
│ │  Office  │ │
│ │ Docs     │ │
│ └──────────┘ │
└──────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────┐
│                    Output                            │
│          .md file + images/ dir + .zip package       │
└─────────────────────────────────────────────────────┘
```

### Parsing Backend Comparison

| Backend | Method | Speed | Quality | Best For |
|---|---|---|---|---|
| `pipeline` | Pipeline: layout → formula → table → OCR | ⚡ Fast | ⭐⭐⭐ | General documents |
| `vlm` | Vision Language Model direct inference | 🐢 Slow | ⭐⭐⭐⭐⭐ | Complex layouts, academic papers |
| `hybrid` | Pipeline + VLM hybrid | 🐢 Slow | ⭐⭐⭐⭐ | Balance speed and quality |
| `office` | Office document parser | ⚡ Fast | ⭐⭐⭐ | .docx / .xlsx / .pptx |

---

## 📁 Project Structure

```
AllToMD/
├── frontend/                     # Vue 3 frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── AppHeader.vue          # Top header bar
│   │   │   ├── HistoryPanel.vue       # Left · History
│   │   │   ├── UploadPanel.vue        # Center · Upload & convert
│   │   │   ├── ResultPanel.vue        # Right · Result preview
│   │   │   └── AdvancedOptions.vue    # Advanced options
│   │   ├── stores/app.js              # Pinia global state
│   │   ├── api/mineru.js              # Backend API wrapper
│   │   ├── i18n/index.js              # i18n (CN/EN)
│   │   └── utils/                     # Utilities
│   ├── package.json
│   └── vite.config.js
│
├── MinerU/                        # MinerU engine (based on v3.4.4)
│   ├── mineru/
│   │   ├── cli/
│   │   │   ├── fast_api.py            # FastAPI main app
│   │   │   ├── web_api.py             # URL/HTML conversion API
│   │   │   └── client.py              # CLI client
│   │   ├── backend/
│   │   │   ├── pipeline/              # Pipeline backend
│   │   │   ├── vlm/                   # VLM backend
│   │   │   ├── hybrid/               # Hybrid backend
│   │   │   └── office/               # Office document backend
│   │   └── model/                     # AI model definitions
│   ├── pyproject.toml
│   └── LICENSE.md
│
├── 启动Web_Dev.bat                # Dev startup script
├── AllToMD使用说明/               # User manual
├── logo.png / logo.ico            # Project logo
├── LICENSE                        # Apache 2.0
└── README.md
```

---

## 📡 API Docs

### File Conversion

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/tasks` | Submit a file conversion task |
| `GET` | `/tasks/{task_id}` | Query task status and progress |
| `GET` | `/tasks/{task_id}/result` | Download conversion result (ZIP) |
| `DELETE` | `/tasks/{task_id}` | Cancel a task |

<details>
<summary>📖 Request Parameters</summary>

| Parameter | Type | Description |
|---|---|---|
| `files` | File[] | Uploaded files |
| `lang_list` | String[] | OCR languages (`ch`, `en`) |
| `backend` | String | Backend type: `pipeline` / `vlm` / `hybrid` |
| `effort` | String | Hybrid effort: `low` / `medium` / `high` |
| `parse_method` | String | Parse method: `auto` / `ocr` / `txt` |
| `formula_enable` | String | Formula recognition toggle |
| `table_enable` | String | Table recognition toggle |
| `image_analysis` | String | Image analysis toggle |
| `start_page_id` | String | Start page |
| `end_page_id` | String | End page |
</details>

### URL/HTML Conversion

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/config` | Get frontend config |
| `POST` | `/api/convert/url_html` | Convert URL/HTML |
| `GET` | `/api/download/{task_id}` | Download conversion result |

---

## ⚙️ Configuration

### Key Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODELSCOPE_CACHE` | `model_cache/` | AI model cache directory |
| `MINERU_MODEL_SOURCE` | `modelscope` | Model download source |
| `MINERU_WEB_UI_DIR` | `frontend/dist` | Frontend static files directory |
| `PLAYWRIGHT_BROWSERS_PATH` | `ms-playwright/` | Playwright browser path |

### Timeout Settings

| Scenario | Strategy |
|---|---|
| File upload | Base 2 min + 1 min per 10MB, max 10 min |
| Conversion polling | 30 sec per page, min 15 min, max 120 min |
| URL/HTML conversion | Fixed 2 min |
| Default API timeout | 30 sec |

---

## ❓ FAQ

<details>
<summary><b>First launch is slow / stuck downloading</b></summary>

On first run, AI models (OCR, layout analysis, formula recognition, etc.) are automatically downloaded from ModelScope to `model_cache/` (~1 GB). Ensure a stable network connection. Subsequent launches will load directly from local cache.
</details>

<details>
<summary><b>Port 7860 is already in use</b></summary>

The startup script checks if port 7860 is available. If it's occupied, close the process using that port, or change the port number in `启动Web_Dev.bat`.

```bash
# Find the process using the port
netstat -ano | findstr :7860
```
</details>

<details>
<summary><b>Playwright fails to start</b></summary>

Ensure Chromium is installed and `PLAYWRIGHT_BROWSERS_PATH` is set correctly:

```bash
set PLAYWRIGHT_BROWSERS_PATH=..\ms-playwright
python -m playwright install chromium
```

Some websites have anti-bot detection that may block Playwright. In that case, manually save the HTML from your browser and upload the file.
</details>

<details>
<summary><b>GPU inference not working / slow</b></summary>

1. Ensure CUDA drivers (11.8+) are installed
2. Install GPU-enabled PyTorch:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```
3. Verify GPU availability: `python -c "import torch; print(torch.cuda.is_available())"`
</details>

<details>
<summary><b>Model cache downloaded to C: drive</b></summary>

Set the environment variable before launching to redirect cache to the project directory:

```bash
set MODELSCOPE_CACHE=..\model_cache
```

If models were already downloaded to C:, move the `.cache/modelscope` directory to `model_cache/`.
</details>

---

## 🗺️ Roadmap

- [x] Multi-format support (PDF / Word / Excel / PPT / Images / HTML)
- [x] URL web page direct conversion
- [x] Four parsing backends (Pipeline / VLM / Hybrid / Office)
- [x] Bilingual UI (Chinese / English)
- [x] History management
- [x] Real-time progress tracking
- [ ] Docker one-click deployment
- [ ] Batch file queue
- [ ] Markdown editing and export
- [ ] More OCR language support
- [ ] Plugin system

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'feat: add some feature'`
4. Push the branch: `git push origin feature/your-feature`
5. Submit a Pull Request

### Development Conventions

- Build frontend after changes: `cd frontend && npm run build`
- Restart FastAPI service after backend changes
- Use Conventional Commits format for commit messages

---

## 📄 License

This project is licensed under **Apache License 2.0** — see [LICENSE](LICENSE).

The project is built on [MinerU](https://github.com/opendatalab/MinerU) v3.4.4, also under Apache License 2.0 (with additional terms) — see [MinerU/LICENSE.md](MinerU/LICENSE.md).

## 🙏 Acknowledgements

- **[MinerU](https://github.com/opendatalab/MinerU)** — Document parsing engine by OpenDataLab
- **[Vue.js](https://vuejs.org/)** — The Progressive JavaScript Framework
- **[Element Plus](https://element-plus.org/)** — Vue 3 UI component library
- **[FastAPI](https://fastapi.tiangolo.com/)** — Modern, fast Python web framework
- **[PyTorch](https://pytorch.org/)** — Deep learning framework

---

<div align="center">

**If this project helps you, please give it a ⭐ Star!**

<br/>

<sub>by <a href="https://github.com/kaisooQing">kaisooQing</a></sub>

</div>
