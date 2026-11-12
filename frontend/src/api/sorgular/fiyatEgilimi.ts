import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { FiyatEgilimiSonucu } from "../tipler";
import { anahtar } from "./anahtarlar";

/** Pencere seçenekleri (ay). */
export const EGILIM_AYLARI = [3, 6, 12, 24] as const;
export type EgilimAyi = (typeof EGILIM_AYLARI)[number];
export const VARSAYILAN_AY: EgilimAyi = 12;

export function egilimAyi(metin: string | null): EgilimAyi {
  const n = Number(metin);
  return (EGILIM_AYLARI as readonly number[]).includes(n) ? (n as EgilimAyi) : VARSAYILAN_AY;
}

/**
 * Fiyat eğilimi: son `ay` ayda her malzemenin ilk/son fiyatı, değişim ve yıllık yüzdesi, senaryo enflasyonuyla kıyas.
 * Yüzdeler sunucudan metin ("69.00" = %69) gelir. Hiçbir şey kaydedilmez.
 */
export function useFiyatEgilimi(senaryo: number | null | undefined, ay: number, yalnizAsan: boolean) {
  return useQuery({
    queryKey: anahtar.fiyatEgilimi(senaryo, ay, yalnizAsan),
    enabled: senaryo != null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: (): Promise<FiyatEgilimiSonucu> =>
      cagir(
        api.GET("/api/v1/analiz/fiyat-egilimi", {
          params: { query: { senaryo: senaryo as number, ay, yalniz_asan: yalnizAsan || undefined } },
        }),
      ) as Promise<FiyatEgilimiSonucu>,
  });
}
