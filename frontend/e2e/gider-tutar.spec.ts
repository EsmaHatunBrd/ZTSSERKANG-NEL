import { expect, test } from "@playwright/test";

// Yazma istekleri ve ilk açılış diyaloğu kullanıcı adı ister: testlerde ad önceden kayıtlıdır.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
});

// Not: e2e/kurulum.py her koşuda veri/e2e.db'yi silip gerçek kitabı yeniden yükler; değişiklik sonraki koşuları etkilemez.
test("gider: havuzu taban × çarpan ve alt kalem tutarıyla kaydet -> kartta Gider Toplamı ve çarpan satırı güncellenir", async ({ page }) => {
  await page.goto("/gider?senaryo=1");
  await expect(page.getByRole("heading", { name: "Gider Dağıtım" })).toBeVisible();

  // Anahtarlı bir havuz (elektrik: hat payları). Kartın mevcut toplamını oku.
  const kart = page.locator("section[aria-labelledby='havuz-elektrik']");
  await expect(kart).toBeVisible();
  await kart.getByRole("button", { name: "Havuzu düzenle elektrik" }).click();
  const diyalog = page.getByRole("dialog", { name: "Havuzu düzenle: elektrik" });
  await expect(diyalog).toBeVisible();

  // B3: Excel'deki '=8400000*1.4*1.2' formülü taban + iki çarpan olarak gelir (8.400.000 × 1,4 × 1,2 = 14.112.000 TL).
  await expect(diyalog.getByLabel("Taban tutar (TL)")).toHaveValue(/^8\.?400\.?000/);
  await expect(diyalog.getByLabel("Çarpan adı 1")).toHaveValue("Excel çarpanı 1");
  await expect(diyalog.getByTestId("form-gider-toplami")).toHaveText("14.112.000,00 TL");

  // Taban × çarpan: 1.000.000 × 1,25 = 1.250.000 TL (canlı hesap). İkinci Excel çarpanı silinir, ilki SGK olur.
  await diyalog.getByRole("button", { name: "Çarpanı sil 2" }).click();
  await diyalog.getByLabel("Taban tutar (TL)").fill("1000000");
  await diyalog.getByLabel("Çarpan adı 1").fill("SGK");
  await diyalog.getByLabel("Çarpan 1").fill("1,25");
  await expect(diyalog.getByTestId("form-gider-toplami")).toHaveText("1.250.000,00 TL");

  // Dokunulmayan satırlar payını korur (tutarları yeni toplama göre yenilenir); ilk satır elle 470.000 TL = %37,6 yazılır.
  // Kitaptaki elektrik payları %100 topladığından ilk satırın payı değişmeyince toplam %100 kalır ve onay diyaloğu çıkmaz.
  // Kitaptaki paylar tam %100 toplamayabilir (Excel yuvarlaması): toplam %100 değilse mevcut onay diyaloğu çıkar ve geçilir.
  await diyalog.getByLabel("Tutar (TL) 1").fill("470000");
  await expect(diyalog.getByTestId("form-pay-1")).toHaveText("37,6 %");
  const tam = (await diyalog.getByTestId("form-pay-toplam").innerText()).trim() === "100,0 %";
  await diyalog.getByLabel("Neden").fill(`E2E çarpanlı giriş ${Date.now()}`);
  await diyalog.getByRole("button", { name: "Kaydet" }).click();
  if (!tam) {
    const onay = page.getByRole("dialog", { name: "Pay toplamı %100 değil" });
    await expect(onay).toBeVisible();
    await onay.getByRole("button", { name: "Yine de kaydet" }).click();
  }
  await expect(page.getByRole("status")).toContainText("kaydedildi");

  // Kart: Gider Toplamı yeni değer, çarpan satırı ve ilk alt kalemin tutarı.
  await expect(kart.getByTestId("carpan-elektrik")).toContainText("1.000.000,00 × 1,25 = 1.250.000,00 TL");
  await expect(kart.getByRole("row", { name: /Toplam/ }).last()).toContainText("1.250.000,00 TL");
  await expect(kart.locator("tbody tr").first()).toContainText("470.000,00 TL");
  await expect(kart.locator("tbody tr").first()).toContainText("37,6 %");
});
