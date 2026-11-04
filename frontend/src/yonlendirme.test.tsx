import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { TooltipProvider } from "@/bilesenler/ui/tooltip";
import { sunucu } from "@/test/msw/sunucu";
import { MENU } from "@/bilesenler/Kabuk";
import { rotalar } from "./yonlendirme";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

function kur(yol: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const yon = createMemoryRouter(rotalar, { initialEntries: [yol] });
  render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <RouterProvider router={yon} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
  return yon;
}

describe("yönlendirme", () => {
  it("menüdeki 'Ürün Maliyeti' sabit bir ürüne değil ürün seçiciye gider", () => {
    const urun = MENU.find((m) => m.etiket === "Ürün Maliyeti");
    expect(urun?.yol).toBe("/urunler");
  });

  it("Ana Sayfa'da sol panel yok; bir bölüm kartı seçilince panel açılır", async () => {
    kur("/?senaryo=1");
    const kart = await screen.findByRole("link", { name: /Parametreler/ });
    expect(screen.queryByRole("navigation", { name: "Ana menü" })).not.toBeInTheDocument();
    await userEvent.click(kart);
    expect(await screen.findByRole("navigation", { name: "Ana menü" })).toBeInTheDocument();
  });

  it("menü bağlantıları seçili senaryoyu ?senaryo= ile taşır", async () => {
    kur("/parametreler?senaryo=2");
    const menu = screen.getByRole("navigation", { name: "Ana menü" });
    await waitFor(() => expect(within(menu).getByRole("link", { name: "Ürün Maliyeti" })).toHaveAttribute("href", "/urunler?senaryo=2"));
    expect(within(menu).getByRole("link", { name: "Teklifler" })).toHaveAttribute("href", "/teklifler?senaryo=2");
  });

  it("/urunler ürün seçici açar; satıra tıklayınca ürün ekranına senaryo ile gider", async () => {
    const yon = kur("/urunler?senaryo=1");
    expect(await screen.findByRole("heading", { name: "Ürünler" })).toBeInTheDocument();
    const tablo = await screen.findByRole("table");
    const satir = await within(tablo).findByText("URUN-001");
    await userEvent.click(satir);
    expect(yon.state.location.pathname).toBe("/urunler/URUN-001");
    expect(yon.state.location.search).toContain("senaryo=1");
  });

  it("ürün seçicide kod/ad ile arama yapılır", async () => {
    kur("/urunler?senaryo=1");
    await screen.findByText("URUN-001");
    await userEvent.type(screen.getByLabelText("Ürün ara"), "URUN-002");
    expect(screen.queryByText("URUN-001")).not.toBeInTheDocument();
    expect(screen.getByText("URUN-002")).toBeInTheDocument();
  });

  it("bilinmeyen adres 'Sayfa bulunamadı' ve ana sayfa bağlantısı gösterir", async () => {
    kur("/yok-boyle-bir-sayfa");
    expect(await screen.findByText("Sayfa bulunamadı")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ana sayfaya dön" })).toHaveAttribute("href", "/");
  });

  it("sayfa çizilirken hata fırlarsa errorElement 'Beklenmeyen bir hata' gösterir", async () => {
    const Patlak = () => {
      throw new Error("deneme hatası");
    };
    const yon = createMemoryRouter([{ path: "/", element: <Patlak />, errorElement: rotalar[0].errorElement }], { initialEntries: ["/"] });
    const sus = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(<RouterProvider router={yon} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Beklenmeyen bir hata oluştu");
    expect(screen.getByRole("link", { name: "Ana sayfaya dön" })).toBeInTheDocument();
    sus.mockRestore();
  });
});
