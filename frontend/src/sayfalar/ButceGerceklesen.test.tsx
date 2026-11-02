import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kiyasListesi, kiyasSatirlari } from "@/test/fikstur/kiyas";
import { senaryolar } from "@/test/fikstur/urunler";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import ButceGerceklesen from "./ButceGerceklesen";
import KiyasUrun from "./KiyasUrun";
import { GerceklesenSeridi } from "./dashboard/GerceklesenSeridi";
import { kutular } from "./kiyas/SapmaGrafigi";
import { varsayilanCift } from "./kiyasCifti";

beforeAll(() => {
  // Recharts ResponsiveContainer jsdom'da ölçemez: sabit boyut bildiren gözlemci.
  globalThis.ResizeObserver = class {
    cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }
    observe(hedef: Element) {
      this.cb(
        [{ target: hedef, contentRect: { width: 600, height: 200 } } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  sunucu.listen({ onUnhandledFrame: "error" });
});
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

let yon: ReturnType<typeof createMemoryRouter>;
const istekler: URL[] = [];

function kur(yol = "/butce-gerceklesen?senaryo=1", karsi: number | null = 2) {
  istekler.length = 0;
  sunucu.use(
    http.get("*/api/v1/kiyas/karsi", () =>
      HttpResponse.json({ karsi: karsi === null ? null : { id: karsi, ad: "Gerçekleşen", tur: "gerceklesen", sezon: "2026-2027" } }),
    ),
    http.get("*/api/v1/kiyas", ({ request }) => {
      istekler.push(new URL(request.url));
      return HttpResponse.json(kiyasListesi);
    }),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const sar = (el: React.ReactNode) => <SenaryoSaglayici>{el}</SenaryoSaglayici>;
  yon = createMemoryRouter(
    [
      { path: "/butce-gerceklesen", element: sar(<ButceGerceklesen />) },
      { path: "/butce-gerceklesen/:kod", element: sar(<KiyasUrun />) },
      { path: "/", element: sar(<GerceklesenSeridi />) },
    ],
    { initialEntries: [yol] },
  );
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={yon} />
    </QueryClientProvider>,
  );
}

describe("varsayilanCift ve kutular", () => {
  it("seçili senaryonun türüne göre A/B; gerçekleşen seçiliyse karşısı bütçe olur", () => {
    expect(varsayilanCift(senaryolar[0], 2)).toEqual({ a: 1, b: 2 });
    expect(varsayilanCift(senaryolar[1], 1)).toEqual({ a: 1, b: 2 });
    expect(varsayilanCift(null, 2)).toEqual({ a: null, b: null });
  });

  it("sapma yüzdelerini 5 puanlık kutulara sayar; uçlar ±%20 dışı, sapmasızlar sayılmaz", () => {
    const k = kutular([...kiyasSatirlari, { ...kiyasSatirlari[0], sapma_yuzde: "35" }, { ...kiyasSatirlari[0], sapma_yuzde: "-0.1" }]);
    const adet = (e: string) => k.find((x) => x.etiket === e)?.adet;
    expect(adet("+10…+15")).toBe(1);
    expect(adet("-10…-5")).toBe(1);
    expect(adet("0…+5")).toBe(1);
    expect(adet("-5…0")).toBe(1);
    expect(adet("> +20")).toBe(1);
    expect(k.reduce((t, x) => t + x.adet, 0)).toBe(5);
  });
});

describe("Bütçe vs Gerçekleşen sayfası", () => {
  it("varsayılan çift karşı senaryodan gelir; özet kutuları, tablo ve yalnız bir taraftaki ürün", async () => {
    kur();
    expect(await screen.findByText("Biberiye Turşu")).toBeInTheDocument();
    expect(istekler[0].searchParams.get("a")).toBe("1");
    expect(istekler[0].searchParams.get("b")).toBe("2");
    expect(istekler[0].searchParams.get("esik")).toBe("5");
    expect(screen.getByLabelText("Bütçe senaryosu")).toHaveValue("1");
    expect(screen.getByLabelText("Gerçekleşen senaryosu")).toHaveValue("2");
    expect(screen.getByText("±%5 dışında").closest("button")).toHaveTextContent("2");
    expect(screen.getByText("Yalnız bütçede")).toBeInTheDocument();
    expect(screen.getByText("+10,0 %")).toBeInTheDocument();
    expect(screen.getByText("-10,0 %")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Excel/ })).toHaveAttribute("href", "/api/v1/disa-aktar/butce-gerceklesen.xlsx?a=1&b=2&esik=5");
  });

  it("yalnız sapanlar süzgeci ve eşik URL'de; eşik değişince yeni istek", async () => {
    const u = userEvent.setup();
    kur();
    await screen.findByText("Acı Sos");
    await u.click(screen.getByRole("checkbox", { name: "Yalnız sapanlar" }));
    expect(screen.queryByText("Acı Sos")).not.toBeInTheDocument();
    expect(screen.getByText("Biberiye Turşu")).toBeInTheDocument();
    expect(screen.getByText("Kornişon")).toBeInTheDocument();
    expect(yon.state.location.search).toContain("sapan=1");
    const esik = screen.getByLabelText("Sapma eşiği (yüzde)");
    await u.clear(esik);
    await u.type(esik, "10");
    await waitFor(() => expect(istekler.some((x) => x.searchParams.get("esik") === "10")).toBe(true));
    expect(yon.state.location.search).toContain("esik=10");
  });

  it("satıra tıklayınca ürün kıyas ekranı: sapma kaynağı, değişen reçete hücresi, parametreler", async () => {
    const u = userEvent.setup();
    kur();
    await u.click(await screen.findByText("Biberiye Turşu"));
    expect(yon.state.location.pathname).toBe("/butce-gerceklesen/03.001");
    const kaynak = await screen.findByRole("region", { name: "Sapmanın kaynağı" });
    expect(within(kaynak).getByText("Malzeme fiyatları")).toBeInTheDocument();
    expect(within(kaynak).getByText("Enflasyon")).toBeInTheDocument();
    expect(within(kaynak).getByText("Toplam fark")).toBeInTheDocument();
    const recete = screen.getByRole("region", { name: "Reçete" });
    expect(within(recete).getByText("bütçe 5,0000")).toBeInTheDocument();
    expect(within(recete).getByText("(yalnız gerçekleşende)")).toBeInTheDocument();
    const param = screen.getByRole("region", { name: "Parametreler" });
    expect(within(param).getByText("52,85")).toBeInTheDocument();
    await u.click(screen.getByRole("link", { name: "Bütçe vs Gerçekleşen" }));
    expect(yon.state.location.pathname).toBe("/butce-gerceklesen");
  });

  it("gerçekleşen senaryo yoksa yükleme yönlendirmesi", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: [senaryolar[0]], toplam: 1 })));
    kur("/butce-gerceklesen?senaryo=1", null);
    expect(await screen.findByText("Henüz gerçekleşen çalışması yok.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Veri Aktar" })).toHaveAttribute("href", "/recete-aktar?senaryo=1");
    expect(istekler).toHaveLength(0);
  });
});

describe("Genel Bakış gerçekleşen şeridi", () => {
  it("karşı senaryo varsa özet ve bağlantı", async () => {
    kur("/?senaryo=1");
    const serit = await screen.findByRole("status", { name: "Gerçekleşen kıyası" });
    await waitFor(() => expect(serit).toHaveTextContent("3 üründen 2 tanesinin maliyeti ±%5'in dışında"));
    expect(within(serit).getByRole("link")).toHaveAttribute("href", "/butce-gerceklesen?senaryo=1&a=1&b=2");
  });

  it("karşı senaryo yoksa hiçbir şey çizilmez", async () => {
    kur("/?senaryo=1", null);
    await waitFor(() => expect(screen.queryByRole("status", { name: "Gerçekleşen kıyası" })).not.toBeInTheDocument());
    expect(istekler).toHaveLength(0);
  });
});
