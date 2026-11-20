/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "var(--tg-theme-bg-color, #ffffff)",
        secondary: "var(--tg-theme-secondary-bg-color, #f4f4f5)",
        foreground: "var(--tg-theme-text-color, #000000)",
        muted: "var(--tg-theme-hint-color, #71717a)",
        primary: "var(--tg-theme-button-color, #2481cc)",
        "primary-foreground": "var(--tg-theme-button-text-color, #ffffff)",
      },
    },
  },
  plugins: [],
};
