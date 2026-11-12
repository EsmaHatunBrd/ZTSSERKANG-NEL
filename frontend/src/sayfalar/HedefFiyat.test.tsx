import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import type { HedefFiyatSatiri } from "@/api/tipler";
import HedefFiyat from "./HedefFiyat";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

function satir(
  kod: string,
  ad: string,
  bolge: HedefFiyatSatiri["bolge"],
  zam: string | null,
  ek: string | null,
  hata: string | null = null,
): HedefFiyatSatiri {
  return {
    kod,
    ad,
    aile: "Turşu",
    bolge,
    maliyet: "30",
    gecen_yil_fiyat: zam === null ? null : "33",
    hesap_fiyati: "35",
    mevcut_marj: "0.1",
    hedef_fiyat: "34.5",
    gereken_zam: zam,
    liste_fiyati_yurtici: kod === "U3" ? null : "54.75",
    liste_fiyati_yurtdisi: kod === "U3" ? null : "38.35",
    marka: kod === "U3" ? null : "Berrak",
    adet: "10000",
    yillik_ek_gelir: ek,
    hata,
  };
}

const KAYITLAR = [
  satir("U1", "Biber Turşusu", "yuksek_adet_dusuk_marj", "0.0455", "15000"),
  satir("U2", "Zeytin Ezmesi", "yuksek_adet_yuksek_marj", "-0.05", "-17000"),
  satir("U3", "Domates Salçası", "dusuk_adet_dusuk_marj", "0.08", "4000"),
  satir("U4", "Nar Ekşisi", null, null, null, "Reçete eksik"),
];

function kur(marjlar: (string | null)[]) {
  sunucu.use(
    http.get(`${T}/analiz/hedef-fiyat`, ({ request }) => {
      const m = new URL(request.url).searchParams.get("marj");
      marjlar.push(m);
      return HttpResponse.json({
        marj: m ?? "0.15",
        bolen_yurtici: "0.63",
        bolen_yurtdisi: "0.90",
        yuvarlama: "0.05",
        adet_kaynagi: "satis_gecmisi",
        ozet: { urun_sayisi: 4, zam_gereken: 2, fiyatsiz: 0, hatali: 1, yillik_ek_gelir: "19000", ort_zam: "0.052" },
        kayitlar: KAYITLAR,
      });
    }),
  );
}

function ciz(adres = "/?senaryo=1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[adres]}>
        <SenaryoSaglayici>
          <HedefFiyat />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Marjı koruyan fiyat", () => {
  it("ilk istekte marj göndermez, gelen marjı kutuya yazar; değiştirip Hesapla deyince marj=0.2 gider", async () => {
    const marjlar: (string | null)[] = [];
    kur(marjlar);
    ciz();
    expect(await screen.findByText("Biber Turşusu")).toBeInTheDocument();
    expect(marjlar[0]).toBeNull();
    const kutu = screen.getByLabelText("Hedef marj (%)");
    expect(kutu).toHaveValue("15");
    expect(screen.getByText("Zam gereken ürün")).toBeInTheDocument();
    expect(screen.getByText(/liste fiyatı yalnız Berrak: yurtiçi ÷ 0,63, yurtdışı ÷ 0,90, en yakın 0,05 TL/)).toBeInTheDocument();
    // Hatalı ürün tabloda değil, ayrı notta
    expect(screen.getByRole("region", { name: "Hesaplanamayan ürünler" })).toHaveTextContent("Reçete eksik");

    await userEvent.clear(kutu);
    await userEvent.type(kutu, "20{Enter}");
    await waitFor(() => expect(marjlar.at(-1)).toBe("0.2"));
    await waitFor(() => expect(screen.getByLabelText("Hedef marj (%)")).toHaveValue("20"));
  });

  it("Excel'e indir bağlantısı ekranda uygulanan marj, bölge ve süzgeci taşır", async () => {
    kur([]);
    ciz();
    expect(await screen.findByText("Biber Turşusu")).toBeInTheDocument();
    const indir = () => screen.getByRole("link", { name: /Excel'e indir/ });
    expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/hedef-fiyat.xlsx?senaryo=1&yalniz_zam=1");

    await userEvent.click(screen.getByLabelText("Yalnız zam gerekenler"));
    expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/hedef-fiyat.xlsx?senaryo=1");

    const kutu = screen.getByLabelText("Hedef marj (%)");
    await userEvent.clear(kutu);
    await userEvent.type(kutu, "20{Enter}");
    await waitFor(() => expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/hedef-fiyat.xlsx?senaryo=1&marj=0.2"));

    await userEvent.click(within(screen.getByRole("group", { name: "Bölge" })).getByRole("button", { name: "Fiyatı gözden geçir" }));
    expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/hedef-fiyat.xlsx?senaryo=1&marj=0.2&bolge=yuksek_adet_dusuk_marj");
  });

  it("iki liste fiyatı sütunu: yurtiçi ve yurtdışı; Berrak olmayan üründe —", async () => {
    kur([]);
    ciz();
    const tablo = await screen.findByRole("table");
    expect(await within(tablo).findByText("Biber Turşusu")).toBeInTheDocument();
    expect(within(tablo).getByRole("columnheader", { name: /Liste fiyatı yurtiçi/ })).toBeInTheDocument();
    expect(within(tablo).getByRole("columnheader", { name: /Liste fiyatı yurtdışı/ })).toBeInTheDocument();
    const biber = within(tablo).getByText("Biber Turşusu").closest("tr") as HTMLElement;
    expect(biber).toHaveTextContent("54,75 TL");
    expect(biber).toHaveTextContent("38,35 TL");
    const salca = within(tablo).getByText("Domates Salçası").closest("tr") as HTMLElement;
    expect(within(salca).getAllByText("—").length).toBeGreaterThanOrEqual(2);
  });

  it("varsayılan yalnız zam gerekenleri gösterir; kutu kaldırılınca hepsi görünür", async () => {
    kur([]);
    ciz();
    const tablo = await screen.findByRole("table");
    expect(await within(tablo).findByText("Biber Turşusu")).toBeInTheDocument();
    expect(within(tablo).getByText("Domates Salçası")).toBeInTheDocument();
    expect(within(tablo).queryByText("Zeytin Ezmesi")).not.toBeInTheDocument();
    expect(within(tablo).queryByText("Nar Ekşisi")).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Yalnız zam gerekenler"));
    expect(within(tablo).getByText("Zeytin Ezmesi")).toBeInTheDocument();
  });

  it("?bolge= ile o bölgeye süzülür; Tümü süzmeyi kaldırır", async () => {
    kur([]);
    ciz("/?senaryo=1&bolge=yuksek_adet_dusuk_marj");
    const tablo = await screen.findByRole("table");
    expect(await within(tablo).findByText("Biber Turşusu")).toBeInTheDocument();
    expect(within(tablo).queryByText("Domates Salçası")).not.toBeInTheDocument();
    const grup = screen.getByRole("group", { name: "Bölge" });
    expect(within(grup).getByRole("button", { name: "Fiyatı gözden geçir" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(within(grup).getByRole("button", { name: "Tümü" }));
    expect(within(tablo).getByText("Domates Salçası")).toBeInTheDocument();
  });
});
