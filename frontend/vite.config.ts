/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Куда проксировать API в разработке (по умолчанию локальный backend на 8000).
const API_TARGET = process.env.LABFLOW_API ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    // В разработке запросы к API и WebSocket проксируются на FastAPI.
    proxy: {
      '/api': { target: API_TARGET, ws: true },
      '/docs': API_TARGET,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    globals: false,
  },
})
