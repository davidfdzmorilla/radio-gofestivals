import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/unit/setup.ts'],
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    globals: true,
    server: {
      deps: {
        // next-intl es ESM puro e importa "next/navigation" sin extensión;
        // externalizado lo resuelve Node (y falla porque next no tiene
        // exports map). Inlineado lo procesa Vite y aplica el alias de abajo.
        inline: ['next-intl'],
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/app/**', 'src/components/**'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // next no publica "exports" map: los imports sin extensión que hace
      // next-intl (ESM) solo resuelven dentro del bundler de Next. Fuera
      // (Vitest/Vite) hay que apuntar al stub .js explícitamente.
      'next/navigation': path.resolve(__dirname, 'node_modules/next/navigation.js'),
      'next/link': path.resolve(__dirname, 'node_modules/next/link.js'),
    },
  },
});
