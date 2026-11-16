import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactElement } from "react";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem } from "@/api/tipler";
import { OturumSaglayici } from "@/bilesenler/GirisKapisi";
import SmmDonemler from "./SmmDonemler";
import SmmReceteler from "./SmmReceteler";
import SmmStok from "./SmmStok";
import SmmSureler from "./SmmSureler";
import SmmUretim from "./SmmUretim";
import SmmVeri from "./SmmVeri";

// SMM ekranları Fiyat Çalışması'yla aynı düzenleme kilidini kullanır: kilitliyken yazma eylemleri devre dışı, "Düzenlemeyi aç" + onayla
// etkin. Test kurulumu kilidi varsayılan AÇIK başlatır; buradaki testler `kilitle()` ile kilitli başlar.

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem = {
  id: 7,
  yil: 2026,
  ay: 10,
  ad: "Ekim 2026",
  kaynak_dosya: null,
  finansman: "0",
  kalem_sayisi: 2,
  olusturan: "Esma",
  recete_kaynagi: "ana",
  devir_donem_id: null,
  kilitli: false,
  kilitleyen: null,
  excel_kontrol: null,
} as unknown as SmmDonem;

/** Kilidi kapatır ve kilit açma bildirimini yakalar. */
function kilitle() {
  sessionStorage.removeItem("fiyat-calismasi.duzenleme-acik-bitis");
  const bildirimler: unknown[] = [];
  sunucu.use(
    http.post(`${T}/duzenleme-kilidi/ac`, async ({ request }) => {
      bildirimler.push(await request.json());
      return HttpResponse.json({ kayit_id: 1, sayfa: "/", senaryo_id: null, kullanici: "Test" }, { status: 201 });
    }),
  );
  return bildirimler;
}

async function duzenlemeyiAc() {
  await userEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
  await userEvent.click(await screen.findByRole("button", { name: "Evet, aç" }));
  await waitFor(() => expect(screen.getByTestId("duzenleme-kilidi")).toHaveAttribute("data-durum", "acik"));
}

function oturumla(rol: string, eleman: ReactElement) {
  const kullanici = { id: 1, kullanici_adi: "x", ad: "X", rol, rol_ad: rol, aktif: true, sifre_degismeli: false } as never;
  return <OturumSaglayici deger={{ girisZorunlu: true, kullanici }}>{eleman}</OturumSaglayici>;
}

function veriDurumu(d: SmmDonem) {
  return {
    donem: d,
    donem_basi: { kaynak: "devir", dolu: 2, tutar: "480", hazir: true },
    kaynaklar: [{ kaynak: "alim", ad: "Alım ve satış", zorunlu: true, yuklendi: true, dolu: 2, son: null, elle: 0, elle_uyari: null }],
    eksik: [],
    ayarlar: { finansman: "0", gider_720: "2000", gider_730: "3000" },
    turler: [],
    grupsuz: { kalem: 0, alim_tutar: "0", dbs_tutar: "0", ornek: [] },
    devir: null,
  };
}

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

function sureleriTanimla(d: SmmDonem = donem) {
  sunucu.use(
    http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [d] })),
    http.get(`${T}/smm/donemler/:id/sureler`, () => HttpResponse.json({ donem: d, kayitlar: [sure] })),
  );
}

describe("SMM düzenleme kilidi", () => {
  it("Dönemler: kilitliyken yeni dönem, Excel yükleme ve silme kapalı; onayla açılır ve günlüğe senaryosuz yazılır", async () => {
    const bildirimler = kilitle();
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.post(`${T}/smm/donemler/yukle/onizle`, () =>
        HttpResponse.json({
          ...{ okunan: 10, yeni: 10, degisen: 0, ayni: 0, silinecek: 0, atlanan: 0, sorunlu: [], uyarilar: [] },
          ...{ yil: 2026, ay: 10, donem_ad: "Ekim 2026", mevcut_donem_id: donem.id, kilitli: false, kalem: 10, mevcut_kalem: 10 },
          ...{ recete_satiri: 0, iscilik: 0, sayfalar: ["DBS"] },
        }),
      ),
      http.get(`${T}/smm/donemler/:id/son-yukleme`, () => HttpResponse.json({ son: null })),
    );
    kurSayfa(<SmmDonemler />);
    const sil = await screen.findByRole("button", { name: "Sil — Ekim 2026" });
    const yeni = screen.getByRole("button", { name: "Kasım 2026 dönemini aç" });
    expect(screen.getByTestId("duzenleme-kilidi")).toHaveAttribute("data-durum", "kilitli");
    expect(yeni).toBeDisabled();
    expect(sil).toBeDisabled();
    expect(screen.getByLabelText("Reçete kaynağı — Ekim 2026")).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("SMM dosyası"), new File(["x"], "10-2026 SMM.xlsx"));
    // Önizleme okumadır: kilitliyken de yapılır; önizleme kutusundaki "Yükle" kapalı kalır.
    await userEvent.click(screen.getByRole("button", { name: "Önizle" }));
    const on = await screen.findByRole("region", { name: "Önizleme" });
    expect(within(on).getByRole("button", { name: "Yükle" })).toBeDisabled();

    await duzenlemeyiAc();
    expect(yeni).toBeEnabled();
    expect(sil).toBeEnabled();
    expect(within(on).getByRole("button", { name: "Yükle" })).toBeEnabled();
    await waitFor(() => expect(bildirimler).toEqual([{ senaryo_id: null, sayfa: "/" }]));
  });

  it("Veri Girişi: kilitliyken kaynak yükleme ve gider tutarları kapalı; açınca etkin", async () => {
    kilitle();
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(veriDurumu(donem))),
    );
    kurSayfa(<SmmVeri />);
    const gider = await screen.findByLabelText("720 Direkt işçilik");
    expect(gider).toBeDisabled();
    expect(screen.getByLabelText("Alım ve satış dosyası")).toBeDisabled();
    await duzenlemeyiAc();
    expect(gider).toBeEnabled();
    expect(screen.getByLabelText("Alım ve satış dosyası")).toBeEnabled();
  });

  it("Veri Girişi: dönemi kapatmak düzenleme kilidinden bağımsızdır", async () => {
    kilitle();
    let govde: unknown = null;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(veriDurumu(donem))),
      http.put(`${T}/smm/donemler/:id/kilit`, async ({ request }) => {
        govde = await request.json();
        return HttpResponse.json({ ...donem, kilitli: true });
      }),
    );
    kurSayfa(<SmmVeri />);
    const kapat = await screen.findByRole("button", { name: /Dönemi kapat/ });
    expect(screen.getByTestId("duzenleme-kilidi")).toHaveAttribute("data-durum", "kilitli");
    expect(kapat).toBeEnabled();
    await userEvent.click(kapat);
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Kapat ve kilitle" }));
    await waitFor(() => expect(govde).toEqual({ kilitli: true }));
  });

  it("Veri Girişi: dönem kapalıysa düzenleme açık olsa da yazılamaz; kilit açma (Genel Direktör) yine çalışır", async () => {
    // Düzenleme kilidi AÇIK (test varsayılanı), dönem kapalı.
    const kapali = { ...donem, kilitli: true, kilitleyen: "Esma" } as SmmDonem;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [kapali] })),
      http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(veriDurumu(kapali))),
    );
    kurSayfa(<SmmVeri />);
    const gider = await screen.findByLabelText("720 Direkt işçilik");
    expect(screen.getByTestId("duzenleme-kilidi")).toHaveAttribute("data-durum", "acik");
    expect(screen.getByTestId("duzenleme-engel")).toHaveTextContent("Dönem kapatıldı; değişiklik için önce kilidi açın.");
    expect(gider).toBeDisabled();
    expect(screen.queryByLabelText("Alım ve satış dosyası")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kilidi aç/ })).toBeEnabled();
  });

  it("Stok ve Envanter: kilitliyken kalem ekleme ve düzenleme kapalı; açınca etkin", async () => {
    kilitle();
    const satir = { kod: "HM-1", ad: "Biber", birim: "KG", tur: "0001-Hammadde", kontrol: false };
    for (const a of ["dbs_tutar", "alim_tutar", "ortalama_fiyat", "sayim_miktar", "dss_tutar", "sarf_miktar", "sarf_tutar"])
      Object.assign(satir, { [a]: "1" });
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/stok`, () =>
        HttpResponse.json({ donem, toplamlar: null, kontrol_sayisi: 0, turler: [], kayitlar: [satir] }),
      ),
      http.get(`${T}/smm/donemler/:id/stok/elle`, () => HttpResponse.json({ kayitlar: {} })),
    );
    kurSayfa(<SmmStok />);
    const duzenle = await screen.findByRole("button", { name: "Düzenle HM-1" });
    expect(duzenle).toBeDisabled();
    expect(screen.getByRole("button", { name: "Kalem ekle" })).toBeDisabled();
    await duzenlemeyiAc();
    expect(screen.getByRole("button", { name: "Düzenle HM-1" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Kalem ekle" })).toBeEnabled();
  });

  it("Üretim Maliyeti: kilitliyken dağıtım havuzu ve anahtarı kapalı; açınca etkin", async () => {
    kilitle();
    const ozet = (asama: number) => ({
      asama,
      ad: `A${asama}`,
      urun_sayisi: 0,
      uretilen_urun: 0,
      sure_yok: 0,
      alim_kurali: 0,
      kod_bosluklu: 0,
      excel_elle: 0,
      malzeme: "0",
      iscilik: "0",
      gug: "0",
      fire: "0",
      toplam: "0",
      excel: { karsilastirilan: 0, esit: 0, farkli: 0, farkli_ornek: [] },
    });
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/uretim`, () =>
        HttpResponse.json({
          donem,
          asama: 50,
          ozetler: [ozet(20), ozet(40), ozet(50)],
          dagitim: {
            havuzlar: [{ anahtar: "50_uretim", ad: "50 · Üretim işçilik + GÜG", tutar: "300", excel: "300", degisti: false }],
            dagitilan: "300",
            mizan_720: "1000",
            mizan_730: "5000",
            dagitilmayan: "5700",
            anahtarlar: [{ anahtar: "50", ad: "50 · İşçilik + GÜG", alan: "dolum_sn", excel_varsayilani: "dolum_sn" }],
          },
          kayitlar: [],
        }),
      ),
    );
    kurSayfa(<SmmUretim />);
    const havuz = await screen.findByLabelText("50 · Üretim işçilik + GÜG");
    const anahtar = screen.getByLabelText("Dağıtım anahtarı — 50 · İşçilik + GÜG");
    expect(havuz).toBeDisabled();
    expect(anahtar).toBeDisabled();
    await duzenlemeyiAc();
    expect(havuz).toBeEnabled();
    expect(anahtar).toBeEnabled();
  });

  it("Reçeteler: kilitliyken yükleme, yeni reçete ve alternatif seçimi kapalı; açınca etkin", async () => {
    kilitle();
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })),
      http.get(`${T}/smm/receteler`, () =>
        HttpResponse.json({
          son_yukleme: null,
          asama_sayilari: { "50": 1 },
          alternatifli_urun: 1,
          kayitlar: [
            {
              ana_kod: "03-1",
              ana_ad: "Biber 370 etiketli",
              asama: 50,
              alternatifler: ["00", "01"],
              secili_alternatif: "00",
              satir_sayisi: 1,
            },
          ],
        }),
      ),
      http.post(`${T}/smm/receteler/onizle`, () =>
        HttpResponse.json({
          satir_sayisi: 1,
          urun_sayisi: 1,
          asama: { "50": 1 },
          alternatifli_urun: 0,
          mevcut_urun: 1,
          eklenecek_urun: 0,
          kalkacak_urun: 0,
          degisecek_urun: 1,
          ornek: [],
        }),
      ),
      http.get(`${T}/smm/receteler/:kod`, () =>
        HttpResponse.json({
          ana_kod: "03-1",
          ana_ad: "Biber 370 etiketli",
          asama: 50,
          kod_asamasi: 50,
          secili_alternatif: "00",
          elle: false,
          elle_degistiren: null,
          canias_var: true,
          alternatifler: [
            { alternatif: "00", satirlar: [] },
            { alternatif: "01", satirlar: [] },
          ],
        }),
      ),
    );
    kurSayfa(<SmmReceteler />);
    const yeni = await screen.findByRole("button", { name: /Yeni reçete/ });
    expect(yeni).toBeDisabled();
    // Önizleme okumadır: kilitliyken de yapılır; "Yükle" kapalı kalır.
    await userEvent.upload(screen.getByLabelText("Reçete dosyası"), new File(["x"], "Recete.xlsx"));
    await userEvent.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByText(/değişecek 1/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yükle" })).toBeDisabled();
    // Çekmecede alternatif seçimi ve satır ekleme kapalı
    await userEvent.click(within(screen.getByRole("table")).getByText("Biber 370 etiketli"));
    const cekmece = await screen.findByRole("dialog");
    expect(await within(cekmece).findByRole("button", { name: "Bunu kullan" })).toBeDisabled();
    expect(within(cekmece).getAllByRole("button", { name: /Satır ekle/ })[0]).toBeDisabled();
    expect(within(cekmece).getByLabelText("Ürünün aşaması")).toBeDisabled();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await duzenlemeyiAc();
    expect(screen.getByRole("button", { name: /Yeni reçete/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Yükle" })).toBeEnabled();
  });

  it("Üretim Süreleri: kilitliyken ekle, düzenle ve sil kapalı; açınca etkin", async () => {
    kilitle();
    sureleriTanimla();
    kurSayfa(<SmmSureler />);
    const duzenle = await screen.findByRole("button", { name: "Düzenle — 03-1" });
    expect(duzenle).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sil — 03-1" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Satır ekle/ })).toBeDisabled();
    await duzenlemeyiAc();
    expect(screen.getByRole("button", { name: "Düzenle — 03-1" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Sil — 03-1" })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Satır ekle/ })).toBeEnabled();
  });

  it("Üretim Süreleri: kapalı dönemde düzenleme açık olsa da yazılamaz", async () => {
    sureleriTanimla({ ...donem, kilitli: true } as SmmDonem);
    kurSayfa(<SmmSureler />);
    expect(await screen.findByRole("button", { name: "Düzenle — 03-1" })).toBeDisabled();
    expect(screen.getByTestId("duzenleme-kilidi")).toHaveAttribute("data-durum", "acik");
    expect(screen.getByTestId("duzenleme-engel")).toHaveTextContent("Dönem kapatıldı");
  });

  it("Satın alma SMM'de yazamaz: şeritte düğme yok, yazma kapalı (kilit Fiyat Çalışması'nda açık olsa da)", async () => {
    sureleriTanimla();
    kurSayfa(oturumla("satin_alma", <SmmSureler />));
    expect(await screen.findByRole("button", { name: "Düzenle — 03-1" })).toBeDisabled();
    const serit = screen.getByTestId("duzenleme-kilidi");
    expect(serit).toHaveAttribute("data-durum", "kilitli");
    expect(serit).toHaveTextContent("Satın alma rolüyle Maliyet Muhasebesi'nde değişiklik yapılamaz.");
    expect(within(serit).queryByRole("button")).not.toBeInTheDocument();
  });

  it("Muhasebe rolü SMM'de kilidi açabilir; izleyici açamaz", async () => {
    kilitle();
    sureleriTanimla();
    const { unmount } = kurSayfa(oturumla("muhasebe", <SmmSureler />));
    await screen.findByRole("button", { name: "Düzenle — 03-1" });
    expect(screen.getByRole("button", { name: "Düzenlemeyi aç" })).toBeInTheDocument();
    unmount();
    kurSayfa(oturumla("izleyici", <SmmSureler />));
    await screen.findByRole("button", { name: "Düzenle — 03-1" });
    expect(screen.queryByRole("button", { name: "Düzenlemeyi aç" })).not.toBeInTheDocument();
    expect(screen.getByTestId("duzenleme-kilidi")).toHaveTextContent("İzleyici rolüyle değişiklik yapılamaz.");
  });
});
