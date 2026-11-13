import { expect, test } from "@playwright/test";
import { DASHBOARD_BEKLEME_MS } from "./sabitler";

// Veri Kontrolü (D7): gerçek kitapta bilinen veri sorunları (fiyatsız malzeme, geçici kodlar, 02/03 kod sorunu) görünür; kayda tıklayınca
// ilgili liste süzülmüş açılır; Genel Bakış'ta özet bağlantısı vardır. Sayılar kitaba bağlı olduğundan yalnız varlıkları denetlenir.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
  // Düzenleme kilidi uygulamada kilitli başlar; yazma yapan senaryolar için sekmede açık başlatılır.
  await page.addInitScript(() => sessionStorage.setItem("fiyat-calismasi.duzenleme-acik-bitis", String(Date.now() + 3_600_000)));
});

test("veri kontrolü: kontroller ve çözüm bağlantıları; fiyatsız malzemeye tıklayınca Malzeme Fiyatları süzülür; Genel Bakış şeridi", async ({
  page,
}) => {
  await page.goto("/veri-kontrolu?senaryo=1");
  const fiyat = page.getByRole("region", { name: "Fiyatı olmayan malzeme" });
  await expect(fiyat).toContainText("Dikkat", { timeout: DASHBOARD_BEKLEME_MS });
  await expect(page.getByRole("region", { name: "Geçici kodlu ürün" })).toContainText("12 kayıt");
  await expect(page.getByRole("region", { name: "Üretim Adetleri'nde eşleşmeyen kod" })).toContainText("Dikkat");
  await expect(page.getByRole("region", { name: "Reçetesi olmayan ürün" })).toContainText("Tamam");

  await fiyat.getByRole("button", { name: "Kayıtlar" }).click();
  const ilk = fiyat.getByRole("listitem").first().getByRole("link");
  const kod = ((await ilk.textContent()) ?? "").split(" · ")[0];
  await ilk.click();
  await expect(page).toHaveURL(/\/fiyatlar\?fiyatsiz=1&arama=/);
  await expect(page.getByRole("table")).toContainText(kod, { timeout: DASHBOARD_BEKLEME_MS });

  await page.goto("/genel-bakis?senaryo=1");
  const serit = page.getByRole("status", { name: "Veri Kontrolü" });
  await expect(serit).toContainText("konu ilgi bekliyor", { timeout: DASHBOARD_BEKLEME_MS });
  await serit.getByRole("link").click();
  await expect(page).toHaveURL(/\/veri-kontrolu\?senaryo=1/);
});
