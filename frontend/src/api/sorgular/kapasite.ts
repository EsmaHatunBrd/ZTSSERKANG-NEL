import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";
import { anahtar } from "./anahtarlar";

export interface KapasiteListeSecenegi {
  sayfa?: number;
  boyut?: number;
}

/** Üretim Adetleri sayfası (Excel `Üretim Adetleri`): ürün başına kapasite/hedef. */
export function useKapasite(senaryo: number | null | undefined, secenek: KapasiteListeSecenegi = {}) {
  return useQuery({
    queryKey: anahtar.kapasite(senaryo, secenek),
    enabled: senaryo != null,
    // Yalnızca aynı senaryonun önceki verisi (sayfa değişimi) gösterilir.
    placeholderData: (onceki, oncekiSorgu) => (oncekiSorgu?.queryKey[1] === (senaryo ?? null) ? onceki : undefined),
    queryFn: () =>
      cagir(
        api.GET("/api/v1/uretim-kapasitesi", {
          params: { query: { senaryo: senaryo as number, sayfa: secenek.sayfa, boyut: secenek.boyut } },
        }),
      ),
  });
}

export interface KapasiteKaydetDegiskenleri {
  urunKodu: string;
  senaryo: number;
  govde: Sema["KapasiteGiris"];
}

/** Bir ürünün kapasite satırını yazar (neden zorunlu). Hedef üretim dashboard'daki üretim adedini etkileyebilir. */
export function useKapasiteKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ urunKodu, senaryo, govde }: KapasiteKaydetDegiskenleri) =>
      cagir(
        api.PUT("/api/v1/uretim-kapasitesi/{urun_kodu}", {
          params: { path: { urun_kodu: urunKodu }, query: { senaryo } },
          body: govde,
        }),
      ),
    onSuccess: () =>
      Promise.all(["kapasite", "ambalaj-ozeti", "urunler"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}
