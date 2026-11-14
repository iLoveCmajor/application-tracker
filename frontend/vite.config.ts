/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The UI calls /api/v1 (and /health, /ready) on its own origin; these forward them to the FastAPI backend.
const backend = 'http://localhost:8000'
const proxy = { '/api': backend, '/health': backend, '/ready': backend }

export default defineConfig({
  plugins: [react()],
  server: { proxy },
  preview: { proxy },
  test: {
    environment: 'node',
  },
})
