// SMM ekranlarını muhasebe1 ile tarar: hata, geliştirici dili, boş/NaN değer. Kullanım: node test-dongusu/deneme/11-18-2026-smm-ekran-tarama.cjs
const { chromium } = require("../../frontend/node_modules/@playwright/test");
const A = "http://127.0.0.1:8048";
const YOLLAR = ["/smm", "/smm/veri", "/smm/stok", "/smm/uretim", "/smm/sarf-farki", "/smm/ozet", "/smm/receteler", "/smm/sureler"];
const RX = /Faz ?\d|\buç\b|endpoint|TODO|Yakında|undefined|NaN|\bnull\b|\[object|Error:|_id\b|\bNone\b|dashboard/g;
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto(A + "/");
  await p.getByLabel("Kullanıcı adı").fill("muhasebe1");
  await p.getByLabel("Şifre").fill("Deneme2026!");
  await p.getByRole("button", { name: "Giriş yap" }).click();
  await p.waitForTimeout(1500);
  for (const y of YOLLAR) {
    await p.goto(A + y);
    await p.waitForLoadState("networkidle").catch(() => {});
    await p.waitForTimeout(2000);
    const t = await p.locator("main").innerText().catch(() => "");
    const m = [...new Set(t.match(RX) || [])];
    const hata = (t.match(/[^\n]*(bir hata oluştu|beklenmeyen|yüklenemedi|hesaplanamadı)[^\n]*/i) || [""])[0];
    console.log(`${y}: ${m.length ? "JARGON " + m.join(",") : "temiz"}${hata ? " | HATA: " + hata.slice(0, 120) : ""} | ${t.length} karakter`);
    await p.screenshot({ path: __dirname + "/smm" + y.replace(/\//g, "-") + ".png" });
  }
  await b.close();
})();
