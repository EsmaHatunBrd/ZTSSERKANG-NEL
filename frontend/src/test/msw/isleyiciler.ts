import { http, HttpResponse } from "msw";
import { hesapYaniti } from "../fikstur/hesapYaniti";
import {
  ambalajlar,
  calismaDisiSatir,
  dashboardSatirlari,
  fireKurallari,
  havuzlar,
  kopyalananSayilar,
  malzemeGruplari,
  malzemeler,
  recete,
  RECETESIZ_KOD,
  senaryolar,
  teklifler,
  uyarilar,
} from "../fikstur/urunler";
import { aileTrendi, aileler, urunKarsilastirma } from "../fikstur/karsilastirma";
import { kiyasListesi, kiyasUrun } from "../fikstur/kiyas";
import { tutarlilik } from "../fikstur/tutarlilik";
import { fiyatGecmisi, parametreDegerleri, parametreGecmisi, parametreTanimlari } from "../fikstur/parametreler";

const T = "*/api/v1";

function liste<K>(kayitlar: K[]) {
  return HttpResponse.json({ kayitlar, toplam: kayitlar.length });
}

/** Kaydı olmayan ürünün stok devri yanıtı (sözleşme: 200, alanlar null, stok_etkisi false). */
export const bosStokDevri = (urun_kodu: string) => ({
  urun_kodu,
  adet: null,
  birim_maliyet: null,
  enflasyon: null,
  uretim_adedi: null,
  enflasyon_kullanilan: null,
  uretim_adedi_kullanilan: null,
  uretim_adedi_kaynagi: null,
  guncel_stok_maliyeti: null,
  bu_yil_maliyet: null,
  ortalama_maliyet: null,
  stok_payi: null,
  stok_etkisi: false,
  aciklama: null,
});

export const bulunamadi = (mesaj: string, alanlar: Record<string, unknown> = {}) =>
  HttpResponse.json({ hata: "bulunamadi", mesaj, alanlar }, { status: 404 });

export const dogrulamaHatasi = (alanlar: Record<string, unknown> = { ad: "zorunlu alan" }) =>
  HttpResponse.json({ hata: "dogrulama", mesaj: "istek gövdesi geçersiz", alanlar }, { status: 422 });

export const isleyiciler = [
  // Son yükleme (geri al şeridi): varsayılan "geri alınacak yükleme yok". Testler gerektiğinde `sunucu.use` ile ezer.
  http.get(`${T}/*/son-yukleme`, () => HttpResponse.json({ son: null })),
  // Stokta kalan: varsayılan "kayıt yok" (ürün ekranı fazladan bir şey göstermez). Testler gerektiğinde `sunucu.use` ile ezer.
  http.get(`${T}/urunler/:kod/stok-devri`, ({ params }) => HttpResponse.json(bosStokDevri(String(params.kod)))),
  http.get(`${T}/stok-devri`, () => HttpResponse.json({ kayitlar: [] })),
  http.get(`${T}/senaryolar`, () => liste(senaryolar)),
  http.post(`${T}/senaryolar`, async ({ request }) => {
    const g = (await request.json()) as { sezon_ad: string; tur: string; ad: string };
    if (!g.ad) return dogrulamaHatasi();
    return HttpResponse.json({ id: 3, kilitli: false, urun_sayisi: 0, ...g }, { status: 201 });
  }),
  // Faz 5c: kopyala / düzenle / sil (sözleşme: docs/10-23-2026-faz5c-yeni-calisma-plani.md).
  http.post(`${T}/senaryolar/:id/kopyala`, async ({ params, request }) => {
    const g = (await request.json()) as { sezon_ad: string; ad: string; tur: string; neden?: string };
    if (!g.neden) return dogrulamaHatasi({ neden: "zorunlu alan" });
    if (!senaryolar.some((s) => s.id === Number(params.id))) return bulunamadi("senaryo yok", { id: params.id });
    return HttpResponse.json(
      {
        id: 4,
        sezon_ad: g.sezon_ad,
        ad: g.ad,
        tur: g.tur,
        kilitli: false,
        urun_sayisi: kopyalananSayilar.recete,
        kopyalanan: kopyalananSayilar,
      },
      { status: 201 },
    );
  }),
  http.patch(`${T}/senaryolar/:id`, async ({ params, request }) => {
    const g = (await request.json()) as { sezon_ad?: string; ad?: string; neden?: string };
    const s = senaryolar.find((x) => x.id === Number(params.id));
    if (!s) return bulunamadi("senaryo yok", { id: params.id });
    if (!g.neden) return dogrulamaHatasi({ neden: "zorunlu alan" });
    if (s.kilitli) return HttpResponse.json({ hata: "catisma", mesaj: "Senaryo kilitli", alanlar: {} }, { status: 409 });
    return HttpResponse.json({ ...s, ...(g.ad ? { ad: g.ad } : {}), ...(g.sezon_ad ? { sezon_ad: g.sezon_ad } : {}) });
  }),
  http.delete(`${T}/senaryolar/:id`, ({ params }) =>
    // Fikstürde #2'nin kayıtlı hesabı var sayılır: silinemez.
    params.id === "2"
      ? HttpResponse.json({ hata: "catisma", mesaj: "Kayıtlı hesabı olan senaryo silinemez", alanlar: {} }, { status: 409 })
      : new HttpResponse(null, { status: 204 }),
  ),

  // Ürünler / dashboard
  http.get(`${T}/urunler`, ({ request }) => {
    const p = new URL(request.url).searchParams;
    const gecici = p.get("gecici");
    let k = gecici === null ? dashboardSatirlari : dashboardSatirlari.filter((s) => String(s.gecici_kod) === gecici);
    // Faz 5c: `?tum=1` çalışma dışı (reçetesiz) ürünleri de katar.
    if (p.get("tum") === "true" && gecici !== "true") k = [...k, calismaDisiSatir];
    return HttpResponse.json({ kayitlar: k, toplam: k.length, enflasyon_altinda_toplam: 7 });
  }),
  http.get(`${T}/urunler/:kod/recete/versiyonlar`, () =>
    liste([{ id: 10, versiyon: 2, kaynak: "excel", aktif: true, olusturma_zamani: "2026-10-01T08:00:00+00:00" }]),
  ),
  http.get(`${T}/urunler/:kod/recete`, ({ params }) =>
    params.kod === "YOK"
      ? bulunamadi("ürün yok", { kod: "YOK" })
      : params.kod === RECETESIZ_KOD
        ? HttpResponse.json({ id: null, versiyon: 0, kaynak: "", satirlar: [] })
        : HttpResponse.json(recete),
  ),
  http.post(`${T}/urunler/:kod/recete`, () => HttpResponse.json({ id: 11, versiyon: 3, satir_sayisi: 1 }, { status: 201 })),
  http.post(`${T}/urunler/:kod/recete/kurallara-birak`, () => HttpResponse.json({ id: 12, versiyon: 4, satir_sayisi: 1 }, { status: 201 })),
  http.post(`${T}/urunler/:kod/hesapla`, ({ params }) =>
    params.kod === "YOK" ? bulunamadi("ürün yok", { kod: "YOK" }) : HttpResponse.json({ ...hesapYaniti, urun_kodu: String(params.kod) }),
  ),
  http.get(`${T}/urunler/:kod/hesaplar`, () =>
    liste([{ id: 5, hesap_tarihi: "2026-10-21", olusturan: "Eşma", maliyet_tl: "38.130789", satis_tl: "45.756947" }]),
  ),
  http.post(`${T}/urunler/:kod/hesaplar`, () =>
    HttpResponse.json({ id: 6, olusturan: "Eşma", hesap_tarihi: "2026-10-21" }, { status: 201 }),
  ),
  http.get(`${T}/urunler/:kod`, ({ params }) =>
    params.kod === "YOK"
      ? bulunamadi("ürün yok", { kod: "YOK" })
      : params.kod === RECETESIZ_KOD
        ? HttpResponse.json({
            id: 4,
            kod: params.kod,
            ad: calismaDisiSatir.ad,
            ambalaj_hacmi: "720",
            hat: "Cam Hattı",
            taze_tursu_sinifi: "Taze/Turşu",
            suzme_kg: "0.45",
            pazar: "Yurtiçi",
            aktif: true,
            gecici_kod: false,
            senaryoda: false,
            uretim_hedefi: null,
          })
        : HttpResponse.json({
            id: 1,
            kod: params.kod,
            ad: "Salatalık Turşusu 720 ml",
            ambalaj_hacmi: "720",
            ambalaj_etiket: "720 ml",
            aile: "turşu",
            aile_ad: "turşu",
            hat: "Cam Hattı",
            taze_tursu_sinifi: "tursu",
            suzme_kg: "0.45",
            pazar: "Yurtiçi",
            aktif: true,
            gecici_kod: false,
            senaryoda: true,
          }),
  ),
  http.get(`${T}/hesaplar/:id/teklifler`, () => liste(teklifler)),
  http.post(`${T}/hesaplar/:id/teklifler`, () => HttpResponse.json(teklifler[0], { status: 201 })),
  http.get(`${T}/hesaplar/:id`, ({ params }) =>
    params.id === "0"
      ? bulunamadi("hesap yok", { id: 0 })
      : HttpResponse.json({
          id: Number(params.id),
          urun_id: 1,
          senaryo_id: 1,
          hesap_tarihi: "2026-10-21",
          olusturan: "Eşma",
          girdi_snapshot: {},
          sonuc_snapshot: {},
          uyarilar: [],
          gorunum: hesapYaniti,
        }),
  ),
  http.get(`${T}/uyarilar`, () => liste(uyarilar)),

  // Malzemeler
  http.get(`${T}/malzemeler`, ({ request }) => {
    const p = new URL(request.url).searchParams;
    const fiyatsiz = p.get("fiyatsiz") === "true";
    let k = fiyatsiz ? malzemeler.filter((m) => m.fiyatsiz || m.kart_yok) : malzemeler.filter((m) => !m.kart_yok);
    if (p.get("revize") === "true") k = k.filter((m) => m.revize);
    const q = (p.get("arama") ?? "").toLocaleLowerCase("tr"); // sunucu araması: sayfalamadan önce kod/ad
    if (q) k = k.filter((m) => m.kod.toLocaleLowerCase("tr").includes(q) || (m.ad ?? "").toLocaleLowerCase("tr").includes(q));
    return HttpResponse.json({ kayitlar: k, toplam: k.length });
  }),
  http.get(`${T}/malzemeler/:kod/fiyatlar`, () => liste(fiyatGecmisi)),
  http.post(`${T}/malzemeler/:kod/fiyatlar`, () =>
    HttpResponse.json({ id: 3, fiyat: "6", gecerlilik_basi: "2026-10-21" }, { status: 201 }),
  ),
  http.post(`${T}/import/fiyat-listesi/uygula`, () => HttpResponse.json({ yazilan: 1, kodlar: ["M-001"] })),
  http.post(`${T}/import/fiyat-listesi`, () =>
    HttpResponse.json({ yeni: [{ kod: "M-050", yeni: "3.5" }], degisen: [{ kod: "M-001", eski: "5.9", yeni: "6" }], ayni: 4, hatali: [] }),
  ),
  http.post(`${T}/import/excel-tam`, () => HttpResponse.json({ urun_sayisi: 3, kart_farklari: [], yeniden_adlandirilan: [] })),
  // Müşavir Excel'i: varsayılan şablon yok (testler `sunucu.use` ile şablonlu durumu verir)
  http.get(`${T}/disa-aktar/musavir/fiyat-kitabi/durum`, () => HttpResponse.json({ sablon: null, uyarilar_ozeti: null })),
  http.post(`${T}/import/excel-tam/musavir-sablonu/onizle`, () =>
    HttpResponse.json({ dosya_adi: "kitap.xlsx", sayfalar: ["S.ALMA BF", "Gider Dağıtım", "001"], urun_sayfasi: 1, mevcut: null }),
  ),
  http.post(`${T}/import/excel-tam/musavir-sablonu`, () =>
    HttpResponse.json({ sablon: { dosya_adi: "kitap.xlsx", zaman: "2026-11-17T09:00:00", olusturan: "t", boyut: 1000 } }),
  ),

  // Parametreler
  http.get(`${T}/parametreler/tanimlar`, () => liste(parametreTanimlari)),
  http.get(`${T}/parametreler/:anahtar/gecmis`, () => liste(parametreGecmisi)),
  http.post(`${T}/parametreler/:anahtar/degerler`, () =>
    HttpResponse.json({ id: 3, deger: "52", gecerlilik_basi: "2026-10-21" }, { status: 201 }),
  ),
  http.get(`${T}/parametreler`, () => HttpResponse.json(parametreDegerleri)),

  // Gider, ambalaj, fire
  http.get(`${T}/gider-havuzlari`, () => HttpResponse.json({ kayitlar: havuzlar, toplam: havuzlar.length, pay_kontrol: [] })),
  http.put(`${T}/gider-havuzlari/:kod`, () => HttpResponse.json({ ...havuzlar[0], pay_kontrol: [] })),
  http.get(`${T}/ambalaj-siniflari`, () => liste(ambalajlar)),
  http.put(`${T}/ambalaj-siniflari`, () => liste(ambalajlar)),
  http.get(`${T}/fire-kurallari`, () => liste(fireKurallari)),
  http.post(`${T}/fire-kurallari`, () => HttpResponse.json(fireKurallari[0], { status: 201 })),
  http.get(`${T}/malzeme-gruplari`, () => liste(malzemeGruplari)),
  http.post(`${T}/malzeme-gruplari`, () => HttpResponse.json(malzemeGruplari[0], { status: 201 })),
  http.get(`${T}/degisiklikler`, () => liste([])),

  // Karşılaştırma (Faz 5) ve satış geçmişi
  http.get(`${T}/karsilastirma/urun/:kod`, () => HttpResponse.json(urunKarsilastirma)),
  http.get(`${T}/karsilastirma/aileler`, () => HttpResponse.json(aileler)),
  http.get(`${T}/karsilastirma/aile/:aile`, () => HttpResponse.json(aileTrendi)),

  // Bütçe vs Gerçekleşen (Faz 6). Karşı senaryo varsayılanı yok: Genel Bakış şeridi testlerde görünmez (testler açıkça ekler).
  http.get(`${T}/kiyas/karsi`, () => HttpResponse.json({ karsi: null })),
  http.get(`${T}/kiyas`, () => HttpResponse.json(kiyasListesi)),
  http.get(`${T}/kiyas/urun/:kod`, () => HttpResponse.json(kiyasUrun)),

  // Veri Kontrolü (D7): varsayılan hepsi tamam (Genel Bakış şeridi görünmez; testler açıkça ekler).
  http.get(`${T}/tutarlilik`, () => HttpResponse.json(tutarlilik)),
  http.patch(`${T}/urunler/:kod/aile`, async ({ params, request }) => {
    const g = (await request.json()) as { aile: string | null };
    return HttpResponse.json({ kod: params.kod, aile: (g.aile ?? "turetilen").toLocaleLowerCase("tr"), aile_ad: g.aile ?? "turetilen" });
  }),
  http.get(`${T}/satis-gecmisi`, () =>
    HttpResponse.json({
      kayitlar: [
        {
          id: 1,
          urun_kodu: "URUN-001",
          urun_ad: "Salatalık Turşusu 720 ml",
          musteri: "Müşteri B",
          tarih: "2025-09-01",
          fiyat: "42",
          para_birimi: "TL",
          adet: "100",
          olusturan: "t",
        },
        {
          id: 2,
          urun_kodu: "URUN-001",
          urun_ad: "Salatalık Turşusu 720 ml",
          musteri: "Müşteri A",
          tarih: "2025-10-01",
          fiyat: "43",
          para_birimi: "TL",
          adet: "300",
          olusturan: "t",
        },
        {
          id: 3,
          urun_kodu: "URUN-001",
          urun_ad: "Salatalık Turşusu 720 ml",
          musteri: "Müşteri A",
          tarih: "2025-11-01",
          fiyat: "43",
          para_birimi: "TL",
          adet: "50",
          olusturan: "t",
        },
      ],
      toplam: 3,
    }),
  ),
];
