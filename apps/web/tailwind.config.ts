import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        magenta: {
          DEFAULT: 'var(--magenta)',
          50: 'var(--magenta-50)',
          700: 'var(--magenta-700)',
          900: 'var(--magenta-900)',
        },
        cyan: {
          DEFAULT: 'var(--cyan)',
          50: 'var(--cyan-50)',
          700: 'var(--cyan-700)',
          900: 'var(--cyan-900)',
        },
        wave: {
          DEFAULT: 'var(--wave)',
          50: 'var(--wave-50)',
          700: 'var(--wave-700)',
        },
        ink: 'var(--ink)',
      },
      fontFamily: {
        display: ['var(--font-display)', 'sans-serif'],
        body: ['var(--font-body)', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config;
