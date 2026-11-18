import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiHatasi, cagir } from "../istemci";
import type { Sema, UrunGiris } from "../tipler";
import { anahtar } from "./anahtarlar";

export interface UrunListeSecenegi {
  sayfa?: number;
  boyut?: number;
  gecici?: boolean;
  tarih?: string;
  /** Faz 5c: çalışma dışı (bu senaryoda reçetesi olmayan) ürünler de listelensin (`?tum=1`). */
  tum?: boolean;
}

export function useUrunler(senaryo: number | null | undefined, secenek: UrunListeSecenegi = {}) {
  return useQuery({
    queryKey: anahtar.urunler(senaryo, secenek),
    enabled: senaryo != null,
    // Yalnızca aynı senaryonun önceki verisi (sayfa değişimi) gösterilir; senaryo değişince başka senaryonun tutarları asla.
    placeholderData: (onceki, oncekiSorgu) => (oncekiSorgu?.queryKey[1] === (senaryo ?? null) ? onceki : undefined),
    queryFn: () =>
      cagir(
        api.GET("/api/v1/urunler", {
          params: {
            query: {
              senaryo: senaryo as number,
              sayfa: secenek.sayfa,
              boyut: secenek.boyut,
              gecici: secenek.gecici,
              tarih: secenek.tarih,
              tum: secenek.tum,
            },
          },
        }),
      ),
  });
}

export function useUrun(kod: string, senaryo?: number | null) {
  return useQuery({
    queryKey: anahtar.urun(kod, senaryo),
    enabled: !!kod,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/urunler/{kod}", {
          params: { path: { kod }, query: { senaryo: senaryo ?? undefined } },
        }),
      ),
  });
}

export function useRecete(kod: string, senaryo: number | null | undefined, tarih?: string) {
  return useQuery({
    queryKey: [...anahtar.recete(kod, senaryo), tarih ?? null],
    enabled: !!kod && senaryo != null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/urunler/{kod}/recete", {
          params: {
            path: { kod },
            query: { senaryo: senaryo as number, tarih },
          },
        }),
      ),
  });
}

export interface UrunOlusturDegiskenleri {
  kod: string;
  govde: UrunGiris;
}

/**
 * Yeni ürün kartı (Faz 5c). `PUT /urunler/{kod}` upsert olduğundan var olan kart sessizce ezilmesin diye önce `GET` ile
 * kod tekilliği denetlenir: kart varsa 409 benzeri `ApiHatasi("catisma")` fırlatılır. Başarıda ürün listeleri yenilenir.
 */
export function useUrunOlustur() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ kod, govde }: UrunOlusturDegiskenleri) => {
      let mevcutAd: string | null = null;
      try {
        mevcutAd = (await cagir(api.GET("/api/v1/urunler/{kod}", { params: { path: { kod } } }))).ad;
      } catch (e) {
        if (!(e instanceof ApiHatasi && e.durum === 404)) throw e;
      }
      if (mevcutAd !== null) {
        throw new ApiHatasi("catisma", `Bu kod zaten kayıtlı: ${mevcutAd}. Mevcut kartı değiştirmek için ürün ekranını kullanın.`, {}, 409);
      }
      // Not: "ERP kodu yok / geçici kod" seçeneği `UrunGiris` şemasında olmadığı için gönderilmez (ledger: açık nokta).
      return cagir(api.PUT("/api/v1/urunler/{kod}", { params: { path: { kod } }, body: govde }));
    },
    onSuccess: (_v, { kod }) =>
      Promise.all([qc.invalidateQueries({ queryKey: ["urunler"] }), qc.invalidateQueries({ queryKey: ["urun", kod] })]),
  });
}

/** Ürün pasifleştirme: ürün sorgularını yeniler (silme yoktur). */
export function useUrunPasiflestir() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (kod: string) => cagir(api.PATCH("/api/v1/urunler/{kod}/pasif", { params: { path: { kod } } })),
    onSuccess: () => Promise.all([qc.invalidateQueries({ queryKey: ["urunler"] }), qc.invalidateQueries({ queryKey: ["urun"] })]),
  });
}

export interface ReceteKaydetDegiskenleri {
  kod: string;
  senaryo: number;
  satirlar: Sema["ReceteSatirGiris"][];
  /** Zorunlu neden: Değişiklik Günlüğüne reçete sürümüyle yazılır. */
  neden: string;
}

/** Yeni reçete versiyonu açar (tam satır listesi + neden). Reçete, ürün, uyarı ve kayıtlı hesap sorgularını yeniler. */
export function useReceteKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, senaryo, satirlar, neden }: ReceteKaydetDegiskenleri) =>
      cagir(
        api.POST("/api/v1/urunler/{kod}/recete", {
          params: { path: { kod }, query: { senaryo } },
          body: { satirlar, neden: neden.trim() },
        }),
      ),
    onSuccess: (_v, { kod }) =>
      Promise.all(
        [["recete", kod], ["urunler"], ["urun", kod], ["uyarilar"], ["hesaplar", kod]].map((queryKey) =>
          qc.invalidateQueries({ queryKey }),
        ),
      ),
  });
}

export interface UretimHedefiKaydetDegiskenleri {
  kod: string;
  senaryo: number;
  govde: Sema["UretimHedefiNedenliGiris"];
}

/** Ürünün üretim bilgilerini (vardiya üretim adedi, personel, mal kabul) nedenle yazar; ürün, dashboard, uyarı ve hesap sorgularını yeniler. */
export function useUretimHedefiKaydet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, senaryo, govde }: UretimHedefiKaydetDegiskenleri) =>
      cagir(
        api.PUT("/api/v1/urunler/{kod}/uretim-hedefi", {
          params: { path: { kod }, query: { senaryo } },
          body: govde,
        }),
      ),
    onSuccess: (_v, { kod }) =>
      Promise.all(
        [["urun", kod], ["urunler"], ["uyarilar"], ["hesaplar", kod], ["karsilastirma"]].map((queryKey) =>
          qc.invalidateQueries({ queryKey }),
        ),
      ),
  });
}
