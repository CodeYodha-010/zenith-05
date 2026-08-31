import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy: the browser only ever talks to one origin, so the Django
// session cookie flows to /api without any CORS configuration.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
