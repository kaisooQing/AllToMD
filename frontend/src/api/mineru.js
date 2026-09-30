import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000, // global default: 30s
})

export async function getConfig() {
  const { data } = await api.get('/api/config', { timeout: 10000 })
  return data
}

export async function submitTask(formData, timeout = 120000) {
  const { data } = await api.post('/tasks', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout, // 默认 2 min，大文件可传入更长超时
  })
  return data
}

export async function getTaskStatus(taskId) {
  const { data } = await api.get(`/tasks/${taskId}`, { timeout: 10000 })
  return data
}

export async function getTaskResult(taskId) {
  const response = await api.get(`/tasks/${taskId}/result`, {
    responseType: 'blob',
    timeout: 60000, // 1 min for ZIP download
  })
  return response
}

export async function cancelTask(taskId) {
  const { data } = await api.delete(`/tasks/${taskId}`, { timeout: 10000 })
  return data
}

export async function getUrlHtmlResultDownload(taskId) {
  const response = await api.get(`/api/download/${taskId}`, {
    responseType: 'blob',
    timeout: 60000, // 1 min for ZIP download
  })
  return response
}

export async function convertUrlHtml(formData) {
  const { data } = await api.post('/api/convert/url_html', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 minutes — image downloads are concurrent & capped
  })
  return data
}

export async function openOutputDir(outputDir) {
  const { data } = await api.post('/api/open-output-dir', { output_dir: outputDir }, { timeout: 15000 })
  return data
}

export async function getResultFileUrl(taskId, path) {
  return `/api/files/${taskId}/${encodeURIComponent(path).replace(/%2F/g, '/')}`
}

export async function getPreviewPdfUrl(taskId) {
  return `/api/preview/${taskId}`
}

export default api
