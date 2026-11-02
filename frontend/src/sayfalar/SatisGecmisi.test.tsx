import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { rotalar } from "@/yonlendirme";
import SatisGecmisi from "./SatisGecmisi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

const T = "*/api/v1/satis-gecmisi";
const KAYITLAR = [
  { id: 7, urun_kodu: "ORNEK-001", urun_ad: "Örnek Ürün", musteri: "Deneme Ltd", tarih: "2025-03-01", fiyat: "1234.5", para_birimi: "EUR", adet: "100", olusturan: "esma" },
  { id: 8, urun_kodu: "ORNEK-002", urun_ad: "Başka Ürün", musteri: "Başka AŞ", tarih: "2024-12-31", fiyat: "9", para_birimi: "TL", adet: "2000", olusturan: "esma" },
];

function kur() {
  const istekler = { liste: [] as string[], ekle: [] as Record<string, unknown>[], sil: [] as string[], yukle: 0 };
  const durum = { yuklemeYaniti: null as Response | null };
  sunucu.use(
    http.get(T, ({ request }) => {
      istekler.liste.push(new URL(request.url).search);
      return HttpResponse.json({ kayitlar: KAYITLAR, toplam: 2 });
    }),
    http.post(T, async ({ request }) => {
      const govde = (await request.json()) as Record<string, unknown>;
      istekler.ekle.push(govde);
      return HttpResponse.json({ ...KAYITLAR[0], ...govde, id: 9, urun_ad: "Örnek Ürün", olusturan: "esma" }, { status: 201 });
    }),
    // jsdom FormData + undici: MSW çok parçalı gövdeyi okuyamaz (bkz. isleyiciler-aktar.ts); yalnız içerik türü doğrulanır.
    http.post(`${T}/yukle`, ({ request }) => {
      istekler.yukle += 1;
      expect(request.headers.get("content-type")).toContain("multipart/form-data");
      return durum.yuklemeYaniti ?? HttpResponse.json({ eklenen: 3, hatalar: [] });
    }),
    http.delete(`${T}/:id`, ({ params }) => {
      istekler.sil.push(String(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SatisGecmisi />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { istekler, durum };
}

describe("SatisGecmisi (Faz 5 T2)", () => {
  it("rota kayıtlıdır", () => {
    expect(rotalar[0].children.some((r) => r.path === "satis-gecmisi")).toBe(true);
  });

  it("listeyi, şablon bağlantısını ve para birimli fiyatı gösterir", async () => {
    kur();
    expect(await screen.findByRole("heading", { name: "Satış Geçmişi" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/satis-gecmisi/sablon.xlsx");
    const satir = (await screen.findByText("ORNEK-001")).closest("tr") as HTMLElement;
    expect(within(satir).getByText("Örnek Ürün")).toBeInTheDocument();
    expect(within(satir).getByText("01.03.2025")).toBeInTheDocument();
    expect(within(satir).getByText("1.234,50 EUR")).toBeInTheDocument();
    expect(within(satir).getByText("100")).toBeInTheDocument();
  });

  it("süzgeç değerlerini sorguya yazar", async () => {
    const { istekler } = kur();
    await screen.findByText("ORNEK-001");
    await userEvent.type(screen.getByLabelText("Ürün kodu"), "ORN");
    await userEvent.type(screen.getByLabelText("Müşteri"), "Den");
    await userEvent.type(screen.getByLabelText("Başlangıç tarihi"), "2025-01-01");
    await waitFor(() => {
      const son = new URLSearchParams(istekler.liste.at(-1));
      expect(son.get("urun_kodu")).toBe("ORN");
      expect(son.get("musteri")).toBe("Den");
      expect(son.get("bas")).toBe("2025-01-01");
    });
  });

  it("dosya yükleme başarısında eklenen sayısını gösterir", async () => {
    const { istekler } = kur();
    await screen.findByText("ORNEK-001");
    const yukleDugmesi = screen.getByRole("button", { name: "Yükle" });
    expect(yukleDugmesi).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("Dosya seç"), new File(["urun_kodu;musteri"], "satis.csv", { type: "text/csv" }));
    await userEvent.click(yukleDugmesi);
    expect(await screen.findByRole("status", { name: "Yükleme sonucu" })).toHaveTextContent("3 satır eklendi");
    expect(istekler.yukle).toBe(1);
  });

  it("yükleme hatasında satır numaralı hata listesini gösterir", async () => {
    const { durum } = kur();
    durum.yuklemeYaniti = HttpResponse.json(
      {
        hata: "dogrulama",
        mesaj: "dosyada hatalı satırlar var; hiçbir satır eklenmedi",
        alanlar: { hatalar: [{ satir_no: 3, mesaj: "ürün bulunamadı" }, { satir_no: 5, mesaj: "tarih geçersiz" }] },
      },
      { status: 422 },
    );
    await screen.findByText("ORNEK-001");
    await userEvent.upload(screen.getByLabelText("Dosya seç"), new File(["x"], "satis.csv"));
    await userEvent.click(screen.getByRole("button", { name: "Yükle" }));
    const uyari = await screen.findByRole("alert", { name: "Yükleme hataları" });
    expect(within(uyari).getByText("Satır 3: ürün bulunamadı")).toBeInTheDocument();
    expect(within(uyari).getByText("Satır 5: tarih geçersiz")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Yükleme sonucu" })).not.toBeInTheDocument();
  });

  it("satır eklerken gövdeyi Decimal metni olarak gönderir", async () => {
    const { istekler } = kur();
    await screen.findByText("ORNEK-001");
    const form = screen.getByRole("form", { name: "Satır ekle" });
    await userEvent.type(within(form).getByLabelText("Ürün kodu *"), "ORNEK-001");
    await userEvent.type(within(form).getByLabelText("Müşteri *"), "Deneme Ltd");
    await userEvent.type(within(form).getByLabelText("Tarih *"), "2025-06-30");
    await userEvent.type(within(form).getByLabelText("Fiyat *"), "12,5");
    await userEvent.selectOptions(within(form).getByLabelText("Para birimi"), "USD");
    await userEvent.type(within(form).getByLabelText("Adet *"), "40");
    await userEvent.click(within(form).getByRole("button", { name: "Ekle" }));
    await waitFor(() => expect(istekler.ekle).toHaveLength(1));
    expect(istekler.ekle[0]).toEqual({ urun_kodu: "ORNEK-001", musteri: "Deneme Ltd", tarih: "2025-06-30", fiyat: "12.5", para_birimi: "USD", adet: "40" });
    expect(await screen.findByRole("status", { name: "Ekleme durumu" })).toBeInTheDocument();
  });

  it("geçersiz forma istek atmaz", async () => {
    const { istekler } = kur();
    await screen.findByText("ORNEK-001");
    const form = screen.getByRole("form", { name: "Satır ekle" });
    await userEvent.type(within(form).getByLabelText("Ürün kodu *"), "ORNEK-001");
    await userEvent.click(within(form).getByRole("button", { name: "Ekle" }));
    expect(await within(form).findByRole("alert")).toHaveTextContent("zorunlu");
    expect(istekler.ekle).toHaveLength(0);
  });

  it("silmeden önce onay ister; vazgeçince istek atmaz, onaylayınca siler", async () => {
    const { istekler } = kur();
    const satir = (await screen.findByText("ORNEK-001")).closest("tr") as HTMLElement;
    await userEvent.click(within(satir).getByRole("button", { name: /^Sil/ }));
    const diyalog = await screen.findByRole("dialog");
    await userEvent.click(within(diyalog).getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(istekler.sil).toEqual([]);
    await userEvent.click(within(satir).getByRole("button", { name: /^Sil/ }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(istekler.sil).toEqual(["7"]));
  });
});
