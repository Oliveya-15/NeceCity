/**
 * NeceCity design tokens - "Civic SaaS" system.
 *
 * Palette sampled from the NeceCity logo (navy + orange) layered onto a
 * soft neutral (slate) base, matching a modern data-dashboard aesthetic:
 * light surfaces, generous whitespace, deep-navy/slate for text and
 * structure, orange reserved for accents and calls to action.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#EEF2F8',
          100: '#D6E0EE',
          400: '#274672',
          600: '#0B2A52',
          700: '#08213F',
          900: '#031D46',
        },
        orange: {
          50: '#FFF2E9',
          100: '#FFDDC2',
          500: '#FD6001',
          600: '#E15400',
        },
        // Soft neutral "slate" scale - the base of the new light aesthetic.
        slate: {
          25: '#FCFCFD',
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          900: '#0F172A',
        },
        ink: {
          900: '#0F172A',
          700: '#334155',
          500: '#64748B',
          300: '#94A3B8',
        },
        canvas: '#F6F7FB',
        surface: '#FFFFFF',
        line: '#E7EAF0',
        success: { DEFAULT: '#1E8E5A', bg: '#E8F5EE' },
        warning: { DEFAULT: '#B4680A', bg: '#FDF1E2' },
        danger: { DEFAULT: '#C6303E', bg: '#FBEAEC' },
        info: { DEFAULT: '#2563A8', bg: '#E9F1FA' },
      },
      fontFamily: {
        sans: ['"Public Sans"', 'system-ui', '-apple-system', 'sans-serif'],
      },
      borderRadius: {
        sm: '6px',
        DEFAULT: '10px',
        md: '12px',
        lg: '16px',
        xl: '20px',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgba(16,24,40,0.04), 0 1px 3px 0 rgba(16,24,40,0.06)',
        'card-hover': '0 2px 4px -1px rgba(16,24,40,0.06), 0 4px 12px -2px rgba(16,24,40,0.08)',
        popover: '0 4px 6px -2px rgba(16,24,40,0.05), 0 12px 24px -4px rgba(16,24,40,0.12)',
      },
    },
  },
  plugins: [],
}
