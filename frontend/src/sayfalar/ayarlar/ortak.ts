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
