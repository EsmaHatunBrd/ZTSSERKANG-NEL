import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { sunucu } from "@/test/msw/sunucu";
import { formAlanlariniYakala } from "@/test/msw/isleyiciler-aktar";
import {
  aktarimHatasi,
  aktarimIsleyici,
  giderOnizle,
  giderUygula,
  satinAlmaOnizle,
  satinAlmaUygula,
  uretimOnizle,
  uretimUygula,
  type AktarimIstegi,
} from "@/test/msw/isleyiciler-aktarim";
import { SenaryoSaglayici, SenaryoSecici } from "@/bilesenler/SenaryoSecici";
import { http, HttpResponse } from "msw";
import ReceteAktar from "../ReceteAktar";
import type { AktarimOnizleStokDevri, AktarimUygulaStokDevri } from "@/api/tipler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
let form: ReturnType<typeof formAlanlariniYakala> | null = null;
afterEach(() => {
  sunucu.resetHandlers();
  form?.geri();
  form = null;
});
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function kur(secici = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/recete-aktar?senaryo=1"]}>
        <SenaryoSaglayici>
          {secici && <SenaryoSecici />}
          {secici && <SenaryoSecici />}
          <Routes>
            <Route path="/recete-aktar" element={<ReceteAktar />} />
            <Route path="/satis-gecmisi" element={<p>Satış sayfası</p>} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const xlsx = () => new File(["x"], "veri.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

async function sekme(ad: string) {
  await waitFor(() => expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("1"));
  await userEvent.click(screen.getByRole("tab", { name: ad }));
}

async function dosyaVeOnizle() {
  await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
  const dugme = screen.getByRole("button", { name: "Önizle" });
  await waitFor(() => expect(dugme).toBeEnabled());
  await userEvent.click(dugme);
  return screen.findByRole("region", { name: "Önizleme" });
}

describe("Veri Aktar sayfası", () => {
  it("başlık ve yedi sekme", async () => {
    kur();
    expect(screen.getByRole("heading", { name: "Veri Aktar" })).toBeInTheDocument();
    expect(screen.getByText("Excel'den veri yükleme ve elle reçete girişi")).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Tüm çalışma kitabı",
      "Satın alma fiyat listesi",
      "Üretim adetleri",
      "Gider dağıtım",
      "Satış geçmişi",
      "Ürün reçetesi",
      "Stokta kalan",
    ]);
  });

  it("satış geçmişi sekmesi sayfaya yönlendirir ve şablonu bağlar", async () => {
    kur();
    await sekme("Satış geçmişi");
    expect(screen.getByRole("link", { name: "Satış Geçmişi sayfasına git" })).toHaveAttribute("href", "/satis-gecmisi");
    expect(screen.getByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/satis-gecmisi/sablon.xlsx");
  });
});

describe("Veri Aktar - üretim adetleri", () => {
  it("önizle gövdesi, fark tablosu, neden boşken Uygula pasif, uygula gövdesi ve özet", async () => {
    const istek: AktarimIstegi[] = [];
    form = formAlanlariniYakala();
    sunucu.use(
      aktarimIsleyici("uretim-adetleri", "onizle", uretimOnizle, istek),
      aktarimIsleyici("uretim-adetleri", "uygula", uretimUygula, istek),
    );
    kur();
    await sekme("Üretim adetleri");
    const onizleme = await dosyaVeOnizle();

    expect(istek).toHaveLength(1);
    expect(istek[0].icerikTuru).toMatch(/^multipart\/form-data; boundary=/);
    expect((form.alanlar.dosya as File).name).toBe("veri.xlsx");
    expect(form.alanlar.senaryo).toBe("1");
    expect("neden" in form.alanlar).toBe(false);

    const yeni = within(onizleme).getByRole("region", { name: "Yeni ürünler" });
    expect(within(yeni).getByText("T-1")).toBeInTheDocument();
    expect(within(yeni).getByText("90")).toBeInTheDocument();
    const degisen = within(onizleme).getByRole("region", { name: "Değişen alanlar" });
    expect(within(degisen).getByText("190")).toBeInTheDocument();
    expect(within(degisen).getByText("195")).toBeInTheDocument();
    expect(within(onizleme).getByText("3", { selector: "span" })).toBeInTheDocument();
    expect(within(onizleme).getByText(/ürün kodu T-3 birden fazla/)).toBeInTheDocument();

    const uygula = screen.getByRole("button", { name: "Uygula" });
    expect(uygula).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Neden"), "ilk yükleme");
    expect(uygula).toBeEnabled();
    await userEvent.click(uygula);

    const ozet = await screen.findByRole("region", { name: "Aktarım özeti" });
    const kart = (ad: string) => within(ozet).getByText(ad, { selector: "[data-kart-baslik]" }).parentElement as HTMLElement;
    expect(within(kart("Eklenen")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Güncellenen")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Uyarılar")).getByText("1")).toBeInTheDocument();
    expect(istek.map((i) => i.asama)).toEqual(["onizle", "uygula"]);
    expect(form.alanlar.neden).toBe("ilk yükleme");
    expect("gecerlilik_basi" in form.alanlar).toBe(false);
  });

  it("yazılacak değişiklik yoksa Uygula pasif kalır", async () => {
    sunucu.use(aktarimIsleyici("uretim-adetleri", "onizle", { yeni: [], degisen: [], ayni: 5, uyarilar: [] }));
    kur();
    await sekme("Üretim adetleri");
    const onizleme = await dosyaVeOnizle();
    expect(within(onizleme).getByText("Yazılacak değişiklik yok.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Neden"), "x");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
  });

  it("422 hatasını gösterir; yanlış uzantıyı reddeder", async () => {
    sunucu.use(
      aktarimHatasi("uretim-adetleri", "onizle", "Üretim Adetleri sayfası bulunamadı; tek sayfalık dosyada ilk sayfa kullanılır", {
        sayfa: "Üretim Adetleri",
      }),
    );
    kur();
    await sekme("Üretim adetleri");
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), new File(["x"], "a.csv", { type: "text/csv" }), { applyAccept: false });
    expect(screen.getByText("Yalnızca .xlsx dosyası yüklenebilir")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Önizle" })).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await userEvent.click(screen.getByRole("button", { name: "Önizle" }));
    const uyari = await screen.findByRole("alert");
    expect(uyari).toHaveTextContent("Üretim Adetleri sayfası bulunamadı");
    expect(uyari).toHaveTextContent("sayfa: Üretim Adetleri");
  });

  it("uygulama 422 verirse hata listelenir ve özet görünmez", async () => {
    sunucu.use(aktarimIsleyici("uretim-adetleri", "onizle", uretimOnizle), aktarimHatasi("uretim-adetleri", "uygula", "neden zorunlu"));
    kur();
    await sekme("Üretim adetleri");
    await dosyaVeOnizle();
    await userEvent.type(screen.getByLabelText("Neden"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Uygula" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("neden zorunlu");
    expect(screen.queryByRole("region", { name: "Aktarım özeti" })).not.toBeInTheDocument();
  });
});

describe("Veri Aktar - satın alma fiyat listesi", () => {
  it("geçerlilik tarihi ve kartları güncelle gövdede gider; fark tabloları ve özet", async () => {
    form = formAlanlariniYakala();
    sunucu.use(aktarimIsleyici("satin-alma", "onizle", satinAlmaOnizle), aktarimIsleyici("satin-alma", "uygula", satinAlmaUygula));
    kur();
    await sekme("Satın alma fiyat listesi");
    fireTarih(await screen.findByLabelText("Geçerlilik tarihi"), "2026-09-01");
    const onizleme = await dosyaVeOnizle();
    expect(form.alanlar.gecerlilik_basi).toBe("2026-09-01");
    expect(form.alanlar.senaryo).toBe("1");

    expect(within(within(onizleme).getByRole("region", { name: "Yeni malzemeler" })).getByText("Kavanoz")).toBeInTheDocument();
    expect(within(within(onizleme).getByRole("region", { name: "Kart farkları" })).getByText("ad, birim")).toBeInTheDocument();
    expect(within(onizleme).getByRole("region", { name: "Yeni fiyatlar" })).toBeInTheDocument();
    const degisen = within(onizleme).getByRole("region", { name: "Değişen fiyatlar" });
    expect(within(degisen).getByText("MLZ-3")).toBeInTheDocument();
    expect(within(degisen).getByText("2,5000")).toBeInTheDocument();
    expect(within(degisen).getByText("3,0000")).toBeInTheDocument();
    // G2: S.ALMA BF I sütunu (revize) ayrı tablo + sayaç
    const revize = within(onizleme).getByRole("region", { name: "Revize fiyatlar (S.ALMA BF I)" });
    expect(within(revize).getByText("2,8000")).toBeInTheDocument();
    expect(within(onizleme).getByText("Revize edilen:", { exact: false })).toHaveTextContent("Revize edilen: 1");

    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Kartları güncelle"));
    await userEvent.type(screen.getByLabelText("Neden"), "bütçe");
    await userEvent.click(screen.getByRole("button", { name: "Uygula" }));

    const ozet = await screen.findByRole("region", { name: "Aktarım özeti" });
    const kart = (ad: string) => within(ozet).getByText(ad, { selector: "[data-kart-baslik]" }).parentElement as HTMLElement;
    expect(within(kart("Eklenen malzeme")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Yazılan fiyat")).getByText("2")).toBeInTheDocument();
    expect(within(kart("Revize (I) yazılan")).getByText("1")).toBeInTheDocument();
    expect(form.alanlar.gecerlilik_basi).toBe("2026-09-01");
    expect(form.alanlar.kartlari_guncelle).toBe("true");
    expect(form.alanlar.neden).toBe("bütçe");
  });

  it("hatalı satır varsa listelenir ve Uygula pasif kalır", async () => {
    sunucu.use(aktarimIsleyici("satin-alma", "onizle", { ...satinAlmaOnizle, hatali: ["MLZ-9"] }));
    kur();
    await sekme("Satın alma fiyat listesi");
    const onizleme = await dosyaVeOnizle();
    expect(within(onizleme).getByText("MLZ-9: fiyat sayı değil veya negatif")).toBeInTheDocument();
    expect(within(onizleme).getByText("Hatalı satırlar düzeltilmeden uygulanamaz.")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Neden"), "x");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
  });

  it("tarih değişince önizleme geçersiz olur", async () => {
    sunucu.use(aktarimIsleyici("satin-alma", "onizle", satinAlmaOnizle));
    kur();
    await sekme("Satın alma fiyat listesi");
    await dosyaVeOnizle();
    fireTarih(screen.getByLabelText("Geçerlilik tarihi"), "2026-10-01");
    await waitFor(() => expect(screen.queryByRole("region", { name: "Önizleme" })).not.toBeInTheDocument());
  });
});

describe("Veri Aktar - gider dağıtım", () => {
  it("yalnız değişen havuzları ve ambalaj farkını gösterir; uygular", async () => {
    form = formAlanlariniYakala();
    sunucu.use(aktarimIsleyici("gider-dagitim", "onizle", giderOnizle), aktarimIsleyici("gider-dagitim", "uygula", giderUygula));
    kur();
    await sekme("Gider dağıtım");
    expect(screen.queryByLabelText("Geçerlilik tarihi")).not.toBeInTheDocument();
    const onizleme = await dosyaVeOnizle();
    const havuz = within(onizleme).getByRole("region", { name: "Değişen havuzlar" });
    expect(within(havuz).getByText("Dolum doğrudan işçilik")).toBeInTheDocument();
    expect(within(havuz).queryByText("Elektrik")).not.toBeInTheDocument();
    expect(within(havuz).getByText("1.000,00")).toBeInTheDocument();
    expect(within(havuz).getByText("2.000,00")).toBeInTheDocument();
    expect(within(onizleme).getByText("Aynı havuz:", { exact: false })).toHaveTextContent("Aynı havuz: 1");
    const amb = within(onizleme).getByRole("region", { name: "Ambalaj farkları" });
    expect(within(amb).getByText("uretim_adedi")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Neden"), "revizyon");
    await userEvent.click(screen.getByRole("button", { name: "Uygula" }));
    const ozet = await screen.findByRole("region", { name: "Aktarım özeti" });
    const kart = (ad: string) => within(ozet).getByText(ad, { selector: "[data-kart-baslik]" }).parentElement as HTMLElement;
    expect(within(kart("Yazılan havuz")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Yazılan ambalaj sınıfı")).getByText("1")).toBeInTheDocument();
    expect(form.alanlar.neden).toBe("revizyon");
    expect("kartlari_guncelle" in form.alanlar).toBe(false);
  });
});

/** type="date" girdisine userEvent.type yerine doğrudan değer atar (jsdom'da güvenilir). */

function fireTarih(girdi: HTMLElement, deger: string) {
  fireEvent.change(girdi, { target: { value: deger } });
}

describe("Veri Aktar - senaryo değişimi", () => {
  it("önizlemeden sonra senaryo değişirse önizleme silinir ve Uygula görünmez", async () => {
    sunucu.use(
      http.get("*/api/v1/senaryolar", () =>
        HttpResponse.json({
          kayitlar: [
            { id: 1, sezon_ad: "2026-2027", tur: "fiyat_calismasi", ad: "A" },
            { id: 2, sezon_ad: "2026-2027", tur: "fiyat_calismasi", ad: "B" },
          ],
          toplam: 2,
        }),
      ),
      aktarimIsleyici("uretim-adetleri", "onizle", uretimOnizle),
    );
    kur(true);
    await sekme("Üretim adetleri");
    await dosyaVeOnizle();
    await userEvent.type(screen.getByLabelText("Neden"), "x");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeEnabled();
    await userEvent.selectOptions(screen.getByLabelText("Senaryo"), "2");
    await waitFor(() => expect(screen.queryByRole("region", { name: "Önizleme" })).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Uygula" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Önizle" })).toBeEnabled();
  });
});

describe("Veri Aktar - stokta kalan", () => {
  const satir = { ad: "Salatalık Turşusu 720 ml", enflasyon: null, uretim_adedi: null };
  const onizle: AktarimOnizleStokDevri = {
    sutunlar: {
      urun_kodu: "urun_kodu",
      stok_adet: "stok_adet",
      stok_birim_maliyet: "stok_birim_maliyet",
      enflasyon: null,
      uretim_adedi: "uretim_adedi",
    },
    satirlar: [
      { ...satir, satir_no: 2, urun_kodu: "URUN-001", adet: "1200", birim_maliyet: "10.5", durum: "yeni", eski: null },
      {
        ...satir,
        satir_no: 3,
        urun_kodu: "URUN-002",
        adet: "350",
        birim_maliyet: "8",
        durum: "degisen",
        eski: { adet: "300", birim_maliyet: "8" },
      },
      { ...satir, satir_no: 4, urun_kodu: "URUN-003", adet: "10", birim_maliyet: "1", durum: "ayni", eski: null },
    ],
    hatalar: [],
    yeni: 1,
    degisen: 1,
    ayni: 1,
  };
  const uygula: AktarimUygulaStokDevri = { eklenen: 1, guncellenen: 1, ayni: 1 };

  it("şablon bağlantısı, sayılar, yeni/değişen tabloları, neden zorunlu ve uygula gövdesi", async () => {
    const istek: AktarimIstegi[] = [];
    form = formAlanlariniYakala();
    sunucu.use(aktarimIsleyici("stok-devri", "onizle", onizle, istek), aktarimIsleyici("stok-devri", "uygula", uygula, istek));
    kur();
    await sekme("Stokta kalan");
    expect(screen.getByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/aktarim/stok-devri/sablon.xlsx");
    const onizleme = await dosyaVeOnizle();
    expect(form.alanlar.senaryo).toBe("1");
    expect(within(onizleme).getByText(/Dosyada bulunamayan sütunlar: enflasyon/)).toBeInTheDocument();

    const yeni = within(onizleme).getByRole("region", { name: "Yeni kayıtlar" });
    expect(within(yeni).getByText("1.200")).toBeInTheDocument();
    expect(within(yeni).getByText("10,50")).toBeInTheDocument();
    expect(within(yeni).getByText("parametre")).toBeInTheDocument();
    expect(within(yeni).getByText("geçen yıl satışı")).toBeInTheDocument();
    const degisen = within(onizleme).getByRole("region", { name: "Değişen kayıtlar" });
    expect(within(degisen).getByText("300")).toHaveClass("line-through");
    expect(within(degisen).getByText("350")).toBeInTheDocument();
    expect(within(onizleme).queryByText("URUN-003")).not.toBeInTheDocument();

    const uygulaDugmesi = screen.getByRole("button", { name: "Uygula" });
    expect(uygulaDugmesi).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Neden"), "Yıl sonu sayımı");
    await userEvent.click(uygulaDugmesi);
    const ozet = await screen.findByRole("region", { name: "Aktarım özeti" });
    const kart = (ad: string) => within(ozet).getByText(ad, { selector: "[data-kart-baslik]" }).parentElement as HTMLElement;
    expect(within(kart("Eklenen")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Güncellenen")).getByText("1")).toBeInTheDocument();
    expect(istek.map((i) => i.asama)).toEqual(["onizle", "uygula"]);
    expect(form.alanlar.neden).toBe("Yıl sonu sayımı");
  });

  it("hatalı satır varsa satır numarasıyla listelenir ve uygulanamaz", async () => {
    sunucu.use(aktarimIsleyici("stok-devri", "onizle", { ...onizle, hatalar: [{ satir_no: 5, mesaj: "Ürün bulunamadı: YOK-1" }] }));
    kur();
    await sekme("Stokta kalan");
    const onizleme = await dosyaVeOnizle();
    const hatali = within(onizleme).getByRole("region", { name: "Hatalı satırlar" });
    expect(within(hatali).getByText("5")).toBeInTheDocument();
    expect(within(hatali).getByText("Ürün bulunamadı: YOK-1")).toBeInTheDocument();
    expect(within(onizleme).getByRole("alert")).toHaveTextContent("Hatalı satırlar düzeltilmeden uygulanamaz.");
    await userEvent.type(screen.getByLabelText("Neden"), "x");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
  });
});
