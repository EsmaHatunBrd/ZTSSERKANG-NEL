import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { bosStokDevri } from "@/test/msw/isleyiciler";
import type { StokDevri } from "@/api/tipler";
import { StokEtkisiKarti } from "./StokEtkisiKarti";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

const doluStokDevri: StokDevri = {
  urun_kodu: "URUN-001",
  adet: "1200",
  birim_maliyet: "10",
  enflasyon: null,
  uretim_adedi: "4800",
  enflasyon_kullanilan: "0.5",
  uretim_adedi_kullanilan: "4800",
  uretim_adedi_kaynagi: "elle",
  guncel_stok_maliyeti: "15",
  bu_yil_maliyet: "20",
  ortalama_maliyet: "19",
  stok_payi: "0.2",
  stok_etkisi: true,
  aciklama: null,
};

function kur(eleman: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{eleman}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StokEtkisiKarti", () => {
  it("kayıt yoksa yalnız sade 'Stokta kalan ekle' düğmesi görünür", async () => {
    kur(<StokEtkisiKarti kod="URUN-001" senaryoId={1} kilitli={false} />);
    expect(await screen.findByRole("button", { name: /Stokta kalan ekle/ })).toBeEnabled();
    expect(screen.queryByRole("region", { name: "Stok etkisi" })).not.toBeInTheDocument();
    expect(screen.queryByText("Ortalama maliyet")).not.toBeInTheDocument();
  });

  it("kilitli senaryoda ekleme düğmesi pasiftir", async () => {
    kur(<StokEtkisiKarti kod="URUN-001" senaryoId={1} kilitli />);
    expect(await screen.findByRole("button", { name: /Stokta kalan ekle/ })).toBeDisabled();
  });

  it("ekleme: hatalı alanları Türkçe gösterir, geçerli formda PUT gövdesini (enflasyon oran) ve nedeni gönderir", async () => {
    let govde: Record<string, unknown> | null = null;
    let senaryo: string | null = null;
    sunucu.use(
      http.put(`${T}/urunler/:kod/stok-devri`, async ({ request }) => {
        govde = (await request.json()) as Record<string, unknown>;
        senaryo = new URL(request.url).searchParams.get("senaryo");
        return HttpResponse.json(doluStokDevri);
      }),
    );
    const user = userEvent.setup();
    kur(<StokEtkisiKarti kod="URUN-001" senaryoId={1} kilitli={false} />);
    await user.click(await screen.findByRole("button", { name: /Stokta kalan ekle/ }));
    const diyalog = await screen.findByRole("dialog");

    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));
    expect(within(diyalog).getByText("Stok adedi zorunlu")).toBeInTheDocument();
    expect(within(diyalog).getByText("Neden zorunlu")).toBeInTheDocument();
    expect(govde).toBeNull();

    await user.type(within(diyalog).getByLabelText("Stok adedi"), "1200");
    await user.type(within(diyalog).getByLabelText("Stok birim maliyeti (TL)"), "10,5");
    await user.type(within(diyalog).getByLabelText("Enflasyon (%)"), "45");
    await user.type(within(diyalog).getByLabelText("Neden (zorunlu)"), "Sayım");
    expect(within(diyalog).getByText(/Özet: 1\.200 adet × 10,50 TL stok; enflasyon %45/)).toBeInTheDocument();
    await user.click(within(diyalog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(govde).not.toBeNull());
    expect(govde).toEqual({ adet: "1200", birim_maliyet: "10.5", enflasyon: "0.45", uretim_adedi: null, neden: "Sayım" });
    expect(senaryo).toBe("1");
  });

  it("kayıt varsa değerleri, kaynak rozetlerini ve ortalama maliyeti gösterir; kaldır nedenle DELETE gönderir", async () => {
    let silinen: URL | null = null;
    let kayit: StokDevri = { ...doluStokDevri, aciklama: "Geçen yıl satışı yok; üretim adedi elle girildi." };
    sunucu.use(
      http.get(`${T}/urunler/:kod/stok-devri`, () => HttpResponse.json(kayit)),
      http.delete(`${T}/urunler/:kod/stok-devri`, ({ request }) => {
        silinen = new URL(request.url);
        kayit = bosStokDevri("URUN-001");
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    kur(<StokEtkisiKarti kod="URUN-001" senaryoId={1} kilitli={false} />);
    const kart = await screen.findByRole("region", { name: "Stok etkisi" });
    expect(within(kart).getByText("1.200")).toBeInTheDocument();
    expect(within(kart).getByText("10,00 TL")).toBeInTheDocument();
    expect(within(kart).getByText("50,0 %")).toBeInTheDocument();
    expect(within(kart).getByText("parametre")).toBeInTheDocument();
    expect(within(kart).getByText("elle")).toBeInTheDocument();
    expect(within(kart).getByText("19,00 TL")).toBeInTheDocument();
    expect(within(kart).getByText("20,0 %")).toBeInTheDocument();
    expect(within(kart).getByRole("note")).toHaveTextContent("Geçen yıl satışı yok");

    await user.click(within(kart).getByRole("button", { name: /Kaldır/ }));
    const diyalog = await screen.findByRole("dialog");
    await user.click(within(diyalog).getByRole("button", { name: "Kaldır" }));
    expect(within(diyalog).getByText("Neden zorunlu")).toBeInTheDocument();
    expect(silinen).toBeNull();
    await user.type(within(diyalog).getByLabelText("Neden (zorunlu)"), "Stok satıldı");
    await user.click(within(diyalog).getByRole("button", { name: "Kaldır" }));

    await waitFor(() => expect(silinen).not.toBeNull());
    expect(silinen!.searchParams.get("neden")).toBe("Stok satıldı");
    expect(silinen!.searchParams.get("senaryo")).toBe("1");
    expect(await screen.findByRole("button", { name: /Stokta kalan ekle/ })).toBeInTheDocument();
  });

  it("kilitli senaryoda düzenle ve kaldır pasiftir", async () => {
    sunucu.use(http.get(`${T}/urunler/:kod/stok-devri`, () => HttpResponse.json(doluStokDevri)));
    kur(<StokEtkisiKarti kod="URUN-001" senaryoId={1} kilitli />);
    const kart = await screen.findByRole("region", { name: "Stok etkisi" });
    expect(within(kart).getByRole("button", { name: /Düzenle/ })).toBeDisabled();
    expect(within(kart).getByRole("button", { name: /Kaldır/ })).toBeDisabled();
  });
});
