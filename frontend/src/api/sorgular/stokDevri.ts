import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { StokDevriGiris } from "../tipler";
import { anahtar } from "./anahtarlar";

/** Stokta kalan (geçen yıldan devreden stok) uçları: ürün kaydı, çalışma listesi, yazma ve silme. */

/** Stok devri yazılınca maliyet/satış fiyatı değişebilir: ürün, hesap, dashboard, analiz, karşılaştırma ve liste sorguları yenilenir. */
function yenile(qc: QueryClient, kod: string) {
  return Promise.all(
    [["stok-devri"], ["urun", kod], ["urunler"], ["hesaplar", kod], ["uyarilar"], ["analiz"], ["karsilastirma"], ["liste-calismasi"]].map(
      (queryKey) => qc.invalidateQueries({ queryKey }),
    ),
  );
}

/** Ürünün bu çalışmadaki stokta kalan kaydı; kayıt yoksa alanlar null ve `stok_etkisi` false gelir. */
export function useStokDevri(kod: string, senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.stokDevri(kod, senaryo),
    enabled: !!kod && senaryo != null,
    queryFn: () => cagir(api.GET("/api/v1/urunler/{kod}/stok-devri", { params: { path: { kod }, query: { senaryo: senaryo as number } } })),
  });
}

/** Çalışmada stokta kalanı girilmiş ürünler (Veri Girişi kartındaki kısa liste). */
export function useStokDevriListesi(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.stokDevriListesi(senaryo),
    enabled: senaryo != null,
    queryFn: () => cagir(api.GET("/api/v1/stok-devri", { params: { query: { senaryo: senaryo as number } } })),
  });
}

export interface StokDevriKaydetDegiskenleri {
  kod: string;
  senaryo: number;
  govde: StokDevriGiris;
}

export function useStokDevriKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, senaryo, govde }: StokDevriKaydetDegiskenleri) =>
      cagir(api.PUT("/api/v1/urunler/{kod}/stok-devri", { params: { path: { kod }, query: { senaryo } }, body: govde })),
    onSuccess: (_v, { kod }) => yenile(qc, kod),
  });
}

export interface StokDevriSilDegiskenleri {
  kod: string;
  senaryo: number;
  neden: string;
}

export function useStokDevriSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ kod, senaryo, neden }: StokDevriSilDegiskenleri) => {
      await cagir(api.DELETE("/api/v1/urunler/{kod}/stok-devri", { params: { path: { kod }, query: { senaryo, neden } } }));
    },
    onSuccess: (_v, { kod }) => yenile(qc, kod),
  });
}
