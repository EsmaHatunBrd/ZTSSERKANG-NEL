import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { KarlilikSatiri, KurRiskiSatiri } from "@/api/tipler";
import KurRiski from "./KurRiski";
import KarlilikHaritasi from "./KarlilikHaritasi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

function kur(kod: string, ad: string, yillikEtki: string | null, adet: string | null): KurRiskiSatiri {
  return {
    kod,
    ad,
    hat: "Niko",
    maliyet: "30",
    doviz_payi: "0.4",
    usd_payi: "0.3",
    eur_payi: "0.1",
    birim_etki: "1.2",
    yeni_maliyet: "31.2",
    yillik_adet: adet,
    yillik_etki: yillikEtki,
    hata: null,
  };
}

describe("Kur riski", () => {
  it("varsayılan %10 ile veri gösterir; oran değişip Hesapla'ya basınca oran=0.2 gider", async () => {
    const oranlar: (string | null)[] = [];
    sunucu.use(
      http.get(`${T}/analiz/kur-riski`, ({ request }) => {
        const p = new URL(request.url).searchParams;
        oranlar.push(p.get("oran"));
        return HttpResponse.json({
          oran: p.get("oran"),
          kurlar: { USD: "41.5", EUR: "48.2" },
          ozet: { urun_sayisi: 2, doviz_payi_ort: "0.35", yillik_maliyet: "900000", yillik_etki: "12000", adetsiz_urun: 1, hatali: 0 },
          para_birimleri: [
            { para_birimi: "USD", yillik_etki: "9000", pay: "0.75" },
            { para_birimi: "EUR", yillik_etki: "3000", pay: "0.25" },
          ],
          kayitlar: [kur("U2", "Zeytin Ezmesi", null, null), kur("U1", "Biber Turşusu", "12000", "10000")],
        });
      }),
    );
    kurSayfa(<KurRiski />);
    expect(screen.getByLabelText("Kur artış oranı (%)")).toHaveValue("10");
    expect(await screen.findByText("Biber Turşusu")).toBeInTheDocument();
    expect(oranlar[0]).toBe("0.1");
    expect(screen.getByText("Ortalama döviz payı")).toBeInTheDocument();
    expect(screen.getByText("Adeti olmayan ürün")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Para birimi kırılımı" })).toHaveTextContent("USD");
    // En çok etkilenen (yıllık etkisi olan) üstte
    const satirlar = screen.getAllByRole("row");
    const ilk = satirlar.findIndex((r) => r.textContent?.includes("Biber Turşusu"));
    const ikinci = satirlar.findIndex((r) => r.textContent?.includes("Zeytin Ezmesi"));
    expect(ilk).toBeLessThan(ikinci);

    const kutu = screen.getByLabelText("Kur artış oranı (%)");
    await userEvent.clear(kutu);
    await userEvent.type(kutu, "20");
    await userEvent.click(screen.getByRole("button", { name: "Hesapla" }));
    await waitFor(() => expect(oranlar.at(-1)).toBe("0.2"));
    expect(screen.getByRole("link", { name: /Excel'e indir/ })).toHaveAttribute(
      "href",
      "/api/v1/disa-aktar/kur-riski.xlsx?senaryo=1&oran=0.2",
    );
  });
});

function kar(kod: string, ad: string, bolge: KarlilikSatiri["bolge"], adet: string | null, marj: string): KarlilikSatiri {
  return {
    kod,
    ad,
    aile: "Turşu",
    adet,
    maliyet: "30",
    satis_fiyati: "36",
    marj,
    fiyat_kaynagi: "satis_gecmisi",
    yillik_kar: adet === null ? null : "60000",
    bolge,
    hata: null,
  };
}

describe("Kârlılık haritası", () => {
  it("bölgeleri gösterir; bölge kartına tıklayınca tablo o bölgeye süzülür", async () => {
    sunucu.use(
      http.get(`${T}/analiz/karlilik`, () =>
        HttpResponse.json({
          esik_marj: "0.1",
          esik_adet: "5000",
          ozet: {
            yuksek_adet_yuksek_marj: 1,
            yuksek_adet_dusuk_marj: 1,
            dusuk_adet_yuksek_marj: 0,
            dusuk_adet_dusuk_marj: 0,
            adetsiz: 1,
            hatali: 0,
          },
          kayitlar: [
            kar("U1", "Biber Turşusu", "yuksek_adet_yuksek_marj", "10000", "0.2"),
            kar("U2", "Zeytin Ezmesi", "yuksek_adet_dusuk_marj", "8000", "0.05"),
            kar("U3", "Domates Salçası", null, null, "0.15"),
          ],
        }),
      ),
    );
    kurSayfa(<KarlilikHaritasi />);
    expect(await screen.findByText("Biber Turşusu")).toBeInTheDocument();
    expect(screen.getByText("Zeytin Ezmesi")).toBeInTheDocument();
    expect(screen.getByText("bölge yok")).toBeInTheDocument();
    expect(screen.getAllByText("geçen yıl").length).toBeGreaterThan(0);
    expect(screen.getByText(/1 ürünün yıllık adeti yok/)).toBeInTheDocument();
    const indir = () => screen.getByRole("link", { name: /Excel'e indir/ });
    expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/karlilik.xlsx?senaryo=1");
    // toplam satırı: ürün sayısı, adet ve yıllık kâr (adeti/kârı boş olan atlanır)
    const alt = () => screen.getByRole("table").querySelector("tfoot") as HTMLElement;
    expect(within(alt()).getByText("Toplam (3 ürün)")).toBeInTheDocument();
    expect(within(alt()).getByText("18.000")).toBeInTheDocument();
    expect(within(alt()).getByText("120.000 TL")).toBeInTheDocument();

    const bolgeler = screen.getByRole("group", { name: "Bölgeler" });
    await userEvent.click(within(bolgeler).getByRole("button", { name: /Fiyatı gözden geçir/ }));
    expect(within(bolgeler).getByRole("button", { name: /Fiyatı gözden geçir/ })).toHaveAttribute("aria-pressed", "true");
    const tablo = screen.getByRole("table");
    expect(within(tablo).getByText("Zeytin Ezmesi")).toBeInTheDocument();
    expect(within(tablo).queryByText("Biber Turşusu")).not.toBeInTheDocument();
    expect(within(tablo).queryByText("Domates Salçası")).not.toBeInTheDocument();
    expect(within(alt()).getByText("Toplam (1 ürün)")).toBeInTheDocument();
    expect(within(alt()).getByText("8.000")).toBeInTheDocument();
    expect(within(alt()).getByText("60.000 TL")).toBeInTheDocument();
    expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/karlilik.xlsx?senaryo=1&bolge=yuksek_adet_dusuk_marj");

    await userEvent.click(screen.getByRole("button", { name: /Süzmeyi kaldır/ }));
    expect(within(tablo).getByText("Biber Turşusu")).toBeInTheDocument();
    expect(indir()).toHaveAttribute("href", "/api/v1/disa-aktar/karlilik.xlsx?senaryo=1");
  });
});
