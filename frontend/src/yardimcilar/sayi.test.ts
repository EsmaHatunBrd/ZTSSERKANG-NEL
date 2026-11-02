import { describe, expect, it } from "vitest";
import { sayiApi, sayiGecerli } from "./sayi";

describe("sayi ayrıştırıcı", () => {
  it("geçerli ondalık metinleri kabul eder (virgül ve nokta)", () => {
    for (const s of ["0", "12", "12,5", "12.5", " 7 "]) expect(sayiGecerli(s)).toBe(true);
  });

  it("geçersiz girdiyi reddeder: boş, harf, binlik ayırıcı, işaret", () => {
    for (const s of ["", " ", "abc", "1.234,5", "1,2,3", "-1", "+1", "1e3", "."]) expect(sayiGecerli(s)).toBe(false);
  });

  it("negatifIzin ile eksi işaretini kabul eder", () => {
    expect(sayiGecerli("-1,5", true)).toBe(true);
    expect(sayiApi("-1,5", true)).toBe("-1.5");
  });

  it("sayiApi nokta ondalıklı düz metin verir, geçersizde null döner", () => {
    expect(sayiApi("12,50")).toBe("12.5");
    expect(sayiApi("0,0001")).toBe("0.0001");
    expect(sayiApi("abc")).toBeNull();
    expect(sayiApi("")).toBeNull();
    expect(sayiApi("-1")).toBeNull();
  });
});
