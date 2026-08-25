/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        ink: {
          50: "#ffffff",
          100: "#f9f9f9",
          200: "#f3f3f3",
          300: "#e0e0e0",
          400: "#b4b4b4",
          500: "#8e8e8e",
          600: "#6e6e6e",
          700: "#4a4a4a",
          800: "#2f2f2f",
          900: "#212121",
          950: "#0d0d0d",
        },
        // brand: {
        //   50: "#e6f7f1",
        //   100: "#d1f0e4",
        //   200: "#a3e1c9",
        //   300: "#6ecdaa",
        //   400: "#10a37f",
        //   500: "#0d8a6a",
        //   600: "#0b7559",
        //   700: "#095e47",
        //   800: "#074836",
        //   900: "#053224",
        //   950: "#021f17",
        // },
        brand: {
          50: "#EAF2FB",
          100: "#D6E5F7",
          200: "#AFCBEF",
          300: "#81ADE5",
          400: "#4D87D6",
          500: "#003D7C", // NUS Blue
          600: "#00366D",
          700: "#002E5C",
          800: "#00264A",
          900: "#001B35",
        },
        royal: {
          50: "#f0fdfa",
          100: "#d1f7ee",
          200: "#a3efdd",
          300: "#6ee3c9",
          400: "#10a37f",
          500: "#0d8a6a",
          600: "#0b7559",
          700: "#095e47",
          800: "#074836",
          900: "#053224",
          950: "#021f17",
        },
        emerald2: {
          400: "#34d399",
          500: "#10b981",
          600: "#059669",
        },
        cyan2: {
          400: "#22d3ee",
          500: "#06b6d4",
          600: "#0891b2",
        },
      },
      boxShadow: {
        glass: "none",
        soft: "none",
        glow: "none",
      },
      backdropBlur: {
        xs: "0px",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: 0, transform: "translateY(6px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        pulseDot: {
          "0%, 100%": { opacity: 0.4 },
          "50%": { opacity: 1 },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        fadeIn: "fadeIn 0.4s ease-out",
        pulseDot: "pulseDot 1.2s ease-in-out infinite",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [],
};
