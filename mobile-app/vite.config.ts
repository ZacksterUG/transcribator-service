import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/mobile-app/',
  server: {
    port: 5175,
  },
})
