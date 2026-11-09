import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { SmmStokSatiri } from "../tipler";

/**
 * Stok kalemi düzenleme uçları (api/smm_stok.py). Üretilen şema (`sema.d.ts`) paylaşımlı olduğu ve başka iş kolları tarafından
 * yeniden üretildiği için yollar burada gevşek tipli çağrılır; istemcinin ara katmanı (kullanıcı başlığı, 401, hata gövdesi) aynen uygulanır.
 */
interface GevsekIstemci {
  GET(yol: string, secenek?: object): Promise<{ data?: unknown; error?: unknown; response: Response }>;
  PATCH(yol: string, secenek: object): Promise<{ data?: unknown; error?: unknown; response: Response }>;
  POST(yol: string, secenek: object): Promise<{ data?: unknown; error?: unknown; response: Response }>;
}
const gevsek = api as unknown as GevsekIstemci;

export type SmmKalemAlanlari = Partial<
  Pick<
    SmmStokSatiri,
    | "ad"
    | "birim"
    | "tur"
    | "mizan_kodu"
    | "dbs_miktar"
    | "dbs_tutar"
    | "alim_miktar"
    | "alim_tutar"
    | "iade_miktar"
    | "iade_tutar"
    | "uretim_miktar"
    | "sayim_miktar"
  >
> & { sahit_miktar?: string | null };

export interface SmmElleKayit {
  alanlar: string[];
  zaman: string | null;
  kullanici: string | null;
  kayit: number;
}

export function useSmmElleDegisenler(donemId: number | null) {
  return useQuery({
    queryKey: ["smm", "stok-elle", donemId],
    enabled: donemId !== null,
    queryFn: async () =>
      (await cagir(gevsek.GET(`/api/v1/smm/donemler/${donemId}/stok/elle`))) as { kayitlar: Record<string, SmmElleKayit> },
  });
}

export function useSmmKalemGuncelle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, kod, alanlar, neden }: { donemId: number; kod: string; alanlar: SmmKalemAlanlari; neden: string }) =>
      cagir(gevsek.PATCH(`/api/v1/smm/donemler/${donemId}/stok/${encodeURIComponent(kod)}`, { body: { ...alanlar, neden } })) as Promise<
        SmmStokSatiri & { degisti: string[] }
      >,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmKalemEkle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, kod, alanlar, neden }: { donemId: number; kod: string; alanlar: SmmKalemAlanlari; neden: string }) =>
      cagir(gevsek.POST(`/api/v1/smm/donemler/${donemId}/stok`, { body: { kod, ...alanlar, neden } })) as Promise<
        SmmStokSatiri & { degisti: string[] }
      >,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}
