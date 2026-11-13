import path from "node:path";
import { expect, test } from "@playwright/test";

// Gerçek kitap: e2e/kurulum.py aynı dosyayı yüklediği için ana ürün sayfalarının reçetesi "Aynı" çıkar ve seçili gelmez;
// '(2)' varyant sayfaları farklıdır ama varsayılan seçili değildir. Değişiklik sonraki koşuları etkilemez (kurulum DB'yi siler).
const KITAP = path.resolve(process.cwd(), "..", "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"); // playwright frontend/ klasöründen koşar

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
  // Düzenleme kilidi uygulamada kilitli başlar; yazma yapan senaryolar için sekmede açık başlatılır.
  await page.addInitScript(() => sessionStorage.setItem("fiyat-calismasi.duzenleme-acik-bitis", String(Date.now() + 3_600_000)));
});

test("reçete: kitaptan önizle -> aynı sayfalar seçili değil -> varyantı seç, neden, uygula -> yeni versiyon", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("/recete-aktar?senaryo=1");
  await page.getByRole("tab", { name: "Ürün reçetesi" }).click();
  const form = page.getByRole("form", { name: "Dosyadan reçete aktar" });
  await form.getByLabel("Excel dosyası").setInputFiles(KITAP);
  await form.getByRole("button", { name: "Önizle" }).click();

  const tablo = form.getByRole("region", { name: "Ürün sayfaları" });
  await expect(tablo).toBeVisible({ timeout: 120_000 });
  // 67 ürün sayfası + 2 varyant; kodsuz 056-067 geçici SAYFA-0xx koduyla eşlenir, okunamayan sayfa yok.
  await expect(tablo.getByRole("heading")).toContainText("Ürün sayfaları (69)");
  await expect(form.getByRole("region", { name: "Okunamayan sayfalar" })).toHaveCount(0);
  // Varyantlar önerilmez. (Önceki e2e testleri 001'in reçetesini değiştirmiş olabilir: o zaman 001 'Değişti' ve seçili gelir.)
  const varyant = form.getByRole("checkbox", { name: /^Uygula: 001 \(2\)/ });
  await expect(varyant).not.toBeChecked();
  await expect(form.getByRole("checkbox", { name: /^Uygula: 035 \(2\)/ })).not.toBeChecked();
  const asil = form.getByRole("checkbox", { name: /^Uygula: 001 [^(]/ });
  if (await asil.isChecked()) await asil.uncheck(); // aynı ürün için iki sayfa seçilemez
  for (const k of await form.getByRole("checkbox", { checked: true }).all()) await k.uncheck();
  await expect(form.getByRole("button", { name: "Uygula" })).toBeDisabled();
  await varyant.check();
  await form.getByLabel("Neden").fill(`E2E varyant reçetesi ${Date.now()}`);
  await form.getByRole("button", { name: "Uygula" }).click();

  const ozet = page.getByRole("region", { name: "Aktarım özeti" });
  await expect(ozet).toBeVisible({ timeout: 120_000 });
  await expect(ozet).toContainText(/001 \(2\): .+ → v2/);
});
