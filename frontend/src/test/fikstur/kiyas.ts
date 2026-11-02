import type { BgAlanlar, BgDeger, BgListe, BgSatir, BgUrun } from "@/api/tipler";

/** Faz 6 Bütçe vs Gerçekleşen fikstürleri (uydurma sayılar). A = #1 fiyat çalışması, B = #2 gerçekleşen. */
const dg = (a: string, b: string, fark: string, fark_yuzde: string | null): BgDeger => ({ a, b, fark, fark_yuzde });

const alanlar = (a: string, b: string, yuzde: string): BgAlanlar => ({
  recete_maliyeti: dg("20", "22", "2", "10"),
  gug: dg("5", "5", "0", "0"),
  faaliyet: dg("3", "3", "0", "0"),
  finans: dg("1", "1.1", "0.1", "10"),
  maliyet_tl: dg(a, b, String(Number(b) - Number(a)), yuzde),
  maliyet_usd: dg("0.6", "0.62", "0.02", "3.3"),
  satis_tl: dg("36", "37.2", "1.2", "3.3"),
  satis_usd: dg("0.72", "0.74", "0.02", "2.8"),
});

const satir = (kod: string, ad: string, ek: Partial<BgSatir>): BgSatir => ({
  kod,
  ad,
  hat: "Niko",
  ambalaj_hacmi: "370",
  gecici_kod: false,
  durum: "iki",
  hata: null,
  alanlar: null,
  sapma_yuzde: null,
  sapan: false,
  ...ek,
});

export const kiyasSatirlari: BgSatir[] = [
  satir("03.001", "Biberiye Turşu", { alanlar: alanlar("30", "33", "10"), sapma_yuzde: "10", sapan: true }),
  satir("03.002", "Acı Sos", { alanlar: alanlar("40", "41", "2.5"), sapma_yuzde: "2.5" }),
  satir("03.003", "Kornişon", { alanlar: alanlar("50", "45", "-10"), sapma_yuzde: "-10", sapan: true }),
  satir("03.004", "Yeni Ürün", { durum: "yalniz_a" }),
];

export const kiyasListesi: BgListe = {
  a: { id: 1, ad: "Varsayılan", tur: "fiyat_calismasi", sezon: "2026-2027" },
  b: { id: 2, ad: "Gerçekleşen", tur: "gerceklesen", sezon: "2026-2027" },
  esik: "5",
  tarih: "2026-10-27",
  satirlar: kiyasSatirlari,
  ozet: { karsilastirilan: 3, sapan: 2, yalniz_a: 1, yalniz_b: 0, hatali: 0, ortalama_sapma_yuzde: "0.8333" },
};

export const kiyasUrun: BgUrun = {
  kod: "03.001",
  ad: "Biberiye Turşu",
  a: kiyasListesi.a,
  b: kiyasListesi.b,
  tarih: "2026-10-27",
  alanlar: alanlar("30", "33", "10"),
  recete: [
    {
      kod: "20.10",
      kalem: "Cam Kavanoz",
      durum: "iki",
      a: { miktar: "1", fire: "0.02", brut_miktar: "1.0204", birim_fiyat: "5", tutar: "5.102" },
      b: { miktar: "1", fire: "0.02", brut_miktar: "1.0204", birim_fiyat: "6", tutar: "6.1224" },
      fark_tutar: "1.0204",
      degisen: ["birim_fiyat", "tutar"],
    },
    {
      kod: "20.99",
      kalem: "Yeni Etiket",
      durum: "yalniz_b",
      a: null,
      b: { miktar: "1", fire: "0", brut_miktar: "1", birim_fiyat: "0.5", tutar: "0.5" },
      fark_tutar: "0.5",
      degisen: [],
    },
  ],
  giderler: [{ kod: "elektrik", kalem: "Elektrik Giderleri", grup: "gug", ...dg("1", "1.2", "0.2", "20") }],
  uretim: [{ alan: "vardiya_uretim_adedi", etiket: "Vardiya üretim adedi", a: "60000", b: "54321", degisti: true }],
  parametreler: [
    { anahtar: "enflasyon", a: "0.25", b: "0", degisti: true },
    { anahtar: "kur.USD", a: "50", b: "52.85", degisti: true },
  ],
  ayristirma: [
    { kaynak: "fiyat", etiket: "Malzeme fiyatları", fark: "4" },
    { kaynak: "recete", etiket: "Reçete (miktar, fire, elle fiyat)", fark: "0.5" },
    { kaynak: "uretim", etiket: "Üretim bilgileri", fark: "0.3" },
    { kaynak: "gider", etiket: "Gider oranları", fark: "0.2" },
    { kaynak: "kur", etiket: "Döviz kurları", fark: "0" },
    { kaynak: "enflasyon", etiket: "Enflasyon", fark: "-2" },
    { kaynak: "diger", etiket: "Diğer parametreler (faiz, stok, kâr)", fark: "0" },
  ],
  toplam_fark: "3",
};
