/** Reçete tablosunda Excel tarzı dikey gezinme için saf yardımcılar (DOM'suz, test edilebilir). */

/** Düzenlenebilir sütunlar (girdi `data-alan` değeri). */
export type GirdiAlani = "miktar" | "fire" | "brut" | "fiyat";

export interface GezinmeSatiri {
  /** Katlanmış ara mamulün altındaki satır görünmez: gezinmede atlanır. */
  gorunur: boolean;
  /** Alan -> o satırda odaklanabilir (var ve etkin) bir girdi var mı. Eksik alan = yok. */
  girdiler: Partial<Record<GirdiAlani, boolean>>;
}

/**
 * `satirIndeksi`nden `yon` yönünde (1 aşağı, -1 yukarı) aynı sütunda odaklanabilir ilk satırın indeksi;
 * gizli, girdisiz veya kapalı girdili satırlar atlanır. Yoksa null (kenarda kalınır).
 */
export function sonrakiHucre(satirIndeksi: number, alan: GirdiAlani, yon: 1 | -1, satirlar: GezinmeSatiri[]): number | null {
  for (let i = satirIndeksi + yon; i >= 0 && i < satirlar.length; i += yon) {
    const s = satirlar[i];
    if (s.gorunur && s.girdiler[alan]) return i;
  }
  return null;
}

/** Tuş olayını gezinme yönüne çevirir: Enter/↓ aşağı, Shift+Enter/↑ yukarı; diğerleri null (ezilmez). */
export function gezinmeYonu(e: { key: string; shiftKey: boolean }): 1 | -1 | null {
  if (e.key === "ArrowDown") return 1;
  if (e.key === "ArrowUp") return -1;
  if (e.key === "Enter") return e.shiftKey ? -1 : 1;
  return null;
}

/** Taslak alanı (SatirTaslagi anahtarı) <- girdi sütunu. */
export const TASLAK_ALANI = {
  miktar: "miktar",
  fire: "fire",
  brut: "brut_miktar_elle",
  fiyat: "birim_fiyat_elle",
} as const satisfies Record<GirdiAlani, string>;
