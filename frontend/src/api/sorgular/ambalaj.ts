import { useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { anahtar } from "./anahtarlar";

/** Ambalaj özeti (Excel `Ambalaj Özeti`): ambalaj türü ve kapak bazında ürün sayısı ile üretim adedi. */
export function useAmbalajOzeti(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.ambalajOzeti(senaryo),
    enabled: senaryo != null,
    queryFn: () =>
      cagir(api.GET("/api/v1/ambalaj-ozeti", { params: { query: { senaryo: senaryo as number } } })),
  });
}
