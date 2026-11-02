import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { uyarilarIsleyici } from "@/test/msw/isleyiciler-aktar";
import { cokluUyarilar } from "@/test/fikstur/aktar";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import Uyarilar, { fiyatsizMalzemeler, uyariKategorisi } from "./Uyarilar";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function kur() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/uyarilar?senaryo=1"]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/uyarilar" element={<Uyarilar />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("uyariKategorisi", () => {
  it("metne göre sınıflar", () => {
    expect(uyariKategorisi("Kapak M-77 fiyat listesinde yok")).toBe("fiyat");
    expect(uyariKategorisi("Kur bulunamadı")).toBe("kur");
    expect(uyariKategorisi("Hat Cam Hattı tanımsız")).toBe("hat");
    expect(uyariKategorisi("Taze/turşu sınıfı tanımsız")).toBe("sinif");
    expect(uyariKategorisi("Yurtdışı pazar gideri sıfır")).toBe("yurtdisi");
    expect(uyariKategorisi("Vardiya sayısı tanımsız")).toBe("vardiya");
    expect(uyariKategorisi("Beklenmeyen")).toBe("diger");
    // Malzeme adı sınıflandırmaya girmez (adında 'Kuru', 'Hattı' olsa da).
    expect(uyariKategorisi("15.213 (Kuru Maydanoz): fiyat listesinde yok, 0 TL alındı")).toBe("fiyat");
    expect(uyariKategorisi("16.011 (Kapari): Ziraat kaynaklı ama döviz fiyatlı (EUR): kur uygulanmaz, kontrol edin")).toBe("kur");
  });
});

describe("fiyatsizMalzemeler", () => {
  it("gerçek uyarı biçimini malzemeye göre toplar, çok geçen önce", () => {
    const m = fiyatsizMalzemeler([
      { urun_kodu: "A", uyari: "16.1 (Sarı Turşu): fiyat listesinde yok, 0 TL alındı" },
      { urun_kodu: "B", uyari: "16.1 (Sarı Turşu): fiyat listesinde yok, 0 TL alındı" },
      { urun_kodu: "B", uyari: "15.9 (Salamura): fiyat listesinde yok, 0 TL alındı" },
    ]);
    expect(m).toEqual([
      { malzeme: "16.1 (Sarı Turşu)", urunler: ["A", "B"] },
      { malzeme: "15.9 (Salamura)", urunler: ["B"] },
    ]);
  });
});

describe("Uyarılar", () => {
  it("uyarıları türüne göre gruplar ve sayar", async () => {
    sunucu.use(uyarilarIsleyici(cokluUyarilar));
    kur();
    const fiyat = await screen.findByRole("region", { name: /Fiyat listesinde yok/ });
    // Aynı malzeme iki üründe: tek malzeme satırı, iki ürün bağlantısı.
    expect(within(fiyat).getByText("1", { selector: "[data-sayi]" })).toBeInTheDocument();
    expect(within(fiyat).getByText("Kapak M-77")).toBeInTheDocument();
    expect(within(fiyat).getByText("2 üründe")).toBeInTheDocument();
    expect(within(fiyat).getAllByRole("link", { hidden: true })).toHaveLength(2);
    expect(within(fiyat).getAllByRole("link", { hidden: true })[0]).toHaveAttribute("href", "/urunler/URUN-001?senaryo=1");
    // Fiyat bölümü en sonda: müdahale gerektiren uyarılar önce.
    const bolgeler = screen.getAllByRole("region").map((b) => b.getAttribute("aria-labelledby"));
    expect(bolgeler[0]).toBe("uyari-baslik-kur");
    expect(bolgeler[bolgeler.length - 1]).toBe("uyari-baslik-fiyat");
    for (const ad of [/Kur/, /Hat/, /Sınıf/, /Yurtdışı/, /Vardiya/, /Diğer/]) {
      const g = screen.getByRole("region", { name: ad });
      expect(within(g).getByText(/^[12]$/, { selector: "[data-sayi]" })).toBeInTheDocument();
    }
    expect(screen.getByText("8 uyarı, 3 ürün")).toBeInTheDocument();
  });

  it("uyarı yoksa boş durum gösterir", async () => {
    sunucu.use(uyarilarIsleyici([]));
    kur();
    expect(await screen.findByText("Bu senaryoda uyarı yok")).toBeInTheDocument();
  });

  it("hata durumunu gösterir", async () => {
    sunucu.use(
      http.get("*/api/v1/uyarilar", () => HttpResponse.json({ hata: "sunucu", mesaj: "Uyarılar okunamadı", alanlar: {} }, { status: 500 })),
    );
    kur();
    expect(await screen.findByRole("alert")).toHaveTextContent("Uyarılar okunamadı");
  });
});
