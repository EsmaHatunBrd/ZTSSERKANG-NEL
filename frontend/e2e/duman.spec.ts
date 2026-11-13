import { expect, test } from "@playwright/test";
import { DASHBOARD_BEKLEME_MS } from "./sabitler";

// Yazma istekleri ve ilk açılış diyaloğu kullanıcı adı ister: testlerde ad önceden kayıtlıdır.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
  // Düzenleme kilidi uygulamada kilitli başlar; yazma yapan senaryolar için sekmede açık başlatılır.
  await page.addInitScript(() => sessionStorage.setItem("fiyat-calismasi.duzenleme-acik-bitis", String(Date.now() + 3_600_000)));
});

// Gerçek backend + gerçek Excel verisi: ürün/malzeme adları sabit yazılmaz; sayım, yapı ve değişim doğrulanır.
test("duman: dashboard -> ürün -> birim fiyat değişimi -> Kaydet -> yenile -> teklif turu -> teklifler sayfası", async ({ page }) => {
  await page.goto("/genel-bakis");

  // Senaryo otomatik seçilir (URL ?senaryo= ile eşitlenir).
  await expect(page.getByLabel("Senaryo", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/senaryo=\d+/);

  // Dashboard: ürün sayısı kartı 67.
  const kart = page.getByText("Ürün sayısı", { exact: true }).locator("xpath=..");
  await expect(kart).toContainText("67", { timeout: DASHBOARD_BEKLEME_MS });

  // İlk satıra tıkla -> ürün ekranı.
  const ilkSatir = page.locator("tr[data-satir]").first();
  await expect(ilkSatir).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await ilkSatir.click();
  await expect(page).toHaveURL(/\/urunler\/[^/?]+\?senaryo=\d+/);

  // Reçete tablosu: iki tutar sütunu ve iki toplam.
  const tablo = page.getByRole("table", { name: "Reçete tablosu" });
  await expect(tablo.getByRole("columnheader", { name: "Tutar (firesiz)" })).toBeVisible();
  await expect(tablo.getByRole("columnheader", { name: "Tutar (fireli)" })).toBeVisible();
  const firesizSatir = tablo.getByRole("row", { name: /Malzeme toplamı \(firesiz\)/ });
  const fireliSatir = tablo.getByRole("row", { name: /Malzeme toplamı \(fireli\)/ });
  await expect(firesizSatir).toBeVisible();
  await expect(fireliSatir).toBeVisible();
  const oncekiFireli = (await fireliSatir.innerText()).trim();

  // Birim fiyatı değiştirilebilir (düzenlenir) ve firesiz tutarı sıfırdan büyük ilk satırı bul:
  // fiyatsız satırda fiyat değişse de TL toplamı oynamaz; ürün/ara mamul satırlarında girdi yoktur.
  const basliklar = (await tablo.getByRole("columnheader").allInnerTexts()).map((b) => b.trim());
  const firesizIndeks = basliklar.indexOf("Tutar (firesiz)");
  expect(firesizIndeks, "Tutar (firesiz) sütunu başlıkta bulunmalı").toBeGreaterThanOrEqual(0);
  const satirlar = tablo.locator("tbody tr");
  const adet = await satirlar.count();
  let hedef = -1;
  for (let i = 0; i < adet; i++) {
    const hucreler = await satirlar.nth(i).locator("td").allInnerTexts();
    const firesiz = hucreler[firesizIndeks] ?? "";
    const girdi = satirlar.nth(i).getByRole("textbox", { name: /^Birim fiyat/ });
    if (/[1-9]/.test(firesiz.replace(/\D*TL.*/, "")) && (await girdi.count()) === 1 && (await girdi.isEnabled())) {
      hedef = i;
      break;
    }
  }
  expect(hedef, "fiyatlı, birim fiyatı değiştirilebilir bir reçete satırı bulunmalı").toBeGreaterThanOrEqual(0);
  const fiyatGirdisi = () => satirlar.nth(hedef).getByRole("textbox", { name: /^Birim fiyat/ });
  const eskiFiyat = Number((await fiyatGirdisi().inputValue()).replace(",", "."));
  const yeniFiyat = String(Math.floor(eskiFiyat) * 2 + 7);
  await fiyatGirdisi().fill(yeniFiyat);

  // Şerit tek değişikliği sayar; fireli toplam değişir.
  await expect(page.getByText("1 satırda değişiklik")).toBeVisible();
  await expect.poll(async () => (await fireliSatir.innerText()).trim(), { timeout: 20_000 }).not.toBe(oncekiFireli);

  // Kaydet -> özet diyaloğu -> neden -> gönder -> "Kaydedildi · Hesap #N".
  await page.getByRole("button", { name: "Kaydet" }).click();
  const diyalog = page.getByRole("dialog");
  await expect(diyalog.getByRole("table", { name: "Değişiklik listesi" })).toContainText(/elle birim fiyat/);
  await diyalog.getByLabel("Neden").fill("E2E birim fiyat güncellemesi");
  await diyalog.getByRole("button", { name: "Onayla ve kaydet" }).click();
  await expect(page.getByRole("status", { name: "Kayıt durumu" })).toContainText(/Kaydedildi · Hesap #\d+/);
  await expect(page.getByRole("region", { name: "Kaydedilmemiş değişiklikler" })).toBeHidden();

  // Sayfayı yenile: değer kalıcıdır (reçete yeni sürüm olarak yazıldı).
  await page.reload();
  await expect(tablo).toBeVisible();
  await expect(fiyatGirdisi()).toHaveValue(yeniFiyat, { timeout: 20_000 });

  // Teklif turu ekle (kâr %20).
  const panel = page.getByRole("region", { name: "Teklif turları" });
  await panel.getByRole("textbox", { name: "Kâr %" }).fill("20");
  await panel.getByRole("button", { name: "Yeni tur" }).click();
  const turTablosu = panel.getByRole("table", { name: "Teklif turları tablosu" });
  await expect(turTablosu.getByRole("cell", { name: /^Tur \d+$/ }).first()).toBeVisible();

  // Teklifler sayfası: tur görünür.
  await page.getByRole("navigation", { name: "Ana menü" }).getByRole("link", { name: "Teklifler" }).click();
  await expect(page).toHaveURL(/\/teklifler/);
  await expect(page.getByRole("heading", { name: "Teklifler" })).toBeVisible();
  // Taze veritabanında tek teklif turu vardır: "Tur 1" hücresi ve kâr % 20 görünür.
  const turSatiri = page.locator("tr[data-satir]").filter({ hasText: /Tur 1/ });
  await expect(turSatiri.first()).toBeVisible();
  await expect(turSatiri.first()).toContainText(/20/);
});

test("reçete girintisi: seviye > 0 satırlarda data-seviye ve soldan boşluk (8 + seviye x 14 px)", async ({ page }) => {
  await page.goto("/genel-bakis");
  await expect(page).toHaveURL(/senaryo=\d+/);
  const ilkSatir = page.locator("tr[data-satir]").first();
  await expect(ilkSatir).toBeVisible({ timeout: DASHBOARD_BEKLEME_MS });
  await ilkSatir.click();
  const tablo = page.getByRole("table", { name: "Reçete tablosu" });
  await expect(tablo.getByRole("row", { name: /Malzeme toplamı \(fireli\)/ })).toBeVisible();

  const seviyeli = tablo.locator("tbody tr[data-seviye]");
  const adet = await seviyeli.count();
  expect(adet, "ilk üründe seviye bilgisi olan satırlar bulunmalı").toBeGreaterThan(0);
  let derin = 0;
  for (let i = 0; i < adet; i++) {
    const satir = seviyeli.nth(i);
    const seviye = Number(await satir.getAttribute("data-seviye"));
    const cinsi = satir.locator("td").nth(2);
    const sol = await cinsi.evaluate((e) => parseFloat(getComputedStyle(e).paddingLeft));
    expect(sol, `seviye ${seviye} satırının sol boşluğu`).toBeCloseTo(8 + seviye * 14, 0);
    if (seviye > 0) {
      derin++;
      await expect(cinsi).toContainText("└");
    }
  }
  expect(derin, "seviye > 0 olan en az bir satır bulunmalı").toBeGreaterThan(0);
});
