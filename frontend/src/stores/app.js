import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStore = defineStore('app', () => {
  // Configuration loaded from backend
  const config = ref(null)

  // History items
  const history = ref([])

  // Current task/result
  const currentTaskId = ref('')
  const currentFileName = ref('')
  const currentOutputPath = ref('')
  const currentOutputDir = ref('')
  const currentMdContent = ref('')
  const currentTxtContent = ref('')
  const currentContentListJson = ref('')
  const currentHasImages = ref(false)
  const currentPreviewPdfUrl = ref('')
  const statusLines = ref([])
  const conversionProgress = ref(0)
  const isConverting = ref(false)

  // Input state
  const activeTab = ref('file') // 'file' | 'urlHtml'
  const uploadedFile = ref(null)
  const sourceUrl = ref('')
  const htmlContent = ref('')
  const htmlFile = ref(null)

  // Options
  const options = ref({
    backend: 'pipeline',
    effort: 'medium',
    parseMethod: 'auto',
    formulaEnable: true,
    tableEnable: true,
    imageAnalysis: true,
    language: ['ch'],
    isOcr: true,
    maxPages: 99999,
    serverUrl: 'http://localhost:30000',
  })

  const isHttpClientBackend = computed(() =>
    options.value.backend.endsWith('-http-client')
  )

  const showHybridEffort = computed(() =>
    options.value.backend.startsWith('hybrid')
  )

  const showImageAnalysis = computed(() => {
    const b = options.value.backend
    if (b.startsWith('vlm')) return true
    if (b.startsWith('hybrid') && options.value.effort === 'high') return true
    return false
  })

  const showOcrLanguage = computed(() =>
    options.value.backend === 'pipeline'
  )

  const showForceOcr = computed(() => {
    const b = options.value.backend
    return b === 'pipeline' || b.startsWith('hybrid')
  })

  const showServerUrl = computed(() =>
    options.value.backend.endsWith('-http-client')
  )

  function setConfig(value) {
    config.value = value
    if (value) {
      options.value.backend = value.default_backend || 'pipeline'
      options.value.effort = value.default_effort || 'medium'
      options.value.parseMethod = value.default_parse_method || 'auto'
      options.value.language = value.default_lang_list || ['ch']
      options.value.maxPages = value.default_max_pages || 99999
    }
  }

  function addHistoryItem(item) {
    history.value.unshift({
      id: item.id || Date.now().toString(),
      name: item.name || '',
      taskId: item.taskId || '',
      outputPath: item.outputPath || '',
      outputDir: item.outputDir || '',
      mdContent: item.mdContent || '',
      txtContent: item.txtContent || '',
      contentListJson: item.contentListJson || '',
      hasImages: item.hasImages || false,
      status: item.status || 'completed',
      timestamp: Date.now(),
    })
    // Keep last 50
    if (history.value.length > 50) {
      history.value = history.value.slice(0, 50)
    }
  }

  function clearHistory() {
    history.value = []
  }

  function loadHistoryItem(item) {
    currentTaskId.value = item.taskId || ''
    currentFileName.value = item.name || ''
    currentOutputPath.value = item.outputPath || ''
    currentOutputDir.value = item.outputDir || ''
    currentMdContent.value = item.mdContent || ''
    currentTxtContent.value = item.txtContent || item.mdContent || ''
    currentContentListJson.value = item.contentListJson || ''
    currentHasImages.value = item.hasImages || false
    currentPreviewPdfUrl.value = item.taskId ? `/api/preview/${item.taskId}` : ''
    statusLines.value = item.taskId ? ['已从历史记录恢复'] : []
    conversionProgress.value = item.taskId ? 100 : 0
  }

  function clearCurrent() {
    currentTaskId.value = ''
    currentFileName.value = ''
    currentOutputPath.value = ''
    currentOutputDir.value = ''
    currentMdContent.value = ''
    currentTxtContent.value = ''
    currentContentListJson.value = ''
    currentHasImages.value = false
    currentPreviewPdfUrl.value = ''
    statusLines.value = []
    conversionProgress.value = 0
    uploadedFile.value = null
    sourceUrl.value = ''
    htmlContent.value = ''
    htmlFile.value = null
  }

  function appendStatus(line) {
    statusLines.value.push(line)
    if (statusLines.value.length > 200) {
      statusLines.value.shift()
    }
  }

  function setStatus(lines) {
    statusLines.value = Array.isArray(lines) ? lines : [lines]
  }

  function setProgress(value) {
    const nextValue = Number(value)
    if (!Number.isFinite(nextValue)) return
    conversionProgress.value = Math.max(0, Math.min(100, Math.round(nextValue)))
  }

  return {
    config,
    history,
    currentTaskId,
    currentFileName,
    currentOutputPath,
    currentOutputDir,
    currentMdContent,
    currentTxtContent,
    currentContentListJson,
    currentHasImages,
    currentPreviewPdfUrl,
    statusLines,
    conversionProgress,
    isConverting,
    activeTab,
    uploadedFile,
    sourceUrl,
    htmlContent,
    htmlFile,
    options,
    isHttpClientBackend,
    showHybridEffort,
    showImageAnalysis,
    showOcrLanguage,
    showForceOcr,
    showServerUrl,
    setConfig,
    addHistoryItem,
    clearHistory,
    loadHistoryItem,
    clearCurrent,
    appendStatus,
    setStatus,
    setProgress,
  }
})
