// Şablon rehberini (sablonlar/11-16-2026-sablonlar-rehberi.md) PDF'e çevirir: sablonlar/11-16-2026-sablonlar-rehberi.pdf
// Kalıp: docs/aktarim/pdf-uret.mjs (aynı stil, üst / alt bilgi).
//
// Çalıştırma (proje kökünden):
//   npm install --prefix <geçici-klasör> marked        (projeye bağımlılık eklenmez)
//   MARKED_DIR=<geçici-klasör> node sablonlar/11-16-2026-pdf-uret.mjs
// Playwright (chromium) frontend/node_modules içinden kullanılır.
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const BURASI = path.dirname(fileURLToPath(import.meta.url));
const KOK = path.resolve(BURASI, "..");
const { chromium } = createRequire(path.join(KOK, "frontend/package.json"))("@playwright/test");
const markedKok = process.env.MARKED_DIR;
if (!markedKok) throw new Error("MARKED_DIR ortam değişkeni gerekli (içinde node_modules/marked olan klasör)");
const { marked } = createRequire(path.join(path.resolve(markedKok), "package.json"))("marked");

const AD = "11-16-2026-sablonlar-rehberi";
const TARIH = "16.11.2026";
const logo = "data:image/png;base64," + fs.readFileSync(path.join(KOK, "frontend/public/zeytursan-logo.png")).toString("base64");
const kacis = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const STIL = `
  @page { size: A4 portrait; }
  * { box-sizing: border-box; }
  html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif; font-size: 10pt; line-height: 1.42; color: #1f2417; margin: 0; }
  h1 { font-size: 19pt; line-height: 1.2; color: #36421a; margin: 0 0 4mm; padding-bottom: 2.5mm; border-bottom: 1.4pt solid #5b6e2b; font-weight: 650; }
  h2 { font-size: 13.5pt; color: #36421a; margin: 7mm 0 2.5mm; padding-bottom: 1mm; border-bottom: 0.5pt solid #c3c9ae; break-after: avoid; }
  h3 { font-size: 11.5pt; color: #45541f; margin: 5.5mm 0 2mm; break-after: avoid; }
  p { margin: 0 0 2.2mm; orphans: 3; widows: 3; }
  strong { color: #232a12; }
  ul, ol { margin: 0 0 2.5mm; padding-left: 5.5mm; }
  li { margin: 0 0 1mm; break-inside: avoid; }
  li > ul { margin-top: 1mm; }
  code { font-family: Consolas, "Courier New", monospace; font-size: 0.9em; background: #f0f1e8; border-radius: 2px; padding: 0 1.2mm; }
  table { width: 100%; border-collapse: collapse; margin: 1mm 0 4mm; font-size: 8.4pt; line-height: 1.32; }
  thead { display: table-header-group; }
  th { background: #e9ecdb; color: #36421a; text-align: left; font-weight: 650; }
  th, td { border: 0.5pt solid #bfc5ab; padding: 1.2mm 1.5mm; vertical-align: top; }
  tr { break-inside: avoid; page-break-inside: avoid; }
  tbody tr:nth-child(even) td { background: #fafaf5; }
  td code { white-space: nowrap; font-size: 0.85em; }
  li.gorev { list-style: none; position: relative; }
  li.gorev .kutu { position: absolute; left: -5.2mm; top: 0.75mm; width: 3.1mm; height: 3.1mm; border: 0.8pt solid #45541f; border-radius: 0.4mm; background: #fff; }
  h3 + ul { break-before: avoid; }
`;

const md = fs.readFileSync(path.join(BURASI, `${AD}.md`), "utf8");
let html = marked.parse(md, { gfm: true });
html = html.replace(/<li>(\s*(?:<p>)?)<input[^>]*type="checkbox"[^>]*>\s*/g, '<li class="gorev">$1<span class="kutu"></span>');
const baslik = (md.match(/^# (.+)$/m) ?? [, AD])[1];
const tam = `<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>${kacis(baslik)}</title><style>${STIL}</style></head><body>${html}</body></html>`;

const gecici = path.join(BURASI, `.${AD}.html`);
fs.writeFileSync(gecici, tam, "utf8");
const tarayici = await chromium.launch();
try {
  const sayfa = await tarayici.newPage();
  await sayfa.goto(pathToFileURL(gecici).href, { waitUntil: "load" });
  const hedef = path.join(BURASI, `${AD}.pdf`);
  await sayfa.pdf({
    path: hedef,
    format: "A4",
    printBackground: true,
    displayHeaderFooter: true,
    margin: { top: "24mm", bottom: "17mm", left: "14mm", right: "14mm" },
    headerTemplate: `<div style="width:100%;margin:0 14mm;padding-bottom:2mm;border-bottom:0.5pt solid #9aa283;display:flex;align-items:flex-end;justify-content:space-between;font-family:'Segoe UI',Arial,sans-serif;font-size:8pt;color:#5c6348;-webkit-print-color-adjust:exact;">
      <img src="${logo}" style="height:8.5mm;">
      <span>Fiyat Çalışması · Maliyet Muhasebesi · Excel şablonları · ${TARIH}</span></div>`,
    footerTemplate: `<div style="width:100%;margin:0 14mm;padding-top:1.5mm;border-top:0.5pt solid #c3c9ae;display:flex;justify-content:space-between;font-family:'Segoe UI',Arial,sans-serif;font-size:8pt;color:#5c6348;">
      <span>${kacis(baslik)}</span><span>Sayfa <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
  });
  const n = (fs.readFileSync(hedef, "latin1").match(/\/Type\s*\/Page[^s]/g) ?? []).length;
  console.log(`${AD}.pdf  ${n} sayfa`);
} finally {
  await tarayici.close();
  fs.rmSync(gecici, { force: true });
}
