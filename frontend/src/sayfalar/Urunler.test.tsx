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

describe("Urunler (favoriler ve son açılanlar)", () => {
  const FAVORI = "fiyat-calismasi.favoriler";
  const SON = "fiyat-calismasi.son-acilanlar";
  const oku = (k: string) => JSON.parse(localStorage.getItem(k) ?? "null");

  it("yıldız düğmesi favoriye ekler/çıkarır, localStorage'a yazar ve Favoriler bölümünde bağlantı gösterir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Urunler />);
    const satir = (await screen.findByText("Salatalık Turşusu 720 ml")).closest("tr") as HTMLElement;
    expect(screen.queryByRole("region", { name: "Favoriler" })).not.toBeInTheDocument();
    const yildiz = within(satir).getByRole("button", { name: "Favorilere ekle/çıkar" });
    expect(yildiz).toHaveAttribute("aria-pressed", "false");
    await u.click(yildiz);
    expect(yildiz).toHaveAttribute("aria-pressed", "true");
    expect(oku(FAVORI)).toEqual(["URUN-001"]);
    const bolum = screen.getByRole("region", { name: "Favoriler" });
    const bag = within(bolum).getByRole("link", { name: /Salatalık Turşusu 720 ml/ });
    expect(bag).toHaveAttribute("href", "/urunler/URUN-001?senaryo=1");
    expect(bag).toHaveTextContent("URUN-001");
    await u.click(yildiz);
    expect(yildiz).toHaveAttribute("aria-pressed", "false");
    expect(oku(FAVORI)).toEqual([]);
    expect(screen.queryByRole("region", { name: "Favoriler" })).not.toBeInTheDocument();
  });

  it("kayıtlı favoriler sayfa açılışında görünür", async () => {
    localStorage.setItem(FAVORI, JSON.stringify(["URUN-002"]));
    kurSayfa(<Urunler />);
    const bolum = await screen.findByRole("region", { name: "Favoriler" });
    expect(await within(bolum).findByRole("link", { name: /Biber Turşusu 370 ml/ })).toHaveAttribute("href", "/urunler/URUN-002?senaryo=1");
    const satir = screen.getByRole("cell", { name: "Biber Turşusu 370 ml" }).closest("tr") as HTMLElement;
    expect(within(satir).getByRole("button", { name: "Favorilere ekle/çıkar" })).toHaveAttribute("aria-pressed", "true");
  });

  it("satıra tıklama son açılanlara en başa ekler ve listeyi 8 ile sınırlar; bölüm bağlantıları doğru", async () => {
    const u = userEvent.setup();
    const eski = ["URUN-002", "K-3", "K-4", "K-5", "K-6", "K-7", "K-8", "K-9"];
    localStorage.setItem(SON, JSON.stringify(eski));
    kurSayfa(<Urunler />);
    const bolum = await screen.findByRole("region", { name: "Son açılanlar" });
    expect(within(bolum).getAllByRole("link")).toHaveLength(8);
    expect(await within(bolum).findByRole("link", { name: /Biber Turşusu 370 ml/ })).toHaveAttribute("href", "/urunler/URUN-002?senaryo=1");
    expect(within(bolum).getByRole("link", { name: "K-9" })).toHaveAttribute("href", "/urunler/K-9?senaryo=1");
    await u.click(screen.getByText("Salatalık Turşusu 720 ml"));
    expect(oku(SON)).toEqual(["URUN-001", "URUN-002", "K-3", "K-4", "K-5", "K-6", "K-7", "K-8"]);
  });

  it("aynı ürün yeniden açılınca listede tek kalır ve başa alınır; son açılan yoksa bölüm gizlidir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Urunler />);
    await screen.findByText("Salatalık Turşusu 720 ml");
    expect(screen.queryByRole("region", { name: "Son açılanlar" })).not.toBeInTheDocument();
    localStorage.setItem(SON, JSON.stringify(["URUN-002", "URUN-001"]));
    await u.click(screen.getByText("Salatalık Turşusu 720 ml"));
    expect(oku(SON)).toEqual(["URUN-001", "URUN-002"]);
  });

  it("yıldıza tıklamak satır gezinmesini tetiklemez (son açılanlara yazılmaz)", async () => {
    const u = userEvent.setup();
    kurSayfa(<Urunler />);
    const satir = (await screen.findByText("Salatalık Turşusu 720 ml")).closest("tr") as HTMLElement;
    await u.click(within(satir).getByRole("button", { name: "Favorilere ekle/çıkar" }));
    expect(localStorage.getItem(SON)).toBeNull();
  });
});
