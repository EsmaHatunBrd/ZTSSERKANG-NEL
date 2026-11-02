import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { calismaDisiSatir, dashboardSatirlari } from "@/test/fikstur/urunler";
import { kurSayfa } from "@/test/kur-ayarlar";
import Urunler from "./Urunler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

describe("Urunler (Faz 5c çalışma dışı anahtarı)", () => {
  it("varsayılan listede Durum sütunu yoktur ve istek tum taşımaz; Yeni ürün bağlantısı Veri Girişi'ne gider", async () => {
    const sorgular: (string | null)[] = [];
    sunucu.use(
      http.get("*/api/v1/urunler", ({ request }) => {
        sorgular.push(new URL(request.url).searchParams.get("tum"));
        return HttpResponse.json({ kayitlar: dashboardSatirlari, toplam: 3, enflasyon_altinda_toplam: 0 });
      }),
    );
    kurSayfa(<Urunler />);
    await screen.findByText("Salatalık Turşusu 720 ml");
    expect(sorgular).toEqual([null]);
    expect(screen.queryByRole("columnheader", { name: "Durum" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Yeni ürün" })).toHaveAttribute("href", "/veri-girisi?senaryo=1");
  });

  it("'Çalışma dışı ürünleri göster' tum=true ile sorgular; Durum sütunu Dahil / Çalışma dışı rozetlerini gösterir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Urunler />);
    await screen.findByText("Salatalık Turşusu 720 ml");
    expect(screen.queryByText(calismaDisiSatir.ad)).not.toBeInTheDocument();
    await u.click(screen.getByRole("checkbox", { name: "Çalışma dışı ürünleri göster" }));
    const yeni = await screen.findByText(calismaDisiSatir.ad);
    expect(screen.getByRole("columnheader", { name: "Durum" })).toBeInTheDocument();
    const satir = yeni.closest("tr") as HTMLElement;
    expect(within(satir).getByText("Çalışma dışı")).toHaveAttribute("title", "Reçete bulunamadı");
    const dahil = screen.getByText("Biber Turşusu 370 ml").closest("tr") as HTMLElement;
    expect(within(dahil).getByText("Dahil")).toBeInTheDocument();
    await u.click(screen.getByRole("checkbox", { name: "Çalışma dışı ürünleri göster" }));
    await waitFor(() => expect(screen.queryByText(calismaDisiSatir.ad)).not.toBeInTheDocument());
  });

  it("?tum=1 ile açılınca (Veri Kontrolü bağlantısı) anahtar açık gelir ve istek tum=true taşır", async () => {
    const sorgular: (string | null)[] = [];
    sunucu.use(
      http.get("*/api/v1/urunler", ({ request }) => {
        sorgular.push(new URL(request.url).searchParams.get("tum"));
        return HttpResponse.json({ kayitlar: [...dashboardSatirlari, calismaDisiSatir], toplam: 4, enflasyon_altinda_toplam: 0 });
      }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/urunler?senaryo=1&tum=1"]}>
          <SenaryoSaglayici>
            <Urunler />
          </SenaryoSaglayici>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(calismaDisiSatir.ad)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Çalışma dışı ürünleri göster" })).toBeChecked();
    expect(sorgular).toContain("true");
  });
});
