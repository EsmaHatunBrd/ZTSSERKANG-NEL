import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";

export type GirisKullanicisi = Sema["KullaniciCikis"];
export type Rol = GirisKullanicisi["rol"];

const BEN = ["kimlik", "ben"] as const;
const KULLANICILAR = ["kullanicilar"] as const;

/** Oturumdaki kullanıcı. 401 (giriş yok) hata olarak döner; yeniden denenmez. */
export function useBen() {
  return useQuery({
    queryKey: BEN,
    queryFn: () => cagir(api.GET("/api/v1/kimlik/ben")),
    retry: false,
    staleTime: Infinity,
    // Pencereye dönüşte yeniden sorulmaz: oturum düşerse bunu zaten 401 alan istek bildirir (istemci.ts oturumDustu).
    refetchOnWindowFocus: false,
  });
}

/** Oturum sorgusu dışındaki tüm önbellek (başka kullanıcının verisi ekranda kalmasın). Oturum sorgusu silinmez: kapı onu izliyor. */
const veriyiTemizle = (qc: ReturnType<typeof useQueryClient>) => qc.removeQueries({ predicate: (q) => q.queryKey[0] !== BEN[0] });

export function useGiris() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: Sema["GirisGiris"]) => cagir(api.POST("/api/v1/kimlik/giris", { body: g })),
    onSuccess: (ben) => {
      veriyiTemizle(qc);
      qc.setQueryData(BEN, ben);
    },
  });
}

export function useCikis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/api/v1/kimlik/cikis");
    },
    onSettled: () => {
      veriyiTemizle(qc);
      void qc.invalidateQueries({ queryKey: BEN });
    },
  });
}

export function useSifreDegistir() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: Sema["SifreDegistirGiris"]) => cagir(api.POST("/api/v1/kimlik/sifre", { body: g })),
    onSuccess: (k) => qc.setQueryData(BEN, { giris_zorunlu: true, kullanici: k }),
  });
}

export function useKullanicilar(acik = true) {
  return useQuery({ queryKey: KULLANICILAR, queryFn: () => cagir(api.GET("/api/v1/kullanicilar")), enabled: acik });
}

export function useKullaniciEkle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: Sema["KullaniciEkleGiris"]) => cagir(api.POST("/api/v1/kullanicilar", { body: g })),
    onSuccess: () => qc.invalidateQueries({ queryKey: KULLANICILAR }),
  });
}

export function useKullaniciGuncelle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, govde }: { id: number; govde: Sema["KullaniciGuncelleGiris"] }) =>
      cagir(api.PATCH("/api/v1/kullanicilar/{kullanici_id}", { params: { path: { kullanici_id: id } }, body: govde })),
    onSuccess: () => qc.invalidateQueries({ queryKey: KULLANICILAR }),
  });
}

export function useSifreSifirla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, gecici_sifre }: { id: number; gecici_sifre: string }) =>
      cagir(
        api.POST("/api/v1/kullanicilar/{kullanici_id}/sifre-sifirla", { params: { path: { kullanici_id: id } }, body: { gecici_sifre } }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: KULLANICILAR }),
  });
}
