/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'var(--color-ink)',
        panel: 'var(--color-panel)',
        line: 'var(--color-line)',
        neon: 'var(--color-neon)',
        acid: 'var(--color-acid)',
        ice: 'var(--color-ice)',
        hot: 'var(--color-hot)',
        dim: 'var(--color-dim)',
        'ink-fg': 'var(--color-fg)',
        'ink-muted': 'var(--color-fg-muted)',
        heading: 'var(--color-heading)',
      },
      fontFamily: {
        display: ['"Chakra Petch"', 'sans-serif'],
        mono: ['"Share Tech Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        neon: 'var(--shadow-neon)',
        acid: 'var(--shadow-acid)',
      },
    },
  },
  plugins: [],
};
