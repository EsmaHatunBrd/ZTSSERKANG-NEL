import { expect, test } from "@playwright/test";
import { E2E_URUN_KODU } from "./sabitler";

// Yazma istekleri ve ilk açılış diyaloğu kullanıcı adı ister: testlerde ad önceden kayıtlıdır.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
});

// Not: e2e/kurulum.py her koşuda veri/e2e.db'yi silip gerçek kitabı yeniden yükler; bu yüzden kur değişikliği
// sonraki koşuları etkilemez ve testin sonunda eski kuru geri yazmaya gerek yoktur.
test("kur: ürün ekranında USD kurunu değiştir -> Senaryo geneli -> Kaydet -> Parametreler geçmişinde yeni satır", async ({ page }) => {
  // Dashboard'a bağlı değil: ürün ekranı doğrudan açılır.
  await page.goto(`/urunler/${encodeURIComponent(E2E_URUN_KODU)}?senaryo=1`);
  await expect(page).toHaveURL(/\/urunler\/[^/?]+\?senaryo=\d+/);

  const kurlar = page.getByRole("region", { name: "Kurlar ve enflasyon" });
  const usd = kurlar.getByRole("textbox", { name: "Kur USD" });
  await expect(usd).toBeVisible();
  const eski = Number((await usd.inputValue()).replace(",", "."));
  const yeni = String(Math.floor(eski) + 3);
  await usd.fill(yeni);
  await expect(page.getByText("1 alanda değişiklik")).toBeVisible();

  // Diyalog: kur senaryo genelidir, tüm ürünleri etkiler.
  await page.getByRole("button", { name: "Kaydet" }).click();
  const diyalog = page.getByRole("dialog");
  await expect(diyalog.getByText(/Senaryo geneli — (tüm ürünleri|\d+ ürünü) etkiler/)).toBeVisible();
  const neden = `E2E kur güncellemesi ${Date.now()}`;
  await diyalog.getByLabel("Neden").fill(neden);
  await diyalog.getByRole("button", { name: "Onayla ve kaydet" }).click();
  await expect(page.getByRole("status", { name: "Kayıt durumu" })).toContainText(/Kaydedildi · Hesap #\d+/);

  // Parametreler sayfası: kur.USD geçmişinde yeni değer ve neden görünür.
  await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Parametreler" }).click();
  await expect(page).toHaveURL(/\/parametreler/);
  await page.getByRole("button", { name: "Geçmiş kur.USD" }).click();
  const cekmece = page.getByRole("dialog");
  await expect(cekmece.getByText(neden)).toBeVisible();
  await expect(cekmece.locator("li").first()).toContainText(yeni.replace(".", ","));
});
