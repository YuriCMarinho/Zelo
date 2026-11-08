import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // Testes de UI com jsdom + userEvent passam de 5 s quando a suíte inteira roda em paralelo.
  test: { environment: 'jsdom', setupFiles: ['./src/test-setup.ts'], testTimeout: 15000 },
})
