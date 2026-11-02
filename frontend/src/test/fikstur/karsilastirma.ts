import type { AileKarsilastirma, AileOzeti, UrunKarsilastirma } from "@/api/tipler";

/** Ürün karşılaştırma yanıtı (uydurma veri): TL ve USD geçen yıl, TL altında / USD altında, hedef adet 2 kat. */
export const urunKarsilastirma: UrunKarsilastirma = {
  gecen_yil: {
    donem_basi: "2025-06-01",
    donem_sonu: "2026-05-31",
    kayit_sayisi: 3,
    musteri_sayisi: 2,
    para_birimleri: {
      TL: { fiyat: "42.5", adet: "400", musteri_sayisi: 2, kayit_sayisi: 2 },
      USD: { fiyat: "0.5", adet: "50", musteri_sayisi: 1, kayit_sayisi: 1 },
    },
  },
  enflasyon_esigi: {
    TL: {
      gecen_yil: "42.5",
      yeni: "39.66",
      oran: "0.933083731748",
      fark_yuzde: "-6.691626825119",
      durum: "altinda",
    },
    USD: { gecen_yil: "0.5", yeni: "0.62", oran: "1.24", fark_yuzde: "24", durum: "ustunde" },
  },
  uretim_adedi_etkisi: {
    butce_adedi: "65000",
    hedef_adedi: "130000",
    oran: "2",
    maliyet_tl_butce: "17.0093",
    maliyet_usd_butce: "0.2919",
    maliyet_eur_butce: "0.2433",
    satis_tl_butce: "20.4112",
    satis_usd_butce: "0.3503",
    satis_eur_butce: "0.2919",
    maliyet_tl_hedef: "14.7456",
    maliyet_usd_hedef: "0.2531",
    maliyet_eur_hedef: "0.2109",
    satis_tl_hedef: "17.6947",
    satis_usd_hedef: "0.3037",
    satis_eur_hedef: "0.2531",
  },
  hesap_hatasi: null,
};

export const urunKarsilastirmaBos: UrunKarsilastirma = {
  gecen_yil: null,
  enflasyon_esigi: null,
  uretim_adedi_etkisi: null,
  hesap_hatasi: null,
};

export const aileler: AileOzeti[] = [
  {
    aile: "turşu",
    aile_ad: "turşu",
    urun_sayisi: 2,
    tek_uyeli: false,
    urunler: [
      { kod: "URUN-002", ad: "Biber Turşusu 370 ml", ambalaj_hacmi: "370", ambalaj_etiket: "370 ml" },
      { kod: "URUN-001", ad: "Salatalık Turşusu 720 ml", ambalaj_hacmi: "720", ambalaj_etiket: "720 ml" },
    ],
  },
  {
    aile: "deneme",
    aile_ad: "deneme",
    urun_sayisi: 1,
    tek_uyeli: true,
    urunler: [{ kod: "SAYFA-Deneme", ad: "Deneme Ürünü", ambalaj_hacmi: "500" }],
  },
];

/** "turşu" ailesi: üç ürün, biri hesap hatalı (grafik dışı). */
export const aileTrendi: AileKarsilastirma = {
  aile: "turşu",
  aile_ad: "turşu",
  satirlar: [
    {
      kod: "URUN-002",
      ad: "Biber Turşusu 370 ml",
      ambalaj_hacmi: "370",
      ambalaj_etiket: "370 ml",
      ambalaj_ml: "370",
      suzme_kg: "0.18",
      satis_tl: "32.94",
      satis_usd: "0.564",
      suzme_kg_fiyati: "183",
      kg_basi_satis_tl: "183",
      onceki_ile_fark_yuzde: null,
      hata: null,
    },
    {
      kod: "URUN-003",
      ad: "Turşu 500 ml",
      ambalaj_hacmi: "500",
      ambalaj_etiket: "500 ml",
      ambalaj_ml: "500",
      suzme_kg: "0.25",
      satis_tl: null,
      satis_usd: null,
      suzme_kg_fiyati: null,
      kg_basi_satis_tl: null,
      onceki_ile_fark_yuzde: null,
      hata: "üretim hedefi yok",
    },
    {
      kod: "URUN-001",
      ad: "Salatalık Turşusu 720 ml",
      ambalaj_hacmi: "5",
      ambalaj_etiket: "5 lt",
      ambalaj_ml: "5000",
      suzme_kg: "0.36",
      satis_tl: "45.756947",
      satis_usd: "0.785",
      suzme_kg_fiyati: "127.1",
      kg_basi_satis_tl: "127.1",
      onceki_ile_fark_yuzde: "-30.5",
      hata: null,
    },
  ],
};
