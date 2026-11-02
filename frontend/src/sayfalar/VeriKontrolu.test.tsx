import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { tutarlilikSorunlu } from "@/test/fikstur/tutarlilik";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import VeriKontrolu, { senaryoluYol } from "./VeriKontrolu";
import { VeriKontroluSeridi } from "./dashboard/VeriKontroluSeridi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

let yon: ReturnType<typeof createMemoryRouter>;

function kur(yol = "/veri-kontrolu?senaryo=1", sorunlu = true) {
  if (sorunlu) sunucu.use(http.get("*/api/v1/tutarlilik", () => HttpResponse.json(tutarlilikSorunlu)));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  yon = createMemoryRouter(
    [
      {
        path: "/veri-kontrolu",
        element: (
          <SenaryoSaglayici>
            <VeriKontrolu />
          </SenaryoSaglayici>
        ),
      },
      {
        path: "/",
        element: (
          <SenaryoSaglayici>
            <VeriKontroluSeridi senaryoId={1} />
          </SenaryoSaglayici>
        ),
      },
      { path: "*", element: <div>hedef</div> },
    ],
    { initialEntries: [yol] },
  );
  render(
    <QueryClientProvider client={qc}>
      <RouterProvider router={yon} />
    </QueryClientProvider>,
  );
}

describe("senaryoluYol", () => {
  it("sorgu varsa & ile, yoksa ? ile senaryo ekler", () => {
    expect(senaryoluYol("/gider", 5)).toBe("/gider?senaryo=5");
    expect(senaryoluYol("/fiyatlar?fiyatsiz=1", 5)).toBe("/fiyatlar?fiyatsiz=1&senaryo=5");
    expect(senaryoluYol("/gider", null)).toBe("/gider");
  });
});

describe("Veri Kontrolü sayfası", () => {
  it("ağır olan üstte, durum metinle; hata kartının kayıtları açık, dikkat kartınınki kapalı; çözüm bağlantısı senaryolu", async () => {
    kur();
    const basliklar = await screen.findAllByRole("heading", { level: 2 });
    expect(basliklar.map((h) => h.textContent)).toEqual(["Hesaplanamayan ürün", "Fiyatı olmayan malzeme", "Gider payı %100 değil"]);
    expect(screen.getByText("2 konu", { exact: false })).toBeInTheDocument();
    const hata = screen.getByRole("region", { name: "Hesaplanamayan ürün" });
    expect(within(hata).getByText(/Hata · 1 kayıt/)).toBeInTheDocument();
    expect(within(hata).getByRole("link", { name: "03.009 · Kornişon" })).toHaveAttribute("href", "/urunler/03.009?senaryo=1");
    const fiyat = screen.getByRole("region", { name: "Fiyatı olmayan malzeme" });
    expect(within(fiyat).queryByRole("link", { name: /Sarımsak/ })).not.toBeInTheDocument();
    expect(within(fiyat).getByRole("link", { name: /Malzeme Fiyatları/ })).toHaveAttribute("href", "/fiyatlar?fiyatsiz=1&senaryo=1");
    const tamam = screen.getByRole("region", { name: "Gider payı %100 değil" });
    expect(within(tamam).getByText("Tamam")).toBeInTheDocument();
    expect(within(tamam).queryByRole("button")).not.toBeInTheDocument();
  });

  it("Kayıtlar düğmesi listeyi açar; kayda tıklayınca ilgili sayfaya gider", async () => {
    const u = userEvent.setup();
    kur();
    const fiyat = await screen.findByRole("region", { name: "Fiyatı olmayan malzeme" });
    const dugme = within(fiyat).getByRole("button", { name: "Kayıtlar" });
    expect(dugme).toHaveAttribute("aria-expanded", "false");
    await u.click(dugme);
    expect(within(fiyat).getByRole("button", { name: "Gizle" })).toHaveAttribute("aria-expanded", "true");
    await u.click(within(fiyat).getByRole("link", { name: "15.001 · Sarımsak" }));
    expect(yon.state.location.pathname).toBe("/fiyatlar");
    expect(yon.state.location.search).toBe("?fiyatsiz=1&arama=15.001&senaryo=1");
  });

  it("hepsi tamamsa tek satır özet", async () => {
    kur("/veri-kontrolu?senaryo=1", false);
    expect(await screen.findByText("Tüm kontroller tamam.")).toBeInTheDocument();
  });
});

describe("Genel Bakış Veri Kontrolü şeridi", () => {
  it("ilgi bekleyen konu varsa sayı, başlıklar ve bağlantı", async () => {
    kur("/");
    const serit = await screen.findByRole("status", { name: "Veri Kontrolü" });
    expect(serit).toHaveTextContent("2 konu ilgi bekliyor (1 tanesi hesabı engelliyor)");
    expect(serit).toHaveTextContent("fiyatı olmayan malzeme");
    expect(within(serit).getByRole("link")).toHaveAttribute("href", "/veri-kontrolu?senaryo=1");
  });

  it("hepsi tamamsa çizilmez", async () => {
    kur("/", false);
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByRole("status", { name: "Veri Kontrolü" })).not.toBeInTheDocument();
  });
});
