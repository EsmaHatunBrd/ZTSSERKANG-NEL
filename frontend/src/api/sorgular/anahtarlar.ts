/**
 * queryKey sözleşmesi: [kaynak, ...ayırt edici parametreler].
 * Önek ile geçersiz kılma: invalidateQueries({ queryKey: ["urunler"] }) tüm ürün sorgularını yeniler.
 */
type Kimlik = number | null | undefined;

export const anahtar = {
  senaryolar: () => ["senaryolar"] as const,
  urunler: (senaryo: Kimlik, secenek?: object) => ["urunler", senaryo ?? null, secenek ?? {}] as const,
  urun: (kod: string, senaryo?: Kimlik) => ["urun", kod, senaryo ?? null] as const,
  recete: (kod: string, senaryo: Kimlik) => ["recete", kod, senaryo ?? null] as const,
  hesaplar: (kod: string, senaryo: Kimlik) => ["hesaplar", kod, senaryo ?? null] as const,
  hesap: (id: Kimlik) => ["hesap", id ?? null] as const,
  teklifler: (hesapId: Kimlik) => ["teklifler", hesapId ?? null] as const,
  /** `teklifler` önekini paylaşır: ["teklifler"] geçersiz kılması hem hesap hem senaryo listesini yeniler. */
  senaryoTeklifleri: (senaryo: Kimlik, secenek?: object) => ["teklifler", "senaryo", senaryo ?? null, secenek ?? {}] as const,
  malzemeler: (senaryo: Kimlik, secenek?: object) => ["malzemeler", senaryo ?? null, secenek ?? {}] as const,
  fiyatGecmisi: (kod: string, senaryo: Kimlik) => ["fiyat-gecmisi", kod, senaryo ?? null] as const,
  parametreler: (senaryo: Kimlik, tarih?: string) => ["parametreler", senaryo ?? null, tarih ?? null] as const,
  parametreTanimlari: () => ["parametre-tanimlari"] as const,
  parametreGecmisi: (a: string, senaryo: Kimlik) => ["parametre-gecmisi", a, senaryo ?? null] as const,
  giderHavuzlari: (senaryo: Kimlik) => ["gider-havuzlari", senaryo ?? null] as const,
  ambalajlar: (senaryo: Kimlik) => ["ambalajlar", senaryo ?? null] as const,
  fireKurallari: (senaryo: Kimlik) => ["fire-kurallari", senaryo ?? null] as const,
  malzemeGruplari: () => ["malzeme-gruplari"] as const,
  uyarilar: (senaryo: Kimlik) => ["uyarilar", senaryo ?? null] as const,
  kapasite: (senaryo: Kimlik, secenek?: object) => ["kapasite", senaryo ?? null, secenek ?? {}] as const,
  satisGecmisi: (secenek?: object) => ["satis-gecmisi", secenek ?? {}] as const,
  ambalajOzeti: (senaryo: Kimlik) => ["ambalaj-ozeti", senaryo ?? null] as const,
  /** `karsilastirma` öneki: aile değişince hepsi birlikte yenilenir. */
  karsilastirmaUrun: (kod: string, senaryo: Kimlik, tarih?: string, musteri?: string) =>
    ["karsilastirma", "urun", kod, senaryo ?? null, tarih ?? null, musteri ?? null] as const,
  aileler: (senaryo: Kimlik) => ["karsilastirma", "aileler", senaryo ?? null] as const,
  aileTrendi: (aile: string, senaryo: Kimlik, tarih?: string) => ["karsilastirma", "aile", aile, senaryo ?? null, tarih ?? null] as const,
  /** Bütçe vs Gerçekleşen: `kiyas` öneki. */
  kiyas: (a: Kimlik, b: Kimlik, esik: string) => ["kiyas", "liste", a ?? null, b ?? null, esik] as const,
  kiyasUrun: (kod: string, a: Kimlik, b: Kimlik) => ["kiyas", "urun", kod, a ?? null, b ?? null] as const,
  karsiSenaryo: (senaryo: Kimlik) => ["kiyas", "karsi", senaryo ?? null] as const,
  tutarlilik: (senaryo: Kimlik) => ["tutarlilik", senaryo ?? null] as const,
};
