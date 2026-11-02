import { http, HttpResponse } from "msw";
import type { HesapYaniti, Teklif } from "@/api/tipler";
import { urunHesapYaniti, urunReceteleri } from "../fikstur/urunMaliyeti";

const T = "*/api/v1";

export interface UrunIstekleri {
  hesapla: Record<string, unknown>[];
  hesaplar: Record<string, unknown>[];
  recete: Record<string, unknown>[][];
  teklifler: Record<string, unknown>[];
  durumlar: { id: string; govde: Record<string, unknown> }[];
}

interface Secenek {
  yanit?: HesapYaniti;
  /** hesapla çağrısı için hata yanıtı üretir (örn. 422). */
  hesaplaHatasi?: (govde: Record<string, unknown>) => Response | null;
}

/** Ürün Maliyeti testlerinin ek MSW işleyicileri; gelen istek gövdelerini `istekler`e yazar. */
export function urunIsleyicileri(secenek: Secenek = {}) {
  const istekler: UrunIstekleri = { hesapla: [], hesaplar: [], recete: [], teklifler: [], durumlar: [] };
  const teklifler: Teklif[] = [];
  const isleyiciler = [
    http.get(`${T}/urunler/:kod/recete`, () => HttpResponse.json(urunReceteleri)),
    http.post(`${T}/urunler/:kod/hesapla`, async ({ request }) => {
      const g = (await request.json()) as Record<string, unknown>;
      istekler.hesapla.push(g);
      const hata = secenek.hesaplaHatasi?.(g);
      if (hata) return hata;
      return HttpResponse.json(secenek.yanit ?? urunHesapYaniti);
    }),
    http.post(`${T}/urunler/:kod/hesaplar`, async ({ request }) => {
      istekler.hesaplar.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ id: 6, olusturan: "Kullanıcı 1", hesap_tarihi: "2026-10-21" }, { status: 201 });
    }),
    http.post(`${T}/urunler/:kod/recete`, async ({ request }) => {
      istekler.recete.push((await request.json()) as Record<string, unknown>[]);
      return HttpResponse.json({ id: 11, versiyon: 3, satir_sayisi: 3 }, { status: 201 });
    }),
    http.get(`${T}/hesaplar/:id/teklifler`, () => HttpResponse.json({ kayitlar: teklifler, toplam: teklifler.length })),
    http.post(`${T}/hesaplar/:id/teklifler`, async ({ request, params }) => {
      const g = (await request.json()) as Record<string, unknown>;
      istekler.teklifler.push(g);
      const t: Teklif = {
        id: teklifler.length + 1,
        maliyet_hesabi_id: Number(params.id),
        tur_no: teklifler.length + 1,
        kar_orani: String(g.kar_orani),
        fiyat_tl: "45.756947",
        fiyat_usd: "0.785494",
        fiyat_eur: null,
        musteri: (g.musteri as string | null) ?? null,
        durum: "taslak",
        notu: (g.notu as string | null) ?? null,
        olusturan: "Kullanıcı 1",
      };
      teklifler.push(t);
      return HttpResponse.json(t, { status: 201 });
    }),
    http.patch(`${T}/teklifler/:id/durum`, async ({ request, params }) => {
      const g = (await request.json()) as { durum: string };
      istekler.durumlar.push({ id: String(params.id), govde: g });
      const t = teklifler.find((x) => x.id === Number(params.id));
      if (t) t.durum = g.durum;
      return HttpResponse.json(t ?? {});
    }),
  ];
  return { isleyiciler, istekler };
}
