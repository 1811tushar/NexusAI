import { defineConfig } from '@playwright/test'

// Mocks (default): starts the Vite dev server with MSW. Real stack: E2E_BASE_URL=http://localhost:3000 (see README).
const real = !!process.env.E2E_BASE_URL
export default defineConfig({
  testDir: '.',
  timeout: real ? 240_000 : 90_000,
  expect: { timeout: real ? 60_000 : 10_000 },
  use: { baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173' },
  webServer: real ? undefined : { command: 'npm run dev', env: { VITE_USE_MOCKS: 'true' }, url: 'http://localhost:5173', reuseExistingServer: true },
})
