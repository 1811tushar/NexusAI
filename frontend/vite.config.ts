import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: { port: 5173, proxy: { '/api': { target: 'http://localhost:8080', changeOrigin: false } } },
  build: { outDir: 'dist' },
  test: { environment: 'jsdom', globals: true, setupFiles: ['src/setupTests.ts'], exclude: ['e2e/**', 'node_modules/**'] },
})
