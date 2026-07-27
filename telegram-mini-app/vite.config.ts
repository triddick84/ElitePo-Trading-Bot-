import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Deployed under the main frontend's public path at /tma/.
// The build outputs into /app/frontend/public/tma/ so React's CRA static
// serving picks it up (no separate deploy pipeline needed).
export default defineConfig({
  plugins: [react()],
  base: '/tma/',
  build: {
    outDir: '../frontend/public/tma',
    emptyOutDir: true,
    assetsDir: 'assets',
    sourcemap: false,
  },
  server: {
    port: 5174,
    strictPort: true,
  },
});
