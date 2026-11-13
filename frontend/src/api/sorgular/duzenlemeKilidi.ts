import { api, cagir } from "../istemci";

/**
 * Düzenleme kilidinin açıldığını sunucuya bildirir (Değişiklik Günlüğü'nde "Düzenleme kilidi açıldı").
 * Üretilen şema (`sema.d.ts`) paylaşımlı olduğu ve başka iş kollarınca yeniden üretildiği için yol burada gevşek tipli çağrılır
 * (`smmStok.ts` kalıbı); istemcinin ara katmanı (kullanıcı başlığı, 401, hata gövdesi) aynen uygulanır.
 */
interface GevsekIstemci {
  POST(yol: string, secenek: object): Promise<{ data?: unknown; error?: unknown; response: Response }>;
}
const gevsek = api as unknown as GevsekIstemci;

export interface DuzenlemeKilidiAcGiris {
  senaryo_id: number | null;
  /** Kilidin açıldığı sayfanın yolu (ör. "/fiyatlar"). */
  sayfa: string;
}

export interface DuzenlemeKilidiAcCikis {
  kayit_id: number;
  sayfa: string;
  senaryo_id: number | null;
  kullanici: string;
}

export function duzenlemeKilidiAcildiBildir(g: DuzenlemeKilidiAcGiris): Promise<DuzenlemeKilidiAcCikis> {
  return cagir(gevsek.POST("/api/v1/duzenleme-kilidi/ac", { body: g })) as Promise<DuzenlemeKilidiAcCikis>;
}
