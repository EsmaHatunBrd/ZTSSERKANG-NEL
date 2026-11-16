import createClient from "openapi-fetch";
import type { paths } from "./sema";
import * as kullanici from "@/yardimcilar/kullanici";

/** Backend'in kararlı ayrıntı kodları (`kod`): durumu mesaj metnine bakmadan tanımak için. */
export const HATA_KODU = { hedefYok: "hedef_yok", parametreEksik: "parametre_eksik" } as const;

/** Backend'in tekdüze hata gövdesi (`{hata, mesaj, alanlar, kod}`) ve HTTP durumu. */
export class ApiHatasi extends Error {
  hata: string;
  mesaj: string;
  alanlar: Record<string, unknown>;
  durum: number;
  /** Kararlı ayrıntı kodu (ör. "hedef_yok"); backend vermediyse null. */
  kod: string | null;

  constructor(hata: string, mesaj: string, alanlar: Record<string, unknown> = {}, durum = 0, kod: string | null = null) {
    super(mesaj);
    this.name = "ApiHatasi";
    this.hata = hata;
    this.mesaj = mesaj;
    this.alanlar = alanlar;
    this.durum = durum;
    this.kod = kod;
  }
}

/**
 * Üretilen şemadaki yollar `/api/v1` önekini zaten içerir; bu yüzden baseUrl yalnızca kök adrestir
 * (geliştirmede Vite `/api` isteklerini backend'e vekiller).
 */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "http://localhost",
  // Çağrı anında çözülür (testlerde MSW'nin fetch'i sonradan yamalaması için).
  fetch: (istek) => globalThis.fetch(istek),
});

/** Yazma sayılmayan POST uçları (hesaplama / önizleme): kullanıcı adı olmadan da çalışır. */
const YAZMA_DEGIL = [/\/hesapla$/, /\/import\/fiyat-listesi$/, /\/onay-ciktisi\/(fiyat|smm)$/];

export const KULLANICI_YOK_MESAJI = "Önce üst bardan adınızı girin";

/**
 * Giriş modu (sunucu girişi zorunlu tutuyorsa GirisKapisi açar): yazan kişi oturum çerezinden gelir, ad başlığı ve yerel ad
 * denetimi yapılmaz. Bir istek 401 dönerse (oturum kapanmış) `oturumDustu` çağrılır: kapı giriş ekranına döner.
 */
let girisModu = false;
let oturumDustu: (() => void) | null = null;

export function girisModunuAyarla(acik: boolean, dustu: (() => void) | null = null): void {
  girisModu = acik;
  oturumDustu = dustu;
}

/** Tamamlanan her API yanıtının özeti (yol, yöntem, başarı): düzenleme kilidi süresini yenilemek gibi yan işler için. */
export interface YanitBilgisi {
  yol: string;
  yontem: string;
  basarili: boolean;
  /** Veri yazan istek mi (GET/HEAD ve hesaplama/önizleme POST'ları değil). */
  yazma: boolean;
}
const yanitDinleyicileri = new Set<(b: YanitBilgisi) => void>();

/** Her API yanıtında çağrılacak dinleyici ekler; dönen işlev aboneliği kaldırır. Dinleyici hatası isteği etkilemez. */
export function yanitDinle(dinleyici: (b: YanitBilgisi) => void): () => void {
  yanitDinleyicileri.add(dinleyici);
  return () => yanitDinleyicileri.delete(dinleyici);
}

/** Hesaplama, önizleme ve onay çıktısı POST'ları veri yazmaz. */
const SALT_OKUNUR_POST = [/\/hesapla$/, /\/onizle$/, /\/import\/fiyat-listesi$/, /\/onay-ciktisi\/(fiyat|smm)$/];

function yanitiBildir(request: Request, response: Response): void {
  if (yanitDinleyicileri.size === 0) return;
  const yol = new URL(request.url).pathname;
  const yontem = request.method.toUpperCase();
  const yazma = yontem !== "GET" && yontem !== "HEAD" && !SALT_OKUNUR_POST.some((r) => r.test(yol));
  for (const d of yanitDinleyicileri) {
    try {
      d({ yol, yontem, basarili: response.ok, yazma });
    } catch {
      /* dinleyici hatası isteği bozmasın */
    }
  }
}

api.use({
  onResponse({ request, response }) {
    yanitiBildir(request, response);
    if (girisModu && response.status === 401 && !new URL(request.url).pathname.startsWith("/api/v1/kimlik/")) oturumDustu?.();
    return response;
  },
  onRequest({ request }) {
    if (girisModu) return request;
    const ad = kullanici.al();
    const yazma = request.method !== "GET" && request.method !== "HEAD";
    if (yazma && !kullanici.adGecerli(ad) && !YAZMA_DEGIL.some((r) => r.test(new URL(request.url).pathname))) {
      // Denetim izi için yazan kişi bilinmeli: istek ağa çıkmadan tekdüze hata gövdesiyle reddedilir.
      return Response.json({ hata: "kullanici_yok", mesaj: KULLANICI_YOK_MESAJI, alanlar: {} }, { status: 400 });
    }
    request.headers.set("X-Kullanici", encodeURIComponent(ad));
    return request;
  },
});

/** openapi-fetch yanıtının yapısal alt kümesi; `D` üretilen şemadaki başarı gövdesinden çıkarılır. */
interface Yanit<D> {
  data?: D;
  error?: unknown;
  response: Response;
}

function govdedenHata(error: unknown, durum: number): ApiHatasi {
  if (typeof error === "object" && error !== null) {
    const g = error as Record<string, unknown>;
    if (typeof g.hata === "string" && typeof g.mesaj === "string") {
      const alanlar = typeof g.alanlar === "object" && g.alanlar !== null ? (g.alanlar as Record<string, unknown>) : {};
      return new ApiHatasi(g.hata, g.mesaj, alanlar, durum, typeof g.kod === "string" ? g.kod : null);
    }
    // FastAPI'nin ham doğrulama gövdesi ({detail: [...]}) — normalde backend bunu çevirir.
    if (Array.isArray(g.detail)) {
      return new ApiHatasi("dogrulama", "İstek gövdesi geçersiz", { detail: g.detail }, durum);
    }
  }
  return new ApiHatasi("sunucu", `Beklenmeyen sunucu yanıtı (HTTP ${durum})`, {}, durum);
}

/**
 * openapi-fetch çağrısını sarar: başarıda veriyi döndürür, hatada `ApiHatasi` fırlatır.
 * Ağ hatası -> `ApiHatasi("ag", "Sunucuya ulaşılamadı")`.
 * Dönüş tipi, çağrının üretilmiş şemadaki (`sema.d.ts`) başarı yanıtından çıkarılır; çağıran tip belirtmez.
 */
export async function cagir<D>(p: Promise<Yanit<D>>): Promise<NonNullable<D>> {
  let sonuc: Yanit<D>;
  try {
    sonuc = await p;
  } catch {
    throw new ApiHatasi("ag", "Sunucuya ulaşılamadı");
  }
  if (sonuc.error !== undefined || !sonuc.response.ok) {
    throw govdedenHata(sonuc.error, sonuc.response.status);
  }
  return sonuc.data as NonNullable<D>;
}

/** Kullanıcıya gösterilecek tek hata metni: mesaj + (varsa) "alan: değer" ayrıntıları. */
export function hataMetni(e: unknown): string {
  if (e instanceof ApiHatasi) {
    const girdiler = Object.entries(e.alanlar ?? {});
    if (girdiler.length === 0) return e.mesaj;
    const ayrinti = girdiler.map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`).join("; ");
    return `${e.mesaj} — ${ayrinti}`;
  }
  return e instanceof Error ? e.message : "Beklenmeyen hata";
}

/** `hataMetni` ama hata yoksa null (diyalogların `hata` prop'u için). */
export function hataMetniVarsa(e: unknown): string | null {
  return e ? hataMetni(e) : null;
}
