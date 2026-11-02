import type { HesapYaniti, Recete } from "@/api/tipler";
import { hesapYaniti as temel } from "./hesapYaniti";

/** Ürün Maliyeti ekranı fikstürü (uydurma veri): 3 malzeme satırı + gider satırları. */
export const urunReceteleri: Recete = {
  id: 10,
  versiyon: 2,
  kaynak: "excel",
  satirlar: [
    {
      sira: 1,
      malzeme_kodu: "M-001",
      ad: "Pet Şişe 500 ml",
      miktar: "1",
      birim: "adet",
      dugum_tipi: "yaprak",
      fire_override: null,
      brut_miktar_elle: null,
      birim_fiyat_elle: null,
      fire_orani: "0.02",
      fire_kaynagi: "tip:ambalaj",
    },
    {
      sira: 2,
      malzeme_kodu: "M-050",
      ad: "Salamura Karışımı",
      miktar: "0.35",
      birim: "kg",
      dugum_tipi: "yaprak",
      fire_override: null,
      brut_miktar_elle: "0.38",
      birim_fiyat_elle: "12.4",
      fire_orani: "0.0857",
      fire_kaynagi: "elle",
    },
    {
      sira: 3,
      malzeme_kodu: "M-77",
      ad: "Kapak",
      miktar: "1",
      birim: "adet",
      dugum_tipi: "yaprak",
      fire_override: null,
      brut_miktar_elle: null,
      birim_fiyat_elle: null,
      fire_orani: "0.01",
      fire_kaynagi: "tip:ambalaj",
    },
  ],
};

export const urunHesapYaniti: HesapYaniti = {
  ...temel,
  satirlar: [
    { ...temel.satirlar[0], kod: "M-001" },
    { ...temel.satirlar[1], kod: "M-050" },
    {
      kalem: "Kapak",
      grup: "malzeme",
      kod: "M-77",
      miktar: "1",
      brut_miktar: "1.010101",
      birim_fiyat: "0",
      tutar: "0",
      tutar_firesiz: "0",
      maliyet_yuzdesi: "0",
      fiyat_yuzdesi: "0",
      fire_orani: "0.01",
      fire_kaynagi: "tip:ambalaj",
      miktar_kaynagi: "fire",
      fiyat_kaynagi: "yok",
      brut_miktar_elle: null,
      birim_fiyat_elle: null,
    },
    { ...temel.satirlar[2], kod: null },
  ],
};
