import { useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { anahtar } from "./anahtarlar";

/** Bütçe (a) vs gerçekleşen (b): ürün başına A | B | fark | fark % (sunucu önbellekli). esik: yüzde metni ("5"). */
export function useKiyasListesi(a: number | null, b: number | null, esik: string) {
  return useQuery({
    queryKey: anahtar.kiyas(a, b, esik),
    enabled: a != null && b != null && a !== b,
    queryFn: () => cagir(api.GET("/api/v1/kiyas", { params: { query: { a: a as number, b: b as number, esik } } })),
  });
}

/** Tek ürün: reçete/gider/üretim/parametre yan yana ve sapma kaynağı ayrıştırması. */
export function useKiyasUrun(kod: string, a: number | null, b: number | null) {
  return useQuery({
    queryKey: anahtar.kiyasUrun(kod, a, b),
    enabled: !!kod && a != null && b != null && a !== b,
    queryFn: () => cagir(api.GET("/api/v1/kiyas/urun/{kod}", { params: { path: { kod }, query: { a: a as number, b: b as number } } })),
  });
}

/** Seçili senaryonun aynı sezondaki karşılığı (fiyat çalışması <-> gerçekleşen); yoksa `karsi: null`. */
export function useKarsiSenaryo(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.karsiSenaryo(senaryo),
    enabled: senaryo != null,
    queryFn: () => cagir(api.GET("/api/v1/kiyas/karsi", { params: { query: { senaryo: senaryo as number } } })),
  });
}
