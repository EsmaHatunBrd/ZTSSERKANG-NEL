import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem, SmmStokTablosu } from "@/api/tipler";
import AnaSayfa from "@/sayfalar/AnaSayfa";
import SmmDonemler, { dosyadanDonem } from "./SmmDonemler";
import SmmStok from "./SmmStok";
import SmmOzet from "./SmmOzet";
import SmmReceteler from "./SmmReceteler";
import SmmSureler from "./SmmSureler";
import SmmVeri from "./SmmVeri";
import SmmSarfFarki from "./SmmSarfFarki";
import SmmUretim from "./SmmUretim";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem: SmmDonem = {
  id: 7,
  yil: 2026,
  ay: 9,
  ad: "Eylül 2026",
  kaynak_dosya: "09-2026 SMM v1.xlsx",
  finansman: "0",
  kalem_sayisi: 2006,
  olusturan: "Esma",
  recete_kaynagi: "excel",
  devir_donem_id: null,
  kilitli: false,
  kilitleyen: null,
  excel_kontrol: {
    karsilastirilan: 2006,
    esit: 1961,
    farkli: 0,
    farkli_ornek: [],
    excelde_sarf_bos: 45,
    excelde_sarf_bos_ornek: ["HM-1"],
    excelde_sarf_bos_tutar: "13793262.71",
    excelde_tekrar: ["AMB-1"],
  },
};

function satir(kod: string, ad: string, tur: string, sarf: string, kontrol = false) {
  return {
    kod,
    ad,
    birim: "KG",
    tur,
    mizan_kodu: "150.01.001",
    dbs_miktar: "100",
    dbs_tutar: "1000",
    alim_miktar: "100",
    alim_tutar: "1400",
    iade_miktar: "0",
    iade_tutar: "0",
    uretim_miktar: "0",
    sayim_miktar: "40",
    satis_miktar: "0",
    sahit_miktar: "0",
    finansman_payi: "0",
    toplam_miktar: "200",
    toplam_tutar: "2400",
    ortalama_fiyat: "12",
    kalan_miktar: "200",
    kalan_tutar: "2400",
    dss_tutar: "480",
    sarf_miktar: sarf,
    sarf_tutar: String(Number(sarf) * 12),
    uretime_giden: String(Number(sarf) * 12),
    kontrol,
  };
}

const stok: SmmStokTablosu = {
  donem,
  toplamlar: {
    dbs_tutar: "1000",
    alim_tutar: "1400",
    finansman_payi: "0",
    iade_tutar: "0",
    dss_tutar: "480",
    sarf_tutar: "1800",
    uretime_giden: "1800",
  },
  kontrol_sayisi: 1,
  turler: [{ tur: "0001-Hammadde", kalem: 2, dbs_tutar: "1000", alim_tutar: "1400", dss_tutar: "480", sarf_tutar: "1800" }],
  kayitlar: [satir("HM-1", "Biber", "0001-Hammadde", "160"), satir("HM-2", "Zeytin", "0001-Hammadde", "-5", true)],
};

describe("SMM", () => {
  it("dosya adından dönem okunur", () => {
    expect(dosyadanDonem("09-2026 SMM v1.xlsx")).toEqual({ ay: 9, yil: 2026 });
    expect(dosyadanDonem("smm.xlsx")).toBeNull();
  });

  it("Excel yüklenir; dönem varsa üzerine yazma onayı sorulur; Excel karşılaştırması gösterilir", async () => {
    let cagri = 0;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })),
      // İlk gönderim: dönem zaten var (409); onaydan sonra ikinci gönderim üzerine yazar.
      http.post(`${T}/smm/donemler/yukle`, () => {
        cagri += 1;
        if (cagri === 1)
          return HttpResponse.json({ hata: "catisma", mesaj: "Eylül 2026 dönemi zaten yüklü", alanlar: {}, kod: null }, { status: 409 });
        return HttpResponse.json(donem);
      }),
    );
    kurSayfa(<SmmDonemler />);
    expect(await screen.findByText(/Henüz dönem yok/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("SMM dosyası"), new File(["x"], "09-2026 SMM v1.xlsx"));
    expect(screen.getByLabelText("Ay")).toHaveValue("9");
    await userEvent.click(screen.getByRole("button", { name: "Yükle" }));
    const d = await screen.findByRole("dialog");
    await userEvent.click(within(d).getByRole("button", { name: "Üzerine yaz" }));
    await waitFor(() => expect(cagri).toBe(2));
    const durum = await screen.findByRole("status");
    expect(durum).toHaveTextContent("Eylül 2026 yüklendi: 2006 stok kalemi");
    expect(durum).toHaveTextContent("1961");
    expect(durum).toHaveTextContent("45 kalemin sarf formülü boş");
  });

  it("stok tablosu: özet, türe göre, kontrol edilecekler süzgeci sunucuya gider", async () => {
    const sorgular: (string | null)[] = [];
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/stok`, ({ request }) => {
        sorgular.push(new URL(request.url).searchParams.get("yalniz_kontrol"));
        return HttpResponse.json(stok);
      }),
    );
    kurSayfa(<SmmStok />);
    expect(await screen.findByText("Biber")).toBeInTheDocument();
    expect(screen.getByLabelText("Kontrol edin")).toBeInTheDocument();
    expect(screen.getByText("Dönem sonu stok (sayım)")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/Yalnız kontrol edilecekler/));
    await waitFor(() => expect(sorgular).toContain("true"));
  });

  it("üretim maliyeti: aşama seçilir, Excel farkı işaretlenir, reçete açılır, dağıtım kaydedilir", async () => {
    const asamalar: (string | null)[] = [];
    let dagitimGovdesi: unknown = null;
    const urun = (kod: string, ad: string, farkli: boolean) => ({
      kod,
      ad,
      birim: "AD",
      uretim_miktar: "100",
      malzeme: "23.47",
      stok_payi: "0",
      iscilik: "3",
      gug: "0",
      fire: "0.2147",
      alim_fiyati: "0",
      alim_kurali: false,
      birim_maliyet: "26.6847",
      toplam: "2668.47",
      satir_sayisi: 2,
      sure_yok: false,
      excel_birim: farkli ? "99" : "26.6847",
      excel_farkli: farkli,
    });
    const ozet = (asama: number, ad: string, farkli: number) => ({
      asama,
      ad,
      urun_sayisi: 2,
      uretilen_urun: 1,
      sure_yok: 0,
      alim_kurali: 0,
      kod_bosluklu: 0,
      excel_elle: 0,
      malzeme: "2347",
      iscilik: "300",
      gug: "0",
      fire: "21.47",
      toplam: "2668.47",
      excel: { karsilastirilan: 2, esit: 2 - farkli, farkli, farkli_ornek: [] },
    });
    const dagitim = {
      havuzlar: [{ anahtar: "50_uretim", ad: "50 · Üretim işçilik + GÜG", tutar: "300", excel: "300", degisti: false }],
      dagitilan: "300",
      mizan_720: "1000",
      mizan_730: "5000",
      dagitilmayan: "5700",
      anahtarlar: [{ anahtar: "50", ad: "50 · İşçilik + GÜG", alan: "dolum_sn", excel_varsayilani: "dolum_sn" }],
    };
    let elleGovdesi: unknown = null;
    sunucu.use(
      http.put(`${T}/smm/donemler/:id/uretim/:asama/:kod/elle`, async ({ request }) => {
        elleGovdesi = await request.json();
        return HttpResponse.json({
          urun: { ...urun("03-1", "Biber 370 etiketli", true), birim_maliyet: "30", elle_alanlar: ["birim_maliyet"] },
          asama: 50,
          satirlar: [],
        });
      }),
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/uretim`, ({ request }) => {
        asamalar.push(new URL(request.url).searchParams.get("asama"));
        return HttpResponse.json({
          donem,
          asama: Number(new URL(request.url).searchParams.get("asama")),
          ozetler: [ozet(20, "Sebze kabul", 0), ozet(40, "Üretim hattı", 0), ozet(50, "Etiketleme", 1)],
          dagitim,
          kayitlar: [urun("03-1", "Biber 370 etiketli", true), urun("03-3", "Zeytin 370", false)],
        });
      }),
      http.get(`${T}/smm/donemler/:id/uretim/:asama/:kod`, () =>
        HttpResponse.json({
          urun: urun("03-1", "Biber 370 etiketli", true),
          asama: 50,
          satirlar: [
            {
              malzeme_kod: "02-1",
              malzeme_ad: "Biber 370",
              miktar: "1",
              birim: "AD",
              carpan: "1",
              fiyat: "21.47",
              fiyat_kaynagi: "asama_40",
              tutar: "21.47",
              fire_orani: "0.01",
              fire_tutari: "0.2147",
            },
          ],
        }),
      ),
      http.put(`${T}/smm/donemler/:id/dagitim`, async ({ request }) => {
        dagitimGovdesi = await request.json();
        return HttpResponse.json(dagitim);
      }),
      // gider dağıtım tablosu (ayrı testi SmmGiderSarf.test.tsx'te): bölüm açılınca istenir
      http.get(`${T}/smm/donemler/:id/gider-dagitimi`, () =>
        HttpResponse.json({ hata: "bulunamadi", mesaj: "bu testte yok", alanlar: {}, kod: null }, { status: 404 }),
      ),
    );
    kurSayfa(<SmmUretim />);
    await screen.findByText("Biber 370 etiketli");
    const tablo = screen.getByRole("table");
    expect(within(tablo).getAllByLabelText("Excel'den farklı")).toHaveLength(1);
    expect(screen.getByText(/1 üründe birim maliyet Excel'in hesapladığından farklı/)).toBeInTheDocument();
    // aşama değişince sunucuya yeni aşama gider
    await userEvent.click(screen.getByRole("button", { name: /40 · Üretim hattı/ }));
    await waitFor(() => expect(asamalar).toContain("40"));
    // ürün satırına tıklayınca reçete çekmecesi
    await userEvent.click(within(screen.getByRole("table")).getByText("Biber 370 etiketli"));
    const cekmece = await screen.findByRole("dialog");
    expect(await within(cekmece).findByText(/40 aşama maliyeti/)).toBeInTheDocument();
    // birim maliyet elle girilir
    await userEvent.click(within(cekmece).getByRole("button", { name: "Birim maliyet elle gir" }));
    const bm = within(cekmece).getByLabelText("Birim maliyet (elle)");
    await userEvent.clear(bm);
    await userEvent.type(bm, "30");
    await userEvent.click(within(cekmece).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(elleGovdesi).toEqual({ alanlar: { birim_maliyet: "30" } }));
    await userEvent.keyboard("{Escape}");
    // dağıtım havuzu değiştirilir
    await userEvent.click(screen.getByText("Dağıtılan işçilik ve genel gider"));
    const kutu = screen.getByLabelText("50 · Üretim işçilik + GÜG");
    await userEvent.clear(kutu);
    await userEvent.type(kutu, "600");
    await userEvent.click(screen.getByRole("button", { name: "Kaydet ve yeniden hesapla" }));
    await waitFor(() => expect(dagitimGovdesi).toEqual({ havuzlar: { "50_uretim": "600" }, anahtarlar: {} }));
    // dağıtım anahtarı değişir
    await userEvent.selectOptions(screen.getByLabelText("Dağıtım anahtarı — 50 · İşçilik + GÜG"), "uretim");
    await waitFor(() => expect(dagitimGovdesi).toEqual({ havuzlar: {}, anahtarlar: { "50": "uretim" } }));
  });

  it("üretim süreleri: satır düzenlenir ve eklenir", async () => {
    const istekler: { yol: string; govde: unknown }[] = [];
    const sure = {
      id: 5,
      kod: "03-1",
      mamul_kod: "03-1",
      yari_mamul_kod: null,
      ad: "Biber 370 etiketli",
      vardiya_uretim: "50000",
      dolum_isci: "12",
      etiket_isci: "6",
      dolum_sn: "1",
      dolum_adam_sn: "6",
      etiket_sn: "1",
      etiket_adam_sn: "3",
    };
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/sureler`, () => HttpResponse.json({ donem, kayitlar: [sure] })),
      http.put(`${T}/smm/sureler/:id`, async ({ request }) => {
        istekler.push({ yol: "put", govde: await request.json() });
        return HttpResponse.json(sure);
      }),
      http.post(`${T}/smm/donemler/:id/sureler`, async ({ request }) => {
        istekler.push({ yol: "post", govde: await request.json() });
        return HttpResponse.json({ ...sure, id: 6, kod: "03-2", mamul_kod: "03-2" }, { status: 201 });
      }),
    );
    kurSayfa(<SmmSureler />);
    await userEvent.click(await screen.findByRole("button", { name: "Düzenle — 03-1" }));
    const kutu = screen.getByLabelText("Dolum sn — 03-1");
    await userEvent.clear(kutu);
    await userEvent.type(kutu, "2");
    await userEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect((istekler[0].govde as Record<string, unknown>).dolum_sn).toBe("2"));
    await userEvent.click(screen.getByRole("button", { name: /Satır ekle/ }));
    expect(screen.getByRole("button", { name: "Ekle" })).toBeDisabled(); // kod zorunlu
    await userEvent.type(screen.getByLabelText("Mamul kodu (50) (yeni)"), "03-2");
    await userEvent.type(screen.getByLabelText("Dolum sn (yeni)"), "1,5");
    await userEvent.click(screen.getByRole("button", { name: "Ekle" }));
    await waitFor(() =>
      expect(istekler[1]).toEqual({ yol: "post", govde: { mamul_kod: "03-2", yari_mamul_kod: null, ad: null, dolum_sn: "1.5" } }),
    );
  });

  it("sarf farkı: toplamlar ve en az fark süzgeci sunucuya gider", async () => {
    const esikler: (string | null)[] = [];
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      // en büyük farklar bölümü (ayrı testi SmmGiderSarf.test.tsx'te)
      http.get(`${T}/smm/donemler/:id/sarf-farki/ozet`, () =>
        HttpResponse.json({
          donem,
          ilk: 20,
          kalem_sayisi: 0,
          kalemler: [],
          ozet: { toplam_fark_tutari: "0", fazla_tutar: "0", eksik_tutar: "0", fazla_sayisi: 0, eksik_sayisi: 0, birim_uyumsuz_sayisi: 0 },
        }),
      ),
      http.get(`${T}/smm/donemler/:id/sarf-farki`, ({ request }) => {
        esikler.push(new URL(request.url).searchParams.get("esik"));
        return HttpResponse.json({
          donem,
          toplamlar: { recete_tutar: "3300000", stok_tutar: "1920000", fazla: "0", eksik: "-1380000" },
          turler: ["0001-Hammadde"],
          kayitlar: [
            {
              kod: "HM-1",
              ad: "Biber",
              birim: "KG",
              tur: "0001-Hammadde",
              ortalama_fiyat: "12",
              recete_sarf: "275",
              stok_sarf: "160",
              fark: "-115",
              fark_tutar: "-1380",
              fark_orani: "-0.4182",
              urun_sayisi: 1,
              kartsiz: false,
              uretim_girisi: "0",
              satis_miktar: "0",
              sahit_miktar: "0",
              birim_uyumsuz: false,
              recete_birimleri: ["KG"],
            },
            {
              kod: "ETK-1",
              ad: "Etiket",
              birim: "AD",
              tur: "0008-Ambalaj Malzeme",
              ortalama_fiyat: "2",
              recete_sarf: "100",
              stok_sarf: "0",
              fark: "-100",
              fark_tutar: "-200",
              fark_orani: "-1",
              urun_sayisi: 2,
              kartsiz: false,
              uretim_girisi: "0",
              satis_miktar: "0",
              sahit_miktar: "0",
              birim_uyumsuz: true,
              recete_birimleri: ["AD", "MT"],
            },
          ],
          birim_uyumsuz_sayisi: 1,
        });
      }),
    );
    kurSayfa(<SmmSarfFarki />);
    await screen.findByText("Biber");
    expect(within(screen.getByRole("table")).getByText("Biber")).toBeInTheDocument();
    expect(screen.getByText("Reçeteye göre sarf")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByLabelText("Birim uyumsuz")).toBeInTheDocument();
    expect(screen.getByText(/Reçetede AD, MT, kartta AD/)).toBeInTheDocument();
    expect(screen.getByText(/1 malzemede reçete birimi kart biriminden farklı/)).toBeInTheDocument();
    expect(esikler[0]).toBe("1000");
    await userEvent.selectOptions(screen.getByLabelText("En az fark"), "100000");
    await waitFor(() => expect(esikler).toContain("100000"));
  });

  it("SMM özeti: tablo, DSS karşılaştırması, mizan uyarısı ve dengeli fiş taslağı", async () => {
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/ozet`, () =>
        HttpResponse.json({
          donem,
          smm: "9090",
          uretim_maliyeti: "9090",
          uretilen: "9090",
          ilk_madde: "3090",
          donem_sonu_stok: "480",
          satilan_hm_ym: "0",
          tablo: [
            {
              hesap: "150",
              ad: "İlk madde ve malzeme",
              kalem: 3,
              sonuc_ad: "710 · İlk madde ve malzeme gideri",
              sonuc: "3090",
              satirlar: [
                { ad: "Dönem başı stok", isaret: "+", tutar: "1250" },
                { ad: "Dönem sonu stok (sayım)", isaret: "−", tutar: "480" },
              ],
            },
          ],
          dss_kiyas: {
            karsilastirilan: 638,
            esit: 638,
            farkli: 0,
            farkli_ornek: [],
            excel_toplam: "718908012.86",
            bizim_toplam: "718908013.14",
          },
          mizan_kiyas: [{ hesap: "150", ad: "İlk madde ve malzeme", mizan: "37840410.83", sayim: "46317687.60", fark: "-8477276.77" }],
          mizan_tarihi: "31.08.2025",
          yansitilan: { "721": "-51754642.62", "731": "-162203116.83" },
          fis: [
            { hesap: "710", ad: "Direkt İlk Madde", aciklama: "İlk madde ve malzeme kullanımı", borc: "3090", alacak: "0" },
            { hesap: "150", ad: "İlk Madde ve Malzeme", aciklama: "İlk madde ve malzeme kullanımı", borc: "0", alacak: "3090" },
          ],
          fis_borc: "3090",
          fis_alacak: "3090",
        }),
      ),
    );
    kurSayfa(<SmmOzet />);
    expect(await screen.findByText("710 · İlk madde ve malzeme gideri")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("638 kalemin 638'i aynı");
    expect(screen.getByText("31.08.2025")).toBeInTheDocument();
    const fis = screen.getByRole("region", { name: "SMM fişi taslağı" });
    expect(within(fis).getAllByText(/3\.090,00/).length).toBeGreaterThanOrEqual(4);
  });

  it("reçeteler: döküm önizlenir ve yüklenir; ürün açılır, alternatif seçilir", async () => {
    let yuklendi = false;
    let secilen: unknown = null;
    const onizleme = {
      satir_sayisi: 6387,
      urun_sayisi: 1171,
      asama: { "20": 336, "40": 240, "50": 595 },
      alternatifli_urun: 42,
      mevcut_urun: 0,
      eklenecek_urun: 1171,
      kalkacak_urun: 0,
      degisecek_urun: 0,
      ornek: [],
    };
    const detay = (secili: string) => ({
      ana_kod: "03-1",
      ana_ad: "Biber 370 etiketli",
      asama: 50,
      secili_alternatif: secili,
      elle: false,
      elle_degistiren: null,
      canias_var: true,
      alternatifler: [
        {
          alternatif: "00",
          satirlar: [
            { id: 11, satir_no: 1, kalem_tipi: 2, malzeme_kod: "ETK-1", malzeme_ad: "Etiket", miktar: "1", birim: "AD", fire_orani: "0" },
          ],
        },
        {
          alternatif: "01",
          satirlar: [
            {
              id: 12,
              satir_no: 1,
              kalem_tipi: 1,
              malzeme_kod: "02-1",
              malzeme_ad: "Biber 370",
              miktar: "1",
              birim: "AD",
              fire_orani: "0.01",
            },
          ],
        },
      ],
    });
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })),
      http.get(`${T}/smm/receteler`, () =>
        HttpResponse.json({
          son_yukleme: yuklendi
            ? { kaynak_dosya: "Reçete.xlsx", satir_sayisi: 6387, urun_sayisi: 1171, olusturan: "Esma", zaman: "2026-11-09T10:00:00" }
            : null,
          asama_sayilari: yuklendi ? { "50": 1 } : {},
          alternatifli_urun: yuklendi ? 1 : 0,
          kayitlar: yuklendi
            ? [
                {
                  ana_kod: "03-1",
                  ana_ad: "Biber 370 etiketli",
                  asama: 50,
                  alternatifler: ["00", "01"],
                  secili_alternatif: "00",
                  satir_sayisi: 1,
                },
              ]
            : [],
        }),
      ),
      http.post(`${T}/smm/receteler/onizle`, () => HttpResponse.json(onizleme)),
      http.post(`${T}/smm/receteler/yukle`, () => {
        yuklendi = true;
        return HttpResponse.json(onizleme);
      }),
      http.get(`${T}/smm/receteler/:kod`, () => HttpResponse.json(detay("00"))),
      http.put(`${T}/smm/receteler/:kod/alternatif`, async ({ request }) => {
        secilen = await request.json();
        return HttpResponse.json(detay("01"));
      }),
    );
    kurSayfa(<SmmReceteler />);
    expect(await screen.findByText(/Henüz reçete yüklenmedi/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("Reçete dosyası"), new File(["x"], "Reçete.xlsx"));
    expect(screen.getByRole("button", { name: "Yükle" })).toBeDisabled(); // önce önizleme
    await userEvent.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByText(/eklenecek 1171/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Yükle" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Yüklendi: 1171 ürün");
    await userEvent.click(await screen.findByText("Biber 370 etiketli"));
    const cekmece = await screen.findByRole("dialog");
    expect(await within(cekmece).findByText("Hesapta kullanılıyor")).toBeInTheDocument();
    await userEvent.click(within(cekmece).getByRole("button", { name: "Bunu kullan" }));
    await waitFor(() => expect(secilen).toEqual({ alternatif: "01" }));
  });

  it("reçete elle düzenlenir: satır güncellenir, satır eklenir, Canias'a döndürülür", async () => {
    const istekler: { yol: string; govde: unknown }[] = [];
    const detay = (elle: boolean) => ({
      ana_kod: "02-1",
      ana_ad: "Biber 370",
      asama: 40,
      kod_asamasi: 40,
      secili_alternatif: "00",
      elle,
      elle_degistiren: elle ? "Esma" : null,
      canias_var: true,
      alternatifler: [
        {
          alternatif: "00",
          satirlar: [
            { id: 21, satir_no: 1, kalem_tipi: 2, malzeme_kod: "AMB-1", malzeme_ad: "Kavanoz", miktar: "1", birim: "AD", fire_orani: "0" },
          ],
        },
      ],
    });
    let elle = false;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })),
      http.get(`${T}/smm/receteler`, () =>
        HttpResponse.json({
          son_yukleme: null,
          asama_sayilari: { "40": 1 },
          alternatifli_urun: 0,
          elle_urun: elle ? 1 : 0,
          kayitlar: [
            { ana_kod: "02-1", ana_ad: "Biber 370", asama: 40, alternatifler: ["00"], secili_alternatif: "00", satir_sayisi: 1, elle },
          ],
        }),
      ),
      http.get(`${T}/smm/receteler/:kod`, () => HttpResponse.json(detay(elle))),
      http.get(`${T}/smm/malzeme-ara`, () => HttpResponse.json([{ kod: "ETK-1", ad: "Etiket", birim: "AD" }])),
      http.put(`${T}/smm/recete-satirlari/:id`, async ({ request, params }) => {
        istekler.push({ yol: `put ${params.id}`, govde: await request.json() });
        elle = true;
        return HttpResponse.json(detay(true));
      }),
      http.post(`${T}/smm/receteler/:kod/satirlar`, async ({ request }) => {
        istekler.push({ yol: "post satir", govde: await request.json() });
        elle = true;
        return HttpResponse.json(detay(true), { status: 201 });
      }),
      http.put(`${T}/smm/receteler/:kod/asama`, async ({ request }) => {
        istekler.push({ yol: "asama", govde: await request.json() });
        return HttpResponse.json(detay(true));
      }),
      http.post(`${T}/smm/receteler/:kod/canias-a-don`, () => {
        istekler.push({ yol: "don", govde: null });
        elle = false;
        return HttpResponse.json(detay(false));
      }),
    );
    kurSayfa(<SmmReceteler />);
    await userEvent.click(await screen.findByText("Biber 370"));
    const cekmece = await screen.findByRole("dialog");
    // satır düzenle: miktar 2, fire %5
    await userEvent.click(await within(cekmece).findByRole("button", { name: "Düzenle — AMB-1" }));
    const mk = within(cekmece).getByLabelText("Miktar — AMB-1");
    await userEvent.clear(mk);
    await userEvent.type(mk, "2");
    const fr = within(cekmece).getByLabelText("Fire % — AMB-1");
    await userEvent.clear(fr);
    await userEvent.type(fr, "5");
    await userEvent.click(within(cekmece).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(istekler[0]).toEqual({ yol: "put 21", govde: { miktar: "2", birim: "AD", fire_orani: "0.05" } }));
    expect(await within(cekmece).findByText("Elle değiştirildi")).toBeInTheDocument();
    // satır ekle: malzeme ara, seç, miktar gir
    await userEvent.click(within(cekmece).getByRole("button", { name: /Satır ekle/ }));
    await userEvent.type(within(cekmece).getByLabelText("Malzeme ara"), "etk");
    await userEvent.click(await within(cekmece).findByRole("button", { name: /Etiket/ }));
    await userEvent.type(within(cekmece).getByLabelText("Yeni satır miktarı"), "1");
    await userEvent.click(within(cekmece).getByRole("button", { name: "Satırı ekle" }));
    await waitFor(() =>
      expect(istekler[1]).toEqual({
        yol: "post satir",
        govde: { alternatif: "00", malzeme_kod: "ETK-1", malzeme_ad: "Etiket", miktar: "1", birim: "AD", fire_orani: "0" },
      }),
    );
    // aşama değiştir
    await userEvent.selectOptions(within(cekmece).getByLabelText("Ürünün aşaması"), "50");
    await waitFor(() => expect(istekler.find((i) => i.yol === "asama")?.govde).toEqual({ asama: 50 }));
    // Canias'a döndür (onaylı)
    await userEvent.click(within(cekmece).getByRole("button", { name: /Canias'a döndür/ }));
    const onay = await screen.findByRole("dialog", { name: "Canias reçetesine dönülsün mü?" });
    await userEvent.click(within(onay).getByRole("button", { name: "Canias'a döndür" }));
    await waitFor(() => expect(istekler.map((i) => i.yol)).toContain("don"));
  });

  it("yeni dönem açılır: devir bilgisi gösterilir", async () => {
    let govde: unknown = null;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.post(`${T}/smm/donemler`, async ({ request }) => {
        govde = await request.json();
        return HttpResponse.json(
          {
            ...donem,
            id: 8,
            ay: 10,
            ad: "Ekim 2026",
            kaynak_dosya: null,
            excel_kontrol: null,
            recete_kaynagi: "ana",
            devir_donem_id: 7,
            devir: { onceki: "Eylül 2026", kalem: 638, tutar: "718908013.14" },
          },
          { status: 201 },
        );
      }),
    );
    kurSayfa(<SmmDonemler />);
    // son dönem Eylül 2026 -> öneri Ekim 2026
    await userEvent.click(await screen.findByRole("button", { name: "Ekim 2026 dönemini aç" }));
    await waitFor(() => expect(govde).toEqual({ yil: 2026, ay: 10 }));
    expect(await screen.findByText(/Eylül 2026 sayımından 638 kalem/)).toBeInTheDocument();
  });

  it("veri girişi: kontrol listesi eksikleri gösterir, kaynak yüklenir, dönem kilitlenir", async () => {
    let yuklenen: string | null = null;
    let kilitGovdesi: unknown = null;
    let kilitli = false;
    const durum = () => ({
      donem: { ...donem, kilitli, kilitleyen: kilitli ? "Esma" : null },
      donem_basi: { kaynak: "devir", dolu: 638, tutar: "718908013.14", hazir: true },
      kaynaklar: [
        { kaynak: "alim", ad: "Alım ve satış", zorunlu: true, yuklendi: false, dolu: 0, son: null },
        { kaynak: "iade", ad: "Alım iadeleri", zorunlu: false, yuklendi: false, dolu: 0, son: null },
      ],
      eksik: ["Alım ve satış"],
      ayarlar: { finansman: "0", gider_720: "61499485.05", gider_730: "228857742.78" },
      turler: [],
    });
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(durum())),
      http.post(`${T}/smm/donemler/:id/veri/:kaynak`, ({ params }) => {
        yuklenen = params.kaynak as string;
        return HttpResponse.json(durum());
      }),
      http.put(`${T}/smm/donemler/:id/kilit`, async ({ request }) => {
        kilitGovdesi = await request.json();
        kilitli = true;
        return HttpResponse.json({ ...donem, kilitli: true, kilitleyen: "Esma" });
      }),
    );
    kurSayfa(<SmmVeri />);
    expect(await screen.findByText(/Eksik:/)).toHaveTextContent("Alım ve satış");
    await userEvent.upload(screen.getByLabelText("Alım ve satış dosyası"), new File(["x"], "alim-rapor.xlsx"));
    await userEvent.click(screen.getAllByRole("button", { name: /Yükle/ })[0]);
    await waitFor(() => expect(yuklenen).toBe("alim"));
    expect(screen.getByRole("link", { name: /SMM fişini Excel olarak indir/ })).toHaveAttribute("href", "/api/v1/smm/donemler/7/fis.xlsx");
    await userEvent.click(screen.getByRole("button", { name: /Dönemi kapat/ }));
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("Eksik veri var: Alım ve satış");
    await userEvent.click(within(onay).getByRole("button", { name: "Kapat ve kilitle" }));
    await waitFor(() => expect(kilitGovdesi).toEqual({ kilitli: true }));
    // Sayfadaki kapanış bandı ve düzenleme kilidi şeridindeki dönem uyarısı ikisi de "kapatıldı" der.
    expect(await screen.findByText(/kapatıldı.*veriler değiştirilemez/)).toBeInTheDocument();
    expect(screen.getByTestId("duzenleme-engel")).toHaveTextContent("Dönem kapatıldı; değişiklik için önce kilidi açın.");
  });

  it("Ana Sayfa'da iş seçilir: Maliyet Muhasebesi bölümleri görünür ve seçim hatırlanır", async () => {
    sunucu.use(http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })));
    kurSayfa(<AnaSayfa />);
    expect(await screen.findByRole("region", { name: "Çalışma" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Maliyet Muhasebesi/ }));
    const bolge = screen.getByRole("region", { name: "Maliyet Muhasebesi" });
    expect(within(bolge).getByRole("link", { name: /Dönemler/ })).toHaveAttribute("href", "/smm");
    expect(within(bolge).getByRole("link", { name: /Stok ve Envanter/ })).toHaveAttribute("href", "/smm/stok");
    expect(screen.queryByRole("region", { name: "Çalışma" })).not.toBeInTheDocument();
    expect(localStorage.getItem("fiyat-calismasi.alan")).toBe("smm");
    // dönem yoksa sıradaki adım: ilk dönemi başlat
    const adim = await screen.findByRole("region", { name: "Bu ay sıradaki adım" });
    expect(adim).toHaveTextContent("İlk dönemi başlatın");
    expect(within(adim).getByRole("link", { name: /Dönemler'e git/ })).toHaveAttribute("href", "/smm");
    localStorage.removeItem("fiyat-calismasi.alan");
  });

  it("sıradaki adım: veri eksikse Veri Girişi'ne, dönem kapalıysa yeni döneme yönlendirir", async () => {
    let kilitli = false;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [{ ...donem, kilitli }] })),
      http.get(`${T}/smm/donemler/:id/veri`, () =>
        HttpResponse.json({
          donem,
          donem_basi: { kaynak: "devir", dolu: 1, tutar: "1", hazir: true },
          kaynaklar: [],
          eksik: ["Sayım (dönem sonu stok)"],
          ayarlar: { finansman: "0", gider_720: "0", gider_730: "0" },
          turler: [],
        }),
      ),
    );
    localStorage.setItem("fiyat-calismasi.alan", "smm");
    const { unmount } = kurSayfa(<AnaSayfa />);
    let adim = await screen.findByRole("region", { name: "Bu ay sıradaki adım" });
    expect(await within(adim).findByText("Eylül 2026 · veriler eksik")).toBeInTheDocument();
    expect(adim).toHaveTextContent("Eksik: Sayım (dönem sonu stok)");
    expect(within(adim).getByRole("link", { name: /Veri Girişi'ne git/ })).toHaveAttribute("href", "/smm/veri?donem=7");
    unmount();
    kilitli = true;
    kurSayfa(<AnaSayfa />);
    adim = await screen.findByRole("region", { name: "Bu ay sıradaki adım" });
    expect(await within(adim).findByText("Eylül 2026 kapatıldı · sırada Ekim 2026")).toBeInTheDocument();
    expect(within(adim).getByRole("link", { name: /Ekim 2026 dönemini aç/ })).toHaveAttribute("href", "/smm");
    localStorage.removeItem("fiyat-calismasi.alan");
  });
});
