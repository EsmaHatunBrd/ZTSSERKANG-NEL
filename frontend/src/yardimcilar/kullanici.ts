const ANAHTAR = "fiyat-calismasi.kullanici";

export function al(): string {
  try {
    return localStorage.getItem(ANAHTAR)?.trim() || "sistem";
  } catch {
    return "sistem";
  }
}

export function kaydet(ad: string): void {
  try {
    localStorage.setItem(ANAHTAR, ad.trim());
  } catch {
    /* localStorage kullanılamıyor */
  }
}

export const VARSAYILAN = "sistem";

/** Kayıtlı (boş olmayan) ad var mı? İlk açılışta ad diyaloğunu açmak için. */
export function kayitliMi(): boolean {
  try {
    return !!localStorage.getItem(ANAHTAR)?.trim();
  } catch {
    return false;
  }
}

/** Denetim izine yazılabilir bir ad mı (boş değil ve varsayılan "sistem" değil)? */
export function adGecerli(ad: string): boolean {
  const t = ad.trim();
  return t !== "" && t.toLocaleLowerCase("tr") !== VARSAYILAN;
}
