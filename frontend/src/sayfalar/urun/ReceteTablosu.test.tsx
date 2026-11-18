import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { urunExcelHesapYaniti } from "@/test/fikstur/urunExcel";
import { urunReceteleri } from "@/test/fikstur/urunMaliyeti";
import type { HesapSatiri, ReceteSatiri } from "@/api/tipler";
import { formulIpucu } from "./formulMetni";
import { ALT_SATIRLI_SILINEMEZ, ReceteTablosu, URUN_SATIRI_SILINEMEZ, YOGUNLUK_ANAHTARI } from "./ReceteTablosu";
import { sonrakiHucre, type GezinmeSatiri } from "./receteKlavye";

function kur(ek: Partial<Parameters<typeof ReceteTablosu>[0]> = {}) {
  const onTaslak = vi.fn();
  render(
    <ReceteTablosu
      satirlar={urunExcelHesapYaniti.satirlar}
      recete={urunReceteleri.satirlar}
      uyarilar={[]}
      yukleniyor={false}
      hata={null}
      taslak={{}}
      onTaslak={onTaslak}
      urunKodu="URUN-001"
      {...ek}
    />,
  );
  return onTaslak;
}

beforeEach(() => localStorage.clear());
afterEach(() => localStorage.clear());

describe("ReceteTablosu düzeni", () => {
  it("grup başlıkları (Malzeme, Miktar, Fiyat, Tutar, Pay, Kaynak) görünür; sütun başlıkları tam adlarını korur", () => {
    kur();
    const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
    for (const g of ["Malzeme", "Miktar", "Fiyat", "Tutar", "Pay", "Kaynak"]) {
      expect(within(tablo).getAllByText(g, { selector: "th" }).length).toBeGreaterThan(0);
    }
    // Grup satırı erişilebilirlik ağacında sütun başlığı sayılmaz: mevcut testler ilk 14 başlığı sırayla okur.
    const basliklar = within(tablo)
      .getAllByRole("columnheader")
      .map((h) => (h.textContent ?? "").trim());
    expect(basliklar.slice(0, 14)).toEqual([
      "Satır",
      "Kod",
      "Cinsi",
      "Miktar",
      "Fire %",
      "Brüt",
      "Birim",
      "Birim fiyat",
      "Kaynak",
      "Döviz",
      "Tutar (firesiz)",
      "Tutar (fireli)",
      "Maliyet %",
      "Satış %",
    ]);
    expect(within(tablo).getByRole("columnheader", { name: "Tutar (firesiz)" })).toHaveAttribute("title", "Tutar (firesiz)");
  });

  it("Cinsi hücresi tam adı title ile taşır; ara mamul altındaki satırda girinti işareti kalır", () => {
    kur();
    const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
    const hucre = within(tablo).getByText("Salamura Karışımı");
    expect(hucre).toHaveAttribute("title", "Salamura Karışımı");
    expect(hucre.className).toMatch(/truncate/);
    // Ürün kodu farklı bir ara mamul varsa sonraki yaprak satır girintilidir (└ işareti seviye bilgisiyle gelir, girinti veri özniteliğiyle).
    expect(hucre.closest("tr")).toHaveAttribute("data-girinti", "0");
  });

  it("Sıkı / Rahat anahtarı localStorage'a yazar ve tabloyu sıkılaştırır", async () => {
    const u = userEvent.setup();
    kur();
    const grup = screen.getByRole("group", { name: "Tablo yoğunluğu" });
    const siki = within(grup).getByRole("button", { name: "Sıkı" });
    const rahat = within(grup).getByRole("button", { name: "Rahat" });
    expect(rahat).toHaveAttribute("aria-pressed", "true");
    await u.click(siki);
    expect(siki).toHaveAttribute("aria-pressed", "true");
    expect(localStorage.getItem(YOGUNLUK_ANAHTARI)).toBe("siki");
    expect(screen.getByRole("table", { name: "Reçete tablosu" })).toHaveAttribute("data-yogunluk", "siki");
    await u.click(rahat);
    expect(localStorage.getItem(YOGUNLUK_ANAHTARI)).toBe("rahat");
  });

  it("kayıtlı tercih 'siki' ise sıkı açılır", () => {
    localStorage.setItem(YOGUNLUK_ANAHTARI, "siki");
    kur();
    expect(screen.getByRole("button", { name: "Sıkı" })).toHaveAttribute("aria-pressed", "true");
  });

  it("miktar ve fiyat kaynağı rozetleri tek satırda yan yana", () => {
    kur();
    const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
    const satir = within(tablo).getByText("Salamura Karışımı").closest("tr") as HTMLElement;
    const hucreler = within(satir).getAllByRole("cell");
    // Son sütun satır işlemleri (Sil); kaynak rozetleri ondan önceki hücrede.
    const kaynak = hucreler[hucreler.length - 2];
    expect(kaynak.querySelector("[data-kaynaklar]")?.className).toMatch(/flex-row|flex-nowrap/);
  });
});

// ---------------------------------------------------------------------------------------------------------------------
// Dalga 2-A: formül ipucu, ağaç katlama, Excel tarzı klavye gezinme. Uydurma iç içe reçete (şirket verisi içermez).
// ---------------------------------------------------------------------------------------------------------------------

const bosSatir: HesapSatiri = {
  kalem: "",
  grup: "malzeme",
  kod: null,
  sira: null,
  doviz: "TL",
  miktar: null,
  brut_miktar: null,
  birim_fiyat: null,
  tutar: "0",
  tutar_firesiz: "0",
  maliyet_yuzdesi: null,
  fiyat_yuzdesi: null,
  fire_orani: null,
  fire_kaynagi: null,
  miktar_kaynagi: null,
  fiyat_kaynagi: null,
  brut_miktar_elle: null,
  birim_fiyat_elle: null,
  birim: null,
  zs: "S",
};

/** Ürün (0) > Salamura (1) > Tuz, Su (2); Pet Şişe (1). */
const agacSatirlari: HesapSatiri[] = [
  {
    ...bosSatir,
    kalem: "Konserve 400 g",
    kod: "URUN-001",
    sira: 1,
    dugum_tipi: "ara_mamul",
    seviye: 0,
    miktar: "1",
    brut_miktar: "1",
    birim: "adet",
  },
  {
    ...bosSatir,
    kalem: "Salamura Karışımı",
    kod: "ARA-1",
    sira: 2,
    dugum_tipi: "ara_mamul",
    seviye: 1,
    miktar: "0.4",
    brut_miktar: "0.4",
    birim: "kg",
  },
  {
    ...bosSatir,
    kalem: "Tuz",
    kod: "M-010",
    sira: 3,
    dugum_tipi: "yaprak",
    seviye: 2,
    miktar: "0.35",
    brut_miktar: "0.357143",
    birim: "kg",
    birim_fiyat: "12.4",
    fire_orani: "0.02",
    fire_kaynagi: "tip:tuz",
    tutar_firesiz: "4.340000",
    tutar: "4.428571",
    miktar_kaynagi: "fire",
    fiyat_kaynagi: "liste",
    zs: "Z",
  },
  {
    ...bosSatir,
    kalem: "Su",
    kod: "M-011",
    sira: 4,
    dugum_tipi: "yaprak",
    seviye: 2,
    miktar: "1",
    brut_miktar: "1.1",
    birim: "lt",
    birim_fiyat: "0.5",
    fire_orani: "0",
    tutar_firesiz: "0.500000",
    tutar: "0.550000",
    miktar_kaynagi: "elle",
    fiyat_kaynagi: "liste",
    brut_miktar_elle: "1.1",
    zs: "Z",
  },
  {
    ...bosSatir,
    kalem: "Pet Şişe 500 ml",
    kod: "M-001",
    sira: 5,
    dugum_tipi: "yaprak",
    seviye: 1,
    miktar: "1",
    brut_miktar: "1.020408",
    birim: "adet",
    birim_fiyat: "5.9",
    doviz: "EUR",
    fire_orani: "0.02",
    fire_kaynagi: "tip:ambalaj",
    tutar_firesiz: "7.375000",
    tutar: "7.525510",
    miktar_kaynagi: "fire",
    fiyat_kaynagi: "liste",
  },
];

const agacRecetesi: ReceteSatiri[] = agacSatirlari.map((s) => ({
  sira: s.sira as number,
  malzeme_kodu: s.kod as string,
  ad: s.kalem,
  miktar: s.miktar ?? "0",
  birim: s.birim ?? null,
  dugum_tipi: (s.dugum_tipi as "yaprak" | "ara_mamul") ?? "yaprak",
  seviye: s.seviye,
  fire_override: null,
  brut_miktar_elle: s.brut_miktar_elle,
  birim_fiyat_elle: s.birim_fiyat_elle,
  fire_orani: s.fire_orani ?? "0",
  fire_kaynagi: s.fire_kaynagi,
}));

function agacKur(ek: Partial<Parameters<typeof ReceteTablosu>[0]> = {}) {
  const onTaslak = vi.fn();
  render(
    <ReceteTablosu
      satirlar={agacSatirlari}
      recete={agacRecetesi}
      uyarilar={[]}
      yukleniyor={false}
      hata={null}
      taslak={{}}
      onTaslak={onTaslak}
      urunKodu="URUN-001"
      {...ek}
    />,
  );
  const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
  const satir = (ad: string) => within(tablo).getByText(ad).closest("tr") as HTMLElement;
  return { onTaslak, tablo, satir };
}

describe("formulIpucu (saf)", () => {
  it("TL satırında miktar × fiyat = firesiz, brüt × fiyat = fireli, brüt = miktar ÷ (1 − fire)", () => {
    const ip = formulIpucu(agacSatirlari[2]);
    expect(ip.firesiz).toBe("Tutar (firesiz) = miktar × birim fiyat: 0,35 kg × 12,4 TL = 4,34 TL · fiyat: Liste (TL)");
    expect(ip.fireli).toBe("Tutar (fireli) = brüt × birim fiyat: 0,357143 kg × 12,4 TL = 4,43 TL · brüt = 0,35 ÷ (1 − %2 fire)");
    expect(ip.brut).toBe("Brüt = miktar ÷ (1 − fire): 0,35 ÷ (1 − %2) = 0,357143 kg · miktar: Fire kuralı");
  });

  it("döviz satırında çarpım TL tutara eşit değilse '=' yerine '→ … (kur uygulanmış)' yazar; kur uydurmaz", () => {
    const ip = formulIpucu(agacSatirlari[4]);
    expect(ip.firesiz).toBe("Tutar (firesiz) = miktar × birim fiyat: 1 adet × 5,9 EUR → 7,38 TL (kur uygulanmış) · fiyat: Liste (EUR)");
    expect(ip.firesiz).not.toContain("kur:");
  });

  it("elle brüt satırında brüt ipucu 'elle girildi' der; ara mamul ve gider satırında ipucu yok", () => {
    expect(formulIpucu(agacSatirlari[3]).brut).toBe("Brüt elle girildi: 1,1 lt (fire uygulanmaz) · miktar: Elle");
    expect(formulIpucu(agacSatirlari[1])).toEqual({});
    expect(formulIpucu({ ...bosSatir, grup: "gug", kalem: "Elektrik", tutar: "3", tutar_firesiz: "3" })).toEqual({});
  });
});

describe("ReceteTablosu formül ipucu (A1)", () => {
  it("Tutar (firesiz)/(fireli) hücreleri title ipucu taşır; Brüt girdisinin hücresi de", () => {
    const { satir } = agacKur();
    const tuz = satir("Tuz");
    const hucreler = within(tuz).getAllByRole("cell");
    expect(hucreler[5]).toHaveAttribute("title", expect.stringContaining("0,35 ÷ (1 − %2) = 0,357143 kg"));
    expect(within(hucreler[10]).getByTitle(/0,35 kg × 12,4 TL = 4,34 TL/)).toBeInTheDocument();
    expect(within(hucreler[11]).getByTitle(/0,357143 kg × 12,4 TL = 4,43 TL/)).toBeInTheDocument();
    // Ürün satırında formül yok: ipucu da yok.
    expect(satir("Konserve 400 g").querySelector("[data-formul]")).toBeNull();
  });

  it("fare üstüne gelince balon hemen açılır, title kaldırılır; fare çekilince kapanır ve title geri gelir", async () => {
    const u = userEvent.setup();
    const { satir } = agacKur();
    const tetik = within(satir("Tuz")).getAllByTitle(/0,35 kg × 12,4 TL/)[0];
    await u.hover(tetik);
    const ipucu = await screen.findByRole("tooltip");
    expect(ipucu).toHaveTextContent("0,35 kg × 12,4 TL = 4,34 TL");
    expect(tetik).not.toHaveAttribute("title");
    await u.unhover(tetik);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    expect(tetik).toHaveAttribute("title", expect.stringContaining("0,35 kg × 12,4 TL"));
  });

  it("klavyeyle odaklanınca ipucu metni role=tooltip olarak görünür, odak kalkınca kapanır", async () => {
    const u = userEvent.setup();
    const { satir } = agacKur();
    const tetik = within(satir("Tuz")).getAllByTitle(/0,35 kg × 12,4 TL/)[0];
    tetik.focus();
    const ipucu = await screen.findByRole("tooltip");
    expect(ipucu).toHaveTextContent("0,35 kg × 12,4 TL = 4,34 TL");
    expect(tetik).toHaveAttribute("aria-describedby", ipucu.id);
    // Tab: bir sonraki tutar hücresinin ipucu açılır, öncekininki kapanır (tek balon).
    await u.tab();
    expect(screen.getAllByRole("tooltip")).toHaveLength(1);
    expect(screen.getByRole("tooltip")).toHaveTextContent("0,357143 kg × 12,4 TL = 4,43 TL");
    act(() => (document.activeElement as HTMLElement).blur());
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});

describe("ReceteTablosu ağaç katlama (A2)", () => {
  it("ara mamul satırında daralt/genişlet düğmesi; ürün satırında yok; daraltınca alt satırlar gizlenir, toplamlar değişmez", async () => {
    const u = userEvent.setup();
    const { tablo, satir } = agacKur();
    expect(within(satir("Konserve 400 g")).queryByRole("button", { name: /Alt satırları/ })).toBeNull();
    const dugme = within(satir("Salamura Karışımı")).getByRole("button", { name: "Alt satırları gizle" });
    expect(dugme).toHaveAttribute("aria-expanded", "true");
    const toplamOnce = within(tablo).getByRole("row", { name: /Malzeme toplamı \(fireli\)/ }).textContent;

    await u.click(dugme);
    expect(dugme).toHaveAttribute("aria-expanded", "false");
    expect(dugme).toHaveAccessibleName("Alt satırları göster");
    expect(within(tablo).queryByText("Tuz")).toBeNull();
    expect(within(tablo).queryByText("Su")).toBeNull();
    expect(within(tablo).getByText("Pet Şişe 500 ml")).toBeInTheDocument();
    expect(within(tablo).getByRole("row", { name: /Malzeme toplamı \(fireli\)/ }).textContent).toBe(toplamOnce);

    await u.click(dugme);
    expect(dugme).toHaveAttribute("aria-expanded", "true");
    expect(within(tablo).getByText("Tuz")).toBeInTheDocument();
  });
});

describe("sonrakiHucre (saf)", () => {
  const satirlar: GezinmeSatiri[] = [
    { gorunur: true, girdiler: {} }, // ürün satırı: girdi yok
    { gorunur: true, girdiler: { miktar: true, fire: true, brut: true, fiyat: true } },
    { gorunur: false, girdiler: { miktar: true, fire: true, brut: true, fiyat: true } }, // katlanmış
    { gorunur: true, girdiler: { miktar: true, fire: false, brut: true, fiyat: true } }, // fire kapalı (elle brüt)
    { gorunur: true, girdiler: { miktar: true, fire: true, brut: true, fiyat: true } },
  ];
  it("aşağı giderken gizli ve girdisiz satırları atlar; sonda null", () => {
    expect(sonrakiHucre(1, "miktar", 1, satirlar)).toBe(3);
    expect(sonrakiHucre(1, "fire", 1, satirlar)).toBe(4);
    expect(sonrakiHucre(4, "miktar", 1, satirlar)).toBeNull();
  });
  it("yukarı giderken de aynı; başta null", () => {
    expect(sonrakiHucre(3, "miktar", -1, satirlar)).toBe(1);
    expect(sonrakiHucre(4, "fire", -1, satirlar)).toBe(1);
    expect(sonrakiHucre(1, "fiyat", -1, satirlar)).toBeNull();
  });
});

describe("ReceteTablosu klavye gezinme (A3)", () => {
  it("Enter / ok aşağı aynı sütunda bir alt satıra, Shift+Enter / ok yukarı üst satıra gider; kapalı fire atlanır", async () => {
    const u = userEvent.setup();
    const { tablo } = agacKur();
    const tuzMiktar = within(tablo).getByLabelText("Miktar — Tuz");
    tuzMiktar.focus();
    await u.keyboard("{Enter}");
    expect(within(tablo).getByLabelText("Miktar — Su")).toHaveFocus();
    await u.keyboard("{ArrowDown}");
    expect(within(tablo).getByLabelText("Miktar — Pet Şişe 500 ml")).toHaveFocus();
    await u.keyboard("{ArrowUp}");
    expect(within(tablo).getByLabelText("Miktar — Su")).toHaveFocus();
    await u.keyboard("{Shift>}{Enter}{/Shift}");
    expect(tuzMiktar).toHaveFocus();
    // Su satırının fire girdisi elle brüt yüzünden kapalı: Tuz fire'dan Enter Pet Şişe fire'a atlar.
    within(tablo).getByLabelText("Fire % — Tuz").focus();
    await u.keyboard("{Enter}");
    expect(within(tablo).getByLabelText("Fire % — Pet Şişe 500 ml")).toHaveFocus();
  });

  it("katlanmış ara mamulün satırları gezinmede atlanır", async () => {
    const u = userEvent.setup();
    const { tablo, satir } = agacKur();
    await u.click(within(satir("Salamura Karışımı")).getByRole("button", { name: "Alt satırları gizle" }));
    const pet = within(tablo).getByLabelText("Miktar — Pet Şişe 500 ml");
    pet.focus();
    await u.keyboard("{ArrowUp}");
    expect(pet).toHaveFocus();
  });

  it("Escape odaklanmadan önceki taslak değerini geri yazar ve odak hücrede kalır", async () => {
    const u = userEvent.setup();
    const { tablo, onTaslak } = agacKur({ taslak: { 3: { miktar: "0.5" } } });
    const tuz = within(tablo).getByLabelText("Miktar — Tuz");
    await u.click(tuz);
    await u.type(tuz, "9");
    expect(onTaslak).toHaveBeenLastCalledWith({ satirlar: { 3: { miktar: "0.359" } } });
    await u.keyboard("{Escape}");
    expect(onTaslak).toHaveBeenLastCalledWith({ satirlar: { 3: { miktar: "0.5" } } });
    expect(tuz).toHaveFocus();
    // Taslağı olmayan hücrede Escape taslağı siler (undefined).
    const su = within(tablo).getByLabelText("Miktar — Su");
    await u.click(su);
    await u.type(su, "2");
    await u.keyboard("{Escape}");
    expect(onTaslak).toHaveBeenLastCalledWith({ satirlar: { 4: { miktar: undefined } } });
  });
});

describe("ReceteTablosu satır ekle / sil (D3)", () => {
  it("her düzenlenebilir satırda Sil; tıklayınca silinen listesi taslağa yazılır", async () => {
    const u = userEvent.setup();
    const onTaslak = kur({ silinen: [3] });
    const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
    const salamura = within(tablo).getByText("Salamura Karışımı").closest("tr") as HTMLElement;
    await u.click(within(salamura).getByRole("button", { name: "Satırı sil — Salamura Karışımı" }));
    expect(onTaslak).toHaveBeenLastCalledWith({ silinen: [3, 2] });
  });

  it("silinecek satır üstü çizili ve düzenlenmez; satırda ve alttaki listede 'Geri al' silmeyi kaldırır", async () => {
    const u = userEvent.setup();
    const onTaslak = kur({ silinen: [2] });
    const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
    const salamura = within(tablo).getByText("Salamura Karışımı").closest("tr") as HTMLElement;
    expect(salamura).toHaveAttribute("data-taslak", "silinecek");
    expect(within(salamura).queryByLabelText(/Miktar — /)).toBeNull();
    await u.click(within(salamura).getByRole("button", { name: "Silmeyi geri al — Salamura Karışımı" }));
    expect(onTaslak).toHaveBeenLastCalledWith({ silinen: [] });
    const liste = screen.getByRole("region", { name: "Silinecek satırlar" });
    expect(liste).toHaveTextContent("Satır 2");
    expect(liste).toHaveTextContent("M-050");
    await u.click(within(liste).getByRole("button", { name: "Silmeyi geri al — Satır 2" }));
    expect(onTaslak).toHaveBeenLastCalledWith({ silinen: [] });
  });

  it("alt satırı olan ara mamul ve ürün satırı silinemez (pasif, nedeni ipucunda); yaprak alt satır silinebilir", () => {
    const { satir } = agacKur();
    const salamura = within(satir("Salamura Karışımı")).getByRole("button", { name: "Satırı sil — Salamura Karışımı" });
    expect(salamura).toBeDisabled();
    expect(salamura).toHaveAttribute("title", ALT_SATIRLI_SILINEMEZ);
    const urun = within(satir("Konserve 400 g")).getByRole("button", { name: "Satırı sil — Konserve 400 g" });
    expect(urun).toBeDisabled();
    expect(urun).toHaveAttribute("title", URUN_SATIRI_SILINEMEZ);
    expect(within(satir("Tuz")).getByRole("button", { name: "Satırı sil — Tuz" })).toBeEnabled();
  });

  it("canlı hesapta n+1 sıralı satır 'Yeni' rozetiyle çizilir; Kaldır taslaktaki eklenen satırı çıkarır", async () => {
    const u = userEvent.setup();
    const yeni = { malzeme_kodu: "M-900", ad: "Etiket", miktar: "1", birim: "adet" };
    const satirlar: HesapSatiri[] = [
      ...urunExcelHesapYaniti.satirlar.filter((s) => s.grup === "malzeme"),
      { ...bosSatir, kalem: "Etiket", kod: "M-900", sira: 4, miktar: "1", brut_miktar: "1", birim_fiyat: "0.2", tutar: "0.2" },
      ...urunExcelHesapYaniti.satirlar.filter((s) => s.grup !== "malzeme"),
    ];
    const onTaslak = kur({ satirlar, eklenen: [yeni] });
    const tablo = screen.getByRole("table", { name: "Reçete tablosu" });
    const satir = within(tablo).getByText("Etiket").closest("tr") as HTMLElement;
    expect(satir).toHaveAttribute("data-taslak", "eklendi");
    expect(within(satir).getByText("Yeni")).toBeInTheDocument();
    expect(within(satir).queryByLabelText(/Miktar — /)).toBeNull();
    await u.click(within(satir).getByRole("button", { name: "Eklenen satırı kaldır — Etiket" }));
    expect(onTaslak).toHaveBeenLastCalledWith({ eklenen: [] });
  });

  it("kayıtlı hesap görünümünde (salt okunur) işlem sütunu ve Satır ekle yoktur", () => {
    kur({ saltOkunur: true });
    expect(screen.queryByRole("button", { name: /Satırı sil/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Satır ekle" })).toBeNull();
  });
});
