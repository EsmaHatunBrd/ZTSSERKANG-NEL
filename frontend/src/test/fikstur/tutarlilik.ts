import type { Tutarlilik, TutarlilikKontrolu } from "@/api/tipler";

const k = (kod: string, baslik: string, ek: Partial<TutarlilikKontrolu> = {}): TutarlilikKontrolu => ({
  kod,
  baslik,
  aciklama: `${baslik} açıklaması`,
  durum: "tamam",
  sayi: 0,
  cozum: { etiket: "Düzelt", yol: "/" },
  ogeler: [],
  ...ek,
});

/** Varsayılan: tüm kontroller tamam. */
export const tutarlilik: Tutarlilik = {
  senaryo_id: 1,
  kontroller: [k("hesaplanamayan", "Hesaplanamayan ürün"), k("fiyatsiz", "Fiyatı olmayan malzeme"), k("pay", "Gider payı %100 değil")],
  ozet: { hata: 0, dikkat: 0, tamam: 3 },
};

/** Sorunlu: bir hata, bir dikkat, bir tamam (sunucu sırası tamam önce: sayfa ağır olanı üste alır). */
export const tutarlilikSorunlu: Tutarlilik = {
  senaryo_id: 1,
  kontroller: [
    k("pay", "Gider payı %100 değil"),
    k("fiyatsiz", "Fiyatı olmayan malzeme", {
      durum: "dikkat",
      sayi: 2,
      cozum: { etiket: "Malzeme Fiyatları (yalnız fiyatsızlar)", yol: "/fiyatlar?fiyatsiz=1" },
      ogeler: [
        {
          etiket: "15.001 · Sarımsak",
          aciklama: "3 üründe kullanılıyor: 03.001, 03.002, 03.003",
          yol: "/fiyatlar?fiyatsiz=1&arama=15.001",
        },
        { etiket: "15.002 · Dereotu", aciklama: "1 üründe kullanılıyor: 03.001", yol: "/fiyatlar?fiyatsiz=1&arama=15.002" },
      ],
    }),
    k("hesaplanamayan", "Hesaplanamayan ürün", {
      durum: "hata",
      sayi: 1,
      cozum: { etiket: "Ürün Maliyeti", yol: "/urunler" },
      ogeler: [{ etiket: "03.009 · Kornişon", aciklama: "üretim bilgileri girilmemiş", yol: "/urunler/03.009" }],
    }),
  ],
  ozet: { hata: 1, dikkat: 1, tamam: 1 },
};
