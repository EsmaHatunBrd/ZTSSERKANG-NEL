import { expect, test } from "@playwright/test";
import { DASHBOARD_BEKLEME_MS, E2E_URUN_KODU } from "./sabitler";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
  // Düzenleme kilidi uygulamada kilitli başlar; yazma yapan senaryolar için sekmede açık başlatılır.
  await page.addInitScript(() => sessionStorage.setItem("fiyat-calismasi.duzenleme-acik-bitis", String(Date.now() + 3_600_000)));
});

// Gerçek backend + gerçek Excel verisi: aile adları sabit yazılmaz; yapı doğrulanır.
test("karşılaştırma sayfası: çok üyeli aile seçilince tablo (>= 2 satır) ve grafik gelir; URL aileyi taşır", async ({ page }) => {
  await page.goto("/karsilastirma");
  await expect(page).toHaveURL(/senaryo=\d+/);
  const liste = page.getByRole("navigation", { name: "Aile listesi" });
  const cokUyeli = liste.getByRole("button", { name: /\d+ ürün/ }).first();
  await expect(cokUyeli).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await cokUyeli.click();
  await expect(page).toHaveURL(/aile=/);

  const satirlar = page.locator("tr[data-satir]");
  await expect(satirlar.first()).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  expect(await satirlar.count()).toBeGreaterThanOrEqual(2);

  const grafik = page.getByRole("img", { name: /ailesi, ambalaj hacmine göre/ });
  await expect(grafik).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await expect(grafik.locator("svg").first()).toBeVisible();
  expect(await grafik.locator("svg.recharts-surface").count()).toBeGreaterThanOrEqual(2);
});

test("ürün ekranı: Karşılaştırma kartı ve aile rozeti görünür (satış geçmişi yoksa boş durum kabul)", async ({ page }) => {
  await page.goto(`/urunler/${encodeURIComponent(E2E_URUN_KODU)}`);
  const kart = page.getByRole("region", { name: "Karşılaştırma" });
  await expect(kart).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await expect(kart.getByRole("heading", { name: "Geçen yıl" })).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await expect(kart.getByRole("heading", { name: "Enflasyon eşiği" })).toBeVisible();
  await expect(kart.getByRole("heading", { name: "Hedef adetle" })).toBeVisible();
  await expect(page.getByText(/^Aile:/)).toBeVisible();
  // Satış fiyatı (%20) tablosu Excel düzeninde.
  await expect(page.getByRole("table", { name: "Satış fiyatı tablosu" })).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
});
