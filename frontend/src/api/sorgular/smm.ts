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

/** Yükleme yazınca: SMM sorguları ve "Son yükleme — Geri al" şeritleri tazelenir. */
function yuklemeSonrasi(qc: ReturnType<typeof useQueryClient>) {
  return Promise.all([qc.invalidateQueries({ queryKey: ["smm"] }), qc.invalidateQueries({ queryKey: ["son-yukleme"] })]);
}

/**
 * SMM Excel'ini yükler. Dönem verilmezse dosya adından çıkarılır; dönem zaten varsa 409 (üzerine yazmak için `uzerineYaz`);
 * üzerine yazarken kalem yarıdan azsa 409 `satir_kaybi_onayi` (`onay` ile yazılır).
 */
export function useSmmYukle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ dosya, yil, ay, uzerineYaz, onay }: { dosya: File; yil?: number; ay?: number; uzerineYaz?: boolean; onay?: boolean }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/yukle", {
          body: {} as never,
          bodySerializer: () =>
            formVerisi({
              dosya,
              ...(yil ? { yil: String(yil) } : {}),
              ...(ay ? { ay: String(ay) } : {}),
              ...(uzerineYaz ? { uzerine_yaz: "true" } : {}),
              ...(onay ? { onay: "true" } : {}),
            }),
        }),
      ),
    onSuccess: () => yuklemeSonrasi(qc),
  });
}

/** SMM Excel'i önizlemesi (yazmaz). */
export function useSmmDonemOnizle() {
  return useMutation({
    mutationFn: ({ dosya, yil, ay }: { dosya: File; yil?: number; ay?: number }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/yukle/onizle", {
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya, ...(yil ? { yil: String(yil) } : {}), ...(ay ? { ay: String(ay) } : {}) }),
        }),
      ),
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

function receteDosyasi(yol: "/api/v1/smm/receteler/onizle" | "/api/v1/smm/receteler/yukle", dosya: File, onay = false) {
  return cagir(api.POST(yol, { body: {} as never, bodySerializer: () => formVerisi({ dosya, ...(onay ? { onay: "true" } : {}) }) }));
}

export function useSmmReceteOnizle() {
  return useMutation({ mutationFn: (dosya: File) => receteDosyasi("/api/v1/smm/receteler/onizle", dosya) });
}

/** Canias dökümünü yükler; ürün yarıdan azsa 409 `satir_kaybi_onayi` (`onay` ile yazılır). */
export function useSmmReceteYukle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ dosya, onay }: { dosya: File; onay?: boolean }) => receteDosyasi("/api/v1/smm/receteler/yukle", dosya, onay),
    onSuccess: () => yuklemeSonrasi(qc),
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

/** Aylık kaynağı yükler; kayıt yarıdan azsa 409 `satir_kaybi_onayi` (`onay` ile yazılır). Yanıtın `yukleme` alanı yazılmayan satırları verir. */
export function useSmmVeriYukle(donemId: number | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kaynak, dosya, onay }: { kaynak: string; dosya: File; onay?: boolean }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/{donem_id}/veri/{kaynak}", {
          params: { path: { donem_id: donemId as number, kaynak } },
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya, ...(onay ? { onay: "true" } : {}) }),
        }),
      ),
    onSuccess: () => yuklemeSonrasi(qc),
  });
}

/** Aylık kaynak önizlemesi (yazmaz): yeni / değişen / aynı / sıfırlanacak, sorunlu satırlar, uyarılar. */
export function useSmmVeriOnizle(donemId: number | null) {
  return useMutation({
    mutationFn: ({ kaynak, dosya }: { kaynak: string; dosya: File }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/{donem_id}/veri/{kaynak}/onizle", {
          params: { path: { donem_id: donemId as number, kaynak } },
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya }),
        }),
      ),
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

/** Hata kodları: kapatırken eksik varsa 409 `kapanis_eksik` (alanlar.eksikler), sonraki dönem kilitliyse 409 `sonraki_kilitli`. */
export const SMM_KAPANIS_EKSIK = "kapanis_eksik";

/** Dönemi kapatır ya da kilidi açar (kilit açma yalnız Genel Direktör). `zorla`: eksikler görüldükten sonra "yine de kapat". */
export function useSmmKilit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, kilitli, zorla }: { donemId: number; kilitli: boolean; zorla?: boolean }) =>
      cagir(
        api.PUT("/api/v1/smm/donemler/{donem_id}/kilit", {
          params: { path: { donem_id: donemId } },
          // zorla yalnız gerektiğinde gönderilir (şemada varsayılanı false)
          body: (zorla ? { kilitli, zorla: true } : { kilitli }) as { kilitli: boolean; zorla: boolean },
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm"] }),
  });
}

/** Açılış stoku önceki dönemin şu anki kapanışıyla aynı mı; farklı kalemlerin ilk 20'si. */
export function useSmmDevirDurumu(donemId: number | null, acik = true) {
  return useQuery({
    queryKey: ["smm", "devir-durumu", donemId],
    enabled: donemId !== null && acik,
    queryFn: () => cagir(api.GET("/api/v1/smm/donemler/{donem_id}/devir-durumu", { params: { path: { donem_id: donemId as number } } })),
  });
}

/** Açılış stokunu önceki dönemin güncel kapanışından yeniden yazar; elle girilmiş açılışlar korunur (`elleEz` ile ezilir). */
export function useSmmDevirYenile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, neden, elleEz }: { donemId: number; neden: string; elleEz?: boolean }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/{donem_id}/devir-yenile", {
          params: { path: { donem_id: donemId } },
          body: { neden, elle_ez: Boolean(elleEz) },
        }),
      ),
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

/** Bütçe (Fiyat Çalışması senaryosu) ile dönemin fiili SMM birim maliyeti; eşleme ürün koduyla. */
export function useSmmButceKiyas(donemId: number | null, senaryoId: number | null) {
  return useQuery({
    queryKey: ["smm", "butce-kiyas", donemId, senaryoId],
    enabled: donemId !== null && senaryoId !== null,
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/butce-kiyas", {
          params: { path: { donem_id: donemId as number }, query: { senaryo: senaryoId as number } },
        }),
      ),
  });
}

/** Dönemlerin SMM tablosu ana satırları (en eski başta); `donemler` boşsa son 6 dönem. */
export function useSmmKarsilastirma(donemler: number[] = []) {
  return useQuery({
    queryKey: ["smm", "karsilastirma", donemler],
    placeholderData: keepPreviousData,
    queryFn: () =>
      cagir(api.GET("/api/v1/smm/karsilastirma", { params: { query: { donemler: donemler.length ? donemler.join(",") : undefined } } })),
  });
}

/** Ürünün aşama aşama birim maliyeti, reçete satırları ve önceki dönemle farkı. */
export function useSmmMaliyetKarti(donemId: number | null, kod: string | null) {
  return useQuery({
    queryKey: ["smm", "maliyet-karti", donemId, kod],
    enabled: donemId !== null && kod !== null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/urun/{kod}/maliyet-karti", {
          params: { path: { donem_id: donemId as number, kod: kod as string } },
        }),
      ),
  });
}

/** Gider dağıtım tablosu: 720 / 730 mizan, aşamalara dağıtılan ve dağıtılmayan, aşama başına işçilik / GÜG, en çok gider alan ürünler. */
export function useSmmGiderDagitimi(donemId: number | null, acik = true) {
  return useQuery({
    queryKey: ["smm", "gider-dagitimi", donemId],
    enabled: donemId !== null && acik,
    queryFn: () => cagir(api.GET("/api/v1/smm/donemler/{donem_id}/gider-dagitimi", { params: { path: { donem_id: donemId as number } } })),
  });
}

/** Tutara göre en büyük sarf farkları (birim uyumsuzlar hariç) ve fazla / eksik özeti. */
export function useSmmSarfOzeti(donemId: number | null, ilk = 20) {
  return useQuery({
    queryKey: ["smm", "sarf-ozet", donemId, ilk],
    enabled: donemId !== null,
    queryFn: () =>
      cagir(
        api.GET("/api/v1/smm/donemler/{donem_id}/sarf-farki/ozet", { params: { path: { donem_id: donemId as number }, query: { ilk } } }),
      ),
  });
}

// ---------------------------------------------------------------- müşavir Excel'i (kendi SMM Excel'i şablon, rakamlar uygulamadan)
export const smmMusavirExcelAdresi = (donemId: number) => `/api/v1/smm/donemler/${donemId}/musavir-excel.xlsx`;

/** Müşavir Excel'inin şablonu: dönemin kendi SMM Excel'i ya da en yakın önceki dönemin; yoksa `sablon: null`. */
export function useSmmMusavirDurum(donemId: number | null) {
  return useQuery({
    queryKey: ["smm", "musavir-excel", donemId],
    enabled: donemId !== null,
    queryFn: () =>
      cagir(api.GET("/api/v1/smm/donemler/{donem_id}/musavir-excel/durum", { params: { path: { donem_id: donemId as number } } })),
  });
}

/** "Müşavir şablonu olarak yalnız sakla" önizlemesi (yazmaz): sayfa adları; SMM Excel'i değilse 422. */
export function useSmmMusavirSablonOnizle() {
  return useMutation({
    mutationFn: ({ donemId, dosya }: { donemId: number; dosya: File }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/{donem_id}/musavir-excel/sablon/onizle", {
          params: { path: { donem_id: donemId } },
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya }),
        }),
      ),
  });
}

/** Dönem verisine dokunmadan yalnız müşavir şablonunu saklar. */
export function useSmmMusavirSablonSakla() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ donemId, dosya }: { donemId: number; dosya: File }) =>
      cagir(
        api.POST("/api/v1/smm/donemler/{donem_id}/musavir-excel/sablon", {
          params: { path: { donem_id: donemId } },
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya }),
        }),
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["smm", "musavir-excel"] }),
  });
}
