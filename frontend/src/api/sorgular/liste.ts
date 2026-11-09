import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";
import { anahtar } from "./anahtarlar";
import { formVerisi } from "./aktar";

/** Liste çalışması: `bolen` verilirse kaydetmeden o bölenle hesaplanır (deneme). */
export function useListeCalismasi(senaryo: number | null | undefined, bolen?: string) {
  return useQuery({
    queryKey: anahtar.listeCalismasi(senaryo, bolen),
    enabled: senaryo != null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(api.GET("/api/v1/liste-calismasi", { params: { query: { senaryo: senaryo as number, bolen: bolen || undefined } } })),
  });
}

/** Liste verisi `liste-calismasi` önekiyle tutulur; her yazma onu yeniler. */
function yenile(qc: ReturnType<typeof useQueryClient>) {
  return qc.invalidateQueries({ queryKey: ["liste-calismasi"] });
}

export function useListeFiyatiKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (govde: Sema["ListeFiyatiGiris"]) => cagir(api.PUT("/api/v1/liste-fiyatlari", { body: govde })),
    onSuccess: () => yenile(qc),
  });
}

export function useListeFiyatiSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ urun_kodu, yil }: { urun_kodu: string; yil: number }) =>
      cagir(api.DELETE("/api/v1/liste-fiyatlari/{urun_kodu}/{yil}", { params: { path: { urun_kodu, yil } } })),
    onSuccess: () => yenile(qc),
  });
}

/** CSV/xlsx; herhangi bir satır hatalıysa 422 (`ApiHatasi.alanlar.hatalar`) ve hiçbir satır yazılmaz. */
export function useListeYukle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dosya: File) =>
      cagir(api.POST("/api/v1/liste-fiyatlari/yukle", { body: {} as never, bodySerializer: () => formVerisi({ dosya }) })),
    onSuccess: () => yenile(qc),
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
