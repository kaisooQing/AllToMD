import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/tasks': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/file_parse': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:7860',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
