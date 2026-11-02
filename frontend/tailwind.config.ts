import type { Config } from "tailwindcss";

// Tailwind v4: tema CSS icinde (src/index.css) tanimlidir; bu dosya @config ile yuklenir.
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
} satisfies Config;
