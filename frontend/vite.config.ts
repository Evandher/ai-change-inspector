import { defineConfig } from 'vitest/config'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'INSPECTOR_')
  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      strictPort: true,
      cors: false,
      headers: { 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'" },
      // The same fixtures feed backend tests and the browser's example buttons.
      fs: {
        allow: ['.', '../examples/diffs'],
        deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/.local/**', '**/*.sqlite3*', '**/*.db*'],
      },
      proxy: {
        '/api': env.INSPECTOR_API_URL || 'http://127.0.0.1:8000',
        '/health': env.INSPECTOR_API_URL || 'http://127.0.0.1:8000',
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      clearMocks: true,
    },
  }
})
