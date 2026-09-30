/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Neutral financial-portal surfaces
        surface: {
          950: 'var(--ifg-canvas)',
          900: 'var(--ifg-surface)',
          800: 'var(--ifg-surface-muted)',
          700: 'var(--ifg-border)',
          600: 'var(--ifg-border-strong)',
          500: 'var(--ifg-muted)',
        },
        // Brand accent — steel blue
        brand: {
          400: 'var(--ifg-primary-soft)',
          500: 'var(--ifg-primary)',
          600: 'var(--ifg-primary-strong)',
        },
        // Risk levels
        risk: {
          low: 'var(--ifg-risk-low)',
          medium: 'var(--ifg-risk-medium)',
          high: 'var(--ifg-risk-high)',
          critical: 'var(--ifg-risk-critical)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
          lg: '0.5rem',
      },
    },
  },
  plugins: [],
}
