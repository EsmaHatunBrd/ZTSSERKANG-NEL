import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";
import { anahtar } from "./anahtarlar";

export interface MalzemeListeSecenegi {
  fiyatsiz?: boolean;
  sayfa?: number;
  boyut?: number;
  tarih?: string;
  /** Yalnız geçerli fiyatı ilk bütçeden farklı olanlar (S.ALMA BF I revizesi ya da sonraki değişiklik). */
  revize?: boolean;
  /** Kod ya da adda geçen metin; sunucu sayfalamadan önce süzer (aranan malzeme başka sayfada olsa da bulunur). */
  arama?: string;
}

/** Malzeme listesi sorgusunun seçenekleri: hook ile anlık `fetchQuery` (ör. kod doğrulama) aynı önbelleği paylaşır. */
export function malzemelerSorgusu(senaryo: number | null | undefined, secenek: MalzemeListeSecenegi = {}) {
  return {
    queryKey: anahtar.malzemeler(senaryo, secenek),
    queryFn: () =>
      cagir(
        api.GET("/api/v1/malzemeler", {
          params: {
            query: {
              senaryo: senaryo as number,
              fiyatsiz: secenek.fiyatsiz,
              sayfa: secenek.sayfa,
              boyut: secenek.boyut,
              tarih: secenek.tarih,
              revize: secenek.revize,
              arama: secenek.arama || undefined,
            },
          },
        }),
      ),
  };
}

export function useMalzemeler(senaryo: number | null | undefined, secenek: MalzemeListeSecenegi = {}) {
  return useQuery({
    ...malzemelerSorgusu(senaryo, secenek),
    enabled: senaryo != null,
    // Yalnızca aynı senaryonun önceki verisi (sayfa değişimi) gösterilir; senaryo değişince başka senaryonun tutarları asla.
    placeholderData: (onceki, oncekiSorgu) => (oncekiSorgu?.queryKey[1] === (senaryo ?? null) ? onceki : undefined),
  });
}

export function useFiyatGecmisi(kod: string | null | undefined, senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.fiyatGecmisi(kod ?? "", senaryo),
    enabled: !!kod && senaryo != null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/malzemeler/{kod}/fiyatlar", {
          params: { path: { kod: kod as string }, query: { senaryo: senaryo as number } },
        }),
      ),
  });
}

/** Yeni fiyat kaydı (geri al da bu yoldan yeni kayıt olarak eklenir; güncelleme yok). */
export function useFiyatEkle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, senaryo, govde }: { kod: string; senaryo: number; govde: Sema["FiyatGiris"] }) =>
      cagir(
        api.POST("/api/v1/malzemeler/{kod}/fiyatlar", {
          params: { path: { kod }, query: { senaryo } },
          body: govde,
        }),
      ),
    onSuccess: () =>
      Promise.all(["malzemeler", "fiyat-gecmisi", "urunler", "uyarilar", "recete"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}

export function useMalzemeGruplari() {
  return useQuery({
    queryKey: anahtar.malzemeGruplari(),
    queryFn: () => cagir(api.GET("/api/v1/malzeme-gruplari")),
  });
}

export function useGrupOlustur() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (govde: Sema["GrupGiris"]) => cagir(api.POST("/api/v1/malzeme-gruplari", { body: govde })),
    onSuccess: () =>
      Promise.all([qc.invalidateQueries({ queryKey: anahtar.malzemeGruplari() }), qc.invalidateQueries({ queryKey: ["recete"] })]),
  });
}
