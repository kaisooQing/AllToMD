<template>
  <section class="upload-panel">
    <div class="panel-header">{{ $t('upload.title') }}</div>

    <el-tabs v-model="store.activeTab" class="upload-tabs">
      <el-tab-pane :label="$t('upload.fileTab')" name="file" />
      <el-tab-pane :label="$t('upload.urlHtmlTab')" name="urlHtml" />
    </el-tabs>

    <div class="preview-area">
      <template v-if="store.activeTab === 'file'">
        <div v-if="!localFile" class="upload-wrap">
          <el-upload
            drag
            action=""
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="false"
            accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.html,.htm,.png,.jpg,.jpeg,.gif,.webp,.bmp,.tiff"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              {{ $t('upload.dragText') }}
            </div>
            <template #tip>
              <div class="el-upload__tip">{{ $t('upload.formats') }}</div>
            </template>
          </el-upload>
        </div>
        <div v-else class="file-preview">
          <el-icon class="file-preview-icon" :class="`file-preview-icon-${getFileKind(localFile?.name)}`">
            <component :is="selectedFileIcon" />
          </el-icon>
          <div class="file-preview-type">{{ getFileTypeLabel(localFile?.name) }}</div>
          <div class="file-preview-name">{{ localFile?.name }}</div>
          <el-button size="small" link :icon="Close" @click="localFile = null">
            清除
          </el-button>
        </div>
      </template>

      <template v-else>
        <div class="url-html-editor">
          <div class="url-html-title">网页链接 / HTML 片段</div>
          <div class="url-html-desc">输入网页链接，或直接粘贴一段 HTML 源码。HTML 文件请回到“文件上传”页上传。</div>
          <div class="scope-card">
            <div class="scope-title">转换范围</div>
            <el-radio-group v-model="conversionScope" class="scope-options">
              <el-radio-button label="smart" value="smart">智能正文</el-radio-button>
              <el-radio-button label="full" value="full">整页内容</el-radio-button>
            </el-radio-group>
            <div class="scope-desc">
              {{ conversionScope === 'smart'
                ? '自动提取文章正文，过滤导航、广告、页脚等无关内容。'
                : '尽量转换页面里的全部可读内容，适合产品页、活动页、论坛页。' }}
            </div>
          </div>
          <textarea
            ref="sourceInput"
            v-model="store.sourceUrl"
            class="native-textarea"
            rows="8"
            :placeholder="$t('upload.urlPlaceholder')"
          />
          <div class="url-html-tips">
            <span>支持 URL</span>
            <span>支持 HTML 片段</span>
            <span>HTML 文件请用文件上传</span>
          </div>
        </div>
      </template>
    </div>

    <AdvancedOptions class="advanced-wrap" />

    <div class="status-panel" v-if="store.statusLines.length">
      <el-progress
        class="convert-progress"
        :percentage="store.conversionProgress"
        :status="progressStatus"
        :stroke-width="8"
      />
      <div class="status-line" v-for="(line, idx) in store.statusLines" :key="idx">
        {{ line }}
      </div>
    </div>

    <div class="action-bar">
      <el-button type="primary" size="large" :loading="store.isConverting" @click="startConvert">
        {{ $t('upload.convert') }}
      </el-button>
      <el-button
        v-if="store.isConverting"
        type="danger"
        size="large"
        @click="stopConvert"
      >
        停止转换
      </el-button>
      <el-button size="large" @click="clearAll">
        {{ $t('upload.clear') }}
      </el-button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, markRaw, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import JSZip from 'jszip'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Close, DataAnalysis, Document, Files, Grid, Link, Picture, Tickets, UploadFilled } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { getConfig, submitTask, getTaskStatus, getTaskResult, convertUrlHtml, cancelTask } from '@/api/mineru'
import { getFileKind, getFileTypeLabel } from '@/utils/fileType'
import AdvancedOptions from './AdvancedOptions.vue'

const store = useAppStore()
const { t } = useI18n()
const sourceInput = ref(null)
const localFile = ref(null)
const conversionScope = ref('smart')
const progressStatus = computed(() => (store.conversionProgress >= 100 ? 'success' : undefined))
const selectedFileIcon = computed(() => {
  const iconMap = {
    excel: Grid,
    word: Document,
    ppt: DataAnalysis,
    pdf: Tickets,
    image: Picture,
    html: Link,
    markdown: Document,
    json: Files,
    file: Files,
  }
  return iconMap[getFileKind(localFile.value?.name)] || Files
})

onMounted(async () => {
  try {
    const cfg = await getConfig()
    store.setConfig(cfg)
  } catch (e) {
    ElMessage.error('加载配置失败，请检查服务是否正常运行')
  }
})

function handleFileChange(file) {
  const raw = markRaw(file.raw)
  localFile.value = raw
  store.uploadedFile = raw
}

function clearAll() {
  localFile.value = null
  store.clearCurrent()
}

async function stopConvert() {
  if (!store.currentTaskId) {
    store.isConverting = false
    store.setProgress(0)
    store.setStatus([])
    return
  }
  try {
    await cancelTask(store.currentTaskId)
    ElMessage.success('已停止转换')
  } catch (e) {
    // 任务可能已结束，忽略错误
  }
  store.isConverting = false
  store.setProgress(0)
  store.setStatus(['已停止转换'])
}

async function startConvert() {
  const activeTab = store.activeTab
  const sourceUrlText = sourceInput.value?.value?.trim() || store.sourceUrl.trim()
  const selectedScope = conversionScope.value

  if (store.activeTab === 'file' && !localFile.value) {
    ElMessage.warning('Please select a file')
    return
  }
  if (store.activeTab === 'urlHtml' && !sourceUrlText) {
    ElMessage.warning('Please enter URL or HTML')
    return
  }

  store.clearCurrent()
  store.activeTab = activeTab
  if (activeTab === 'urlHtml') {
    store.sourceUrl = sourceUrlText
  }
  store.isConverting = true
  store.setProgress(5)
  store.setStatus([t('status.preparing')])

  try {
    if (store.activeTab === 'urlHtml') {
      await convertUrlHtmlInternal(sourceUrlText, selectedScope)
    } else {
      await convertFileInternal()
    }
  } catch (e) {
    store.setProgress(0)
    const msg = extractError(e)
    store.setStatus([`转换失败：${msg.split('\n')[0]}`])
    console.error('Convert error:', msg, e)
    showErrorPopup(msg)
  } finally {
    store.isConverting = false
  }
}

function showErrorPopup(msg) {
  // 对于包含多行详细说明的错误，使用 MessageBox 显示完整信息
  if (msg.includes('\n') && msg.length > 60) {
    ElMessageBox.alert(msg.replace(/\n/g, '<br>'), '转换失败', {
      dangerouslyUseHTMLString: true,
      confirmButtonText: '知道了',
      customClass: 'error-detail-msgbox',
    })
  } else {
    ElMessage.error(msg)
  }
}

function extractError(e) {
  // 1. 检测网络层错误（服务器未启动、断网等）
  if (e?.code === 'ERR_NETWORK' || e?.message?.includes('Network Error')) {
    return (
      '无法连接到转换服务。\n\n' +
      '可能原因：\n' +
      '1. 服务未启动或已意外停止\n' +
      '2. 网络连接异常\n\n' +
      '建议：请检查软件是否正常运行，或重新启动软件。'
    )
  }
  if (e?.code === 'ECONNABORTED' || e?.message?.includes('timeout')) {
    return (
      '请求超时，服务器未在规定时间内响应。\n\n' +
      '可能原因：\n' +
      '1. 文件过大，转换耗时较长\n' +
      '2. 服务器负载过高\n' +
      '3. 网络连接不稳定\n\n' +
      '建议：请稍后重试，或尝试转换较小的文件。'
    )
  }

  const data = e?.response?.data
  const status = e?.response?.status

  // 2. 根据 HTTP 状态码生成友好提示
  if (status === 0 || (e?.message && e.message.includes('Network Error'))) {
    return '无法连接到转换服务。\n\n建议：请检查软件是否正常运行，或重新启动软件。'
  }

  if (data) {
    // 提取后端返回的 detail 信息
    let detail = ''
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((d) => d.msg || d.message || JSON.stringify(d))
        .filter(Boolean)
      detail = messages.join('; ')
    } else if (data.detail?.msg) {
      detail = String(data.detail.msg)
    } else if (data.detail?.message) {
      detail = String(data.detail.message)
    } else if (data.detail) {
      detail = String(data.detail)
    } else if (data.message) {
      detail = String(data.message)
    } else {
      try { detail = JSON.stringify(data) } catch { detail = String(data) }
    }

    // 如果后端已返回多行友好提示（包含 \n），直接使用
    if (detail.includes('\n')) return detail

    // 根据状态码补充说明
    if (status === 400) {
      // 不支持的文件类型
      if (detail.includes('Unsupported file type') || detail.includes('file type')) {
        return (
          '不支持的文件类型。\n\n' +
          `错误详情：${detail}\n\n` +
          '支持的格式：PDF、DOCX、DOC、PPTX、PPT、XLSX、XLS、HTML、HTM、PNG、JPG、JPEG、GIF、WEBP、BMP、TIFF\n\n' +
          '建议：请选择上述支持的文件格式。'
        )
      }
      return `请求参数错误。\n\n错误详情：${detail}\n\n建议：请检查输入内容后重试。`
    }
    if (status === 404) {
      if (detail.includes('Task not found')) {
        return '任务不存在或已过期。\n\n可能原因：任务结果已被清理或服务已重启。\n建议：请重新上传文件进行转换。'
      }
      return `资源未找到。\n\n${detail}`
    }
    if (status === 403 || status === 401) {
      return detail
    }
    if (status === 422) {
      return detail
    }
    if (status === 409) {
      return `转换任务执行失败。\n\n${detail}\n\n建议：请检查文件是否损坏，或尝试更换文件后重试。`
    }
    if (status === 413) {
      return (
        '文件过大，超出服务器限制。\n\n' +
        '建议：请尝试压缩文件或拆分后分批转换。'
      )
    }
    if (status === 500) {
      // Office 格式转换失败
      if (detail.includes('office') || detail.includes('Office') || detail.includes('COM') || detail.includes('win32com')) {
        return (
          'Office 文件转换失败。\n\n' +
          `错误详情：${detail}\n\n` +
          '可能原因：\n' +
          '1. 电脑未安装 Microsoft Office 或 WPS\n' +
          '2. Office 程序异常或被占用\n' +
          '3. 文件已损坏或格式不标准\n\n' +
          '建议：\n' +
          '- 请确保已安装 Office（Word/Excel/PowerPoint）\n' +
          '- 关闭可能占用该文件的程序后重试\n' +
          '- 或将文件另存为新版格式（.docx/.xlsx/.pptx）后重试'
        )
      }
      return `服务器内部错误。\n\n错误详情：${detail}\n\n建议：请稍后重试，如持续报错请重启软件。`
    }
    if (status === 502) {
      return `无法连接到目标网站。\n\n${detail}\n\n建议：请检查 URL 是否正确，或确认网络连接正常后重试。`
    }
    if (status === 503) {
      if (detail.includes('Task manager') || detail.includes('not initialized')) {
        return '转换服务尚未就绪。\n\n可能原因：服务正在启动中或出现异常。\n建议：请等待几秒后重试，或重启软件。'
      }
      return `服务暂时不可用。\n\n${detail}\n\n建议：请稍后重试。`
    }
    if (status === 504) {
      return `请求超时。\n\n${detail}\n\n建议：请稍后重试，或在浏览器中打开页面后保存为 HTML 文件上传转换。`
    }

    return detail
  }

  // 3. 前端 JS 抛出的错误
  if (e?.message) {
    const msg = String(e.message)
    if (msg.includes('转换超时')) {
      return msg + '\n\n建议：任务可能仍在后台运行，请稍后查看历史记录。'
    }
    if (msg.includes('No markdown file found')) {
      return '转换结果中未找到 Markdown 文件。\n\n可能原因：文件内容为空或转换异常。\n建议：请检查文件内容，或尝试重新转换。'
    }
    if (msg.includes('Task failed')) {
      return '转换任务失败。\n\n可能原因：文件损坏、格式不支持或服务器异常。\n建议：请检查文件后重试，或更换文件格式。'
    }
    return msg
  }

  return String(e)
}

async function convertUrlHtmlInternal(sourceUrlText = '', selectedScope = conversionScope.value) {
  const formData = new FormData()
  if (sourceUrlText) formData.append('source_url', sourceUrlText)
  formData.append('conversion_scope', selectedScope)

  // 渐进式进度模拟：URL 转换是单个阻塞请求，需要在等待期间提供视觉反馈
  // 阶段：5%→15% 抓取页面 → 15%→40% 渲染/解析 → 40%→80% 下载图片 → 80%→90% 生成Markdown
  const stages = [
    { target: 12, delay: 600, label: '正在抓取网页...' },
    { target: 20, delay: 1500, label: '正在解析页面内容...' },
    { target: 35, delay: 2500, label: '正在提取正文...' },
    { target: 55, delay: 4000, label: '正在下载图片...' },
    { target: 70, delay: 6000, label: '正在下载图片...' },
    { target: 82, delay: 9000, label: '正在生成 Markdown...' },
    { target: 88, delay: 12000, label: '正在生成 Markdown...' },
  ]

  let progressTimer = null
  let stageIdx = 0
  function startProgressSim() {
    function advance() {
      if (stageIdx < stages.length) {
        const s = stages[stageIdx]
        store.setProgress(s.target)
        store.setStatus([s.label])
        stageIdx++
        progressTimer = setTimeout(advance, s.delay)
      } else {
        // 超过所有阶段后，以极慢速度逼近 92%
        progressTimer = setInterval(() => {
          if (store.conversionProgress < 91) {
            store.setProgress(store.conversionProgress + 1)
          }
        }, 3000)
      }
    }
    advance()
  }
  function stopProgressSim() {
    if (progressTimer) {
      clearTimeout(progressTimer)
      clearInterval(progressTimer)
      progressTimer = null
    }
  }

  startProgressSim()
  try {
    const result = await convertUrlHtml(formData)
    stopProgressSim()
    store.setProgress(100)
    store.setStatus(['转换完成'])
    applyResult(result, result.task_id, result.safe_name)
  } catch (e) {
    stopProgressSim()
    throw e
  }
}

function isHtmlUpload(file) {
  const name = file?.name || ''
  return /\.html?$/i.test(name)
}

async function convertHtmlUploadInternal() {
  const formData = new FormData()
  formData.append('html_file', localFile.value)
  formData.append('conversion_scope', 'full')

  // 渐进式进度模拟：HTML 文件转换同样是单个阻塞请求，需要在等待期间提供视觉反馈
  const stages = [
    { target: 12, delay: 600, label: '正在解析 HTML 文件...' },
    { target: 25, delay: 1500, label: '正在解析页面内容...' },
    { target: 40, delay: 2500, label: '正在提取正文...' },
    { target: 55, delay: 4000, label: '正在下载图片...' },
    { target: 70, delay: 6000, label: '正在下载图片...' },
    { target: 82, delay: 9000, label: '正在生成 Markdown...' },
    { target: 88, delay: 12000, label: '正在生成 Markdown...' },
  ]

  let progressTimer = null
  let stageIdx = 0
  function startProgressSim() {
    function advance() {
      if (stageIdx < stages.length) {
        const s = stages[stageIdx]
        store.setProgress(s.target)
        store.setStatus([s.label])
        stageIdx++
        progressTimer = setTimeout(advance, s.delay)
      } else {
        // 超过所有阶段后，以极慢速度逼近 92%
        progressTimer = setInterval(() => {
          if (store.conversionProgress < 91) {
            store.setProgress(store.conversionProgress + 1)
          }
        }, 3000)
      }
    }
    advance()
  }
  function stopProgressSim() {
    if (progressTimer) {
      clearTimeout(progressTimer)
      clearInterval(progressTimer)
      progressTimer = null
    }
  }

  startProgressSim()
  try {
    const result = await convertUrlHtml(formData)
    stopProgressSim()
    store.setProgress(100)
    store.setStatus(['转换完成'])
    applyResult(result, result.task_id, result.safe_name || localFile.value.name)
  } catch (e) {
    stopProgressSim()
    throw e
  }
}

async function convertFileInternal() {
  if (isHtmlUpload(localFile.value)) {
    await convertHtmlUploadInternal()
    return
  }

  const formData = new FormData()
  formData.append('files', localFile.value)
  store.options.language.forEach((lang) => formData.append('lang_list', lang))
  formData.append('backend', 'pipeline')
  formData.append('effort', 'medium')
  formData.append('parse_method', store.options.parseMethod)
  formData.append('formula_enable', String(store.options.formulaEnable))
  formData.append('table_enable', String(store.options.tableEnable))
  formData.append('image_analysis', String(store.options.imageAnalysis))
  formData.append('server_url', store.options.serverUrl || '')
  formData.append('return_md', 'true')
  formData.append('return_content_list', 'true')
  formData.append('return_images', 'true')
  formData.append('response_format_zip', 'true')
  formData.append('return_original_file', 'false')
  formData.append('client_side_output_generation', 'false')
  formData.append('start_page_id', '0')
  formData.append('end_page_id', String(store.options.maxPages))

  // 上传超时：按文件大小计算，基础 2 分钟，每 10MB 加 1 分钟，上限 10 分钟
  const fileSizeMB = (localFile.value?.size || 0) / (1024 * 1024)
  const uploadTimeout = Math.min(120000 + Math.floor(fileSizeMB / 10) * 60000, 600000)
  const submitRes = await submitTask(formData, uploadTimeout)
  const taskId = submitRes.task_id
  store.currentTaskId = taskId
  store.currentFileName = localFile.value.name
  store.setProgress(3)
  store.setStatus([`任务已提交：${taskId}`])

  let terminal = false
  let statusData = null
  let pollCount = 0
  // 轮询超时：动态计算。页数未知时给 15 分钟基础超时，
  // 收到页数后按每页 30 秒重新计算，上限 120 分钟。
  // 只能延长不能缩短，避免收到页数后超时反而变短。
  let maxPoll = 900 // 初始 900 次（15 分钟）
  while (!terminal) {
    await new Promise((r) => setTimeout(r, 1000))
    // 用户点击停止转换后，退出轮询
    if (!store.isConverting) {
      return
    }
    statusData = await getTaskStatus(taskId)
    pollCount += 1
    if (statusData.status === 'processing') {
      const realProgress = statusData.progress || 5
      const detail = statusData.progress_detail || '正在转换，请稍候...'
      store.setStatus([detail])
      // 进度只能单调递增，避免后端进度回退覆盖前端
      if (realProgress >= store.conversionProgress) {
        store.setProgress(realProgress)
      }
      // 收到页数信息后，按页数动态延长超时
      const totalPages = statusData.total_pages || 0
      if (totalPages > 0) {
        // 每页 30 秒（30 次轮询），最少 15 分钟，最多 120 分钟
        const pageBasedPoll = Math.min(Math.max(totalPages * 30, 900), 7200)
        if (pageBasedPoll > maxPoll) {
          maxPoll = pageBasedPoll
        }
      }
    } else if (statusData.status === 'pending') {
      store.setStatus(['任务排队中...'])
    } else if (statusData.status === 'completed') {
      store.setStatus(['正在整理转换结果...'])
    } else if (statusData.status === 'failed') {
      store.setStatus(['转换失败'])
    }
    if (statusData.status === 'completed' || statusData.status === 'failed') {
      terminal = true
    } else if (pollCount >= maxPoll) {
      throw new Error('转换超时，请稍后重试（任务可能仍在后台运行）')
    }
  }

  // 用户取消后任务变为 failed，不应当作错误抛出
  if (statusData.status === 'failed') {
    if (!store.isConverting || (statusData.error && statusData.error.includes('取消'))) {
      // 用户主动取消，静默退出
      return
    }
    throw new Error(statusData.error || 'Task failed')
  }

  const outputDir = statusData.output_dir || ''
  store.setProgress(92)

  const resultResponse = await getTaskResult(taskId)
  store.setProgress(96)
  const contentType = resultResponse.headers['content-type'] || ''
  const blob = new Blob([resultResponse.data])

  let result
  if (contentType.includes('application/zip')) {
    result = await processZipResult(blob, taskId)
  } else {
    const text = await blob.text()
    const json = JSON.parse(text)
    const firstKey = Object.keys(json.results || {})[0]
    const first = json.results?.[firstKey] || {}
    result = {
      md_content: first.md_content || '',
      txt_content: first.md_content || '',
      content_list_json: first.content_list || '',
      has_images: false,
    }
  }

  applyResult(result, taskId, localFile.value.name, outputDir)
  store.setProgress(100)
  store.setStatus(['转换完成'])
}

async function processZipResult(blob, taskId) {
  const zip = await JSZip.loadAsync(blob)
  const files = {}
  zip.forEach((relativePath, file) => {
    files[relativePath] = file
  })

  const mdPaths = Object.keys(files).filter((p) => p.endsWith('.md'))
  if (!mdPaths.length) {
    throw new Error('No markdown file found in result archive')
  }
  const mdPath = mdPaths[0]
  const mdDir = mdPath.substring(0, mdPath.lastIndexOf('/'))
  let mdContent = await files[mdPath].async('text')

  // Build blob URLs for images
  const imageMap = {}
  const mdDirPrefix = mdDir ? mdDir + '/' : ''
  for (const [relativePath, file] of Object.entries(files)) {
    if (relativePath.includes('/images/') || relativePath.startsWith('images/')) {
      const ext = relativePath.split('.').pop() || 'png'
      const imageBlob = await file.async('blob')
      const url = URL.createObjectURL(new Blob([imageBlob], { type: `image/${ext}` }))
      const key = mdDirPrefix ? relativePath.replace(mdDirPrefix, '') : relativePath
      imageMap[key] = url
    }
  }

  // Replace relative image paths in markdown with blob URLs
  mdContent = mdContent.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
    const cleanSrc = src.split('?')[0]
    for (const [key, url] of Object.entries(imageMap)) {
      if (key.endsWith(cleanSrc) || cleanSrc.endsWith(key)) {
        return `![${alt}](${url})`
      }
    }
    return match
  })

  // Try to find content_list.json
  const contentListPath = Object.keys(files).find(
    (p) => p.endsWith('_content_list.json') || p.endsWith('/content_list.json')
  )
  let contentListJson = ''
  if (contentListPath) {
    contentListJson = await files[contentListPath].async('text')
  }

  const hasImages = Object.keys(imageMap).length > 0
  return {
    md_content: mdContent,
    txt_content: await files[mdPath].async('text'),
    content_list_json: contentListJson,
    has_images: hasImages,
    md_dir: mdDir,
    md_path: mdPath,
  }
}

function joinOutputDir(baseDir, relativeDir) {
  if (!baseDir || !relativeDir) return baseDir || ''
  const separator = baseDir.includes('\\') ? '\\' : '/'
  const cleanBase = baseDir.replace(/[\\/]+$/, '')
  const cleanRelative = relativeDir.replace(/^[\\/]+/, '').replace(/[\\/]+/g, separator)
  return `${cleanBase}${separator}${cleanRelative}`
}

function applyResult(result, taskId, name, outputDir = '') {
  const baseOutputDir = outputDir || result.output_dir || ''
  const mdOutputDir = joinOutputDir(baseOutputDir, result.md_dir || '')
  store.currentTaskId = taskId
  store.currentFileName = name
  store.currentMdContent = result.md_content || ''
  store.currentTxtContent = result.txt_content || ''
  store.currentContentListJson = result.content_list_json || ''
  store.currentHasImages = result.has_images || false
  store.currentOutputPath = result.output_path || ''
  store.currentOutputDir = mdOutputDir || baseOutputDir
  store.currentPreviewPdfUrl = ''

  store.addHistoryItem({
    id: taskId,
    name,
    taskId,
    outputPath: result.output_path || '',
    outputDir: store.currentOutputDir,
    mdContent: store.currentMdContent,
    txtContent: store.currentTxtContent,
    contentListJson: store.currentContentListJson,
    hasImages: result.has_images || false,
    status: 'completed',
  })
}
</script>

<style scoped>
.upload-panel {
  flex: 1;
  min-width: 340px;
  background: #fff;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.panel-header {
  padding: 12px 16px;
  font-weight: 700;
  border-bottom: 1px solid var(--mineru-border);
  flex: none;
}

.upload-tabs {
  flex: none;
  padding: 12px 16px 0;
}

.upload-tabs :deep(.el-tabs__content) {
  padding: 12px 0;
}

.upload-icon {
  font-size: 32px;
  color: var(--mineru-accent);
  margin-bottom: 8px;
}

.selected-file {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 12px;
  background: var(--mineru-accent-soft);
  border-radius: var(--mineru-radius-sm);
  font-size: 13px;
}

.native-textarea {
  width: 100%;
  flex: 1;
  min-height: 0;
  padding: 10px 12px;
  border: 1px solid var(--mineru-border);
  border-radius: var(--mineru-radius-sm);
  font-family: inherit;
  font-size: 13px;
  resize: vertical;
  outline: none;
}

.native-textarea:focus {
  border-color: var(--mineru-accent);
}

.preview-area {
  flex: 1;
  min-height: 180px;
  margin: 0 16px;
  border: 1px solid var(--mineru-border);
  border-radius: var(--mineru-radius);
  overflow: hidden;
  background: #f8fafc;
}

.upload-wrap,
.upload-wrap > div {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.upload-wrap {
  padding: 12px;
}

.upload-wrap :deep(.el-upload) {
  flex: 1;
  width: 100%;
  min-height: 0;
}

.upload-wrap :deep(.el-upload-dragger) {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-wrap :deep(.el-upload__tip) {
  flex: none;
  padding: 8px 0 0;
  margin: 0;
  text-align: center;
  font-size: 12px;
  color: var(--mineru-text-tertiary);
}

.file-preview {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--mineru-text-primary);
}

.file-preview-icon {
  font-size: 40px;
  color: var(--mineru-accent);
}

.file-preview-icon-excel {
  color: #16a34a;
}

.file-preview-icon-word {
  color: #2563eb;
}

.file-preview-icon-ppt {
  color: #ea580c;
}

.file-preview-icon-pdf {
  color: #dc2626;
}

.file-preview-icon-image {
  color: #7c3aed;
}

.file-preview-icon-html,
.file-preview-icon-url {
  color: #0891b2;
}

.file-preview-type {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--mineru-accent-soft);
  color: var(--mineru-accent);
  font-size: 12px;
  font-weight: 700;
}

.file-preview-name {
  font-size: 14px;
  max-width: 80%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pdf-preview,
.pdf-preview iframe {
  width: 100%;
  height: 100%;
  border: none;
}

.url-html-editor {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
}

.url-html-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--mineru-text-primary);
}

.url-html-desc {
  font-size: 12px;
  color: var(--mineru-text-tertiary);
}

.scope-card {
  padding: 12px;
  border: 1px solid var(--mineru-border);
  border-radius: var(--mineru-radius-sm);
  background: #fff;
}

.scope-title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--mineru-text-primary);
}

.scope-options {
  margin-bottom: 8px;
}

.scope-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--mineru-text-tertiary);
}

.url-html-tips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.url-html-tips span {
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--mineru-accent-soft);
  color: var(--mineru-accent);
  font-size: 12px;
}

.advanced-wrap {
  margin: 12px 16px 0;
  flex: none;
}

.status-panel {
  margin: 12px 16px 0;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid var(--mineru-border);
  border-radius: var(--mineru-radius-sm);
  max-height: 120px;
  overflow-y: auto;
  font-size: 12px;
  color: var(--mineru-text-secondary);
  flex: none;
}

.convert-progress {
  margin-bottom: 8px;
}

.status-line {
  line-height: 1.6;
}

.action-bar {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  border-top: 1px solid var(--mineru-border);
  flex: none;
}
</style>
