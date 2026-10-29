import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env from project root first, then frontend directory
  const env = loadEnv(mode, '../', '')
  const frontendEnv = loadEnv(mode, process.cwd(), '')
  const rawApiUrl = env.VITE_API_URL || frontendEnv.VITE_API_URL || process.env.VITE_API_URL
  // Always default in production container builds to clean relative portless reverse proxy path
  const apiUrl = (rawApiUrl && rawApiUrl.startsWith('/markdown-optimizer'))
    ? rawApiUrl
    : '/markdown-optimizer/api/v1'

  return {
    plugins: [react()],
    base: '/markdown-optimizer/',
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl),
    },
    server: {
      port: 5173,
      host: true,
      proxy: {
        '/markdown-optimizer/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/markdown-optimizer/, ''),
        },
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})
