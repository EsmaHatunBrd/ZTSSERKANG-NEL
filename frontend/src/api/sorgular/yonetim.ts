import { useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { YonetimOzeti } from "../tipler";
import { anahtar } from "./anahtarlar";

/**
 * Yönetim Özeti: seçili çalışmanın marj, maliyet yapısı, hedef altı, kur riski, teklif, veri kontrolü ve stok etkisi özeti tek yanıtta.
 * `surum` 0 ise sunucu önbelleğinden; "Yenile" ile artırılır ve `yenile=1` gönderilir (yeniden hesaplanır).
 */
export function useYonetimOzeti(senaryo: number | null | undefined, surum = 0) {
  return useQuery({
    queryKey: anahtar.yonetimOzeti(senaryo, surum),
    enabled: senaryo != null,
    staleTime: 60_000,
    queryFn: (): Promise<YonetimOzeti> =>
      cagir(
        api.GET("/api/v1/yonetim/ozet", { params: { query: { senaryo: senaryo as number, yenile: surum > 0 || undefined } } }),
      ) as Promise<YonetimOzeti>,
  });
}
