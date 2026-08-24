/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        canvas: { light: "#FAF8F5", dark: "#141312" },
        charcoal: {
          50: "#F5F4F3", 100: "#E6E4E2", 200: "#CBC7C3", 300: "#A6A09A",
          400: "#7C756D", 500: "#57514B", 600: "#3D3833", 700: "#2A2622",
          800: "#1D1A17", 900: "#12100E",
        },
        rose: {
          50: "#FBF0EF", 100: "#F4D9D6", 200: "#E7B3AC", 300: "#D68C81",
          400: "#C06D5F", 500: "#A44E3F", 600: "#7C3B30", 700: "#5A2A22",
        },
        sand: {
          50: "#FAF7F2", 100: "#F0E9DE", 200: "#E2D5C1", 300: "#CFBB9C",
        },
      },
      fontFamily: {
        display: ["'Playfair Display'", "serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 2px 20px rgba(20, 19, 18, 0.06)",
        card: "0 8px 30px rgba(20, 19, 18, 0.08)",
      },
      borderRadius: {
        xl2: "1.25rem",
      },
    },
  },
  plugins: [],
};
