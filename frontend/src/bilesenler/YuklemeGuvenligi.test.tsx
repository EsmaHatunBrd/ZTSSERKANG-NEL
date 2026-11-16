import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { sunucu } from "@/test/msw/sunucu";
import { bosOzet, giderOnizle } from "@/test/msw/isleyiciler-aktarim";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { SablonIndir } from "@/bilesenler/SablonIndir";
import { SonYuklemeSeridi } from "@/bilesenler/SonYuklemeSeridi";
import { YuklemeOzetiKutusu } from "@/bilesenler/YuklemeOzetiKutusu";
import { GiderDagitimAktar } from "@/sayfalar/aktar/GiderDagitimAktar";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => {
  localStorage.clear();
});

function sar(icerik: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/recete-aktar?senaryo=1"]}>
        <SenaryoSaglayici>{icerik}</SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const xlsx = () => new File(["x"], "gider.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

describe("SablonIndir", () => {
  it("şablon kimliğinden indirme bağlantısı", () => {
    render(<SablonIndir kimlik="gider_dagitim" />);
    expect(screen.getByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/sablonlar/gider_dagitim.xlsx");
  });
});

describe("YuklemeOzetiKutusu", () => {
  it("sayılar, uyarılar ve sorunlu satırlar (ilk 50) + tümünü Excel indir", async () => {
    let govde: { baslik: string; satirlar: unknown[] } | null = null;
    sunucu.use(
      http.post("*/api/v1/sablonlar/sorunlu-satirlar.xlsx", async ({ request }) => {
        govde = (await request.json()) as typeof govde;
        return new HttpResponse(new Blob(["x"]), { headers: { "Content-Disposition": 'attachment; filename="sorunlu-satirlar.xlsx"' } });
      }),
    );
    const sorunlu = Array.from({ length: 60 }, (_, i) => ({
      satir: i + 2,
      kod: `M-${i}`,
      alan: "fiyat",
      deger: "abc",
      neden: "sayı değil",
    }));
    const u = userEvent.setup();
    URL.createObjectURL = () => "blob:x";
    URL.revokeObjectURL = () => undefined;
    sar(
      <YuklemeOzetiKutusu
        ozet={{
          ...bosOzet,
          okunan: 70,
          yeni: 3,
          degisen: 5,
          ayni: 2,
          silinecek: 4,
          atlanan: 60,
          sorunlu,
          uyarilar: ["M-1: fiyat %20 değişiyor"],
        }}
      />,
    );
    const ozet = screen.getByLabelText("Yükleme özeti");
    expect(within(ozet).getByText("Okunan:").nextSibling).toHaveTextContent("70");
    expect(within(ozet).getByText("Silinecek:").nextSibling).toHaveTextContent("4");
    expect(screen.getByRole("list", { name: "Uyarılar" })).toHaveTextContent("%20");
    const tablo = screen.getByRole("table", { name: "Sorunlu satırlar" });
    expect(within(tablo).getAllByRole("row")).toHaveLength(51); // başlık + ilk 50
    expect(screen.getByText(/ilk 50 \/ 60/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Tümünü Excel indir" }));
    await waitFor(() => expect(govde?.satirlar).toHaveLength(60));
  });
});

describe("SonYuklemeSeridi", () => {
  it("son yüklemeyi gösterir, onay sorusuyla geri alır", async () => {
    let geriAlindi = 0;
    sunucu.use(
      http.get("*/api/v1/aktarim/uretim-adetleri/son-yukleme", () =>
        HttpResponse.json(
          geriAlindi
            ? { son: null }
            : { son: { id: 1, zaman: "2026-11-16T11:20:00", olusturan: "esma", ozet: "2 yeni ürün", kaynak_dosya: "uretim.xlsx" } },
        ),
      ),
      http.post("*/api/v1/aktarim/uretim-adetleri/son-yuklemeyi-geri-al", ({ request }) => {
        expect(new URL(request.url).searchParams.get("senaryo")).toBe("1");
        geriAlindi += 1;
        return HttpResponse.json({
          geri_alinan: { id: 1, zaman: null, olusturan: "esma", ozet: "2 yeni ürün", kaynak_dosya: null },
          mesaj: "Son yükleme geri alındı (2 yeni ürün).",
        });
      }),
    );
    const u = userEvent.setup();
    sar(<SonYuklemeSeridi yol="/api/v1/aktarim/uretim-adetleri" sorgu={{ senaryo: 1 }} />);
    const serit = await screen.findByLabelText("Son yükleme");
    expect(serit).toHaveTextContent("esma, 2 yeni ürün (uretim.xlsx)");
    await u.click(within(serit).getByRole("button", { name: "Geri al" }));
    const diyalog = await screen.findByRole("dialog");
    expect(diyalog).toHaveTextContent("Son yüklemeyi geri al");
    await u.click(within(diyalog).getByRole("button", { name: "Geri al" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Son yükleme geri alındı");
    expect(geriAlindi).toBe(1);
    await waitFor(() => expect(screen.queryByLabelText("Son yükleme")).not.toBeInTheDocument());
  });

  it("kilitliyken Geri al pasif", async () => {
    sunucu.use(
      http.get("*/api/v1/x/son-yukleme", () =>
        HttpResponse.json({ son: { id: 1, zaman: null, olusturan: "esma", ozet: "3 fiyat", kaynak_dosya: null } }),
      ),
    );
    sar(<SonYuklemeSeridi yol="/api/v1/x" sorgu={{ senaryo: 1 }} kilitli kilitNedeni="Düzenleme kilitli" />);
    expect(await screen.findByRole("button", { name: "Geri al" })).toBeDisabled();
  });
});

describe("Veri Aktar — satır kaybı onayı (409)", () => {
  it("'N kalem silinecek' diye sorar, onaylanınca onay=true ile yeniden gönderir; özet ve şablon bağlantısı görünür", async () => {
    const onaylar: (string | null)[] = [];
    const asil = FormData.prototype.append;
    let sonOnay: string | null = null;
    FormData.prototype.append = function (this: FormData, ad: string, deger: string | Blob, dosyaAdi?: string) {
      if (ad === "onay" && typeof deger === "string") sonOnay = deger;
      return dosyaAdi === undefined ? asil.call(this, ad, deger as string) : asil.call(this, ad, deger as Blob, dosyaAdi);
    } as typeof FormData.prototype.append;
    try {
      sunucu.use(
        http.post("*/api/v1/aktarim/gider-dagitim/onizle", () =>
          HttpResponse.json({ ...giderOnizle, ozet: { ...bosOzet, okunan: 12, degisen: 1, ayni: 10, silinecek: 3 } }),
        ),
        http.post("*/api/v1/aktarim/gider-dagitim/uygula", () => {
          onaylar.push(sonOnay);
          sonOnay = null;
          if (onaylar.length === 1)
            return HttpResponse.json(
              {
                hata: "catisma",
                mesaj: "Yeni dosyada 1 ambalaj sınıfı var, mevcut veride 4. Yüklerseniz 3 ambalaj sınıfı silinecek. Emin misiniz?",
                alanlar: { mevcut: 4, yeni: 1, silinecek: 3 },
                kod: "satir_kaybi_onayi",
              },
              { status: 409 },
            );
          return HttpResponse.json({ havuz: 1, ambalaj: 1, havuz_kodlari: ["dolum_iscilik"] });
        }),
      );
      const u = userEvent.setup();
      sar(<GiderDagitimAktar />);
      expect(screen.getByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/sablonlar/gider_dagitim.xlsx");
      expect(screen.getByText(/başlık adları büyük\/küçük harf fark etmez/)).toBeInTheDocument();
      await u.upload(screen.getByLabelText("Excel dosyası"), xlsx());
      await u.click(screen.getByRole("button", { name: "Önizle" }));
      const ozet = await screen.findByLabelText("Yükleme özeti");
      expect(within(ozet).getByText("Silinecek:").nextSibling).toHaveTextContent("3");
      await u.type(screen.getByLabelText("Neden"), "bütçe revizyonu");
      await u.click(screen.getByRole("button", { name: "Uygula" }));
      const diyalog = await screen.findByRole("dialog");
      expect(diyalog).toHaveTextContent("3 kalem silinecek. Emin misiniz?");
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // 409 onayı hata kutusu olarak gösterilmez
      await u.click(within(diyalog).getByRole("button", { name: "Evet, yükle" }));
      expect(await screen.findByRole("region", { name: "Aktarım özeti" })).toBeInTheDocument();
      expect(onaylar).toEqual([null, "true"]);
    } finally {
      FormData.prototype.append = asil;
    }
  });
});
