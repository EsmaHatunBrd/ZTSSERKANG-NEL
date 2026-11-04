import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import type { GirisKullanicisi, Rol } from "@/api/sorgular/kimlik";
import { OturumSaglayici } from "./GirisKapisi";
import { MENU, MENU_GRUPLARI, useGorunurGruplar } from "./Kabuk";

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
    expect(MENU_GRUPLARI[0].ogeler.map((o) => o.etiket)).toEqual(["Ana Sayfa", "Genel Bakış", "Ürün Maliyeti", "Teklifler", "Kıyasla"]);
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
