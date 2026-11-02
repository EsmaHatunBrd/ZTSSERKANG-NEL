import type { FiyatKaydi, ParametreDegerleri, ParametreKaydi, ParametreTanimi } from "@/api/tipler";

export const parametreDegerleri: ParametreDegerleri = {
  enflasyon: "0.25",
  "kur.USD": "50",
  "kur.EUR": "55",
  "faiz.TL": "0.40",
  "stok_ay.TL": "6",
};

export const parametreTanimlari: ParametreTanimi[] = [
  { anahtar: "enflasyon", aciklama: "Yıllık enflasyon varsayımı", birim: "oran" },
  { anahtar: "kur.USD", aciklama: "USD/TL kuru", birim: "TL" },
  { anahtar: "faiz.TL", aciklama: "TL finansman faizi", birim: "oran" },
  { anahtar: "stok_ay.TL", aciklama: "Stok süresi", birim: "ay" },
];

export const parametreGecmisi: ParametreKaydi[] = [
  {
    id: 2,
    deger: "50",
    gecerlilik_basi: "2026-10-01",
    neden: "Kur güncellemesi",
    kapsam_tipi: "genel",
    kapsam_id: null,
    olusturan: "Eşma",
    olusturma_zamani: "2026-10-01T08:00:00+00:00",
  },
  {
    id: 1,
    deger: "45",
    gecerlilik_basi: "2026-01-01",
    neden: "Sezon başı",
    kapsam_tipi: "genel",
    kapsam_id: null,
    olusturan: "sistem",
    olusturma_zamani: "2026-01-01T08:00:00+00:00",
  },
];

export const fiyatGecmisi: FiyatKaydi[] = [
  {
    id: 2,
    fiyat: "5.9",
    para_birimi: "TL",
    gecerlilik_basi: "2026-10-01",
    kaynak: "elle",
    neden: "Yeni liste",
    olusturan: "Eşma",
    olusturma_zamani: "2026-10-01T08:00:00+00:00",
  },
  {
    id: 1,
    fiyat: "5.2",
    para_birimi: "TL",
    gecerlilik_basi: "2026-01-01",
    kaynak: "import",
    neden: "Sezon başı",
    olusturan: "sistem",
    olusturma_zamani: "2026-01-01T08:00:00+00:00",
  },
];
