import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // Applies in dev too, not just the production build -- the dev server
  // serves the app at http://localhost:5173/glassbox/ (redirecting `/`
  // there), not at `/`. import.meta.env.BASE_URL is '/glassbox/' in both
  // dev and prod, so main.tsx's router `basename` and data.ts's fetch base
  // stay correct without branching on `command`/`mode`.
  base: '/glassbox/',
  plugins: [react(), tailwindcss()],
})
