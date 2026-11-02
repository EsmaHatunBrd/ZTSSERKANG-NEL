/** Ambalaj gösterimi: sunucunun türettiği etiket ("5 lt", "370 ml") varsa o; yoksa hacim (en çok 3 ondalık) ve BİRİMSİZ. */
export function ambalajMetni(etiket: string | null | undefined, hacim: string | null | undefined): string {
  if (etiket) return etiket;
  if (hacim === null || hacim === undefined || hacim === "") return "—";
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 3 }).format(hacim as unknown as number);
}
