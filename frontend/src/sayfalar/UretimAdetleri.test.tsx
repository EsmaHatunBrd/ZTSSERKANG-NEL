import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { urunExcelIsleyicileri } from "@/test/msw/isleyiciler-urun-excel";
import { sunucu } from "@/test/msw/sunucu";
import { MENU } from "@/bilesenler/Kabuk";
import { rotalar } from "@/yonlendirme";
import UretimAdetleri from "./UretimAdetleri";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function kur() {
  const { isleyiciler, istekler } = urunExcelIsleyicileri();
  sunucu.use(...isleyiciler);
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/uretim-adetleri?senaryo=1"]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/uretim-adetleri" element={<UretimAdetleri />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return istekler;
}

const satir = (kod: string) => screen.getByText(kod).closest("tr") as HTMLElement;

describe("UretimAdetleri (U8)", () => {
  it("kapasite tablosunu senaryo ile çeker ve Excel sütunlarıyla gösterir", async () => {
    const istekler = kur();
    expect(await screen.findByRole("heading", { name: "Üretim Adetleri" })).toBeInTheDocument();
    const tablo = await screen.findByRole("table", { name: "Üretim adetleri tablosu" });
    await within(tablo).findByText("URUN-001");
    expect(within(tablo).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Ürün kodu",
      "Ürün",
      "Net kapasite",
      "Net süre",
      "Toplam kapasite",
      "Toplam süre",
      "Hedef üretim",
      "Ortalama işçi",
      "",
    ]);
    const bir = satir("URUN-001");
    expect(within(bir).getByText("Salatalık Turşusu 720 ml")).toBeInTheDocument();
    expect(within(bir).getByText("12.000")).toBeInTheDocument();
    expect(within(bir).getByText("7,5")).toBeInTheDocument();
    expect(within(bir).getByText("11.000")).toBeInTheDocument();
    expect(within(satir("URUN-002")).getByText("—")).toBeInTheDocument();
    expect(istekler.kapasiteListe[0]).toContain("senaryo=1");
  });

  it("satır içi düzenleme: neden zorunlu, PUT gövdesi alanlar + neden", async () => {
    const istekler = kur();
    await screen.findByText("URUN-001");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Düzenle — URUN-001" }));
    const hedef = screen.getByLabelText("Hedef üretim");
    await user.clear(hedef);
    await user.type(hedef, "11500");
    const kaydet = screen.getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled(); // neden yok
    await user.type(screen.getByLabelText("Neden"), "Sezon planı güncellendi");
    expect(kaydet).toBeEnabled();
    await user.click(kaydet);
    await waitFor(() => expect(istekler.kapasiteKaydet).toHaveLength(1));
    expect(istekler.kapasiteKaydet[0]).toEqual({
      kod: "URUN-001",
      senaryo: "1",
      govde: {
        net_kapasite: "12000",
        net_sure: "7.5",
        toplam_kapasite: "13000",
        toplam_sure: "8",
        hedef_uretim: "11500",
        ortalama_isci: "9",
        neden: "Sezon planı güncellendi",
      },
    });
    expect(await screen.findByRole("status", { name: "Kayıt durumu" })).toHaveTextContent("URUN-001");
    // Liste yenilendi, düzenleyici kapandı.
    await waitFor(() => expect(within(satir("URUN-001")).getByText("11.500")).toBeInTheDocument());
    expect(screen.queryByLabelText("Hedef üretim")).not.toBeInTheDocument();
  });

  it("geçersiz sayı kaydı engeller ve hata gösterir", async () => {
    const istekler = kur();
    await screen.findByText("URUN-001");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Düzenle — URUN-001" }));
    const hedef = screen.getByLabelText("Hedef üretim");
    await user.clear(hedef);
    await user.type(hedef, "abc");
    await user.type(screen.getByLabelText("Neden"), "deneme");
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    expect(screen.getByText("Hedef üretim sayı olmalı")).toBeInTheDocument();
    expect(istekler.kapasiteKaydet).toHaveLength(0);
  });
});

describe("Üretim Adetleri menü ve rota", () => {
  it("menüde ve rota ağacında /uretim-adetleri vardır", () => {
    expect(MENU.find((m) => m.etiket === "Üretim Adetleri")?.yol).toBe("/uretim-adetleri");
    expect(rotalar[0].children.some((c) => "path" in c && c.path === "uretim-adetleri")).toBe(true);
  });
});
