import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { urunExcelIsleyicileri } from "@/test/msw/isleyiciler-urun-excel";
import { sunucu } from "@/test/msw/sunucu";
import Dashboard from "../Dashboard";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

function kur() {
  sunucu.use(...urunExcelIsleyicileri().isleyiciler);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/?senaryo=1"]}>
        <SenaryoSaglayici>
          <Dashboard />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Dashboard ambalaj özeti kartı (U8)", () => {
  it("ambalaj türü ve kapak bazında ürün sayısı ile üretim adedini gösterir", async () => {
    kur();
    const kart = await screen.findByRole("region", { name: "Ambalaj özeti" });
    expect(await within(kart).findByText("Cam")).toBeInTheDocument();
    const cam = within(kart).getByText("Cam").closest("li") as HTMLElement;
    expect(within(cam).getByText("12 ürün")).toBeInTheDocument();
    expect(within(cam).getByText("1.250.000 adet")).toBeInTheDocument();
    const kapak = within(kart).getByText("Twist-off 82 mm").closest("li") as HTMLElement;
    expect(within(kapak).getByText("9 ürün")).toBeInTheDocument();
    expect(within(kapak).getByText("900.000 adet")).toBeInTheDocument();
  });

  it("özet alınamazsa kart hata iletisini gösterir, dashboard çalışmaya devam eder", async () => {
    sunucu.use(
      http.get("*/api/v1/ambalaj-ozeti", () =>
        HttpResponse.json({ hata: "sunucu", mesaj: "özet hesaplanamadı", alanlar: {} }, { status: 500 }),
      ),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/?senaryo=1"]}>
          <SenaryoSaglayici>
            <Dashboard />
          </SenaryoSaglayici>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const kart = await screen.findByRole("region", { name: "Ambalaj özeti" });
    expect(await within(kart).findByText(/özet hesaplanamadı/)).toBeInTheDocument();
    expect(await within(await screen.findByRole("table")).findByText("Biber Turşusu 370 ml")).toBeInTheDocument();
  });
});
