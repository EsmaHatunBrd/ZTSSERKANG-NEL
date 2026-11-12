import { expect, test } from "@playwright/test";
import { DASHBOARD_BEKLEME_MS } from "./sabitler";

// Yazma istekleri ve ilk açılış diyaloğu kullanıcı adı ister: testlerde ad önceden kayıtlıdır.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
});

// Not: e2e/kurulum.py her koşuda veri/e2e.db'yi silip gerçek kitabı yeniden yükler; burada açılan boş çalışma ve yeni ürün
// sonraki koşuları etkilemez. Şirket verisi sabit yazılmaz: malzeme kodu gerçek kitaptan API ile alınır.
test("yeni çalışma: boş çalışma aç → Veri Girişi'nden yeni ürün → ürün ekranında reçete satırı → dashboard'da ürün görünür", async ({
  page,
  request,
}) => {
  // Fiyatı olan (kartı var, fiyatsız değil) bir malzeme kodu.
  // Sabit port yok: baseURL (Vite) üzerinden vekil; e2e backend portu E2E_API_PORT ile değişebilir.
  const yanit = await request.get("/api/v1/malzemeler?senaryo=1&boyut=100");
  expect(yanit.ok()).toBeTruthy();
  const { kayitlar } = (await yanit.json()) as { kayitlar: { kod: string; fiyatsiz?: boolean; kart_yok?: boolean }[] };
  const malzeme = kayitlar.find((m) => !m.fiyatsiz && !m.kart_yok);
  expect(malzeme, "fiyatı olan bir malzeme bulunmalı").toBeTruthy();

  await page.goto("/genel-bakis");
  await expect(page).toHaveURL(/senaryo=\d+/);
  const eskiUrl = page.url();

  // Üst bar: Yeni çalışma → Boş.
  await page.getByRole("button", { name: "Yeni çalışma" }).click();
  const diyalog = page.getByRole("dialog", { name: "Yeni çalışma" });
  await expect(diyalog.getByRole("tab", { name: "Boş" })).toHaveAttribute("aria-selected", "true");
  // Sezon adı backend'de YYYY-YYYY biçiminde olmalı; kurulum DB'yi her koşuda sıfırladığından sabit değer çakışmaz.
  const sezon = "2031-2032";
  await diyalog.getByLabel("Sezon adı").fill(sezon);
  await diyalog.getByLabel("Çalışma adı").fill("E2E Boş çalışma");
  await diyalog.getByRole("button", { name: "Boş çalışma aç" }).click();
  await expect(diyalog).toBeHidden();

  // Yeni çalışma seçildi (URL ve seçici); dashboard boş durumu.
  await expect(page).not.toHaveURL(eskiUrl);
  await expect(page.locator("#senaryo-secici option:checked")).toHaveText(new RegExp(`${sezon} · E2E Boş çalışma`));
  await expect(page.getByRole("heading", { name: "Bu çalışmada henüz ürün yok" })).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await expect(page.getByRole("button", { name: "Geçen sezondan kopyala" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Excel yükle" })).toBeVisible();

  // Yeni ürün kartı.
  await page.getByRole("link", { name: "Yeni ürün" }).click();
  await expect(page).toHaveURL(/\/veri-girisi\?senaryo=\d+/);
  const kod = `E2E-URUN-${Date.now()}`;
  const kart = page.getByRole("region", { name: "Yeni ürün" });
  await kart.getByLabel("Ürün kodu").fill(kod);
  await kart.getByLabel("Ürün adı").fill("E2E Deneme Ürünü 720 ml");
  await kart.getByLabel("Ambalaj hacmi (ml)").fill("720");
  await kart.getByLabel("Süzme miktar (kg)").fill("0,45");
  await kart.getByLabel("Hat", { exact: true }).fill("E2E Hattı");
  await kart.getByRole("button", { name: "Ürünü kaydet" }).click();
  const receteyiKur = kart.getByRole("link", { name: "Reçeteyi kur" });
  await expect(receteyiKur).toBeVisible();
  await receteyiKur.click();
  await expect(page).toHaveURL(new RegExp(`/urunler/${encodeURIComponent(kod).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\?senaryo=\\d+`));

  // Reçetesiz ürün ekranı: şerit + not + elle satır girişi (hesap koşmaz).
  await expect(page.getByTestId("senaryo-disi-seridi")).toBeVisible();
  await expect(page.getByText("Reçete girilince hesaplanır")).toBeVisible();
  await expect(page.getByRole("table", { name: "Reçete tablosu" })).toHaveCount(0);
  await page.getByLabel("Malzeme kodu 1", { exact: true }).fill(malzeme!.kod);
  // exact: "Miktar 1" aksi hâlde "Elle brüt miktar 1" ile de eşleşir.
  await page.getByLabel("Miktar 1", { exact: true }).fill("1");
  await page.getByRole("button", { name: "Reçeteyi kaydet" }).click();
  const onay = page.getByRole("dialog", { name: "İlk reçete kaydedilecek" });
  await expect(onay).toContainText(/ilk reçete versiyonu 1 satırla açılır/);
  await onay.getByRole("button", { name: "Onayla ve kaydet" }).click();

  // Reçete gelince ekran normal akışa döner: tablo görünür, şerit kalkar.
  await expect(page.getByRole("table", { name: "Reçete tablosu" })).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await expect(page.getByTestId("senaryo-disi-seridi")).toBeHidden();

  // Dashboard'da ürün satırı görünür (hesap hatalı olsa da üyelik reçeteyle gelir).
  await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Genel Bakış" }).click();
  await expect(page.locator("tr[data-satir]").filter({ hasText: kod })).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
});
