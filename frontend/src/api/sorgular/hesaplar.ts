import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";
import { anahtar } from "./anahtarlar";

export interface HesaplaDegiskenleri {
  kod: string;
  govde: Sema["HesaplaGiris"];
}

/** "Ne olur" hesabı: kaydetmez, bu yüzden hiçbir sorguyu geçersiz kılmaz. */
export function useHesapla() {
  return useMutation({
    mutationFn: ({ kod, govde }: HesaplaDegiskenleri) =>
      cagir(api.POST("/api/v1/urunler/{kod}/hesapla", { params: { path: { kod } }, body: govde })),
  });
}

export function useHesapKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, govde }: HesaplaDegiskenleri) =>
      cagir(api.POST("/api/v1/urunler/{kod}/hesaplar", { params: { path: { kod } }, body: govde })),
    onSuccess: (_v, { kod }) =>
      Promise.all([qc.invalidateQueries({ queryKey: ["hesaplar", kod] }), qc.invalidateQueries({ queryKey: ["urunler"] })]),
  });
}

/** Faz 4c "Kaydet": ürün kartı, hedef, reçete, parametre ve gider tek atomik istekte yazılır. */
export const TOPLU_KAYIT_SORGULARI = ["urun", "urunler", "hesaplar", "uyarilar", "recete", "parametreler", "gider-havuzlari"] as const;

export function useTopluKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, govde }: { kod: string; govde: Sema["TopluKaydetGiris"] }) =>
      cagir(api.POST("/api/v1/urunler/{kod}/kaydet", { params: { path: { kod } }, body: govde })),
    onSuccess: () => Promise.all(TOPLU_KAYIT_SORGULARI.map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}

export function useHesaplar(kod: string, senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.hesaplar(kod, senaryo),
    enabled: !!kod && senaryo != null,
    queryFn: () => cagir(api.GET("/api/v1/urunler/{kod}/hesaplar", { params: { path: { kod }, query: { senaryo: senaryo as number } } })),
  });
}

export function useHesap(id: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.hesap(id),
    enabled: id != null,
    queryFn: () => cagir(api.GET("/api/v1/hesaplar/{hesap_id}", { params: { path: { hesap_id: id as number } } })),
  });
}

export function useTeklifler(hesapId: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.teklifler(hesapId),
    enabled: hesapId != null,
    queryFn: () => cagir(api.GET("/api/v1/hesaplar/{hesap_id}/teklifler", { params: { path: { hesap_id: hesapId as number } } })),
  });
}

export interface SenaryoTeklifSecenegi {
  durum?: string;
  musteri?: string;
  /** Ürün kodu ya da adında geçen metin. */
  urun?: string;
  sayfa?: number;
  boyut?: number;
}

/** Senaryo geneli teklif listesi: süzme ve sayfalama sunucuda yapılır. */
export function useSenaryoTeklifleri(senaryo: number | null | undefined, secenek: SenaryoTeklifSecenegi = {}) {
  return useQuery({
    queryKey: anahtar.senaryoTeklifleri(senaryo, secenek),
    enabled: senaryo != null,
    // Yalnızca aynı senaryonun önceki verisi (sayfa/süzme değişimi) gösterilir.
    placeholderData: (onceki, oncekiSorgu) => (oncekiSorgu?.queryKey[2] === (senaryo ?? null) ? onceki : undefined),
    queryFn: () =>
      cagir(
        api.GET("/api/v1/teklifler", {
          params: {
            query: {
              senaryo: senaryo as number,
              durum: secenek.durum || undefined,
              musteri: secenek.musteri || undefined,
              urun: secenek.urun || undefined,
              sayfa: secenek.sayfa,
              boyut: secenek.boyut,
            },
          },
        }),
      ),
  });
}

export function useTeklifEkle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ hesapId, govde }: { hesapId: number; govde: Sema["TeklifGiris"] }) =>
      cagir(api.POST("/api/v1/hesaplar/{hesap_id}/teklifler", { params: { path: { hesap_id: hesapId } }, body: govde })),
    // ["teklifler"] öneki hesap bazlı ve senaryo geneli listeleri; ["hesaplar"] kayıtlı hesabın son tur özetini yeniler.
    onSuccess: () => Promise.all([qc.invalidateQueries({ queryKey: ["teklifler"] }), qc.invalidateQueries({ queryKey: ["hesaplar"] })]),
  });
}

export function useTeklifDurum() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ teklifId, durum }: { teklifId: number; durum: string }) =>
      cagir(api.PATCH("/api/v1/teklifler/{teklif_id}/durum", { params: { path: { teklif_id: teklifId } }, body: { durum } })),
    onSuccess: () => Promise.all([qc.invalidateQueries({ queryKey: ["teklifler"] }), qc.invalidateQueries({ queryKey: ["hesaplar"] })]),
  });
}

/** Teklif turunu kalıcı siler (içeriği Değişiklik Günlüğünde kalır); listeler ve son tur özeti yenilenir. */
export function useTeklifSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (teklifId: number) => cagir(api.DELETE("/api/v1/teklifler/{teklif_id}", { params: { path: { teklif_id: teklifId } } })),
    onSuccess: () => Promise.all([qc.invalidateQueries({ queryKey: ["teklifler"] }), qc.invalidateQueries({ queryKey: ["hesaplar"] })]),
  });
}
