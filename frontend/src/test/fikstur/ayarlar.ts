import type { GiderHavuzu, ParametreDegerleri, ParametreTanimi } from "@/api/tipler";

export const ayarTanimlari: ParametreTanimi[] = [
  { anahtar: "enflasyon", aciklama: "Yıllık enflasyon varsayımı", birim: "oran" },
  { anahtar: "satis_kar", aciklama: "Satış kâr oranı", birim: "oran" },
  { anahtar: "vardiya_saati", aciklama: "Vardiya saati", birim: "saat" },
  { anahtar: "kur.USD", aciklama: "USD/TL kuru", birim: "TL" },
  { anahtar: "faiz.TL", aciklama: "TL finansman faizi", birim: "oran" },
  { anahtar: "stok_ay.TL", aciklama: "Stok süresi", birim: "ay" },
  { anahtar: "teklif_kar.1", aciklama: "Teklif kârı (tur 1)", birim: "oran" },
  { anahtar: "dagitim_carpani.uretim", aciklama: "Üretim dağıtım çarpanı", birim: null },
];

export const ayarDegerleri: ParametreDegerleri = {
  enflasyon: "0.25",
  satis_kar: "0.2",
  vardiya_saati: "8",
  "kur.USD": "50",
  "faiz.TL": "0.40",
  "stok_ay.TL": "6",
  "teklif_kar.1": "0.2",
  "dagitim_carpani.uretim": "1.5",
};

/** Pay toplamı %100 olmayan havuz (0,3 + 0,267 = 0,567). */
export const bozukHavuz: GiderHavuzu = {
  kod: "uretim",
  ad: "Üretim Giderleri",
  toplam_tutar: "100000",
  baz_tipi: "saniye",
  baz_miktar: "3600",
  taban_tutar: null,
  carpanlar: [],
  anahtarlar: [
    { alt_kalem: "Dolum", pay_orani: "0.3", baz_miktar: "1" },
    { alt_kalem: "Etiketleme", pay_orani: "0.267", baz_miktar: "1" },
  ],
};
