import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { anahtar } from "./anahtarlar";

/** Ürün karşılaştırma kartı: geçen yıl, enflasyon eşiği, hedef adet etkisi (sunucu hesabı; müşteri süzgeci isteğe bağlı). */
export function useUrunKarsilastirma(kod: string, senaryo: number | null | undefined, tarih?: string, musteri?: string) {
  return useQuery({
    queryKey: anahtar.karsilastirmaUrun(kod, senaryo, tarih || undefined, musteri || undefined),
    enabled: !!kod && senaryo != null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/karsilastirma/urun/{kod}", {
          params: {
            path: { kod },
            query: { senaryo: senaryo as number, tarih: tarih || undefined, musteri: musteri || undefined },
          },
        }),
      ),
  });
}

export function useAileler(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.aileler(senaryo),
    enabled: senaryo != null,
    queryFn: () =>
      cagir(api.GET("/api/v1/karsilastirma/aileler", { params: { query: { senaryo: senaryo as number } } })),
  });
}

/** Seçili ailenin ambalaj hacmine göre sıralı tablosu (aile adı yola kodlanarak gider). */
export function useAileTrendi(aile: string | null, senaryo: number | null | undefined, tarih?: string) {
  return useQuery({
    queryKey: anahtar.aileTrendi(aile ?? "", senaryo, tarih),
    enabled: !!aile && senaryo != null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/karsilastirma/aile/{aile}", {
          params: { path: { aile: aile as string }, query: { senaryo: senaryo as number, tarih } },
        }),
      ),
  });
}

/** Ürün ailesini elle atar; `aile: null` addan yeniden türetir. Ürün ve karşılaştırma sorgularını yeniler. */
export function useAileDegistir() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, aile }: { kod: string; aile: string | null }) =>
      cagir(api.PATCH("/api/v1/urunler/{kod}/aile", { params: { path: { kod } }, body: { aile } })),
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ["karsilastirma"] }),
        qc.invalidateQueries({ queryKey: ["urun"] }),
        qc.invalidateQueries({ queryKey: ["urunler"] }),
      ]),
  });
}
