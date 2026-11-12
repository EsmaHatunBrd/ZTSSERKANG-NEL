import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type {
  AktarimOnizleGider,
  AktarimOnizleRecete,
  AktarimOnizleSatinAlma,
  AktarimOnizleStokDevri,
  AktarimOnizleUretim,
  AktarimUygulaGider,
  AktarimUygulaRecete,
  AktarimUygulaSatinAlma,
  AktarimUygulaStokDevri,
  AktarimUygulaUretim,
} from "../tipler";
import { formVerisi } from "./aktar";

/** Ayrı ayrı yüklenebilen veri türleri (uç adresindeki parça). */
export type AktarimTipi = "uretim-adetleri" | "satin-alma" | "gider-dagitim" | "recete" | "stok-devri";

export interface TipHaritasi {
  "uretim-adetleri": { onizle: AktarimOnizleUretim; uygula: AktarimUygulaUretim };
  "satin-alma": { onizle: AktarimOnizleSatinAlma; uygula: AktarimUygulaSatinAlma };
  "gider-dagitim": { onizle: AktarimOnizleGider; uygula: AktarimUygulaGider };
  recete: { onizle: AktarimOnizleRecete; uygula: AktarimUygulaRecete };
  "stok-devri": { onizle: AktarimOnizleStokDevri; uygula: AktarimUygulaStokDevri };
}

/** Başarılı uygulamada yenilenecek sorgu önekleri (yazılan veriyi gösteren tüm ekranlar). */
const GECERSIZ: Record<AktarimTipi, string[]> = {
  "uretim-adetleri": ["kapasite", "ambalaj-ozeti", "urunler", "hesaplar", "uyarilar"],
  "satin-alma": ["malzemeler", "fiyat-gecmisi", "urunler", "hesaplar", "uyarilar"],
  "gider-dagitim": ["gider-havuzlari", "ambalajlar", "ambalaj-ozeti", "urunler", "hesaplar", "uyarilar"],
  "stok-devri": ["stok-devri", "urun", "urunler", "hesaplar", "uyarilar", "analiz", "karsilastirma", "liste-calismasi"],
  recete: ["recete", "urun", "urunler", "hesaplar", "uyarilar", "ambalaj-ozeti", "karsilastirma", "senaryolar", "gunluk", "arsiv"],
};

export interface AktarimOnizleDegiskenleri {
  dosya: File;
  senaryo: number;
  /** Yalnız satın almada: fiyat karşılaştırması bu tarihteki geçerli fiyata göre yapılır. */
  gecerlilik_basi?: string;
}

export interface AktarimUygulaDegiskenleri extends AktarimOnizleDegiskenleri {
  neden: string;
  /** Yalnız satın almada: geçerlilik tarihi zorunludur. */
  kartlari_guncelle?: boolean;
  /** Yalnız reçetede: uygulanacak ürün sayfaları. */
  sayfalar?: string[];
}

// Uç adresi tipe göre değişir; openapi-fetch yolu sabit ister, bu yüzden ilk uca daraltılır (gövde bodySerializer ile kurulur).
type OnizleYolu = "/api/v1/aktarim/uretim-adetleri/onizle";
type UygulaYolu = "/api/v1/aktarim/uretim-adetleri/uygula";

export function useAktarimOnizle<T extends AktarimTipi>(tip: T) {
  return useMutation({
    mutationFn: (d: AktarimOnizleDegiskenleri) =>
      cagir(
        api.POST(`/api/v1/aktarim/${tip}/onizle` as OnizleYolu, {
          body: {} as never,
          bodySerializer: () => formVerisi({ ...d }),
        }),
      ) as unknown as Promise<TipHaritasi[T]["onizle"]>,
  });
}

export function useAktarimUygula<T extends AktarimTipi>(tip: T) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: AktarimUygulaDegiskenleri) =>
      cagir(
        api.POST(`/api/v1/aktarim/${tip}/uygula` as UygulaYolu, {
          body: {} as never,
          bodySerializer: () => formVerisi({ ...d }),
        }),
      ) as unknown as Promise<TipHaritasi[T]["uygula"]>,
    onSuccess: () => Promise.all(GECERSIZ[tip].map((k) => qc.invalidateQueries({ queryKey: [k] }))),
  });
}
