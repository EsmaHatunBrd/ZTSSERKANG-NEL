import { D } from "@/yardimcilar/para";
import { sayiGecerli } from "@/yardimcilar/sayi";

export { sayiApi, sayiGecerli } from "@/yardimcilar/sayi";

const SAYI_NEGATIF = /^-?\d+([.,]\d+)?$/;

/** Sıfırdan büyük mü (katsayı gibi alanlar için). */
export function sayiPozitif(s: string): boolean {
  return sayiGecerli(s) && D(s.trim().replace(",", ".")).gt(0);
}

export const SAYI_MESAJI = "Geçerli bir sayı girin (negatif olamaz)";

/** Eksi değer girilebilen parametreler; diğerleri negatif kabul etmez. */
export const NEGATIF_OLABILIR = new Set(["enflasyon", "maliyet_sapma"]);

/** Hata iletisi: sayı değilse "Sayı olmalı", negatifse SAYI_MESAJI; geçerliyse null. */
export function sayiHatasi(s: string, negatifIzin = false): string | null {
  if (sayiGecerli(s, negatifIzin)) return null;
  return SAYI_NEGATIF.test(s.trim()) ? SAYI_MESAJI : "Sayı olmalı";
}

/** zod `superRefine` için: `z.string().superRefine(sayiKurali())`. */
export const sayiKurali =
  (negatifIzin = false) =>
  (x: string, ctx: { addIssue: (i: { code: "custom"; message: string }) => void }) => {
    const m = sayiHatasi(x, negatifIzin);
    if (m) ctx.addIssue({ code: "custom", message: m });
  };

/**
 * Açık/kapalı (0/1) parametrelerin birimi (ör. `satis_ortalama_maliyetten`). Bu birimdeki parametre "Açık / Kapalı" gösterilir ve
 * değer girişi yerine aç/kapa ile değiştirilir. Backend birim adı değişirse yalnız burası düzeltilir.
 */
export const EVET_HAYIR_BIRIMI = "evet_hayir";

/** 0/1 parametre değeri açık mı ("1", "1.0", "1.00" açık; boş/0 kapalı). */
export function acikMi(deger: string | null | undefined): boolean {
  if (deger === null || deger === undefined || deger.trim() === "") return false;
  return !D(deger.trim().replace(",", ".")).isZero();
}

/**
 * Parametre giriş birimi. Oran türü parametreler (enflasyon, satış kârı, teklif kârları, faizler, maliyet sapma, marj eşiği...)
 * kullanıcıdan YÜZDE olarak alınır ("25" = %25, API'ye 0.25 gider). Liste bölenleri oran birimli olsa da yüzde değildir (0,63 gibi
 * bölen); düz sayı olarak girilir. Sunucu sınırları: kur > 0, yüzde %0-%300 (enflasyon ve maliyet sapma -%100'den büyük),
 * vardiya saati 0-24, bölen 0 < b <= 1.
 */
export const BOLEN_ANAHTARLARI = new Set(["liste_bolen_yurtici", "liste_bolen_yurtdisi"]);

export function bolenMi(anahtar: string): boolean {
  return BOLEN_ANAHTARLARI.has(anahtar);
}

/** Kullanıcıya yüzde olarak gösterilen ve yüzde olarak girilen parametre mi? */
export function yuzdeMi(anahtar: string, birim: string | null | undefined): boolean {
  return birim === "oran" && !bolenMi(anahtar);
}

/** API oranı -> kutuya yazılacak yüzde ("0.25" -> "25", "0.075" -> "7,5"); boş/geçersizse "". */
export function oranYuzdeye(oran: string): string {
  const t = oran.trim().replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(t)) return "";
  return D(t).times(100).toDecimalPlaces(6).toFixed().replace(".", ",");
}

/** API yüzde metni (nokta ondalık, "25") -> API oranı ("0.25"). */
export function yuzdeOrana(yuzde: string): string {
  return D(yuzde).dividedBy(100).toFixed();
}

/** Açıklamadan okunur kısa ad: "Enflasyon öngörüsü (yalnız fiyat çalışması)" -> "Enflasyon öngörüsü"; yoksa anahtar. */
export function okunurAd(anahtar: string, aciklama: string | null | undefined): string {
  if (!aciklama) return anahtar;
  return aciklama.split(" (")[0].split(":")[0].trim() || anahtar;
}

/**
 * Kaydetmeden önce "Yine de kaydet" onayı gerektiren olağan dışı değer: oran %100'ün üstü ya da kur önceki geçerli değerden %50'den
 * fazla değişiyor. `yeni` ve `onceki` API metnidir (oran olarak). Olağansa null.
 */
export function olaganDisiNeden(
  anahtar: string,
  birim: string | null | undefined,
  yeni: string,
  onceki: string | undefined,
): string | null {
  if (yuzdeMi(anahtar, birim) && D(yeni).greaterThan(1)) {
    return "Değer %100'ün üstünde. Yüzde olarak girildiğinden emin olun (ör. %25 için 25 yazılır).";
  }
  if (anahtar.startsWith("kur.") && onceki !== undefined && /^-?\d+(\.\d+)?$/.test(onceki.trim()) && D(onceki).greaterThan(0)) {
    const degisim = D(yeni).dividedBy(D(onceki)).minus(1).abs();
    if (degisim.greaterThan(0.5)) return "Kur önceki değerden %50'den fazla değişiyor.";
  }
  return null;
}
