import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  resolve: {
    alias: {
      '@': `${import.meta.dirname}/src`,
    },
  },
  server: {
    watch: {
      // Don't watch large binary files in public/ — prevents EBUSY crashes
      ignored: ['**/public/videos/**', '**/*.mp4', '**/*.webm'],
    },
  },
})
