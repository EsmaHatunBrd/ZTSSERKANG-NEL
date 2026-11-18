import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { dogrulamaHatasi } from "@/test/msw/isleyiciler";
import { ayarlarIsleyicileri, yeniKayit, type YazimKaydi } from "@/test/msw/isleyiciler-ayarlar";
import { ayarDegerleri, ayarTanimlari } from "@/test/fikstur/ayarlar";
import { EVET_HAYIR_BIRIMI } from "./ayarlar/ortak";
import { kurSayfa } from "@/test/kur-ayarlar";
import { bugunIso } from "@/yardimcilar/tarih";
import Parametreler from "./Parametreler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let kayit: YazimKaydi;
beforeEach(() => {
  localStorage.clear();
  kayit = yeniKayit();
  sunucu.use(...ayarlarIsleyicileri(kayit));
});

describe("Parametreler", () => {
  it("grupları ve değerleri gösterir; dağıtım çarpanları bu sayfada gösterilmez", async () => {
    kurSayfa(<Parametreler />);
    expect(await screen.findByRole("heading", { name: "Genel" })).toBeInTheDocument();
    for (const g of ["Kurlar", "Faiz", "Stok süresi", "Teklif kâr oranları"]) {
      expect(screen.getByRole("heading", { name: new RegExp(g) })).toBeInTheDocument();
    }
    const satir = screen.getByText("enflasyon").closest("tr") as HTMLElement;
    expect(await within(satir).findByText("25,00 %")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Dağıtım çarpanları/ })).not.toBeInTheDocument();
    expect(screen.queryByText("dagitim_carpani.uretim")).not.toBeInTheDocument();
    expect(screen.queryByText(/Faz/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Değiştir dagitim_carpani.uretim" })).not.toBeInTheDocument();
  });

  it("neden boşsa gönderilmez", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir kur.USD" }));
    await u.click(await screen.findByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Neden zorunlu")).toBeInTheDocument();
    expect(kayit.parametre).toHaveLength(0);
  });

  it("genel kapsamda yeni değer ekler", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir kur.USD" }));
    const d = await screen.findByLabelText(/Yeni değer/);
    await u.clear(d);
    await u.type(d, "52,5");
    await u.type(screen.getByLabelText("Neden"), "Kur güncellemesi");
    expect(screen.getByText(/Özet: USD\/TL kuru 52,5 TL olacak/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0]).toEqual({
      anahtar: "kur.USD",
      govde: { deger: "52.5", gecerlilik_basi: bugunIso(), neden: "Kur güncellemesi", kapsam_tipi: "genel" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("USD/TL kuru değeri kaydedildi.");
  });

  it("ürün kapsamında kapsam_id gönderir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir satis_kar" }));
    await u.click(await screen.findByLabelText("Yalnızca bir ürün için"));
    await u.selectOptions(await screen.findByLabelText("Ürün"), "URUN-001");
    const d = screen.getByLabelText(/Yeni değer/);
    await u.clear(d);
    await u.type(d, "30");
    await u.type(screen.getByLabelText("Neden"), "Özel fiyat");
    await waitFor(() => expect(screen.getByRole("button", { name: "Kaydet" })).toBeEnabled());
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0].govde).toMatchObject({ deger: "0.3", kapsam_tipi: "urun", kapsam_id: 1 });
  });

  it("geçmişte 'Geri al' eski değeri yeni kayıt olarak POST eder", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Geçmiş kur.USD" }));
    const li = (await screen.findByText("Sezon başı")).closest("li") as HTMLElement;
    await u.click(within(li).getByRole("button", { name: /Geri al/ }));
    expect(kayit.parametre).toHaveLength(0);
    await u.click(await screen.findByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0]).toEqual({
      anahtar: "kur.USD",
      govde: {
        deger: "45",
        gecerlilik_basi: bugunIso(),
        neden: "Geri alındı: 01.01.2026 değeri",
        kapsam_tipi: "genel",
        kapsam_id: null,
      },
    });
  });

  it("gerçekleşen senaryoda enflasyon kilitlidir ve açıklanır", async () => {
    kurSayfa(<Parametreler />, 2);
    await screen.findByRole("heading", { name: "Genel" });
    expect(screen.getByText(/Gerçekleşen senaryoda enflasyon kilitlidir/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Değiştir enflasyon" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Değiştir kur.USD" })).toBeInTheDocument();
  });

  it("gerçekleşen senaryoda enflasyon geçmişinde Geri al yoktur, kur.USD'de vardır", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />, 2);
    await u.click(await screen.findByRole("button", { name: "Geçmiş enflasyon" }));
    await screen.findByText("Sezon başı");
    expect(screen.queryByRole("button", { name: /Geri al/ })).not.toBeInTheDocument();
    expect(screen.getByText(/geri alınamaz/)).toBeInTheDocument();
    await u.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByText("Sezon başı")).not.toBeInTheDocument());
    await u.click(screen.getByRole("button", { name: "Geçmiş kur.USD" }));
    await screen.findByText("Sezon başı");
    expect(screen.getAllByRole("button", { name: /Geri al/ }).length).toBeGreaterThan(0);
  });

  it("geri al onay ister; sunucu hatası role=alert ile gösterilir", async () => {
    const u = userEvent.setup();
    sunucu.use(http.post("*/api/v1/parametreler/:anahtar/degerler", () => dogrulamaHatasi()));
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Geçmiş kur.USD" }));
    const li = (await screen.findByText("Sezon başı")).closest("li") as HTMLElement;
    await u.click(within(li).getByRole("button", { name: /Geri al/ }));
    expect(await screen.findByText(/01\.01\.2026 tarihli 45 TL değeri bugünden itibaren geçerli olacak/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Onayla" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/geçersiz/);
  });

  it("negatif parametre değeri (-%5) kabul edilir ve oran olarak POST edilir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir enflasyon" }));
    const d = await screen.findByLabelText(/Yeni değer/);
    await u.clear(d);
    await u.type(d, "-5");
    await u.type(screen.getByLabelText("Neden"), "Deflasyon tahmini");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0].govde).toMatchObject({ deger: "-0.05", kapsam_tipi: "genel" });
  });

  it("stok_ay.TL için -1 reddedilir, POST gitmez; sayı olmayan girdi 'Sayı olmalı' der", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir stok_ay.TL" }));
    const d = await screen.findByLabelText(/Yeni değer/);
    await u.clear(d);
    await u.type(d, "-1");
    await u.type(screen.getByLabelText("Neden"), "Deneme");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText(/negatif olamaz/)).toBeInTheDocument();
    await u.clear(d);
    await u.type(d, "abc");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Sayı olmalı")).toBeInTheDocument();
    expect(kayit.parametre).toHaveLength(0);
  });

  it("açık/kapalı parametre 'Kapalı' görünür; Aç nedenle 1 değerini bugünden genel kapsamda yazar", async () => {
    const tanimlar = [
      ...ayarTanimlari,
      { anahtar: "satis_ortalama_maliyetten", aciklama: "Satış fiyatı ortalama maliyetten", birim: EVET_HAYIR_BIRIMI },
    ];
    sunucu.use(
      http.get("*/api/v1/parametreler/tanimlar", () => HttpResponse.json({ kayitlar: tanimlar, toplam: tanimlar.length })),
      http.get("*/api/v1/parametreler", () => HttpResponse.json({ ...ayarDegerleri, satis_ortalama_maliyetten: "0" })),
    );
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    const anahtar = await screen.findByRole("switch", { name: "Aç/Kapat satis_ortalama_maliyetten" });
    expect(anahtar).toHaveAttribute("aria-checked", "false");
    const satir = screen.getByText("satis_ortalama_maliyetten").closest("tr") as HTMLElement;
    expect(within(satir).getByText("Kapalı")).toBeInTheDocument();
    // Değer girişi değil aç/kapa: "Değiştir" düğmesi yok.
    expect(within(satir).queryByRole("button", { name: /^Değiştir/ })).not.toBeInTheDocument();

    await u.click(anahtar);
    const diyalog = await screen.findByRole("dialog");
    expect(diyalog).toHaveTextContent(/tüm ürünler için Açık olacak/);
    await u.click(within(diyalog).getByRole("button", { name: "Aç" }));
    expect(within(diyalog).getByText("Neden zorunlu")).toBeInTheDocument();
    expect(kayit.parametre).toHaveLength(0);
    await u.type(within(diyalog).getByLabelText("Neden (zorunlu)"), "Stok kararı");
    await u.click(within(diyalog).getByRole("button", { name: "Aç" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0]).toEqual({
      anahtar: "satis_ortalama_maliyetten",
      govde: { deger: "1", gecerlilik_basi: bugunIso(), neden: "Stok kararı", kapsam_tipi: "genel" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Satış fiyatı ortalama maliyetten açıldı.");
  });

  it("oran parametresi yüzde olarak girilir: kutu mevcut değeri yüzde gösterir, 30 yazınca 0.3 gider", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir satis_kar" }));
    const d = await screen.findByLabelText(/Yeni değer \(yüzde/);
    expect(d).toHaveValue("20");
    expect(screen.getByText("%")).toBeInTheDocument();
    await u.clear(d);
    await u.type(d, "30");
    await u.type(screen.getByLabelText("Neden"), "Yeni kâr");
    expect(screen.getByText(/Özet: Satış kâr oranı 30,00 % olacak/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0]).toMatchObject({ anahtar: "satis_kar", govde: { deger: "0.3", kapsam_tipi: "genel" } });
    expect(screen.queryByRole("heading", { name: "Değer olağan dışı görünüyor" })).not.toBeInTheDocument();
  });

  it("%100'ün üstündeki oran 'Yine de kaydet' onayı ister; Vazgeç gönderMEZ, onay 2.5 gönderir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir enflasyon" }));
    const d = await screen.findByLabelText(/Yeni değer/);
    expect(d).toHaveValue("25");
    await u.clear(d);
    await u.type(d, "250");
    await u.type(screen.getByLabelText("Neden"), "Yanlış yazım");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    const onay = await screen.findByRole("dialog", { name: "Değer olağan dışı görünüyor" });
    expect(onay).toHaveTextContent("25,00 % → 250,00 %");
    expect(onay).toHaveTextContent(/%100'ün üstünde/);
    await u.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(kayit.parametre).toHaveLength(0);
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await u.click(
      within(await screen.findByRole("dialog", { name: "Değer olağan dışı görünüyor" })).getByRole("button", { name: "Yine de kaydet" }),
    );
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0]).toMatchObject({ anahtar: "enflasyon", govde: { deger: "2.5" } });
  });

  it("kur önceki değerden %50'den fazla değişirse onay ister", async () => {
    const u = userEvent.setup();
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir kur.USD" }));
    const d = await screen.findByLabelText(/Yeni değer/);
    await u.clear(d);
    await u.type(d, "5");
    await u.type(screen.getByLabelText("Neden"), "Deneme");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    const onay = await screen.findByRole("dialog", { name: "Değer olağan dışı görünüyor" });
    expect(onay).toHaveTextContent("50 TL → 5 TL");
    expect(onay).toHaveTextContent(/%50'den fazla/);
    expect(kayit.parametre).toHaveLength(0);
  });

  it("sunucunun sınır hatası (422) diyalogda gösterilir", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.post("*/api/v1/parametreler/:anahtar/degerler", () =>
        HttpResponse.json({ hata: "dogrulama", mesaj: "USD/TL kuru 0'dan büyük olmalı.", alanlar: {} }, { status: 422 }),
      ),
    );
    kurSayfa(<Parametreler />);
    await u.click(await screen.findByRole("button", { name: "Değiştir kur.USD" }));
    const d = await screen.findByLabelText(/Yeni değer/);
    await u.clear(d);
    await u.type(d, "45");
    await u.type(screen.getByLabelText("Neden"), "Deneme");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("USD/TL kuru 0'dan büyük olmalı.");
  });
});
