import type { Senaryo } from "@/api/tipler";

export const TUR_ADI: Record<string, string> = { fiyat_calismasi: "Fiyat çalışması", gerceklesen: "Gerçekleşen" };

/** Seçici ve diyaloglarda ortak senaryo etiketi: `#1 · 2026-27 · Varsayılan · Fiyat çalışması · Kilitli`. */
export function senaryoEtiketi(s: Senaryo): string {
  return `#${s.id} · ${s.sezon_ad} · ${s.ad} · ${TUR_ADI[s.tur] ?? s.tur}${s.kilitli ? " · Kilitli" : ""}`;
}
