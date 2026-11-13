import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import { formVerisi } from "./aktar";

export interface SmmStokSecenegi {
  tur?: string;
  arama?: string;
  yalniz_kontrol?: boolean;
}

export function useSmmDonemleri() {
  return useQuery({ queryKey: ["smm", "donemler"], queryFn: () => cagir(api.GET("/api/v1/smm/donemler")) });
}

export function useSmmStok(donemId: number | null, secenek: SmmStokSecenegi = {}) {
  return useQuery({
    queryKey: ["smm", "stok", donemId, secenek],
    enabled: donemId !== null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/stok", {
          params: {
            path: { donem_id: donemId as number },
            query: {
              tur: secenek.tur || undefined,
              arama: secenek.arama || undefined,
              yalniz_kontrol: secenek.yalniz_kontrol || undefined,
            },
          },
        }),
      ),
  });
}

/** SMM Excel'ini yükler. Dönem verilmezse dosya adından çıkarılır; dönem zaten varsa 409 (üzerine yazmak için `uzerineYaz`). */
export function useSmmYukle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ dosya, yil, ay, uzerineYaz }: { dosya: File; yil?: number; ay?: number; uzerineYaz?: boolean }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/yukle", {
          body: {} as never,
          bodySerializer: () =>
            formVerisi({
              dosya,
              ...(yil ? { yil: String(yil) } : {}),
              ...(ay ? { ay: String(ay) } : {}),
              ...(uzerineYaz ? { uzerine_yaz: "true" } : {}),
            }),
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export interface SmmUretimSecenegi {
  asama: number;
  arama?: string;
  yalniz_farkli?: boolean;
}

/** Aşama maliyetleri: üç aşamanın özeti, dağıtım havuzları ve seçilen aşamanın ürünleri. */
export function useSmmUretim(donemId: number | null, secenek: SmmUretimSecenegi) {
  return useQuery({
    queryKey: ["smm", "uretim", donemId, secenek],
    enabled: donemId !== null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/uretim", {
          params: {
            path: { donem_id: donemId as number },
            query: { asama: secenek.asama, arama: secenek.arama || undefined, yalniz_farkli: secenek.yalniz_farkli || undefined },
          },
        }),
      ),
  });
}

export function useSmmUrunRecetesi(donemId: number | null, asama: number, kod: string | null) {
  return useQuery({
    queryKey: ["smm", "recete", donemId, asama, kod],
    enabled: donemId !== null && kod !== null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/uretim/{asama}/{kod}", {
          params: { path: { donem_id: donemId as number, asama, kod: kod as string } },
        }),
      ),
  });
}

/** Dağıtım havuzlarını değiştirir (anahtar -> TL); aşama maliyetleri ve sarf farkı yeniden hesaplanır. */
export function useSmmDagitim(donemId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ havuzlar = {}, anahtarlar = {} }: { havuzlar?: Record<string, string>; anahtarlar?: Record<string, string> }) =>
      cagir(
        api.PUT("/api/v1/smm/donemler/{donem_id}/dagitim", {
          params: { path: { donem_id: donemId as number } },
          body: { havuzlar, anahtarlar },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

/** Ürünün aşama değerlerini elle girer (birim başına TL); null = formüle dön. */
export function useSmmUrunElle(donemId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ asama, kod, alanlar }: { asama: number; kod: string; alanlar: Record<string, string | null> }) =>
      cagir(
        api.PUT("/api/v1/smm/donemler/{donem_id}/uretim/{asama}/{kod}/elle", {
          params: { path: { donem_id: donemId as number, asama, kod } },
          body: { alanlar },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmSureler(donemId: number | null, arama = "") {
  return useQuery({
    queryKey: ["smm", "sureler", donemId, arama],
    enabled: donemId !== null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/sureler", {
          params: { path: { donem_id: donemId as number }, query: { arama: arama || undefined } },
        }),
      ),
  });
}

export type SureGirdisi = Partial<
  Record<
    | "mamul_kod"
    | "yari_mamul_kod"
    | "ad"
    | "vardiya_uretim"
    | "dolum_isci"
    | "etiket_isci"
    | "dolum_sn"
    | "dolum_adam_sn"
    | "etiket_sn"
    | "etiket_adam_sn",
    string | null
  >
>;

export function useSmmSureDuzenle(donemId: number | null) {
  const qc = useQueryClient();
  const bitti = () => qc.invalidateQueries({ queryKey: ["smm"] });
  return {
    ekle: useMutation({
      mutationFn: (g: SureGirdisi) =>
        cagir(api.POST("/api/v1/smm/donemler/{donem_id}/sureler", { params: { path: { donem_id: donemId as number } }, body: g })),
      onSuccess: bitti,
    }),
    guncelle: useMutation({
      mutationFn: ({ id, g }: { id: number; g: SureGirdisi }) =>
        cagir(api.PUT("/api/v1/smm/sureler/{sure_id}", { params: { path: { sure_id: id } }, body: g })),
      onSuccess: bitti,
    }),
    sil: useMutation({
      mutationFn: (id: number) => cagir(api.DELETE("/api/v1/smm/sureler/{sure_id}", { params: { path: { sure_id: id } } })),
      onSuccess: bitti,
    }),
  };
}

export interface SmmSarfSecenegi {
  arama?: string;
  tur?: string;
  esik?: number;
}

export function useSmmSarfFarki(donemId: number | null, secenek: SmmSarfSecenegi = {}) {
  return useQuery({
    queryKey: ["smm", "sarf", donemId, secenek],
    enabled: donemId !== null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/sarf-farki", {
          params: {
            path: { donem_id: donemId as number },
            query: { arama: secenek.arama || undefined, tur: secenek.tur || undefined, esik: secenek.esik || undefined },
          },
        }),
      ),
  });
}

/** SMM özeti: dönem sonu stok değerlemesi, SMM tablosu, stok mizanı karşılaştırması ve fiş taslağı. */
export function useSmmOzet(donemId: number | null) {
  return useQuery({
    queryKey: ["smm", "ozet", donemId],
    enabled: donemId !== null,
    queryFn: () => cagir(api.GET("/api/v1/smm/donemler/{donem_id}/ozet", { params: { path: { donem_id: donemId as number } } })),
  });
}

/** Excel'siz yeni dönem: dönem başı stok önceki dönemin sayımından devreder. */
export function useSmmYeniDonem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: { yil: number; ay: number }) => cagir(api.POST("/api/v1/smm/donemler", { body: g })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

/** Dönemin reçete kaynağı: 'excel' (dönemle yüklenen) ya da 'ana' (kalıcı Canias reçeteleri). */
export function useSmmReceteKaynagi() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, kaynak }: { donemId: number; kaynak: "excel" | "ana" }) =>
      cagir(api.PUT("/api/v1/smm/donemler/{donem_id}/recete-kaynagi", { params: { path: { donem_id: donemId } }, body: { kaynak } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmReceteler(secenek: { arama?: string; asama?: number | null } = {}) {
  return useQuery({
    queryKey: ["smm", "receteler", secenek],
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/receteler", { params: { query: { arama: secenek.arama || undefined, asama: secenek.asama || undefined } } }),
      ),
  });
}

export function useSmmRecete(kod: string | null) {
  return useQuery({
    queryKey: ["smm", "recete-detay", kod],
    enabled: kod !== null,
    queryFn: () => cagir(api.GET("/api/v1/smm/receteler/{kod}", { params: { path: { kod: kod as string } } })),
  });
}

function receteDosyasi(yol: "/api/v1/smm/receteler/onizle" | "/api/v1/smm/receteler/yukle", dosya: File) {
  return cagir(api.POST(yol, { body: {} as never, bodySerializer: () => formVerisi({ dosya }) }));
}

export function useSmmReceteOnizle() {
  return useMutation({ mutationFn: (dosya: File) => receteDosyasi("/api/v1/smm/receteler/onizle", dosya) });
}

export function useSmmReceteYukle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (dosya: File) => receteDosyasi("/api/v1/smm/receteler/yukle", dosya),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmAlternatif() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kod, alternatif }: { kod: string; alternatif: string }) =>
      cagir(api.PUT("/api/v1/smm/receteler/{kod}/alternatif", { params: { path: { kod } }, body: { alternatif } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export interface ReceteSatiriGirdisi {
  alternatif: string;
  malzeme_kod: string;
  malzeme_ad?: string | null;
  miktar: string;
  birim: string;
  fire_orani: string;
}

/** Reçeteyi elle düzenleme: satır ekle / güncelle / sil, alternatif kopyala, Canias'a döndür, yeni ürün reçetesi. */
export function useSmmReceteDuzenle() {
  const qc = useQueryClient();
  const bitti = () => qc.invalidateQueries({ queryKey: ["smm"] });
  return {
    ekle: useMutation({
      mutationFn: ({ kod, satir }: { kod: string; satir: ReceteSatiriGirdisi }) =>
        cagir(api.POST("/api/v1/smm/receteler/{kod}/satirlar", { params: { path: { kod } }, body: satir })),
      onSuccess: bitti,
    }),
    guncelle: useMutation({
      mutationFn: ({ id, alanlar }: { id: number; alanlar: { miktar?: string; birim?: string; fire_orani?: string } }) =>
        cagir(api.PUT("/api/v1/smm/recete-satirlari/{satir_id}", { params: { path: { satir_id: id } }, body: alanlar })),
      onSuccess: bitti,
    }),
    sil: useMutation({
      mutationFn: (id: number) => cagir(api.DELETE("/api/v1/smm/recete-satirlari/{satir_id}", { params: { path: { satir_id: id } } })),
      onSuccess: bitti,
    }),
    kopyala: useMutation({
      mutationFn: ({ kod, kaynak, yeni }: { kod: string; kaynak: string; yeni: string }) =>
        cagir(api.POST("/api/v1/smm/receteler/{kod}/alternatif-kopyala", { params: { path: { kod } }, body: { kaynak, yeni } })),
      onSuccess: bitti,
    }),
    asama: useMutation({
      mutationFn: ({ kod, asama }: { kod: string; asama: number }) =>
        cagir(api.PUT("/api/v1/smm/receteler/{kod}/asama", { params: { path: { kod } }, body: { asama } })),
      onSuccess: bitti,
    }),
    caniasaDon: useMutation({
      mutationFn: (kod: string) => cagir(api.POST("/api/v1/smm/receteler/{kod}/canias-a-don", { params: { path: { kod } } })),
      onSuccess: bitti,
    }),
    yeniUrun: useMutation({
      mutationFn: (g: ReceteSatiriGirdisi & { ana_kod: string; ana_ad?: string | null }) =>
        cagir(api.POST("/api/v1/smm/receteler", { body: g })),
      onSuccess: bitti,
    }),
  };
}

export function useSmmMalzemeAra(q: string) {
  return useQuery({
    queryKey: ["smm", "malzeme-ara", q],
    enabled: q.trim().length >= 2,
    placeholderData: keepPreviousData,
    queryFn: () => cagir(api.GET("/api/v1/smm/malzeme-ara", { params: { query: { q } } })),
  });
}

export function useSmmReceteKiyas(donemId: number | null) {
  return useQuery({
    queryKey: ["smm", "recete-kiyas", donemId],
    enabled: donemId !== null,
    queryFn: () => cagir(api.GET("/api/v1/smm/receteler/kiyas", { params: { query: { donem: donemId as number } } })),
  });
}

/** Dönemin veri kontrol listesi. */
export function useSmmVeriDurumu(donemId: number | null) {
  return useQuery({
    queryKey: ["smm", "veri", donemId],
    enabled: donemId !== null,
    queryFn: () => cagir(api.GET("/api/v1/smm/donemler/{donem_id}/veri", { params: { path: { donem_id: donemId as number } } })),
  });
}

export function useSmmVeriYukle(donemId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kaynak, dosya }: { kaynak: string; dosya: File }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/{donem_id}/veri/{kaynak}", {
          params: { path: { donem_id: donemId as number, kaynak } },
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya }),
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmAyarlar(donemId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: { finansman?: string | null; gider_720?: string | null; gider_730?: string | null }) =>
      cagir(api.PUT("/api/v1/smm/donemler/{donem_id}/ayarlar", { params: { path: { donem_id: donemId as number } }, body: g })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmKilit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, kilitli }: { donemId: number; kilitli: boolean }) =>
      cagir(api.PUT("/api/v1/smm/donemler/{donem_id}/kilit", { params: { path: { donem_id: donemId } }, body: { kilitli } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export const smmFisAdresi = (donemId: number) => `/api/v1/smm/donemler/${donemId}/fis.xlsx`;

export function useSmmSil() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cagir(api.DELETE("/api/v1/smm/donemler/{donem_id}", { params: { path: { donem_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export type SmmMizanTuru = "gider" | "stok";

/** Dönemin gider (720 / 730) ya da stok (150 / 151 / 152) mizanı satırları. */
export function useSmmMizan(donemId: number | null, tur: SmmMizanTuru, acik = true) {
  return useQuery({
    queryKey: ["smm", "mizan", donemId, tur],
    enabled: donemId !== null && acik,
    queryFn: () =>
      cagir(api.GET("/api/v1/smm/donemler/{donem_id}/mizan/{tur}", { params: { path: { donem_id: donemId as number, tur } } })),
  });
}

export function useSmmMizanEkle(donemId: number, tur: SmmMizanTuru) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: { hesap: string; ad?: string | null; bakiye: string; neden: string }) =>
      cagir(api.POST("/api/v1/smm/donemler/{donem_id}/mizan/{tur}", { params: { path: { donem_id: donemId, tur } }, body: g })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmMizanGuncelle(donemId: number, tur: SmmMizanTuru) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ hesap, ...g }: { hesap: string; ad?: string | null; bakiye?: string; neden: string }) =>
      cagir(
        api.PATCH("/api/v1/smm/donemler/{donem_id}/mizan/{tur}/{hesap}", { params: { path: { donem_id: donemId, tur, hesap } }, body: g }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

export function useSmmMizanSil(donemId: number, tur: SmmMizanTuru) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ hesap, neden }: { hesap: string; neden: string }) =>
      cagir(
        api.DELETE("/api/v1/smm/donemler/{donem_id}/mizan/{tur}/{hesap}", {
          params: { path: { donem_id: donemId, tur, hesap }, query: { neden } },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}
