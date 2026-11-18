import { describe, expect, it } from "vitest";
import { degerMetni } from "./ParametreDiyalogu";
import { olaganDisiNeden, oranYuzdeye, yuzdeMi, yuzdeOrana } from "./ortak";

describe("degerMetni", () => {
  it("en çok 4 ondalık, Türkçe binlik ayraç; oran yüzde; sayı değilse olduğu gibi", () => {
    expect(degerMetni("63.291139240506325", "TL")).toBe("63,2911 TL");
    expect(degerMetni("0.5660377358490566", "TL")).toBe("0,566 TL");
    expect(degerMetni("50", "TL")).toBe("50 TL");
    expect(degerMetni("7.5", "saat")).toBe("7,5 saat");
    expect(degerMetni("1250000.5", null)).toBe("1.250.000,5");
    expect(degerMetni("0.25", "oran")).toBe("25,00 %");
    expect(degerMetni("abc", null)).toBe("abc");
  });
});

describe("yüzde dönüşümü ve bölen gösterimi", () => {
  it("oran <-> yüzde; bölen yüzde değil", () => {
    expect(oranYuzdeye("0.25")).toBe("25");
    expect(oranYuzdeye("0.075")).toBe("7,5");
    expect(oranYuzdeye("")).toBe("");
    expect(yuzdeOrana("25")).toBe("0.25");
    expect(yuzdeOrana("-5")).toBe("-0.05");
    expect(yuzdeMi("enflasyon", "oran")).toBe(true);
    expect(yuzdeMi("liste_bolen_yurtici", "oran")).toBe(false);
    expect(yuzdeMi("kur.USD", "TL")).toBe(false);
    expect(degerMetni("0.63", "oran", "liste_bolen_yurtici")).toBe("0,63");
    expect(degerMetni("0.63", "oran", "satis_kar")).toBe("63,00 %");
  });

  it("olağan dışı: oran %100'ün üstü, kur %50'den fazla değişim", () => {
    expect(olaganDisiNeden("enflasyon", "oran", "2.5", "0.25")).toMatch(/%100'ün üstünde/);
    expect(olaganDisiNeden("enflasyon", "oran", "1", "0.25")).toBeNull();
    expect(olaganDisiNeden("liste_bolen_yurtici", "oran", "1", "0.63")).toBeNull();
    expect(olaganDisiNeden("kur.USD", "TL", "76", "50")).toMatch(/%50'den fazla/);
    expect(olaganDisiNeden("kur.USD", "TL", "74", "50")).toBeNull();
    expect(olaganDisiNeden("kur.USD", "TL", "74", undefined)).toBeNull();
  });
});
