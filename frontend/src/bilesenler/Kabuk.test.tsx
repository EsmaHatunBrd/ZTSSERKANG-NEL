import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { GirisKullanicisi, Rol } from "@/api/sorgular/kimlik";
import { TooltipProvider } from "@/bilesenler/ui/tooltip";
import { sunucu } from "@/test/msw/sunucu";
import { OturumSaglayici } from "./GirisKapisi";
import { Kabuk, MENU, MENU_DAR_ANAHTARI, MENU_GRUPLARI, useGorunurGruplar } from "./Kabuk";

describe("Kabuk menüsü", () => {
  it("beş grup: Çalışma, Veri girişi (gir), Kayıtlar (listeler), Kontrol, Yönetim", () => {
    expect(MENU_GRUPLARI.map((g) => g.grup)).toEqual(["Çalışma", "Veri girişi", "Kayıtlar", "Kontrol", "Yönetim"]);
    expect(MENU_GRUPLARI[1].ogeler.map((o) => o.etiket)).toEqual(["Veri Girişi", "Veri Aktar"]);
    expect(MENU_GRUPLARI[2].ogeler.map((o) => o.etiket)).toEqual([
      "Malzeme Fiyatları",
      "Parametreler",
      "Gider Dağıtım",
      "Üretim Adetleri",
      "Satış Geçmişi",
    ]);
  });
  it("Ana Sayfa kökte, Genel Bakış kendi adresinde; kıyas sayfaları tek Kıyasla öğesinde; ürün uyarıları Veri Kontrolü altında", () => {
    expect(MENU_GRUPLARI[0].ogeler.map((o) => o.etiket)).toEqual([
      "Ana Sayfa",
      "Genel Bakış",
      "Yönetim Özeti",
      "Ürün Maliyeti",
      "Teklifler",
      "Analiz",
      "Kıyasla",
    ]);
    expect(MENU.find((m) => m.etiket === "Ana Sayfa")).toMatchObject({ yol: "/", son: true });
    expect(MENU.find((m) => m.etiket === "Genel Bakış")?.yol).toBe("/genel-bakis");
    expect(MENU.find((m) => m.etiket === "Kıyasla")).toMatchObject({ yol: "/butce-gerceklesen", ekYollar: ["/karsilastirma", "/arsiv"] });
    expect(MENU_GRUPLARI[3].ogeler.map((o) => o.etiket)).toEqual(["Veri Kontrolü", "Değişiklik Günlüğü"]);
    expect(MENU.find((m) => m.etiket === "Veri Kontrolü")?.ekYollar).toEqual(["/uyarilar"]);
  });
  it("her öğenin simgesi var; Ana Sayfa dışındaki her öğenin kart açıklaması var", () => {
    expect(MENU.every((m) => !!m.simge)).toBe(true);
    expect(MENU.filter((m) => m.yol !== "/").every((m) => !!m.aciklama)).toBe(true);
    expect(MENU.some((m) => m.etiket === "Satış Geçmişi" && m.yol === "/satis-gecmisi")).toBe(true);
  });
});

describe("Role göre görünen gruplar", () => {
  const kullanici = (rol: Rol): GirisKullanicisi => ({
    id: 1,
    kullanici_adi: "x",
    ad: "X",
    rol,
    rol_ad: rol,
    aktif: true,
    sifre_degismeli: false,
  });
  const gruplar = (girisZorunlu: boolean, rol?: Rol) =>
    renderHook(() => useGorunurGruplar(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <OturumSaglayici deger={{ girisZorunlu, kullanici: rol ? kullanici(rol) : null }}>{children}</OturumSaglayici>
      ),
    }).result.current.map((g) => g.grup);

  it("Yönetim yalnız Genel Direktör'e; Veri girişi izleyiciye gösterilmez; girişsiz kurulumda Yönetim yok", () => {
    expect(gruplar(true, "genel_direktor")).toEqual(["Çalışma", "Veri girişi", "Kayıtlar", "Kontrol", "Yönetim"]);
    expect(gruplar(true, "muhasebe")).toEqual(["Çalışma", "Veri girişi", "Kayıtlar", "Kontrol"]);
    expect(gruplar(true, "satin_alma")).toEqual(["Çalışma", "Veri girişi", "Kayıtlar", "Kontrol"]);
    expect(gruplar(true, "izleyici")).toEqual(["Çalışma", "Kayıtlar", "Kontrol"]);
    expect(gruplar(false)).toEqual(["Çalışma", "Veri girişi", "Kayıtlar", "Kontrol"]);
  });
});

describe("Kabuk düzeni (iş alanı anahtarı kenar menüde, daraltılabilir menü)", () => {
  beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
  afterEach(() => sunucu.resetHandlers());
  afterAll(() => sunucu.close());
  beforeEach(() => localStorage.clear());

  function kur(yol: string) {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[yol]}>
            <Routes>
              <Route element={<Kabuk />}>
                <Route path="/parametreler" element={<div>Parametreler sayfası</div>} />
                <Route path="/smm" element={<div>SMM sayfası</div>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );
  }

  it("iş alanı anahtarı kenar menüde (üst çubukta değil) render edilir; tıklayınca alan değişir", async () => {
    kur("/parametreler?senaryo=1");
    const kenar = await screen.findByRole("complementary");
    const alan = within(kenar).getByRole("navigation", { name: "İş alanı" });
    expect(within(screen.getByRole("banner")).queryByRole("navigation", { name: "İş alanı" })).not.toBeInTheDocument();
    expect(within(alan).getByRole("link", { name: "Fiyat Çalışması" })).toHaveAttribute("aria-current", "page");
    await userEvent.click(within(alan).getByRole("link", { name: "Maliyet Muhasebesi" }));
    expect(await screen.findByText("SMM sayfası")).toBeInTheDocument();
    expect(within(alan).getByRole("link", { name: "Maliyet Muhasebesi" })).toHaveAttribute("aria-current", "page");
  });

  it("Menüyü daralt: aria-expanded değişir, tercih localStorage'a yazılır; öğeler title ile adını taşır", async () => {
    kur("/parametreler?senaryo=1");
    const dugme = await screen.findByRole("button", { name: "Menüyü daralt" });
    expect(dugme).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(dugme);
    const genislet = screen.getByRole("button", { name: "Menüyü genişlet" });
    expect(genislet).toHaveAttribute("aria-expanded", "false");
    expect(localStorage.getItem(MENU_DAR_ANAHTARI)).toBe("1");
    const menu = screen.getByRole("navigation", { name: "Ana menü" });
    expect(within(menu).getByRole("link", { name: "Parametreler" })).toHaveAttribute("title", "Parametreler");
    await userEvent.click(genislet);
    expect(localStorage.getItem(MENU_DAR_ANAHTARI)).toBe("0");
  });

  it("kayıtlı tercih dar ise menü dar açılır", async () => {
    localStorage.setItem(MENU_DAR_ANAHTARI, "1");
    kur("/parametreler?senaryo=1");
    expect(await screen.findByRole("button", { name: "Menüyü genişlet" })).toHaveAttribute("aria-expanded", "false");
  });
});
