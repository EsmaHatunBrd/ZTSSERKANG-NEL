import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem } from "@/api/tipler";
import SmmSarfFarki from "./SmmSarfFarki";
import SmmUretim from "./SmmUretim";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem = {
  id: 7,
  yil: 2026,
  ay: 9,
  ad: "Eylül 2026",
  kaynak_dosya: null,
  finansman: "0",
  kalem_sayisi: 5,
  olusturan: "Esma",
  recete_kaynagi: "excel",
  devir_donem_id: null,
  excel_kontrol: null,
  kilitli: false,
  kilitleyen: null,
} as unknown as SmmDonem;

// Uydurma dönem: havuzlar 20: 1000, 40 işçilik 400, 40 GÜG 1000, 50: 300; mizan 720: 1000, 730: 5000.
const URETIM = {
  donem,
  asama: 50,
  ozetler: [20, 40, 50].map((asama) => ({
    asama,
    ad: { 20: "Sebze kabul", 40: "Üretim hattı", 50: "Etiketleme" }[asama],
    urun_sayisi: 1,
    uretilen_urun: 1,
    sure_yok: 0,
    alim_kurali: 0,
    kod_bosluklu: 0,
    excel_elle: 0,
    malzeme: "100",
    iscilik: "100",
    gug: "0",
    fire: "0",
    toplam: "200",
    excel: { karsilastirilan: 0, esit: 0, farkli: 0, farkli_ornek: [] },
  })),
  dagitim: {
    havuzlar: [{ anahtar: "50_uretim", ad: "50 · Üretim işçilik + GÜG", tutar: "300", excel: "300", degisti: false }],
    dagitilan: "2700",
    mizan_720: "1000",
    mizan_730: "5000",
    dagitilmayan: "3300",
    anahtarlar: [],
  },
  kayitlar: [],
};
const asama = (a: number, ad: string, anahtar: string, birlesik: boolean, isc: string, gug: string, top: string, pay: string) => ({
  asama: a,
  ad,
  anahtar,
  birlesik,
  havuz: top,
  iscilik: isc,
  gug,
  toplam: top,
  pay_yuzde: pay,
  urun_sayisi: 1,
  uretim_miktar: "100",
  birim_basina_ortalama: "10",
});
const GIDER = {
  donem,
  kaynaklar: [
    {
      hesap: "720",
      ad: "Direkt işçilik giderleri",
      mizan_tutari: "1000",
      dagitilan: "400",
      dagitilan_kapsami: "40 · işçilik",
      dagitilmayan: null,
      dagitilmayan_yuzde: null,
    },
    {
      hesap: "730",
      ad: "Genel üretim giderleri",
      mizan_tutari: "5000",
      dagitilan: "1000",
      dagitilan_kapsami: "40 · GÜG",
      dagitilmayan: null,
      dagitilmayan_yuzde: null,
    },
  ],
  toplam: { mizan_tutari: "6000", dagitilan: "2700", dagitilmayan: "3300", dagitilmayan_yuzde: "0.55" },
  ayrilmamis: "1300",
  havuz_toplami: "2700",
  asamalar: [
    asama(20, "Sebze kabul", "Üretim miktarı", true, "1000", "0", "1000", "0.37"),
    asama(40, "Üretim hattı", "İşçilik: Üretim × etiket adam-sn · GÜG: Üretim × dolum sn", false, "400", "1000", "1400", "0.52"),
    asama(50, "Etiketleme", "Üretim × dolum sn", true, "300", "0", "300", "0.11"),
  ],
  urunler_ilk20: [
    { kod: "02-1", ad: "Biber 370", asama: 40, iscilik: "400", gug: "1000", toplam: "1400" },
    { kod: "01-1", ad: "Biber salamura", asama: 20, iscilik: "1000", gug: "0", toplam: "1000" },
  ],
  urun_sayisi: 2,
  esik_yuzde: "0.05",
  notlar: ["Aşama havuzlarına girilen işçilik + GÜG 2.700 TL, gider mizanı 720 + 730 6.000 TL: 3.300 TL havuzlara aktarılmamış."],
};

describe("Üretim Maliyeti: gider dağıtım tablosu", () => {
  it("bölüm açılınca 720 / 730 / toplam kutuları, aşama tablosu, grafik ve en çok gider alan ürünler; havuz alanları yerinde", async () => {
    let giderIstegi = 0;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/uretim`, () => HttpResponse.json(URETIM)),
      http.get(`${T}/smm/donemler/:id/gider-dagitimi`, ({ params }) => {
        giderIstegi += 1;
        expect(params.id).toBe("7");
        return HttpResponse.json(GIDER);
      }),
    );
    kurSayfa(<SmmUretim />);
    const u = userEvent.setup();
    await u.click(await screen.findByText("Dağıtılan işçilik ve genel gider"));
    // kutular: 720 ve 730'da yalnız 40'ın ayrılabilen kısmı; toplamda dağıtılmayan %55 -> sarı vurgu
    const k720 = await screen.findByRole("region", { name: "720 · Direkt işçilik giderleri" });
    expect(within(k720).getByText("Ayrı dağıtılan (40 · işçilik)")).toBeInTheDocument();
    expect(within(k720).getByText("1.000 TL")).toBeInTheDocument();
    expect(within(k720).getByText("400 TL")).toBeInTheDocument();
    expect(k720).not.toHaveAttribute("data-uyari");
    const top = screen.getByRole("region", { name: "720 + 730 toplam" });
    expect(top).toHaveAttribute("data-uyari", "true");
    expect(within(top).getByText("6.000 TL")).toBeInTheDocument();
    expect(within(top).getByText("3.300 TL")).toBeInTheDocument();
    expect(within(top).getByText("(55,0 %)")).toBeInTheDocument();
    expect(within(top).getByText(/%5'inden fazlası/)).toBeInTheDocument();
    expect(within(top).getByText(/1.300 TL kadarı 20 ve 50'de işçilik \+ GÜG birleşik/)).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Dağıtım notları" })).getByText(/havuzlara aktarılmamış/)).toBeInTheDocument();
    // aşama tablosu: 40 ayrı, 20 / 50 birleşik
    const tablo = screen.getByRole("table", { name: "Aşamalara dağıtılan işçilik ve GÜG" });
    const s40 = within(tablo).getByRole("row", { name: /40 · Üretim hattı/ });
    expect(within(s40).getByText("1.400 TL")).toBeInTheDocument();
    expect(within(s40).getByText("52,0 %")).toBeInTheDocument();
    expect(within(within(tablo).getByRole("row", { name: /20 · Sebze kabul/ })).getByText("1.000 TL (işçilik + GÜG)")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Aşamalara dağıtılan işçilik ve genel üretim gideri/ })).toHaveAccessibleName(
      /40 · Üretim hattı: işçilik 400 TL, GÜG 1.000 TL/,
    );
    // en çok gider alan ürünler katlanır
    await u.click(screen.getByText(/En çok gider alan 2 ürün/));
    const urunler = screen.getByRole("table", { name: "En çok gider alan ürünler" });
    expect(within(urunler).getAllByRole("row")[1]).toHaveTextContent("Biber 370");
    // mevcut havuz alanları ve düğmeler kaybolmadı
    expect(screen.getByLabelText("50 · Üretim işçilik + GÜG")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet ve yeniden hesapla" })).toBeInTheDocument();
    expect(giderIstegi).toBe(1);
  });

  it("bölüm kapalıyken istek atılmaz; sunucu hatası bölümde gösterilir", async () => {
    let giderIstegi = 0;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/uretim`, () => HttpResponse.json(URETIM)),
      http.get(`${T}/smm/donemler/:id/gider-dagitimi`, () => {
        giderIstegi += 1;
        return HttpResponse.json({ hata: "bulunamadi", mesaj: "dönem bulunamadı", alanlar: {}, kod: null }, { status: 404 });
      }),
    );
    kurSayfa(<SmmUretim />);
    await screen.findByText("Dağıtılan işçilik ve genel gider");
    expect(giderIstegi).toBe(0);
    await userEvent.click(screen.getByText("Dağıtılan işçilik ve genel gider"));
    expect(await screen.findByRole("alert")).toHaveTextContent("dönem bulunamadı");
  });
});

const sarfKalemi = (kod: string, ad: string, tutar: string, yon: "fazla" | "eksik") => ({
  kod,
  ad,
  birim: "KG",
  tur: "0001-Hammadde",
  birim_fiyat: "10",
  beklenen_sarf: "100",
  gercek_sarf: "120",
  fark_miktar: "20",
  fark_tutar: tutar,
  fark_yuzde: "0.2",
  yon,
});
const SARF_OZET = {
  donem,
  ilk: 20,
  kalem_sayisi: 3,
  kalemler: [
    sarfKalemi("01-1", "Biber salamura", "4128", "fazla"),
    sarfKalemi("HM-1", "Biber", "-1380", "eksik"),
    sarfKalemi("AMB-1", "Kavanoz", "575", "fazla"),
  ],
  ozet: {
    toplam_fark_tutari: "3323",
    fazla_tutar: "4703",
    eksik_tutar: "-1380",
    fazla_sayisi: 2,
    eksik_sayisi: 1,
    birim_uyumsuz_sayisi: 1,
  },
};
const sarfSatiri = (kod: string, ad: string) => ({
  kod,
  ad,
  birim: "KG",
  tur: "0001-Hammadde",
  ortalama_fiyat: "12",
  recete_sarf: "275",
  stok_sarf: "160",
  fark: "-115",
  fark_tutar: "-1380",
  fark_orani: "-0.4182",
  urun_sayisi: 1,
  kartsiz: false,
  uretim_girisi: "0",
  satis_miktar: "0",
  sahit_miktar: "0",
  birim_uyumsuz: false,
  recete_birimleri: ["KG"],
});

describe("Sarf Farkı: en büyük farklar", () => {
  it("özet şerit, çift yönlü grafik; kaleme tıklayınca tablo süzülür, Tümü süzgeci kaldırır", async () => {
    const sorgular: string[] = [];
    let ozetIlk: string | null = null;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/sarf-farki/ozet`, ({ request }) => {
        ozetIlk = new URL(request.url).searchParams.get("ilk");
        return HttpResponse.json(SARF_OZET);
      }),
      http.get(`${T}/smm/donemler/:id/sarf-farki`, ({ request }) => {
        sorgular.push(new URL(request.url).searchParams.toString());
        return HttpResponse.json({
          donem,
          toplamlar: { recete_tutar: "3300", stok_tutar: "1920", fazla: "4703", eksik: "-1380" },
          turler: ["0001-Hammadde"],
          kayitlar: [sarfSatiri("HM-1", "Biber")],
          birim_uyumsuz_sayisi: 1,
        });
      }),
    );
    kurSayfa(<SmmSarfFarki />);
    const u = userEvent.setup();
    const bolum = await screen.findByRole("region", { name: "En büyük farklar" });
    expect(ozetIlk).toBe("20");
    expect(within(bolum).getByText("3.323 TL")).toBeInTheDocument();
    expect(within(bolum).getByText("4.703 TL")).toHaveClass("text-red-700");
    expect(within(bolum).getByText("1.380 TL")).toHaveClass("text-green-700");
    expect(within(bolum).getByText("Birim uyumsuz (sıralamada yok)")).toBeInTheDocument();
    expect(await within(bolum).findByRole("img", { name: /En büyük 3 sarf farkı/ })).toHaveAccessibleName(
      /Biber salamura: fazla 4.128 TL; Biber: eksik 1.380 TL/,
    );
    // mevcut tablo yerinde
    expect(within(screen.getByRole("table")).getByText("Biber")).toBeInTheDocument();
    expect(sorgular[0]).toBe("esik=1000");
    // listeden kaleme tıkla -> tablo o kodla, eşiksiz süzülür
    await u.click(within(bolum).getByText(/Liste olarak göster/));
    const liste = within(bolum).getByRole("list", { name: "En büyük farklar listesi" });
    const dugmeler = within(liste).getAllByRole("button");
    expect(dugmeler).toHaveLength(3);
    expect(dugmeler[0]).toHaveTextContent("01-1 · fazla harcanan · 20,0 %");
    expect(dugmeler[1]).toHaveTextContent("HM-1 · az harcanan");
    expect(dugmeler[1]).toHaveTextContent("-1.380 TL");
    await u.click(within(liste).getByRole("button", { name: /HM-1/ }));
    await waitFor(() => expect(sorgular.at(-1)).toBe("arama=HM-1"));
    expect(screen.getByLabelText("Malzeme ara")).toHaveValue("HM-1");
    expect(screen.getByLabelText("En az fark")).toHaveValue("0");
    expect(within(liste).getByRole("button", { name: /HM-1/ })).toHaveAttribute("aria-pressed", "true");
    // Tümü: arama temizlenir
    await u.click(within(bolum).getByRole("button", { name: "Tümü" }));
    await waitFor(() => expect(sorgular.at(-1)).toBe(""));
    expect(screen.getByLabelText("Malzeme ara")).toHaveValue("");
  });
});
