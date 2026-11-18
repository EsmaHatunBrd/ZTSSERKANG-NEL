import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { ListeCalismasi, ListeFiyatiGiris, ListePazari } from "../tipler";
import { anahtar } from "./anahtarlar";
import { formVerisi } from "./aktar";

export interface ListeDenemesi {
  /** Seçili pazar (yurtiçi/yurtdışı); her pazarın kendi böleni var. */
  pazar: ListePazari;
  /** Verilirse kaydetmeden o bölenle hesaplanır (deneme). */
  bolen?: string;
  /** Verilirse kaydetmeden o yuvarlama adımıyla hesaplanır (deneme). */
  yuvarlama?: string;
}

/** Liste çalışması (yalnız Berrak ürünleri): seçili pazarın bölenle ve yuvarlama adımıyla liste fiyatları. */
export function useListeCalismasi(senaryo: number | null | undefined, { pazar, bolen, yuvarlama }: ListeDenemesi) {
  return useQuery({
    queryKey: anahtar.listeCalismasi(senaryo, pazar, bolen, yuvarlama),
    enabled: senaryo != null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/liste-calismasi", {
          params: {
            query: {
              senaryo: senaryo as number,
              bolen: bolen || undefined,
              pazar,
              yuvarlama: yuvarlama || undefined,
            },
          },
        }),
      ) as Promise<ListeCalismasi>,
  });
}

/** Liste verisi `liste-calismasi` önekiyle tutulur; her yazma onu yeniler. */
function yenile(qc: ReturnType<typeof useQueryClient>) {
  return qc.invalidateQueries({ queryKey: ["liste-calismasi"] });
}

/** `senaryo`: kayda o çalışmanın bugünkü böleni yazılsın diye gönderilir (yoksa pazarın varsayılanı yazılır). */
export function useListeFiyatiKaydet(senaryo: number | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    // `neden`: Değişiklik Günlüğüne yazılan zorunlu gerekçe (gövdede; ekleme ve güncelleme aynı uç).
    mutationFn: (govde: ListeFiyatiGiris & { neden: string }) =>
      cagir(api.PUT("/api/v1/liste-fiyatlari", { params: { query: { senaryo: senaryo ?? undefined } }, body: govde })),
    onSuccess: () => yenile(qc),
  });
}

export function useListeFiyatiSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ urun_kodu, yil, pazar, neden }: { urun_kodu: string; yil: number; pazar: ListePazari; neden: string }) =>
      cagir(
        api.DELETE("/api/v1/liste-fiyatlari/{urun_kodu}/{yil}", {
          params: { path: { urun_kodu, yil }, query: { pazar, neden } },
        }),
      ),
    onSuccess: () => yenile(qc),
  });
}

/** CSV/xlsx; herhangi bir satır hatalıysa 422 (`ApiHatasi.alanlar.hatalar`) ve hiçbir satır yazılmaz. */
export function useListeYukle(senaryo: number | null | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dosya: File) =>
      cagir(
        api.POST("/api/v1/liste-fiyatlari/yukle", {
          params: { query: { senaryo: senaryo ?? undefined } },
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya }),
        }),
      ),
    onSuccess: () => Promise.all([yenile(qc), qc.invalidateQueries({ queryKey: ["son-yukleme"] })]),
  });
}

/** Hiçbir şey yazmaz: yeni / değişecek / aynı ve hatalı satırlar + standart özet. */
export function useListeOnizle() {
  return useMutation({
    mutationFn: (dosya: File) =>
      cagir(api.POST("/api/v1/liste-fiyatlari/onizle", { body: {} as never, bodySerializer: () => formVerisi({ dosya }) })),
  });
}

export function useListeOrnekUret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (senaryo: number) => cagir(api.POST("/api/v1/liste-calismasi/ornek", { params: { query: { senaryo } } })),
    onSuccess: () => yenile(qc),
  });
}

export function useListeOrnekSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => cagir(api.DELETE("/api/v1/liste-calismasi/ornek")),
    onSuccess: () => yenile(qc),
  });
}
