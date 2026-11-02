import type { Sema } from "@/api/tipler";

export type GunlukSatiri = Sema["GunlukSatiri"];
export type ArsivSezon = Sema["ArsivSezon"];
export type ArsivKaydi = Sema["ArsivKaydi"];
export type ArsivKiyasi = Sema["ArsivKiyasi"];

/** Uydurma günlük akışı: parametre (geri alınabilir), fire (değil), hesap, ürün kartı. */
export const gunlukSatirlari: GunlukSatiri[] = [
  {
    id: "parametre:12",
    zaman: "2026-10-22T08:00:00+00:00",
    kullanici: "Esma",
    tur: "parametre",
    baslik: "Parametre: kur.USD",
    urun_kodu: null,
    senaryo_id: 1,
    eski: "50",
    yeni: "55",
    neden: "Kur güncellemesi",
    geri_alinabilir: true,
    geri_al: {
      yol: "/api/v1/parametreler/kur.USD/degerler?senaryo=1",
      govde: { deger: "50", gecerlilik_basi: "2026-10-22", neden: "Geri alındı (günlük #12)", kapsam_tipi: "genel", kapsam_id: null },
    },
  },
  {
    id: "fire:4",
    zaman: "2026-10-22T07:30:00+00:00",
    kullanici: "Ayşe",
    tur: "fire",
    baslik: "Fire kuralı: malzeme KAV",
    urun_kodu: null,
    senaryo_id: 1,
    eski: "0.02",
    yeni: "0.03",
    neden: "Tedarikçi değişti",
    geri_alinabilir: false,
    geri_al: null,
  },
  {
    id: "hesap:5",
    zaman: "2026-10-21T10:00:00+00:00",
    kullanici: "Esma",
    tur: "hesap",
    baslik: "Hesap kaydedildi (2026-10-21)",
    urun_kodu: "URUN-001",
    senaryo_id: 1,
    eski: null,
    yeni: "maliyet 38.130789 TL",
    neden: null,
    geri_alinabilir: false,
    geri_al: null,
  },
  {
    id: "degisiklik:7",
    zaman: "2026-10-20T09:00:00+00:00",
    kullanici: "sistem",
    tur: "urun",
    baslik: "Ürün kartı güncellendi",
    urun_kodu: "URUN-001",
    senaryo_id: null,
    eski: "hat: Cam Hattı",
    yeni: "hat: Niko",
    neden: null,
    geri_alinabilir: false,
    geri_al: null,
  },
];

export const arsivSezonlari: ArsivSezon[] = [
  {
    id: 1,
    ad: "2026-27",
    baslangic: "2026-06-01",
    bitis: "2027-05-31",
    senaryolar: [
      {
        id: 1,
        tur: "fiyat_calismasi",
        ad: "Varsayılan",
        aciklama: null,
        olusturma_zamani: "2026-06-02T08:00:00+00:00",
        olusturan: "Esma",
        kilitli: false,
        kaynak_dosya: "berrak-2026.xlsx",
        urun_sayisi: 3,
        hesap_sayisi: 2,
        teklif_sayisi: 1,
      },
      {
        id: 2,
        tur: "gerceklesen",
        ad: "Gerçekleşen",
        aciklama: null,
        olusturma_zamani: "2026-07-01T08:00:00+00:00",
        olusturan: "Ayşe",
        kilitli: true,
        kaynak_dosya: null,
        urun_sayisi: 1,
        hesap_sayisi: 0,
        teklif_sayisi: 0,
      },
    ],
  },
  { id: 2, ad: "2025-26", baslangic: "2025-06-01", bitis: "2026-05-31", senaryolar: [] },
];

export const arsivKayitlari: ArsivKaydi[] = [
  {
    id: 11,
    urun_kodu: "URUN-001",
    urun_ad: "Salatalık Turşusu 720 ml",
    hesap_tarihi: "2026-10-21",
    olusturma_zamani: "2026-10-21T10:00:00+00:00",
    olusturan: "Esma",
    neden: "Kur revizyonu",
    maliyet_tl: "38.130789",
    satis_tl: "45.756947",
    teklif_sayisi: 1,
  },
  {
    id: 10,
    urun_kodu: "URUN-001",
    urun_ad: "Salatalık Turşusu 720 ml",
    hesap_tarihi: "2026-09-15",
    olusturma_zamani: "2026-09-15T10:00:00+00:00",
    olusturan: "Ayşe",
    neden: null,
    maliyet_tl: "36.5",
    satis_tl: "43.8",
    teklif_sayisi: 0,
  },
];

export const arsivKiyasi: ArsivKiyasi = {
  a: { id: 10, urun_kodu: "URUN-001", urun_ad: "Salatalık Turşusu 720 ml", senaryo_id: 1, hesap_tarihi: "2026-09-15", olusturma_zamani: null, olusturan: "Ayşe" },
  b: { id: 11, urun_kodu: "URUN-001", urun_ad: "Salatalık Turşusu 720 ml", senaryo_id: 1, hesap_tarihi: "2026-10-21", olusturma_zamani: null, olusturan: "Esma" },
  uyari: null,
  toplamlar: [
    { alan: "malzeme_toplami", etiket: "Malzeme toplamı", a: "10.5", b: "12.25", fark: "1.75" },
    { alan: "finansman_dahil_maliyet_tl", etiket: "Maliyet (TL, finansman dahil)", a: "36.5", b: "38.130789", fark: "1.630789" },
  ],
  fiyatlar: [{ alan: "satis_fiyati_tl", etiket: "Satış fiyatı (TL)", a: "43.8", b: "45.756947", fark: "1.956947" }],
  satirlar: [
    { malzeme_kodu: "KAV-720", ad: "Kavanoz 720 ml", a_tutar: "5", b_tutar: "5.5", fark: "0.5", durum: "ortak" },
    { malzeme_kodu: "KAP-01", ad: "Kapak", a_tutar: null, b_tutar: "1.5", fark: "1.5", durum: "sadece_b" },
  ],
};
