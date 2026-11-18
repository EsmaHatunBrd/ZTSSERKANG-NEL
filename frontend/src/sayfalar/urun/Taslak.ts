import Decimal from "decimal.js";
import type { HesapYaniti, ReceteSatiri, Sema, Urun, UrunGiris } from "@/api/tipler";
import { paraBicimle } from "@/yardimcilar/para";
import { parametreDegerGoster, parametreEtiketi } from "./parametreEtiketleri";
import { eslestir, fireYuzdeMetni, MALZEME, sayiGoster } from "./yardimci";

/**
 * Ürün ekranının tek taslağı: hücreye yazılan her değer burada durur; hesaba (override) ve tek "Kaydet"e buradan gider.
 * Sunucu değeriyle aynı olan alan taslakta tutulmaz (`taslakYamasi` düşürür).
 */
export const URUN_ALANLARI = ["hat", "taze_tursu_sinifi", "ambalaj_hacmi", "suzme_kg", "pazar", "marka"] as const;
export type UrunAlani = (typeof URUN_ALANLARI)[number];

export const HEDEF_ALANLARI = [
  "vardiya_uretim_adedi",
  "dolum_personel",
  "etiketleme_adedi",
  "etiket_personel",
  "mal_kabul_miktar_kg",
  "mal_kabul_fire",
] as const;
export type HedefAlani = (typeof HEDEF_ALANLARI)[number];

export type Kapsam = "urun" | "genel";

export interface SatirTaslagi {
  miktar?: string;
  /** Fire oranı (0.05 gibi, yüzde değil). */
  fire?: string;
  /** Metin = elle brüt; null = sunucudaki elle brütü kaldır (fire oranına dön). */
  brut_miktar_elle?: string | null;
  /** Metin = elle fiyat; null = listeye dön. */
  birim_fiyat_elle?: string | null;
}

/** Taslakta reçeteye eklenen satır (Kaydet'te yeni sürümün sonuna girer). */
export interface YeniSatir {
  malzeme_kodu: string;
  ad: string;
  /** API sayısı (noktalı). */
  miktar: string;
  birim: string | null;
  /** Fire oranı (0.05 gibi); boşsa fire kurallardan gelir. */
  fire?: string;
  /** Reçete ağacındaki seviye: reçetede seviye varsa üst düzey malzeme seviyesi (`yeniSatirSeviyesi`). */
  seviye?: number | null;
}

/** Gider satırında elle yazılabilen hücreler (Excel I/K/M/P). */
export const GIDER_ELLE_ALANLARI = ["miktar", "brut_miktar", "birim_fiyat", "tutar"] as const;
export type GiderElleAlani = (typeof GIDER_ELLE_ALANLARI)[number];
/** Gider kalemi kodu -> elle hücre -> değer. Taslakta `null` = "formüle dön" (kayıtlı elle değeri kaldır). */
export type GiderElle = Record<string, Partial<Record<GiderElleAlani, string | null>>>;

export interface Taslak {
  urun: Partial<Record<UrunAlani, string>>;
  /** Değerler metin; yalnız `pazarlama_yonetim_uygula` mantıksaldır. Mal kabul fire oran olarak (0.05). */
  hedef: Partial<Record<HedefAlani, string>> & { pazarlama_yonetim_uygula?: boolean };
  /** Reçete sırası -> satır taslağı. */
  satirlar: Record<number, SatirTaslagi>;
  /** kur.USD, enflasyon, faiz.TL, stok_ay.TL, vardiya_saati, maliyet_sapma ... (API değeri: oranlar 0.25 gibi). */
  parametreler: Record<string, string>;
  giderOranlari: Record<string, string>;
  /** Bu ürüne özel elle gider hücreleri (senaryo oranından bağımsız). */
  giderElle: GiderElle;
  /** Reçetenin sonuna eklenecek satırlar (sırayla; canlı hesapta sırası n+1, n+2 ...). */
  eklenen: YeniSatir[];
  /** Silinecek reçete satırlarının sıraları (artan). */
  silinen: number[];
}

/**
 * `onTaslak(yama)` imzası. Anahtar var ve değeri `undefined` ise o taslak girdisi silinir.
 * `null` yalnız `brut_miktar_elle` / `birim_fiyat_elle` için anlamlıdır ("elle değeri kaldır").
 */
export interface TaslakYamasi {
  urun?: Partial<Record<UrunAlani, string | undefined>>;
  hedef?: Partial<Record<HedefAlani, string | undefined>> & { pazarlama_yonetim_uygula?: boolean | undefined };
  satirlar?: Record<number, { [K in keyof SatirTaslagi]?: SatirTaslagi[K] | undefined }>;
  parametreler?: Record<string, string | undefined>;
  giderOranlari?: Record<string, string | undefined>;
  giderElle?: Record<string, Partial<Record<GiderElleAlani, string | null | undefined>>>;
  /** Eklenen satırların yeni tam listesi (yerine geçer). */
  eklenen?: YeniSatir[];
  /** Silinecek satır sıralarının yeni tam listesi (yerine geçer). */
  silinen?: number[];
}

export const taslakBos = (): Taslak => ({
  urun: {},
  hedef: {},
  satirlar: {},
  parametreler: {},
  giderOranlari: {},
  giderElle: {},
  eklenen: [],
  silinen: [],
});

const SATIR_ALANLARI = ["miktar", "fire", "brut_miktar_elle", "birim_fiyat_elle"] as const;

/** Taslaktaki değişen alan sayısı. */
export function taslakSayisi(t: Taslak): number {
  const satir = Object.values(t.satirlar).reduce((n, s) => n + SATIR_ALANLARI.filter((a) => s[a] !== undefined).length, 0);
  const hedef = Object.values(t.hedef).filter((v) => v !== undefined).length;
  const elle = Object.values(t.giderElle).reduce((n, h) => n + Object.keys(h).length, 0);
  const yapi = (t.eklenen?.length ?? 0) + (t.silinen?.length ?? 0);
  return (
    Object.keys(t.urun).length + hedef + satir + Object.keys(t.parametreler).length + Object.keys(t.giderOranlari).length + elle + yapi
  );
}

/**
 * Eklenen satırın seviyesi: reçetede seviye yoksa null; varsa üst düzey malzeme seviyesi (ürün satırı varsa onun bir altı,
 * yoksa reçetedeki en küçük seviye). Böylece yeni satır hiçbir ara mamulün altına girmez.
 */
export function yeniSatirSeviyesi(recete: ReceteSatiri[], urunKodu?: string): number | null {
  const seviyeli = recete.filter((r) => r.seviye != null);
  if (seviyeli.length === 0) return null;
  const urun = seviyeli.find((r) => r.dugum_tipi === "ara_mamul" && !!urunKodu && r.malzeme_kodu === urunKodu);
  if (urun) return (urun.seviye as number) + 1;
  return Math.min(...seviyeli.map((r) => r.seviye as number));
}

/** Taslaktaki eklenen satır -> API reçete satırı. */
export function yeniSatirGirisi(y: YeniSatir): Sema["ReceteSatirGiris"] {
  const g: Sema["ReceteSatirGiris"] = { malzeme_kodu: y.malzeme_kodu, ad: y.ad, miktar: y.miktar, birim: y.birim, dugum_tipi: "yaprak" };
  if (y.fire !== undefined) g.fire_override = y.fire;
  if (y.seviye != null) g.seviye = y.seviye;
  return g;
}

/** Sunucudaki (kayıtlı) değerler: taslakla karşılaştırma ve "eski" sütunu için. */
export interface SunucuDegerleri {
  recete: ReceteSatiri[];
  /** Taslaksız hesabın üretim bilgisi (kayıtlı ürün kartı + üretim hedefi). */
  uretim?: Sema["UretimBilgisiCikis"] | null;
  /** Kayıtlı ürün kartının markası (üretim bilgisinde yok; ürün kartından gelir). */
  marka?: string | null;
  /** Kayıtlı parametre değerleri (kur.USD ...). */
  parametreler?: Record<string, string>;
  giderOranlari?: Record<string, string>;
  /** Reçete sırası -> malzemenin para birimi (diyalogda elle fiyat satırlarında gösterilir). */
  dovizler?: Record<number, string>;
  /** Kayıtlı elle gider hücreleri (taslaksız hesabın `elle_alanlar`ından). */
  giderElle?: Record<string, Partial<Record<GiderElleAlani, string>>>;
}

/** Hesap satırındaki elle gider hücresinin değeri (elle değer hesabın o alanında aynen görünür). */
const satirAlani = (s: HesapYaniti["satirlar"][number], a: GiderElleAlani): string | null =>
  a === "miktar" ? s.miktar : a === "brut_miktar" ? s.brut_miktar : a === "birim_fiyat" ? s.birim_fiyat : s.tutar;

const GIDER_SKALER: Record<string, string> = {
  dolum_iscilik: "dolum_iscilik_sn",
  etiket_iscilik: "etiket_iscilik_sn",
  endirekt_iscilik: "endirekt_iscilik_sn",
  diger_gug: "diger_gug_sn",
};
const GIDER_SOZLUK: Record<string, { alan: string; urunAlani: "taze_tursu_sinifi" | "hat" }> = {
  mal_kabul_iscilik: { alan: "mal_kabul_iscilik_kg", urunAlani: "taze_tursu_sinifi" },
  mal_kabul_gug: { alan: "mal_kabul_gug_kg", urunAlani: "taze_tursu_sinifi" },
  elektrik: { alan: "elektrik_sn", urunAlani: "hat" },
};

/**
 * Gider hesap satırının (`kod`) `gider_oranlari` anahtarı; düzenlenemeyen kalem için null.
 * Sınıf/hat anahtarı casefold edilir (backend `anahtar()` ile aynı).
 */
export function giderAnahtari(
  kod: string | null | undefined,
  uretim: { taze_tursu_sinifi?: string | null; hat?: string | null } | null | undefined,
): string | null {
  if (!kod) return null;
  if (GIDER_SKALER[kod]) return GIDER_SKALER[kod];
  const s = GIDER_SOZLUK[kod];
  if (!s) return null;
  const alt = (uretim?.[s.urunAlani] ?? "").trim().toLowerCase();
  return alt ? `${s.alan}.${alt}` : null;
}

/** Kalıcı yazılan dört skaler gider anahtarının havuz kodu (`_sn` düşülmüş); diğerleri için null. */
export function giderHavuzKodu(anahtar: string): string | null {
  return Object.values(GIDER_SKALER).includes(anahtar) ? anahtar.replace(/_sn$/, "") : null;
}

/** Taslaksız hesap yanıtından sunucu değerlerini çıkarır. */
export function sunucuDegerleri(taban: HesapYaniti | null | undefined, recete: ReceteSatiri[]): SunucuDegerleri {
  const parametreler: Record<string, string> = {};
  const o = taban?.parametreler;
  if (o) {
    parametreler.enflasyon = o.enflasyon;
    parametreler.maliyet_sapma = o.maliyet_sapma;
    for (const [onek, grup] of [
      ["kur", o.kurlar],
      ["faiz", o.faiz],
      ["stok_ay", o.stok_ay],
    ] as const) {
      for (const [pb, v] of Object.entries(grup)) parametreler[`${onek}.${pb}`] = v;
    }
  }
  Object.assign(parametreler, taban?.kullanilan_parametreler ?? {});
  const saat = taban?.uretim?.vardiya_saati;
  if (parametreler.vardiya_saati === undefined && saat != null) parametreler.vardiya_saati = saat;
  const giderOranlari: Record<string, string> = {};
  const dovizler: Record<number, string> = {};
  const satirlar = taban?.satirlar ?? [];
  const giderElle: NonNullable<SunucuDegerleri["giderElle"]> = {};
  for (const s of satirlar) {
    if (s.grup === MALZEME || s.grup === "finansman") continue;
    const elle = (s.elle_alanlar ?? []) as GiderElleAlani[];
    if (s.kod && elle.length > 0) {
      giderElle[s.kod] = Object.fromEntries(elle.map((a) => [a, satirAlani(s, a) ?? "0"]));
    }
    // Birim fiyatı elle yazılmış satırda gösterilen değer senaryo oranı değildir.
    if (s.birim_fiyat == null || elle.includes("birim_fiyat")) continue;
    const a = giderAnahtari(s.kod, taban?.uretim);
    if (a) giderOranlari[a] = s.birim_fiyat;
  }
  eslestir(satirlar, recete).forEach((r, i) => {
    const d = satirlar[i].doviz;
    if (r && d) dovizler[r.sira] = d;
  });
  return { recete, uretim: taban?.uretim ?? null, parametreler, giderOranlari, dovizler, giderElle };
}

function ayni(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (a == null || b == null) return false;
  const sa = String(a);
  const sb = String(b);
  if (sa === sb) return true;
  try {
    return new Decimal(sa).eq(new Decimal(sb));
  } catch {
    return false;
  }
}

function alanBirlestir<T>(
  mevcut: Record<string, T>,
  yama: Record<string, T | undefined> | undefined,
  sunucu: (anahtar: string) => unknown,
): Record<string, T> {
  const sonuc = { ...mevcut };
  if (!yama) return sonuc;
  for (const [a, v] of Object.entries(yama)) {
    const s = sunucu(a);
    if (v === undefined || (s !== undefined && s !== null && ayni(v, s))) delete sonuc[a];
    else sonuc[a] = v;
  }
  return sonuc;
}

/** Yamayı taslağa uygular; sunucu değeriyle aynı olan alanlar düşer. Saf fonksiyon. */
export function taslakYamasi(t: Taslak, yama: TaslakYamasi, sunucu: SunucuDegerleri): Taslak {
  const u = sunucu.uretim as Record<string, unknown> | null | undefined;
  const sonraki: Taslak = {
    ...t,
    // Marka üretim bilgisinde değil, ürün kartında; boş marka kayıtlı "yok" ile aynıdır.
    urun: alanBirlestir(t.urun, yama.urun, (a) => (a === "marka" ? (sunucu.marka ?? "") : u?.[a])) as Taslak["urun"],
    hedef: alanBirlestir(
      t.hedef as Record<string, string | boolean>,
      yama.hedef as Record<string, string | boolean | undefined> | undefined,
      (a) => u?.[a],
    ) as Taslak["hedef"],
    parametreler: alanBirlestir(t.parametreler, yama.parametreler, (a) => sunucu.parametreler?.[a]),
    giderOranlari: alanBirlestir(t.giderOranlari, yama.giderOranlari, (a) => sunucu.giderOranlari?.[a]),
    satirlar: { ...t.satirlar },
    giderElle: { ...t.giderElle },
    eklenen: yama.eklenen ?? t.eklenen ?? [],
    silinen: yama.silinen ? [...new Set(yama.silinen)].sort((a, b) => a - b) : (t.silinen ?? []),
  };
  for (const [kod, hy] of Object.entries(yama.giderElle ?? {})) {
    const giris = { ...t.giderElle[kod] };
    for (const a of GIDER_ELLE_ALANLARI) {
      if (!(a in hy)) continue;
      const v = hy[a];
      // Kayıtlı değerle aynıysa (kayıtlı elle değer yokken formüle dönmek dahil) taslakta tutulmaz.
      if (v === undefined || ayni(v ?? null, sunucu.giderElle?.[kod]?.[a] ?? null)) delete giris[a];
      else giris[a] = v;
    }
    if (Object.keys(giris).length > 0) sonraki.giderElle[kod] = giris;
    else delete sonraki.giderElle[kod];
  }
  for (const [anahtar, sy] of Object.entries(yama.satirlar ?? {})) {
    const sira = Number(anahtar);
    const r = sunucu.recete.find((x) => x.sira === sira);
    const giris: SatirTaslagi = { ...t.satirlar[sira] };
    for (const a of SATIR_ALANLARI) {
      if (!(a in sy)) continue;
      const v = sy[a];
      const sunucuDeger = a === "fire" ? r?.fire_override : r?.[a];
      const elle = a === "brut_miktar_elle" || a === "birim_fiyat_elle";
      const dus =
        v === undefined || (r !== undefined && (elle ? ayni(v ?? null, sunucuDeger ?? null) : sunucuDeger != null && ayni(v, sunucuDeger)));
      if (dus) delete giris[a];
      else (giris as Record<string, unknown>)[a] = v;
    }
    if (SATIR_ALANLARI.some((a) => giris[a] !== undefined)) sonraki.satirlar[sira] = giris;
    else delete sonraki.satirlar[sira];
  }
  // Silinen satırın hücre taslakları anlamsızdır: düşer (geri alınınca hücre kayıtlı değerle başlar).
  for (const sira of sonraki.silinen) delete sonraki.satirlar[sira];
  // Hat/sınıf değişince eski hat/sınıfa bağlı gider oranı girdileri yetim kalır: etkin değere uymayanlar düşer.
  if (yama.urun && ("hat" in yama.urun || "taze_tursu_sinifi" in yama.urun)) {
    const kf = (v: unknown) =>
      String(v ?? "")
        .trim()
        .toLowerCase();
    const hat = kf(sonraki.urun.hat ?? u?.hat);
    const sinif = kf(sonraki.urun.taze_tursu_sinifi ?? u?.taze_tursu_sinifi);
    const gider = { ...sonraki.giderOranlari };
    for (const k of Object.keys(gider)) {
      const [alan, nokta, alt] = [k.split(".")[0], k.includes("."), k.slice(k.indexOf(".") + 1)];
      if (!nokta) continue;
      const beklenen = alan === "elektrik_sn" ? hat : alan.startsWith("mal_kabul_") ? sinif : null;
      if (beklenen !== null && kf(alt) !== beklenen) delete gider[k];
    }
    sonraki.giderOranlari = gider;
  }
  return sonraki;
}

/** Kayıtlı elle gider hücreleri + taslak (null = kaldır): sunucuya gidecek tam harita. */
export function etkinGiderElle(t: Taslak, sunucu: SunucuDegerleri["giderElle"]): Record<string, Sema["GiderElleGiris"]> {
  const out: Record<string, Sema["GiderElleGiris"]> = {};
  for (const kod of new Set([...Object.keys(sunucu ?? {}), ...Object.keys(t.giderElle)])) {
    const h: Sema["GiderElleGiris"] = {};
    for (const a of GIDER_ELLE_ALANLARI) {
      const taslakta = t.giderElle[kod] !== undefined && a in t.giderElle[kod];
      const v = taslakta ? t.giderElle[kod][a] : sunucu?.[kod]?.[a];
      if (v != null) h[a] = v;
    }
    if (Object.keys(h).length > 0) out[kod] = h;
  }
  return out;
}

const etkinElle = (r: ReceteSatiri | undefined, s: SatirTaslagi | undefined): string | null =>
  s && s.brut_miktar_elle !== undefined ? s.brut_miktar_elle : (r?.brut_miktar_elle ?? null);

/** Elle brüt olan satırda fire taslağı geçersizdir (backend 422): bu satırlar. */
export function dusenFireSatirlari(t: Taslak, recete: ReceteSatiri[]): ReceteSatiri[] {
  return recete.filter((r) => t.satirlar[r.sira]?.fire !== undefined && etkinElle(r, t.satirlar[r.sira]) !== null);
}

/** Hesaplama (hesapla/hesaplar) gövdesinin `override` alanı; taslak boşsa undefined. */
export function taslaktanOverride(
  t: Taslak,
  recete: ReceteSatiri[],
  sunucuGiderElle?: SunucuDegerleri["giderElle"],
): Sema["HesaplaGiris"]["override"] | undefined {
  if (taslakSayisi(t) === 0) return undefined;
  const fire: Record<string, string> = {};
  const satirlar: Record<string, Sema["SatirOverride"]> = {};
  const silinen = new Set(t.silinen ?? []);
  for (const [anahtar, s] of Object.entries(t.satirlar)) {
    const sira = Number(anahtar);
    if (silinen.has(sira)) continue;
    const r = recete.find((x) => x.sira === sira);
    if (s.fire !== undefined && etkinElle(r, s) === null) fire[anahtar] = s.fire;
    const o: Sema["SatirOverride"] = { elle_brut_kaldir: false, elle_fiyat_kaldir: false };
    if (s.miktar !== undefined) o.miktar = s.miktar;
    if (s.brut_miktar_elle === null) o.elle_brut_kaldir = true;
    else if (s.brut_miktar_elle !== undefined) o.brut_miktar_elle = s.brut_miktar_elle;
    if (s.birim_fiyat_elle === null) o.elle_fiyat_kaldir = true;
    else if (s.birim_fiyat_elle !== undefined) o.birim_fiyat_elle = s.birim_fiyat_elle;
    if (s.miktar !== undefined || s.brut_miktar_elle !== undefined || s.birim_fiyat_elle !== undefined) satirlar[anahtar] = o;
  }
  const override: NonNullable<Sema["HesaplaGiris"]["override"]> = {
    parametreler: { ...t.parametreler },
    fire,
    satirlar,
    gider_oranlari: { ...t.giderOranlari },
  };
  if (Object.keys(t.hedef).length > 0) override.uretim = { ...t.hedef };
  // Marka hesabı etkilemez ve geçici değişiklikte (override) yeri yok: yalnız Kaydet ile ürün kartına yazılır.
  const { marka: _marka, ...urunOverride } = t.urun;
  if (Object.keys(urunOverride).length > 0) override.urun = urunOverride as Sema["UrunOverride"];
  // Elle gider: sunucu kayıtlı haritanın TAMAMI yerine geçirir; bu yüzden kayıtlı + taslak birlikte gider.
  if (Object.keys(t.giderElle).length > 0) override.gider_elle = etkinGiderElle(t, sunucuGiderElle);
  // Reçete yapısı: silinen satırlar canlı hesaptan düşer, eklenenler sona girer (sunucu özgün sıraları korur).
  if (silinen.size > 0) override.silinen_satirlar = [...silinen].sort((a, b) => a - b);
  if ((t.eklenen ?? []).length > 0) override.eklenen_satirlar = t.eklenen.map(yeniSatirGirisi);
  return override;
}

/** Parametre anahtarının varsayılan yazım kapsamı. */
export function varsayilanKapsam(anahtar: string): Kapsam {
  if (anahtar.startsWith("faiz.") || anahtar.startsWith("stok_ay.") || anahtar === "vardiya_saati") return "urun";
  return "genel";
}

/** Kalıcı yazımı bu ekrandan yapılamayan gider oranları (mal kabul ve elektrik). */
export function giderKaliciMi(anahtar: string): boolean {
  return !(anahtar.startsWith("mal_kabul_") || anahtar.startsWith("elektrik_sn."));
}

export const GIDER_KALICI_DEGIL_NOTU = "kalıcı yazım Gider Dağıtım sayfasından";

export interface KaydetSecenekleri {
  senaryoId: number;
  tarih?: string;
  neden: string;
  hesabiKaydet: boolean;
  /** Kayıtlı ürün kartı (ürün alanı taslağı varsa gerekli). */
  urun?: Pick<Urun, "ad" | "ambalaj_hacmi" | "hat" | "taze_tursu_sinifi" | "suzme_kg" | "pazar" | "marka">;
  /** Kayıtlı üretim hedefi (hedef taslağı varsa gerekli). */
  hedef?: Pick<Sema["UretimBilgisiCikis"], HedefAlani | "pazarlama_yonetim_uygula"> | null;
  recete: ReceteSatiri[];
  /** parametre anahtarı -> kapsam; verilmeyen anahtar `varsayilanKapsam` alır. */
  kapsamSecimi?: Record<string, Kapsam>;
  /** Gider havuzları (GET /gider-havuzlari): havuz toplamı = oran x baz_miktar. */
  havuzlar?: HavuzBilgisi[];
  /** Kayıtlı elle gider hücreleri (`SunucuDegerleri.giderElle`); elle gider taslağı varsa tam harita için. */
  giderElle?: SunucuDegerleri["giderElle"];
}

export type HavuzBilgisi = Pick<Sema["GiderHavuzuCikis"], "kod" | "toplam_tutar" | "baz_miktar">;

/** POST /urunler/{kod}/kaydet gövdesi. Yalnız taslağı olan bölümler gönderilir. */
export function taslaktanKaydetGovdesi(t: Taslak, s: KaydetSecenekleri): Sema["TopluKaydetGiris"] {
  const govde: Sema["TopluKaydetGiris"] = {
    senaryo_id: s.senaryoId,
    neden: s.neden.trim(),
    hesabi_kaydet: s.hesabiKaydet,
  };
  if (s.tarih) govde.tarih = s.tarih;

  if (Object.keys(t.urun).length > 0) {
    if (!s.urun) throw new Error("Ürün kartı yüklenemedi");
    const urun: UrunGiris = {
      ad: s.urun.ad,
      ambalaj_hacmi: t.urun.ambalaj_hacmi ?? s.urun.ambalaj_hacmi,
      hat: t.urun.hat ?? s.urun.hat,
      taze_tursu_sinifi: t.urun.taze_tursu_sinifi ?? s.urun.taze_tursu_sinifi,
      suzme_kg: t.urun.suzme_kg ?? s.urun.suzme_kg,
      pazar: (t.urun.pazar ?? s.urun.pazar) as Sema["UrunGiris"]["pazar"],
    };
    // Marka: taslakta varsa o (boş -> null: sunucu addan türetir), yoksa kayıtlı değer korunur.
    if (t.urun.marka !== undefined) urun.marka = t.urun.marka.trim() || null;
    else if (s.urun.marka !== undefined) urun.marka = s.urun.marka;
    govde.urun = urun;
  }

  if (Object.keys(t.hedef).length > 0) {
    if (!s.hedef) throw new Error("Üretim hedefi yüklenemedi");
    const h = s.hedef;
    govde.uretim_hedefi = {
      vardiya_uretim_adedi: t.hedef.vardiya_uretim_adedi ?? h.vardiya_uretim_adedi,
      dolum_personel: t.hedef.dolum_personel ?? h.dolum_personel,
      etiketleme_adedi: t.hedef.etiketleme_adedi ?? h.etiketleme_adedi,
      etiket_personel: t.hedef.etiket_personel ?? h.etiket_personel,
      mal_kabul_miktar_kg: t.hedef.mal_kabul_miktar_kg ?? h.mal_kabul_miktar_kg,
      mal_kabul_fire: t.hedef.mal_kabul_fire ?? h.mal_kabul_fire,
      pazarlama_yonetim_uygula: t.hedef.pazarlama_yonetim_uygula ?? h.pazarlama_yonetim_uygula,
    };
  }

  const silinen = new Set(t.silinen ?? []);
  const eklenen = t.eklenen ?? [];
  if (Object.keys(t.satirlar).length > 0 || silinen.size > 0 || eklenen.length > 0) {
    const kalan = s.recete.filter((r) => !silinen.has(r.sira));
    if (kalan.length + eklenen.length === 0) throw new Error("Reçetede en az bir satır kalmalı");
    govde.recete = kalan.map((r) => {
      const x = t.satirlar[r.sira];
      const brut = etkinElle(r, x);
      const fiyat = x && x.birim_fiyat_elle !== undefined ? x.birim_fiyat_elle : r.birim_fiyat_elle;
      const satir: Sema["ReceteSatirGiris"] = {
        malzeme_kodu: r.malzeme_kodu,
        ad: r.ad,
        miktar: x?.miktar ?? r.miktar,
        birim: r.birim,
        dugum_tipi: r.dugum_tipi,
        // Elle brüt satırında fire yazılamaz (backend 422): fire düşer.
        fire_override: brut !== null ? null : (x?.fire ?? r.fire_override),
        brut_miktar_elle: brut,
        birim_fiyat_elle: fiyat,
      };
      if (r.seviye != null) satir.seviye = r.seviye;
      // Excel'den gelen elle Z/S ve para birimi yeni sürümde korunur.
      if (r.zs_elle) satir.zs_elle = r.zs_elle as Sema["ReceteSatirGiris"]["zs_elle"];
      if (r.para_birimi_elle) satir.para_birimi_elle = r.para_birimi_elle;
      return satir;
    });
    // Eklenen satırlar yeni sürümün sonuna girer (canlı hesaptaki sırayla aynı).
    govde.recete.push(...eklenen.map(yeniSatirGirisi));
  }

  const parametreler = Object.entries(t.parametreler);
  if (parametreler.length > 0) {
    govde.parametreler = parametreler.map(([anahtar, deger]) => ({
      anahtar,
      deger,
      kapsam: s.kapsamSecimi?.[anahtar] ?? varsayilanKapsam(anahtar),
    }));
  }
  // Ruling 7: dört skaler gider oranı havuz toplamı olarak kalıcı yazılır (toplam = oran x baz_miktar).
  const havuzlar: Sema["HavuzTutarGiris"][] = [];
  const yalnizHesap: Record<string, string> = {};
  for (const [anahtar, oran] of Object.entries(t.giderOranlari)) {
    const kod = giderHavuzKodu(anahtar);
    if (!kod) {
      yalnizHesap[anahtar] = oran;
      continue;
    }
    const h = s.havuzlar?.find((x) => x.kod === kod);
    if (!h || h.baz_miktar == null) throw new Error("Gider havuzu bilgisi yüklenemedi");
    havuzlar.push({ kod, toplam_tutar: new Decimal(oran).times(h.baz_miktar).toFixed() });
  }
  if (havuzlar.length > 0) govde.gider_havuzlari = havuzlar;
  if (Object.keys(t.giderElle).length > 0) govde.gider_elle = etkinGiderElle(t, s.giderElle);
  // Ruling 8: kalıcı yazılmayan gider oranları kaydedilen hesabın girdi anlık görüntüsüne override olarak girer.
  if (s.hesabiKaydet && Object.keys(yalnizHesap).length > 0)
    govde.override = { parametreler: {}, fire: {}, satirlar: {}, gider_oranlari: yalnizHesap };
  return govde;
}

export interface DegisiklikSatiri {
  /** Benzersiz anahtar: urun.hat, hedef.dolum_personel, satir.3.fire, parametre.kur.USD, gider.dolum_iscilik_sn */
  alan: string;
  etiket: string;
  eski: string;
  yeni: string;
  etki: "urun" | "senaryo";
  /** false: bu Kaydet ile kalıcı yazılmaz, yalnız hesapta kullanılır. */
  kalici: boolean;
  /** kalici=false ise açıklama. */
  not?: string;
  /** Parametre satırında anahtar (kapsam seçimi için). */
  parametre?: string;
  /** Ek ayrıntı (gider oranı için "havuz toplamı a → b TL"). */
  ek?: string;
}

const URUN_ADI: Record<UrunAlani, string> = {
  suzme_kg: "Süzme miktar (kg)",
  hat: "Üretim hattı",
  taze_tursu_sinifi: "Taze/Turşu sınıfı",
  ambalaj_hacmi: "Ambalaj (ml)",
  pazar: "Pazar",
  marka: "Marka",
};

const HEDEF_ADI: Record<HedefAlani | "pazarlama_yonetim_uygula", string> = {
  vardiya_uretim_adedi: "Vardiya üretim adedi",
  dolum_personel: "Dolum personel",
  etiketleme_adedi: "Etiketleme adedi",
  etiket_personel: "Etiket personel",
  mal_kabul_miktar_kg: "Mal kabul miktarı (kg)",
  mal_kabul_fire: "Mal kabul fire",
  pazarlama_yonetim_uygula: "Pazarlama/yönetim payı",
};

/** Gider kalemi kodu -> kısa Türkçe ad (elle hücre listelerinde). */
export const GIDER_KALEM_ADI: Record<string, string> = {
  mal_kabul_iscilik: "Mal kabul işçilik",
  dolum_iscilik: "Dolum işçilik",
  etiket_iscilik: "Etiket işçilik",
  endirekt_iscilik: "Endirekt işçilik",
  mal_kabul_gug: "Mal kabul GÜG",
  elektrik: "Elektrik",
  dogalgaz: "Doğalgaz",
  amortisman: "Amortisman",
  diger_gug: "Diğer GÜG",
  pazarlama: "Pazarlama",
  yonetim: "Yönetim",
};

const GIDER_HUCRE_ADI: Record<GiderElleAlani, string> = {
  miktar: "miktar",
  brut_miktar: "brüt",
  birim_fiyat: "birim fiyat",
  tutar: "tutar",
};

/** Gider oranı anahtarı -> Türkçe etiket. */
export function giderEtiketi(anahtar: string): string {
  const [taban, alt] = anahtar.split(".");
  const ad: Record<string, string> = {
    dolum_iscilik_sn: "Dolum işçilik ₺/sn",
    etiket_iscilik_sn: "Etiket işçilik ₺/sn",
    endirekt_iscilik_sn: "Endirekt işçilik ₺/sn",
    diger_gug_sn: "Diğer GÜG ₺/sn",
    mal_kabul_iscilik_kg: "Mal kabul işçilik ₺/kg",
    mal_kabul_gug_kg: "Mal kabul GÜG ₺/kg",
    elektrik_sn: "Elektrik ₺/sn",
  };
  const metin = ad[taban] ?? taban;
  return alt ? `${metin} — ${alt}` : metin;
}

/** Kayıtlı hesabın `girdi_snapshot.override` içeriği (yalnız satır/ürün/gider oranı), okunur etiketlerle. */
export function kayitliOverrideListesi(override: unknown): { etiket: string; deger: string }[] {
  if (!override || typeof override !== "object") return [];
  const o = override as Record<string, unknown>;
  const liste: { etiket: string; deger: string }[] = [];
  const kayit = (v: unknown): Record<string, unknown> => (v && typeof v === "object" ? (v as Record<string, unknown>) : {});
  for (const [a, v] of Object.entries(kayit(o.urun))) {
    if (v == null) continue;
    const say = a === "suzme_kg" || a === "ambalaj_hacmi";
    liste.push({ etiket: URUN_ADI[a as UrunAlani] ?? a, deger: say ? sayiGoster(String(v)) : String(v) });
  }
  for (const [sira, v] of Object.entries(kayit(o.satirlar)).sort((x, y) => Number(x[0]) - Number(y[0]))) {
    const s = kayit(v);
    const on = `Satır ${sira}`;
    if (s.miktar != null) liste.push({ etiket: `${on} · miktar`, deger: sayiGoster(String(s.miktar)) });
    if (s.brut_miktar_elle != null) liste.push({ etiket: `${on} · elle brüt`, deger: sayiGoster(String(s.brut_miktar_elle)) });
    if (s.elle_brut_kaldir === true) liste.push({ etiket: `${on} · elle brüt`, deger: "fire oranına döndü" });
    if (s.birim_fiyat_elle != null) liste.push({ etiket: `${on} · elle birim fiyat`, deger: sayiGoster(String(s.birim_fiyat_elle)) });
    if (s.elle_fiyat_kaldir === true) liste.push({ etiket: `${on} · elle birim fiyat`, deger: "listeye döndü" });
  }
  for (const [a, v] of Object.entries(kayit(o.gider_oranlari))) {
    liste.push({ etiket: giderEtiketi(a), deger: sayiGoster(String(v), 6) });
  }
  for (const [kod, h] of Object.entries(kayit(o.gider_elle))) {
    for (const [a, v] of Object.entries(kayit(h))) {
      if (v == null) continue;
      liste.push({
        etiket: `${GIDER_KALEM_ADI[kod] ?? kod} · elle ${GIDER_HUCRE_ADI[a as GiderElleAlani] ?? a}`,
        deger: sayiGoster(String(v), 6),
      });
    }
  }
  return liste;
}

const evetHayir = (b: unknown) => (b === null || b === undefined ? "—" : b ? "evet" : "hayır");
const yuzdeMetni = (v: unknown) => (v === null || v === undefined ? "—" : `${fireYuzdeMetni(String(v))} %`);

/** Kaydet diyaloğunun ve şeridin okuduğu değişiklik listesi. */
export function degisiklikListesi(t: Taslak, s: SunucuDegerleri, havuzlar?: HavuzBilgisi[]): DegisiklikSatiri[] {
  const liste: DegisiklikSatiri[] = [];
  const u = s.uretim as Record<string, unknown> | null | undefined;

  for (const a of URUN_ALANLARI) {
    const yeni = t.urun[a];
    if (yeni === undefined) continue;
    const say = a === "suzme_kg" || a === "ambalaj_hacmi";
    const eski = a === "marka" ? s.marka || null : u?.[a];
    liste.push({
      alan: `urun.${a}`,
      etiket: URUN_ADI[a],
      eski: eski == null ? "—" : say ? sayiGoster(String(eski)) : String(eski),
      yeni: say ? sayiGoster(yeni) : a === "marka" && yeni.trim() === "" ? "— (addan türetilir)" : yeni,
      etki: "urun",
      kalici: true,
    });
  }

  for (const a of [...HEDEF_ALANLARI, "pazarlama_yonetim_uygula"] as const) {
    const yeni = t.hedef[a];
    if (yeni === undefined) continue;
    const eski = u?.[a];
    const bicim = (v: unknown) =>
      a === "pazarlama_yonetim_uygula" ? evetHayir(v) : a === "mal_kabul_fire" ? yuzdeMetni(v) : v == null ? "—" : sayiGoster(String(v));
    liste.push({ alan: `hedef.${a}`, etiket: HEDEF_ADI[a], eski: bicim(eski), yeni: bicim(yeni), etki: "urun", kalici: true });
  }

  for (const anahtar of Object.keys(t.satirlar)
    .map(Number)
    .sort((a, b) => a - b)) {
    const x = t.satirlar[anahtar];
    const r = s.recete.find((y) => y.sira === anahtar);
    const on = `Satır ${anahtar}${r ? ` · ${r.ad}` : ""}`;
    const ekle = (alan: string, ad: string, eski: string, yeni: string) =>
      liste.push({ alan: `satir.${anahtar}.${alan}`, etiket: `${on} · ${ad}`, eski, yeni, etki: "urun", kalici: true });
    const doviz = s.dovizler?.[anahtar] ? ` ${s.dovizler[anahtar]}` : "";
    if (x.miktar !== undefined) ekle("miktar", "miktar", r ? sayiGoster(r.miktar) : "—", sayiGoster(x.miktar));
    if (x.fire !== undefined)
      ekle(
        "fire",
        "fire",
        r ? (r.fire_override != null ? yuzdeMetni(r.fire_override) : `${yuzdeMetni(r.fire_orani)} (kural)`) : "—",
        yuzdeMetni(x.fire),
      );
    if (x.brut_miktar_elle !== undefined)
      ekle(
        "brut_miktar_elle",
        "elle brüt",
        r?.brut_miktar_elle != null ? sayiGoster(r.brut_miktar_elle) : "fire oranı",
        x.brut_miktar_elle !== null ? sayiGoster(x.brut_miktar_elle) : "fire oranına döner",
      );
    if (x.birim_fiyat_elle !== undefined)
      ekle(
        "birim_fiyat_elle",
        "elle birim fiyat",
        r?.birim_fiyat_elle != null ? `${sayiGoster(r.birim_fiyat_elle)}${doviz}` : "liste fiyatı",
        x.birim_fiyat_elle !== null ? `${sayiGoster(x.birim_fiyat_elle)}${doviz}` : "listeye döner",
      );
  }

  for (const sira of t.silinen ?? []) {
    const r = s.recete.find((y) => y.sira === sira);
    liste.push({
      alan: `silinen.${sira}`,
      etiket: `Satır silindi: ${r ? `${r.malzeme_kodu} · ${r.ad}` : `Satır ${sira}`}`,
      eski: r ? `Satır ${sira} · ${sayiGoster(r.miktar)}${r.birim ? ` ${r.birim}` : ""}` : `Satır ${sira}`,
      yeni: "silinecek",
      etki: "urun",
      kalici: true,
    });
  }
  (t.eklenen ?? []).forEach((y, i) => {
    liste.push({
      alan: `eklenen.${i}`,
      etiket: `Satır eklendi: ${y.malzeme_kodu} · ${y.ad || "—"}`,
      eski: "—",
      yeni: `${sayiGoster(y.miktar)}${y.birim ? ` ${y.birim}` : ""} · fire ${y.fire !== undefined ? `${sayiGoster(fireYuzdeMetni(y.fire))} %` : "kuraldan"}`,
      etki: "urun",
      kalici: true,
    });
  });

  for (const [anahtar, yeni] of Object.entries(t.parametreler)) {
    const eski = s.parametreler?.[anahtar];
    liste.push({
      alan: `parametre.${anahtar}`,
      etiket: parametreEtiketi(anahtar),
      eski: eski === undefined ? "—" : parametreDegerGoster(anahtar, eski),
      yeni: parametreDegerGoster(anahtar, yeni),
      etki: varsayilanKapsam(anahtar) === "urun" ? "urun" : "senaryo",
      kalici: true,
      parametre: anahtar,
    });
  }

  for (const [kod, h] of Object.entries(t.giderElle)) {
    for (const a of GIDER_ELLE_ALANLARI) {
      if (!(a in h)) continue;
      const eski = s.giderElle?.[kod]?.[a];
      const yeni = h[a];
      liste.push({
        alan: `gider_elle.${kod}.${a}`,
        etiket: `${GIDER_KALEM_ADI[kod] ?? kod} · elle ${GIDER_HUCRE_ADI[a]}`,
        eski: eski != null ? sayiGoster(eski, 6) : "formül",
        yeni: yeni != null ? sayiGoster(yeni, 6) : "formüle döner",
        etki: "urun",
        kalici: true,
      });
    }
  }

  for (const [anahtar, yeni] of Object.entries(t.giderOranlari)) {
    const eski = s.giderOranlari?.[anahtar];
    const kalici = giderKaliciMi(anahtar);
    let ek: string | undefined;
    const kod = giderHavuzKodu(anahtar);
    const havuz = kod ? havuzlar?.find((h) => h.kod === kod) : undefined;
    if (havuz && havuz.baz_miktar != null) {
      const yeniToplam = new Decimal(yeni).times(havuz.baz_miktar).toFixed();
      ek = `havuz toplamı ${paraBicimle(havuz.toplam_tutar, "", 0)} → ${paraBicimle(yeniToplam, "", 0)} TL`;
    }
    liste.push({
      alan: `gider.${anahtar}`,
      etiket: giderEtiketi(anahtar),
      eski: eski === undefined ? "—" : sayiGoster(eski, 6),
      yeni: sayiGoster(yeni, 6),
      etki: kalici ? "senaryo" : "urun",
      kalici,
      ...(kalici ? {} : { not: GIDER_KALICI_DEGIL_NOTU }),
      ...(ek ? { ek } : {}),
    });
  }
  return liste;
}
