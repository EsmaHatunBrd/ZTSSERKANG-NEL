import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Liste, Sema, Senaryo, SenaryoGuncelleGiris, SenaryoKopyaGiris } from "../tipler";
import { anahtar } from "./anahtarlar";

export function useSenaryolar() {
  return useQuery({
    queryKey: anahtar.senaryolar(),
    queryFn: () => cagir(api.GET("/api/v1/senaryolar")),
    select: (v) => v.kayitlar,
    staleTime: 60_000,
  });
}

/**
 * Yeni senaryoyu listeye hemen ekler, sonra listeyi sunucudan tazeler ve tazeleme bitene kadar bekler:
 * SenaryoSaglayici yeni kimliği listede bulamazsa seçimi ilk senaryoya düşürür; bu yüzden `sec()` bundan sonra çağrılmalıdır.
 */
function listeyeEkle(qc: QueryClient, yeni: Senaryo) {
  qc.setQueryData<Liste<Senaryo>>(anahtar.senaryolar(), (eski) =>
    eski && !eski.kayitlar.some((s) => s.id === yeni.id) ? { kayitlar: [...eski.kayitlar, yeni], toplam: eski.toplam + 1 } : eski,
  );
  return qc.invalidateQueries({ queryKey: anahtar.senaryolar() });
}

export function useSenaryoOlustur() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (govde: Sema["SenaryoGiris"]) => cagir(api.POST("/api/v1/senaryolar", { body: govde })),
    onSuccess: (yeni) => listeyeEkle(qc, yeni),
  });
}

export interface SenaryoKopyaDegiskenleri {
  kaynakId: number;
  govde: SenaryoKopyaGiris;
}

/** Faz 5c: `POST /senaryolar/{id}/kopyala` — seçilen tabloları yeni senaryoya tek işlemle kopyalar; yanıt sayıları taşır. */
export function useSenaryoKopyala() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kaynakId, govde }: SenaryoKopyaDegiskenleri) =>
      cagir(api.POST("/api/v1/senaryolar/{senaryo_id}/kopyala", { params: { path: { senaryo_id: kaynakId } }, body: govde })),
    onSuccess: (yeni) => listeyeEkle(qc, yeni),
  });
}

export interface SenaryoGuncelleDegiskenleri {
  id: number;
  govde: SenaryoGuncelleGiris;
}

/** Faz 5c: `PATCH /senaryolar/{id}` (ad / sezon / açıklama + neden); kilitli senaryoda 409. */
export function useSenaryoGuncelle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, govde }: SenaryoGuncelleDegiskenleri) =>
      cagir(api.PATCH("/api/v1/senaryolar/{senaryo_id}", { params: { path: { senaryo_id: id } }, body: govde })),
    onSuccess: () => qc.invalidateQueries({ queryKey: anahtar.senaryolar() }),
  });
}

/** Faz 5c: `DELETE /senaryolar/{id}` → 204; kayıtlı hesabı varsa ya da kilitliyse 409 (mesaj sunucudan). */
export function useSenaryoSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cagir(api.DELETE("/api/v1/senaryolar/{senaryo_id}", { params: { path: { senaryo_id: id } } })),
    onSuccess: (_v, id) => {
      qc.setQueryData<Liste<Senaryo>>(anahtar.senaryolar(), (eski) =>
        eski ? { kayitlar: eski.kayitlar.filter((s) => s.id !== id), toplam: Math.max(0, eski.toplam - 1) } : eski,
      );
      return qc.invalidateQueries({ queryKey: anahtar.senaryolar() });
    },
  });
}
