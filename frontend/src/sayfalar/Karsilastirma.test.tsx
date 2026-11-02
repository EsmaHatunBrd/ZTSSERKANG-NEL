import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import Karsilastirma from "./Karsilastirma";

beforeAll(() => {
  // Recharts ResponsiveContainer jsdom'da boyut ölçemez: gözlemci, gözlemlenen öğe için sabit 600x220 boyut bildirir.
  globalThis.ResizeObserver = class {
    cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }
    observe(hedef: Element) {
      this.cb([{ target: hedef, contentRect: { width: 600, height: 220 } } as unknown as ResizeObserverEntry], this as unknown as ResizeObserver);
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

function kur(yol = "/karsilastirma?senaryo=1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  yon = createMemoryRouter(
    [
      {
        path: "/karsilastirma",
        element: (
          <SenaryoSaglayici>
            <Karsilastirma />
          </SenaryoSaglayici>
        ),
      },
    ],
    { initialEntries: [yol] },
  );
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={yon} />
    </QueryClientProvider>,
  );
}

describe("Karşılaştırma sayfası", () => {
  it("aile_ad gösterilir (liste, başlık), URL ve istek anahtarı kullanır; tek üyeli aile bilgi satırı çıkar", async () => {
    sunucu.use(
      http.get("*/api/v1/karsilastirma/aileler", () =>
        HttpResponse.json([
          { aile: "karişik turşu", aile_ad: "karışık turşu", urun_sayisi: 2, tek_uyeli: false, urunler: [] },
          { aile: "tek", aile_ad: "tek", urun_sayisi: 1, tek_uyeli: true, urunler: [] },
        ]),
      ),
      http.get("*/api/v1/karsilastirma/aile/:aile", ({ params }) =>
        HttpResponse.json({ aile: params.aile, aile_ad: params.aile === "tek" ? "tek" : "karışık turşu", satirlar: [] }),
      ),
    );
    kur();
    const liste = await screen.findByRole("navigation", { name: "Aile listesi" });
    const btn = await within(liste).findByRole("button", { name: /karışık turşu/ });
    expect(within(liste).queryByText("karişik turşu")).not.toBeInTheDocument();
    await userEvent.click(btn);
    expect(yon.state.location.search).toContain("aile=kari%C5%9Fik+tur%C5%9Fu");
    expect(await screen.findByRole("heading", { level: 2, name: "karışık turşu" })).toBeInTheDocument();
    expect(screen.queryByTestId("tek-uyeli-notu")).not.toBeInTheDocument();
    await userEvent.click(within(liste).getByRole("button", { name: /tek/ }));
    expect(await screen.findByTestId("tek-uyeli-notu")).toHaveTextContent("tek üyeli");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // Uyarı değil, bilgi satırı
  });

  it("üst not: sayfanın yüklü fiyat çalışmasını kullandığını söyler ve Satış Geçmişi'ne bağlantı verir", async () => {
    kur();
    const not = await screen.findByRole("note");
    expect(not).toHaveTextContent(/yüklü fiyat çalışmasını kullanır/);
    expect(within(not).getByRole("link", { name: "Satış Geçmişi" })).toHaveAttribute("href", expect.stringContaining("/satis-gecmisi"));
  });

  it("aile listesi ürün sayısını gösterir; tek üyeli aile soluk ve 'tek ürün' yazar; aile seçilmeyince yönlendirme metni", async () => {
    kur();
    const liste = await screen.findByRole("navigation", { name: "Aile listesi" });
    const tursu = await within(liste).findByRole("button", { name: /turşu/ });
    expect(tursu).toHaveTextContent("2 ürün");
    const deneme = within(liste).getByRole("button", { name: /deneme/ });
    expect(deneme).toHaveTextContent("tek ürün");
    expect(deneme.className).toMatch(/opacity-60/);
    expect(screen.getByText("Soldan bir aile seçin.")).toBeInTheDocument();
  });

  it("aile seçilince tablo ve grafik gelir; URL aile parametresi yazılır; geri gidince seçim kalkar", async () => {
    kur();
    await userEvent.click(await screen.findByRole("button", { name: /turşu/ }));
    expect(yon.state.location.search).toContain("aile=tur%C5%9Fu");
    expect(yon.state.location.search).toContain("senaryo=1");

    // Tablo: üç satır (biri hata), hata satırı uyarı metniyle.
    const tablo = await screen.findByRole("table");
    await within(tablo).findByText("Biber Turşusu 370 ml");
    const govde = tablo.querySelectorAll("tbody tr");
    expect(govde).toHaveLength(3);
    expect(within(tablo).getByText("üretim hedefi yok")).toBeInTheDocument();
    const urun1 = within(tablo).getByText("Salatalık Turşusu 720 ml").closest("tr") as HTMLElement;
    expect(within(urun1).getByText("45,76 TL")).toBeInTheDocument();
    expect(within(urun1).getByText("-30,5 %")).toBeInTheDocument();

    // Grafik: erişilebilir etiket, hatasız 2 nokta; çubuk paneli ve çizgi paneli ayrı tek eksen.
    const grafik = await screen.findByRole("img", { name: /turşu ailesi/ });
    await waitFor(() => expect(grafik.querySelectorAll("svg").length).toBeGreaterThanOrEqual(2));
    expect(grafik.querySelectorAll(".recharts-bar-rectangle")).toHaveLength(2);
    expect(grafik.querySelectorAll(".recharts-line").length).toBe(1);
    expect(grafik.querySelectorAll(".recharts-line-dot")).toHaveLength(2);
    expect(grafik.getAttribute("aria-label")).toContain("370 ml: birim satış 32,94 TL");
    expect(grafik.getAttribute("aria-label")).toContain("5 lt: birim satış 45,76 TL");
    expect(grafik.getAttribute("aria-label")).not.toMatch(/5 ml|5 000|5000 ml/);
    // Sunucu sırası korunur (370 ml, sonra 5 lt); x ekseni etiketleri etiketten gelir.
    expect(grafik.textContent).toMatch(/370 ml[\s\S]*5 lt/);
    expect(within(tablo).getByText("5 lt")).toBeInTheDocument();
    expect(grafik.getAttribute("aria-label")).not.toContain("500 ml");

    await yon.navigate(-1);
    await waitFor(() => expect(screen.getByText("Soldan bir aile seçin.")).toBeInTheDocument());
  });

  it("URL'de aile varsa doğrudan açılır ve aile adı yola kodlanarak istenir", async () => {
    const yollar: string[] = [];
    sunucu.use(
      http.get("*/api/v1/karsilastirma/aile/:aile", ({ request }) => {
        yollar.push(new URL(request.url).pathname);
        return HttpResponse.json({ aile: "a/b", satirlar: [] });
      }),
    );
    kur("/karsilastirma?senaryo=1&aile=a%2Fb");
    await screen.findByText("Bu ailede ürün yok");
    expect(yollar[0]).toBe("/api/v1/karsilastirma/aile/a%2Fb");
    expect(screen.queryByRole("img", { name: /ailesi/ })).not.toBeInTheDocument();
  });

  it("arama aile veya ürün adına göre süzer; sonuç yoksa açıklama gösterir", async () => {
    kur();
    await screen.findByRole("button", { name: /turşu/ });
    await userEvent.type(screen.getByRole("searchbox", { name: "Aile ara" }), "deneme ürünü");
    expect(screen.queryByRole("button", { name: /turşu/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deneme/ })).toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox", { name: "Aile ara" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Aile ara" }), "yok böyle");
    expect(screen.getByText("Aramaya uyan aile yok")).toBeInTheDocument();
  });

  it("aile listesi boşsa ve hata verirse durum metinleri görünür", async () => {
    sunucu.use(http.get("*/api/v1/karsilastirma/aileler", () => HttpResponse.json([])));
    kur();
    expect(await screen.findByText(/Aile bulunamadı/)).toBeInTheDocument();
  });

  it("aile listesi hata verirse uyarı gösterir", async () => {
    sunucu.use(
      http.get("*/api/v1/karsilastirma/aileler", () =>
        HttpResponse.json({ hata: "bulunamadi", mesaj: "senaryo yok", alanlar: {} }, { status: 404 }),
      ),
    );
    kur();
    expect(await screen.findByRole("alert")).toHaveTextContent("senaryo yok");
  });
});
