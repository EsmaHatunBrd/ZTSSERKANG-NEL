/** Teklif durumları (backend `DURUMLAR` ile aynı): [değer, etiket]. */
export const TEKLIF_DURUMLARI: [string, string][] = [
  ["taslak", "Taslak"],
  ["gonderildi", "Gönderildi"],
  ["kabul", "Kabul"],
  ["red", "Red"],
];

export const teklifDurumAdi = (d: string | null | undefined) =>
  d ? (TEKLIF_DURUMLARI.find(([v]) => v === d)?.[1] ?? d) : "—";

/** Onay gerektiren (sonuçlandıran) durumlar. */
export const ONAY_GEREKEN_DURUMLAR = new Set(["kabul", "red"]);
