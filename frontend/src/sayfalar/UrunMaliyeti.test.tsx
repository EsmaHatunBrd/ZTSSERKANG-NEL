import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { http, HttpResponse, type RequestHandler } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { urunIsleyicileri } from "@/test/msw/isleyiciler-urun";
import { urunExcelIsleyicileri, type UrunExcelIstekleri } from "@/test/msw/isleyiciler-urun-excel";
import { urunHesapYaniti, urunReceteleri } from "@/test/fikstur/urunMaliyeti";
import { urunExcelHesapYaniti } from "@/test/fikstur/urunExcel";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { RECETESIZ_KOD, senaryolar } from "@/test/fikstur/urunler";
import { KILIT_KAPSAM_NOTU, KILIT_METNI } from "@/bilesenler/KilitSeridi";
import UrunMaliyeti, { HEDEF_YOK_METNI, RECETE_YOK_METNI, SENARYO_DISI_METNI } from "./UrunMaliyeti";
import { eslestir } from "./urun/yardimci";
import type { HesapSatiri, ReceteSatiri } from "@/api/tipler";

beforeAll(() => {
  // Recharts ResponsiveContainer jsdom'da ResizeObserver ister.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  sunucu.listen({ onUnhandledFrame: "error" });
});
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

let sonQc: QueryClient;
let sonExcel: UrunExcelIstekleri;
let sonYon: ReturnType<typeof createMemoryRouter>;

function kur(
  secenek: Parameters<typeof urunIsleyicileri>[0] & Parameters<typeof urunExcelIsleyicileri>[0] = {},
  /** Ürün işleyicilerinin önüne geçen ek işleyiciler (ilk eşleşen kazanır). */
  ek: RequestHandler[] = [],
  yol = "/urunler/URUN-001?senaryo=1",
) {
  const { isleyiciler, istekler } = urunIsleyicileri(secenek);
  const excel = urunExcelIsleyicileri(secenek);
  sonExcel = excel.istekler;
  sunucu.use(...ek, ...isleyiciler, ...excel.isleyiciler);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  sonQc = qc;
  // Sayfadan ayrılma engeli veri yönlendiricisi ister (uygulamadaki gibi).
  sonYon = createMemoryRouter(
    [
      {
        path: "/urunler/:kod",
        element: (
          <SenaryoSaglayici>
            <UrunMaliyeti />
          </SenaryoSaglayici>
        ),
      },
      { path: "/baska", element: <p>Başka sayfa</p> },
    ],
    { initialEntries: [yol] },
  );
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={sonYon} />
    </QueryClientProvider>,
  );
  return istekler;
}

async function tabloHazir() {
  const tablo = await screen.findByRole("table", { name: "Reçete tablosu" });
  await within(tablo).findByText("Pet Şişe 500 ml");
  return tablo;
}

/** Şeritteki Kaydet -> diyalogda neden yaz -> Onayla ve kaydet. */
async function kaydetAkisi(user: ReturnType<typeof userEvent.setup>, neden = "Test nedeni") {
  await user.click(screen.getByRole("button", { name: "Kaydet" }));
  const diyalog = await screen.findByRole("dialog");
  await user.type(within(diyalog).getByLabelText("Neden"), neden);
  await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
  return diyalog;
}

const satir = (tablo: HTMLElement, ad: string) => within(tablo).getByText(ad).closest("tr") as HTMLElement;
const son = <T,>(d: T[]) => d[d.length - 1];

describe("UrunMaliyeti", () => {
  it("kilitli senaryoda şerit görünür, hücreler düzenlenebilir ama Kaydet pasiftir ('Senaryo kilitli')", async () => {
    const kilitli = senaryolar.map((s) => (s.id === 1 ? { ...s, kilitli: true } : s));
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: kilitli, toplam: kilitli.length })));
    kur();
    const tablo = await tabloHazir();
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
    expect(screen.getByText(KILIT_KAPSAM_NOTU)).toBeInTheDocument();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    expect(fire).toBeEnabled(); // what-if serbest
    const user = userEvent.setup();
    await user.clear(fire);
    await user.type(fire, "5");
    expect(await screen.findByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument();
    const kaydet = screen.getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled();
    expect(kaydet).toHaveAttribute("title", "Senaryo kilitli");
  });

  it("kilitsiz senaryoda kilit şeridi yoktur", async () => {
    kur();
    await tabloHazir();
    expect(screen.queryByText(KILIT_METNI)).not.toBeInTheDocument();
  });

  it("stokta kalan kaydı yoksa yalnız sade 'Stokta kalan ekle' düğmesi; taslak sayısını etkilemez", async () => {
    kur();
    await tabloHazir();
    expect(await screen.findByRole("button", { name: /Stokta kalan ekle/ })).toBeEnabled();
    expect(screen.queryByRole("region", { name: "Stok etkisi" })).not.toBeInTheDocument();
  });

  it("tek tabloda iki tutar sütununu ve iki malzeme toplamını gösterir", async () => {
    kur();
    const tablo = await tabloHazir();
    expect(within(tablo).getByRole("columnheader", { name: "Tutar (firesiz)" })).toBeInTheDocument();
    expect(within(tablo).getByRole("columnheader", { name: "Tutar (fireli)" })).toBeInTheDocument();
    const pet = satir(tablo, "Pet Şişe 500 ml");
    expect(within(pet).getByText("7,38 TL")).toBeInTheDocument(); // 7.375 firesiz
    expect(within(pet).getByText("7,53 TL")).toBeInTheDocument(); // 7.525510 fireli
    const firesiz = within(tablo).getByText("Malzeme toplamı (firesiz)").closest("tr") as HTMLElement;
    const fireli = within(tablo).getByText("Malzeme toplamı (fireli)").closest("tr") as HTMLElement;
    expect(within(firesiz).getByText("11,72 TL")).toBeInTheDocument();
    expect(within(fireli).getByText("12,24 TL")).toBeInTheDocument();
    // gider satırları reçete tablosunda değil, gider kalemlerinde
    expect(within(tablo).queryByText("Direkt işçilik")).not.toBeInTheDocument();
    expect(screen.getAllByText("Direkt işçilik").length).toBeGreaterThanOrEqual(1);
  });

  it("toplamlar kartı fireli ve firesiz zincirleri yan yana gösterir", async () => {
    kur();
    await tabloHazir();
    const kart = screen.getByRole("region", { name: "Toplamlar" });
    const maliyet = within(kart).getByText("Finansman dahil maliyet TL").parentElement as HTMLElement;
    expect(within(maliyet).getByText("38,13 TL")).toBeInTheDocument();
    expect(within(maliyet).getByText("36,91 TL")).toBeInTheDocument();
    // Satış fiyatları ayrı tabloda (Excel düzeni); Toplamlar kartında tekrar etmez.
    expect(within(kart).queryByText(/Satış fiyatı/)).not.toBeInTheDocument();
    const tablo = screen.getByRole("table", { name: "Satış fiyatı tablosu" });
    const tl = within(tablo).getByText("TL").closest("tr") as HTMLElement;
    expect(within(tl).getByText("45,76 TL")).toBeInTheDocument();
    expect(within(tl).getByText("44,29 TL")).toBeInTheDocument();
  });

  it("kaynak rozetleri doğru metni gösterir", async () => {
    kur();
    const tablo = await tabloHazir();
    const pet = satir(tablo, "Pet Şişe 500 ml");
    expect(within(pet).getByText("Fire")).toBeInTheDocument();
    expect(within(pet).getByText("Liste")).toBeInTheDocument();
    expect(within(satir(tablo, "Salamura Karışımı")).getAllByText("Elle")).toHaveLength(2);
    expect(within(satir(tablo, "Kapak")).getByText("Yok")).toBeInTheDocument();
  });

  it("elle brüt satırında fire hücresi pasiftir, diğerinde etkindir", async () => {
    kur();
    const tablo = await tabloHazir();
    expect(within(tablo).getByLabelText(/Fire % .*Salamura/)).toBeDisabled();
    expect(within(tablo).getByLabelText(/Fire % .*Pet Şişe/)).toBeEnabled();
  });

  it("fire hücresi değişince hesapla override.fire ile yeniden çağrılır", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    expect(istekler.hesapla[0]).toMatchObject({ senaryo_id: 1 });
    expect(istekler.hesapla[0]).not.toHaveProperty("override");
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    const user = userEvent.setup();
    await user.clear(fire);
    await user.type(fire, "5");
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { fire: Record<string, string> } };
      expect(g.override.fire).toEqual({ "1": "0.05" });
    });
    // şerit değişiklik sayısını gösterir
    expect(screen.getByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument();
  });

  it("Vazgeç taslağı temizler ve hesabı yeniden koşar", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(fire);
    await user.type(fire, "5");
    await waitFor(() => expect(JSON.stringify(son(istekler.hesapla))).toContain('"0.05"'));
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(JSON.stringify(son(istekler.hesapla))).not.toContain('"0.05"'));
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Vazgeç" })).not.toBeInTheDocument();
  });

  it("Kaydet: diyalogda eski → yeni ve etki gösterilir; neden boşken onay pasiftir; gövde doğru gider, başarıdan sonra taslak sıfırlanır", async () => {
    kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(fire);
    await user.type(fire, "5");
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    const usd = screen.getByLabelText("Kur USD");
    await user.clear(usd);
    await user.type(usd, "52");
    await waitFor(() => expect(screen.getByText("1 satırda ve 2 alanda değişiklik · 1 fire")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    const liste = within(diyalog).getByRole("table", { name: "Değişiklik listesi" });
    const fireSatiri = liste.querySelector('[data-alan="satir.1.fire"]') as HTMLElement;
    expect(fireSatiri).toHaveTextContent("Satır 1 · Pet Şişe 500 ml · fire");
    expect(fireSatiri).toHaveTextContent("2 % (kural)");
    expect(fireSatiri).toHaveTextContent("5 %");
    expect(within(fireSatiri).getByText("Bu ürün")).toBeInTheDocument();
    const faizSatiri = liste.querySelector('[data-alan="parametre.faiz.TL"]') as HTMLElement;
    expect(faizSatiri).toHaveTextContent("40,0 %");
    expect(faizSatiri).toHaveTextContent("50,0 %");
    expect(within(faizSatiri).getByText("Bu ürün")).toBeInTheDocument();
    const kurSatiri = liste.querySelector('[data-alan="parametre.kur.USD"]') as HTMLElement;
    expect(await within(kurSatiri).findByText("Senaryo geneli — 3 ürünü etkiler")).toBeInTheDocument();
    // Neden zorunlu
    const onay = within(diyalog).getByRole("button", { name: "Onayla ve kaydet" });
    expect(onay).toBeDisabled();
    expect(within(diyalog).getByLabelText("Hesabı da kaydet")).toBeChecked();
    await user.type(within(diyalog).getByLabelText("Neden"), "  Ekim güncellemesi ");
    expect(onay).toBeEnabled();
    await user.click(onay);
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    const kayit = sonExcel.topluKaydet[0];
    expect(kayit.kod).toBe("URUN-001");
    expect(kayit.govde).toMatchObject({
      senaryo_id: 1,
      neden: "Ekim güncellemesi",
      hesabi_kaydet: true,
      parametreler: [
        { anahtar: "faiz.TL", deger: "0.5", kapsam: "urun" },
        { anahtar: "kur.USD", deger: "52", kapsam: "genel" },
      ],
    });
    const recete = kayit.govde.recete as Record<string, unknown>[];
    expect(recete).toHaveLength(3);
    expect(recete[0]).toMatchObject({ malzeme_kodu: "M-001", fire_override: "0.05" });
    expect(kayit.govde).not.toHaveProperty("urun");
    expect(kayit.govde).not.toHaveProperty("uretim_hedefi");
    // Başarı: şeritte durum, taslak sıfır, diyalog kapalı
    const durum = await screen.findByRole("status", { name: "Kayıt durumu" });
    expect(durum).toHaveTextContent("Kaydedildi · Hesap #7");
    expect(durum).toHaveTextContent("3 reçete satırı");
    expect(durum).toHaveTextContent("2 parametre");
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("gönderim sürerken diyalog kapatılamaz; yanıt gelince taslak temizlenir ve tek POST yazılır", async () => {
    kur();
    await tabloHazir();
    let birak: () => void = () => {};
    const bekle = new Promise<void>((r) => (birak = r));
    let istek = 0;
    sunucu.use(
      http.post("*/api/v1/urunler/:kod/kaydet", async () => {
        istek += 1;
        await bekle;
        return HttpResponse.json({
          hesap: null,
          hesap_id: 7,
          yazilan: { urun: 0, hedef: 0, recete: 0, parametre: 1, havuz: 0 },
          uyarilar: [],
        });
      }),
    );
    const user = userEvent.setup();
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    await kaydetAkisi(user);
    await waitFor(() => expect(istek).toBe(1));
    // Gönderim sürerken kapatma denemeleri
    const diyalog = screen.getByRole("dialog");
    expect(within(diyalog).getByRole("button", { name: "Vazgeç" })).toBeDisabled();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    birak();
    const durum = await screen.findByRole("status", { name: "Kayıt durumu" });
    expect(durum).toHaveTextContent("Kaydedildi · Hesap #7");
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(istek).toBe(1);
  });

  it("Kaydet başarısında ürün, reçete, parametre ve gider sorguları geçersiz kılınır", async () => {
    kur();
    await tabloHazir();
    const gecersiz = vi.spyOn(sonQc, "invalidateQueries");
    const user = userEvent.setup();
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    await kaydetAkisi(user);
    await screen.findByRole("status", { name: "Kayıt durumu" });
    const anahtarlar = gecersiz.mock.calls.map((c) => (c[0] as { queryKey: string[] }).queryKey[0]);
    for (const k of ["urun", "urunler", "hesaplar", "uyarilar", "recete", "parametreler", "gider-havuzlari"]) {
      expect(anahtarlar).toContain(k);
    }
  });

  it("Kaydet: senaryo geneli parametre 'Yalnız bu ürün için yaz' ile kapsamı urun'a çevrilir; 'Hesabı da kaydet' kapatılabilir", async () => {
    kur();
    await tabloHazir();
    const user = userEvent.setup();
    const enf = screen.getByLabelText("Enflasyon (%)");
    await user.clear(enf);
    await user.type(enf, "30");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    await user.click(within(diyalog).getByLabelText("Yalnız bu ürün için yaz — Enflasyon (%)"));
    expect(within(diyalog).getByText("Bu ürün")).toBeInTheDocument();
    await user.click(within(diyalog).getByLabelText("Hesabı da kaydet"));
    await user.type(within(diyalog).getByLabelText("Neden"), "Deneme");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    expect(sonExcel.topluKaydet[0].govde).toMatchObject({
      hesabi_kaydet: false,
      parametreler: [{ anahtar: "enflasyon", deger: "0.3", kapsam: "urun" }],
    });
    expect(await screen.findByRole("status", { name: "Kayıt durumu" })).not.toHaveTextContent("Hesap #");
  });

  it("Kaydet diyalogu senaryo geneli rozetinde senaryodaki ürün sayısını gösterir (N ürünü etkiler)", async () => {
    sunucu.use(http.get("*/api/v1/urunler", () => HttpResponse.json({ kayitlar: [], toplam: 7 })));
    kur();
    await tabloHazir();
    const user = userEvent.setup();
    const enf = screen.getByLabelText("Enflasyon (%)");
    await user.clear(enf);
    await user.type(enf, "30");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    expect(await within(diyalog).findByText("Senaryo geneli — 7 ürünü etkiler")).toBeInTheDocument();
  });

  it("parametre hücresinin 'Eski değer' ipucu sunucu tabanını gösterir, yeniden hesaplanmış değeri değil", async () => {
    kur();
    // Önizleme yeniden hesabı: gönderilen enflasyon override'ı yanıtta kullanılan değer olur (sunucu davranışı)
    sunucu.use(
      http.post("*/api/v1/urunler/:kod/hesapla", async ({ request }) => {
        const g = (await request.json()) as { override?: { parametreler?: Record<string, string> } };
        const e = g.override?.parametreler?.enflasyon;
        return HttpResponse.json(
          e
            ? { ...urunHesapYaniti, kullanilan_parametreler: { ...urunHesapYaniti.kullanilan_parametreler, enflasyon: e } }
            : urunHesapYaniti,
        );
      }),
    );
    await tabloHazir();
    const user = userEvent.setup();
    const enf = screen.getByLabelText("Enflasyon (%)");
    const taban = (enf as HTMLInputElement).value;
    await user.clear(enf);
    await user.type(enf, "30");
    await waitFor(() => expect(enf).toHaveAttribute("title", `Eski değer: ${taban} %`));
  });

  it("Kaydet: sunucu hatası diyalogda gösterilir, taslak ve diyalog korunur", async () => {
    kur({
      kaydetHatasi: () => HttpResponse.json({ hata: "dogrulama", mesaj: "Parametre değeri geçersiz", alanlar: {} }, { status: 422 }),
    });
    await tabloHazir();
    const user = userEvent.setup();
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    const diyalog = await kaydetAkisi(user);
    expect(await within(diyalog).findByRole("alert")).toHaveTextContent("Parametre değeri geçersiz");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Faiz TL (%)")).toHaveValue("50");
    expect(screen.getByText("1 alanda değişiklik")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Kayıt durumu" })).not.toBeInTheDocument();
  });

  it("taslak yokken sayfadan ayrılırken engel çıkmaz", async () => {
    kur();
    await tabloHazir();
    await sonYon.navigate("/baska");
    await waitFor(() => expect(screen.getByText("Başka sayfa")).toBeInTheDocument());
  });

  it("elle brüt moduna geçince fire pasifleşir, hesapla override.satirlar ile çağrılır; reçete Kaydet ile yazılır", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const girdi = within(tablo).getByLabelText(/Brüt — Pet Şişe/);
    await user.clear(girdi);
    await user.type(girdi, "1.05");
    expect(within(tablo).getByLabelText(/Fire % .*Pet Şişe/)).toBeDisabled();
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { satirlar: Record<string, unknown> } };
      expect(g.override.satirlar).toEqual({ "1": { brut_miktar_elle: "1.05", elle_brut_kaldir: false, elle_fiyat_kaldir: false } });
    });
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    expect(within(diyalog).getByText(/Pet Şişe 500 ml · elle brüt/)).toBeInTheDocument();
    await user.type(within(diyalog).getByLabelText("Neden"), "Elle brüt");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    const govde = sonExcel.topluKaydet[0].govde.recete as Record<string, unknown>[];
    expect(govde).toHaveLength(3);
    expect(govde[0]).toMatchObject({ malzeme_kodu: "M-001", brut_miktar_elle: "1.05", birim_fiyat_elle: null });
    expect(govde[1]).toMatchObject({ malzeme_kodu: "M-050", brut_miktar_elle: "0.38", birim_fiyat_elle: "12.4" });
  });

  it("elle fiyattan listeye dönüş taslağa yazılır ve kayıtta birim_fiyat_elle null gider", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    await user.click(within(satir(tablo, "Salamura Karışımı")).getByRole("button", { name: /Listeye dön/ }));
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { satirlar: Record<string, unknown> } };
      expect(g.override.satirlar).toEqual({ "2": { elle_brut_kaldir: false, elle_fiyat_kaldir: true } });
    });
    await kaydetAkisi(user);
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    const recete = sonExcel.topluKaydet[0].govde.recete as Record<string, unknown>[];
    expect(recete[1]).toMatchObject({ malzeme_kodu: "M-050", birim_fiyat_elle: null, brut_miktar_elle: "0.38" });
  });

  it("uyarılar açılır listede görünür ve fiyatı olmayan satır vurgulanır", async () => {
    kur();
    const tablo = await tabloHazir();
    expect(satir(tablo, "Kapak")).toHaveAttribute("data-uyari", "true");
    expect(satir(tablo, "Pet Şişe 500 ml")).not.toHaveAttribute("data-uyari");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Uyarılar/ }));
    expect(await screen.findByText("Kapak M-77 fiyat listesinde yok, 0 TL alındı")).toBeInTheDocument();
    expect(screen.queryByText("Yurtdışı yüzde kuralı doğrulanmadı")).not.toBeInTheDocument();
  });

  it("yurtdışı uyarısında sarı bant gösterilir", async () => {
    kur({ yanit: { ...urunHesapYaniti, uyarilar: ["Yurtdışı ürün: yüzde kuralı uygulandı"] } });
    await tabloHazir();
    expect(screen.getByRole("note")).toHaveTextContent("Yurtdışı yüzde kuralı doğrulanmadı");
  });

  it("backend hata mesajını gösterir", async () => {
    kur({
      hesaplaHatasi: (g) =>
        (g.override as { fire?: Record<string, string> } | undefined)?.fire?.["1"]
          ? HttpResponse.json(
              { hata: "dogrulama", mesaj: "Elle brüt miktarı olan satıra fire override verilemez", alanlar: {} },
              { status: 422 },
            )
          : null,
    });
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    await user.type(within(tablo).getByLabelText(/Fire % .*Pet Şişe/), "9");
    expect(await screen.findByRole("alert")).toHaveTextContent("Elle brüt miktarı olan satıra fire override verilemez");
  });

  it("finansman faizi parametre override'ı olarak gönderilir", async () => {
    const istekler = kur();
    await tabloHazir();
    const user = userEvent.setup();
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { parametreler: Record<string, string> } };
      expect(g.override.parametreler).toEqual({ "faiz.TL": "0.5" });
    });
  });

  it("yüzde grafiği erişilebilir bir görsel olarak çizilir", async () => {
    kur();
    await tabloHazir();
    expect(await screen.findByRole("img", { name: /Maliyet ve satış payları/ })).toBeInTheDocument();
  });

  it("teklif turu ekler ve durumu değiştirir", async () => {
    const istekler = kur();
    await tabloHazir();
    const user = userEvent.setup();
    await screen.findByRole("option", { name: /#5/ });
    await user.type(screen.getByLabelText("Kâr %"), "20");
    await user.type(screen.getByLabelText("Müşteri"), "Örnek Müşteri");
    await user.click(screen.getByRole("button", { name: "Yeni tur" }));
    await waitFor(() => expect(istekler.teklifler).toHaveLength(1));
    expect(istekler.teklifler[0]).toMatchObject({ kar_orani: "0.2", musteri: "Örnek Müşteri" });
    const durum = await screen.findByLabelText("Durum — Tur 1");
    await user.selectOptions(durum, "gonderildi");
    await waitFor(() => expect(istekler.durumlar).toHaveLength(1));
    expect(istekler.durumlar[0]).toEqual({ id: "1", govde: { durum: "gonderildi" } });
  });
});

describe("UrunMaliyeti düzeltme turu 1", () => {
  it("fire taslağı olan satır elle brüte geçince diyalog fire'ın düşeceğini söyler ve gövdeden düşürür", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const f1 = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(f1);
    await user.type(f1, "5");
    await waitFor(() => expect(JSON.stringify(son(istekler.hesapla))).toContain('"0.05"'));
    const brut = within(tablo).getByLabelText(/Brüt — Pet Şişe/);
    await user.clear(brut);
    await user.type(brut, "1.05");
    // Elle brüt satırında fire hesaba da gönderilmez (backend 422).
    await waitFor(() => expect(JSON.stringify(son(istekler.hesapla))).not.toContain('"fire":{"1"'));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    expect(within(diyalog).getByText("Satır 1: fire düşer (elle brüt)")).toBeInTheDocument();
    await user.type(within(diyalog).getByLabelText("Neden"), "x");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    const recete = sonExcel.topluKaydet[0].govde.recete as Record<string, unknown>[];
    expect(recete[0]).toMatchObject({ brut_miktar_elle: "1.05", fire_override: null });
  });

  it("sunucuda elle brüt olan satır taslakta fire'e döndürülse de fire girdisi pasif kalır", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const sal = satir(tablo, "Salamura Karışımı");
    await user.click(within(sal).getByRole("button", { name: /Fire oranı uygula/ }));
    const fire = within(tablo).getByLabelText(/Fire % .*Salamura/);
    expect(fire).toBeDisabled();
    expect(fire).toHaveAccessibleDescription("Reçeteyi kaydedince fire girilebilir");
    await user.type(fire, "5");
    expect(istekler.hesapla.every((g) => !JSON.stringify(g).includes('"fire":{"2"'))).toBe(true);
  });

  it("başarısız yeniden hesapta eski sonuç 'güncel değil' rozetiyle gösterilir ve Kaydet kapanır; başarılı hesapta açılır", async () => {
    kur({
      hesaplaHatasi: (g) =>
        (g.override as { fire?: Record<string, string> } | undefined)?.fire?.["1"]
          ? HttpResponse.json({ hata: "dogrulama", mesaj: "Geçersiz fire", alanlar: {} }, { status: 422 })
          : null,
    });
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.type(fire, "9");
    expect(await screen.findByText("Güncel değil — son geçerli sonuç")).toBeInTheDocument();
    // Şeritte kırmızı hata metni; Kaydet kapalı (nedenle birlikte)
    expect(within(screen.getByRole("region", { name: "Kaydedilmemiş değişiklikler" })).getByRole("alert")).toHaveTextContent(
      "Geçersiz fire",
    );
    const kaydet = screen.getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled();
    expect(kaydet).toHaveAttribute("title", "Hesap hatası var: önce değişikliği düzeltin");
    expect(within(tablo).getByText("Pet Şişe 500 ml")).toBeInTheDocument();
    await user.clear(fire);
    await waitFor(() => expect(screen.queryByText("Güncel değil — son geçerli sonuç")).not.toBeInTheDocument());
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
  });

  it("kayıtlı hesap listesinde son tur, kâr ve durum özetini gösterir", async () => {
    sunucu.use(
      http.get("*/api/v1/urunler/:kod/hesaplar", () =>
        HttpResponse.json({
          kayitlar: [
            {
              id: 5,
              hesap_tarihi: "2026-10-21",
              olusturan: "Eşma",
              maliyet_tl: "38.13",
              satis_tl: "45.75",
              son_tur_no: 2,
              son_kar_orani: "0.25",
              son_musteri: "Örnek Müşteri",
              son_durum: "gonderildi",
            },
            { id: 4, hesap_tarihi: "2026-10-10", olusturan: "Eşma", maliyet_tl: "37", satis_tl: "44" },
          ],
          toplam: 2,
        }),
      ),
    );
    kur();
    const secici = await screen.findByRole("combobox", { name: "Kayıtlı hesap" });
    await waitFor(() => expect(within(secici).getAllByRole("option")).toHaveLength(2));
    const secenekler = within(secici).getAllByRole("option");
    expect(secenekler[0]).toHaveTextContent("#5 · 21.10.2026 · Eşma · Tur 2 · 25,0 % · Gönderildi");
    expect(secenekler[1]).toHaveTextContent(/^#4 · 10\.10\.2026 · Eşma$/);
  });

  it("eslestir: kodsuz satır, sonraki kodlu satırın reçete yerini almaz", () => {
    const hs = (kod: string | null) => ({ grup: "malzeme", kod, kalem: "x" }) as HesapSatiri;
    const rs = (sira: number, kod: string) => ({ sira, malzeme_kodu: kod }) as ReceteSatiri;
    const sonuc = eslestir([hs(null), hs("A")], [rs(1, "A"), rs(2, "B")]);
    expect(sonuc[1]?.malzeme_kodu).toBe("A");
    expect(sonuc[0]?.malzeme_kodu).toBe("B");
  });

  it("eslestir: sira doluysa aynı kodlu iki satır sira ile eşlenir", () => {
    const hs = (sira: number | null, kod: string) => ({ grup: "malzeme", kod, kalem: "x", sira }) as HesapSatiri;
    const rs = (sira: number, kod: string) => ({ sira, malzeme_kodu: kod }) as ReceteSatiri;
    // Sunucu satırları ters sırada: kod ile eşleme 2. satırı 1. reçete satırına bağlardı.
    const sonuc = eslestir([hs(2, "A"), hs(1, "A")], [rs(1, "A"), rs(2, "A")]);
    expect(sonuc[0]?.sira).toBe(2);
    expect(sonuc[1]?.sira).toBe(1);
    // sira yoksa (eski anlık görüntü) kod/sıra eşlemesi sürer.
    const eski = eslestir([hs(null, "A"), hs(null, "A")], [rs(1, "A"), rs(2, "A")]);
    expect(eski.map((r) => r?.sira)).toEqual([1, 2]);
  });

  it("Döviz sütunu doviz değerini gösterir, boşsa —", async () => {
    const satirlar = urunHesapYaniti.satirlar.map((s, i) =>
      s.grup === "malzeme" ? { ...s, sira: i + 1, doviz: i === 0 ? "USD" : null } : s,
    );
    kur({ yanit: { ...urunHesapYaniti, satirlar } });
    const tablo = await tabloHazir();
    expect(within(tablo).getByRole("columnheader", { name: "Döviz" })).toBeInTheDocument();
    const basliklar = within(tablo)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    const k = basliklar.indexOf("Döviz");
    expect(within(satir(tablo, "Pet Şişe 500 ml")).getAllByRole("cell")[k]).toHaveTextContent("USD");
    expect(within(satir(tablo, "Salamura Karışımı")).getAllByRole("cell")[k]).toHaveTextContent("—");
  });
});

const dovizli = (dovizler: Record<string, string | null>) => ({
  ...urunHesapYaniti,
  satirlar: urunHesapYaniti.satirlar.map((s) =>
    s.grup === "malzeme" && s.kod && s.kod in dovizler ? { ...s, doviz: dovizler[s.kod] } : s,
  ),
});

describe("UrunMaliyeti son tur — F2 döviz etiketleri", () => {
  it("birim fiyat hücresi malzemenin dövizini gösterir (TL sabitlenmez)", async () => {
    kur({ yanit: dovizli({ "M-001": "EUR", "M-77": "GBP" }) });
    const tablo = await tabloHazir();
    const pet = satir(tablo, "Pet Şişe 500 ml");
    expect(within(pet).getByLabelText("Birim fiyat (EUR) — Pet Şişe 500 ml")).toHaveValue("5,9");
    expect(within(pet).getByText("EUR")).toBeInTheDocument();
    expect(within(pet).queryByLabelText("Birim fiyat (TL) — Pet Şişe 500 ml")).not.toBeInTheDocument();
  });

  it("elle fiyat girdisinin etiketi dövizi içerir; hesapla gövdesine elle fiyat gider", async () => {
    const istekler = kur({ yanit: dovizli({ "M-001": "USD" }) });
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fiyat = within(tablo).getByLabelText("Birim fiyat (USD) — Pet Şişe 500 ml");
    await user.clear(fiyat);
    await user.type(fiyat, "6");
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { satirlar: Record<string, { birim_fiyat_elle?: string }> } };
      expect(g.override.satirlar["1"].birim_fiyat_elle).toBe("6");
    });
  });
});

describe("UrunMaliyeti son tur", () => {
  const fireYaz = async (tablo: HTMLElement, ad: RegExp, metin: string) => {
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(ad);
    await user.clear(fire);
    await user.type(fire, metin);
    return user;
  };

  it("F5: aralık dışı fire yüzdesi istemcide reddedilir, hesaba gönderilmez", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    await fireYaz(tablo, /Fire % .*Pet Şişe/, "150");
    expect(await screen.findByText("Fire % 0 ile 100 arasında olmalı (100 hariç)")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 450));
    expect(istekler.hesapla.every((g) => !JSON.stringify(g).includes("1.5"))).toBe(true);
    // Geçersiz girdide override kalkar: son hesap isteğinde fire yok.
    expect(JSON.stringify(son(istekler.hesapla))).not.toContain('"fire"');
  });

  it("F5: sunucu hata mesajına alan ayrıntıları eklenir", async () => {
    kur({
      hesaplaHatasi: (g) =>
        (g.override as { fire?: Record<string, string> } | undefined)?.fire?.["1"]
          ? HttpResponse.json({ hata: "dogrulama", mesaj: "İstek geçersiz", alanlar: { "override.fire": "çok büyük" } }, { status: 422 })
          : null,
    });
    const tablo = await tabloHazir();
    await fireYaz(tablo, /Fire % .*Pet Şişe/, "9");
    expect(await screen.findByRole("alert")).toHaveTextContent("İstek geçersiz — override.fire: çok büyük");
  });

  it("I1: fire sütunu 'Fire %' başlığı taşır", async () => {
    kur();
    const tablo = await tabloHazir();
    expect(within(tablo).getByRole("columnheader", { name: "Fire %" })).toBeInTheDocument();
  });

  const surumluRecete = () => {
    let surum = 10;
    sunucu.use(
      http.get("*/api/v1/urunler/:kod/recete", () => HttpResponse.json({ ...urunReceteleri, id: surum })),
      http.post("*/api/v1/urunler/:kod/recete", () => {
        surum = 11;
        return HttpResponse.json({ id: 11, versiyon: 3, satir_sayisi: 3 }, { status: 201 });
      }),
    );
    return (n: number) => (surum = n);
  };

  it("I5: reçete sürümü dışarıdan değişince satır taslakları temizlenir", async () => {
    kur();
    const surumAyarla = surumluRecete();
    const tablo = await tabloHazir();
    await fireYaz(tablo, /Fire % .*Pet Şişe/, "5");
    await waitFor(() => expect(screen.getByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument());
    surumAyarla(11);
    await sonQc.invalidateQueries({ queryKey: ["recete"] });
    await waitFor(() => expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument());
  });

  it("I2: kayıtlı hesap seçimi salt okunur hesap görünümüne bağlanır", async () => {
    kur();
    await tabloHazir();
    const bag = await screen.findByRole("link", { name: "Kayıtlı hesabı görüntüle" });
    expect(bag).toHaveAttribute("href", "/hesaplar/5");
  });

  it("H1: Geçmiş hesaplar bölümü Teklif turlarının altında kayıtlı hesabı listeler", async () => {
    kur();
    await tabloHazir();
    const bolum = await screen.findByRole("region", { name: "Geçmiş hesaplar" });
    expect(within(bolum).getByRole("heading", { name: "Geçmiş hesaplar" })).toBeInTheDocument();
    expect(await within(bolum).findByRole("link", { name: "#5" })).toHaveAttribute("href", "/hesaplar/5?senaryo=1");
    expect(within(bolum).getByRole("checkbox", { name: "Kıyas için seç: 21.10.2026 #5" })).toBeInTheDocument();
    const teklif = screen.getByRole("region", { name: "Teklif turları" });
    expect(teklif.compareDocumentPosition(bolum) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

const excelKur = () => kur({ yanit: urunExcelHesapYaniti });
const basliklar = (tablo: HTMLElement) =>
  within(tablo)
    .getAllByRole("columnheader")
    .map((h) => (h.textContent ?? "").trim());

describe("U5 reçete tablosu: Excel sütun sırası ve ağaç", () => {
  it("sütunlar Satır, Kod, Cinsi, Miktar, Fire %, Brüt, Birim, Birim fiyat, Kaynak (Z/S), Döviz, Tutar, Maliyet %, Satış % sırasındadır", async () => {
    excelKur();
    const tablo = await tabloHazir();
    expect(basliklar(tablo).slice(0, 14)).toEqual([
      "Satır",
      "Kod",
      "Cinsi",
      "Miktar",
      "Fire %",
      "Brüt",
      "Birim",
      "Birim fiyat",
      "Kaynak",
      "Döviz",
      "Tutar (firesiz)",
      "Tutar (fireli)",
      "Maliyet %",
      "Satış %",
    ]);
  });

  it("birim ve Kaynak (Z/S: Ziraat / Satın alma) hücreleri satırdan gelir; ürünün kendi satırı 'Ürün' rozetli, sonraki yaprak satırlar girintilidir", async () => {
    excelKur();
    const tablo = await tabloHazir();
    const k = basliklar(tablo);
    const hucre = (ad: string, sutun: string) => within(satir(tablo, ad)).getAllByRole("cell")[k.indexOf(sutun)];
    expect(hucre("Salamura Karışımı", "Birim")).toHaveTextContent("kg");
    expect(hucre("Salamura Karışımı", "Kaynak")).toHaveTextContent("Satın alma");
    expect(hucre("Kapak", "Kaynak")).toHaveTextContent("Ziraat");
    expect(within(tablo).getAllByRole("columnheader")[k.indexOf("Kaynak")]).toHaveAttribute(
      "title",
      expect.stringContaining("Ziraat: enflasyon uygulanmaz"),
    );
    expect(within(satir(tablo, "Pet Şişe 500 ml")).getByText("Ürün")).toBeInTheDocument();
    expect(satir(tablo, "Pet Şişe 500 ml")).toHaveAttribute("data-girinti", "0");
    // Ürünün kendi satırından sonra girinti yok.
    expect(satir(tablo, "Salamura Karışımı")).toHaveAttribute("data-girinti", "0");
    expect(satir(tablo, "Kapak")).toHaveAttribute("data-girinti", "0");
  });

  it("ürün kodundan farklı ara mamul satırı 'Ara mamul' rozeti taşır", async () => {
    const satirlar = urunExcelHesapYaniti.satirlar.map((s) => (s.kod === "URUN-001" ? { ...s, kod: "YM-01" } : s));
    kur({ yanit: { ...urunExcelHesapYaniti, satirlar } });
    const tablo = await tabloHazir();
    expect(within(satir(tablo, "Pet Şişe 500 ml")).getByText("Ara mamul")).toBeInTheDocument();
    expect(satir(tablo, "Salamura Karışımı")).toHaveAttribute("data-girinti", "1");
  });
});

describe("U4 gider kalemleri: Excel blokları", () => {
  it("üç grup başlığı, ara toplamlar, gider toplamı ve toplam birim maliyet gösterilir", async () => {
    excelKur();
    await tabloHazir();
    const bolge = screen.getByRole("region", { name: "Gider kalemleri" });
    const tablo = within(bolge).getByRole("table");
    expect(basliklar(tablo)).toEqual([
      "Kalem",
      "Miktar",
      "Fire %",
      "Brüt",
      "Birim",
      "Birim fiyat",
      "Döviz",
      "Tutar",
      "Maliyet %",
      "Satış %",
    ]);
    for (const g of ["Direkt işçilik", "Genel üretim giderleri", "Diğer giderler"]) {
      expect(within(tablo).getAllByText(g).length).toBeGreaterThanOrEqual(1);
    }
    const satirOf = (metin: string) => within(tablo).getByText(metin).closest("tr") as HTMLElement;
    expect(within(satirOf("Elektrik Giderleri")).getByText("3,10 TL")).toBeInTheDocument();
    expect(within(satirOf("Gider toplamı")).getByText("4,95 TL")).toBeInTheDocument();
    // malzeme 12,23751 + gider toplamı 4,95
    expect(within(satirOf("Toplam birim maliyet")).getByText("17,19 TL")).toBeInTheDocument();
    expect(within(satirOf("Diğer giderler toplamı")).getByText("2,40 TL")).toBeInTheDocument();
    expect(within(tablo).getByText(/dolum yapılan toplam adede göre dağıtılmıştır/)).toBeInTheDocument();
  });
});

describe("U6 toplamlar kartı: Excel sırası", () => {
  it("satırlar Excel sırasında; döviz tutarları kendi para birimiyle; notlar altta", async () => {
    excelKur();
    await tabloHazir();
    const kart = screen.getByRole("region", { name: "Toplamlar" });
    const etiketler = Array.from(kart.querySelectorAll("[data-etiket]")).map((e) => e.textContent);
    expect(etiketler).toEqual([
      "Hammadde-yardımcı malzeme toplamı",
      "Direkt işçilik",
      "GÜG",
      "Gider toplamı",
      "Toplam birim maliyet",
      "Diğer giderler",
      "Giydirilmiş maliyet",
      "Finansman (TL)",
      "Finansman dahil maliyet TL",
      "Finansman dahil maliyet USD",
      "Finansman dahil maliyet EUR",
      "Finansman dahil maliyet GBP",
      "Finansman dahil maliyet ZAR",
    ]);
    const satirOf = (e: string) => within(kart).getByText(e).parentElement as HTMLElement;
    expect(within(satirOf("Finansman dahil maliyet GBP")).getByText("0,510 GBP")).toBeInTheDocument();
    expect(within(satirOf("Finansman dahil maliyet ZAR")).getByText("11,230 ZAR")).toBeInTheDocument();
    expect(within(satirOf("Toplam birim maliyet")).getByText("17,19 TL")).toBeInTheDocument();
    // Satış fiyatı, süzme kg ve teklifler Toplamlar kartında tekrar etmez; ayrı "Satış fiyatı (%20)" bölümündedir.
    expect(within(kart).queryByText(/Satış fiyatı|Süzme kg|Teklif/)).not.toBeInTheDocument();
    expect(within(kart).queryByText("Fiyatlara KDV dahil değildir")).not.toBeInTheDocument();
  });

  it("Satış fiyatı (%20) tablosu: para birimi, kur, fireli/firesiz fiyat; not, süzme kg ve teklifler", async () => {
    excelKur();
    await tabloHazir();
    const bolum = screen.getByRole("region", { name: "Satış fiyatı" });
    expect(within(bolum).getByRole("heading", { name: "Satış fiyatı (%20)" })).toBeInTheDocument();
    const tablo = within(bolum).getByRole("table", { name: "Satış fiyatı tablosu" });
    expect(
      within(tablo)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Para birimi", "Kur", "Fiyat (fireli)", "Fiyat (firesiz)"]);
    const satirlar = within(tablo).getAllByRole("row").slice(1);
    expect(satirlar.map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(["TL", "USD", "EUR", "GBP", "ZAR"]);
    const hucre = (pb: string, i: number) =>
      within(satirlar.find((r) => within(r).getAllByRole("cell")[0].textContent === pb) as HTMLElement).getAllByRole("cell")[i].textContent;
    expect(hucre("TL", 1)).toBe("—");
    expect(hucre("TL", 2)).toBe("45,76 TL");
    expect(hucre("USD", 1)).toBe("50,00");
    expect(hucre("GBP", 1)).toBe("65,00");
    expect(hucre("ZAR", 1)).toBe("2,70");
    expect(hucre("GBP", 2)).toBe("0,612 GBP");
    // Not satırı vurgulu liste; süzme kg birim fiyatı tek satır; teklifler oranlarla.
    expect(within(bolum).getByLabelText("Hesap notları")).toHaveTextContent("Fiyatlara KDV dahil değildir");
    expect(within(bolum).getByText("Süzme kg birim fiyatı")).toBeInTheDocument();
    const teklifler = within(bolum).getByRole("table", { name: "Teklifler tablosu" });
    expect(
      within(teklifler)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["", "1. teklif %20", "2. teklif %17", "3. teklif %14"]);
    expect(within(teklifler).getAllByText("0,785 USD").length).toBeGreaterThanOrEqual(1);
  });
});

const parametreBolgesi = (ad: string) => screen.getByRole("region", { name: ad });

describe("U2 kurlar ve enflasyon bloğu", () => {
  it("enflasyon, maliyet sapma ve kurlar değerleriyle gösterilir; 'ne olur' düzenlemesi override.parametreler olarak gider", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const blok = parametreBolgesi("Kurlar ve enflasyon");
    expect(within(blok).getByLabelText("Enflasyon (%)")).toHaveValue("25");
    expect(within(blok).getByLabelText("Maliyet sapma (%)")).toHaveValue("3");
    for (const [pb, v] of [
      ["USD", "50"],
      ["EUR", "55"],
      ["GBP", "65"],
      ["CHF", "58"],
      ["RUB", "0.6"],
      ["ZAR", "2.7"],
    ]) {
      expect(within(blok).getByLabelText(`Kur ${pb}`)).toHaveValue(v);
    }
    const user = userEvent.setup();
    const usd = within(blok).getByLabelText("Kur USD");
    await user.clear(usd);
    await user.type(usd, "52");
    const enf = within(blok).getByLabelText("Enflasyon (%)");
    await user.clear(enf);
    await user.type(enf, "30");
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { parametreler: Record<string, string> } };
      expect(g.override.parametreler).toEqual({ "kur.USD": "52", enflasyon: "0.3" });
    });
    expect(within(blok).getByRole("link", { name: "Parametrelerde kalıcı değiştir" })).toHaveAttribute("href", "/parametreler?senaryo=1");
  });
});

describe("U3 finansman tablosu", () => {
  it("para birimi satırlarında faiz, stok süresi, dönem faizi ve kendi para biriminde faiz tutarı; altında finansman dahil maliyet ve kur", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const blok = parametreBolgesi("Finansman");
    const tablo = within(blok).getByRole("table", { name: "Finansman tablosu" });
    expect(basliklar(tablo)).toEqual(["Para birimi", "Faiz oranı (%)", "Stok süresi (ay)", "Dönem faizi", "Faiz tutarı (TL)"]);
    const tl = within(tablo).getByText("TL", { selector: "td" }).closest("tr") as HTMLElement;
    expect(within(tl).getByLabelText("Faiz TL (%)")).toHaveValue("40");
    expect(within(tl).getByLabelText("Stok süresi TL (ay)")).toHaveValue("6");
    expect(within(tl).getByText("20,0 %")).toBeInTheDocument(); // 0.4 / 12 * 6
    expect(within(tl).getByText("6,36 TL")).toBeInTheDocument();
    const usd = within(tablo).getByText("USD", { selector: "td" }).closest("tr") as HTMLElement;
    expect(within(usd).getByText("0,95 TL")).toBeInTheDocument(); // motor TL cinsinden verir
    expect(within(usd).queryByText(/\d USD$/)).not.toBeInTheDocument();
    expect(within(usd).getByText("3,0 %")).toBeInTheDocument(); // 0.06 / 12 * 6
    expect(within(tablo).getByText("ZAR", { selector: "td" })).toBeInTheDocument();

    const maliyet = within(blok).getByRole("table", { name: "Finansman dahil maliyet" });
    expect(basliklar(maliyet)).toEqual(["Para birimi", "Finansman dahil maliyet", "Kur"]);
    const gbp = within(maliyet).getByText("GBP", { selector: "td" }).closest("tr") as HTMLElement;
    expect(within(gbp).getByText("0,5100 GBP")).toBeInTheDocument();
    expect(within(gbp).getByText("65,0000")).toBeInTheDocument();
    const tlMaliyet = within(maliyet).getByText("TL", { selector: "td" }).closest("tr") as HTMLElement;
    expect(within(tlMaliyet).getByText("38,13 TL")).toBeInTheDocument();

    const user = userEvent.setup();
    const faiz = within(tl).getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    const stok = within(usd).getByLabelText("Stok süresi USD (ay)");
    await user.clear(stok);
    await user.type(stok, "3");
    await waitFor(() => {
      const g = son(istekler.hesapla) as { override: { parametreler: Record<string, string> } };
      expect(g.override.parametreler).toEqual({ "faiz.TL": "0.5", "stok_ay.USD": "3" });
    });
  });
});

describe("U1 üretim bilgileri bloğu", () => {
  const blok = () => screen.getByRole("region", { name: "Üretim bilgileri" });

  it("Excel alanları değerleriyle, hesap tarihi ve senaryoyla gösterilir", async () => {
    excelKur();
    await tabloHazir();
    const b = await screen.findByRole("region", { name: "Üretim bilgileri" });
    expect(within(b).getByLabelText("Süzme miktar (kg)")).toHaveValue("0.45");
    expect(within(b).getByLabelText("Vardiya üretim adedi")).toHaveValue("12000");
    expect(within(b).getByLabelText("Vardiya saati")).toHaveValue("7.5");
    expect(within(b).getByLabelText("Dolum personel")).toHaveValue("6");
    expect(within(b).getByLabelText("Etiketleme adedi")).toHaveValue("3000");
    expect(within(b).getByLabelText("Etiket personel")).toHaveValue("2");
    expect(within(b).getByLabelText("Ambalaj (ml)")).toHaveValue("720");
    expect(within(b).getByLabelText("Mal kabul miktarı (kg)")).toHaveValue("0.5");
    expect(within(b).getByLabelText("Mal kabul fire (%)")).toHaveValue("5");
    expect(within(b).getByLabelText("Pazar")).toHaveValue("Yurtiçi");
    expect(within(b).getByLabelText("Taze/Turşu sınıfı")).toHaveValue("Taze/Turşu");
    expect(within(b).getByLabelText("Pazarlama/yönetim payı uygula")).toBeChecked();
    await waitFor(() => expect(within(b).getByLabelText("Üretim hattı")).toHaveValue("Niko"));
    expect(within(b).getByLabelText("Üretim hattı")).toContainElement(within(b).getByRole("option", { name: "Herbort" }));
    expect(b).toHaveTextContent("21.10.2026");
    expect(b).toHaveTextContent("2026-2027 · Varsayılan");
  });

  it("hücre düzenlemeleri override.uretim olarak gider; vardiya saati override.parametreler'e yazılır; şerit sayar", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const b = blok();
    const user = userEvent.setup();
    const vardiya = within(b).getByLabelText("Vardiya üretim adedi");
    await user.clear(vardiya);
    await user.type(vardiya, "15000");
    const fire = within(b).getByLabelText("Mal kabul fire (%)");
    await user.clear(fire);
    await user.type(fire, "8");
    await user.click(within(b).getByLabelText("Pazarlama/yönetim payı uygula"));
    const saat = within(b).getByLabelText("Vardiya saati");
    await user.clear(saat);
    await user.type(saat, "8");
    await user.selectOptions(within(b).getByLabelText("Pazar"), "Yurtdışı");
    await waitFor(() => {
      const g = son(istekler.hesapla) as {
        override: { uretim: Record<string, unknown>; parametreler: Record<string, string>; urun: Record<string, unknown> };
      };
      expect(g.override.uretim).toEqual({
        vardiya_uretim_adedi: "15000",
        mal_kabul_fire: "0.08",
        pazarlama_yonetim_uygula: false,
      });
      expect(g.override.parametreler).toEqual({ vardiya_saati: "8" });
      expect(g.override.urun).toEqual({ pazar: "Yurtdışı" });
    });
    expect(screen.getByText("5 alanda değişiklik")).toBeInTheDocument();
    // sunucudaki değere dönmek taslağı düşürür
    await user.click(within(b).getByLabelText("Pazarlama/yönetim payı uygula"));
    expect(screen.getByText("4 alanda değişiklik")).toBeInTheDocument();
  });

  it("Kaydet: ürün kartı ve üretim hedefi tek gövdede tam kayıt olarak gider (PUT'lar çağrılmaz)", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const b = blok();
    const user = userEvent.setup();
    const vardiya = within(b).getByLabelText("Vardiya üretim adedi");
    await user.clear(vardiya);
    await user.type(vardiya, "15000");
    await waitFor(() => expect(within(b).getByLabelText("Üretim hattı")).toHaveValue("Niko"));
    await user.selectOptions(within(b).getByLabelText("Üretim hattı"), "Herbort");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    const hedefSatiri = diyalog.querySelector('[data-alan="hedef.vardiya_uretim_adedi"]') as HTMLElement;
    expect(hedefSatiri).toHaveTextContent("12000");
    expect(hedefSatiri).toHaveTextContent("15000");
    const hatSatiri = diyalog.querySelector('[data-alan="urun.hat"]') as HTMLElement;
    expect(hatSatiri).toHaveTextContent("Niko");
    expect(hatSatiri).toHaveTextContent("Herbort");
    await user.type(within(diyalog).getByLabelText("Neden"), "Hat değişti");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    expect(sonExcel.topluKaydet[0].govde).toEqual({
      senaryo_id: 1,
      neden: "Hat değişti",
      hesabi_kaydet: true,
      urun: {
        ad: "Salatalık Turşusu 720 ml",
        ambalaj_hacmi: "720",
        hat: "Herbort",
        taze_tursu_sinifi: "Taze/Turşu",
        suzme_kg: "0.45",
        pazar: "Yurtiçi",
      },
      uretim_hedefi: {
        vardiya_uretim_adedi: "15000",
        dolum_personel: "6",
        etiketleme_adedi: "3000",
        etiket_personel: "2",
        mal_kabul_miktar_kg: "0.5",
        mal_kabul_fire: "0.05",
        pazarlama_yonetim_uygula: true,
      },
    });
    expect(sonExcel.urunKaydet).toHaveLength(0);
    expect(sonExcel.hedefKaydet).toHaveLength(0);
    expect(await screen.findByRole("status", { name: "Kayıt durumu" })).toHaveTextContent("ürün kartı, üretim hedefi");
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
    // Taslak sıfırlandı: hesap taslaksız yeniden koşar.
    await waitFor(() => expect(son(istekler.hesapla)).not.toHaveProperty("override"));
  });

  it("Marka: üretim bilgilerinde yazılır, hesaba (override) gitmez; Kaydet ürün kartına marka ile yazar", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const b = blok();
    const user = userEvent.setup();
    const marka = within(b).getByLabelText("Marka");
    expect(marka).toHaveValue("");
    expect(marka).toHaveAttribute("placeholder", "addan türetilir");
    await user.type(marka, "Berrak");
    await waitFor(() => expect(screen.getByText("1 alanda değişiklik")).toBeInTheDocument());
    expect(son(istekler.hesapla)).not.toHaveProperty("override.urun");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    const markaSatiri = diyalog.querySelector('[data-alan="urun.marka"]') as HTMLElement;
    expect(markaSatiri).toHaveTextContent("Marka");
    expect(markaSatiri).toHaveTextContent("Berrak");
    await user.type(within(diyalog).getByLabelText("Neden"), "Marka girildi");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    expect(sonExcel.topluKaydet[0].govde.urun).toEqual({
      ad: "Salatalık Turşusu 720 ml",
      ambalaj_hacmi: "720",
      hat: "Niko",
      taze_tursu_sinifi: "Taze/Turşu",
      suzme_kg: "0.45",
      pazar: "Yurtiçi",
      marka: "Berrak",
    });
  });
});

describe("Fix round 1", () => {
  it("finansman satırı gider gruplarında listelenmez; Diğer ara toplamı toplamlar.diger'dir", async () => {
    excelKur();
    await tabloHazir();
    const tablo = within(screen.getByRole("region", { name: "Gider kalemleri" })).getByRole("table");
    expect(within(tablo).queryByText("Finansman")).not.toBeInTheDocument();
    const diger = within(tablo).getByText("Diğer giderler toplamı").closest("tr") as HTMLElement;
    expect(within(diger).getByText("2,40 TL")).toBeInTheDocument();
  });

  it("Kaydet diyaloğu ham anahtar göstermez: parametre Türkçe etiketle listelenir", async () => {
    excelKur();
    await tabloHazir();
    const user = userEvent.setup();
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    expect(within(diyalog).getByText("Faiz TL (%)")).toBeInTheDocument();
    expect(within(diyalog).queryByText(/faiz\.TL/)).not.toBeInTheDocument();
  });
});

describe("Faz 4b-ek: Net miktar ve kur sırası", () => {
  it("Net miktar (kg) satırı Süzme miktarın hemen altında salt okunur '—' ve 'Excel'de kullanılmıyor' ipucuyla görünür", async () => {
    excelKur();
    await tabloHazir();
    const b = await screen.findByRole("region", { name: "Üretim bilgileri" });
    const etiketler = Array.from(b.querySelectorAll("label > span.text-muted-foreground")).map((e) => e.textContent);
    expect(etiketler.indexOf("Net miktar (kg)")).toBe(etiketler.indexOf("Süzme miktar (kg)") + 1);
    const net = within(b).getByTitle("Excel'de kullanılmıyor");
    expect(net).toHaveTextContent("—");
    expect(b.querySelector("input[aria-label='Net miktar (kg)']")).toBeNull();
  });

  it("kurlar Excel sırasında (USD, EUR, GBP, CHF, RUB, ZAR) listelenir", async () => {
    excelKur();
    await tabloHazir();
    const blok = parametreBolgesi("Kurlar ve enflasyon");
    const kurEtiketleri = Array.from(blok.querySelectorAll("label > span.text-muted-foreground"))
      .map((e) => e.textContent)
      .filter((e) => e?.endsWith(" kuru"));
    expect(kurEtiketleri).toEqual(["USD kuru", "EUR kuru", "GBP kuru", "CHF kuru", "RUB kuru", "ZAR kuru"]);
  });
});

describe("Faz 4c U2: hücreye yaz", () => {
  type Hesap = {
    override: {
      satirlar: Record<string, Record<string, unknown>>;
      gider_oranlari: Record<string, string>;
      urun: Record<string, string>;
      uretim: Record<string, unknown>;
    };
  };
  const sonG = (i: { hesapla: unknown[] }) => son(i.hesapla) as Hesap;

  it("miktar hücresi override.satirlar.miktar yazılır, hücre vurgulanır ve ipucu eski değeri söyler; boşaltınca taslak silinir", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const miktar = within(tablo).getByLabelText(/Miktar — Pet Şişe/);
    expect(miktar).not.toHaveAttribute("data-degisti");
    await user.clear(miktar);
    await user.type(miktar, "2,5");
    await waitFor(() =>
      expect(sonG(istekler).override.satirlar).toEqual({ "1": { miktar: "2.5", elle_brut_kaldir: false, elle_fiyat_kaldir: false } }),
    );
    expect(miktar).toHaveAttribute("data-degisti", "true");
    expect(miktar).toHaveAttribute("title", "Eski değer: 1");
    expect(screen.getByText("1 satırda değişiklik")).toBeInTheDocument();
    await user.clear(miktar);
    await waitFor(() => expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument());
  });

  it("brüt boşaltılınca kurala bırakılır, birim fiyat boşaltılınca listeye dönülür; kayıtta null gider", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const brut = within(tablo).getByLabelText(/Brüt — Salamura/);
    expect(brut).toHaveValue("0,38");
    await user.clear(brut);
    const fiyat = within(tablo).getByLabelText(/Birim fiyat — Salamura/);
    await user.clear(fiyat);
    await waitFor(() => expect(sonG(istekler).override.satirlar).toEqual({ "2": { elle_brut_kaldir: true, elle_fiyat_kaldir: true } }));
    expect(brut).toHaveAttribute("title", "Eski değer: 0,38");
    expect(fiyat).toHaveAttribute("title", "Eski değer: 12,4");
    await kaydetAkisi(user);
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    const recete = sonExcel.topluKaydet[0].govde.recete as Record<string, unknown>[];
    expect(recete[1]).toMatchObject({ malzeme_kodu: "M-050", brut_miktar_elle: null, birim_fiyat_elle: null });
  });

  it("geçersiz metin taslağı değiştirmez; elle brütte fire pasiftir ve ipucu elle brüt uyarısı verir", async () => {
    const istekler = kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const miktar = within(tablo).getByLabelText(/Miktar — Pet Şişe/);
    await user.clear(miktar);
    await user.type(miktar, "abc");
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
    expect(istekler.hesapla.every((g) => !JSON.stringify(g).includes("override"))).toBe(true);
    expect(within(tablo).getByLabelText(/Fire % .*Salamura/)).toHaveAttribute("title", "elle brüt: fire uygulanmaz");
  });

  it("rozetler taslağa göre canlı güncellenir: elle brüt yazılınca Elle, kurala dönünce Fire", async () => {
    kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const pet = satir(tablo, "Pet Şişe 500 ml");
    expect(within(pet).getByText("Fire")).toBeInTheDocument();
    const brut = within(pet).getByLabelText(/Brüt — Pet/);
    await user.clear(brut);
    await user.type(brut, "1.1");
    expect(within(pet).getByRole("button", { name: /Miktar kaynağı .*Elle/ })).toBeInTheDocument();
    await user.click(within(pet).getByRole("button", { name: /Fire oranı uygula/ }));
    expect(within(pet).queryByRole("button", { name: /Miktar kaynağı/ })).not.toBeInTheDocument();
    expect(within(pet).getByText("Fire")).toBeInTheDocument();
  });

  it("ürün satırı ve ara mamul satırları düzenlenmez", async () => {
    excelKur();
    const tablo = await tabloHazir();
    const urun = satir(tablo, "Pet Şişe 500 ml");
    expect(within(urun).queryAllByRole("textbox")).toHaveLength(0);
    expect(urun).toHaveClass("font-semibold");
    expect(within(satir(tablo, "Salamura Karışımı")).getAllByRole("textbox").length).toBeGreaterThan(0);
  });

  it("seviye girintisi: 8 + seviye x 14 px, seviye > 0 için └ işareti", async () => {
    const seviye = [0, 1, 2];
    const satirlar = urunExcelHesapYaniti.satirlar.map((s, i) => (i < 3 ? { ...s, seviye: seviye[i] } : s));
    kur({ yanit: { ...urunExcelHesapYaniti, satirlar } });
    const tablo = await tabloHazir();
    const cinsi = (ad: string) => within(satir(tablo, ad)).getByText(ad, { exact: false }).closest("td") as HTMLElement;
    expect(cinsi("Pet Şişe 500 ml")).toHaveStyle({ paddingLeft: "8px" });
    expect(cinsi("Salamura Karışımı")).toHaveStyle({ paddingLeft: "22px" });
    expect(cinsi("Kapak")).toHaveStyle({ paddingLeft: "36px" });
    expect(satir(tablo, "Salamura Karışımı")).toHaveAttribute("data-seviye", "1");
    expect(satir(tablo, "Pet Şişe 500 ml")).toHaveAttribute("data-seviye", "0");
    expect(within(cinsi("Pet Şişe 500 ml")).queryByText("└")).not.toBeInTheDocument();
    expect(within(cinsi("Kapak")).getByText("└")).toBeInTheDocument();
  });

  it("seviye null: girinti dugum_tipi sezgisinden gelir, data-seviye yoktur", async () => {
    const satirlar = urunExcelHesapYaniti.satirlar.map((s) => (s.kod === "URUN-001" ? { ...s, kod: "YM-01" } : s));
    kur({ yanit: { ...urunExcelHesapYaniti, satirlar } });
    const tablo = await tabloHazir();
    expect(satir(tablo, "Salamura Karışımı")).not.toHaveAttribute("data-seviye");
    expect(satir(tablo, "Salamura Karışımı")).toHaveAttribute("data-girinti", "1");
  });

  it("gider birim fiyatı anahtarla taslağa yazılır (hat casefold); ipucu Senaryo geneli, elektrik için kalıcı yazım notu da", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const gider = screen.getByRole("region", { name: "Gider kalemleri" });
    const user = userEvent.setup();
    const dolum = within(gider).getByLabelText("Birim fiyat — Direkt işçilik");
    expect(dolum).toHaveAttribute("title", "Senaryo geneli oran — tüm ürünleri etkiler");
    await user.clear(dolum);
    await user.type(dolum, "1000");
    const elektrik = within(gider).getByLabelText("Birim fiyat — Elektrik Giderleri");
    expect(elektrik).toHaveAttribute("title", expect.stringContaining("kalıcı yazım Gider Dağıtım sayfasından"));
    await user.clear(elektrik);
    await user.type(elektrik, "0,002");
    await waitFor(() => expect(sonG(istekler).override.gider_oranlari).toEqual({ dolum_iscilik_sn: "1000", "elektrik_sn.niko": "0.002" }));
    expect(dolum).toHaveAttribute("title", expect.stringContaining("Eski değer: 925"));
    // Pazarlama (diğer giderler) senaryo oranı olarak düzenlenmez; yalnız bu ürün için elle değer yazılabilir
    expect(within(gider).queryByLabelText("Birim fiyat — Pazarlama Satış Giderleri")).not.toBeInTheDocument();
  });

  it("gider tutarına tıklayınca bu ürün için elle değer yazılır; Elle rozetiyle formüle dönülür", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const gider = screen.getByRole("region", { name: "Gider kalemleri" });
    const user = userEvent.setup();
    expect(within(gider).queryByLabelText("Tutar — Elektrik Giderleri")).not.toBeInTheDocument(); // formüllü hücre düz metin
    await user.click(within(gider).getByRole("button", { name: "Tutar — Elektrik Giderleri: bu ürün için elle değer yaz" }));
    const tutar = within(gider).getByLabelText("Tutar — Elektrik Giderleri");
    expect(tutar).toHaveFocus();
    await user.clear(tutar);
    await user.type(tutar, "0");
    await waitFor(() =>
      expect((son(istekler.hesapla) as { override: { gider_elle?: unknown } }).override.gider_elle).toEqual({ elektrik: { tutar: "0" } }),
    );
    await user.click(within(gider).getByRole("button", { name: "Tutar — Elektrik Giderleri: Elle. Formüle dön" }));
    await waitFor(() => expect(son(istekler.hesapla)).not.toHaveProperty("override"));
  });

  it("Kaydet: dolum oranı havuz toplamı olarak yazılır, elektrik yalnız hesap override ında kalır; diyalog oran ve havuz toplamını gösterir", async () => {
    excelKur();
    await tabloHazir();
    const gider = screen.getByRole("region", { name: "Gider kalemleri" });
    const user = userEvent.setup();
    const dolum = within(gider).getByLabelText("Birim fiyat — Direkt işçilik");
    await user.clear(dolum);
    await user.type(dolum, "1000");
    const elektrik = within(gider).getByLabelText("Birim fiyat — Elektrik Giderleri");
    await user.clear(elektrik);
    await user.type(elektrik, "0,002");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    const d = diyalog.querySelector('[data-alan="gider.dolum_iscilik_sn"]') as HTMLElement;
    expect(d).toHaveTextContent("Dolum işçilik ₺/sn");
    expect(d).toHaveTextContent("925 → yeni: 1000");
    expect(d).toHaveTextContent("havuz toplamı 925.000 → 1.000.000 TL");
    expect(await within(d).findByText("Senaryo geneli — 3 ürünü etkiler")).toBeInTheDocument();
    const e = diyalog.querySelector('[data-alan="gider.elektrik_sn.niko"]') as HTMLElement;
    expect(within(e).getByText("Yalnız bu hesapta")).toBeInTheDocument();
    await user.type(within(diyalog).getByLabelText("Neden"), "Gider güncellemesi");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    const govde = sonExcel.topluKaydet[0].govde;
    expect(govde.gider_havuzlari).toEqual([{ kod: "dolum_iscilik", toplam_tutar: "1000000" }]);
    expect(govde.override).toEqual({ parametreler: {}, fire: {}, satirlar: {}, gider_oranlari: { "elektrik_sn.niko": "0.002" } });
  });

  it("Hesabı da kaydet kapalıyken override gövdeye girmez", async () => {
    excelKur();
    await tabloHazir();
    const user = userEvent.setup();
    const gider = screen.getByRole("region", { name: "Gider kalemleri" });
    const elektrik = within(gider).getByLabelText("Birim fiyat — Elektrik Giderleri");
    await user.clear(elektrik);
    await user.type(elektrik, "0,002");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    await user.click(within(diyalog).getByLabelText("Hesabı da kaydet"));
    await user.type(within(diyalog).getByLabelText("Neden"), "x");
    await user.click(within(diyalog).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    expect(sonExcel.topluKaydet[0].govde).not.toHaveProperty("override");
  });

  it("elle fiyat satırında diyalog döviz kodunu gösterir", async () => {
    kur({ yanit: dovizli({ "M-001": "USD" }) });
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fiyat = within(tablo).getByLabelText("Birim fiyat (USD) — Pet Şişe 500 ml");
    await user.clear(fiyat);
    await user.type(fiyat, "6");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    const diyalog = await screen.findByRole("dialog");
    const s = diyalog.querySelector('[data-alan="satir.1.birim_fiyat_elle"]') as HTMLElement;
    expect(s).toHaveTextContent("liste fiyatı → yeni: 6 USD");
  });

  it("ürün alanları anında hesaba girer (override.urun); kur hücresi vurgulanır", async () => {
    const istekler = excelKur();
    await tabloHazir();
    const b = screen.getByRole("region", { name: "Üretim bilgileri" });
    const user = userEvent.setup();
    await user.selectOptions(within(b).getByLabelText("Üretim hattı"), "Herbort");
    await user.selectOptions(within(b).getByLabelText("Taze/Turşu sınıfı"), "Turşu/Turşu");
    const suzme = within(b).getByLabelText("Süzme miktar (kg)");
    await user.clear(suzme);
    await user.type(suzme, "0,6");
    await waitFor(() =>
      expect(sonG(istekler).override.urun).toEqual({ hat: "Herbort", taze_tursu_sinifi: "Turşu/Turşu", suzme_kg: "0.6" }),
    );
    expect(within(b).queryByRole("button", { name: /Kalıcı kaydet/ })).not.toBeInTheDocument();
    const usd = within(screen.getByRole("region", { name: "Kurlar ve enflasyon" })).getByLabelText("Kur USD");
    await user.clear(usd);
    await user.type(usd, "52");
    expect(usd).toHaveAttribute("data-degisti", "true");
    expect(usd).toHaveAttribute("title", "Eski değer: 50");
  });
});

describe("UrunMaliyeti — reçetesiz ürün (Faz 5c)", () => {
  /** `GET recete` boş yapı (versiyon 0) döner; reçete POST edilince gerçek reçeteye ve `senaryoda: true`ya geçer. */
  function recetesizIsleyiciler() {
    let kayitli = false;
    const gonderilen: Record<string, unknown>[][] = [];
    const ek: RequestHandler[] = [
      http.get("*/api/v1/urunler/:kod/recete", () =>
        kayitli ? HttpResponse.json(urunReceteleri) : HttpResponse.json({ id: null, versiyon: 0, kaynak: "", satirlar: [] }),
      ),
      http.post("*/api/v1/urunler/:kod/recete", async ({ request }) => {
        gonderilen.push((await request.json()) as Record<string, unknown>[]);
        kayitli = true;
        return HttpResponse.json({ id: 11, versiyon: 1, satir_sayisi: 1 }, { status: 201 });
      }),
      http.get("*/api/v1/urunler/:kod", ({ params }) =>
        HttpResponse.json({
          id: 4,
          kod: params.kod,
          ad: "Yeni Ürün 720 ml",
          ambalaj_hacmi: "720",
          hat: "Hat A",
          taze_tursu_sinifi: "Taze/Turşu",
          suzme_kg: "0.45",
          pazar: "Yurtiçi",
          aktif: true,
          gecici_kod: false,
          senaryoda: kayitli,
          uretim_hedefi: null,
        }),
      ),
    ];
    return { ek, gonderilen };
  }

  it("boş reçetede not, 'çalışmada yok' şeridi ve satır formu görünür; hesap çağrılmaz; kaydedince tabloya ve hesaba döner", async () => {
    const { ek, gonderilen } = recetesizIsleyiciler();
    const istekler = kur({}, ek, `/urunler/${RECETESIZ_KOD}?senaryo=1`);
    expect(await screen.findByText(RECETE_YOK_METNI)).toBeInTheDocument();
    expect(await screen.findByTestId("senaryo-disi-seridi")).toHaveTextContent(SENARYO_DISI_METNI);
    expect(screen.getByRole("heading", { name: "Yeni Ürün 720 ml" })).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Reçete tablosu" })).not.toBeInTheDocument();
    // Ürün kodu sabittir (alan yok); satır ekleme akışı mevcut form.
    expect(screen.queryByLabelText("Ürün kodu")).not.toBeInTheDocument();
    expect(screen.getByRole("form", { name: "Elle reçete girişi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Satır ekle" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Teklif turları" })).not.toBeInTheDocument();
    expect(istekler.hesapla).toHaveLength(0);

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Malzeme kodu 1"), "M-001");
    await user.type(screen.getByLabelText("Ad 1"), "Pet Şişe 500 ml");
    await user.type(screen.getByLabelText("Miktar 1"), "1");
    await user.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    const onay = await screen.findByRole("dialog", { name: "İlk reçete kaydedilecek" });
    await waitFor(() => expect(onay).toHaveTextContent(/ilk reçete versiyonu 1 satırla açılır ve ürün çalışmaya dahil olur/));
    await user.click(within(onay).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(gonderilen).toHaveLength(1));
    expect(gonderilen[0]).toEqual([{ malzeme_kodu: "M-001", ad: "Pet Şişe 500 ml", miktar: "1", dugum_tipi: "yaprak" }]);

    // Reçete oluşunca hesap koşar, tablo gelir, şerit kalkar.
    await tabloHazir();
    await waitFor(() => expect(istekler.hesapla.length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.queryByTestId("senaryo-disi-seridi")).not.toBeInTheDocument());
    expect(screen.queryByText(RECETE_YOK_METNI)).not.toBeInTheDocument();
  });

  it("üye üründe (senaryoda: true) şerit yoktur", async () => {
    kur();
    await tabloHazir();
    expect(screen.queryByTestId("senaryo-disi-seridi")).not.toBeInTheDocument();
  });

  it("hesap 'üretim hedefi yok' derse ekranda üretim bilgileri kartı açılır; kaydedince hesap yeniden koşar ve kart kapanır", async () => {
    let hedefVar = false;
    const urunGovdesi = (kod: string) => ({
      id: 1,
      kod,
      ad: "Salatalık Turşusu 720 ml",
      ambalaj_hacmi: "720",
      hat: "Hat A",
      taze_tursu_sinifi: "Taze/Turşu",
      suzme_kg: "0.45",
      pazar: "Yurtiçi",
      aktif: true,
      gecici_kod: false,
      senaryoda: true,
      uretim_hedefi: hedefVar
        ? {
            id: 4,
            vardiya_uretim_adedi: "12000",
            dolum_personel: "6",
            etiketleme_adedi: "3000",
            etiket_personel: "2",
            mal_kabul_miktar_kg: "0.5",
            mal_kabul_fire: "0.05",
            pazarlama_yonetim_uygula: true,
          }
        : null,
    });
    const hedefGovdeleri: Record<string, unknown>[] = [];
    const istekler = kur(
      {
        hesaplaHatasi: () =>
          hedefVar
            ? null
            : HttpResponse.json(
                { hata: "bulunamadi", mesaj: "üretim hedefi yok", alanlar: { urun: "URUN-001", senaryo_id: 1 }, kod: "hedef_yok" },
                { status: 404 },
              ),
      },
      [
        http.get("*/api/v1/urunler/:kod", ({ params }) => HttpResponse.json(urunGovdesi(String(params.kod)))),
        http.put("*/api/v1/urunler/:kod/uretim-hedefi", async ({ request }) => {
          const g = (await request.json()) as Record<string, unknown>;
          hedefGovdeleri.push(g);
          hedefVar = true;
          return HttpResponse.json({ id: 4, ...g });
        }),
      ],
    );
    const kart = await screen.findByRole("region", { name: HEDEF_YOK_METNI });
    expect(screen.getAllByRole("alert")[0]).toHaveTextContent("üretim hedefi yok");
    // Sabit ürün: seçici yok; dokunulmadan hata satırları gösterilmez.
    expect(within(kart).queryByLabelText("Ürün")).not.toBeInTheDocument();
    expect(within(kart).queryByText(/geçerli bir sayı olmalı/)).not.toBeInTheDocument();
    const user = userEvent.setup();
    const alanlar: [string, string][] = [
      ["Vardiya üretim adedi", "12000"],
      ["Dolum personel", "6"],
      ["Etiketleme adedi", "3000"],
      ["Etiket personel", "2"],
      ["Mal kabul miktarı (kg)", "0,5"],
      ["Mal kabul fire (%)", "5"],
    ];
    for (const [etiket, deger] of alanlar) await user.type(within(kart).getByLabelText(etiket), deger);
    await user.type(within(kart).getByLabelText("Neden"), "İlk üretim bilgisi");
    const onceki = istekler.hesapla.length;
    await user.click(within(kart).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(hedefGovdeleri).toHaveLength(1));
    expect(hedefGovdeleri[0]).toMatchObject({ vardiya_uretim_adedi: "12000", mal_kabul_fire: "0.05", neden: "İlk üretim bilgisi" });
    // Kayıt sonrası hesap kendiliğinden yeniden koşar; sonuç gelince kart kapanır.
    await waitFor(() => expect(istekler.hesapla.length).toBeGreaterThan(onceki));
    await tabloHazir();
    await waitFor(() => expect(screen.queryByRole("region", { name: HEDEF_YOK_METNI })).not.toBeInTheDocument());
  });

  it("hesap 'zorunlu parametre eksik' derse Parametreler bağlantılı not görünür", async () => {
    kur({
      hesaplaHatasi: () =>
        HttpResponse.json(
          { hata: "dogrulama", mesaj: "zorunlu parametre eksik", alanlar: { eksik: ["enflasyon"] }, kod: "parametre_eksik" },
          { status: 422 },
        ),
    });
    const not = await screen.findByRole("note");
    expect(not).toHaveTextContent("Hesap için parametre değerleri gerekli");
    expect(within(not).getByRole("link", { name: "Parametreler" })).toHaveAttribute("href", "/parametreler?senaryo=1");
  });
});

describe("Dalga 2-C: yapışkan değişiklik çubuğu", () => {
  const cubuk = () => screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" });

  it("değişiklik yokken çubuk, Kaydet ve Vazgeç yoktur", async () => {
    kur();
    await tabloHazir();
    expect(cubuk()).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Vazgeç" })).not.toBeInTheDocument();
    expect(screen.queryByText("Değişiklik yok")).not.toBeInTheDocument();
  });

  it("bir hücre değişince '1 satırda değişiklik' ile Kaydet/Vazgeç görünür; Vazgeç çubuğu kaldırır", async () => {
    kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const miktar = within(tablo).getByLabelText(/Miktar — Pet Şişe/);
    await user.clear(miktar);
    await user.type(miktar, "2,5");
    const b = await screen.findByRole("region", { name: "Kaydedilmemiş değişiklikler" });
    expect(b).toHaveAttribute("aria-live", "polite");
    expect(within(b).getByText("1 satırda değişiklik")).toBeInTheDocument();
    expect(within(b).getByRole("button", { name: "Kaydet" })).toBeEnabled();
    const vazgec = within(b).getByRole("button", { name: "Vazgeç" });
    expect(vazgec).toBeEnabled();
    await user.click(vazgec);
    await waitFor(() => expect(cubuk()).not.toBeInTheDocument());
    expect(miktar).toHaveValue("1");
  });

  it("fire ve parametre değişince satır, fire ve alan sayıları ayrı yazılır; Kaydet sonrası çubuk kaybolur", async () => {
    kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(fire);
    await user.type(fire, "5");
    const faiz = screen.getByLabelText("Faiz TL (%)");
    await user.clear(faiz);
    await user.type(faiz, "50");
    await waitFor(() => expect(screen.getByText("1 satırda ve 1 alanda değişiklik · 1 fire")).toBeInTheDocument());
    await kaydetAkisi(user);
    await waitFor(() => expect(sonExcel.topluKaydet).toHaveLength(1));
    await waitFor(() => expect(cubuk()).not.toBeInTheDocument());
    expect(await screen.findByRole("status", { name: "Kayıt durumu" })).toHaveTextContent("Kaydedildi · Hesap #7");
  });

  it("taslak varken sayfadan ayrılma onayı çıkar; Vazgeç kalır, Ayrıl çıkar", async () => {
    kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(fire);
    await user.type(fire, "5");
    await sonYon.navigate("/baska");
    const diyalog = await screen.findByRole("dialog");
    expect(diyalog).toHaveTextContent("Kaydedilmemiş değişiklikler var. Sayfadan ayrılmak istiyor musunuz?");
    await user.click(within(diyalog).getByRole("button", { name: "Vazgeç" }));
    expect(sonYon.state.location.pathname).toBe("/urunler/URUN-001");
    expect(cubuk()).toBeInTheDocument();
    await sonYon.navigate("/baska");
    await user.click(await within(await screen.findByRole("dialog")).findByRole("button", { name: "Ayrıl" }));
    await waitFor(() => expect(screen.getByText("Başka sayfa")).toBeInTheDocument());
  });

  it("taslak varken beforeunload tarayıcı onayı ister, taslak temizlenince istemez", async () => {
    kur();
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(fire);
    await user.type(fire, "5");
    await screen.findByRole("region", { name: "Kaydedilmemiş değişiklikler" });
    const olay = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(olay);
    expect(olay.defaultPrevented).toBe(true);
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(cubuk()).not.toBeInTheDocument());
    const olay2 = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(olay2);
    expect(olay2.defaultPrevented).toBe(false);
  });
});

describe("Düzenleme kilidi: ürün ekranı", () => {
  const acUcu = () =>
    http.post("*/api/v1/duzenleme-kilidi/ac", () =>
      HttpResponse.json({ kayit_id: 1, sayfa: "/urunler/URUN-001", senaryo_id: 1, kullanici: "Test Kullanıcı" }, { status: 201 }),
    );

  it("kilitliyken reçete hücreleri, üretim bilgileri ve stok etkisi devre dışı; kilit açılınca etkin", async () => {
    sessionStorage.removeItem("fiyat-calismasi.duzenleme-acik-bitis");
    kur({ yanit: urunExcelHesapYaniti }, [acUcu()]);
    const tablo = await tabloHazir();
    expect(screen.getByRole("group", { name: "Düzenleme kilidi" })).toHaveTextContent(
      "Düzenleme kilitli. Değişiklik yapmak için kilidi açın.",
    );
    // Reçete hücreleri girdi olarak kalır (taslak görünür) ama hepsi devre dışıdır.
    const miktarlar = () => within(tablo).getAllByLabelText(/^Miktar — /);
    expect(miktarlar().length).toBeGreaterThan(0);
    for (const g of within(tablo).getAllByRole("textbox")) expect(g).toBeDisabled();
    expect(miktarlar()[0]).toHaveAttribute("title", "Düzenleme kilitli");
    expect(await screen.findByLabelText("Üretim hattı")).toBeDisabled();
    expect(screen.getByLabelText("Vardiya üretim adedi")).toBeDisabled();
    expect(screen.getByLabelText("Marka")).toBeDisabled();
    expect(await screen.findByRole("button", { name: /Stokta kalan ekle/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Ürün ailesini düzenle" })).toBeDisabled();
    // Okuma serbest: hesap tarihi ve tablo görünümü kilitlenmez.
    expect(screen.getByLabelText("Hesap tarihi")).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    await userEvent.click(await screen.findByRole("button", { name: "Evet, aç" }));
    await waitFor(() => expect(miktarlar()[0]).toBeEnabled());
    expect(screen.getByLabelText("Üretim hattı")).toBeEnabled();
    expect(screen.getByLabelText("Vardiya üretim adedi")).toBeEnabled();
    expect(screen.getByRole("button", { name: /Stokta kalan ekle/ })).toBeEnabled();
  });

  it("taslak varken kilitlenirse taslak silinmez: hücre değeri ve çubuk kalır, Kaydet 'Düzenleme kilitli' ile pasiftir", async () => {
    kur({}, [acUcu()]);
    const tablo = await tabloHazir();
    const user = userEvent.setup();
    const fire = within(tablo).getByLabelText(/Fire % .*Pet Şişe/);
    await user.clear(fire);
    await user.type(fire, "5");
    expect(await screen.findByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Kilitle" }));
    expect(await screen.findByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument();
    const kaydet = screen.getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled();
    expect(kaydet).toHaveAttribute("title", "Düzenleme kilitli");
    expect(within(tablo).getByLabelText(/Fire % .*Pet Şişe/)).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    await user.click(await screen.findByRole("button", { name: "Evet, aç" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Kaydet" })).toBeEnabled());
    expect(screen.getByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument();
  });
});
