/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        teal: {
          50: '#EFFAF8',
          100: '#D9F2ED',
          200: '#B3E5DB',
          300: '#7ED1C1',
          400: '#43B4A0',
          500: '#0F766E', // primary
          600: '#0C615A',
          700: '#0A4E48',
          800: '#083C38',
          900: '#062B28',
        },
        crimson: {
          50: '#FDF2F2',
          100: '#FCE4E4',
          400: '#E5484D',
          500: '#DC2626', // blood accent -- used sparingly
          600: '#B91C1C',
          700: '#991515',
        },
        ink: {
          50: '#F8FAFA',
          100: '#F1F5F4',
          400: '#64748B',
          600: '#475569',
          800: '#1E293B',
          900: '#0F172A',
        },
      },
      fontFamily: {
        display: ['"Sora"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      boxShadow: {
        soft: '0 2px 8px -2px rgba(15, 23, 42, 0.08), 0 4px 16px -4px rgba(15, 23, 42, 0.06)',
        card: '0 1px 2px rgba(15, 23, 42, 0.04), 0 8px 24px -8px rgba(15, 23, 42, 0.10)',
      },
      keyframes: {
        pulseLine: {
          '0%': { strokeDashoffset: '1000' },
          '100%': { strokeDashoffset: '0' },
        },
        floatUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'pulse-line': 'pulseLine 2.4s ease-out forwards',
        'float-up': 'floatUp 0.5s ease-out forwards',
      },
    },
  },
  plugins: [],
}
