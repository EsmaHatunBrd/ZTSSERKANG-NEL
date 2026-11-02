import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";
import { anahtar } from "./anahtarlar";

export function useGiderHavuzlari(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.giderHavuzlari(senaryo),
    enabled: senaryo != null,
    queryFn: () =>
      cagir(api.GET("/api/v1/gider-havuzlari", { params: { query: { senaryo: senaryo as number } } })),
  });
}

export function useHavuzKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, senaryo, govde }: { kod: string; senaryo: number; govde: Sema["HavuzGiris"] }) =>
      cagir(
        api.PUT("/api/v1/gider-havuzlari/{kod}", { params: { path: { kod }, query: { senaryo } }, body: govde }),
      ),
    onSuccess: () => Promise.all(["gider-havuzlari", "urunler"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}

export function useAmbalajlar(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.ambalajlar(senaryo),
    enabled: senaryo != null,
    queryFn: () =>
      cagir(api.GET("/api/v1/ambalaj-siniflari", { params: { query: { senaryo: senaryo as number } } })),
  });
}

export function useAmbalajKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ senaryo, govde }: { senaryo: number; govde: Sema["AmbalajKaydiGiris"] }) =>
      cagir(api.PUT("/api/v1/ambalaj-siniflari", { params: { query: { senaryo } }, body: govde })),
    onSuccess: () => Promise.all(["ambalajlar", "urunler"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}

export function useFireKurallari(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.fireKurallari(senaryo),
    enabled: senaryo != null,
    queryFn: () =>
      cagir(api.GET("/api/v1/fire-kurallari", { params: { query: { senaryo: senaryo as number } } })),
  });
}

export function useFireKuraliEkle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ senaryo, govde }: { senaryo: number; govde: Sema["FireKuraliGiris"] }) =>
      cagir(api.POST("/api/v1/fire-kurallari", { params: { query: { senaryo } }, body: govde })),
    onSuccess: () =>
      Promise.all(["fire-kurallari", "recete", "urunler"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}
