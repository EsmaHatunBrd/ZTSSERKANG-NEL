import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, onTestFinished } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import type { AktarimOnizleRecete } from "@/api/tipler";
import { ReceteDosyaAktar, seciliSayfalar } from "./ReceteDosyaAktar";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => {
  localStorage.clear();
  localStorage.setItem("fiyat-calismasi.kullanici", "esma");
});

const bos = { eklenen: [], cikan: [], degisen: [], uyarilar: [], elle_fiyat: 0, elle_brut: 0 };
const onizleme: AktarimOnizleRecete = {
  sayfalar: [
    {
      ...bos,
      sayfa: "001",
      kod: "03.001",
      ad: "Biberiye Turşu",
      durum: "degisti",
      satir_sayisi: 21,
      secili: true,
      degisen: [{ kod: "20.10", ad: "Cam Kavanoz", alanlar: ["miktar"] }],
      eklenen: [{ kod: "20.99", ad: "Yeni Etiket", alanlar: [] }],
    },
    {
      ...bos,
      sayfa: "001 (2)",
      kod: "03.001",
      ad: "Biberiye Turşu",
      durum: "degisti",
      satir_sayisi: 21,
      secili: false,
      uyarilar: ["'(2)' ekli sayfa: aynı ürünün alternatif hesabı olabilir"],
    },
    { ...bos, sayfa: "035", kod: "03.035", ad: "Acı Sos", durum: "ayni", satir_sayisi: 31, secili: false },
    { ...bos, sayfa: "070", kod: "03.070", ad: "Yeni Turşu", durum: "yeni_urun", satir_sayisi: 12, secili: true },
  ],
  hatali: [{ sayfa: "Sayfa2", mesaj: "ürün kodu yok (D6 hücresi boş)" }],
};

function kur() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/recete-aktar?senaryo=1"]}>
        <SenaryoSaglayici>
          <ReceteDosyaAktar />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const xlsx = () => new File(["x"], "recete.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

describe("seciliSayfalar", () => {
  it("önerilen seçim üzerine kullanıcı işaretlerini uygular", () => {
    expect(seciliSayfalar(onizleme, {})).toEqual(["001", "070"]);
    expect(seciliSayfalar(onizleme, { "001": false, "001 (2)": true })).toEqual(["001 (2)", "070"]);
  });
});

describe("ReceteDosyaAktar", () => {
  it("önizleme: durum, fark özeti, varyant uyarısı ve okunamayan sayfa; uygula seçilen sayfaları ve nedeni gönderir", async () => {
    const u = userEvent.setup();
    // Form alanları gönderilmeden yakalanır (MSW'de multipart gövde okunamıyor); diziler tekrar eden adla eklenir.
    const giden: [string, string][] = [];
    let uygulandi = 0;
    const asil = FormData.prototype.append;
    FormData.prototype.append = function (this: FormData, ad: string, deger: string | Blob, dosyaAdi?: string) {
      if (typeof deger === "string") giden.push([ad, deger]);
      return dosyaAdi === undefined ? asil.call(this, ad, deger as string) : asil.call(this, ad, deger as Blob, dosyaAdi);
    } as typeof FormData.prototype.append;
    onTestFinished(() => {
      FormData.prototype.append = asil;
    });
    sunucu.use(
      http.post("*/api/v1/aktarim/recete/onizle", () => HttpResponse.json(onizleme)),
      http.post("*/api/v1/aktarim/recete/uygula", () => {
        uygulandi += 1;
        return HttpResponse.json({ uygulanan: [{ sayfa: "001 (2)", kod: "03.001", versiyon: 3 }], yeni_urun: 0 });
      }),
    );
    kur();
    await u.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await u.click(screen.getByRole("button", { name: "Önizle" }));

    const tablo = await screen.findByRole("region", { name: "Ürün sayfaları" });
    expect(within(tablo).getByText(/seçili 2/)).toBeInTheDocument();
    expect(within(tablo).getByText("+1 eklenen · 1 değişen")).toBeInTheDocument();
    expect(within(tablo).getByText("Yeni ürün")).toBeInTheDocument();
    expect(within(tablo).getByText(/alternatif hesabı olabilir/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Okunamayan sayfalar" })).toHaveTextContent("ürün kodu yok");
    expect(screen.getByRole("checkbox", { name: "Uygula: 001 (2) Biberiye Turşu" })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Uygula: 035 Acı Sos" })).not.toBeChecked();

    // Asıl sayfa yerine varyant seçilir, yeni ürün bırakılır.
    await u.click(screen.getByRole("checkbox", { name: "Uygula: 001 Biberiye Turşu" }));
    await u.click(screen.getByRole("checkbox", { name: "Uygula: 001 (2) Biberiye Turşu" }));
    await u.click(screen.getByRole("checkbox", { name: "Uygula: 070 Yeni Turşu" }));
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled(); // neden boş
    await u.type(screen.getByLabelText("Neden"), "hazır alım varyantı");
    await u.click(screen.getByRole("button", { name: "Uygula" }));

    await waitFor(() => expect(uygulandi).toBe(1));
    expect(giden.filter(([k]) => k === "sayfalar").map(([, v]) => v)).toEqual(["001 (2)"]);
    expect(giden).toContainEqual(["neden", "hazır alım varyantı"]);
    expect(giden).toContainEqual(["senaryo", "1"]);
    const ozet = await screen.findByRole("region", { name: "Aktarım özeti" });
    expect(ozet).toHaveTextContent("001 (2): 03.001 → v3");
  });

  it("hiçbir sayfa seçili değilse Uygula kapalıdır", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.post("*/api/v1/aktarim/recete/onizle", () =>
        HttpResponse.json({ ...onizleme, sayfalar: onizleme.sayfalar.map((s) => ({ ...s, secili: false })) }),
      ),
    );
    kur();
    await u.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await u.click(screen.getByRole("button", { name: "Önizle" }));
    await screen.findByRole("region", { name: "Ürün sayfaları" });
    await u.type(screen.getByLabelText("Neden"), "x");
    expect(screen.getByRole("button", { name: "Uygula" })).toBeDisabled();
    expect(screen.getByText("Yazılacak değişiklik yok.")).toBeInTheDocument();
  });
});
