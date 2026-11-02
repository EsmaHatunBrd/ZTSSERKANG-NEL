/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
  // Geliştirme portu 5180 (5173 bu makinede başka bir süreç tarafından kullanılıyor).
  // Doluysa Vite bir sonraki boş portu seçer; sabit port için `npm run dev -- --strictPort`.
  // `/api` vekil hedefi: API_PORT ortam değişkeni (varsayılan 8000; e2e 8010 kullanır).
  server: { port: 5180, proxy: { "/api": `http://127.0.0.1:${process.env.API_PORT ?? "8000"}` } },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["src/test/kurulum.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    testTimeout: 10000,
    hookTimeout: 10000,
  },
});
