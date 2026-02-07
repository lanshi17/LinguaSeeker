import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
        configure: (proxy, _options) => {
          proxy.on('error', (err, req, res) => {
            console.log('【代理错误】', err.message)
            console.log('  请求:', req.method, req.url)
            if ('writeHead' in res) {
              res.writeHead(500, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({
                error: 'Proxy Error',
                message: err.message,
                hint: 'Backend may not be running on http://localhost:8000'
              }))
            }
          })
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('【代理请求】', req.method?.padEnd(6), req.url)
            console.log('  → 转发到:', proxyReq.path)
          })
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('【代理响应】', proxyRes.statusCode, req.url)
          })
        },
      },
    },
  },
})
