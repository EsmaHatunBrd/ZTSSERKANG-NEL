import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, cagir } from "../istemci";
import type { paths } from "../sema";
import type { Sema } from "../tipler";

/** Günlük süzgeçleri; boş değerler istekten çıkarılır. `senaryo` yoksa tüm senaryolar. */
export interface GunlukSuzgeci {
  senaryo?: number | null;
  bas?: string;
  son?: string;
  kullanici?: string;
  tur?: string[];
  urun_kodu?: string;
  q?: string;
  sayfa?: number;
  boyut?: number;
}

export type GunlukSatiri = Sema["GunlukSatiri"];
export type GunlukOzeti = Sema["GunlukOzeti"];

type GunlukSorgusu = NonNullable<paths["/api/v1/gunluk"]["get"]["parameters"]["query"]>;

/** Boş / tanımsız süzgeçleri çıkarır (xlsx adresi ve istek için ortak). */
export function gunlukSorgusu(s: GunlukSuzgeci): GunlukSorgusu {
  const cikis: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(s)) {
    if (v === undefined || v === null || v === "" || (Array.isArray(v) && v.length === 0)) continue;
    cikis[k] = v;
  }
  return cikis as GunlukSorgusu;
}

/** Excel dışa aktarma adresi: sayfa/boyut dışındaki aynı süzgeçler. */
export function gunlukXlsxAdresi(s: GunlukSuzgeci): string {
  const { sayfa: _sayfa, boyut: _boyut, ...geri } = s;
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(gunlukSorgusu(geri))) {
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.set(k, String(v));
  }
  const q = p.toString();
  return `/api/v1/disa-aktar/gunluk.xlsx${q ? `?${q}` : ""}`;
}

export const gunlukAnahtar = {
  liste: (s: GunlukSuzgeci) => ["gunluk", "liste", gunlukSorgusu(s)] as const,
  ozet: (senaryo: number | null | undefined, gun: number) => ["gunluk", "ozet", senaryo ?? null, gun] as const,
};

/** `enabled=false`: senaryo listesi yüklenirken "tüm senaryolar" isteği boşuna atılmasın. */
export function useGunluk(s: GunlukSuzgeci, enabled = true) {
  return useQuery({
    queryKey: gunlukAnahtar.liste(s),
    enabled,
    placeholderData: keepPreviousData,
    queryFn: () => cagir(api.GET("/api/v1/gunluk", { params: { query: gunlukSorgusu(s) } })),
  });
}

/** "Son N gün" özet kartları. */
export function useGunlukOzeti(senaryo: number | null | undefined, gun = 7, enabled = true) {
  return useQuery({
    queryKey: gunlukAnahtar.ozet(senaryo, gun),
    enabled,
    queryFn: () =>
      cagir(api.GET("/api/v1/gunluk/ozet", { params: { query: { ...(senaryo != null ? { senaryo } : {}), gun } } })),
  });
}

/**
 * Günlükteki "geri al": sunucunun verdiği `geri_al.yol`/`govde` mevcut yazma ucuna aynen POST edilir
 * (yeni kayıt olarak eklenir; hiçbir kayıt silinmez/güncellenmez). Yol sorgu dizesi içerir; istemci ara katmanı
 * (kullanıcı başlığı) bu çağrıya da uygulanır.
 */
export function useGunlukGeriAl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (g: { yol: string; govde: Record<string, unknown> }) =>
      cagir(api.POST(g.yol as "/api/v1/senaryolar", { body: g.govde as never })),
    // Geri alma parametre/fiyat/fire/reçete değiştirir: hepsine bağlı ekranlar yenilensin.
    onSuccess: () =>
      Promise.all(
        ["gunluk", "parametreler", "parametre-gecmisi", "malzemeler", "fiyat-gecmisi", "fire-kurallari", "urunler", "urun", "recete", "uyarilar", "hesaplar", "arsiv"].map(
          (k) => qc.invalidateQueries({ queryKey: [k] }),
        ),
      ),
  });
}
