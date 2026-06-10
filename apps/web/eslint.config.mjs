import { defineConfig } from 'eslint/config';
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';

export default defineConfig([
  {
    ignores: [
      '.next/**',
      'node_modules/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'next-env.d.ts',
    ],
  },
  {
    extends: [...nextCoreWebVitals],
    rules: {
      // Regla nueva de react-hooks v6 (eslint-config-next 16). Marca 18
      // patrones preexistentes (init/fetch con setState en efecto) que
      // funcionan; adopción incremental — TODO(david, 2026-06-10).
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
]);
