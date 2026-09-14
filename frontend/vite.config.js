import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // Pin the port instead of letting Vite silently pick
    // the next free one (5173 -> 5174 -> 5176...) whenever
    // a previous dev server is still running. That drift
    // is what made it look like fixes "weren't working" —
    // you were sometimes testing against a stale server on
    // an old port while the backend's CORS allowlist and
    // your own expectations were based on a different one.
    port: 5173,
    strictPort: true,

    // NOTE: this proxy is currently unused by the app —
    // api.js calls http://localhost:8000 directly rather
    // than going through /api. Harmless to keep for later,
    // but it is not what's fixing (or causing) the CORS
    // issue either way.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})