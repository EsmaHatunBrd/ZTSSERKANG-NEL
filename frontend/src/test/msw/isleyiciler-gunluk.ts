import { http, HttpResponse } from "msw";
import { arsivKayitlari, arsivKiyasi, arsivSezonlari, gunlukSatirlari } from "../fikstur/gunluk";

const T = "*/api/v1";

export interface GunlukIstekleri {
  /** GET /gunluk sorguları (tekrarlı alanlar dizi: tur). */
  liste: Record<string, string | string[]>[];
  ozet: Record<string, string>[];
  arsivKayitlari: Record<string, string>[];
  kiyas: Record<string, string>[];
  kilit: { yol: string; govde: { neden: string } }[];
}

export const yeniGunlukIstekleri = (): GunlukIstekleri => ({ liste: [], ozet: [], arsivKayitlari: [], kiyas: [], kilit: [] });

function sorguNesnesi(url: string): Record<string, string | string[]> {
  const p = new URL(url).searchParams;
  const cikis: Record<string, string | string[]> = {};
  p.forEach((_, k) => {
    const v = p.getAll(k);
    cikis[k] = v.length > 1 || k === "tur" ? v : v[0];
  });
  return cikis;
}

/** Tekrarsız sorgu parametreleri (ilk değer). */
function duzSorgu(url: string): Record<string, string> {
  const cikis: Record<string, string> = {};
  new URL(url).searchParams.forEach((v, k) => {
    if (!(k in cikis)) cikis[k] = v;
  });
  return cikis;
}

/** Günlük + arşiv + kilit uçları (uydurma veri). `satirlar` verilirse günlük akışı onlardan gelir. */
export function gunlukIsleyicileri(kayit?: GunlukIstekleri, satirlar = gunlukSatirlari) {
  return [
    http.get(`${T}/gunluk/ozet`, ({ request }) => {
      kayit?.ozet.push(duzSorgu(request.url));
      return HttpResponse.json({
        gun: 7,
        toplam: 4,
        kullanici_bazinda: [
          { kullanici: "Esma", adet: 2 },
          { kullanici: "Ayşe", adet: 1 },
          { kullanici: "sistem", adet: 1 },
        ],
        tur_bazinda: [
          { tur: "parametre", adet: 1 },
          { tur: "hesap", adet: 1 },
        ],
      });
    }),
    http.get(`${T}/gunluk`, ({ request }) => {
      const q = sorguNesnesi(request.url);
      kayit?.liste.push(q);
      const turler = (q.tur as string[] | undefined) ?? [];
      const kul = (q.kullanici as string | undefined)?.toLowerCase();
      const k = satirlar.filter((s) => (turler.length === 0 || turler.includes(s.tur)) && (!kul || s.kullanici.toLowerCase() === kul));
      const sayfa = Number(q.sayfa ?? 1);
      const boyut = Number(q.boyut ?? 50);
      return HttpResponse.json({ kayitlar: k.slice((sayfa - 1) * boyut, sayfa * boyut), toplam: k.length, sayfa, boyut });
    }),
    http.get(`${T}/arsiv/senaryo/:id/kayitlar`, ({ request, params }) => {
      kayit?.arsivKayitlari.push({ id: String(params.id), ...duzSorgu(request.url) });
      const k = params.id === "1" ? arsivKayitlari : [];
      return HttpResponse.json({ kayitlar: k, toplam: k.length, sayfa: 1, boyut: 50 });
    }),
    http.get(`${T}/arsiv/kiyas`, ({ request }) => {
      kayit?.kiyas.push(duzSorgu(request.url));
      return HttpResponse.json(arsivKiyasi);
    }),
    http.get(`${T}/arsiv`, () => HttpResponse.json({ sezonlar: arsivSezonlari })),
    http.post(`${T}/senaryolar/:id/kilitle`, async ({ request, params }) => {
      const govde = (await request.json()) as { neden: string };
      kayit?.kilit.push({ yol: `kilitle/${params.id}`, govde });
      return HttpResponse.json({ id: Number(params.id), sezon_ad: "2026-27", tur: "fiyat_calismasi", ad: "Varsayılan", kilitli: true });
    }),
    http.post(`${T}/senaryolar/:id/kilit-ac`, async ({ request, params }) => {
      const govde = (await request.json()) as { neden: string };
      kayit?.kilit.push({ yol: `kilit-ac/${params.id}`, govde });
      return HttpResponse.json({ id: Number(params.id), sezon_ad: "2026-27", tur: "gerceklesen", ad: "Gerçekleşen", kilitli: false });
    }),
  ];
}
