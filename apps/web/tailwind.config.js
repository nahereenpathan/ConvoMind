/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#06152F',
          900: '#0A1B35',
          850: '#0B2342',
          800: '#102C4D',
          700: '#123456',
          600: '#1D4E78',
          500: '#2563EB',
          400: '#3B82F6',
          300: '#B8C7DA',
          200: '#8FA4BD',
          100: '#D1DCEC',
          50: '#F8FAFC',
        },
        brand: {
          50: '#EEF2FF',
          100: '#E0E7FF',
          200: '#C7D2FE',
          300: '#A5B4FC',
          400: '#818CF8',
          500: '#6366F1',
          600: '#4F46E5',
          700: '#4338CA',
          800: '#3730A3',
          900: '#312E81',
          950: '#1E1B4B',
        },
        surface: {
          page: '#06152F',
          sidebar: '#0A1B35',
          header: '#0B2342',
          card: '#102C4D',
          elevated: '#123456',
          border: '#1D4E78',
        },
        convotext: {
          primary: '#F8FAFC',
          secondary: '#B8C7DA',
          muted: '#8FA4BD',
        },
      },
    },
  },
  plugins: [],
}
