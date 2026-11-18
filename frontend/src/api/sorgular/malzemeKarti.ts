import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiHatasi, api, cagir } from "../istemci";
import type { Sema } from "../tipler";

/**
 * Yeni malzeme kartı açar (`POST /malzemeler`). Sunucu aynı kodda kart varsa sessizce günceller; ekrandan yanlışlıkla mevcut kartı
 * ezmemek için önce kod aranır ve tam eşleşen kart varsa `cakisma` hatası fırlatılır.
 */
export function useMalzemeKartiOlustur() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ senaryo, govde }: { senaryo: number; govde: Sema["MalzemeGiris"] }) => {
      const liste = await cagir(api.GET("/api/v1/malzemeler", { params: { query: { senaryo, arama: govde.kod, boyut: 50 } } }));
      const mevcut = liste.kayitlar.find((m) => m.kod.toLowerCase() === govde.kod.toLowerCase() && !m.kart_yok);
      if (mevcut) {
        throw new ApiHatasi(
          "cakisma",
          `Bu kod zaten kayıtlı: ${mevcut.ad ?? mevcut.kod}. Fiyatını "Malzeme fiyatı" kartından girin.`,
          { kod: govde.kod },
          409,
        );
      }
      return cagir(api.POST("/api/v1/malzemeler", { body: govde }));
    },
    onSuccess: () => Promise.all(["malzemeler", "uyarilar", "recete"].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}
