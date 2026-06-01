import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default defineConfig({
  plugins: [react() as any, tailwindcss() as any],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
