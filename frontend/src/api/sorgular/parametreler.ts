import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { Sema } from "../tipler";
import { anahtar } from "./anahtarlar";

export function useParametreler(senaryo: number | null | undefined, tarih?: string) {
  return useQuery({
    queryKey: anahtar.parametreler(senaryo, tarih),
    enabled: senaryo != null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/parametreler", { params: { query: { senaryo: senaryo as number, tarih } } }),
      ),
  });
}

export function useParametreTanimlari() {
  return useQuery({
    queryKey: anahtar.parametreTanimlari(),
    staleTime: 5 * 60_000,
    queryFn: () => cagir(api.GET("/api/v1/parametreler/tanimlar")),
  });
}

export function useParametreGecmisi(a: string | null | undefined, senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.parametreGecmisi(a ?? "", senaryo),
    enabled: !!a && senaryo != null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/parametreler/{anahtar}/gecmis", {
          params: { path: { anahtar: a as string }, query: { senaryo: senaryo as number } },
        }),
      ),
  });
}

/** Geri al da dahil her değişiklik yeni değer kaydıdır. */
export function useParametreEkle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      anahtar: a,
      senaryo,
      govde,
    }: {
      anahtar: string;
      senaryo: number;
      govde: Sema["ParametreDegerGiris"];
    }) =>
      cagir(
        api.POST("/api/v1/parametreler/{anahtar}/degerler", {
          params: { path: { anahtar: a }, query: { senaryo } },
          body: govde,
        }),
      ),
    onSuccess: () =>
      Promise.all(
        ["parametreler", "parametre-gecmisi", "urunler", "uyarilar"].map((k) => qc.invalidateQueries({ queryKey: [k] })),
      ),
  });
}
