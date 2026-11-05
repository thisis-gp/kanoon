import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  // Only variables with these prefixes reach the browser bundle. Never use an empty prefix: it would expose every env var.
  envPrefix: ['VITE_', 'KANOON_'],
  plugins: [react()],
  resolve:{
    alias:{
      "@": path.resolve(__dirname, './src'),
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
})
