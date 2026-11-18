import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import type { YonetimOzeti as Ozet } from "@/api/tipler";
import YonetimOzeti from "./YonetimOzeti";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

/** Uydurma kısa fikstür (şirket verisi yok). */
const OZET: Ozet = {
  baslik: {
    senaryo_id: 1,
    sezon_ad: "2026-2027",
    ad: "Varsayılan",
    tur: "fiyat_calismasi",
    kilitli: false,
    hesap_tarihi: "2026-11-12",
    uretim_zamani: "2026-11-12T09:00:00+00:00",
  },
  urunler: { toplam: 12, hesaplanan: 10, hatali: 2 },
  marj: {
    ortalama: "0.22",
    agirlikli_ortalama: "0.185",
    adetli_urun: 7,
    hedef: "0.2",
    marj_esigi: "0.15",
    adet_kaynagi: "satis_gecmisi",
    gecen_yil_agirlikli_ortalama: "0.064",
    gecen_yil_urun: 6,
  },
  maliyet_yapisi: {
    urun_sayisi: 10,
    toplam_tl: "1000",
    urun_basina_tl: "100",
    kalemler: {
      malzeme: { toplam_tl: "600", pay_yuzde: "60.00", urun_basina_tl: "60" },
      uretim: { toplam_tl: "250", pay_yuzde: "25.00", urun_basina_tl: "25" },
      faaliyet: { toplam_tl: "100", pay_yuzde: "10.00", urun_basina_tl: "10" },
      finansman: { toplam_tl: "50", pay_yuzde: "5.00", urun_basina_tl: "5" },
    },
  },
  hedef_alti: {
    esik: "0.15",
    toplam: 4,
    kayitlar: [
      { kod: "U1", ad: "Biber Turşusu", kar_orani: "0.08", maliyet: "30", satis: "32.4", fiyat_kaynagi: "gecen_yil" },
      { kod: "U2", ad: "Nar Ekşisi", kar_orani: "0.12", maliyet: "50", satis: "56", fiyat_kaynagi: "hesap" },
    ],
  },
  kur_riski: {
    oran: "0.10",
    kurlar: { USD: "41.5", EUR: "48.2" },
    doviz_payi_yuzde: "35.00",
    yillik_etki_tl: "120000",
    yillik_maliyet_tl: "3400000",
    adetsiz_urun: 1,
    hatali: 0,
    en_riskli: [{ kod: "U3", ad: "Kapaklı Kavanoz", maliyet: "40", birim_etki: "2.4", yillik_etki: "48000", doviz_payi_yuzde: "60.00" }],
  },
  teklifler: {
    toplam: 9,
    durumlar: { taslak: 2, gonderildi: 1, kabul: 5, red: 1 },
    acik_sayi: 3,
    acik_toplam_tl: "45000",
    en_eski_acik: [
      {
        teklif_id: 7,
        urun_kodu: "U1",
        urun_ad: "Biber Turşusu",
        musteri: "Müşteri A",
        durum: "gonderildi",
        tur_no: 2,
        tarih: "2026-09-01",
        hesap_tarihi: "2026-08-30",
        fiyat_tl: "33.5",
      },
    ],
  },
  veri_kontrolu: {
    hata: 1,
    dikkat: 2,
    bilgi: 0,
    tamam: 5,
    sorunlar: [
      { kod: "fiyatsiz_malzeme", baslik: "Fiyatsız malzeme", durum: "hata", sayi: 3 },
      { kod: "satis_yok", baslik: "Satış fiyatı olmayan ürün", durum: "dikkat", sayi: 2 },
    ],
  },
  en_pahali: [
    { kod: "U9", ad: "Büyük Kavanoz", maliyet: "180", satis: "210" },
    { kod: "U8", ad: "Orta Kavanoz", maliyet: "120", satis: "150" },
  ],
  stok_etkisi: null,
  uyarilar: [{ kod: "U11", ad: "Deneme Ürünü", mesaj: "Reçete bulunamadı" }],
};

function kur(ozet: Ozet = OZET) {
  sunucu.use(http.get(`${T}/yonetim/ozet`, () => HttpResponse.json(ozet)));
}

function Yer() {
  const l = useLocation();
  return <output data-testid="yer">{l.pathname + l.search}</output>;
}

function ciz() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/yonetim-ozeti?senaryo=1"]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/yonetim-ozeti" element={<YonetimOzeti />} />
            <Route path="/urunler/:kod" element={<Yer />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const kutu = (ad: string) => screen.getByRole("group", { name: ad });

describe("Yönetim Özeti", () => {
  it("dört özet kutusunu ve alt başlığı gösterir", async () => {
    kur();
    ciz();
    expect(screen.getByRole("heading", { name: "Yönetim Özeti" })).toBeInTheDocument();
    expect(await screen.findByText("2026-2027 · Varsayılan · hesap tarihi 12.11.2026")).toBeInTheDocument();
    const urun = kutu("Ürün");
    expect(within(urun).getByText("12")).toBeInTheDocument();
    expect(urun).toHaveTextContent("10 hesaplanan");
    expect(urun).toHaveTextContent("2 hatalı");
    // kâr marjı: büyük sayı geçen yılın satış fiyatıyla (Kârlılık haritası), küçük sayı hesaplanan satış fiyatıyla; rozet eşik altı sayısı
    const marj = kutu("Kâr marjı");
    expect(marj).toHaveTextContent("6,4 % geçen yılın satış fiyatıyla");
    expect(marj).toHaveTextContent("adetle ağırlıklı · 6 ürün");
    expect(marj).toHaveTextContent("Hesaplanan satış fiyatıyla 18,5 %");
    expect(marj).not.toHaveTextContent("hedef");
    expect(within(marj).getByText("Marj eşiğinin altında 4 ürün")).toBeInTheDocument();
    const kur_ = kutu("Kur riski");
    expect(kur_).toHaveTextContent("35,0 %");
    expect(kur_).toHaveTextContent("120.000 TL");
    // açık tekliflerin TL toplamı (birim fiyatların toplamı) gösterilmez; durum sayıları yazılır
    const teklif = kutu("Teklifler");
    expect(within(teklif).getByText("3 açık teklif")).toBeInTheDocument();
    expect(teklif).toHaveTextContent("toplam 9 teklif (5 kabul, 1 red)");
    expect(teklif).not.toHaveTextContent("TL");
  });

  it("maliyet yapısı kalemleri yüzde ve ürün başına TL ile", async () => {
    kur();
    ciz();
    const yapi = await screen.findByRole("region", { name: "Maliyet yapısı" });
    expect(yapi).toHaveTextContent("Malzeme");
    expect(yapi).toHaveTextContent("60,0 %");
    expect(yapi).toHaveTextContent("60,00 TL");
    expect(yapi).toHaveTextContent("Finansman");
  });

  it("hedef altı tablosu satırları ve toplamı; satır ürün ekranına götürür", async () => {
    kur();
    ciz();
    const bolum = await screen.findByRole("region", { name: "Marj eşiğinin altındaki ürünler" });
    expect(bolum).toHaveTextContent("toplam 4 ürün");
    expect(bolum).toHaveTextContent(/marj eşiği \d+,\d %/);
    const satir = within(bolum).getByText("Nar Ekşisi").closest("tr") as HTMLElement;
    expect(satir).toHaveTextContent("12,0 %");
    expect(satir).toHaveTextContent("56,00 TL");
    expect(satir).toHaveTextContent("hesap");
    expect(within(bolum).getByText("Biber Turşusu").closest("tr")).toHaveTextContent("geçen yıl");
    await userEvent.click(within(bolum).getByText("Nar Ekşisi"));
    expect(await screen.findByTestId("yer")).toHaveTextContent("/urunler/U2?senaryo=1");
  });

  it("en riskli, en eski açık teklif, veri kontrolü, en pahalı ve uyarılar bölümleri", async () => {
    kur();
    ciz();
    expect(await screen.findByRole("region", { name: "En riskli ürünler (kur)" })).toHaveTextContent("Kapaklı Kavanoz");
    expect(screen.getByRole("region", { name: "En riskli ürünler (kur)" })).toHaveTextContent("60,0 %");
    const teklif = screen.getByRole("region", { name: "En eski açık teklifler" });
    expect(teklif).toHaveTextContent("Müşteri A");
    expect(teklif).toHaveTextContent("01.09.2026");
    expect(teklif).toHaveTextContent("33,50 TL");
    const kontrol = screen.getByRole("region", { name: "Veri Kontrolü" });
    expect(kontrol).toHaveTextContent("1 hata");
    expect(kontrol).toHaveTextContent("2 dikkat");
    expect(kontrol).toHaveTextContent("Fiyatsız malzeme");
    expect(within(kontrol).getByRole("link", { name: /Veri Kontrolü/ })).toHaveAttribute("href", "/veri-kontrolu?senaryo=1");
    expect(screen.getByRole("region", { name: "En pahalı ürünler" })).toHaveTextContent("Büyük Kavanoz");
    expect(screen.getByRole("region", { name: "Hesaplanamayan ürünler" })).toHaveTextContent("Reçete bulunamadı");
  });

  it("stok etkisi null iken kart yok; dolu iken değerleriyle var", async () => {
    kur();
    const { unmount } = ciz();
    await screen.findByRole("region", { name: "Maliyet yapısı" });
    expect(screen.queryByRole("region", { name: "Stok etkisi" })).not.toBeInTheDocument();
    unmount();

    kur({
      ...OZET,
      stok_etkisi: { kayit_sayisi: 6, etkili_urun: 4, stok_adedi: "12000", toplam_etki_tl: "-8500", satis_ortalama_maliyetten: true },
      uyarilar: [],
    });
    ciz();
    const stok = await screen.findByRole("region", { name: "Stok etkisi" });
    expect(stok).toHaveTextContent("6");
    expect(stok).toHaveTextContent("12.000");
    expect(stok).toHaveTextContent("-8.500 TL");
    expect(stok).toHaveTextContent("Açık");
    expect(screen.queryByRole("region", { name: "Hesaplanamayan ürünler" })).not.toBeInTheDocument();
  });

  it("Yazdır / PDF window.print çağırır; Yenile yenile=true ile yeniden ister", async () => {
    const istekler: (string | null)[] = [];
    sunucu.use(
      http.get(`${T}/yonetim/ozet`, ({ request }) => {
        istekler.push(new URL(request.url).searchParams.get("yenile"));
        return HttpResponse.json(OZET);
      }),
    );
    const yazdir = vi.spyOn(window, "print").mockImplementation(() => undefined);
    ciz();
    // Veri gelene dek düğmeler pasiftir.
    await screen.findByText("2026-2027 · Varsayılan · hesap tarihi 12.11.2026");
    await userEvent.click(screen.getByRole("button", { name: /Yazdır \/ PDF/ }));
    expect(yazdir).toHaveBeenCalledTimes(1);
    yazdir.mockRestore();
    expect(istekler).toEqual([null]);
    await userEvent.click(screen.getByRole("button", { name: "Yenile" }));
    await waitFor(() => expect(istekler.at(-1)).toBe("true"));
  });

  it("hata durumunda role=alert", async () => {
    sunucu.use(
      http.get(`${T}/yonetim/ozet`, () => HttpResponse.json({ hata: "sunucu", mesaj: "Özet hesaplanamadı", alanlar: {} }, { status: 500 })),
    );
    ciz();
    expect(await screen.findByRole("alert")).toHaveTextContent("Özet hesaplanamadı");
  });
});
