import path from "node:path";
import { expect, test } from "@playwright/test";
import { DASHBOARD_BEKLEME_MS } from "./sabitler";

// Faz 6 uçtan uca: deneme gerçekleşen kitabı (scripts/10-27-2026-gerceklesen-deneme-uret.py; asıl kitabın kopyası, olası gerçek
// değerler) Veri Aktar'dan "Gerçekleşen" türüyle aynı sezona yüklenir, sonra Bütçe vs Gerçekleşen ekranları açılır.
// e2e/kurulum.py DB'yi her koşuda sıfırlar: burada açılan senaryo sonraki koşuları etkilemez.
const DENEME = path.resolve(process.cwd(), "..", "10-27-2026-gerceklesen-deneme-2026-2027.xlsx"); // playwright frontend/ klasöründen koşar

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
  // Düzenleme kilidi uygulamada kilitli başlar; yazma yapan senaryolar için sekmede açık başlatılır.
  await page.addInitScript(() => sessionStorage.setItem("fiyat-calismasi.duzenleme-acik-bitis", String(Date.now() + 3_600_000)));
});

test("gerçekleşen: Excel'i Gerçekleşen türüyle yükle -> kıyas listesi, sapan süzgeci, ürün sapma kaynağı, Genel Bakış şeridi", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await page.goto("/recete-aktar?senaryo=1");
  await page.getByRole("tab", { name: "Tüm çalışma kitabı" }).click();
  const form = page.getByRole("form", { name: "Tüm çalışma kitabını içe aktar" });
  await form.getByLabel("Yeni senaryo oluştur").check();
  await form.getByLabel("Excel dosyası").setInputFiles(DENEME);
  await form.getByLabel("Sezon adı").fill("2026-2027");
  await form.getByLabel("Senaryo adı").fill("E2E Gerçekleşen");
  await form.getByLabel("Tür").selectOption("gerceklesen");
  await form.getByRole("button", { name: "İçe aktar" }).click();
  await expect(page.getByRole("region", { name: "İçe aktarma özeti" })).toBeVisible({ timeout: 180_000 });

  // Bütçe (#1) seçiliyken varsayılan B aynı sezonun gerçekleşenidir.
  await page.goto("/butce-gerceklesen?senaryo=1");
  await expect(page.getByLabel("Gerçekleşen senaryosu").locator("option:checked")).toContainText("E2E Gerçekleşen");
  const tablo = page.getByRole("table");
  await expect(tablo.getByRole("row")).toHaveCount(68, { timeout: DASHBOARD_BEKLEME_MS }); // başlık + 67 ürün
  await expect(page.getByText("Karşılaştırılan ürün").locator("..")).toContainText("67");

  // Kutu URL'den okunur; URL değişimi React Router'da geçiş (transition) olduğundan işaret tablo yeniden çizilince görünür:
  // check() anlık durum bakar, burada tıklanıp işaret beklenir.
  await expect(page.getByText("Maliyet sapması dağılımı")).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  const sapanKutusu = page.getByRole("checkbox", { name: "Yalnız sapanlar" });
  await sapanKutusu.click();
  await expect(sapanKutusu).toBeChecked();
  await expect(page).toHaveURL(/sapan=1/);
  const sapanSatir = await tablo.getByRole("row").count();
  expect(sapanSatir).toBeGreaterThan(1);
  expect(sapanSatir).toBeLessThan(68);

  await tablo.getByRole("row").nth(1).click();
  await expect(page).toHaveURL(/\/butce-gerceklesen\/[^?]+\?/);
  const kaynak = page.getByRole("region", { name: "Sapmanın kaynağı" });
  await expect(kaynak).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  for (const e of [
    "Malzeme fiyatları",
    "Reçete (miktar, fire, elle fiyat)",
    "Üretim bilgileri",
    "Giderler (oran ve elle)",
    "Döviz kurları",
    "Enflasyon",
  ]) {
    await expect(kaynak.getByText(e, { exact: true })).toBeVisible();
  }
  await expect(page.getByRole("region", { name: "Parametreler" })).toContainText("kur.USD");

  await page.goto("/genel-bakis?senaryo=1");
  await expect(page.getByRole("status", { name: "Gerçekleşen kıyası" })).toContainText("67 üründen", { timeout: DASHBOARD_BEKLEME_MS });
});
