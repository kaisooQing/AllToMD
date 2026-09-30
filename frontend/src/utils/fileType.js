export function getFileExtension(name = '') {
  const cleanName = String(name || '').split('?')[0].split('#')[0]
  const match = cleanName.match(/\.([^.\\/]+)$/)
  return match ? match[1].toLowerCase() : ''
}

export function getFileKind(name = '', taskId = '') {
  if (String(taskId || '').startsWith('web_')) return 'url'

  const ext = getFileExtension(name)
  if (['xls', 'xlsx', 'csv', 'tsv'].includes(ext)) return 'excel'
  if (['doc', 'docx'].includes(ext)) return 'word'
  if (['ppt', 'pptx'].includes(ext)) return 'ppt'
  if (ext === 'pdf') return 'pdf'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff', 'svg'].includes(ext)) return 'image'
  if (['html', 'htm'].includes(ext)) return 'html'
  if (ext === 'md') return 'markdown'
  if (ext === 'json') return 'json'
  return 'file'
}

export function getFileTypeLabel(name = '', taskId = '') {
  const kind = getFileKind(name, taskId)
  const ext = getFileExtension(name)
  const labels = {
    excel: ext ? ext.toUpperCase() : 'XLS',
    word: ext ? ext.toUpperCase() : 'DOC',
    ppt: ext ? ext.toUpperCase() : 'PPT',
    pdf: 'PDF',
    image: ext ? ext.toUpperCase() : 'IMG',
    html: 'HTML',
    url: 'URL',
    markdown: 'MD',
    json: 'JSON',
    file: ext ? ext.toUpperCase() : 'FILE',
  }
  return labels[kind] || 'FILE'
}
