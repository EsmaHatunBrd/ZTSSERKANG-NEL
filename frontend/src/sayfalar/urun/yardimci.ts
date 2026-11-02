import type { HesapSatiri, HesapYaniti, ReceteSatiri } from "@/api/tipler";
import { apiMetni, D } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import type { SatirTaslagi } from "./Taslak";

export function etkinBrutElle(r: ReceteSatiri, t: SatirTaslagi | undefined): string | null {
  return t && "brut_miktar_elle" in t ? (t.brut_miktar_elle ?? null) : r.brut_miktar_elle;
}

export function etkinFiyatElle(r: ReceteSatiri, t: SatirTaslagi | undefined): string | null {
  return t && "birim_fiyat_elle" in t ? (t.birim_fiyat_elle ?? null) : r.birim_fiyat_elle;
}

export const MALZEME = "malzeme";

export function malzemeSatirlari(satirlar: HesapSatiri[]): HesapSatiri[] {
  return satirlar.filter((s) => s.grup === MALZEME);
}

/**
 * Hesap satırını reçete satırıyla eşler. `sira` (1 tabanlı malzeme satırı) doluysa doğrudan o reçete
 * satırıyla eşlenir; `sira` yoksa (eski anlık görüntüler) önce kod, kod da yoksa sıra kullanılır.
 * Eşleşmeyen satır için null döner (satır içi düzenleme kapalı kalır).
 */
export function eslestir(satirlar: HesapSatiri[], recete: ReceteSatiri[]): (ReceteSatiri | null)[] {
  const kullanilan = new Set<number>();
  const sirali = [...recete].sort((a, b) => a.sira - b.sira);
  const sonuc: (ReceteSatiri | null)[] = satirlar.map(() => null);
  // 0. geçiş: sunucunun verdiği sıra ile kesin eşleme.
  satirlar.forEach((s, i) => {
    if (s.grup !== MALZEME || s.sira == null) return;
    const aday = sirali.find((r) => !kullanilan.has(r.sira) && r.sira === s.sira);
    if (aday) {
      kullanilan.add(aday.sira);
      sonuc[i] = aday;
    }
  });
  // 1. geçiş: sırasız, kodlu satırlar kodla eşlenir.
  satirlar.forEach((s, i) => {
    if (s.grup !== MALZEME || s.sira != null || !s.kod) return;
    const aday = sirali.find((r) => !kullanilan.has(r.sira) && r.malzeme_kodu === s.kod);
    if (aday) {
      kullanilan.add(aday.sira);
      sonuc[i] = aday;
    }
  });
  // 2. geçiş: kodsuz satırlar kalan reçete satırlarına sırayla atanır (kodlu satırın yerini çalamaz).
  satirlar.forEach((s, i) => {
    if (s.grup !== MALZEME || s.sira != null || s.kod) return;
    const aday = sirali.find((r) => !kullanilan.has(r.sira));
    if (aday) {
      kullanilan.add(aday.sira);
      sonuc[i] = aday;
    }
  });
  return sonuc;
}

/** Fire oranı (0.02) -> girdi metni ("2"). */
export function fireYuzdeMetni(oran: string | null | undefined): string {
  if (oran === null || oran === undefined) return "";
  return D(oran).times(100).toDecimalPlaces(4).toFixed();
}

export const FIRE_ARALIK_MESAJI = "Fire % 0 ile 100 arasında olmalı (100 hariç)";

/** Fire yüzdesi girdisi geçerli mi (sayı ve 0 ≤ x < 100)? Geçerliyse null, değilse Türkçe iletiyi döndürür. */
export function fireYuzdeHatasi(yuzde: string): string | null {
  const v = sayiApi(yuzde);
  if (v === null) return "Fire % sayı olmalı";
  const x = D(v);
  return x.gte(0) && x.lt(100) ? null : FIRE_ARALIK_MESAJI;
}

/** Girdi metni ("5" veya "5,5") -> API oranı ("0.05"); geçersiz veya aralık dışıysa null. */
export function fireOraniMetni(yuzde: string): string | null {
  const v = fireYuzdeHatasi(yuzde) === null ? sayiApi(yuzde) : null;
  return v === null ? null : apiMetni(D(v).div(100));
}

export function sayiGoster(x: string | null | undefined, basamak = 4): string {
  if (x === null || x === undefined) return "—";
  return D(x).toDecimalPlaces(basamak).toFixed().replace(".", ",");
}

export const FIYAT_YOK = "fiyat listesinde yok";

export function fiyatsizMi(s: HesapSatiri, uyarilar: string[]): boolean {
  return uyarilar.some(
    (u) => u.includes(FIYAT_YOK) && ((s.kod != null && s.kod !== "" && u.includes(s.kod)) || u.includes(s.kalem)),
  );
}

/** Kurlar/finansman bloklarının okuduğu parametre görünümü (HesapYaniti.parametreler; eski anlık görüntülerde kullanilan_parametreler'den çıkarılır). */
export interface ParametreGorunumu {
  enflasyon: string | null;
  maliyet_sapma: string | null;
  kurlar: Record<string, string>;
  faiz: Record<string, string>;
  stok_ay: Record<string, string>;
}

export function parametreGorunumu(h: Pick<HesapYaniti, "parametreler" | "kullanilan_parametreler">): ParametreGorunumu {
  if (h.parametreler) {
    const p = h.parametreler;
    return { enflasyon: p.enflasyon, maliyet_sapma: p.maliyet_sapma, kurlar: p.kurlar, faiz: p.faiz, stok_ay: p.stok_ay };
  }
  const k = h.kullanilan_parametreler;
  const grup = (onek: string) =>
    Object.fromEntries(Object.entries(k).filter(([a]) => a.startsWith(onek)).map(([a, v]) => [a.slice(onek.length), v]));
  return {
    enflasyon: k.enflasyon ?? null,
    maliyet_sapma: k.maliyet_sapma ?? null,
    kurlar: grup("kur."),
    faiz: grup("faiz."),
    stok_ay: grup("stok_ay."),
  };
}

/** Oran metni (0.25) -> yüzde girdi metni ("25"). */
export const oranYuzdeMetni = fireYuzdeMetni;

/** Yüzde girdisi ("25" veya "-3,5") -> API oranı ("0.25"); geçersizse null. */
export function yuzdeOranMetni(yuzde: string, negatifIzin = false): string | null {
  const v = sayiApi(yuzde, negatifIzin);
  return v === null ? null : apiMetni(D(v).div(100));
}
