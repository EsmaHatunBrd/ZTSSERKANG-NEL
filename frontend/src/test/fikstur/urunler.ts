import type {
  Ambalaj,
  DashboardSatiri,
  FireKurali,
  GiderHavuzu,
  Malzeme,
  MalzemeGrubu,
  Recete,
  Senaryo,
  Teklif,
  Uyari,
} from "@/api/tipler";

export const senaryolar: Senaryo[] = [
  // Sezon adı backend kuralıyla uyumlu: YYYY-YYYY.
  { id: 1, sezon_ad: "2026-2027", tur: "fiyat_calismasi", ad: "Varsayılan", kilitli: false, urun_sayisi: 3 },
  { id: 2, sezon_ad: "2026-2027", tur: "gerceklesen", ad: "Gerçekleşen", kilitli: false, urun_sayisi: 0 },
];

/** Faz 5c: `POST /senaryolar/{id}/kopyala` yanıtındaki sayılar (uydurma). */
export const kopyalananSayilar = {
  recete: 67,
  fiyat: 661,
  parametre: 12,
  metin: 3,
  havuz: 8,
  ambalaj: 4,
  hedef: 67,
  kapasite: 5,
  fire: 2,
  sablon: 1,
};

/** Faz 5c: bu senaryoda reçetesi olmayan (çalışma dışı) ürün kodu; `GET recete` boş yapı döner. */
export const RECETESIZ_KOD = "YENI-001";

const bos: Omit<DashboardSatiri, "id" | "kod" | "ad" | "ambalaj_hacmi" | "hat" | "gecici_kod"> = {
  recete_maliyeti: null,
  gug: null,
  faaliyet: null,
  finans: null,
  gider_yuzdesi: null,
  maliyet_tl: null,
  maliyet_usd: null,
  maliyet_eur: null,
  satis_tl: null,
  uretim_adedi: null,
  maliyet_tl_firesiz: null,
  maliyet_usd_firesiz: null,
  uyari_sayisi: null,
  hata: null,
  stok_etkisi: false,
};

/** Dashboard: 3 ürün, biri hatalı. */
export const dashboardSatirlari: DashboardSatiri[] = [
  {
    id: 1,
    kod: "URUN-001",
    ad: "Salatalık Turşusu 720 ml",
    ambalaj_hacmi: "720",
    ambalaj_etiket: "720 ml",
    hat: "Cam Hattı",
    gecici_kod: false,
    recete_maliyeti: "12.237510",
    gug: "4.950000",
    faaliyet: "2.400000",
    finans: "0.912000",
    gider_yuzdesi: "0.192000",
    maliyet_tl: "38.130789",
    maliyet_usd: "0.654579",
    maliyet_eur: "0.601200",
    satis_tl: "45.756947",
    uretim_adedi: "12000",
    maliyet_tl_firesiz: "36.912345",
    maliyet_usd_firesiz: "0.633700",
    uyari_sayisi: 1,
    hata: null,
    gecen_yil_tl: "42.5",
    enflasyon_durumu: "altinda",
    enflasyon_fark_yuzde: "-6.691626825119851",
    hedef_adet_maliyet_tl: "36.100000",
    stok_etkisi: false,
  },
  {
    id: 2,
    kod: "URUN-002",
    ad: "Biber Turşusu 370 ml",
    ambalaj_hacmi: "0.54",
    ambalaj_etiket: "5 lt",
    hat: "Cam Hattı",
    gecici_kod: false,
    recete_maliyeti: "9.100000",
    gug: "3.800000",
    faaliyet: "1.900000",
    finans: "0.700000",
    gider_yuzdesi: "0.201000",
    maliyet_tl: "27.450000",
    maliyet_usd: "0.470000",
    maliyet_eur: "0.432000",
    satis_tl: "32.940000",
    uretim_adedi: "18000",
    maliyet_tl_firesiz: "26.700000",
    maliyet_usd_firesiz: "0.457000",
    uyari_sayisi: 0,
    hata: null,
    gecen_yil_tl: "30",
    enflasyon_durumu: "ustunde",
    enflasyon_fark_yuzde: "4.2",
    hedef_adet_maliyet_tl: "27.450000",
    stok_etkisi: false,
  },
  {
    ...bos,
    id: 3,
    kod: "SAYFA-Deneme",
    ad: "Deneme Ürünü",
    ambalaj_hacmi: "500",
    hat: "Pet Hattı",
    gecici_kod: true,
    hata: "Reçete bulunamadı",
  },
];

/** Faz 5c: yalnız `?tum=1` ile gelen çalışma dışı satır (bu senaryoda reçetesi yok). */
export const calismaDisiSatir: DashboardSatiri = {
  ...bos,
  id: 4,
  kod: RECETESIZ_KOD,
  ad: "Yeni Ürün 720 ml",
  ambalaj_hacmi: "720",
  hat: "Cam Hattı",
  gecici_kod: false,
  hata: "Reçete bulunamadı",
};

export const malzemeler: Malzeme[] = [
  {
    kod: "M-001",
    ad: "Pet Şişe 500 ml",
    tip: "ambalaj",
    birim: "adet",
    para_birimi: "TL",
    zs: "S",
    fiyat: "5.9",
    fiyatsiz: false,
    gecerlilik_basi: "2026-09-01",
    kaynak: "import",
    ilk_fiyat: "5.2",
    revize: true,
  },
  {
    kod: "M-002",
    ad: "Kapak 38 mm",
    tip: "ambalaj",
    birim: "adet",
    para_birimi: "TL",
    zs: "Z",
    fiyat: "0",
    fiyatsiz: true,
    ilk_fiyat: null,
    revize: false,
  },
  { kod: "M-099", ad: null, kart_yok: true },
];

export const recete: Recete = {
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
  ],
};

export const havuzlar: GiderHavuzu[] = [
  {
    kod: "uretim",
    ad: "Üretim Giderleri",
    toplam_tutar: "100000",
    baz_tipi: "saniye",
    baz_miktar: "3600",
    taban_tutar: null,
    carpanlar: [],
    anahtarlar: [
      { alt_kalem: "Dolum", pay_orani: "0.6", baz_miktar: "1" },
      { alt_kalem: "Etiketleme", pay_orani: "0.4", baz_miktar: "1" },
    ],
  },
];

export const ambalajlar: Ambalaj[] = [{ ad: "Cam 720", hacim: "720", uretim_adedi: "12000", katsayi: "1.2" }];

export const fireKurallari: FireKurali[] = [
  {
    id: 1,
    kapsam_tipi: "tip",
    kapsam_deger: "ambalaj",
    oran: "0.02",
    oncelik: 1,
    gecerlilik_basi: "2026-01-01",
    neden: "Sezon başı",
    olusturan: "sistem",
  },
];

export const malzemeGruplari: MalzemeGrubu[] = [{ id: 1, ad: "Hassas", malzeme_kodlari: ["M-001"] }];

export const uyarilar: Uyari[] = [{ urun_kodu: "URUN-001", uyari: "Kapak M-77 fiyat listesinde yok, 0 TL alındı" }];

export const teklifler: Teklif[] = [
  {
    id: 1,
    maliyet_hesabi_id: 5,
    tur_no: 1,
    kar_orani: "0.2",
    fiyat_tl: "45.756947",
    fiyat_usd: "0.785494",
    fiyat_eur: null,
    musteri: "Örnek Müşteri",
    durum: "taslak",
    notu: null,
    olusturan: "sistem",
  },
];
