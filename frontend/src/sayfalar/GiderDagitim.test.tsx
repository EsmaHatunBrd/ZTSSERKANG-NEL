import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { ayarlarIsleyicileri, yeniKayit, type YazimKaydi } from "@/test/msw/isleyiciler-ayarlar";
import { havuzlar } from "@/test/fikstur/urunler";
import { kurSayfa } from "@/test/kur-ayarlar";
import GiderDagitim from "./GiderDagitim";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let kayit: YazimKaydi;
beforeEach(() => {
  localStorage.clear();
  kayit = yeniKayit();
  sunucu.use(...ayarlarIsleyicileri(kayit));
});

describe("GiderDagitim", () => {
  it("havuz kartı Excel düzenindedir: Gider Toplamı · Çalışılan Saniye · B.M. / SN · Gider %", async () => {
    kurSayfa(<GiderDagitim />);
    const kart = (await screen.findByRole("heading", { name: /Üretim Giderleri/ })).closest("section") as HTMLElement;
    expect(within(kart).getAllByText("100.000,00 TL").length).toBeGreaterThan(0);   // havuz toplamı (özet + toplam satırı)
    expect(within(kart).getByRole("columnheader", { name: "Gider Toplamı" })).toBeInTheDocument();
    expect(within(kart).getByRole("columnheader", { name: "Çalışılan Saniye" })).toBeInTheDocument();
    expect(within(kart).getByRole("columnheader", { name: "B.M. / SN" })).toBeInTheDocument();
    expect(within(kart).getByRole("columnheader", { name: "Gider %" })).toBeInTheDocument();
    const dolum = within(kart).getByRole("row", { name: /Dolum/ });
    expect(dolum).toHaveTextContent("30.000,00 TL");          // 100.000 × 0,3 (varsayılan işleyici fikstürü)
    expect(dolum).toHaveTextContent("30.000,000000 TL");      // 30.000 / baz 1
    expect(dolum).toHaveTextContent("30,0 %");
  });

  it("pay toplamı 0,567 kırmızı gösterilir", async () => {
    kurSayfa(<GiderDagitim />);
    const toplam = await screen.findByTestId("pay-toplam-uretim");
    expect(toplam).toHaveTextContent("56,7 %");
    expect(toplam.className).toMatch(/text-red-600/);
  });

  it("pay toplamı %100 ise kırmızı değildir", async () => {
    sunucu.use(
      http.get("*/api/v1/gider-havuzlari", () =>
        HttpResponse.json({ kayitlar: havuzlar, toplam: 1, pay_kontrol: [] }),
      ),
    );
    kurSayfa(<GiderDagitim />);
    const toplam = await screen.findByTestId("pay-toplam-uretim");
    expect(toplam).toHaveTextContent("100,0 %");
    expect(toplam.className).not.toMatch(/text-red-600/);
  });

  it("havuz düzenleme: canlı pay toplamı ve kaydet", async () => {
    const u = userEvent.setup();
    kurSayfa(<GiderDagitim />);
    await u.click(await screen.findByRole("button", { name: "Havuzu düzenle uretim" }));
    const canli = await screen.findByTestId("form-pay-toplam");
    expect(canli).toHaveTextContent("56,7 %");
    expect(canli.className).toMatch(/text-red-600/);
    await u.click(screen.getByRole("radio", { name: "Yüzdeyle" }));   // varsayılan giriş tutarla; bu test yüzde girişini dener
    const pay = screen.getByLabelText("Pay (%) 2");
    await u.clear(pay);
    await u.type(pay, "70");
    expect(canli).toHaveTextContent("100,0 %");
    expect(canli.className).not.toMatch(/text-red-600/);
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Neden zorunlu")).toBeInTheDocument();
    expect(kayit.havuz).toHaveLength(0);
    await u.type(screen.getByLabelText("Neden"), "Aralık bütçesi");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.havuz).toHaveLength(1));
    expect(kayit.havuz[0]).toEqual({
      kod: "uretim",
      govde: {
        ad: "Üretim Giderleri",
        neden: "Aralık bütçesi",
        toplam_tutar: "100000",
        baz_tipi: "saniye",
        baz_miktar: "3600",
        anahtarlar: [
          { alt_kalem: "Dolum", pay_orani: "0.3", baz_miktar: "1" },
          { alt_kalem: "Etiketleme", pay_orani: "0.7", baz_miktar: "1" },
        ],
      },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/Üretim Giderleri kaydedildi/);
  });

  it("M5: pay toplamı %100 değilse kaydetmeden önce onay ister", async () => {
    const u = userEvent.setup();
    kurSayfa(<GiderDagitim />);
    await u.click(await screen.findByRole("button", { name: "Havuzu düzenle uretim" }));
    await screen.findByTestId("form-pay-toplam");
    await u.type(screen.getByLabelText("Neden"), "Deneme");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    const onay = await screen.findByRole("dialog", { name: "Pay toplamı %100 değil" });
    expect(onay).toHaveTextContent("56,7 %");
    expect(kayit.havuz).toHaveLength(0);
    await u.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(kayit.havuz).toHaveLength(0);
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await u.click(within(await screen.findByRole("dialog", { name: "Pay toplamı %100 değil" })).getByRole("button", { name: "Yine de kaydet" }));
    await waitFor(() => expect(kayit.havuz).toHaveLength(1));
  });

  it("ambalaj sınıfları listelenir ve tümü değiştirilerek kaydedilir", async () => {
    const u = userEvent.setup();
    kurSayfa(<GiderDagitim />);
    expect(await screen.findByText("Cam 720")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Ambalaj sınıflarını düzenle" }));
    await u.click(await screen.findByRole("button", { name: "Satır ekle" }));
    await u.type(screen.getByLabelText("Ad 2"), "PET 500");
    await u.type(screen.getByLabelText("Hacim 2"), "500");
    await u.type(screen.getByLabelText("Üretim adedi 2"), "8000");
    await u.type(screen.getByLabelText("Katsayı 2"), "1,1");
    expect(screen.getByText(/2 sınıf kaydedilecek/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Neden zorunlu")).toBeInTheDocument();
    expect(kayit.ambalaj).toHaveLength(0);
    await u.type(screen.getByLabelText("Neden"), "Yeni PET sınıfı");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.ambalaj).toHaveLength(1));
    expect(kayit.ambalaj[0]).toEqual({
      neden: "Yeni PET sınıfı",
      siniflar: [
        { ad: "Cam 720", hacim: "720", uretim_adedi: "12000", katsayi: "1.2" },
        { ad: "PET 500", hacim: "500", uretim_adedi: "8000", katsayi: "1.1" },
      ],
    });
  });

  it("sıfır katsayı reddedilir", async () => {
    const u = userEvent.setup();
    kurSayfa(<GiderDagitim />);
    await screen.findByText("Cam 720");
    await u.click(screen.getByRole("button", { name: "Ambalaj sınıflarını düzenle" }));
    const k = await screen.findByLabelText("Katsayı 1");
    await u.clear(k);
    await u.type(k, "0");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Katsayı sıfırdan büyük olmalı")).toBeInTheDocument();
    expect(kayit.ambalaj).toHaveLength(0);
  });
});
