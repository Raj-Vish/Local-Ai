import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Pinned, because the backend's CORS allowlist names this exact origin.
    // strictPort makes a clash fail loudly instead of silently moving to the
    // next free port, which would leave every API call blocked by CORS with
    // no obvious cause. 5173/5174 are used by other projects on this machine.
    port: 5180,
    strictPort: true,
  },
})
