import { D } from "./para";

const SAYI = /^\d+([.,]\d+)?$/;
const SAYI_NEGATIF = /^-?\d+([.,]\d+)?$/;

/** Girilen metin geçerli bir ondalık sayı mı ("12,5" ve "12.5" kabul; binlik ayırıcı, üstel gösterim ve işaret red; "-" yalnız negatifIzin ile). */
export function sayiGecerli(s: string, negatifIzin = false): boolean {
  return (negatifIzin ? SAYI_NEGATIF : SAYI).test(s.trim());
}

/** API'ye gidecek düz metin (nokta ondalık, üstel gösterim yok). Geçersiz girdide null. */
export function sayiApi(s: string, negatifIzin = false): string | null {
  return sayiGecerli(s, negatifIzin) ? D(s.trim().replace(",", ".")).toFixed() : null;
}
