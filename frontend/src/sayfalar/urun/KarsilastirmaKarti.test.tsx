import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { urunKarsilastirmaBos } from "@/test/fikstur/karsilastirma";
import { AileRozeti } from "./AileRozeti";
import { KarsilastirmaKarti } from "./KarsilastirmaKarti";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

function kur(eleman: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{eleman}</MemoryRouter>
    </QueryClientProvider>,
  );
  return qc;
}

describe("KarsilastirmaKarti", () => {
  it("üç bölümü sunucu değerleriyle gösterir", async () => {
    kur(<KarsilastirmaKarti kod="URUN-001" senaryoId={1} tarih="" />);
    const kart = await screen.findByRole("region", { name: "Karşılaştırma" });

    const gecen = await within(kart).findByRole("table", {
      name: "Geçen yıl ortalama fiyat",
    });
    const tl = within(gecen).getByText("TL").closest("tr") as HTMLElement;
    expect(within(tl).getByText("42,50 TL")).toBeInTheDocument();
    expect(within(tl).getByText("400")).toBeInTheDocument();
    expect(within(gecen).getByText("0,500 USD")).toBeInTheDocument();

    const enf = within(kart).getByRole("table", { name: "Enflasyon eşiği" });
    const enfTl = within(enf).getByText("TL").closest("tr") as HTMLElement;
    expect(within(enfTl).getByText("-6,7 %")).toBeInTheDocument();
    expect(within(enfTl).getByText("altında")).toBeInTheDocument();
    const enfUsd = within(enf).getByText("USD").closest("tr") as HTMLElement;
    expect(within(enfUsd).getByText("üstünde")).toBeInTheDocument();

    const hedef = within(kart).getByRole("table", {
      name: "Hedef adetle maliyet ve satış",
    });
    expect(within(kart).getByText("65.000")).toBeInTheDocument();
    expect(within(kart).getByText("130.000")).toBeInTheDocument();
    expect(within(kart).getByText("2,00 ×")).toBeInTheDocument();
    const maliyetHedef = within(hedef).getByText("Maliyet (hedef adedi)").closest("tr") as HTMLElement;
    expect(within(maliyetHedef).getByText("14,75 TL")).toBeInTheDocument();
    expect(within(maliyetHedef).getByText("0,253 USD")).toBeInTheDocument();
    expect(within(maliyetHedef).getByText("0,211 EUR")).toBeInTheDocument();
  });

  it("veri yoksa her bölüm kısa açıklama ve bağlantı gösterir", async () => {
    sunucu.use(http.get("*/api/v1/karsilastirma/urun/:kod", () => HttpResponse.json(urunKarsilastirmaBos)));
    kur(<KarsilastirmaKarti kod="URUN-001" senaryoId={1} tarih="" />);
    const kart = await screen.findByRole("region", { name: "Karşılaştırma" });
    const bag = await within(kart).findByRole("link", {
      name: "Satış Geçmişi sayfasından yükleyin",
    });
    expect(bag).toHaveAttribute("href", "/satis-gecmisi?senaryo=1");
    expect(within(kart).getByText(/Enflasyon karşılaştırması için/)).toBeInTheDocument();
    expect(
      within(kart).getByRole("link", {
        name: "Üretim Adetleri sayfasından girin",
      }),
    ).toBeInTheDocument();
  });

  it("hesap hatası varsa enflasyon bölümü nedeni yazar", async () => {
    sunucu.use(
      http.get("*/api/v1/karsilastirma/urun/:kod", () =>
        HttpResponse.json({
          ...urunKarsilastirmaBos,
          hesap_hatasi: "üretim hedefi yok",
        }),
      ),
    );
    kur(<KarsilastirmaKarti kod="URUN-001" senaryoId={1} tarih="" />);
    expect(await screen.findByText("Hesap yapılamadı: üretim hedefi yok")).toBeInTheDocument();
  });

  it("sunucu hatasında uyarı gösterir", async () => {
    sunucu.use(
      http.get("*/api/v1/karsilastirma/urun/:kod", () =>
        HttpResponse.json({ hata: "bulunamadi", mesaj: "ürün yok", alanlar: {} }, { status: 404 }),
      ),
    );
    kur(<KarsilastirmaKarti kod="URUN-001" senaryoId={1} tarih="" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("ürün yok");
  });

  it("müşteri listesi satış geçmişinden gelir; seçim musteri ve tarih parametresiyle yeniden sorgular", async () => {
    const istekler: URLSearchParams[] = [];
    sunucu.use(
      http.get("*/api/v1/karsilastirma/urun/:kod", ({ request }) => {
        istekler.push(new URL(request.url).searchParams);
        return HttpResponse.json(urunKarsilastirmaBos);
      }),
    );
    kur(<KarsilastirmaKarti kod="URUN-001" senaryoId={1} tarih="2026-10-01" />);
    const secici = await screen.findByLabelText("Müşteri süzgeci");
    await waitFor(() =>
      expect(
        within(secici)
          .getAllByRole("option")
          .map((o) => o.textContent),
      ).toEqual(["Tüm müşteriler", "Müşteri A", "Müşteri B"]),
    );
    expect(istekler[0].get("senaryo")).toBe("1");
    expect(istekler[0].get("tarih")).toBe("2026-10-01");
    expect(istekler[0].has("musteri")).toBe(false);
    await userEvent.selectOptions(secici, "Müşteri A");
    await waitFor(() => expect(istekler.at(-1)?.get("musteri")).toBe("Müşteri A"));
    expect(istekler.at(-1)?.get("tarih")).toBe("2026-10-01");
  });
});

describe("AileRozeti", () => {
  it("ürünün ailesini gösterir; diyalogdan elle atama PATCH gövdesi {aile} olur", async () => {
    const govdeler: unknown[] = [];
    sunucu.use(
      http.patch("*/api/v1/urunler/:kod/aile", async ({ request }) => {
        govdeler.push(await request.json());
        return HttpResponse.json({ kod: "URUN-001", aile: "yeni aile" });
      }),
    );
    const qc = kur(<AileRozeti kod="URUN-001" aile="turşu" />);
    expect(await screen.findByText("Aile: turşu")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ürün ailesini düzenle" }));
    const diyalog = await screen.findByRole("dialog");
    const girdi = within(diyalog).getByLabelText("Aile adı");
    expect(girdi).toHaveValue("turşu");
    await userEvent.clear(girdi);
    await userEvent.type(girdi, "yeni aile");
    qc.setQueryData(["urun", "URUN-001", 1], { kod: "URUN-001" });
    await userEvent.click(within(diyalog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(govdeler).toEqual([{ aile: "yeni aile" }]));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // urun sorgusu geçersiz kılındı
    expect(qc.getQueryState(["urun", "URUN-001", 1])?.isInvalidated).toBe(true);
  });

  it("G3: rozet ve diyalog anahtarı değil görünen adı (aile_ad) gösterir; yazılan ad {aile} olarak gider", async () => {
    const govdeler: unknown[] = [];
    sunucu.use(
      http.patch("*/api/v1/urunler/:kod/aile", async ({ request }) => {
        govdeler.push(await request.json());
        return HttpResponse.json({
          kod: "URUN-001",
          aile: "karişik turşu",
          aile_ad: "Karışık Turşu",
        });
      }),
    );
    kur(<AileRozeti kod="URUN-001" aile="karişik turşu" aileAd="Karışık Turşu" />);
    expect(await screen.findByText("Aile: Karışık Turşu")).toBeInTheDocument();
    expect(screen.queryByText(/karişik/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ürün ailesini düzenle" }));
    const diyalog = await screen.findByRole("dialog");
    const girdi = within(diyalog).getByLabelText("Aile adı");
    expect(girdi).toHaveValue("Karışık Turşu");
    expect(diyalog).not.toHaveTextContent("karişik");
    await userEvent.clear(girdi);
    await userEvent.type(girdi, "Karışık Turşu Cam");
    await userEvent.click(within(diyalog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(govdeler).toEqual([{ aile: "Karışık Turşu Cam" }]));
  });

  it("'Yeniden türet' null gönderir", async () => {
    const govdeler: unknown[] = [];
    sunucu.use(
      http.patch("*/api/v1/urunler/:kod/aile", async ({ request }) => {
        govdeler.push(await request.json());
        return HttpResponse.json({ kod: "URUN-001", aile: "turşu" });
      }),
    );
    kur(<AileRozeti kod="URUN-001" aile="turşu" />);
    await screen.findByText("Aile: turşu");
    await userEvent.click(screen.getByRole("button", { name: "Ürün ailesini düzenle" }));
    await userEvent.click(
      within(await screen.findByRole("dialog")).getByRole("button", {
        name: "Yeniden türet",
      }),
    );
    await waitFor(() => expect(govdeler).toEqual([{ aile: null }]));
  });

  it("sunucu hatası diyalogda kalır ve Türkçe mesaj gösterir", async () => {
    sunucu.use(
      http.patch("*/api/v1/urunler/:kod/aile", () =>
        HttpResponse.json(
          {
            hata: "dogrulama",
            mesaj: "aile en çok 120 karakter olabilir",
            alanlar: {},
          },
          { status: 422 },
        ),
      ),
    );
    kur(<AileRozeti kod="URUN-001" aile="turşu" />);
    await screen.findByText("Aile: turşu");
    await userEvent.click(screen.getByRole("button", { name: "Ürün ailesini düzenle" }));
    const diyalog = await screen.findByRole("dialog");
    await userEvent.click(within(diyalog).getByRole("button", { name: "Kaydet" }));
    expect(await within(diyalog).findByRole("alert")).toHaveTextContent("120 karakter");
  });
});
