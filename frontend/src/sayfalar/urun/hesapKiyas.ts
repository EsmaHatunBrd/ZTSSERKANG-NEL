import Decimal from "decimal.js";
import type { HesapSatiri, HesapYaniti, KayitliHesapOzeti } from "@/api/tipler";
import { D } from "@/yardimcilar/para";

/** Kayıtlı hesap özetlerini en yeni üstte sıralar: önce hesap_tarihi, eşitse id azalan. */
export function hesaplariSirala<T extends Pick<KayitliHesapOzeti, "id" | "hesap_tarihi">>(kayitlar: readonly T[]): T[] {
  return [...kayitlar].sort((x, y) => (x.hesap_tarihi === y.hesap_tarihi ? y.id - x.id : x.hesap_tarihi < y.hesap_tarihi ? 1 : -1));
}

export interface KiyasSatiri {
  etiket: string;
  /** Para birimi ("TL", "USD", "EUR"); gösterim için. */
  birim: string;
  a: Decimal | null;
  b: Decimal | null;
  /** b - a; iki taraf da doluysa. */
  fark: Decimal | null;
  /** (b - a) / a; a sıfır veya boşsa null (sıfıra bölme yok). */
  farkYuzde: Decimal | null;
}

const metin = (x: string | null | undefined): Decimal | null => (x === null || x === undefined || x === "" ? null : D(x));

function satir(etiket: string, birim: string, aMetin: string | null | undefined, bMetin: string | null | undefined): KiyasSatiri {
  const a = metin(aMetin);
  const b = metin(bMetin);
  const fark = a !== null && b !== null ? b.minus(a) : null;
  const farkYuzde = fark !== null && a !== null && !a.isZero() ? fark.div(a) : null;
  return { etiket, birim, a, b, fark, farkYuzde };
}

/**
 * İki kayıtlı hesabın özet kıyası (A eski, B yeni). Yalnız iki tarafta da en az bir değeri olan satırlar döner
 * (örn. firesiz maliyet veya USD fiyatı hiç yoksa satır atlanır).
 */
export function kiyasla(a: HesapYaniti, b: HesapYaniti): KiyasSatiri[] {
  const adaylar: KiyasSatiri[] = [
    satir("Birim maliyet", "TL", a.toplamlar.maliyet_tl, b.toplamlar.maliyet_tl),
    satir("Firesiz maliyet", "TL", a.toplamlar_firesiz?.maliyet_tl, b.toplamlar_firesiz?.maliyet_tl),
    satir("Malzeme toplamı", "TL", a.toplamlar.malzeme, b.toplamlar.malzeme),
    satir("Gider toplamı", "TL", a.toplamlar.uretim_gideri, b.toplamlar.uretim_gideri),
    satir("Finansman", "TL", a.toplamlar.finansman_tl, b.toplamlar.finansman_tl),
    satir("Satış fiyatı", "TL", a.fiyatlar.satis_tl, b.fiyatlar.satis_tl),
    satir("Satış fiyatı (USD)", "USD", a.fiyatlar.satis_usd, b.fiyatlar.satis_usd),
    satir("Satış fiyatı (EUR)", "EUR", a.fiyatlar.satis_eur, b.fiyatlar.satis_eur),
  ];
  return adaylar.filter((s) => s.a !== null || s.b !== null);
}

export type ReceteKiyasDurumu = "ayni" | "degisti" | "yalniz_a" | "yalniz_b";

export interface ReceteKiyasSatiri {
  anahtar: string;
  kod: string;
  kalem: string;
  a: Decimal | null;
  b: Decimal | null;
  fark: Decimal | null;
  durum: ReceteKiyasDurumu;
}

/** Satır anahtarı: kod; aynı kod birden çok kez geçiyorsa sıra ile ayrılır. */
function anahtarla(satirlar: readonly HesapSatiri[]): Map<string, HesapSatiri> {
  const sonuc = new Map<string, HesapSatiri>();
  const sayac = new Map<string, number>();
  for (const s of satirlar) {
    if (!s.kod) continue;
    const n = (sayac.get(s.kod) ?? 0) + 1;
    sayac.set(s.kod, n);
    sonuc.set(n === 1 ? s.kod : `${s.kod}#${n}`, s);
  }
  return sonuc;
}

/** Reçete satırlarını koda göre eşler (fireli `tutar`); önce A'nın sırası, sonra yalnız B'de olanlar. */
export function receteKiyasla(a: readonly HesapSatiri[], b: readonly HesapSatiri[]): ReceteKiyasSatiri[] {
  const aMap = anahtarla(a);
  const bMap = anahtarla(b);
  const sonuc: ReceteKiyasSatiri[] = [];
  const ekle = (anahtar: string, sa: HesapSatiri | undefined, sb: HesapSatiri | undefined) => {
    const kaynak = (sa ?? sb) as HesapSatiri;
    const av = sa ? D(sa.tutar) : null;
    const bv = sb ? D(sb.tutar) : null;
    const fark = av !== null && bv !== null ? bv.minus(av) : null;
    const durum: ReceteKiyasDurumu = !sa ? "yalniz_b" : !sb ? "yalniz_a" : fark!.isZero() ? "ayni" : "degisti";
    sonuc.push({ anahtar, kod: kaynak.kod ?? "", kalem: kaynak.kalem, a: av, b: bv, fark, durum });
  };
  for (const [anahtar, sa] of aMap) ekle(anahtar, sa, bMap.get(anahtar));
  for (const [anahtar, sb] of bMap) if (!aMap.has(anahtar)) ekle(anahtar, undefined, sb);
  return sonuc;
}
