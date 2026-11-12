import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { HesapSatiri, HesapYaniti, KayitliHesapOzeti } from "@/api/tipler";
import { sunucu } from "@/test/msw/sunucu";
import { hesapYaniti } from "@/test/fikstur/hesapYaniti";
import { BOS_METNI, HesapGecmisi } from "./HesapGecmisi";
import { hesaplariSirala, kiyasla, receteKiyasla } from "./hesapKiyas";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const ozet = (id: number, tarih: string, ek: Partial<KayitliHesapOzeti> = {}): KayitliHesapOzeti => ({
  id,
  hesap_tarihi: tarih,
  olusturan: "Kullanıcı 1",
  maliyet_tl: "38.130789",
  satis_tl: "45.756947",
  ...ek,
});

/** Üç kayıt, sunucudan karışık sırada: en yeni #7 (05.11), sonra #6 ve #4 aynı gün (id büyük önce), en eski #4. */
const KAYITLAR = [
  ozet(4, "2026-10-21", { maliyet_tl: "37", satis_tl: "44" }),
  ozet(7, "2026-11-05", { son_tur_no: 2, son_kar_orani: "0.25", son_durum: "gonderildi" }),
  ozet(6, "2026-10-21"),
];

const satirKod = (s: HesapSatiri, kod: string, tutar?: string): HesapSatiri => ({ ...s, kod, tutar: tutar ?? s.tutar });

/** A (#4): M-001 7.525510, M-050 4.712000, M-099 yalnız A. B (#7): M-001 artmış, M-050 aynı, M-077 yalnız B. */
const GORUNUM_A: HesapYaniti = {
  ...hesapYaniti,
  satirlar: [
    satirKod(hesapYaniti.satirlar[0], "M-001"),
    satirKod(hesapYaniti.satirlar[1], "M-050"),
    satirKod(hesapYaniti.satirlar[1], "M-099", "1.000000"),
    hesapYaniti.satirlar[2],
  ],
};
const GORUNUM_B: HesapYaniti = {
  ...hesapYaniti,
  satirlar: [
    satirKod(hesapYaniti.satirlar[0], "M-001", "8.000000"),
    satirKod(hesapYaniti.satirlar[1], "M-050"),
    satirKod(hesapYaniti.satirlar[1], "M-077", "2.500000"),
    hesapYaniti.satirlar[2],
  ],
  toplamlar: { ...hesapYaniti.toplamlar, maliyet_tl: "40.000000", malzeme: "12.237510" },
  toplamlar_firesiz: null,
  fiyatlar: { ...hesapYaniti.fiyatlar, satis_tl: "48.000000", satis_usd: null },
};

function isleyiciler(kayitlar: KayitliHesapOzeti[] = KAYITLAR) {
  sunucu.use(
    http.get("*/api/v1/urunler/:kod/hesaplar", () => HttpResponse.json({ kayitlar, toplam: kayitlar.length })),
    http.get("*/api/v1/hesaplar/:id", ({ params }) =>
      HttpResponse.json({
        id: Number(params.id),
        urun_id: 1,
        senaryo_id: 1,
        hesap_tarihi: "2026-10-21",
        olusturan: "Kullanıcı 1",
        girdi_snapshot: {},
        sonuc_snapshot: {},
        uyarilar: [],
        gorunum: params.id === "4" ? GORUNUM_A : GORUNUM_B,
      }),
    ),
  );
}

function Konum() {
  const k = useLocation();
  return <p data-testid="konum">{k.pathname + k.search}</p>;
}

function kur(senaryoId: number | null = 1) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/urunler/URUN-001?senaryo=1"]}>
        <Routes>
          <Route path="/urunler/:kod" element={<HesapGecmisi kod="URUN-001" senaryoId={senaryoId} />} />
          <Route path="/hesaplar/:id" element={<Konum />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const bolum = () => screen.getByRole("region", { name: "Geçmiş hesaplar" });
const veriSatirlari = () =>
  within(bolum())
    .getAllByRole("row")
    .filter((r) => r.hasAttribute("data-satir"));
const kutu = (tarih: string, id: number) => screen.getByRole("checkbox", { name: `Kıyas için seç: ${tarih} #${id}` });

describe("HesapGecmisi (liste)", () => {
  it("kayıtlar en yeni üstte sıralanır, bağlantılar senaryo ile hesap sayfasına gider, son tur özeti ve tutarlar biçimlidir", async () => {
    isleyiciler();
    kur();
    await screen.findByRole("link", { name: "#7" });
    const satirlar = veriSatirlari();
    expect(satirlar.map((r) => within(r).getByRole("link").textContent)).toEqual(["#7", "#6", "#4"]);
    expect(within(satirlar[0]).getByRole("link")).toHaveAttribute("href", "/hesaplar/7?senaryo=1");
    expect(satirlar[0]).toHaveTextContent("05.11.2026");
    expect(satirlar[0]).toHaveTextContent("Tur 2 · 25,0 % · Gönderildi");
    expect(satirlar[0]).toHaveTextContent("38,13");
    expect(satirlar[0]).toHaveTextContent("45,76");
    expect(satirlar[2]).toHaveTextContent("—"); // son tur yok
    expect(screen.queryByRole("region", { name: "Hesap kıyası" })).not.toBeInTheDocument();
  });

  it("satıra tıklamak kayıtlı hesabı senaryo ile açar", async () => {
    isleyiciler();
    const u = userEvent.setup();
    kur();
    await screen.findByRole("link", { name: "#4" });
    await u.click(within(veriSatirlari()[2]).getByText("Kullanıcı 1"));
    expect(await screen.findByTestId("konum")).toHaveTextContent("/hesaplar/4?senaryo=1");
  });

  it("kayıt yoksa boş durum metni gösterilir, düğme yoktur", async () => {
    isleyiciler([]);
    kur();
    expect(await screen.findByText(BOS_METNI)).toBeInTheDocument();
    expect(within(bolum()).queryByRole("button", { name: /kaydet|Tümünü göster/i })).not.toBeInTheDocument();
  });

  it("ilk 10 satır gösterilir; Tümünü göster ile hepsi açılır", async () => {
    const cok = Array.from({ length: 12 }, (_, i) => ozet(100 + i, `2026-10-${String(i + 1).padStart(2, "0")}`));
    isleyiciler(cok);
    const u = userEvent.setup();
    kur();
    await screen.findByRole("link", { name: "#111" });
    expect(veriSatirlari()).toHaveLength(10);
    expect(screen.queryByRole("link", { name: "#100" })).not.toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Tümünü göster (12)" }));
    expect(veriSatirlari()).toHaveLength(12);
    expect(screen.getByRole("link", { name: "#100" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tümünü göster/ })).not.toBeInTheDocument();
  });

  it("üçüncü hesap seçilemez; seçim kaldırılınca yeniden seçilebilir", async () => {
    isleyiciler();
    const u = userEvent.setup();
    kur();
    await screen.findByRole("link", { name: "#7" });
    await u.click(kutu("05.11.2026", 7));
    await u.click(kutu("21.10.2026", 6));
    const ucuncu = kutu("21.10.2026", 4);
    expect(ucuncu).toBeDisabled();
    expect(ucuncu).toHaveAttribute("title", expect.stringContaining("En çok iki hesap"));
    await u.click(ucuncu);
    expect(ucuncu).not.toBeChecked();
    await u.click(kutu("21.10.2026", 6));
    expect(ucuncu).toBeEnabled();
  });
});

describe("HesapGecmisi (kıyas paneli)", () => {
  it("iki seçimde üst tablo A eski / B yeni ile farkları, alt tablo yalnız değişen reçete satırlarını gösterir; anahtar hepsini açar", async () => {
    isleyiciler();
    const u = userEvent.setup();
    kur();
    await screen.findByRole("link", { name: "#7" });
    await u.click(kutu("05.11.2026", 7)); // yeni önce seçilse de B olur
    await u.click(kutu("21.10.2026", 4));
    const panel = await screen.findByRole("region", { name: "Hesap kıyası" });
    expect(within(panel).getByRole("heading", { level: 3 })).toHaveTextContent("A 21.10.2026 #4 → B 05.11.2026 #7");
    expect(within(panel).getByRole("link", { name: "Kayıtlı hesabı aç (A #4)" })).toHaveAttribute("href", "/hesaplar/4");
    expect(within(panel).getByRole("link", { name: "Kayıtlı hesabı aç (B #7)" })).toHaveAttribute("href", "/hesaplar/7");
    expect(within(panel).getByRole("link", { name: "Kıyasla modülü" })).toHaveAttribute("href", "/butce-gerceklesen?senaryo=1");

    const ust = await within(panel).findByRole("table", { name: "Kıyas özeti" });
    const satir = (etiket: string) => within(ust).getByText(etiket).closest("tr") as HTMLElement;
    const hucreler = (etiket: string) =>
      within(satir(etiket))
        .getAllByRole("cell")
        .map((c) => c.textContent);
    expect(hucreler("Birim maliyet")).toEqual(["Birim maliyet", "38,13 TL", "40,00 TL", "+1,87 TL", "+4,9 %"]);
    expect(hucreler("Satış fiyatı")).toEqual(["Satış fiyatı", "45,76 TL", "48,00 TL", "+2,24 TL", "+4,9 %"]);
    // Firesiz yalnız A'da: B "—", fark yok.
    expect(hucreler("Firesiz maliyet")).toEqual(["Firesiz maliyet", "36,91 TL", "—", "—", "—"]);
    expect(hucreler("Satış fiyatı (USD)")).toEqual(["Satış fiyatı (USD)", "0,79 USD", "—", "—", "—"]);
    expect(hucreler("Satış fiyatı (EUR)")[4]).toBe("0,0 %");
    expect(within(satir("Birim maliyet")).getAllByRole("cell")[3]).toHaveClass("text-destructive");

    const alt = within(panel).getByRole("table", { name: "Reçete kıyası" });
    const kodlar = () =>
      within(alt)
        .getAllByRole("row")
        .slice(1)
        .map((r) => within(r).getAllByRole("cell")[0].textContent);
    expect(kodlar()).toEqual(["M-001", "M-099", "M-077"]);
    expect(within(alt).getByText("M-001").closest("tr")).toHaveTextContent("+0,47");
    expect(within(alt).getByText("M-099").closest("tr")).toHaveTextContent("yalnız A");
    expect(within(alt).getByText("M-077").closest("tr")).toHaveTextContent("yalnız B");

    await u.click(within(panel).getByRole("switch", { name: "Yalnız değişenleri göster" }));
    expect(kodlar()).toEqual(["M-001", "M-050", "M-099", "M-077"]);
    expect(within(alt).getByText("M-050").closest("tr")).toHaveAttribute("data-durum", "ayni");
  });

  it("hesap yüklenemezse hata gösterilir", async () => {
    isleyiciler();
    sunucu.use(
      http.get("*/api/v1/hesaplar/:id", () => HttpResponse.json({ hata: "bulunamadi", mesaj: "hesap yok", alanlar: {} }, { status: 404 })),
    );
    const u = userEvent.setup();
    kur();
    await screen.findByRole("link", { name: "#7" });
    await u.click(kutu("05.11.2026", 7));
    await u.click(kutu("21.10.2026", 4));
    expect(await screen.findByRole("alert")).toHaveTextContent(/hesap yok|bulunamadı/i);
  });
});

describe("hesapKiyas (saf)", () => {
  it("hesaplariSirala: tarih azalan, eşit tarihte id azalan", () => {
    expect(hesaplariSirala(KAYITLAR).map((h) => h.id)).toEqual([7, 6, 4]);
  });

  it("kiyasla: fark ve yüzde Decimal ile; a sıfırsa yüzde yok; iki taraf da boş satır atlanır", () => {
    const taban = { ...hesapYaniti, toplamlar_firesiz: null, fiyatlar_firesiz: null };
    const a: HesapYaniti = {
      ...taban,
      toplamlar: { ...taban.toplamlar, maliyet_tl: "100", finansman_tl: "0" },
      fiyatlar: { ...taban.fiyatlar, satis_usd: null, satis_eur: null },
    };
    const b: HesapYaniti = {
      ...taban,
      toplamlar: { ...taban.toplamlar, maliyet_tl: "110.5", finansman_tl: "2" },
      fiyatlar: { ...taban.fiyatlar, satis_usd: null, satis_eur: null },
    };
    const s = kiyasla(a, b);
    const bul = (e: string) => s.find((x) => x.etiket === e)!;
    expect(bul("Birim maliyet").fark?.toFixed()).toBe("10.5");
    expect(bul("Birim maliyet").farkYuzde?.toFixed()).toBe("0.105");
    expect(bul("Finansman").fark?.toFixed()).toBe("2");
    expect(bul("Finansman").farkYuzde).toBeNull();
    expect(s.map((x) => x.etiket)).not.toContain("Firesiz maliyet");
    expect(s.map((x) => x.etiket)).not.toContain("Satış fiyatı (USD)");
  });

  it("receteKiyasla: koda göre eşler, kodsuz satırları atlar, yalnız A/B ve değişmeyeni işaretler", () => {
    const s = receteKiyasla(GORUNUM_A.satirlar, GORUNUM_B.satirlar);
    expect(s.map((x) => [x.kod, x.durum])).toEqual([
      ["M-001", "degisti"],
      ["M-050", "ayni"],
      ["M-099", "yalniz_a"],
      ["M-077", "yalniz_b"],
    ]);
    expect(s[0].fark?.toFixed()).toBe("0.47449");
    expect(s[2].b).toBeNull();
    expect(s[3].a).toBeNull();
  });
});
