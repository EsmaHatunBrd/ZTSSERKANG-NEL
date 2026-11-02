import type { GiderHavuzu } from "@/api/tipler";

/** Ürün kartı seçenekleri; ürün ekranındaki "Üretim bilgileri" bloğu ve Veri Girişi "Yeni ürün" kartı aynı listeyi kullanır. */
export const SINIFLAR = ["Taze/Taze", "Taze/Turşu", "Turşu/Turşu"] as const;
export const PAZARLAR = ["Yurtiçi", "Yurtdışı"] as const;
/** Hat adları hat bazlı gider havuzlarının anahtarlarından (alt kalem) gelir. */
export const HAT_HAVUZLARI = ["elektrik", "dogalgaz", "amortisman"];

/** Gider havuzlarından hat listesi (Türkçe sıralı, tekil); `ek` değerler (örn. ürünün mevcut hattı) listeye katılır. */
export function hatListesi(havuzlar: Pick<GiderHavuzu, "kod" | "anahtarlar">[] | undefined, ...ek: (string | undefined)[]): string[] {
  const kume = new Set<string>();
  for (const h of havuzlar ?? []) {
    if (HAT_HAVUZLARI.includes(h.kod)) for (const a of h.anahtarlar) kume.add(a.alt_kalem);
  }
  for (const e of ek) if (e) kume.add(e);
  return [...kume].filter(Boolean).sort((a, b) => a.localeCompare(b, "tr"));
}
