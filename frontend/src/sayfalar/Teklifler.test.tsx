import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { tekliflerIsleyicileri, type TeklifIstekleri } from "@/test/msw/isleyiciler-aktar";
import { senaryoTeklifleri } from "@/test/fikstur/aktar";
import { SenaryoSaglayici, SenaryoSecici } from "@/bilesenler/SenaryoSecici";
import { senaryolar } from "@/test/fikstur/urunler";
import { KILIT_METNI } from "@/bilesenler/KilitSeridi";
import Teklifler from "./Teklifler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let istekler: TeklifIstekleri;
beforeEach(() => {
  localStorage.clear();
  istekler = { liste: [], durumlar: [] };
  sunucu.use(...tekliflerIsleyicileri(istekler));
});

function Yer() {
  const l = useLocation();
  return <output data-testid="yer">{l.pathname + l.search}</output>;
}

function kur() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/teklifler?senaryo=1"]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/teklifler" element={<Teklifler />} />
            <Route path="/urunler/:kod" element={<Yer />} />
            <Route path="/hesaplar/:id" element={<Yer />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const tablo = () => within(screen.getByRole("region", { name: "Teklif listesi" })).getByRole("table");
const listeHazir = () => screen.findByRole("region", { name: "Teklif listesi" });

describe("Teklifler", () => {
  it("kilitli senaryoda şerit görünür, durum seçicileri pasiftir, Teklif Kapak indir açık kalır", async () => {
    const kilitli = senaryolar.map((s) => (s.id === 1 ? { ...s, kilitli: true } : s));
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: kilitli, toplam: kilitli.length })));
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    expect(await screen.findByText(KILIT_METNI)).toBeInTheDocument();
    const secici = within(tablo()).getAllByRole("combobox")[0];
    expect(secici).toBeDisabled();
    expect(secici).toHaveAttribute("title", "Senaryo kilitli");
    expect(screen.getByRole("link", { name: /Teklif Kapak indir/ })).toBeInTheDocument();
    expect(istekler.durumlar).toHaveLength(0);
  });

  it("senaryo geneli tek istekle teklif turlarını listeler", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    expect(within(tablo()).getAllByRole("row")).toHaveLength(1 + 3);
    expect(within(tablo()).getAllByText("45,76 TL").length).toBeGreaterThan(0);
    expect(within(tablo()).getByText("25,0 %")).toBeInTheDocument();
    expect(within(tablo()).getAllByText("21.10.2026").length).toBeGreaterThan(0);
    // Ürün başına fan-out yok: yalnızca bir liste isteği, senaryo ve sayfa parametreleriyle.
    expect(istekler.liste).toHaveLength(1);
    expect(istekler.liste[0]).toMatchObject({ senaryo: "1", sayfa: "1" });
    expect(istekler.liste[0]).not.toHaveProperty("durum");
    expect(istekler.liste[0]).not.toHaveProperty("musteri");
  });

  it("durum ve müşteri süzmesi sunucuya sorgu parametresi olarak gider", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    await userEvent.selectOptions(screen.getByLabelText("Durum"), "kabul");
    await waitFor(() => expect(within(tablo()).getAllByRole("row")).toHaveLength(2));
    expect(within(tablo()).getByText("Başka Müşteri")).toBeInTheDocument();
    expect(istekler.liste[istekler.liste.length - 1]).toMatchObject({ senaryo: "1", durum: "kabul", sayfa: "1" });
    await userEvent.selectOptions(screen.getByLabelText("Durum"), "");
    await userEvent.type(screen.getByLabelText("Müşteri ara"), "örnek");
    await waitFor(() => expect(within(tablo()).getAllByRole("row")).toHaveLength(3));
    expect(within(tablo()).queryByText("Başka Müşteri")).not.toBeInTheDocument();
    const son = istekler.liste[istekler.liste.length - 1];
    expect(son).toMatchObject({ musteri: "örnek" });
    expect(son).not.toHaveProperty("durum");
  });

  it("sayfalama: boyut ve sayfa sunucuya gider", async () => {
    const cok = Array.from({ length: 120 }, (_, i) => ({
      ...senaryoTeklifleri[0],
      teklif_id: 100 + i,
      urun_ad: `Ürün ${i}`,
    }));
    sunucu.use(...tekliflerIsleyicileri(istekler, cok));
    kur();
    await within(await listeHazir()).findByText("Ürün 0");
    expect(istekler.liste[0]).toMatchObject({ sayfa: "1", boyut: "50" });
    expect(screen.getByText("Sayfa 1 / 3")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sonraki" }));
    await within(tablo()).findByText("Ürün 50");
    expect(istekler.liste[istekler.liste.length - 1]).toMatchObject({ sayfa: "2", boyut: "50" });
    expect(screen.getByText("Sayfa 2 / 3")).toBeInTheDocument();
    expect(screen.queryByText(/ilk 100 ürün/i)).not.toBeInTheDocument();
  });

  it("M2: senaryo değişince sayfa 1'e döner", async () => {
    const cok = Array.from({ length: 120 }, (_, i) => ({ ...senaryoTeklifleri[0], teklif_id: 100 + i, urun_ad: `Ürün ${i}` }));
    sunucu.use(...tekliflerIsleyicileri(istekler, cok));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/teklifler?senaryo=1"]}>
          <SenaryoSaglayici>
            <SenaryoSecici />
            <Teklifler />
          </SenaryoSaglayici>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await within(await listeHazir()).findByText("Ürün 0");
    await userEvent.click(screen.getByRole("button", { name: "Sonraki" }));
    await screen.findByText("Sayfa 2 / 3");
    await userEvent.selectOptions(screen.getByLabelText("Senaryo"), "2");
    await screen.findByText("Sayfa 1 / 3");
    await waitFor(() => expect(istekler.liste[istekler.liste.length - 1]).toMatchObject({ senaryo: "2", sayfa: "1" }));
  });

  it("Teklif Kapak indir bağlantısı seçili senaryoya göre", async () => {
    kur();
    const b = await screen.findByRole("link", { name: /Teklif Kapak indir/ });
    expect(b).toHaveAttribute("href", "/api/v1/disa-aktar/teklif-kapak.xlsx?senaryo=1");
    expect(b).toHaveAttribute("download");
  });

  it("senaryo yokken Teklif Kapak indir pasif", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: [], toplam: 0 })));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/teklifler"]}>
          <SenaryoSaglayici>
            <Teklifler />
          </SenaryoSaglayici>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const d = await screen.findByRole("button", { name: /Teklif Kapak indir/ });
    expect(d).toBeDisabled();
    expect(screen.queryByRole("link", { name: /Teklif Kapak indir/ })).not.toBeInTheDocument();
  });

  it("satıra tıklayınca kayıtlı hesap görünümüne gider", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    await userEvent.click(within(tablo()).getAllByText("Biber Turşusu 370 ml")[0]);
    expect(await screen.findByTestId("yer")).toHaveTextContent("/hesaplar/7");
  });

  it("satırdaki durum seçimi PATCH gönderir ve listeyi yeniler", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    const sec = within(tablo()).getByLabelText("Durum — URUN-002 Tur 1");
    expect(sec).toHaveValue("kabul");
    const onceki = istekler.liste.length;
    await userEvent.selectOptions(sec, "red");
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(istekler.durumlar).toEqual([{ id: "3", govde: { durum: "red" } }]));
    await waitFor(() => expect(istekler.liste.length).toBeGreaterThan(onceki));
    await waitFor(() => expect(within(tablo()).getByLabelText("Durum — URUN-002 Tur 1")).toHaveValue("red"));
    // Durum seçimi satır gezinmesini tetiklemez.
    expect(screen.queryByTestId("yer")).not.toBeInTheDocument();
  });

  it("satırdaki Sil onay sorar; onaylanınca DELETE gider, satır gezinmesi tetiklenmez", async () => {
    const silinen: string[] = [];
    const nedenler: (string | null)[] = [];
    sunucu.use(
      http.delete("*/api/v1/teklifler/:id", ({ params, request }) => {
        silinen.push(params.id as string);
        nedenler.push(new URL(request.url).searchParams.get("neden"));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    await userEvent.click(within(tablo()).getByRole("button", { name: "Sil — URUN-001 Tur 2" }));
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("URUN-001 Tur 2 silinecek");
    await userEvent.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(silinen).toHaveLength(0);
    await userEvent.click(within(tablo()).getByRole("button", { name: "Sil — URUN-001 Tur 2" }));
    const onay2 = await screen.findByRole("dialog");
    // D7: neden boşken onay pasif, eski pencerede yazılan neden yeni açılışta temizlenir
    expect(within(onay2).getByRole("button", { name: "Sil" })).toBeDisabled();
    expect(within(onay2).getByText("Neden girin")).toBeInTheDocument();
    await userEvent.type(within(onay2).getByLabelText("Neden (zorunlu)"), "Yanlış tur açıldı");
    await userEvent.click(within(onay2).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(silinen).toEqual(["2"]));
    expect(nedenler).toEqual(["Yanlış tur açıldı"]);
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.queryByTestId("yer")).not.toBeInTheDocument();
  });

  it("kabul edilmiş teklifin Sil düğmesi pasif; ipucu nedenini yazar", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    const sil = within(tablo()).getByRole("button", { name: "Sil — URUN-002 Tur 1" });
    expect(sil).toBeDisabled();
    expect(sil).toHaveAttribute("title", "Kabul edilmiş teklif silinemez; önce durumunu değiştirin.");
    expect(sil.parentElement).toHaveAttribute("title", "Kabul edilmiş teklif silinemez; önce durumunu değiştirin.");
    expect(within(tablo()).getByRole("button", { name: "Sil — URUN-001 Tur 1" })).toBeEnabled();
  });

  it("I6: kabul/red için onay ister; vazgeçilirse PATCH gitmez; diğer durumlar onaysız değişir", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    const sec = within(tablo()).getByLabelText("Durum — URUN-001 Tur 1");
    await userEvent.selectOptions(sec, "kabul");
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("Teklif durumu Kabul olarak değiştirilecek");
    await userEvent.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(istekler.durumlar).toHaveLength(0);
    expect(sec).toHaveValue("taslak");
    await userEvent.selectOptions(sec, "gonderildi");
    await waitFor(() => expect(istekler.durumlar).toEqual([{ id: "1", govde: { durum: "gonderildi" } }]));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("I6: durum güncellenirken seçim kapalıdır; hata satırda role=alert ile gösterilir", async () => {
    let birak: () => void = () => {};
    const bekle = new Promise<void>((r) => (birak = r));
    sunucu.use(
      http.patch("*/api/v1/teklifler/:id/durum", async () => {
        await bekle;
        return HttpResponse.json({ hata: "dogrulama", mesaj: "Durum değiştirilemedi", alanlar: { durum: "geçersiz" } }, { status: 422 });
      }),
    );
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    const sec = within(tablo()).getByLabelText("Durum — URUN-001 Tur 1");
    await userEvent.selectOptions(sec, "gonderildi");
    await waitFor(() => expect(sec).toBeDisabled());
    birak();
    expect(await screen.findByRole("alert")).toHaveTextContent("Durum değiştirilemedi");
    expect(screen.getByRole("alert")).not.toHaveTextContent("durum: geçersiz");
    await waitFor(() => expect(sec).toBeEnabled());
  });

  it("M6: yazdırma özeti yalnızca bu sayfayı kapsadığını belirtir", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    expect(within(screen.getByRole("region", { name: "Teklif özeti" })).getByText(/yalnızca bu sayfa/i)).toBeInTheDocument();
  });

  it("Yazdır teklif özetini hazırlar ve yazdırma penceresini açar", async () => {
    const yazdir = vi.fn();
    vi.stubGlobal("print", yazdir);
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    await userEvent.click(screen.getByRole("button", { name: "Yazdır" }));
    expect(yazdir).toHaveBeenCalledTimes(1);
    const ozet = screen.getByRole("region", { name: "Teklif özeti" });
    expect(within(ozet).getByText("Başka Müşteri")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("boş listede 'Ürün seç' bağlantısı seçili senaryoyla ürün seçiciye götürür", async () => {
    sunucu.use(...tekliflerIsleyicileri(istekler, []));
    kur();
    const bolum = await listeHazir();
    // Senaryo listesi yüklenince bağlantı seçili senaryoyu taşır.
    await waitFor(() => expect(within(bolum).getByRole("link", { name: "Ürün seç" })).toHaveAttribute("href", "/urunler?senaryo=1"));
    expect(bolum).toHaveTextContent("Bu senaryoda teklif yok");
  });

  it("dolu listede 'Ürün seç' bağlantısı yoktur", async () => {
    kur();
    await within(await listeHazir()).findByText("Başka Müşteri");
    expect(screen.queryByRole("link", { name: "Ürün seç" })).not.toBeInTheDocument();
  });

  it("liste hata verirse uyarı gösterir", async () => {
    sunucu.use(
      http.get("*/api/v1/teklifler", () =>
        HttpResponse.json({ hata: "sunucu", mesaj: "Teklifler okunamadı", alanlar: {} }, { status: 500 }),
      ),
    );
    kur();
    expect(await screen.findByRole("alert")).toHaveTextContent("Teklifler okunamadı");
  });
});
