import { describe, expect, it } from "vitest";
import type { DashboardSatiri } from "@/api/tipler";
import { gecenYilVar, karlilikHaritasi } from "./karlilik";

const satir = (
  kod: string,
  adet: string | null,
  maliyet: string | null,
  satis: string | null,
  hata: string | null = null,
): DashboardSatiri =>
  ({ kod, ad: `Ürün ${kod}`, hat: "Niko", uretim_adedi: adet, maliyet_tl: maliyet, satis_tl: satis, hata }) as unknown as DashboardSatiri;

describe("karlilikHaritasi", () => {
  it("kâr oranı (satış − maliyet) / maliyet; eşik hedef kârdan; dört bölgeye ayırır", () => {
    const v = karlilikHaritasi(
      [
        satir("A", "100000", "100", "125"), // çok satan, %25 → kârlı
        satir("B", "80000", "100", "110"), // çok satan, %10 → marjı zayıf
        satir("C", "1000", "100", "130"), // az satan, %30 → kârlı (niş)
        satir("D", "500", "100", "105"), // az satan, %5 → zayıf
      ],
      "0.2",
    );
    expect(v.karEsigi).toBe(20);
    expect(v.karEsigiKaynagi).toBe("hedef");
    expect(v.adetEsigi).toBe((80000 + 1000) / 2);
    expect(Object.fromEntries(v.noktalar.map((n) => [n.kod, n.bolge]))).toEqual({ A: "guclu", B: "risk", C: "nis", D: "zayif" });
    expect(v.sayilar).toEqual({ guclu: 1, risk: 1, nis: 1, zayif: 1 });
    expect(v.noktalar.find((n) => n.kod === "B")).toMatchObject({
      kar: 10,
      adetMetni: "80.000",
      karMetni: "10,0 %",
      satisMetni: "110,00 TL",
    });
  });

  it("hedef kâr yoksa eşik medyandır; hatalı, satışsız ve adetsiz satırlar dışarıda sayılır", () => {
    const v = karlilikHaritasi(
      [
        satir("A", "100", "100", "150"),
        satir("B", "200", "100", "110"),
        satir("C", "300", "100", "120"),
        satir("H", "10", "100", "120", "reçete yok"),
        satir("S", "10", "100", null),
        satir("Z", "0", "100", "120"),
      ],
      null,
    );
    expect(v.karEsigiKaynagi).toBe("medyan");
    expect(v.karEsigi).toBe(20); // 50, 10, 20 → medyan 20
    expect(v.noktalar).toHaveLength(3);
    expect(v.disarida).toBe(3);
  });

  it("geçen yıl kaynağı gecen_yil_tl ile ölçer; fiyatı olmayan satır dışarıda; düz bayrağı yalnız tüm kârlar aynıysa", () => {
    const satirlar = [
      { ...satir("A", "100000", "100", "120"), gecen_yil_tl: "110" },  // bütçede %20, gerçekte %10
      { ...satir("B", "1000", "100", "120"), gecen_yil_tl: "150" },    // gerçekte %50
      { ...satir("C", "500", "100", "120"), gecen_yil_tl: null },      // geçen yıl yok → dışarıda
    ] as DashboardSatiri[];
    const hesap = karlilikHaritasi(satirlar, "0.2", "hesap");
    expect(hesap.duz).toBe(true);
    expect(hesap.noktalar).toHaveLength(3);
    const gecen = karlilikHaritasi(satirlar, "0.2", "gecen_yil");
    expect(gecen.duz).toBe(false);
    expect(gecen.disarida).toBe(1);
    expect(Object.fromEntries(gecen.noktalar.map((n) => [n.kod, n.bolge]))).toEqual({ A: "risk", B: "nis" });
    expect(gecenYilVar(satirlar)).toBe(true);
    expect(gecenYilVar([satir("X", "1", "1", "2")])).toBe(false);
  });

  it("boş girdi güvenli", () => {
    const v = karlilikHaritasi([], "0.2");
    expect(v.noktalar).toEqual([]);
    expect(v.sayilar).toEqual({ guclu: 0, risk: 0, nis: 0, zayif: 0 });
  });
});
