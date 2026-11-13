import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { sunucu } from "@/test/msw/sunucu";
import type { SmmButceKiyas as Kiyas, SmmDonem, SmmKarsilastirma, SmmMaliyetKarti as Kart } from "@/api/tipler";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import SmmAylarArasi from "./SmmAylarArasi";
import SmmButceKiyas from "./SmmButceKiyas";
import SmmMaliyetKarti from "./SmmMaliyetKarti";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem = (id: number, ay: number, ad: string) =>
  ({
    id,
    yil: 2026,
    ay,
    ad,
    kaynak_dosya: null,
    finansman: "0",
    kalem_sayisi: 5,
    olusturan: "Esma",
    recete_kaynagi: "excel",
    devir_donem_id: null,
    excel_kontrol: null,
    kilitli: false,
    kilitleyen: null,
  }) as unknown as SmmDonem;
const EYLUL = donem(7, 9, "Eylül 2026");
const EKIM = donem(8, 10, "Ekim 2026");

/** Sayfayı gerçek rota düzeniyle çizer (maliyet kartı :kod parametresi ve satır tıklamasıyla geçiş için). */
function kur(yol: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[yol]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/smm/butce-kiyas" element={<SmmButceKiyas />} />
            <Route path="/smm/aylar-arasi" element={<SmmAylarArasi />} />
            <Route path="/smm/urun/:kod" element={<SmmMaliyetKarti />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const fiili = { malzeme: "23.47", iscilik: "3", gug: "0", fire: "0.2147", stok_payi: "0" };
const butce = { malzeme: "7.375", iscilik: "1", gug: "2", fire: "0.15", uretim_gideri: "3", pazarlama_yonetim: "1", finansman: "2" };
const kiyasSatiri = (kod: string, ad: string, b: string, f: string, fark: string | null, yuzde: string | null, uretim = "100") => ({
  kod,
  ad,
  asama: 50,
  birim: "AD",
  uretim_miktar: uretim,
  uretildi: uretim !== "0",
  butce_maliyet_tl: b,
  butce_finansman_dahil_tl: "30",
  fiili_birim_maliyet_tl: f,
  fark_tl: fark,
  fark_yuzde: yuzde,
  fiili_dokum: fiili,
  butce_dokum: butce,
  alim_kurali: false,
  butce_hatasi: null,
  eslesme: "kod",
});
const KIYAS = {
  donem: EYLUL,
  senaryo: { id: 1, ad: "Bütçe" },
  ozet: {
    eslesen: 3,
    karsilastirilan: 2,
    uretimsiz: 1,
    yalniz_butce: 1,
    yalniz_fiili: 1,
    ortalama_fark_yuzde: "0.14",
    fiili_yuksek: 1,
  },
  kayitlar: [
    kiyasSatiri("03-1", "Biber turşusu 370", "20", "26", "6", "0.3"),
    kiyasSatiri("03-3", "Kornişon 720", "50", "49", "-1", "-0.02"),
    kiyasSatiri("03-2", "Hazır kavanoz", "40", "50", null, null, "0"),
  ],
  yalniz_butce: [{ kod: "SAYFA-001", ad: "Yeni ürün", butce_maliyet_tl: "12.5", stok_kartinda: false, eslesme: "yok" }],
  yalniz_fiili: [{ kod: "03-9", ad: "Bütçesiz ürün", asama: 50, uretim_miktar: "250", fiili_birim_maliyet_tl: "18.4", eslesme: "yok" }],
} as unknown as Kiyas;

const hucre = (donem_id: number, tutar: string, d: string | null = null, y: string | null = null) => ({
  donem_id,
  tutar,
  degisim_tl: d,
  degisim_yuzde: y,
});
function karsilastirma(iki: boolean): SmmKarsilastirma {
  const satir = (anahtar: string, ad: string, a: string, b: string, d: string, y: string, vurgulu = false) => ({
    anahtar,
    ad,
    vurgulu,
    hucreler: iki ? [hucre(7, a), hucre(8, b, d, y)] : [hucre(7, a)],
    son_fark_tl: iki ? d : null,
    son_fark_yuzde: iki ? y : null,
  });
  return {
    donemler: iki ? [EYLUL, EKIM] : [EYLUL],
    satirlar: [
      satir("ilk_madde", "710 · İlk madde ve malzeme gideri", "8000000", "9000000", "1000000", "0.125"),
      satir("iscilik", "720 Direkt işçilik (gider mizanı)", "1000000", "1500000", "500000", "0.5"),
      satir("gug", "730 Genel üretim gideri (gider mizanı)", "5000000", "4000000", "-1000000", "-0.2"),
      satir("uretim_maliyeti", "Üretim maliyeti", "14000000", "14500000", "500000", "0.0357", true),
      satir("smm", "620 · Satılan mamul maliyeti", "13000000", "13650000", "650000", "0.05", true),
    ],
  } as unknown as SmmKarsilastirma;
}

const asama = (
  a: number,
  ad: string,
  kod: string,
  ust: string | null,
  carpan: string | null,
  m: string,
  i: string,
  g: string,
  f: string,
  b: string,
) => ({
  asama: a,
  ad,
  kod,
  urun_ad: `Ürün ${kod}`,
  birim: a === 20 ? "KG" : "AD",
  ust_kod: ust,
  carpan,
  malzeme: m,
  iscilik: i,
  gug: g,
  fire: f,
  stok_payi: "0",
  birim_maliyet: b,
  uretim_miktar: "100",
  alim_kurali: false,
  elle_alanlar: [],
});
const KART = {
  donem: EKIM,
  kod: "03-1",
  ad: "Biber turşusu 370",
  birim: "AD",
  asama: 50,
  birim_maliyet: "29.6847",
  uretim_miktar: "100",
  toplam: "2968.47",
  alim_kurali: false,
  alim_fiyati: "0",
  asamalar: [
    asama(50, "Etiketleme", "03-1", null, null, "23.47", "6", "0", "0.2147", "29.6847"),
    asama(40, "Üretim hattı", "02-1", "03-1", "1", "7.47", "4", "10", "0", "21.47"),
    asama(20, "Sebze kabul", "01-1", "02-1", "0.2", "6", "2", "0", "0.6", "8.6"),
  ],
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
    {
      malzeme_kod: "ETK-1",
      malzeme_ad: "Etiket",
      miktar: "1",
      birim: "AD",
      carpan: "1",
      fiyat: "2",
      fiyat_kaynagi: "envanter",
      tutar: "2",
      fire_orani: "0",
      fire_tutari: "0",
    },
  ],
  onceki: { donem: EYLUL, asama: 50, birim_maliyet: "26.6847", uretim_miktar: "100", fark_tl: "3", fark_yuzde: "0.1124" },
} as unknown as Kart;

describe("SMM Bütçe Kıyası", () => {
  it("özet kutuları, fark renkleri, eşik süzgeci, eşleşmeyenler; satıra tıklayınca maliyet kartı açılır", async () => {
    const istekler: string[] = [];
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [EYLUL] })),
      http.get(`${T}/smm/donemler/:id/butce-kiyas`, ({ request, params }) => {
        istekler.push(`${params.id}?${new URL(request.url).searchParams.toString()}`);
        return HttpResponse.json(KIYAS);
      }),
      http.get(`${T}/smm/donemler/:id/urun/:kod/maliyet-karti`, () => HttpResponse.json(KART)),
    );
    kur("/smm/butce-kiyas?senaryo=1");
    const u = userEvent.setup();
    expect(await screen.findByText("Biber turşusu 370")).toBeInTheDocument();
    expect(istekler[0]).toBe("7?senaryo=1"); // dönem: en yeni; senaryo: seçili fiyat çalışması
    expect(screen.getByLabelText("Fiyat çalışması")).toHaveValue("1");
    // özet
    expect(screen.getByText("3 · 2 üretildi")).toBeInTheDocument();
    expect(screen.getByText("+14,0 %")).toBeInTheDocument();
    expect(screen.getByText("1 bütçede · 1 fiilide")).toBeInTheDocument();
    // fark: fiili > bütçe kırmızı, altında yeşil, üretim yoksa tire
    const satir = (ad: string) => screen.getByText(ad).closest("tr") as HTMLElement;
    expect(within(satir("Biber turşusu 370")).getByText("+6,00 TL")).toHaveClass("text-red-600");
    expect(within(satir("Biber turşusu 370")).getByText("+30,0 %")).toHaveClass("text-red-600");
    expect(within(satir("Kornişon 720")).getByText("-2,0 %")).toHaveClass("text-green-700");
    expect(within(satir("Hazır kavanoz")).getByText("üretim yok")).toBeInTheDocument();
    expect(within(satir("Hazır kavanoz")).getAllByText("—").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("3 / 3 ürün")).toBeInTheDocument();
    // eşik süzgeci: %10 üstü yalnız 03-1; eşik 1 olunca 03-3 de gelir; farkı olmayan hiç gelmez
    await u.click(screen.getByRole("checkbox", { name: /Yalnız farkı/ }));
    expect(screen.getByText("1 / 3 ürün")).toBeInTheDocument();
    expect(screen.queryByText("Kornişon 720")).not.toBeInTheDocument();
    const esik = screen.getByLabelText("Fark eşiği (yüzde)");
    await u.clear(esik);
    await u.type(esik, "1");
    expect(screen.getByText("2 / 3 ürün")).toBeInTheDocument();
    expect(screen.queryByText("Hazır kavanoz")).not.toBeInTheDocument();
    // eşleşmeyenler katlanır bölümde, iki ayrı liste
    expect(screen.getByText("1 ürün yalnız bütçede · 1 üretilen ürün yalnız fiilide")).toBeInTheDocument();
    const yb = screen.getByRole("table", { name: "Yalnız bütçede olan ürünler" });
    expect(within(yb).getByText("SAYFA-001")).toBeInTheDocument();
    const yf = screen.getByRole("table", { name: "Yalnız fiilide olan ürünler" });
    expect(within(yf).getByText("Bütçesiz ürün")).toBeInTheDocument();
    // satıra tıkla -> ürün maliyet kartı (aynı dönem)
    await u.click(screen.getByRole("cell", { name: /Biber turşusu 370/ }));
    expect(await screen.findByRole("heading", { name: "Biber turşusu 370", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("Toplam birim maliyet")).toBeInTheDocument();
  });

  it("dönem yokken yönlendirme metni; sunucu hatası tabloda gösterilir", async () => {
    sunucu.use(http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })));
    const { unmount } = kur("/smm/butce-kiyas?senaryo=1");
    expect(await screen.findByText(/Henüz dönem yok/)).toBeInTheDocument();
    unmount();
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [EYLUL] })),
      http.get(`${T}/smm/donemler/:id/butce-kiyas`, () =>
        HttpResponse.json({ hata: "bulunamadi", mesaj: "senaryo yok", alanlar: {}, kod: null }, { status: 404 }),
      ),
    );
    kur("/smm/butce-kiyas?senaryo=1");
    expect(await screen.findByText(/senaryo yok/)).toBeInTheDocument();
  });
});

describe("SMM Aylar Arası", () => {
  it("iki dönem: sütunlar en eski solda, hücrede değişim %, son iki ay farkı ve grafik; dönem seçimi sorguya gider", async () => {
    const sorgular: (string | null)[] = [];
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [EKIM, EYLUL] })),
      http.get(`${T}/smm/karsilastirma`, ({ request }) => {
        const d = new URL(request.url).searchParams.get("donemler");
        sorgular.push(d);
        return HttpResponse.json(karsilastirma(d !== "8"));
      }),
    );
    kur("/smm/aylar-arasi");
    const tablo = await screen.findByRole("table", { name: "Dönemlere göre SMM tablosu" });
    expect(sorgular[0]).toBeNull(); // seçim yok: sunucu son 6 dönemi verir
    const basliklar = within(tablo)
      .getAllByRole("columnheader")
      .map((x) => x.textContent);
    expect(basliklar).toEqual(["Kalem", "Eylül 2026", "Ekim 2026", "Son iki ay farkı"]);
    const isc = within(tablo).getByRole("row", { name: /720 Direkt işçilik/ });
    expect(within(isc).getByText("1.000.000 TL")).toBeInTheDocument();
    expect(within(isc).getByText("1.500.000 TL")).toBeInTheDocument();
    expect(within(isc).getAllByText("+50,0 %")).toHaveLength(2); // hücre altı + son sütun
    expect(within(isc).getByText("+500.000 TL")).toBeInTheDocument();
    const gug = within(tablo).getByRole("row", { name: /730 Genel üretim/ });
    expect(within(gug).getByText("-1.000.000 TL").closest("td")).toHaveClass("text-green-700"); // azalış yeşil
    expect(within(tablo).getByRole("row", { name: /620 · Satılan mamul maliyeti/ })).toHaveClass("bg-kart-yesil");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Dönemlere göre maliyet unsurları ve SMM/ })).toHaveAccessibleName(
      /Eylül 2026: SMM 13,0 mn TL; Ekim 2026: SMM 13,7 mn TL/,
    );
    // Eylül'ü kapat: yalnız Ekim istenir; tek dönem notu çıkar, grafik ve fark sütunu kalkar
    const u = userEvent.setup();
    expect(screen.getByRole("button", { name: "Eylül 2026" })).toHaveAttribute("aria-pressed", "true");
    await u.click(screen.getByRole("button", { name: "Eylül 2026" }));
    await waitFor(() => expect(sorgular.at(-1)).toBe("8"));
    expect(await screen.findByRole("note")).toHaveTextContent("Karşılaştırma için ikinci dönem gerekir");
    expect(screen.queryByText("Son iki ay farkı")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /maliyet unsurları/ })).not.toBeInTheDocument();
  });

  it("tek dönem: tek sütun, bilgi notu, grafik yok", async () => {
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [EYLUL] })),
      http.get(`${T}/smm/karsilastirma`, () => HttpResponse.json(karsilastirma(false))),
    );
    kur("/smm/aylar-arasi");
    const tablo = await screen.findByRole("table", { name: "Dönemlere göre SMM tablosu" });
    expect(within(tablo).getAllByRole("columnheader")).toHaveLength(2);
    expect(screen.getByRole("note")).toHaveTextContent("Karşılaştırma için ikinci dönem gerekir");
    expect(screen.queryByRole("group", { name: "Dönemler" })).not.toBeInTheDocument();
    // Tek dönemde aylar arası grafik yok; son dönemin maliyet dağılımı (halka) grafiği var.
    expect(screen.queryByRole("region", { name: "Grafik" })).not.toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /üretim maliyeti dağılımı/ })).toBeInTheDocument();
    expect(within(tablo).queryByText(/%/)).not.toBeInTheDocument();
  });
});

describe("SMM ürün maliyet kartı", () => {
  it("toplam ve önceki aya fark, aşama tablosu ve grafiği, reçete satırları, yazdır", async () => {
    const istekler: string[] = [];
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [EKIM, EYLUL] })),
      http.get(`${T}/smm/donemler/:id/urun/:kod/maliyet-karti`, ({ params }) => {
        istekler.push(`${params.id}/${params.kod}`);
        return HttpResponse.json(KART);
      }),
    );
    const { container } = kur("/smm/urun/03-1?donem=8");
    expect(await screen.findByRole("heading", { name: "Biber turşusu 370", level: 1 })).toBeInTheDocument();
    expect(istekler).toEqual(["8/03-1"]);
    expect(container.querySelector("[data-yazdir]")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Yazdır" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Üretim Maliyeti/ })).toHaveAttribute("href", "/smm/uretim?donem=8");
    // üst: toplam + önceki aya fark (artış kırmızı)
    const toplam = screen.getByText("Toplam birim maliyet").parentElement as HTMLElement;
    expect(within(toplam).getByText("29,6847 TL")).toBeInTheDocument();
    const onceki = screen.getByText("Önceki aya göre").parentElement as HTMLElement;
    expect(onceki).toHaveTextContent("+3,0000 TL");
    expect(onceki).toHaveTextContent("(+11,2 %)");
    expect(onceki).toHaveTextContent("Eylül 2026: 26,6847 TL");
    expect(within(onceki).getByText(/\+3,0000 TL/)).toHaveClass("text-red-600");
    // aşama tablosu: 50 -> 40 -> 20
    const asamalar = screen.getByRole("table", { name: "Aşamalara göre birim maliyet dökümü" });
    const satirlar = within(asamalar).getAllByRole("row").slice(1);
    expect(satirlar.map((r) => within(r).getByRole("rowheader").textContent?.slice(0, 8))).toEqual(["50 · Eti", "40 · Üre", "20 · Seb"]);
    expect(within(satirlar[1]).getByText("10,0000 TL")).toBeInTheDocument(); // 40 GÜG
    expect(within(satirlar[2]).getByRole("rowheader")).toHaveTextContent("üst ürünün biriminde 0,2000 KG");
    expect(await screen.findByRole("img", { name: /Aşamalara göre birim maliyet dökümü/ })).toHaveAccessibleName(
      /40 Üretim hattı \(02-1\): 21,47 TL/,
    );
    // reçete
    const recete = screen.getByRole("table", { name: "Reçete satırları" });
    expect(within(recete).getByText("Biber 370")).toBeInTheDocument();
    expect(within(recete).getByText(/02-1 · 40 aşama maliyeti/)).toBeInTheDocument();
    expect(within(recete).getByText("0,2147 TL")).toBeInTheDocument();
  });

  it("önceki dönem yoksa fark yerine açıklama; ürün bulunamazsa hata", async () => {
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [EYLUL] })),
      http.get(`${T}/smm/donemler/:id/urun/:kod/maliyet-karti`, ({ params }) =>
        params.kod === "YOK"
          ? HttpResponse.json(
              { hata: "bulunamadi", mesaj: "bu dönemde ürünün aşama reçetesi bulunamadı", alanlar: {}, kod: null },
              { status: 404 },
            )
          : HttpResponse.json({ ...KART, donem: EYLUL, onceki: null }),
      ),
    );
    const { unmount } = kur("/smm/urun/03-1");
    expect(await screen.findByText("Önceki dönemde bu ürünün maliyeti yok.")).toBeInTheDocument();
    unmount();
    kur("/smm/urun/YOK");
    expect(await screen.findByRole("alert")).toHaveTextContent("bu dönemde ürünün aşama reçetesi bulunamadı");
    expect(screen.queryByText("Toplam birim maliyet")).not.toBeInTheDocument();
  });
});
