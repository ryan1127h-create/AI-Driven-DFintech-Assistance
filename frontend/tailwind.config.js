/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Space Grotesk", "Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        ink: {
          50: "#f6f7fb",
          100: "#eceef6",
          200: "#d4d8ea",
          300: "#aab1d4",
          400: "#7c85b8",
          500: "#565fa3",
          600: "#3f4885",
          700: "#2f3668",
          800: "#1e2349",
          900: "#12152f",
          950: "#080a1c",
        },
        brand: {
          50: "#eef4ff",
          100: "#d9e6ff",
          200: "#bcd2ff",
          300: "#8eb3ff",
          400: "#598bff",
          500: "#3366ff",
          600: "#1f47f5",
          700: "#1737e1",
          800: "#182fb6",
          900: "#1a2d8f",
          950: "#121d57",
        },
        royal: {
          50: "#f5f3ff",
          100: "#ede9fe",
          200: "#ddd6fe",
          300: "#c4b5fd",
          400: "#a78bfa",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          800: "#5b21b6",
          900: "#4c1d95",
          950: "#2e1065",
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
        glass: "0 8px 32px rgba(8, 10, 28, 0.18)",
        soft: "0 2px 12px rgba(8, 10, 28, 0.08)",
        glow: "0 0 24px rgba(51, 102, 255, 0.25)",
      },
      backdropBlur: {
        xs: "2px",
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
