import { describe, expect, it } from "vitest";
import { MENU, MENU_GRUPLARI } from "./Kabuk";

describe("Kabuk menüsü", () => {
  it("dört grup: Çalışma, Veri girişi (gir), Kayıtlar (listeler), Kontrol", () => {
    expect(MENU_GRUPLARI.map((g) => g.grup)).toEqual(["Çalışma", "Veri girişi", "Kayıtlar", "Kontrol"]);
    expect(MENU_GRUPLARI[1].ogeler.map((o) => o.etiket)).toEqual(["Veri Girişi", "Veri Aktar"]);
    expect(MENU_GRUPLARI[2].ogeler.map((o) => o.etiket)).toEqual([
      "Malzeme Fiyatları",
      "Parametreler",
      "Gider Dağıtım",
      "Üretim Adetleri",
      "Satış Geçmişi",
    ]);
  });
  it("her öğenin simgesi var ve Satış Geçmişi menüde", () => {
    expect(MENU.every((m) => !!m.simge)).toBe(true);
    expect(MENU.some((m) => m.etiket === "Satış Geçmişi" && m.yol === "/satis-gecmisi")).toBe(true);
  });
});
