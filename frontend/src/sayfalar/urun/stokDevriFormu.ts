import type { StokDevri, StokDevriGiris } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { fireYuzdeMetni, yuzdeOranMetni } from "./yardimci";

/**
 * Stokta kalan (geçen yıldan devreden stok) formu: ürün ekranındaki diyalog ve Veri Girişi kartı aynı alanları kullanır.
 * Enflasyon ekranda yüzde girilir (45 = %45), API'ye oran gider (0.45) — parametrelerdeki `enflasyon` ile aynı birim.
 */
export interface StokDevriFormDegeri {
  adet: string;
  birimMaliyet: string;
  /** Yüzde metni; boşsa çalışmanın enflasyon parametresi kullanılır. */
  enflasyon: string;
  /** Boşsa geçen yılın satış adedi kullanılır. */
  uretimAdedi: string;
  neden: string;
}

export type StokDevriHatalari = Partial<Record<keyof StokDevriFormDegeri, string>>;

export const BOS_STOK_FORMU: StokDevriFormDegeri = { adet: "", birimMaliyet: "", enflasyon: "", uretimAdedi: "", neden: "" };

/** Kayıtlı değerlerle form (kayıt yoksa boş); neden her seferinde yeniden yazılır. */
export function stokFormuDoldur(k: StokDevri | null | undefined): StokDevriFormDegeri {
  if (!k || k.adet === null) return BOS_STOK_FORMU;
  return {
    adet: k.adet ?? "",
    birimMaliyet: k.birim_maliyet ?? "",
    enflasyon: k.enflasyon !== null ? fireYuzdeMetni(k.enflasyon) : "",
    uretimAdedi: k.uretim_adedi ?? "",
    neden: "",
  };
}

const pozitif = (s: string) => {
  const v = sayiApi(s);
  return v !== null && D(v).gt(0);
};

/** Alan hataları (Türkçe); boş nesne = form geçerli. */
export function stokFormuHatalari(d: StokDevriFormDegeri): StokDevriHatalari {
  const h: StokDevriHatalari = {};
  if (!d.adet.trim()) h.adet = "Stok adedi zorunlu";
  else if (!pozitif(d.adet)) h.adet = "Stok adedi sıfırdan büyük bir sayı olmalı";
  if (!d.birimMaliyet.trim()) h.birimMaliyet = "Stok birim maliyeti zorunlu";
  else if (!pozitif(d.birimMaliyet)) h.birimMaliyet = "Birim maliyet sıfırdan büyük bir sayı olmalı";
  if (d.enflasyon.trim() && yuzdeOranMetni(d.enflasyon, true) === null)
    h.enflasyon = "Enflasyon geçerli bir yüzde olmalı (örn. 45 ya da 45,5)";
  if (d.uretimAdedi.trim() && !pozitif(d.uretimAdedi)) h.uretimAdedi = "Üretim adedi sıfırdan büyük bir sayı olmalı";
  if (!d.neden.trim()) h.neden = "Neden zorunlu";
  return h;
}

/** Geçerli formdan PUT gövdesi (önce `stokFormuHatalari` boş olmalı). */
export function stokDevriGovdesi(d: StokDevriFormDegeri): StokDevriGiris {
  return {
    adet: sayiApi(d.adet) as string,
    birim_maliyet: sayiApi(d.birimMaliyet) as string,
    enflasyon: d.enflasyon.trim() ? yuzdeOranMetni(d.enflasyon, true) : null,
    uretim_adedi: d.uretimAdedi.trim() ? sayiApi(d.uretimAdedi) : null,
    neden: d.neden.trim(),
  };
}

const adetMetni = (s: string) => paraBicimle(s, "", 0);

/** Kaydetmeden önce gösterilen tek cümlelik özet. */
export function stokFormuOzeti(d: StokDevriFormDegeri): string {
  const adet = sayiApi(d.adet);
  const bm = sayiApi(d.birimMaliyet);
  if (adet === null || bm === null) return "Özet: stok adedi ve birim maliyeti girin.";
  const enf = d.enflasyon.trim() ? `enflasyon %${d.enflasyon.trim()}` : "enflasyon çalışmanın parametresinden";
  const uretim =
    d.uretimAdedi.trim() && sayiApi(d.uretimAdedi) !== null
      ? `bu yıl ${adetMetni(sayiApi(d.uretimAdedi) as string)} adet üretim`
      : "üretim adedi geçen yıl satışından";
  return `Özet: ${adetMetni(adet)} adet × ${paraBicimle(bm, "TL", 2)} stok; ${enf}; ${uretim}. Ortalama maliyet kayıttan sonra hesaplanır.`;
}
