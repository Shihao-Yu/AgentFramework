import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@common/context-management-widget': path.resolve(__dirname, '../../dist-wc/context-management-widget.es.js'),
    },
  },
  server: {
    port: 3001,
  },
})
