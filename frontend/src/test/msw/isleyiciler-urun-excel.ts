import { http, HttpResponse } from "msw";
import { ambalajOzetiVerisi, kapasiteListesi, urunExcelHesapYaniti } from "../fikstur/urunExcel";

const T = "*/api/v1";

export interface UrunExcelIstekleri {
  urunKaydet: { kod: string; govde: Record<string, unknown> }[];
  hedefKaydet: { kod: string; senaryo: string | null; govde: Record<string, unknown> }[];
  kapasiteKaydet: { kod: string; senaryo: string | null; govde: Record<string, unknown> }[];
  kapasiteListe: string[];
  /** POST /urunler/{kod}/kaydet gövdeleri (Faz 4c). */
  topluKaydet: { kod: string; govde: Record<string, unknown> }[];
}

interface Secenek {
  /** Toplu kaydet için hata yanıtı üretir (null = başarılı). */
  kaydetHatasi?: (govde: Record<string, unknown>) => Response | null;
}

/** Faz 4b: kalıcı ürün/hedef kayıtları, hat listesi (gider havuzları), Üretim Adetleri ve ambalaj özeti. Gövdeler `istekler`e yazılır. */
export function urunExcelIsleyicileri(secenek: Secenek = {}) {
  const istekler: UrunExcelIstekleri = { urunKaydet: [], hedefKaydet: [], kapasiteKaydet: [], kapasiteListe: [], topluKaydet: [] };
  const kapasite = kapasiteListesi.kayitlar.map((k) => ({ ...k }));
  const isleyiciler = [
    // Kayıtlı ürün kartı + üretim hedefi (urunExcelHesapYaniti.uretim ile tutarlı).
    http.get(`${T}/urunler/:kod`, ({ params }) =>
      HttpResponse.json({
        id: 1,
        kod: params.kod,
        ad: "Salatalık Turşusu 720 ml",
        ambalaj_hacmi: "720",
        hat: "Niko",
        taze_tursu_sinifi: "Taze/Turşu",
        suzme_kg: "0.45",
        pazar: "Yurtiçi",
        aktif: true,
        gecici_kod: false,
        uretim_hedefi: {
          id: 4,
          vardiya_uretim_adedi: "12000",
          dolum_personel: "6",
          etiketleme_adedi: "3000",
          etiket_personel: "2",
          mal_kabul_miktar_kg: "0.5",
          mal_kabul_fire: "0.05",
          pazarlama_yonetim_uygula: true,
        },
      }),
    ),
    http.get(`${T}/gider-havuzlari`, () =>
      HttpResponse.json({
        kayitlar: [
          // Dolum işçilik havuzu: oran (fikstürde 925) x baz_miktar = toplam_tutar.
          {
            kod: "dolum_iscilik",
            ad: "Dolum işçilik",
            toplam_tutar: "925000",
            baz_tipi: "saniye",
            baz_miktar: "1000",
            anahtarlar: [],
          },
          ...["elektrik", "dogalgaz", "amortisman"].map((kod) => ({
          kod,
          ad: kod,
          toplam_tutar: "1000",
          baz_tipi: "saniye",
          baz_miktar: "3600",
          anahtarlar: [
            { alt_kalem: "Niko", pay_orani: "0.5", baz_miktar: "1" },
            { alt_kalem: "Herbort", pay_orani: "0.5", baz_miktar: "1" },
          ],
          })),
        ],
        toplam: 4,
        pay_kontrol: [],
      }),
    ),
    http.put(`${T}/urunler/:kod`, async ({ request, params }) => {
      const govde = (await request.json()) as Record<string, unknown>;
      istekler.urunKaydet.push({ kod: String(params.kod), govde });
      return HttpResponse.json({
        id: 1,
        kod: params.kod,
        ...govde,
        aktif: true,
        gecici_kod: false,
      });
    }),
    http.put(`${T}/urunler/:kod/uretim-hedefi`, async ({ request, params }) => {
      const govde = (await request.json()) as Record<string, unknown>;
      istekler.hedefKaydet.push({
        kod: String(params.kod),
        senaryo: new URL(request.url).searchParams.get("senaryo"),
        govde,
      });
      return HttpResponse.json({ id: 4, ...govde });
    }),
    http.post(`${T}/urunler/:kod/kaydet`, async ({ request, params }) => {
      const govde = (await request.json()) as Record<string, unknown>;
      istekler.topluKaydet.push({ kod: String(params.kod), govde });
      const hata = secenek.kaydetHatasi?.(govde);
      if (hata) return hata;
      const say = (a: string) => (Array.isArray(govde[a]) ? (govde[a] as unknown[]).length : 0);
      return HttpResponse.json({
        hesap: govde.hesabi_kaydet ? urunExcelHesapYaniti : null,
        hesap_id: govde.hesabi_kaydet ? 7 : null,
        yazilan: {
          urun: govde.urun ? 1 : 0,
          hedef: govde.uretim_hedefi ? 1 : 0,
          recete: say("recete"),
          parametre: say("parametreler"),
          havuz: say("gider_havuzlari"),
        },
        uyarilar: [],
      });
    }),
    http.get(`${T}/uretim-kapasitesi`, ({ request }) => {
      istekler.kapasiteListe.push(new URL(request.url).search);
      return HttpResponse.json({ kayitlar: kapasite, toplam: kapasite.length });
    }),
    http.put(`${T}/uretim-kapasitesi/:kod`, async ({ request, params }) => {
      const govde = (await request.json()) as Record<string, unknown>;
      istekler.kapasiteKaydet.push({
        kod: String(params.kod),
        senaryo: new URL(request.url).searchParams.get("senaryo"),
        govde,
      });
      const i = kapasite.findIndex((k) => k.urun_kodu === params.kod);
      const { neden: _neden, ...alanlar } = govde;
      const yeni = Object.fromEntries(Object.entries(alanlar).map(([a, d]) => [a, String(d)]));
      if (i >= 0) kapasite[i] = { ...kapasite[i], ...yeni } as (typeof kapasite)[number];
      return HttpResponse.json(i >= 0 ? kapasite[i] : {});
    }),
    http.get(`${T}/ambalaj-ozeti`, () => HttpResponse.json(ambalajOzetiVerisi)),
  ];
  return { isleyiciler, istekler };
}
