import { http, HttpResponse } from "msw";
import type {
  AktarimOnizleGider,
  AktarimOnizleSatinAlma,
  AktarimOnizleUretim,
  AktarimUygulaGider,
  AktarimUygulaSatinAlma,
  AktarimUygulaUretim,
} from "@/api/tipler";

const T = "*/api/v1/aktarim";

/** Standart önizleme özeti (boş); testler gerektiğinde alanları ezer. */
export const bosOzet = { okunan: 0, yeni: 0, degisen: 0, ayni: 0, silinecek: 0, atlanan: 0, sorunlu: [], uyarilar: [] };

type Tip = "uretim-adetleri" | "satin-alma" | "gider-dagitim" | "stok-devri";

export interface AktarimIstegi {
  asama: "onizle" | "uygula";
  icerikTuru: string;
}

/** Ağdaki Veri Aktar uçları: istek başlığını `yakala`ya yazar, `yanit`ı döner. Alanlar için `formAlanlariniYakala` kullanılır. */
export function aktarimIsleyici(tip: Tip, asama: "onizle" | "uygula", yanit: unknown, yakala?: AktarimIstegi[]) {
  return http.post(`${T}/${tip}/${asama}`, ({ request }) => {
    yakala?.push({ asama, icerikTuru: request.headers.get("content-type") ?? "" });
    return HttpResponse.json(yanit as Record<string, unknown>);
  });
}

export function aktarimHatasi(tip: Tip, asama: "onizle" | "uygula", mesaj: string, alanlar: Record<string, unknown> = {}) {
  return http.post(`${T}/${tip}/${asama}`, () => HttpResponse.json({ hata: "dogrulama", mesaj, alanlar }, { status: 422 }));
}

export const uretimOnizle: AktarimOnizleUretim = {
  yeni: [{ urun_kodu: "T-1", urun_ad: "Ürün 1", alanlar: { hedef_uretim: "90", net_kapasite: "100" } }],
  degisen: [{ urun_kodu: "T-2", alan: "hedef_uretim", eski: "190", yeni: "195" }],
  ayni: 3,
  uyarilar: ["Üretim Adetleri: ürün kodu T-3 birden fazla satırda; ilk satır korundu"],
  ozet: bosOzet,
};
export const uretimUygula: AktarimUygulaUretim = { eklenen: 1, guncellenen: 1, uyarilar: uretimOnizle.uyarilar };

export const satinAlmaOnizle: AktarimOnizleSatinAlma = {
  yeni_malzeme: [{ kod: "MLZ-1", ad: "Kavanoz", tip: "0008-Ambalaj Malzeme", birim: "AD", para_birimi: "TL", zs: "S" }],
  kart_farki: [{ kod: "MLZ-2", alanlar: ["ad", "birim"] }],
  fiyat_yeni: [{ kod: "MLZ-1", yeni: "5.9", para: "TL" }],
  fiyat_degisen: [{ kod: "MLZ-3", eski: "2.5", yeni: "3", para: "USD", eski_para: "USD" }],
  ayni: 4,
  hatali: [],
  revize: [{ kod: "MLZ-3", ilk: "2.8", revize: "3" }],
  revize_sayisi: 1,
  ozet: bosOzet,
};
export const satinAlmaUygula: AktarimUygulaSatinAlma = {
  malzeme_eklenen: 1,
  kart_guncellenen: 0,
  fiyat_yazilan: 2,
  kodlar: ["MLZ-1", "MLZ-3"],
  ayni: 4,
  revize_yazilan: 1,
};

export const giderOnizle: AktarimOnizleGider = {
  havuz: [
    {
      kod: "dolum_iscilik",
      ad: "Dolum doğrudan işçilik",
      eski_toplam: "1000",
      yeni_toplam: "2000",
      eski_baz: "500",
      yeni_baz: "500",
      anahtar_farki: false,
      degisti: true,
      yeni_carpanlar: [],
    },
    {
      kod: "elektrik",
      ad: "Elektrik",
      eski_toplam: "900",
      yeni_toplam: "900",
      eski_baz: null,
      yeni_baz: null,
      anahtar_farki: false,
      degisti: false,
      yeni_carpanlar: [],
    },
  ],
  ambalaj: {
    eski_adet: 1,
    yeni_adet: 1,
    degisen: [{ ad: "Küçük", alan: "uretim_adedi", eski: "1000", yeni: "2000" }],
  },
  ozet: bosOzet,
};
export const giderUygula: AktarimUygulaGider = { havuz: 1, ambalaj: 1, havuz_kodlari: ["dolum_iscilik"] };
