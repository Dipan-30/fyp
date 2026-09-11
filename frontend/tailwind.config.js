/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── Custom dark palette ──────────────────────────────────────────────
        surface: {
          DEFAULT: '#0f1117',   // page background
          card:    '#1a1d27',   // card / panel background
          raised:  '#22263a',   // slightly elevated element
          border:  '#2d3252',   // subtle border
        },
        brand: {
          DEFAULT: '#6366f1',   // indigo-500 — primary accent
          light:   '#818cf8',   // indigo-400
          dark:    '#4f46e5',   // indigo-600
          glow:    '#6366f133', // for glow/shadow effects
        },
        accent: {
          teal:   '#14b8a6',
          purple: '#a855f7',
          amber:  '#f59e0b',
          rose:   '#f43f5e',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
