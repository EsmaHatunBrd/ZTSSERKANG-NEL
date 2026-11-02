import type { ExcelTamYaniti, KayitliHesapOzeti, SenaryoTeklifSatiri, Uyari } from "@/api/tipler";

export const importOzeti: ExcelTamYaniti = {
  senaryo_id: 7,
  malzeme: 412,
  fiyat: 398,
  havuz: 6,
  ambalaj: 14,
  urun: 85,
  recete: 640,
  parametre: 32,
  atlanan: ["Sayfa 'Notlar' atlandı", "Satır 17 boş"],
  uyarilar: ["Kapak M-77 fiyat listesinde yok"],
  kart_farklari: [{ tur: "urun", kod: "URUN-001", alanlar: ["hat", "suzme_kg"] }],
  yeniden_adlandirilan: [{ eski: "Cam 720", yeni: "Cam 720 ml" }],
  urun_parametre_farklari: [{ ad: "Salatalık Turşusu 720 ml", anahtar: "fire", deger: "0.02" }],
  kapasite: 71,
  mod: "yeni",
  satis_notu: 1,
  revize: 23,
};

/** "Mevcut senaryoyu tamamla" sonucu: yalnız eklenenler sayılır. */
export const tamamlaOzeti: ExcelTamYaniti = {
  senaryo_id: 1,
  malzeme: 0,
  fiyat: 0,
  havuz: 0,
  ambalaj: 0,
  urun: 0,
  recete: 0,
  parametre: 3,
  atlanan: [],
  uyarilar: [],
  kart_farklari: [],
  yeniden_adlandirilan: [],
  urun_parametre_farklari: [],
  kapasite: 71,
  mod: "tamamla",
  satis_notu: 1,
  revize: 0,
};

/** Ürün koduna göre kayıtlı hesaplar (URUN-003'ün hesabı yok). */
export const hesaplarUrunBazli: Record<string, KayitliHesapOzeti[]> = {
  "URUN-001": [
    { id: 5, hesap_tarihi: "2026-10-21", olusturan: "Eşma", maliyet_tl: "38.130789", satis_tl: "45.756947" },
    { id: 4, hesap_tarihi: "2026-10-10", olusturan: "Eşma", maliyet_tl: "37.000000", satis_tl: "44.400000" },
  ],
  "URUN-002": [{ id: 7, hesap_tarihi: "2026-10-15", olusturan: "Ali", maliyet_tl: "30.000000", satis_tl: "36.000000" }],
};

const sat = (o: Partial<SenaryoTeklifSatiri> & Pick<SenaryoTeklifSatiri, "teklif_id" | "hesap_id" | "tur_no">): SenaryoTeklifSatiri => ({
  urun_kodu: "URUN-001",
  urun_ad: "Salatalık Turşusu 720 ml",
  hesap_tarihi: "2026-10-21",
  kar_orani: "0.2",
  fiyat_tl: "45.756947",
  fiyat_usd: "0.785494",
  fiyat_eur: "0.720000",
  musteri: "Örnek Müşteri",
  durum: "taslak",
  olusturan: "Eşma",
  olusturma_zamani: "2026-10-21T09:00:00",
  ...o,
});

/** GET /teklifler (senaryo geneli) yanıtının tüm kayıtları; sunucu süzmesi MSW işleyicisinde yapılır. */
export const senaryoTeklifleri: SenaryoTeklifSatiri[] = [
  sat({ teklif_id: 1, hesap_id: 5, tur_no: 1 }),
  sat({ teklif_id: 2, hesap_id: 5, tur_no: 2, kar_orani: "0.25", fiyat_tl: "47.663684", durum: "gonderildi" }),
  sat({
    teklif_id: 3,
    hesap_id: 7,
    tur_no: 1,
    urun_kodu: "URUN-002",
    urun_ad: "Biber Turşusu 370 ml",
    hesap_tarihi: "2026-10-15",
    musteri: "Başka Müşteri",
    durum: "kabul",
    fiyat_tl: "36.000000",
    fiyat_usd: null,
    fiyat_eur: null,
    olusturan: "Ali",
  }),
];

export const cokluUyarilar: Uyari[] = [
  { urun_kodu: "URUN-001", uyari: "Kapak M-77 fiyat listesinde yok, 0 TL alındı" },
  { urun_kodu: "URUN-002", uyari: "Kapak M-77 fiyat listesinde yok, 0 TL alındı" },
  { urun_kodu: "URUN-002", uyari: "Kur bulunamadı: USD için varsayılan 1 kullanıldı" },
  { urun_kodu: "URUN-001", uyari: "Hat Cam Hattı için üretim adedi tanımsız" },
  { urun_kodu: "URUN-003", uyari: "Taze/turşu sınıfı tanımsız, 'tursu' varsayıldı" },
  { urun_kodu: "URUN-003", uyari: "Yurtdışı pazar gideri sıfır" },
  { urun_kodu: "URUN-001", uyari: "Vardiya sayısı tanımsız" },
  { urun_kodu: "URUN-003", uyari: "Beklenmeyen durum" },
];
