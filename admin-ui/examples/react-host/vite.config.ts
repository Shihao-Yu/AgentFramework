import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@anthropic/admin-ui-widget': path.resolve(__dirname, '../../dist-wc/admin-ui-widget.es.js'),
    },
  },
  server: {
    port: 3001,
  },
})
