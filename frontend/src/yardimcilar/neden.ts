/** Zorunlu "Neden" kutusu boşken onay düğmesinin altında/ipucunda görünen metin. */
export const NEDEN_IPUCU = "Neden girin";

/** Boş ya da yalnız boşluktan oluşan neden geçersizdir (onay düğmesi pasif kalır). */
export function nedenGecerli(neden: string): boolean {
  return neden.trim().length > 0;
}
