import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api/control-owner': {
        target: 'http://127.0.0.1:8787',
      },
      '/vision': {
        target: 'http://127.0.0.1:8787',
        ws: true,
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup.ts',
    include: ['tests/**/*.test.{ts,tsx}', 'src/vision/**/*.test.{ts,tsx}'],
  },
})
