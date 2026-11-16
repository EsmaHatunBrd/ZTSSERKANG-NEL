// Test döngüsü belgelerini (docs/test-dongusu/11-16-2026-*.md) PDF'e çevirir: docs/test-dongusu/<ad>.pdf
// docs/aktarim/pdf-uret.mjs'nin kopyası (aynı görünüm); yalnız klasör, dosya süzgeci, başlık metni ve çıktı yeri farklı.
//
// Çalıştırma (proje kökünden):
//   npm install --prefix <geçici-klasör> marked        (projeye bağımlılık eklenmez)
//   MARKED_DIR=<geçici-klasör> node docs/test-dongusu/pdf-uret.mjs [ad-süzgeci]
// Playwright (chromium) frontend/node_modules içinden kullanılır.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const BURASI = path.dirname(fileURLToPath(import.meta.url));
const KOK = path.resolve(BURASI, "../..");
const { chromium } = createRequire(path.join(KOK, "frontend/package.json"))("@playwright/test");
const markedKok = process.env.MARKED_DIR;
if (!markedKok) throw new Error("MARKED_DIR ortam değişkeni gerekli (içinde node_modules/marked olan klasör)");
const { marked } = createRequire(path.join(path.resolve(markedKok), "package.json"))("marked");

const TARIH = "16.11.2026";
const YATAY = new Set([]);
const KART = /-kart-/;
const logo = "data:image/png;base64," + fs.readFileSync(path.join(KOK, "frontend/public/zeytursan-logo.png")).toString("base64");
const kacis = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const STIL = `
  @page { size: A4 SAYFA_YONU; }
  * { box-sizing: border-box; }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt; line-height: 1.42; color: #1f2417; margin: 0; }
  body.yatay { font-size: 10pt; }
  h1 { font-size: 19pt; line-height: 1.2; color: #36421a; margin: 0 0 4mm; padding-bottom: 2.5mm; border-bottom: 1.4pt solid #5b6e2b; font-weight: 650; }
  h2 { font-size: 13.5pt; color: #36421a; margin: 7mm 0 2.5mm; padding-bottom: 1mm; border-bottom: 0.5pt solid #c3c9ae; break-after: avoid; }
  h3 { font-size: 11.5pt; color: #45541f; margin: 5.5mm 0 2mm; break-after: avoid; }
  h4 { font-size: 10.5pt; color: #45541f; margin: 5mm 0 2mm; text-transform: uppercase; letter-spacing: 0.04em; break-after: avoid; }
  p { margin: 0 0 2.2mm; orphans: 3; widows: 3; }
  strong { color: #232a12; }
  ul, ol { margin: 0 0 2.5mm; padding-left: 5.5mm; }
  li { margin: 0 0 1mm; break-inside: avoid; }
  li > ul { margin-top: 1mm; }
  code { font-family: Consolas, "Courier New", monospace; font-size: 0.92em; background: #f0f1e8; border-radius: 2px; padding: 0 1.2mm; }
  mark.doldur { background: #ffe873; color: #3b3200; border: 0.5pt solid #d9b900; border-radius: 2px; padding: 0 1.2mm; font-weight: 600; font-size: 0.95em; }
  table { width: 100%; border-collapse: collapse; margin: 1mm 0 4mm; font-size: 9.3pt; line-height: 1.35; }
  thead { display: table-header-group; }
  th { background: #e9ecdb; color: #36421a; text-align: left; font-weight: 650; }
  th, td { border: 0.5pt solid #bfc5ab; padding: 1.4mm 1.8mm; vertical-align: top; }
  tr { break-inside: avoid; page-break-inside: avoid; }
  tbody tr:nth-child(even) td { background: #fafaf5; }
  body.yatay table.bes th:nth-child(1), body.yatay table.bes td:nth-child(1) { width: 6%; white-space: nowrap; }
  body.yatay table.bes th:nth-child(2) { width: 13%; }
  body.yatay table.bes th:nth-child(3) { width: 29%; }
  body.yatay table.bes th:nth-child(4) { width: 31%; }
  body.yatay table.bes th:nth-child(5) { width: 21%; }
  figure { margin: 2mm 0 3mm; break-inside: avoid; page-break-inside: avoid; text-align: center; }
  figure img { display: block; margin: 0 auto; max-width: 100%; max-height: 150mm; border: 0.6pt solid #9aa283; border-radius: 1.2mm; }
  figcaption { font-size: 8.6pt; color: #5c6348; margin-top: 1.2mm; font-style: italic; }
  body.yatay figure img { max-width: 64%; max-height: 112mm; }
  body.kart figure img { max-width: 62%; }
  body.kart { font-size: 10pt; }
  body.kart h2 { margin-top: 5mm; }
  .ekran { break-inside: avoid; page-break-inside: avoid; margin-bottom: 4mm; }
  .ekran > p.adim { font-size: 11pt; color: #36421a; margin: 3mm 0 1.5mm; }
  .ekran > p.ne { font-weight: 650; color: #45541f; margin-bottom: 1mm; }
  li.gorev { list-style: none; position: relative; }
  li.gorev .kutu { position: absolute; left: -5.2mm; top: 0.75mm; width: 3.1mm; height: 3.1mm; border: 0.8pt solid #45541f; border-radius: 0.4mm; background: #fff; }
  .ust { font-size: 8.5pt; color: #6a7055; margin: 0 0 3mm; }
`;

function htmlUret(md, ad) {
  let html = marked.parse(md, { gfm: true });
  // Görev kutuları: boş kare
  html = html.replace(/<li>(\s*(?:<p>)?)<input[^>]*type="checkbox"[^>]*>\s*/g, '<li class="gorev">$1<span class="kutu"></span>');
  // Doldurulacak yerler: sarı vurgu
  html = html.replace(/<code>(\[Esma [^<]*\])<\/code>/g, '<mark class="doldur">$1</mark>');
  // Görüntüler: kenarlıklı şekil + alt yazı
  html = html.replace(/<p>((?:\s*<img [^>]*>\s*)+)<\/p>/g, (_, ic) =>
    ic.replace(/<img src="([^"]*)" alt="([^"]*)"[^>]*>/g, (_m, src, alt) => `<figure><img src="${src}" alt="${alt}"><figcaption>${alt}</figcaption></figure>`),
  );
  // Adım başlığı + görüntü + "Bu ekranda ne var" + liste: sayfa ortasında bölünmesin
  html = html.replace(
    /(<p><strong>[^<]*<\/strong>(?:[^<]*)<\/p>\s*)?(<figure>[\s\S]*?<\/figure>)\s*<p>(Bu ekranda ne var:)<\/p>\s*(<ul>[\s\S]*?<\/ul>)/g,
    (_, baslik, sekil, ne, liste) => `<div class="ekran">${baslik ? baslik.replace("<p>", '<p class="adim">') : ""}${sekil}<p class="ne">${ne}</p>${liste}</div>`,
  );
  // Beş sütunlu tablolar (akış tabloları) için sütun genişliği sınıfı
  html = html.replace(/<table>(\s*<thead>\s*<tr>(?:\s*<th[^>]*>[\s\S]*?<\/th>){5}\s*<\/tr>)/g, '<table class="bes">$1');
  const sinif = [YATAY.has(ad) ? "yatay" : "dikey", KART.test(ad) ? "kart" : ""].join(" ").trim();
  const baslik = (md.match(/^# (.+)$/m) ?? [, ad])[1];
  return {
    baslik,
    html: `<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>${kacis(baslik)}</title><base href="${pathToFileURL(BURASI + path.sep).href}">
<style>${STIL.replace("SAYFA_YONU", YATAY.has(ad) ? "landscape" : "portrait")}</style></head><body class="${sinif}">${html}</body></html>`,
  };
}

const suzgec = process.argv[2] ?? "";
const dosyalar = fs
  .readdirSync(BURASI)
  .filter((f) => /^11-16-2026-.*\.md$/.test(f) && f.includes(suzgec))
  .sort();
const tarayici = await chromium.launch();
for (const f of dosyalar) {
  const ad = f.replace(/\.md$/, "");
  const { html, baslik } = htmlUret(fs.readFileSync(path.join(BURASI, f), "utf8"), ad);
  const gecici = path.join(BURASI, `.${ad}.html`);
  fs.writeFileSync(gecici, html, "utf8");
  const sayfa = await tarayici.newPage();
  await sayfa.goto(pathToFileURL(gecici).href, { waitUntil: "load" });
  await sayfa.evaluate(() => Promise.all([...document.images].map((i) => (i.complete ? null : new Promise((c) => ((i.onload = c), (i.onerror = c)))))));
  const kirik = await sayfa.evaluate(() => [...document.images].filter((i) => i.naturalWidth === 0).map((i) => i.getAttribute("src")));
  if (kirik.length) console.log("  KIRIK GÖRÜNTÜ:", kirik.join(", "));
  // Denetim için: SAYFALAR="1-6" ve CIKTI=<klasör> ile yalnız bir sayfa aralığı başka klasöre yazılabilir.
  const hedef = path.join(process.env.CIKTI ?? BURASI, ad + ".pdf");
  await sayfa.pdf({
    path: hedef,
    format: "A4",
    landscape: YATAY.has(ad),
    printBackground: true,
    pageRanges: process.env.SAYFALAR ?? "",
    displayHeaderFooter: true,
    margin: { top: "24mm", bottom: "17mm", left: "15mm", right: "15mm" },
    headerTemplate: `<div style="width:100%;margin:0 15mm;padding-bottom:2mm;border-bottom:0.5pt solid #9aa283;display:flex;align-items:flex-end;justify-content:space-between;font-family:'Segoe UI',Arial,sans-serif;font-size:8pt;color:#5c6348;-webkit-print-color-adjust:exact;">
      <img src="${logo}" style="height:8.5mm;">
      <span>Fiyat Çalışması · Test döngüsü · ${TARIH}</span></div>`,
    footerTemplate: `<div style="width:100%;margin:0 15mm;padding-top:1.5mm;border-top:0.5pt solid #c3c9ae;display:flex;justify-content:space-between;font-family:'Segoe UI',Arial,sans-serif;font-size:8pt;color:#5c6348;">
      <span>${kacis(baslik)}</span><span>Sayfa <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
  });
  await sayfa.close();
  fs.rmSync(gecici);
  const n = (fs.readFileSync(hedef, "latin1").match(/\/Type\s*\/Page[^s]/g) ?? []).length;
  console.log(`${ad}.pdf  ${n} sayfa`);
}
await tarayici.close();
