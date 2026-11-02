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
