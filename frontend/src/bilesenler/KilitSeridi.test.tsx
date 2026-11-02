import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { ayarlarIsleyicileri, yeniKayit } from "@/test/msw/isleyiciler-ayarlar";
import { kurSayfa } from "@/test/kur-ayarlar";
import { senaryolar } from "@/test/fikstur/urunler";
import { rotalar } from "@/yonlendirme";
import Parametreler from "@/sayfalar/Parametreler";
import GiderDagitim from "@/sayfalar/GiderDagitim";
import MalzemeFiyatlari from "@/sayfalar/MalzemeFiyatlari";
import UretimAdetleri from "@/sayfalar/UretimAdetleri";
import ReceteAktar from "@/sayfalar/ReceteAktar";
import { MENU, MENU_GRUPLARI } from "./Kabuk";
import { SenaryoSecici } from "./SenaryoSecici";
import { KILIT_KAPSAM_NOTU, KILIT_METNI } from "./KilitSeridi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const kilitliSenaryolar = senaryolar.map((s) => (s.id === 1 ? { ...s, kilitli: true } : s));

beforeEach(() => {
  localStorage.clear();
  sunucu.use(...ayarlarIsleyicileri(yeniKayit()));
  sunucu.use(
    http.get("*/api/v1/uretim-kapasitesi", () =>
      HttpResponse.json({
        kayitlar: [{ urun_kodu: "URUN-001", urun_ad: "Test", net_kapasite: "1", net_sure: "1", toplam_kapasite: "1", toplam_sure: "1", hedef_uretim: "1", ortalama_isci: "1" }],
        toplam: 1,
      }),
    ),
  );
});

function kilitle() {
  sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: kilitliSenaryolar, toplam: kilitliSenaryolar.length })));
}

describe("Senaryo kilidi: şerit ve pasif yazma düğmeleri", () => {
  it("kilitsiz senaryoda şerit yok, düğmeler açık", async () => {
    kurSayfa(<Parametreler />);
    const dugme = await screen.findByRole("button", { name: "Değiştir kur.USD" });
    expect(dugme).toBeEnabled();
    expect(screen.queryByText(KILIT_METNI)).not.toBeInTheDocument();
  });

  it("Parametreler: sarı şerit ve Değiştir düğmeleri pasif", async () => {
    kilitle();
    kurSayfa(<Parametreler />);
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Değiştir kur.USD" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Değiştir enflasyon" })).toBeDisabled();
    // geçmiş görüntülemek serbest
    expect(screen.getByRole("button", { name: "Geçmiş kur.USD" })).toBeEnabled();
  });

  it("Gider Dağıtım: şerit, havuz ve ambalaj düzenleme pasif", async () => {
    kilitle();
    kurSayfa(<GiderDagitim />);
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Havuzu düzenle/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Ambalaj sınıflarını düzenle" })).toBeDisabled();
  });

  it("Malzeme Fiyatları: şerit, fiyat değiştir ve liste yükle pasif", async () => {
    kilitle();
    kurSayfa(<MalzemeFiyatlari />);
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
    const duzenle = await screen.findAllByRole("button", { name: /^Fiyat değiştir / });
    expect(duzenle.every((d) => (d as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getByRole("button", { name: /Fiyat listesi yükle/ })).toBeDisabled();
  });

  it("Üretim Adetleri: şerit ve Düzenle pasif", async () => {
    kilitle();
    kurSayfa(<UretimAdetleri />);
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Düzenle — URUN-001" })).toBeDisabled();
  });

  it("Veri Aktar: şerit görünür", async () => {
    kilitle();
    kurSayfa(<ReceteAktar />);
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
  });

  it("senaryo seçici kilitli senaryoyu işaretler", async () => {
    kilitle();
    kurSayfa(<SenaryoSecici />);
    expect(await screen.findByRole("option", { name: "#1 · 2026-2027 · Varsayılan · Fiyat çalışması · Kilitli" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "#2 · 2026-2027 · Gerçekleşen · Gerçekleşen" })).toBeInTheDocument();
  });
});

describe("Menü ve rotalar", () => {
  it("Değişiklik Günlüğü Kontrol grubunda, Arşiv Çalışma grubunda; rotalar tanımlı", () => {
    const grup = (ad: string) => MENU_GRUPLARI.find((g) => g.grup === ad)?.ogeler.map((o) => o.etiket);
    expect(grup("Kontrol")).toContain("Değişiklik Günlüğü");
    expect(grup("Çalışma")).toContain("Arşiv");
    expect(MENU.find((m) => m.etiket === "Değişiklik Günlüğü")?.yol).toBe("/gunluk");
    expect(MENU.find((m) => m.etiket === "Arşiv")?.yol).toBe("/arsiv");
    const yollar = rotalar[0].children.map((c) => c.path);
    expect(yollar).toEqual(expect.arrayContaining(["gunluk", "arsiv"]));
  });
});

describe("Senaryo kilidi: kapsam notu", () => {
  it("şerit kapsam cümlesini gösterir", async () => {
    kilitle();
    kurSayfa(<Parametreler />);
    expect(await screen.findByText(KILIT_KAPSAM_NOTU)).toBeInTheDocument();
    expect(KILIT_KAPSAM_NOTU).toBe(
      "Kilit senaryoya bağlı kayıtları korur; ürün/malzeme kartı gibi senaryodan bağımsız veriler değişebilir, kayıtlı hesaplar ve Arşiv etkilenmez.",
    );
  });
});
