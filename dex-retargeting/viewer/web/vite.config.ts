import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',
  build: { assetsDir: 'web-assets' },
  server: {
    port: 5178,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8787', ws: true },
      '/assets': { target: 'http://127.0.0.1:8787' },
    },
  },
})
