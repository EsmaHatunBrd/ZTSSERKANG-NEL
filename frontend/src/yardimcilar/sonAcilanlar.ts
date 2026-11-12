/**
 * Favori ürünler ve son açılan ürünler (tarayıcı `localStorage`, senaryodan bağımsız; kodlar senaryolar arası aynı).
 * Depolama erişimi her yerde try/catch: gizli pencere, kapalı depolama vb. durumlarda boş liste döner.
 */
export const FAVORI_ANAHTARI = "fiyat-calismasi.favoriler";
export const SON_ACILAN_ANAHTARI = "fiyat-calismasi.son-acilanlar";
export const SON_ACILAN_SINIRI = 8;

function kodListesiOku(anahtar: string): string[] {
  try {
    const ham = localStorage.getItem(anahtar);
    if (!ham) return [];
    const v: unknown = JSON.parse(ham);
    return Array.isArray(v) ? v.filter((k): k is string => typeof k === "string" && k !== "") : [];
  } catch {
    return [];
  }
}

function kodListesiYaz(anahtar: string, kodlar: string[]): void {
  try {
    localStorage.setItem(anahtar, JSON.stringify(kodlar));
  } catch {
    /* localStorage kullanilamiyor */
  }
}

export function favorileriOku(): string[] {
  return kodListesiOku(FAVORI_ANAHTARI);
}

/** Kodu favorilere ekler ya da (zaten varsa) çıkarır; yeni listeyi döner. */
export function favoriDegistir(kod: string): string[] {
  const eski = favorileriOku();
  const yeni = eski.includes(kod) ? eski.filter((k) => k !== kod) : [...eski, kod];
  kodListesiYaz(FAVORI_ANAHTARI, yeni);
  return yeni;
}

export function sonAcilanlariOku(): string[] {
  return kodListesiOku(SON_ACILAN_ANAHTARI);
}

/** Ürün açılırken çağrılır: kodu listenin başına alır (tekrar yok), en çok `SON_ACILAN_SINIRI` tutar; yeni listeyi döner. */
export function sonAcilaniKaydet(kod: string): string[] {
  const yeni = [kod, ...sonAcilanlariOku().filter((k) => k !== kod)].slice(0, SON_ACILAN_SINIRI);
  kodListesiYaz(SON_ACILAN_ANAHTARI, yeni);
  return yeni;
}
