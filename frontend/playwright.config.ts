import { defineConfig, devices } from "@playwright/test";

const PYTHON = process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python";

// Gerçek backend (e2e/kurulum.py: veri/e2e.db + gerçek Excel import'u, port 8010) ve gerçek Vite dev sunucusu (5190).
// Portlar geliştirme sunucularından (8000/5180) ayrıdır; e2e, açık dev sunucularla yan yana koşabilir.
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  fullyParallel: false,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  // Giriş zorunlu: sunucular kalkınca bir kez giriş yapılır, testler o oturumla başlar (giriş ekranı testi kendi oturumsuz bağlamını kurar).
  globalSetup: "./e2e/giris-kurulumu.ts",
  use: {
    baseURL: "http://127.0.0.1:5190",
    storageState: "e2e/.oturum.json",
    trace: "on-first-retry",
    ...devices["Desktop Chrome"],
    viewport: { width: 1280, height: 800 },
  },
  webServer: [
    {
      command: `"${PYTHON}" e2e/kurulum.py`,
      url: "http://127.0.0.1:8010/api/v1/senaryolar",
      timeout: 180_000,
      reuseExistingServer: false,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5190 --strictPort",
      env: { API_PORT: "8010" },
      url: "http://127.0.0.1:5190",
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
});
