import { expect, test, type Page } from "@playwright/test";

// Yazma istekleri ve ilk açılış diyaloğu kullanıcı adı ister: testlerde ad önceden kayıtlıdır.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("fiyat-calismasi.kullanici", "E2E Kullanıcı"));
});

const YOLLAR = [
  "/",
  "/urunler",
  "/fiyatlar",
  "/parametreler",
  "/gider",
  "/recete-aktar",
  "/teklifler",
  "/uyarilar",
  "/veri-kontrolu",
  "/butce-gerceklesen",
  "/yardim",
];
const BOYUTLAR = [
  { ad: "1280x800", width: 1280, height: 800 },
  { ad: "768x1024", width: 768, height: 1024 },
];

// /urunler artık ürün seçicidir (sabit "ornek" ürünü yok): 404 beklenmez.
function hataDinle(page: Page): string[] {
  const hatalar: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") hatalar.push(`${m.text()} @ ${m.location().url}`);
  });
  page.on("pageerror", (e) => hatalar.push(`pageerror: ${e.message}`));
  return hatalar;
}

for (const b of BOYUTLAR) {
  for (const yol of YOLLAR) {
    test(`${yol} konsol hatası vermeden açılır (${b.ad})`, async ({ page }) => {
      await page.setViewportSize({ width: b.width, height: b.height });
      const hatalar = hataDinle(page);
      await page.goto(yol);
      await expect(page.getByRole("navigation", { name: "Ana menü" })).toBeVisible();
      await expect(page.locator("#senaryo-secici")).toBeVisible();
      await page.waitForLoadState("networkidle");
      // Yatay taşma: sayfa gövdesi görünüm alanından geniş olmamalı (tablolar kendi içinde kayabilir).
      const tasma = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (b.width === 768 && tasma > 1) {
        const tasanlar = await page.evaluate(() =>
          [...document.querySelectorAll<HTMLElement>("body *")]
            .filter((e) => e.getBoundingClientRect().right > window.innerWidth + 1)
            .slice(0, 8)
            .map(
              (e) =>
                `${e.tagName.toLowerCase()}${e.id ? "#" + e.id : ""}${e.className && typeof e.className === "string" ? "." + e.className.trim().split(/\s+/).slice(0, 3).join(".") : ""} sag=${Math.round(e.getBoundingClientRect().right)}`,
            ),
        );
        expect(tasma, `${yol} yatay taşma ${tasma}px; taşan öğeler: ${tasanlar.join(" | ")}`).toBeLessThanOrEqual(1);
      }
      expect(hatalar).toEqual([]);
    });
  }
}

test("koyu tema anahtarı body arka planını koyulaştırır", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  const parlaklik = () =>
    page.evaluate(() => {
      const c = getComputedStyle(document.body).backgroundColor; // rgb()/oklch() olabilir
      const cv = document.createElement("canvas").getContext("2d")!;
      cv.fillStyle = c;
      cv.fillRect(0, 0, 1, 1);
      const [r, g, bl] = cv.getImageData(0, 0, 1, 1).data;
      return (r + g + bl) / 3;
    });
  const acik = await parlaklik();
  await page.getByRole("button", { name: "Koyu temaya geç" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
  const koyu = await parlaklik();
  expect(acik).toBeGreaterThan(200);
  expect(koyu).toBeLessThan(80);
});

test("klavye odağı görünür halka gösterir", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Ana menü" })).toBeVisible();
  for (const tema of ["light", "dark"] as const) {
    await page.evaluate((t) => document.documentElement.classList.toggle("dark", t === "dark"), tema);
    await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
    await page.keyboard.press("Tab");
    const stil = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement;
      const s = getComputedStyle(el);
      return {
        etiket: el.tagName,
        outlineStyle: s.outlineStyle,
        outlineWidth: parseFloat(s.outlineWidth),
        boxShadow: s.boxShadow,
      };
    });
    expect(stil.outlineStyle, `${tema}: ${JSON.stringify(stil)}`).not.toBe("none");
    expect(stil.outlineWidth, `${tema}: ${JSON.stringify(stil)}`).toBeGreaterThanOrEqual(2);
  }
});
