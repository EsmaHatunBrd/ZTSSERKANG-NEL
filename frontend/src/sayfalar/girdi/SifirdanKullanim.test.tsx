import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { ayarlarIsleyicileri, yeniKayit } from "@/test/msw/isleyiciler-ayarlar";
import { urunExcelIsleyicileri } from "@/test/msw/isleyiciler-urun-excel";
import { kurSayfa } from "@/test/kur-ayarlar";
import VeriGirisi from "../VeriGirisi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

describe("Sıfırdan kullanım (Veri Girişi)", () => {
  it("boş çalışmada gider havuzu seçicisi 11 sabit havuzu 'tanımlı değil' diye listeler ve boş taslakla diyalog açar", async () => {
    sunucu.use(
      http.get(`${T}/gider-havuzlari`, () => HttpResponse.json({ kayitlar: [], toplam: 0, pay_kontrol: [] })),
      ...ayarlarIsleyicileri(yeniKayit()),
      ...urunExcelIsleyicileri().isleyiciler,
    );
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", { name: "Gider havuzu" });
    const secim = await within(k).findByLabelText("Havuz");
    await waitFor(() => expect(within(secim).getAllByRole("option").length).toBe(12)); // "Seçin…" + 11
    expect(within(secim).getByRole("option", { name: /Pazarlama satış giderleri \(pazarlama\) — tanımlı değil/ })).toBeInTheDocument();
    await userEvent.setup().selectOptions(secim, "dolum_iscilik");
    await userEvent.setup().click(within(k).getByRole("button", { name: "Havuzu düzenle" }));
    expect(await screen.findByRole("dialog", { name: /Havuzu düzenle: dolum_iscilik/ })).toBeInTheDocument();
  });

  it("Yeni malzeme: kart açılır, ilk fiyat bu çalışmaya yazılır; var olan kod ezilmez", async () => {
    const istekler: { kart: unknown[]; fiyat: unknown[] } = { kart: [], fiyat: [] };
    sunucu.use(
      http.get(`${T}/malzemeler`, ({ request }) => {
        const arama = new URL(request.url).searchParams.get("arama");
        const kayitlar = arama === "VAR-1" ? [{ kod: "VAR-1", ad: "Var olan", kart_yok: false }] : [];
        return HttpResponse.json({ kayitlar, toplam: kayitlar.length });
      }),
      http.post(`${T}/malzemeler`, async ({ request }) => {
        istekler.kart.push(await request.json());
        return HttpResponse.json({ kod: "KAV-9", ad: "Kavanoz 720" }, { status: 201 });
      }),
      http.post(`${T}/malzemeler/:kod/fiyatlar`, async ({ request, params }) => {
        istekler.fiyat.push({ kod: params.kod, govde: await request.json() });
        return HttpResponse.json({ id: 1 }, { status: 201 });
      }),
      ...ayarlarIsleyicileri(yeniKayit()),
      ...urunExcelIsleyicileri().isleyiciler,
    );
    const u = userEvent.setup();
    kurSayfa(<VeriGirisi />);
    const k = await screen.findByRole("region", { name: "Yeni malzeme" });
    // Var olan kod: reddedilir, kart POST edilmez.
    await u.type(within(k).getByLabelText("Malzeme kodu"), "VAR-1");
    await u.type(within(k).getByLabelText("Ad"), "Başka ad");
    await u.click(within(k).getByRole("button", { name: "Malzemeyi aç" }));
    expect(await within(k).findByRole("alert")).toHaveTextContent("Bu kod zaten kayıtlı");
    expect(istekler.kart).toHaveLength(0);
    // Yeni kod + ilk fiyat.
    await u.clear(within(k).getByLabelText("Malzeme kodu"));
    await u.type(within(k).getByLabelText("Malzeme kodu"), "KAV-9");
    await u.clear(within(k).getByLabelText("Ad"));
    await u.type(within(k).getByLabelText("Ad"), "Kavanoz 720");
    await u.type(within(k).getByLabelText("İlk fiyat (isteğe bağlı)"), "6,5");
    await u.click(within(k).getByRole("button", { name: "Malzemeyi aç" }));
    expect(await within(k).findByRole("alert")).toHaveTextContent("Fiyat girildiyse neden zorunlu");
    await u.type(within(k).getByLabelText("Neden"), "ilk bütçe");
    await u.click(within(k).getByRole("button", { name: "Malzemeyi aç" }));
    await waitFor(() => expect(istekler.fiyat).toHaveLength(1));
    expect(istekler.kart[0]).toMatchObject({
      kod: "KAV-9",
      ad: "Kavanoz 720",
      tip: "0008-Ambalaj Malzeme",
      birim: "AD",
      para_birimi: "TL",
      zs: "S",
    });
    expect(istekler.fiyat[0]).toMatchObject({ kod: "KAV-9", govde: { fiyat: "6.5", neden: "ilk bütçe", para_birimi: "TL", onay: false } });
    expect(await screen.findByRole("status")).toHaveTextContent("KAV-9 malzeme kartı açıldı ve ilk fiyatı girildi.");
  });
});
