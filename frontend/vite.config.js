import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // .env lives at the repo root (sibling to frontend/ and backend/), not here —
  // this is the only backend/frontend config split by folder, so both read from
  // one file. Vite still only exposes VITE_-prefixed keys to client code.
  envDir: '../',
})
