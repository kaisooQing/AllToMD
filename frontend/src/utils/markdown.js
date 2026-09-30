import { marked } from 'marked'
import katex from 'katex'
import 'katex/dist/katex.min.css'

marked.setOptions({
  breaks: true,
  gfm: true,
})

function renderKatex(text) {
  // Render block math: $$...$$
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), { throwOnError: false, displayMode: true })
    } catch {
      return `<pre>${math}</pre>`
    }
  })

  // Render inline math: $...$
  text = text.replace(/([^\$]|^)\$([^\$\n]+?)\$([^\$]|$)/g, (match, before, math, after) => {
    try {
      return `${before}${katex.renderToString(math.trim(), { throwOnError: false, displayMode: false })}${after}`
    } catch {
      return `${before}<code>${math}</code>${after}`
    }
  })

  return text
}

export function renderMarkdown(text) {
  if (!text) return ''
  const withMath = renderKatex(text)
  return marked.parse(withMath)
}
