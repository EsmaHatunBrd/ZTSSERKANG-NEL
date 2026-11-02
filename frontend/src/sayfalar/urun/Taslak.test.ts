import { describe, expect, it } from "vitest";
import { urunReceteleri } from "@/test/fikstur/urunMaliyeti";
import { urunExcelHesapYaniti } from "@/test/fikstur/urunExcel";
import {
  degisiklikListesi,
  dusenFireSatirlari,
  giderAnahtari,
  kayitliOverrideListesi,
  sunucuDegerleri,
  taslakBos,
  taslakSayisi,
  taslakYamasi,
  taslaktanKaydetGovdesi,
  taslaktanOverride,
  varsayilanKapsam,
  type Taslak,
  type TaslakYamasi,
} from "./Taslak";

const recete = urunReceteleri.satirlar; // 1 Pet (fire), 2 Salamura (elle brüt 0.38 + elle fiyat 12.4), 3 Kapak
const sunucu = sunucuDegerleri(urunExcelHesapYaniti, recete);
const uygula = (t: Taslak, y: TaslakYamasi) => taslakYamasi(t, y, sunucu);

describe("taslakYamasi / taslakSayisi", () => {
  it("boş taslağın sayısı 0'dır", () => {
    expect(taslakSayisi(taslakBos())).toBe(0);
  });

  it("her alan ayrı sayılır ve sunucu değeriyle aynı olan alan düşer", () => {
    let t = taslakBos();
    t = uygula(t, { satirlar: { 1: { fire: "0.05", miktar: "2" } } });
    t = uygula(t, { parametreler: { "kur.USD": "52" }, urun: { hat: "Herbort" }, hedef: { dolum_personel: "7" } });
    expect(taslakSayisi(t)).toBe(5);
    // sunucudaki değere geri dönmek taslağı düşürür (kur.USD=50, hat=Niko, dolum=6, miktar=1)
    t = uygula(t, { parametreler: { "kur.USD": "50.0" }, urun: { hat: "Niko" }, hedef: { dolum_personel: "6" }, satirlar: { 1: { miktar: "1.00" } } });
    expect(taslak(t)).toEqual({ fire: "0.05" });
    expect(taslakSayisi(t)).toBe(1);
  });

  function taslak(t: Taslak) {
    return t.satirlar[1];
  }

  it("undefined değer taslak girdisini siler; satır boşalınca satır da silinir", () => {
    let t = uygula(taslakBos(), { satirlar: { 1: { fire: "0.05" } }, parametreler: { enflasyon: "0.3" } });
    t = uygula(t, { satirlar: { 1: { fire: undefined } }, parametreler: { enflasyon: undefined } });
    expect(t).toEqual(taslakBos());
  });

  it("elle brüt: null yalnız sunucuda elle değer varsa kalır; aynı elle değer düşer", () => {
    let t = uygula(taslakBos(), { satirlar: { 1: { brut_miktar_elle: null }, 2: { brut_miktar_elle: null } } });
    expect(t.satirlar[1]).toBeUndefined(); // sunucuda elle yok: null değişiklik değil
    expect(t.satirlar[2]).toEqual({ brut_miktar_elle: null });
    t = uygula(t, { satirlar: { 2: { brut_miktar_elle: "0.380" } } });
    expect(t.satirlar[2]).toBeUndefined(); // sunucu 0.38
  });

  it("fire sunucudaki fire_override ile aynıysa düşer", () => {
    const r = recete.map((x) => (x.sira === 1 ? { ...x, fire_override: "0.05" } : x));
    const s = sunucuDegerleri(urunExcelHesapYaniti, r);
    const t = taslakYamasi(taslakBos(), { satirlar: { 1: { fire: "0.050" } } }, s);
    expect(t.satirlar[1]).toBeUndefined();
  });

  it("boolean hedef (pazarlama) sunucuyla karşılaştırılır", () => {
    const ayni = uygula(taslakBos(), { hedef: { pazarlama_yonetim_uygula: true } });
    expect(taslakSayisi(ayni)).toBe(0);
    const fark = uygula(taslakBos(), { hedef: { pazarlama_yonetim_uygula: false } });
    expect(taslakSayisi(fark)).toBe(1);
  });

  it("sunucuDegerleri vardiya saatini parametrelere ekler", () => {
    expect(sunucu.parametreler?.vardiya_saati).toBe("7.5");
  });
});

describe("taslaktanOverride", () => {
  it("boş taslak override üretmez", () => {
    expect(taslaktanOverride(taslakBos(), recete)).toBeUndefined();
  });

  it("satır fire -> fire, elle -> satirlar, hedef -> uretim, ürün -> urun, parametre, gider", () => {
    let t = taslakBos();
    t = uygula(t, {
      satirlar: { 1: { fire: "0.05", miktar: "2" }, 3: { brut_miktar_elle: "1.1", birim_fiyat_elle: "9" }, 2: { birim_fiyat_elle: null } },
      hedef: { dolum_personel: "7", pazarlama_yonetim_uygula: false },
      urun: { hat: "Herbort", suzme_kg: "0.5" },
      parametreler: { "faiz.TL": "0.5" },
      giderOranlari: { "elektrik_sn.herbort": "0.0012" },
    });
    expect(taslaktanOverride(t, recete)).toEqual({
      parametreler: { "faiz.TL": "0.5" },
      fire: { "1": "0.05" },
      satirlar: {
        "1": { miktar: "2", elle_brut_kaldir: false, elle_fiyat_kaldir: false },
        "2": { elle_brut_kaldir: false, elle_fiyat_kaldir: true },
        "3": { brut_miktar_elle: "1.1", birim_fiyat_elle: "9", elle_brut_kaldir: false, elle_fiyat_kaldir: false },
      },
      uretim: { dolum_personel: "7", pazarlama_yonetim_uygula: false },
      urun: { hat: "Herbort", suzme_kg: "0.5" },
      gider_oranlari: { "elektrik_sn.herbort": "0.0012" },
    });
  });

  it("yalnız fire olan satır satirlar'a girmez; elle brüt satırında fire override'a girmez", () => {
    let t = uygula(taslakBos(), { satirlar: { 1: { fire: "0.05" }, 3: { fire: "0.03" } } });
    t = uygula(t, { satirlar: { 3: { brut_miktar_elle: "1.1" } } });
    const o = taslaktanOverride(t, recete)!;
    expect(o.satirlar).toEqual({ "3": { brut_miktar_elle: "1.1", elle_brut_kaldir: false, elle_fiyat_kaldir: false } });
    expect(o.fire).toEqual({ "1": "0.05" });
  });
});

describe("taslaktanKaydetGovdesi", () => {
  const urun = { ad: "Ürün A", ambalaj_hacmi: "720", hat: "Niko", taze_tursu_sinifi: "Taze/Turşu", suzme_kg: "0.45", pazar: "Yurtiçi" };
  const hedef = urunExcelHesapYaniti.uretim!;
  const temel = { senaryoId: 1, neden: "  Fiyat güncellemesi ", hesabiKaydet: true, urun, hedef, recete };

  it("yalnız taslağı olan bölümleri gönderir", () => {
    const t = uygula(taslakBos(), { parametreler: { "kur.USD": "52" } });
    expect(taslaktanKaydetGovdesi(t, temel)).toEqual({
      senaryo_id: 1,
      neden: "Fiyat güncellemesi",
      hesabi_kaydet: true,
      parametreler: [{ anahtar: "kur.USD", deger: "52", kapsam: "genel" }],
    });
  });

  it("ürün ve hedef taslağı tam kayıt olarak birleştirilir; tarih verilirse gider", () => {
    const t = uygula(taslakBos(), { urun: { hat: "Herbort" }, hedef: { dolum_personel: "7" } });
    const g = taslaktanKaydetGovdesi(t, { ...temel, tarih: "2026-10-21", hesabiKaydet: false });
    expect(g.tarih).toBe("2026-10-21");
    expect(g.hesabi_kaydet).toBe(false);
    expect(g.urun).toEqual({ ad: "Ürün A", ambalaj_hacmi: "720", hat: "Herbort", taze_tursu_sinifi: "Taze/Turşu", suzme_kg: "0.45", pazar: "Yurtiçi" });
    expect(g.uretim_hedefi).toMatchObject({ dolum_personel: "7", vardiya_uretim_adedi: "12000", pazarlama_yonetim_uygula: true });
    expect(g.recete).toBeUndefined();
  });

  it("reçete yalnız satır taslağı varsa tam listedir; fire ve elle değerler birleşir", () => {
    const t = uygula(taslakBos(), { satirlar: { 1: { fire: "0.05" }, 3: { miktar: "2", birim_fiyat_elle: "9" } } });
    const g = taslaktanKaydetGovdesi(t, temel);
    expect(g.recete).toHaveLength(3);
    expect(g.recete![0]).toMatchObject({ malzeme_kodu: "M-001", fire_override: "0.05", brut_miktar_elle: null });
    expect(g.recete![1]).toMatchObject({ malzeme_kodu: "M-050", brut_miktar_elle: "0.38", birim_fiyat_elle: "12.4", fire_override: null });
    expect(g.recete![2]).toMatchObject({ malzeme_kodu: "M-77", miktar: "2", birim_fiyat_elle: "9" });
  });

  it("elle brüt satırında fire taslağı gövdeden düşer ve uyarı listesinde görünür", () => {
    let t = uygula(taslakBos(), { satirlar: { 1: { fire: "0.05" } } });
    t = uygula(t, { satirlar: { 1: { brut_miktar_elle: "1.05" } } });
    expect(dusenFireSatirlari(t, recete).map((r) => r.sira)).toEqual([1]);
    const g = taslaktanKaydetGovdesi(t, temel);
    expect(g.recete![0]).toMatchObject({ brut_miktar_elle: "1.05", fire_override: null });
  });

  it("kapsam varsayılanı: faiz/stok/vardiya saati -> urun, kur/enflasyon/sapma -> genel; seçim geçerlidir", () => {
    expect(varsayilanKapsam("faiz.TL")).toBe("urun");
    expect(varsayilanKapsam("stok_ay.USD")).toBe("urun");
    expect(varsayilanKapsam("vardiya_saati")).toBe("urun");
    expect(varsayilanKapsam("kur.USD")).toBe("genel");
    expect(varsayilanKapsam("enflasyon")).toBe("genel");
    expect(varsayilanKapsam("maliyet_sapma")).toBe("genel");
    const t = uygula(taslakBos(), { parametreler: { "kur.USD": "52", "faiz.TL": "0.5", enflasyon: "0.3" } });
    const g = taslaktanKaydetGovdesi(t, { ...temel, kapsamSecimi: { "kur.USD": "urun" } });
    expect(g.parametreler).toEqual([
      { anahtar: "kur.USD", deger: "52", kapsam: "urun" },
      { anahtar: "faiz.TL", deger: "0.5", kapsam: "urun" },
      { anahtar: "enflasyon", deger: "0.3", kapsam: "genel" },
    ]);
  });

  it("ürün kartı yokken ürün taslağı hata verir", () => {
    const t = uygula(taslakBos(), { urun: { hat: "Herbort" } });
    expect(() => taslaktanKaydetGovdesi(t, { ...temel, urun: undefined })).toThrow("Ürün kartı yüklenemedi");
  });
});

describe("degisiklikListesi", () => {
  it("etiket, eski/yeni ve etki doğru; senaryo geneli parametre ayrı işaretlenir", () => {
    const t = uygula(taslakBos(), {
      parametreler: { "kur.USD": "52", "faiz.TL": "0.5" },
      urun: { hat: "Herbort" },
      hedef: { mal_kabul_fire: "0.08" },
      satirlar: { 1: { fire: "0.05" }, 2: { brut_miktar_elle: null } },
    });
    const l = degisiklikListesi(t, sunucu);
    const al = (a: string) => l.find((x) => x.alan === a)!;
    expect(al("urun.hat")).toMatchObject({ etiket: "Üretim hattı", eski: "Niko", yeni: "Herbort", etki: "urun", kalici: true });
    expect(al("hedef.mal_kabul_fire")).toMatchObject({ eski: "5 %", yeni: "8 %" });
    expect(al("satir.1.fire")).toMatchObject({ etiket: "Satır 1 · Pet Şişe 500 ml · fire", yeni: "5 %" });
    expect(al("satir.2.brut_miktar_elle")).toMatchObject({ eski: "0,38", yeni: "fire oranına döner" });
    expect(al("parametre.kur.USD")).toMatchObject({ etiket: "USD kuru", etki: "senaryo", parametre: "kur.USD" });
    expect(al("parametre.faiz.TL")).toMatchObject({ etiket: "Faiz TL (%)", etki: "urun" });
    expect(l).toHaveLength(6);
  });

  it("mal kabul ve elektrik gider oranları kalıcı değildir; diğer gider oranları kalıcıdır", () => {
    const t = uygula(taslakBos(), {
      giderOranlari: { "mal_kabul_gug_kg.Taze": "0.2", "elektrik_sn.Niko": "0.001", dolum_iscilik_sn: "0.5" },
    });
    const l = degisiklikListesi(t, sunucu);
    const al = (a: string) => l.find((x) => x.alan === a)!;
    expect(al("gider.mal_kabul_gug_kg.Taze")).toMatchObject({ kalici: false, not: "kalıcı yazım Gider Dağıtım sayfasından", etki: "urun" });
    expect(al("gider.elektrik_sn.Niko")).toMatchObject({ kalici: false });
    expect(al("gider.dolum_iscilik_sn")).toMatchObject({ kalici: true, etki: "senaryo", eski: "925" });
  });
});

describe("U2: gider anahtarı, havuz yazımı ve override (Ruling 7 ve 8)", () => {
  const temel = {
    senaryoId: 1,
    neden: "x",
    hesabiKaydet: true,
    recete,
    havuzlar: [
      { kod: "dolum_iscilik", toplam_tutar: "925000", baz_miktar: "1000" },
      { kod: "etiket_iscilik", toplam_tutar: "10", baz_miktar: null },
    ],
  };

  it("giderAnahtari: kod -> anahtar; sınıf ve hat casefold edilir; bilinmeyen kod null", () => {
    const u = { taze_tursu_sinifi: "Taze/Turşu", hat: "Niko" };
    expect(giderAnahtari("dolum_iscilik", u)).toBe("dolum_iscilik_sn");
    expect(giderAnahtari("etiket_iscilik", u)).toBe("etiket_iscilik_sn");
    expect(giderAnahtari("endirekt_iscilik", u)).toBe("endirekt_iscilik_sn");
    expect(giderAnahtari("diger_gug", u)).toBe("diger_gug_sn");
    expect(giderAnahtari("mal_kabul_iscilik", u)).toBe("mal_kabul_iscilik_kg.taze/turşu");
    expect(giderAnahtari("mal_kabul_gug", u)).toBe("mal_kabul_gug_kg.taze/turşu");
    expect(giderAnahtari("elektrik", u)).toBe("elektrik_sn.niko");
    expect(giderAnahtari("dogalgaz", u)).toBeNull();
    expect(giderAnahtari("pazarlama", u)).toBeNull();
    expect(giderAnahtari(null, u)).toBeNull();
    expect(giderAnahtari("elektrik", { hat: " " })).toBeNull();
  });

  it("sunucuDegerleri gider oranlarını hesap satırlarından anahtarla çıkarır", () => {
    expect(sunucu.giderOranlari).toEqual({ dolum_iscilik_sn: "925", "elektrik_sn.niko": "1550" });
  });

  it("dört skaler oran havuz toplamı (oran x baz_miktar) olarak gider; mal kabul/elektrik yalnız override'a", () => {
    const t = uygula(taslakBos(), {
      giderOranlari: { dolum_iscilik_sn: "0.0123", "elektrik_sn.niko": "0.002", "mal_kabul_gug_kg.taze/turşu": "0.2" },
    });
    const g = taslaktanKaydetGovdesi(t, temel);
    expect(g.gider_havuzlari).toEqual([{ kod: "dolum_iscilik", toplam_tutar: "12.3" }]);
    expect(g.override).toEqual({
      parametreler: {},
      fire: {},
      satirlar: {},
      gider_oranlari: { "elektrik_sn.niko": "0.002", "mal_kabul_gug_kg.taze/turşu": "0.2" },
    });
  });

  it("hesabi_kaydet=false iken override gönderilmez; yalnız skaler oranda override yoktur", () => {
    const t = uygula(taslakBos(), { giderOranlari: { "elektrik_sn.niko": "0.002" } });
    expect(taslaktanKaydetGovdesi(t, { ...temel, hesabiKaydet: false })).not.toHaveProperty("override");
    const t2 = uygula(taslakBos(), { giderOranlari: { dolum_iscilik_sn: "1000" } });
    const g = taslaktanKaydetGovdesi(t2, temel);
    expect(g).not.toHaveProperty("override");
    expect(g.gider_havuzlari).toEqual([{ kod: "dolum_iscilik", toplam_tutar: "1000000" }]);
  });

  it("havuz bilgisi yoksa veya baz_miktar boşsa hata verir", () => {
    const t = uygula(taslakBos(), { giderOranlari: { etiket_iscilik_sn: "1" } });
    expect(() => taslaktanKaydetGovdesi(t, temel)).toThrow("Gider havuzu bilgisi yüklenemedi");
    expect(() => taslaktanKaydetGovdesi(t, { ...temel, havuzlar: undefined })).toThrow("Gider havuzu bilgisi yüklenemedi");
  });

  it("diyalog satırı: eski -> yeni oran ve havuz toplamı; elle fiyat satırında döviz kodu", () => {
    const t = uygula(taslakBos(), { giderOranlari: { dolum_iscilik_sn: "1000" }, satirlar: { 3: { birim_fiyat_elle: "9" } } });
    const dovizli = { ...sunucu, dovizler: { 3: "USD" } };
    const l = degisiklikListesi(t, dovizli, temel.havuzlar);
    const gider = l.find((x) => x.alan === "gider.dolum_iscilik_sn")!;
    expect(gider).toMatchObject({ etiket: "Dolum işçilik ₺/sn", eski: "925", yeni: "1000", etki: "senaryo", kalici: true });
    expect(gider.ek).toBe("havuz toplamı 925.000 → 1.000.000 TL");
    expect(l.find((x) => x.alan === "satir.3.birim_fiyat_elle")).toMatchObject({ yeni: "9 USD" });
  });

  it("kayitliOverrideListesi: ürün, satır ve gider oranlarını okunur etiketlerle verir", () => {
    const l = kayitliOverrideListesi({
      urun: { hat: "Herbort", suzme_kg: "0.5" },
      satirlar: { "2": { brut_miktar_elle: "0.4", elle_brut_kaldir: false, elle_fiyat_kaldir: true } },
      gider_oranlari: { "elektrik_sn.niko": "0.002" },
    });
    expect(l).toEqual([
      { etiket: "Üretim hattı", deger: "Herbort" },
      { etiket: "Süzme miktar (kg)", deger: "0,5" },
      { etiket: "Satır 2 · elle brüt", deger: "0,4" },
      { etiket: "Satır 2 · elle birim fiyat", deger: "listeye döndü" },
      { etiket: "Elektrik ₺/sn — niko", deger: "0,002" },
    ]);
    expect(kayitliOverrideListesi(null)).toEqual([]);
    expect(kayitliOverrideListesi({ parametreler: { enflasyon: "0.3" } })).toEqual([]);
  });
});

describe("Fix round 1: hat/sınıf değişince yetim gider oranları", () => {
  const gider = {
    dolum_iscilik_sn: "1",
    etiket_iscilik_sn: "1",
    endirekt_iscilik_sn: "1",
    diger_gug_sn: "1",
    "elektrik_sn.niko": "0.002",
    "mal_kabul_iscilik_kg.taze/turşu": "0.1",
    "mal_kabul_gug_kg.taze/turşu": "0.2",
  };
  const doldur = () => uygula(taslakBos(), { giderOranlari: gider });

  it("hat değişince elektrik_sn.<eski hat> düşer, dört _sn anahtarı ve mal kabul kalır", () => {
    const t = uygula(doldur(), { urun: { hat: "Herbort" } });
    expect(Object.keys(t.giderOranlari).sort()).toEqual(
      ["diger_gug_sn", "dolum_iscilik_sn", "endirekt_iscilik_sn", "etiket_iscilik_sn", "mal_kabul_gug_kg.taze/turşu", "mal_kabul_iscilik_kg.taze/turşu"].sort(),
    );
    expect(t.urun.hat).toBe("Herbort");
  });

  it("sınıf değişince mal_kabul_*.<eski sınıf> düşer, elektrik ve _sn anahtarları kalır", () => {
    const t = uygula(doldur(), { urun: { taze_tursu_sinifi: "Turşu/Turşu" } });
    expect(Object.keys(t.giderOranlari).sort()).toEqual(
      ["diger_gug_sn", "dolum_iscilik_sn", "elektrik_sn.niko", "endirekt_iscilik_sn", "etiket_iscilik_sn"].sort(),
    );
  });

  it("hat sunucu değerine döndürülünce taslak hatta bağlı girdiler düşer", () => {
    let t = uygula(taslakBos(), { urun: { hat: "Herbort" } });
    t = uygula(t, { giderOranlari: { "elektrik_sn.herbort": "0.003" } });
    expect(t.giderOranlari).toEqual({ "elektrik_sn.herbort": "0.003" });
    t = uygula(t, { urun: { hat: "Niko" } }); // sunucu hattı
    expect(t.urun.hat).toBeUndefined();
    expect(t.giderOranlari).toEqual({});
  });
});
