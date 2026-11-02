import { useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { anahtar } from "./anahtarlar";

export function useUyarilar(senaryo: number | null | undefined, tarih?: string) {
  return useQuery({
    queryKey: [...anahtar.uyarilar(senaryo), tarih ?? null],
    enabled: senaryo != null,
    queryFn: () =>
      cagir(api.GET("/api/v1/uyarilar", { params: { query: { senaryo: senaryo as number, tarih } } })),
  });
}
