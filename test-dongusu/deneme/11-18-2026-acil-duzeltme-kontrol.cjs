// Acil düzeltmelerin (D3b, D5-D9) ekran kontrolü. Test sunucusu 8048'de, uydurma test veritabanıyla açık olmalı.
// Kullanım (proje kökünden): node test-dongusu/deneme/11-18-2026-acil-duzeltme-kontrol.cjs
const { chromium } = require("../../frontend/node_modules/@playwright/test");
const ADRES = "http://127.0.0.1:8048";
const SIFRE = "Deneme2026!";
const sonuc = [];
const yaz = (ad, ok, not = "") => sonuc.push(`${ok ? "GEÇTİ" : "KALDI"} · ${ad}${not ? " · " + not : ""}`);

async function giris(b, kad) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage();
  await p.goto(ADRES + "/");
  await p.getByLabel("Kullanıcı adı").fill(kad);
  await p.getByLabel("Şifre").fill(SIFRE);
  await p.getByRole("button", { name: "Giriş yap" }).click();
  await p.waitForTimeout(1500);
  return p;
}
const metin = (p) => p.locator("main").innerText();

(async () => {
  const b = await chromium.launch();
  const gd = await giris(b, "direktor");

  // D5 · Günlük okunur mu
  await gd.goto(ADRES + "/gunluk?senaryo=3");
  await gd.waitForTimeout(2500);
  const satirlar = await gd.locator("main tbody tr").allInnerTexts();
  const ham = satirlar.filter((r) => /_id\b|None|\{'|\[\[|\d\.\d{5,}|\b[a-z]+_[a-z_]+:/.test(r));
  yaz("D5 günlükte ham veri yok", ham.length === 0, ham.length ? ham.slice(0, 3).map((x) => x.replace(/\s+/g, " ").slice(0, 160)).join(" || ") : `${satirlar.length} satır temiz`);
  sonuc.push("   örnek: " + satirlar.slice(0, 4).map((x) => x.replace(/\s+/g, " ").slice(0, 150)).join("\n   örnek: "));
  await gd.screenshot({ path: __dirname + "/kontrol-gunluk.png" });

  // D6 · Hata mesajında teknik ek yok (aynı kullanıcı adını ekle)
  await gd.goto(ADRES + "/kullanicilar");
  await gd.waitForTimeout(1500);
  await gd.getByLabel("Ad soyad").fill("Tekrar");
  await gd.getByLabel("Kullanıcı adı").fill("muhasebe1");
  await gd.getByRole("button", { name: "Kullanıcıyı ekle" }).click();
  await gd.waitForTimeout(1200);
  const hata = (await metin(gd)).split("\n").find((s) => /zaten var/.test(s)) || "";
  yaz("D6 hata mesajı teknik eksiz", hata && !/—\s*\w+_\w+:|kullanici_adi/.test(hata), hata);

  // D8 · Pasifleştir onay soruyor
  const satir = gd.locator("main tbody tr", { hasText: "izleyici1" });
  await satir.getByRole("button", { name: "Pasifleştir" }).click();
  await gd.waitForTimeout(800);
  const d8 = await gd.locator("[role=dialog],[role=alertdialog]").last().innerText().catch(() => "");
  yaz("D8 pasifleştirme onayı", /pasifleştirilsin mi/i.test(d8), d8.split("\n")[0]);
  await gd.getByRole("button", { name: "Vazgeç" }).last().click().catch(() => {});
  await gd.waitForTimeout(500);
  const durum = await gd.locator("main tbody tr", { hasText: "izleyici1" }).innerText();
  yaz("D8 Vazgeç sonrası hâlâ aktif", /Aktif/.test(durum));

  // D7 · Satış geçmişi formunda Neden
  await gd.goto(ADRES + "/satis-gecmisi?senaryo=3");
  await gd.waitForTimeout(2000);
  const sm = await metin(gd);
  yaz("D7 satış satırı formunda Neden", /Neden \(zorunlu\)/.test(sm));

  // D3b · Satır ekle'de olmayan malzeme
  await gd.goto(ADRES + "/urunler/03.99.008?senaryo=3");
  await gd.waitForTimeout(3000);
  const ac = gd.getByRole("button", { name: "Düzenlemeyi aç" });
  if (await ac.count()) {
    await ac.click();
    await gd.getByRole("button", { name: "Evet, aç" }).click();
    await gd.waitForTimeout(800);
  }
  await gd.getByRole("button", { name: "Satır ekle" }).click();
  await gd.waitForTimeout(500);
  await gd.getByLabel("Malzeme kodu ya da adı").fill("Etiket 370");
  await gd.getByLabel("Miktar", { exact: true }).fill("1");
  await gd.getByRole("button", { name: "Satırı ekle" }).click();
  await gd.waitForTimeout(2000);
  const d3 = await metin(gd);
  const yeniVar = (await gd.locator("main table tbody tr", { hasText: "Yeni" }).count()) > 0;
  yaz("D3b olmayan malzeme reddedildi", /Bu kodda malzeme yok/.test(d3) && !yeniVar, (d3.match(/Bu kodda malzeme yok[^\n]*/) || [""])[0]);
  await gd.screenshot({ path: __dirname + "/kontrol-satir-ekle.png" });

  // D9 · İzleyici
  const iz = await giris(b, "izleyici1");
  await iz.goto(ADRES + "/parametreler?senaryo=2");
  await iz.waitForTimeout(2000);
  const ust = await iz.locator("header").innerText();
  const im = await metin(iz);
  yaz("D9 izleyici: Yeni çalışma gizli", !/Yeni çalışma/.test(ust));
  yaz("D9 izleyici: Parametreler salt okunur", /Salt okunur/.test(im) && !/Düzenlemeyi aç/.test(im), (im.match(/Salt okunur[^\n]*/) || [""])[0]);
  await iz.screenshot({ path: __dirname + "/kontrol-izleyici.png" });

  // D9 · Satın alma
  const sa = await giris(b, "satinalma1");
  await sa.goto(ADRES + "/parametreler?senaryo=2");
  await sa.waitForTimeout(2000);
  const sp = await metin(sa);
  yaz("D9 satın alma: Parametreler salt okunur", /Salt okunur/.test(sp), (sp.match(/Salt okunur[^\n]*/) || [""])[0]);
  await sa.goto(ADRES + "/fiyatlar?senaryo=2");
  await sa.waitForTimeout(2000);
  const sf = await metin(sa);
  yaz("D9 satın alma: Malzeme Fiyatları düzenlenebilir", /Düzenlemeyi aç|Düzenleme açık/.test(sf) && !/Salt okunur/.test(sf));
  const sh = await sa.locator("header").innerText();
  yaz("D9 satın alma: Yeni çalışma gizli", !/Yeni çalışma/.test(sh));

  console.log(sonuc.join("\n"));
  await b.close();
})().catch((e) => {
  console.log(sonuc.join("\n"));
  console.log("HATA:", e.message.split("\n")[0]);
  process.exit(1);
});
