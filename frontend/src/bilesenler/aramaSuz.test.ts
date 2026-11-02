import { describe, expect, it } from "vitest";
import { aramaSuz, type AramaOgesi } from "./aramaSuz";

const OGELER: AramaOgesi[] = [
  { tur: "urun", kod: "03.001.000.000.00001", ad: "Örnek Turşu 370 ml" },
  { tur: "urun", kod: "03.002.000.000.00002", ad: "Örnek Turşu 720 ml" },
  { tur: "urun", kod: "05.009.000.000.00009", ad: "Başka Konserve" },
  { tur: "malzeme", kod: "20.11.000.000.0001", ad: "Cam Kavanoz 370 ml" },
  { tur: "malzeme", kod: "30.01.000.000.0001", ad: "İnce Tuz" },
];

describe("aramaSuz", () => {
  it("iki karakterden kısa sorguda boş döner", () => {
    expect(aramaSuz("0", OGELER, 1)).toEqual([]);
  });

  it("kod başlangıcı önce, ad içeriği sonra; ürün yolu senaryoyu taşır", () => {
    const s = aramaSuz("03.0", OGELER, 1);
    expect(s.map((x) => x.kod)).toEqual(["03.001.000.000.00001", "03.002.000.000.00002"]);
    expect(s[0].yol).toBe("/urunler/03.001.000.000.00001?senaryo=1");
  });

  it("Türkçe küçük harfe duyarsız ad araması; malzeme yolu fiyatlar sayfasına arama parametresiyle gider", () => {
    const s = aramaSuz("İNCE", OGELER, 2);
    expect(s).toHaveLength(1);
    expect(s[0]).toMatchObject({ tur: "malzeme", kod: "30.01.000.000.0001", yol: "/fiyatlar?senaryo=2&arama=30.01.000.000.0001" });
  });

  it("'370' hem ürünü hem malzemeyi bulur, türler ayrı sınırlanır", () => {
    const s = aramaSuz("370", OGELER, null, 1);
    expect(s.map((x) => x.tur)).toEqual(["urun", "malzeme"]);
    expect(s[0].yol).toBe("/urunler/03.001.000.000.00001");
  });
});
