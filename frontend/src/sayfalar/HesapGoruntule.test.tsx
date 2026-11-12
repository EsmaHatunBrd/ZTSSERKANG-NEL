import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { hesapYaniti } from "@/test/fikstur/hesapYaniti";
import HesapGoruntule from "./HesapGoruntule";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

function kur(id: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/hesaplar/${id}?senaryo=1`]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/hesaplar/:id" element={<HesapGoruntule />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("HesapGoruntule (kayıtlı hesap)", () => {
  it("başlıkta no, tarih, oluşturan; reçete, gider ve toplamlar salt okunur görünür", async () => {
    kur("5");
    expect(await screen.findByRole("heading", { name: "Kayıtlı hesap #5 · 21.10.2026 · Eşma" })).toBeInTheDocument();
    const recete = screen.getByRole("table", { name: "Reçete tablosu" });
    expect(within(recete).getByText("Pet Şişe 500 ml")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Gider kalemleri" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Toplamlar" })).toBeInTheDocument();
    // Salt okunur: hiçbir giriş alanı / düzenleme düğmesi yok.
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Elle brüt gir|Elle fiyat gir/ })).not.toBeInTheDocument();
    expect(screen.getByText(/salt okunur/i)).toBeInTheDocument();
  });

  const kayitliHesap = (girdiSnapshot: Record<string, unknown>, satirlar = hesapYaniti.satirlar) =>
    sunucu.use(
      http.get("*/api/v1/hesaplar/:id", ({ params }) =>
        HttpResponse.json({
          id: Number(params.id),
          urun_id: 1,
          senaryo_id: 1,
          hesap_tarihi: "2026-10-21",
          olusturan: "Eşma",
          girdi_snapshot: girdiSnapshot,
          sonuc_snapshot: {},
          uyarilar: [],
          gorunum: { ...hesapYaniti, satirlar },
        }),
      ),
    );

  it("girdi_snapshot.override varsa Kayıt anındaki değişiklikler okunur etiketlerle listelenir", async () => {
    kayitliHesap({
      override: {
        urun: { hat: "Herbort" },
        satirlar: { "2": { brut_miktar_elle: "0.4", elle_brut_kaldir: false, elle_fiyat_kaldir: false } },
        gider_oranlari: { "elektrik_sn.niko": "0.002" },
        parametreler: {},
        fire: {},
      },
    });
    kur("5");
    const bolum = await screen.findByRole("region", { name: "Kayıt anındaki değişiklikler" });
    expect(bolum).toHaveTextContent("Üretim hattı");
    expect(bolum).toHaveTextContent("Herbort");
    expect(bolum).toHaveTextContent("Satır 2 · elle brüt");
    expect(bolum).toHaveTextContent("Elektrik ₺/sn — niko");
    expect(bolum).toHaveTextContent("0,002");
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
  });

  it("override yoksa veya boşsa değişiklik listesi görünmez", async () => {
    kayitliHesap({ override: null });
    kur("5");
    await screen.findByRole("heading", { name: /Kayıtlı hesap #5/ });
    expect(screen.queryByRole("region", { name: "Kayıt anındaki değişiklikler" })).not.toBeInTheDocument();
  });

  it("reçete satırlarında seviye girintisi uygulanır", async () => {
    const satirlar = hesapYaniti.satirlar.map((s, i) => (i === 0 ? { ...s, seviye: 0 } : i === 1 ? { ...s, seviye: 2 } : s));
    kayitliHesap({}, satirlar);
    kur("5");
    const recete = await screen.findByRole("table", { name: "Reçete tablosu" });
    const hucre = (ad: string) => within(recete).getByText(ad, { exact: false }).closest("td") as HTMLElement;
    expect(hucre("Pet Şişe 500 ml")).toHaveStyle({ paddingLeft: "8px" });
    expect(hucre("Salamura Karışımı")).toHaveStyle({ paddingLeft: "36px" });
  });

  it("ürüne dönüş bağlantısı ürün ekranını senaryo ile açar", async () => {
    kur("5");
    const bag = await screen.findByRole("link", { name: "Ürün ekranına dön" });
    expect(bag).toHaveAttribute("href", "/urunler/URUN-001?senaryo=1");
  });

  it("olmayan hesapta hata role=alert ile gösterilir", async () => {
    kur("0x");
    expect(await screen.findByRole("alert")).toHaveTextContent("Geçersiz hesap numarası");
  });
});

describe("HesapGoruntule (yazdırma)", () => {
  it("Yazdır düğmesi window.print çağırır; kök eleman data-yazdir taşır", async () => {
    const u = userEvent.setup();
    const yazdir = vi.spyOn(window, "print").mockImplementation(() => undefined);
    const { container } = kur("5");
    const dugme = await screen.findByRole("button", { name: "Yazdır" });
    expect(container.querySelector("[data-yazdir]")).not.toBeNull();
    await u.click(dugme);
    expect(yazdir).toHaveBeenCalledTimes(1);
    yazdir.mockRestore();
  });
});
