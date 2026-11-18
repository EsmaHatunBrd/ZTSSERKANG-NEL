import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { SatisGirisi } from "../tipler";
import { anahtar } from "./anahtarlar";
import { formVerisi } from "./aktar";

export interface SatisListeSecenegi {
  urun_kodu?: string;
  musteri?: string;
  bas?: string;
  son?: string;
  sayfa?: number;
  boyut?: number;
}

/** Satış geçmişi listesi (süzgeç ve sayfalama sunucuda). Boş süzgeç değerleri istekten çıkarılır. */
export function useSatisGecmisi(secenek: SatisListeSecenegi = {}) {
  const sorgu = Object.fromEntries(Object.entries(secenek).filter(([, v]) => v !== "" && v !== undefined)) as SatisListeSecenegi;
  return useQuery({
    queryKey: anahtar.satisGecmisi(sorgu),
    placeholderData: keepPreviousData,
    queryFn: () => cagir(api.GET("/api/v1/satis-gecmisi", { params: { query: sorgu } })),
  });
}

/** Satış geçmişi `satis-gecmisi` önekiyle tutulur; yazma işlemleri yalnız bu öneki yeniler. */
function yenile(qc: ReturnType<typeof useQueryClient>) {
  return qc.invalidateQueries({ queryKey: ["satis-gecmisi"] });
}

export function useSatisEkle() {
  const qc = useQueryClient();
  return useMutation({
    // `neden`: Değişiklik Günlüğüne yazılan zorunlu gerekçe (gövdede).
    mutationFn: (govde: SatisGirisi & { neden: string }) => cagir(api.POST("/api/v1/satis-gecmisi", { body: govde })),
    onSuccess: () => yenile(qc),
  });
}

/** CSV/xlsx yükler; herhangi bir satır hatalıysa 422 (`ApiHatasi.alanlar.hatalar`) ve hiçbir satır yazılmaz. */
export function useSatisYukle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dosya: File) =>
      cagir(api.POST("/api/v1/satis-gecmisi/yukle", { body: {} as never, bodySerializer: () => formVerisi({ dosya }) })),
    onSuccess: () => Promise.all([yenile(qc), qc.invalidateQueries({ queryKey: ["son-yukleme"] })]),
  });
}

/** Hiçbir şey yazmaz: eklenecek, sistemde zaten kayıtlı (atlanacak) ve hatalı satırlar + standart özet. */
export function useSatisOnizle() {
  return useMutation({
    mutationFn: (dosya: File) =>
      cagir(api.POST("/api/v1/satis-gecmisi/onizle", { body: {} as never, bodySerializer: () => formVerisi({ dosya }) })),
  });
}

export function useSatisSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, neden }: { id: number; neden: string }) =>
      cagir(api.DELETE("/api/v1/satis-gecmisi/{id}", { params: { path: { id }, query: { neden } } })),
    onSuccess: () => yenile(qc),
  });
}
