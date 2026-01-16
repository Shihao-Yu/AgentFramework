import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/web-component.tsx'),
      name: 'AdminUIWidget',
      formats: ['es'],
      fileName: (format) => `context-management-widget.${format}.js`,
    },
    rollupOptions: {
      output: {
        assetFileNames: 'context-management-widget.[ext]',
        globals: {},
        inlineDynamicImports: false,
        manualChunks: undefined,
      },
    },
    cssCodeSplit: false,
    sourcemap: true,
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: false,
        drop_debugger: true,
      },
    },
    outDir: 'dist-wc',
    emptyOutDir: true,
  },
})
