import { expect, test } from "@playwright/test";
import { E2E_URUN_KODU } from "./sabitler";

// Bu dosya düzenleme kilidinin gerçek varsayılanını (kilitli) sınar: sessionStorage anahtarı BİLEREK ayarlanmaz.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
});

test("düzenleme kilidi: ürün ekranı kilitli açılır -> Düzenlemeyi aç -> reçete girdisi etkin -> Kilitle -> yeniden devre dışı", async ({
  page,
}) => {
  await page.goto(`/urunler/${encodeURIComponent(E2E_URUN_KODU)}?senaryo=1`);

  const serit = page.getByRole("group", { name: "Düzenleme kilidi" });
  await expect(serit).toContainText("Düzenleme kilitli. Değişiklik yapmak için kilidi açın.");

  const tablo = page.getByRole("table", { name: "Reçete tablosu" });
  const miktar = tablo.getByRole("textbox", { name: /^Miktar — / }).first();
  await expect(miktar).toBeVisible();
  await expect(miktar).toBeDisabled();
  const usd = page.getByRole("region", { name: "Kurlar ve enflasyon" }).getByRole("textbox", { name: "Kur USD" });
  await expect(usd).toBeDisabled();

  await serit.getByRole("button", { name: "Düzenlemeyi aç" }).click();
  await expect(serit).toContainText("Düzenleme açık");
  await expect(miktar).toBeEnabled();
  await expect(usd).toBeEnabled();

  // Kilit sekme genelindedir: başka bir kapsam sayfasında da açık görünür.
  await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Parametreler" }).click();
  await expect(page).toHaveURL(/\/parametreler/);
  await expect(page.getByRole("group", { name: "Düzenleme kilidi" })).toContainText("Düzenleme açık");
  await expect(page.getByRole("button", { name: "Değiştir kur.USD" })).toBeEnabled();

  await page.getByRole("group", { name: "Düzenleme kilidi" }).getByRole("button", { name: "Kilitle" }).click();
  await expect(page.getByRole("group", { name: "Düzenleme kilidi" })).toContainText("Düzenleme kilitli");
  await expect(page.getByRole("button", { name: "Değiştir kur.USD" })).toBeDisabled();

  // Kilidin açılması Değişiklik Günlüğü'ne düşer.
  await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Değişiklik Günlüğü" }).click();
  await expect(page.getByText("Düzenleme kilidi açıldı").first()).toBeVisible();
});
