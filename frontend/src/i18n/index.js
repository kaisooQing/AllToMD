import { createI18n } from 'vue-i18n'

const messages = {
  zh: {
    app: {
      title: 'AllToMD',
      subtitle: '文档转 Markdown',
      poweredBy: 'Powered by MinerU',
      author: '作者：王小氢',
    },
    history: {
      title: '历史记录',
      empty: '暂无文件',
      clear: '清空历史',
    },
    upload: {
      title: '上传文件',
      dragText: '将文件拖放到这里，或点击上传',
      formats: '支持：PDF、Word（.doc/.docx）、Excel（.xls/.xlsx）、PowerPoint（.ppt/.pptx）、图片、HTML',
      urlHtmlTab: 'URL / HTML',
      fileTab: '文件上传',
      urlPlaceholder: '输入网页链接，或粘贴 HTML 片段',
      htmlFileLabel: '或上传本地 HTML 文件',
      convert: '开始转换',
      clear: '清空',
      status: '状态',
    },
    result: {
      title: '转换结果',
      mdRender: 'Markdown 渲染',
      mdText: 'Markdown 原文',
      contentList: 'JSON内容',
      download: '下载结果',
      copy: '复制 Markdown',
      outputDir: '输出目录',
      openDir: '打开目录',
      noResult: '暂无结果',
    },
    options: {
      title: '高级选项',
      backend: '后端',
      effort: 'Hybrid 强度',
      parseMethod: '解析方式',
      formula: '公式识别',
      table: '表格识别',
      imageAnalysis: '图片/图表分析',
      ocrLanguage: 'OCR 语言',
      forceOcr: '强制 OCR',
      maxPages: '最大页数',
      serverUrl: 'Server URL',
    },
    status: {
      preparing: '准备请求...',
      queued: '排队中',
      processing: '解析中',
      completed: '完成',
      failed: '失败',
    },
  },
  en: {
    app: {
      title: 'AllToMD',
      subtitle: 'Document to Markdown converter powered by MinerU',
      poweredBy: 'Powered by MinerU',
      author: 'Author: Wang Xiaoqing',
    },
    history: {
      title: 'History',
      empty: 'No files yet',
      clear: 'Clear history',
    },
    upload: {
      title: 'Upload',
      dragText: 'Drag files here or click to upload',
      formats: 'Supports: PDF, Word (.doc/.docx), Excel (.xls/.xlsx), PowerPoint (.ppt/.pptx), images, HTML',
      urlHtmlTab: 'URL / HTML',
      fileTab: 'File Upload',
      urlPlaceholder: 'Enter a URL or paste HTML snippet',
      htmlFileLabel: 'Or upload a local HTML file',
      convert: 'Convert',
      clear: 'Clear',
      status: 'Status',
    },
    result: {
      title: 'Result',
      mdRender: 'Markdown Render',
      mdText: 'Markdown Source',
      contentList: 'JSON Content',
      download: 'Download',
      copy: 'Copy Markdown',
      outputDir: 'Output directory',
      openDir: 'Open directory',
      noResult: 'No result yet',
    },
    options: {
      title: 'Advanced Options',
      backend: 'Backend',
      effort: 'Hybrid effort',
      parseMethod: 'Parse method',
      formula: 'Formula parsing',
      table: 'Table parsing',
      imageAnalysis: 'Image/chart analysis',
      ocrLanguage: 'OCR language',
      forceOcr: 'Force OCR',
      maxPages: 'Max pages',
      serverUrl: 'Server URL',
    },
    status: {
      preparing: 'Preparing request...',
      queued: 'Queued',
      processing: 'Processing',
      completed: 'Completed',
      failed: 'Failed',
    },
  },
}

function detectLocale() {
  const lang = navigator.language || navigator.userLanguage || 'en'
  return lang.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en',
  messages,
})

export default i18n
