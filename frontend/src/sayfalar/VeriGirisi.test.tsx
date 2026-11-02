import {
  afterAll,
  afterEach,
  beforeAll,
  beforeEach,
  describe,
  expect,
  it,
} from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import {
  ayarlarIsleyicileri,
  yeniKayit,
  type YazimKaydi,
} from "@/test/msw/isleyiciler-ayarlar";
import {
  urunExcelIsleyicileri,
  type UrunExcelIstekleri,
} from "@/test/msw/isleyiciler-urun-excel";
import { senaryolar } from "@/test/fikstur/urunler";
import { kurSayfa } from "@/test/kur-ayarlar";
import { MENU, MENU_GRUPLARI } from "@/bilesenler/Kabuk";
import { rotalar } from "@/yonlendirme";
import { bugunIso } from "@/yardimcilar/tarih";
import VeriGirisi from "./VeriGirisi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let kayit: YazimKaydi;
let istekler: UrunExcelIstekleri;
beforeEach(() => {
  localStorage.clear();
  kayit = yeniKayit();
  const u = urunExcelIsleyicileri();
  istekler = u.istekler;
  sunucu.use(...ayarlarIsleyicileri(kayit), ...u.isleyiciler);
});

const kart = (ad: string) => screen.getByRole("region", { name: ad });

describe("VeriGirisi", () => {
  it("beş giriş kartı çizilir", async () => {
    kurSayfa(<VeriGirisi />);
    expect(
      await screen.findByRole("heading", { name: "Veri Girişi" }),
    ).toBeInTheDocument();
    for (const ad of [
      "Gider havuzu",
      "Malzeme fiyatı",
      "Parametre",
      "Üretim bilgileri (ürün)",
      "Hat kapasitesi (Üretim Adetleri)",
    ]) {
      expect(
        await screen.findByRole("region", { name: ad }),
      ).toBeInTheDocument();
    }
  });

  it("parametre kartı: anahtar seç → değer + tarih + neden → kayıt ve sorgu tazeleme mesajı", async () => {
    const u = userEvent.setup();
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", { name: "Parametre" });
    const secim = await within(k).findByLabelText("Parametre");
    await u.selectOptions(secim, "kur.USD");
    expect(within(k).getByText(/Geçerli değer/)).toHaveTextContent("50 TL");
    await u.click(within(k).getByRole("button", { name: "Değeri değiştir" }));
    const d = await screen.findByRole("dialog", { name: "Değiştir: kur.USD" });
    const deger = within(d).getByLabelText(/Yeni değer/);
    await u.clear(deger);
    await u.type(deger, "55");
    await u.type(within(d).getByLabelText("Neden"), "Kur güncellemesi");
    await u.click(within(d).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.parametre).toHaveLength(1));
    expect(kayit.parametre[0]).toEqual({
      anahtar: "kur.USD",
      govde: {
        deger: "55",
        gecerlilik_basi: bugunIso(),
        neden: "Kur güncellemesi",
        kapsam_tipi: "genel",
      },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "kur.USD değeri kaydedildi.",
    );
    // Salt okunur dağıtım çarpanları seçenek olarak sunulmaz.
    expect(
      within(secim).queryByRole("option", { name: /dagitim_carpani/ }),
    ).not.toBeInTheDocument();
  });

  it("gider havuzu kartı: havuz seç → aynı diyalog açılır, tutarla kaydedilir", async () => {
    const u = userEvent.setup();
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", { name: "Gider havuzu" });
    await u.selectOptions(await within(k).findByLabelText("Havuz"), "uretim");
    expect(within(k).getByText("100.000,00 TL")).toBeInTheDocument();
    await u.click(within(k).getByRole("button", { name: "Havuzu düzenle" }));
    const d = await screen.findByRole("dialog", {
      name: "Havuzu düzenle: uretim",
    });
    const t2 = within(d).getByLabelText("Tutar (TL) 2");
    await u.clear(t2);
    await u.type(t2, "70000");
    await u.type(within(d).getByLabelText("Neden"), "Aralık bütçesi");
    await u.click(within(d).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.havuz).toHaveLength(1));
    expect(kayit.havuz[0].govde).toEqual({
      ad: "Üretim Giderleri",
      neden: "Aralık bütçesi",
      toplam_tutar: "100000",
      baz_tipi: "saniye",
      baz_miktar: "3600",
      anahtarlar: [
        { alt_kalem: "Dolum", pay_orani: "0.3", baz_miktar: "1" },
        { alt_kalem: "Etiketleme", tutar: "70000", baz_miktar: "1" },
      ],
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Üretim Giderleri kaydedildi.",
    );
  });

  it("malzeme fiyatı kartı: kod ara → yeni fiyat + tarih + neden", async () => {
    const u = userEvent.setup();
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", { name: "Malzeme fiyatı" });
    await u.type(within(k).getByLabelText("Malzeme ara"), "M-00");
    expect(
      await within(k).findByRole("button", { name: "Fiyat gir M-001" }),
    ).toBeInTheDocument();
    expect(within(k).queryByText("M-099")).not.toBeInTheDocument(); // kartı olmayan malzeme listelenmez
    await u.click(within(k).getByRole("button", { name: "Fiyat gir M-001" }));
    const d = await screen.findByRole("dialog", {
      name: "Fiyat değiştir: M-001",
    });
    const f = within(d).getByLabelText("Yeni fiyat");
    await u.clear(f);
    await u.type(f, "6,25");
    await u.type(within(d).getByLabelText("Neden"), "Tedarikçi zammı");
    await u.click(within(d).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.fiyat).toHaveLength(1));
    expect(kayit.fiyat[0]).toEqual({
      kod: "M-001",
      senaryo: "1",
      govde: {
        fiyat: "6.25",
        gecerlilik_basi: bugunIso(),
        neden: "Tedarikçi zammı",
        para_birimi: "TL",
      },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "M-001 fiyatı kaydedildi.",
    );
  });

  it("üretim bilgileri kartı: ürün seç → sunucu değerleri dolu → vardiya üretim adedi + neden → PUT uretim-hedefi", async () => {
    const u = userEvent.setup();
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", {
      name: "Üretim bilgileri (ürün)",
    });
    await u.selectOptions(await within(k).findByLabelText("Ürün"), "URUN-001");
    const vardiya = await within(k).findByLabelText("Vardiya üretim adedi");
    await waitFor(() => expect(vardiya).toHaveValue("12000"));
    expect(within(k).getByLabelText("Mal kabul fire (%)")).toHaveValue("5"); // API 0.05 → yüzde
    await u.clear(vardiya);
    await u.type(vardiya, "13000");
    const kaydet = within(k).getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled();
    await u.type(within(k).getByLabelText("Neden"), "Hat planı");
    await u.click(kaydet);
    await waitFor(() => expect(istekler.hedefKaydet).toHaveLength(1));
    expect(istekler.hedefKaydet[0]).toMatchObject({
      kod: "URUN-001",
      senaryo: "1",
    });
    expect(istekler.hedefKaydet[0].govde).toEqual({
      vardiya_uretim_adedi: "13000",
      dolum_personel: "6",
      etiketleme_adedi: "3000",
      etiket_personel: "2",
      mal_kabul_miktar_kg: "0.5",
      mal_kabul_fire: "0.05",
      pazarlama_yonetim_uygula: true,
      neden: "Hat planı",
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "URUN-001 için üretim bilgileri kaydedildi.",
    );
  });

  it("hat kapasitesi kartı: kayıt seç → mevcut form → kayıt", async () => {
    const u = userEvent.setup();
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", {
      name: "Hat kapasitesi (Üretim Adetleri)",
    });
    await u.selectOptions(await within(k).findByLabelText("Kayıt"), "URUN-001");
    const hedef = within(k).getByLabelText("Hedef üretim");
    expect(hedef).toHaveValue("11000");
    await u.clear(hedef);
    await u.type(hedef, "11500");
    const kaydet = within(k).getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled();
    await u.type(within(k).getByLabelText("Neden"), "Sezon planı");
    await u.click(kaydet);
    await waitFor(() => expect(istekler.kapasiteKaydet).toHaveLength(1));
    expect(istekler.kapasiteKaydet[0].govde).toMatchObject({
      hedef_uretim: "11500",
      neden: "Sezon planı",
    });
    expect(await screen.findByRole("status")).toHaveTextContent(
      "URUN-001 için üretim adetleri kaydedildi.",
    );
  });

  it("kilitli senaryoda şerit görünür ve girişler pasiftir", async () => {
    const kilitli = senaryolar.map((s) =>
      s.id === 1 ? { ...s, kilitli: true } : s,
    );
    sunucu.use(
      http.get("*/api/v1/senaryolar", () =>
        HttpResponse.json({ kayitlar: kilitli, toplam: kilitli.length }),
      ),
    );
    kurSayfa(<VeriGirisi />);
    expect(await screen.findByTestId("kilit-seridi")).toBeInTheDocument();
    await screen.findByRole("region", { name: "Gider havuzu" });
    await waitFor(() =>
      expect(
        within(kart("Gider havuzu")).getByRole("button", {
          name: "Havuzu düzenle",
        }),
      ).toBeDisabled(),
    );
    expect(
      within(kart("Parametre")).getByRole("button", {
        name: "Değeri değiştir",
      }),
    ).toBeDisabled();
    expect(
      within(kart("Malzeme fiyatı")).getByLabelText("Malzeme ara"),
    ).toBeDisabled();
    expect(
      within(kart("Üretim bilgileri (ürün)")).getByLabelText("Ürün"),
    ).toBeDisabled();
    expect(
      within(kart("Hat kapasitesi (Üretim Adetleri)")).getByLabelText("Kayıt"),
    ).toBeDisabled();
  });

  it("menüde VERİ grubunun başında ve rota ağacında /veri-girisi vardır", () => {
    const veri = MENU_GRUPLARI.find((g) => g.grup === "Veri girişi");
    expect(veri?.ogeler[0]).toMatchObject({
      yol: "/veri-girisi",
      etiket: "Veri Girişi",
    });
    expect(MENU.find((m) => m.etiket === "Veri Girişi")?.yol).toBe(
      "/veri-girisi",
    );
    expect(
      rotalar[0].children.some((c) => "path" in c && c.path === "veri-girisi"),
    ).toBe(true);
  });
});

describe("VeriGirisi — Yeni ürün kartı (Faz 5c)", () => {
  const urunKarti = async () => screen.findByRole("region", { name: "Yeni ürün" });

  it("kod tekil değilse hata; yoksa PUT gövdesi (gecici_kod dahil), 'Reçeteyi kur' bağlantısı ve form sıfırlanır", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.get("*/api/v1/urunler/:kod", ({ params }) =>
        params.kod === "YENI-01"
          ? HttpResponse.json({ hata: "bulunamadi", mesaj: "ürün yok", alanlar: {} }, { status: 404 })
          : HttpResponse.json({
              id: 1,
              kod: params.kod,
              ad: "Salatalık Turşusu 720 ml",
              ambalaj_hacmi: "720",
              hat: "Hat A",
              taze_tursu_sinifi: "Taze/Turşu",
              suzme_kg: "0.45",
              pazar: "Yurtiçi",
              aktif: true,
              gecici_kod: false,
            }),
      ),
    );
    kurSayfa(<VeriGirisi />);
    const k = await urunKarti();
    await u.type(within(k).getByLabelText("Ürün kodu"), "URUN-001");
    await u.type(within(k).getByLabelText("Ürün adı"), "Kornişon 720 ml");
    await u.type(within(k).getByLabelText("Ambalaj hacmi (ml)"), "720");
    await u.type(within(k).getByLabelText("Süzme miktar (kg)"), "0,45");
    await u.type(within(k).getByLabelText("Hat"), "Hat A");
    expect(within(k).getByText(/Özet: "URUN-001" kodlu "Kornişon 720 ml" kartı açılacak/)).toBeInTheDocument();
    await u.click(within(k).getByRole("button", { name: "Ürünü kaydet" }));
    expect(await within(k).findByRole("alert")).toHaveTextContent("Bu kod zaten kayıtlı: Salatalık Turşusu 720 ml");
    expect(istekler.urunKaydet).toHaveLength(0);

    const kod = within(k).getByLabelText("Ürün kodu");
    await u.clear(kod);
    await u.type(kod, "YENI-01");
    await u.click(within(k).getByRole("button", { name: "Ürünü kaydet" }));
    await waitFor(() => expect(istekler.urunKaydet).toHaveLength(1));
    expect(istekler.urunKaydet[0]).toEqual({
      kod: "YENI-01",
      govde: {
        ad: "Kornişon 720 ml",
        ambalaj_hacmi: "720",
        hat: "Hat A",
        taze_tursu_sinifi: "Taze/Turşu",
        suzme_kg: "0.45",
        pazar: "Yurtiçi",
      },
    });
    const durum = await within(k).findByRole("status");
    expect(durum).toHaveTextContent("YENI-01 · Kornişon 720 ml kaydedildi.");
    expect(within(durum).getByRole("link", { name: "Reçeteyi kur" })).toHaveAttribute("href", "/urunler/YENI-01?senaryo=1");
    expect(within(k).getByLabelText("Ürün kodu")).toHaveValue("");
    expect(screen.getByText(/YENI-01 ürün kartı açıldı; reçetesi kaydedilince çalışmaya dahil olur/)).toBeInTheDocument();
  });

  it("zorunlu alanlar boşken Türkçe hatalar görünür, istek gitmez; hat önerileri hat havuzlarından gelir", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.get("*/api/v1/gider-havuzlari", () =>
        HttpResponse.json({
          kayitlar: [
            {
              kod: "elektrik",
              ad: "Elektrik",
              toplam_tutar: "1000",
              baz_tipi: "saniye",
              baz_miktar: "1",
              taban_tutar: null,
              carpanlar: [],
              anahtarlar: [
                { alt_kalem: "Hat A", pay_orani: "0.5", baz_miktar: "1" },
                { alt_kalem: "Hat B", pay_orani: "0.5", baz_miktar: "1" },
              ],
            },
          ],
          toplam: 1,
          pay_kontrol: [],
        }),
      ),
    );
    kurSayfa(<VeriGirisi />);
    const k = await urunKarti();
    await waitFor(() => expect(k.querySelectorAll("datalist option")).toHaveLength(2));
    expect(k.querySelector("datalist option[value='Hat B']")).not.toBeNull();
    await u.click(within(k).getByRole("button", { name: "Ürünü kaydet" }));
    const hatalar = await within(k).findAllByRole("alert");
    expect(hatalar.map((h) => h.textContent)).toEqual(
      expect.arrayContaining(["Ürün kodu zorunlu", "Ürün adı zorunlu", "Ambalaj hacmi zorunlu", "Süzme kg zorunlu", "Hat zorunlu"]),
    );
    expect(istekler.urunKaydet).toHaveLength(0);
  });
});
