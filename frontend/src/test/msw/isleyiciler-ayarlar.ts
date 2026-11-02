import { http, HttpResponse } from "msw";
import { ayarDegerleri, ayarTanimlari, bozukHavuz } from "../fikstur/ayarlar";

const T = "*/api/v1";

export interface YazimKaydi {
  fiyat: { kod: string; senaryo: string | null; govde: Record<string, unknown> }[];
  parametre: { anahtar: string; govde: Record<string, unknown> }[];
  havuz: { kod: string; govde: Record<string, unknown> }[];
  ambalaj: unknown[];
}

export function yeniKayit(): YazimKaydi {
  return { fiyat: [], parametre: [], havuz: [], ambalaj: [] };
}

/** Faz 4 Task 6 ekranları için ek işleyiciler; yazma gövdelerini `kayit` içine toplar. */
export function ayarlarIsleyicileri(kayit: YazimKaydi, secenek: { payKontrol?: boolean } = {}) {
  return [
    http.get(`${T}/parametreler/tanimlar`, () =>
      HttpResponse.json({ kayitlar: ayarTanimlari, toplam: ayarTanimlari.length }),
    ),
    http.get(`${T}/parametreler`, () => HttpResponse.json(ayarDegerleri)),
    http.post(`${T}/parametreler/:anahtar/degerler`, async ({ request, params }) => {
      kayit.parametre.push({ anahtar: String(params.anahtar), govde: (await request.json()) as Record<string, unknown> });
      return HttpResponse.json({ id: 9, deger: "x", gecerlilik_basi: "2026-10-21" }, { status: 201 });
    }),
    http.post(`${T}/malzemeler/:kod/fiyatlar`, async ({ request, params }) => {
      kayit.fiyat.push({
        kod: String(params.kod),
        senaryo: new URL(request.url).searchParams.get("senaryo"),
        govde: (await request.json()) as Record<string, unknown>,
      });
      return HttpResponse.json({ id: 9, fiyat: "6", gecerlilik_basi: "2026-10-21" }, { status: 201 });
    }),
    http.get(`${T}/gider-havuzlari`, () =>
      HttpResponse.json({
        kayitlar: [bozukHavuz],
        toplam: 1,
        pay_kontrol: secenek.payKontrol === false ? [] : [{ havuz: "uretim", toplam: "0.567" }],
      }),
    ),
    http.put(`${T}/gider-havuzlari/:kod`, async ({ request, params }) => {
      kayit.havuz.push({ kod: String(params.kod), govde: (await request.json()) as Record<string, unknown> });
      return HttpResponse.json({ ...bozukHavuz, pay_kontrol: [] });
    }),
    http.put(`${T}/ambalaj-siniflari`, async ({ request }) => {
      const g = (await request.json()) as { siniflar: unknown[]; neden: string };
      kayit.ambalaj.push(g);
      return HttpResponse.json({ kayitlar: g.siniflar, toplam: g.siniflar.length });
    }),
  ];
}
