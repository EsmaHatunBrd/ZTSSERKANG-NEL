import { describe, expect, it } from "vitest";
import { degerMetni } from "./ParametreDiyalogu";

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
