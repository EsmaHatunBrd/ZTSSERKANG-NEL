import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { OnemliMalzemelerSonucu } from "../tipler";
import { anahtar } from "./anahtarlar";

/** Eşik seçenekleri (yüzde). */
export const ONEM_ESIKLERI = [70, 80, 90] as const;
export type OnemEsigi = (typeof ONEM_ESIKLERI)[number];
export const VARSAYILAN_ESIK: OnemEsigi = 80;

export function onemEsigi(metin: string | null): OnemEsigi {
  const n = Number(metin);
  return (ONEM_ESIKLERI as readonly number[]).includes(n) ? (n as OnemEsigi) : VARSAYILAN_ESIK;
}

/** Sunucuya giden oran metni: 80 -> "0.8". */
const oran = (esik: number) => String(esik / 100);

/**
 * Önemli malzemeler (80/20): yıllık üretim adediyle ağırlıklı malzeme tutarı, pay ve kümülatif pay.
 * `pay_yuzde` / `kumulatif_yuzde` yüzde metnidir ("12.34" = %12,34). Hiçbir şey kaydedilmez.
 */
export function useOnemliMalzemeler(senaryo: number | null | undefined, esik: number) {
  return useQuery({
    queryKey: anahtar.onemliMalzemeler(senaryo, esik),
    enabled: senaryo != null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: (): Promise<OnemliMalzemelerSonucu> =>
      cagir(
        api.GET("/api/v1/analiz/onemli-malzemeler", { params: { query: { senaryo: senaryo as number, esik: oran(esik) } } }),
      ) as Promise<OnemliMalzemelerSonucu>,
  });
}

/** Önemli malzemeler Excel'i: ekrandaki eşikle. */
export function onemliMalzemelerXlsxAdresi(senaryo: number, esik: number): string {
  return `/api/v1/disa-aktar/onemli-malzemeler?senaryo=${senaryo}&esik=${oran(esik)}`;
}

/** Tüm ürünlerin maliyet kartları (Özet + ürün başına sayfa) tek Excel dosyasında. */
export function maliyetKartlariXlsxAdresi(senaryo: number): string {
  return `/api/v1/disa-aktar/maliyet-kartlari?senaryo=${senaryo}`;
}
