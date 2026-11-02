import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";

export type ArsivSezonu = Sema["ArsivSezon"];
export type ArsivSenaryosu = Sema["ArsivSenaryo"];
export type ArsivKaydi = Sema["ArsivKaydi"];
export type ArsivKiyasi = Sema["ArsivKiyasi"];

export const arsivAnahtar = {
  agac: () => ["arsiv", "agac"] as const,
  kayitlar: (senaryo: number | null | undefined, sayfa: number, urunKodu: string) =>
    ["arsiv", "kayitlar", senaryo ?? null, sayfa, urunKodu] as const,
  kiyas: (a: number | null, b: number | null) => ["arsiv", "kiyas", a, b] as const,
};

export function useArsiv() {
  return useQuery({
    queryKey: arsivAnahtar.agac(),
    queryFn: () => cagir(api.GET("/api/v1/arsiv")),
    select: (v) => v.sezonlar,
  });
}

export function useArsivKayitlari(senaryo: number | null | undefined, sayfa: number, boyut: number, urunKodu = "") {
  return useQuery({
    queryKey: arsivAnahtar.kayitlar(senaryo, sayfa, urunKodu),
    enabled: senaryo != null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/arsiv/senaryo/{senaryo_id}/kayitlar", {
          params: { path: { senaryo_id: senaryo as number }, query: { sayfa, boyut, ...(urunKodu ? { urun_kodu: urunKodu } : {}) } },
        }),
      ),
  });
}

/** İki kayıtlı hesabı yan yana getirir; iki kimlik de verilmeden istek atılmaz. */
export function useArsivKiyas(a: number | null, b: number | null) {
  return useQuery({
    queryKey: arsivAnahtar.kiyas(a, b),
    enabled: a != null && b != null,
    queryFn: () => cagir(api.GET("/api/v1/arsiv/kiyas", { params: { query: { hesap_a: a as number, hesap_b: b as number } } })),
  });
}

/** Kilitle / kilidi aç: `neden` zorunlu. Senaryo listesi (kilitli bayrağı), arşiv ağacı ve günlük yenilenir. */
export function useSenaryoKilidi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ senaryo, kilitle, neden }: { senaryo: number; kilitle: boolean; neden: string }) =>
      cagir(
        kilitle
          ? api.POST("/api/v1/senaryolar/{senaryo_id}/kilitle", { params: { path: { senaryo_id: senaryo } }, body: { neden } })
          : api.POST("/api/v1/senaryolar/{senaryo_id}/kilit-ac", { params: { path: { senaryo_id: senaryo } }, body: { neden } }),
      ),
    onSuccess: () => Promise.all(["senaryolar", "arsiv", "gunluk"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}
