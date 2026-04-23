import type { Config } from 'tailwindcss';

export default {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          0: 'var(--bg-0)',
          1: 'var(--bg-1)',
          2: 'var(--bg-2)',
          3: 'var(--bg-3)',
        },
        fg: {
          0: 'var(--fg-0)',
          1: 'var(--fg-1)',
          2: 'var(--fg-2)',
          3: 'var(--fg-3)',
        },
        magenta: {
          DEFAULT: 'var(--magenta)',
          soft: 'var(--magenta-soft)',
        },
        cyan: {
          DEFAULT: 'var(--cyan)',
          soft: 'var(--cyan-soft)',
        },
        wave: {
          DEFAULT: 'var(--wave)',
          soft: 'var(--wave-soft)',
        },
        warm: 'var(--accent-warm)',
        ink: 'var(--bg-1)',
      },
      fontFamily: {
        display: ['Chillax', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        body: ['Satoshi', 'Chillax', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      rotate: {
        '0.5': '0.5deg',
        '1': '1deg',
        '1.5': '1.5deg',
      },
      boxShadow: {
        'sticker-sm': 'var(--sticker-shadow-sm)',
        sticker: 'var(--sticker-shadow-md)',
        'sticker-lg': 'var(--sticker-shadow-lg)',
        'sticker-magenta': 'var(--sticker-shadow-magenta)',
        'sticker-cyan': 'var(--sticker-shadow-cyan)',
      },
    },
  },
  plugins: [],
} satisfies Config;
