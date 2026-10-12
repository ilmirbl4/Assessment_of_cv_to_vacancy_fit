import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rolldownOptions: {
      output: {
        // Крупные библиотеки выносятся в отдельные чанки, чтобы ни один не превышал 500 КБ.
        codeSplitting: {
          groups: [
            { name: 'vendor-react', test: /node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/ },
            { name: 'vendor-ui', test: /node_modules[\\/](@headlessui|@floating-ui|@react-aria|lucide-react)[\\/]/ },
            { name: 'vendor-data', test: /node_modules[\\/](@tanstack|zod|react-hook-form|@hookform)[\\/]/ },
          ],
        },
      },
    },
  },
  server: {
    proxy: { '/api': 'http://localhost:8000' }, // реальный backend, когда моки выключены
  },
});
