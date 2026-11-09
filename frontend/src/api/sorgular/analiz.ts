import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { anahtar } from "./anahtarlar";
import type { HedefFiyatSonucu, KarlilikSonucu, KurRiskiSonucu } from "../tipler";

/** Varsayımlar oran metni ("0.1" = %10). Ürünler kaydetmeden yeniden hesaplanır (birkaç saniye sürebilir). */
export interface YaOlursaVarsayimi {
  kur: string;
  ambalaj: string;
  hammadde: string;
  adet: string;
}

export function useYaOlursa(senaryo: number | null | undefined, v: YaOlursaVarsayimi | null) {
  return useQuery({
    queryKey: anahtar.yaOlursa(senaryo, v ?? {}),
    enabled: senaryo != null && v !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: () =>
      cagir(api.GET("/api/v1/analiz/ya-olursa", { params: { query: { senaryo: senaryo as number, ...(v as YaOlursaVarsayimi) } } })),
  });
}

export function useZamEtkisi(senaryo: number | null | undefined, malzeme: string | null, oran: string | null) {
  return useQuery({
    queryKey: anahtar.zamEtkisi(senaryo, malzeme ?? "", oran ?? ""),
    enabled: senaryo != null && !!malzeme && oran !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/analiz/zam-etkisi", {
          params: { query: { senaryo: senaryo as number, malzeme: malzeme as string, oran: oran as string } },
        }),
      ),
  });
}

/** Kur riski: tüm kurlar `oran` kadar artarsa ("0.1" = %10) ürün başına ve yıllık etki. */
export function useKurRiski(senaryo: number | null | undefined, oran: string | null) {
  return useQuery({
    queryKey: ["analiz", "kur-riski", senaryo ?? null, oran ?? ""] as const,
    enabled: senaryo != null && oran !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: (): Promise<KurRiskiSonucu> =>
      cagir(
        api.GET("/api/v1/analiz/kur-riski", { params: { query: { senaryo: senaryo as number, oran: oran as string } } }),
      ) as Promise<KurRiskiSonucu>,
  });
}

/** Kârlılık haritası: ürünler yıllık adet (medyan) ve marj (hedef) eşiklerine göre dört bölgede. */
export function useKarlilik(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: ["analiz", "karlilik", senaryo ?? null] as const,
    enabled: senaryo != null,
    staleTime: 60_000,
    queryFn: (): Promise<KarlilikSonucu> =>
      cagir(api.GET("/api/v1/analiz/karlilik", { params: { query: { senaryo: senaryo as number } } })) as Promise<KarlilikSonucu>,
  });
}

/** Marjı koruyan fiyat: bugünkü maliyetle hedef marjı (`marj` "0.15" = %15; null ise sunucu marj eşiğini kullanır) tutturan fiyat. */
export function useHedefFiyat(senaryo: number | null | undefined, marj: string | null) {
  return useQuery({
    queryKey: ["analiz", "hedef-fiyat", senaryo ?? null, marj ?? ""] as const,
    enabled: senaryo != null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    queryFn: (): Promise<HedefFiyatSonucu> =>
      cagir(
        api.GET("/api/v1/analiz/hedef-fiyat", {
          params: { query: { senaryo: senaryo as number, ...(marj === null ? {} : { marj }) } },
        }),
      ) as Promise<HedefFiyatSonucu>,
  });
}
