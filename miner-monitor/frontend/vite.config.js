import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5001,
    proxy: {
      '/api': { target: 'http://localhost:5002', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:5002',  changeOrigin: true, ws: true },
    },
  },
})
