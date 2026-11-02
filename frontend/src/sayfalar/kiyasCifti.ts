import type { Senaryo } from "@/api/tipler";

/** Varsayılan çift: seçili senaryo fiyat çalışmasıysa A = o, B = aynı sezonun gerçekleşeni; gerçekleşense tersi. */
export function varsayilanCift(secili: Senaryo | null, karsi: number | null): { a: number | null; b: number | null } {
  if (!secili) return { a: null, b: null };
  return secili.tur === "gerceklesen" ? { a: karsi, b: secili.id } : { a: secili.id, b: karsi };
}
