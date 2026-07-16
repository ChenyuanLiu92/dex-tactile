import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: false,
  use: {
    baseURL: 'http://127.0.0.1:5187',
    browserName: 'chromium',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: 'npm run dev -- --port 5187 --strictPort',
    url: 'http://127.0.0.1:5187',
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
