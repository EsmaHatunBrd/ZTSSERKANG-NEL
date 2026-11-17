import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";

/**
 * Çok parçalı (multipart) yüklemeler: openapi-fetch gövdeyi bodySerializer ile FormData yapar
 * (Content-Type tarayıcıya bırakılır). Üretilen gövde tipi dosyayı string saydığından body `never` ile geçilir.
 */
export function formVerisi(alanlar: Record<string, string | Blob | boolean | number | string[] | null | undefined>): FormData {
  const f = new FormData();
  for (const [k, v] of Object.entries(alanlar)) {
    if (v === null || v === undefined) continue;
    // Dizi: aynı ad tekrarlanır (FastAPI `list[str] = Form(...)`).
    if (Array.isArray(v)) for (const x of v) f.append(k, x);
    else f.append(k, v instanceof Blob ? v : String(v));
  }
  return f;
}

export interface FiyatOnizleDegiskenleri {
  dosya: File;
  senaryo: number;
  gecerlilik_basi?: string;
  /** Elle girilmiş fiyatların da üzerine yazılsın mı (varsayılan: korunur). */
  elle_ustune_yaz?: boolean;
}

export function useImportFiyatOnizle() {
  return useMutation({
    mutationFn: ({ dosya, senaryo, gecerlilik_basi, elle_ustune_yaz }: FiyatOnizleDegiskenleri) =>
      cagir(
        api.POST("/api/v1/import/fiyat-listesi", {
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya, senaryo, gecerlilik_basi, elle_ustune_yaz }),
        }),
      ),
  });
}

export interface FiyatUygulaDegiskenleri {
  dosya: File;
  senaryo: number;
  gecerlilik_basi: string;
  neden: string;
  elle_ustune_yaz?: boolean;
}

export function useImportFiyatUygula() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ dosya, senaryo, gecerlilik_basi, neden, elle_ustune_yaz }: FiyatUygulaDegiskenleri) =>
      cagir(
        api.POST("/api/v1/import/fiyat-listesi/uygula", {
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya, senaryo, gecerlilik_basi, neden, elle_ustune_yaz }),
        }),
      ),
    onSuccess: () =>
      Promise.all(
        ["malzemeler", "fiyat-gecmisi", "urunler", "uyarilar", "son-yukleme"].map((k) => qc.invalidateQueries({ queryKey: [k] })),
      ),
  });
}

export interface ExcelTamDegiskenleri {
  dosya: File;
  /** "Yeni senaryo" modunda zorunlu; `senaryo_id` verilirse sunucu bu üçünü yok sayar. */
  sezon_ad?: string;
  senaryo_ad?: string;
  tur?: "fiyat_calismasi" | "gerceklesen";
  kartlari_guncelle?: boolean;
  /** "Mevcut senaryoyu tamamla" modu: yalnız bu senaryoda eksik olanlar eklenir. */
  senaryo_id?: number;
}

export function useImportExcelTam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (d: ExcelTamDegiskenleri) =>
      cagir(
        api.POST("/api/v1/import/excel-tam", {
          body: {} as never,
          bodySerializer: () => formVerisi({ ...d }),
        }),
      ),
    // Her şey değişebilir (yeni senaryo, kartlar, fiyatlar): tüm önbelleği yenile.
    onSuccess: () => qc.invalidateQueries(),
  });
}

/** Müşavir Excel'i şablonu: aktarım yapmadan yalnız kitabı saklamadan önceki denetim (sayfa adları, ürün sayfası sayısı). */
export function useMusavirSablonuOnizle() {
  return useMutation({
    mutationFn: ({ dosya, senaryo }: { dosya: File; senaryo: number }) =>
      cagir(
        api.POST("/api/v1/import/excel-tam/musavir-sablonu/onizle", {
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya, senaryo }),
        }),
      ),
  });
}

/** Kitabı yalnız müşavir şablonu olarak saklar (senaryo verisine dokunmaz). */
export function useMusavirSablonuSakla() {
  return useMutation({
    mutationFn: ({ dosya, senaryo }: { dosya: File; senaryo: number }) =>
      cagir(
        api.POST("/api/v1/import/excel-tam/musavir-sablonu", {
          body: {} as never,
          bodySerializer: () => formVerisi({ dosya, senaryo }),
        }),
      ),
  });
}
