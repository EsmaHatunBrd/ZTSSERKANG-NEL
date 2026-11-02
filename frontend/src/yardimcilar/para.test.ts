import { describe, expect, it } from "vitest";
import { D, paraBicimle, topla, yuzdeBicimle, apiMetni } from "./para";
describe("para", () => {
  it("string ondalığı kaybetmez", () => { expect(topla(["0.1", "0.2"]).toString()).toBe("0.3"); });
  it("tr-TR biçimler", () => { expect(paraBicimle("38.130789", "TL")).toBe("38,13 TL"); expect(paraBicimle("1234567.891", "USD", 3)).toBe("1.234.567,891 USD"); });
  it("virgüllü girişi okur", () => { expect(D("1.234,56").toString()).toBe("1234.56"); expect(apiMetni(D("1.234,56"))).toBe("1234.56"); });
  it("yüzde", () => { expect(yuzdeBicimle("0.19736")).toBe("19,7 %"); });
  it("boş değer sıfır", () => { expect(D(null).toString()).toBe("0"); });
});
