import { useQuery } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { anahtar } from "./anahtarlar";

/** Veri Kontrolü: çalışmanın veri sorunları (durum, sayı, çözüm bağlantısı, ilgili kayıtlar); sunucu önbellekli. */
export function useTutarlilik(senaryo: number | null | undefined) {
  return useQuery({
    queryKey: anahtar.tutarlilik(senaryo),
    enabled: senaryo != null,
    queryFn: () => cagir(api.GET("/api/v1/tutarlilik", { params: { query: { senaryo: senaryo as number } } })),
  });
}
