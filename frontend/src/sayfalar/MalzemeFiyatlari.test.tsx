import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, onTestFinished } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { dogrulamaHatasi } from "@/test/msw/isleyiciler";
import { ayarlarIsleyicileri, yeniKayit, type YazimKaydi } from "@/test/msw/isleyiciler-ayarlar";
import { kurSayfa } from "@/test/kur-ayarlar";
import { bugunIso } from "@/yardimcilar/tarih";
import { MemoryRouter, useLocation } from "react-router-dom";
import MalzemeFiyatlari from "./MalzemeFiyatlari";

/** Testte URL arama dizesini görünür kılar. */
function KonumGoster() {
  return <span data-testid="konum-arama">{useLocation().search}</span>;
}

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let kayit: YazimKaydi;
beforeEach(() => {
  localStorage.clear();
  kayit = yeniKayit();
  sunucu.use(...ayarlarIsleyicileri(kayit));
});

describe("MalzemeFiyatlari", () => {
  it("adresteki ?fiyatsiz=1 (Genel Bakış kartı) süzgeci açık başlatır ve fiyatsiz=true ile sorgular", async () => {
    const istekler: string[] = [];
    sunucu.use(
      http.get("*/api/v1/malzemeler", ({ request }) => {
        istekler.push(new URL(request.url).search);
      }),
    );
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/fiyatlar?senaryo=1&fiyatsiz=1"]}>
          <SenaryoSaglayici>
            <MalzemeFiyatlari />
          </SenaryoSaglayici>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(istekler.some((q) => q.includes("fiyatsiz=true"))).toBe(true));
    expect(istekler.every((q) => q.includes("fiyatsiz=true"))).toBe(true);
  });

  it("malzemeleri listeler", async () => {
    kurSayfa(<MalzemeFiyatlari />);
    expect(await screen.findByText("Pet Şişe 500 ml")).toBeInTheDocument();
    expect(screen.getByText("5,9000 TL")).toBeInTheDocument();
    expect(screen.queryByText("M-099")).not.toBeInTheDocument();
  });

  it("Geçerlilik ve Kayıt kaynağı sütunlarını gösterir; boşsa —", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    const tablo = await screen.findByRole("table");
    await screen.findByText("Pet Şişe 500 ml");
    const basliklar = within(tablo)
      .getAllByRole("columnheader")
      .map((h) => h.textContent ?? "");
    const g = basliklar.findIndex((b) => b.startsWith("Geçerlilik"));
    const k = basliklar.findIndex((b) => b.startsWith("Kayıt kaynağı"));
    expect(g).toBeGreaterThan(-1);
    expect(k).toBeGreaterThan(-1);
    const dolu = (screen.getByText("Pet Şişe 500 ml").closest("tr") as HTMLElement).querySelectorAll("td");
    expect(dolu[g]).toHaveTextContent("01.09.2026");
    expect(dolu[k]).toHaveTextContent(/İçe aktarma/);
    const bos = (screen.getByText("Kapak 38 mm").closest("tr") as HTMLElement).querySelectorAll("td");
    expect(bos[g]).toHaveTextContent("—");
    expect(bos[k]).toHaveTextContent("—");
    expect(u).toBeDefined();
  });

  it("G2: Kaynak sütunu Z/S yerine Ziraat / Satın alma yazar ve açıklama tooltip'i taşır", async () => {
    kurSayfa(<MalzemeFiyatlari />);
    const tablo = await screen.findByRole("table");
    await screen.findByText("Pet Şişe 500 ml");
    const basliklar = within(tablo)
      .getAllByRole("columnheader")
      .map((h) => (h.textContent ?? "").trim());
    expect(basliklar).not.toContain("Z/S");
    const k = basliklar.indexOf("Kaynak");
    expect(k).toBeGreaterThan(-1);
    const baslik = within(tablo).getAllByRole("columnheader")[k];
    expect(baslik.querySelector("[title]")?.getAttribute("title") ?? baslik.getAttribute("title")).toMatch(
      /Ziraat: enflasyon uygulanmaz · Satın alma: TL fiyata enflasyon, dövize kur/,
    );
    const pet = (screen.getByText("Pet Şişe 500 ml").closest("tr") as HTMLElement).querySelectorAll("td");
    const kapak = (screen.getByText("Kapak 38 mm").closest("tr") as HTMLElement).querySelectorAll("td");
    expect(pet[k]).toHaveTextContent("Satın alma");
    expect(kapak[k]).toHaveTextContent("Ziraat");
  });

  it("G2: İlk bütçe ve Revize sütunları; revize edilende rozet, diğerinde —", async () => {
    kurSayfa(<MalzemeFiyatlari />);
    const tablo = await screen.findByRole("table");
    await screen.findByText("Pet Şişe 500 ml");
    const basliklar = within(tablo)
      .getAllByRole("columnheader")
      .map((h) => (h.textContent ?? "").trim());
    const i = basliklar.indexOf("İlk bütçe");
    const r = basliklar.indexOf("Revize");
    const g = basliklar.indexOf("Geçerli fiyat");
    expect(i).toBeGreaterThan(-1);
    expect(r).toBeGreaterThan(-1);
    expect(i).toBeLessThan(g);
    const pet = (screen.getByText("Pet Şişe 500 ml").closest("tr") as HTMLElement).querySelectorAll("td");
    expect(pet[i]).toHaveTextContent("5,2000 TL");
    expect(pet[g]).toHaveTextContent("5,9000 TL");
    expect(within(pet[r] as HTMLElement).getByText("Revize")).toBeInTheDocument();
    const kapak = (screen.getByText("Kapak 38 mm").closest("tr") as HTMLElement).querySelectorAll("td");
    expect(kapak[i]).toHaveTextContent("—");
    expect(kapak[r]).toHaveTextContent("—");
  });

  it("G2: 'Yalnız revize edilenler' süzgeci revize=true ile sorgular ve URL'ye revize=1 yazar", async () => {
    const u = userEvent.setup();
    const istekler: string[] = [];
    sunucu.use(
      http.get("*/api/v1/malzemeler", ({ request }) => {
        istekler.push(new URL(request.url).search); // yanıt dönmez: varsayılan işleyiciye düşer
      }),
    );
    kurSayfa(
      <>
        <MalzemeFiyatlari />
        <KonumGoster />
      </>,
    );
    await screen.findByText("Pet Şişe 500 ml");
    expect(screen.getByText("Kapak 38 mm")).toBeInTheDocument();
    await u.click(screen.getByRole("checkbox", { name: /Yalnız revize edilenler/ }));
    await waitFor(() => expect(screen.queryByText("Kapak 38 mm")).not.toBeInTheDocument());
    expect(screen.getByText("Pet Şişe 500 ml")).toBeInTheDocument();
    expect(istekler.some((q) => q.includes("revize=true"))).toBe(true);
    expect(screen.getByTestId("konum-arama")).toHaveTextContent("revize=1");
    expect(screen.getByTestId("konum-arama")).toHaveTextContent("senaryo=1");
    await u.click(screen.getByRole("checkbox", { name: /Yalnız revize edilenler/ }));
    await screen.findByText("Kapak 38 mm");
    expect(screen.getByTestId("konum-arama")).not.toHaveTextContent("revize");
  });

  it("fiyatsız filtresi kart_yok satırını 'Kart yok' rozetiyle gösterir", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await screen.findByText("Pet Şişe 500 ml");
    await u.click(screen.getByRole("checkbox", { name: /fiyatsız/i }));
    const satir = (await screen.findByText("M-099")).closest("tr") as HTMLElement;
    expect(within(satir).getByText("Kart yok")).toBeInTheDocument();
    expect(within(satir).getByRole("button", { name: /Fiyat değiştir M-099/ })).toBeDisabled();
  });

  it("neden boşsa fiyat gönderilmez", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat değiştir M-001" }));
    const f = await screen.findByLabelText("Yeni fiyat");
    await u.clear(f);
    await u.type(f, "6,5");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Neden zorunlu")).toBeInTheDocument();
    expect(kayit.fiyat).toHaveLength(0);
  });

  it("fiyat ekler: bugünün tarihi, neden, özet; sonra başarı mesajı", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat değiştir M-001" }));
    const f = await screen.findByLabelText("Yeni fiyat");
    expect(screen.getByLabelText("Geçerlilik tarihi")).toHaveValue(bugunIso());
    await u.clear(f);
    await u.type(f, "6,5");
    expect(screen.getByText(/M-001.*6,5000 TL/)).toBeInTheDocument();
    await u.type(screen.getByLabelText("Neden"), "Yeni liste");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit.fiyat).toHaveLength(1));
    expect(kayit.fiyat[0]).toEqual({
      kod: "M-001",
      senaryo: "1",
      govde: { fiyat: "6.5", gecerlilik_basi: bugunIso(), neden: "Yeni liste", para_birimi: "TL", onay: false },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/M-001 fiyatı kaydedildi/);
  });

  it("geçmişte 'Geri al' eski fiyatı yeni kayıt olarak gönderir", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Geçmiş M-001" }));
    const li = (await screen.findByText("Sezon başı")).closest("li") as HTMLElement;
    await u.click(within(li).getByRole("button", { name: /Geri al/ }));
    expect(kayit.fiyat).toHaveLength(0);
    await u.click(await screen.findByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(kayit.fiyat).toHaveLength(1));
    expect(kayit.fiyat[0].govde).toMatchObject({
      fiyat: "5.2",
      gecerlilik_basi: bugunIso(),
      neden: "Geri alındı: 01.01.2026 değeri",
    });
  });

  it("fiyat listesi yükleme: önizleme sekmeleri ve uygula", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat listesi yükle" }));
    const dosya = new File(["x"], "liste.xlsx");
    await u.upload(await screen.findByLabelText("Fiyat listesi dosyası"), dosya);
    await u.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByRole("tab", { name: /Değişen \(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Yeni \(1\)/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Aynı \(4\)/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Hatalı \(0\)/ })).toBeInTheDocument();
    expect(screen.queryByText(/Revize fiyat/)).not.toBeInTheDocument(); // revize yoksa satır çıkmaz
    await u.click(screen.getByRole("button", { name: "Uygula" }));
    expect(await screen.findByText("Neden zorunlu")).toBeInTheDocument();
    await u.type(screen.getByLabelText("Neden"), "Eylül listesi");
    await u.click(screen.getByRole("button", { name: "Uygula" }));
    expect(await screen.findByText(/1 fiyat yazıldı/)).toBeInTheDocument();
  });

  it("I3: arama kod ve ada bakar; sunucuya gider (sayfalamadan önce süzülür, başka sayfadaki malzeme de bulunur)", async () => {
    const u = userEvent.setup();
    const aramalar: (string | null)[] = [];
    sunucu.events.on("request:start", ({ request }) => {
      if (request.url.includes("/api/v1/malzemeler?")) aramalar.push(new URL(request.url).searchParams.get("arama"));
    });
    onTestFinished(() => sunucu.events.removeAllListeners());
    kurSayfa(<MalzemeFiyatlari />);
    await screen.findByText("Pet Şişe 500 ml");
    const ara = screen.getByLabelText("Malzeme ara (kod ya da ad)");
    await u.type(ara, "pet şişe");
    expect(screen.getByText("Pet Şişe 500 ml")).toBeInTheDocument();
    await u.clear(ara);
    await u.type(ara, "M-001");
    expect(screen.getByText("Pet Şişe 500 ml")).toBeInTheDocument();
    await u.clear(ara);
    await u.type(ara, "yoktur-boyle-bir-sey");
    await waitFor(() => expect(screen.queryByText("Pet Şişe 500 ml")).not.toBeInTheDocument());
    await waitFor(() => expect(aramalar).toContain("yoktur-boyle-bir-sey"));
  });

  it("G3: önizlemede revize (I sütunu) listesi 'kod · ilk → revize' ve sayısıyla görünür", async () => {
    sunucu.use(
      http.post("*/api/v1/import/fiyat-listesi", () =>
        HttpResponse.json({
          yeni: [{ kod: "M-050", yeni: "3.5" }],
          degisen: [{ kod: "M-001", eski: "5.9", yeni: "6.4" }],
          ayni: 4,
          hatali: [],
          revize: [
            { kod: "M-001", ilk: "5.9", revize: "6.4" },
            { kod: "M-050", ilk: null, revize: "3.5" },
          ],
        }),
      ),
    );
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat listesi yükle" }));
    await u.upload(await screen.findByLabelText("Fiyat listesi dosyası"), new File(["x"], "liste.xlsx"));
    await u.click(screen.getByRole("button", { name: "Önizle" }));
    const bolum = await screen.findByRole("region", { name: "Revize fiyatlar" });
    expect(within(bolum).getByText("Revize fiyat (S.ALMA BF I): 2")).toBeInTheDocument();
    const satirlar = within(bolum)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(satirlar).toEqual(["M-001 · 5,9000 → 6,4000", "M-050 · — → 3,5000"]);
    expect(bolum).not.toHaveTextContent("TL");
  });

  it("fiyat listesi önizlemesi 4 ondalıkla ve para birimi olmadan gösterilir", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat listesi yükle" }));
    await u.upload(await screen.findByLabelText("Fiyat listesi dosyası"), new File(["x"], "liste.xlsx"));
    await u.click(screen.getByRole("button", { name: "Önizle" }));
    const panel = await screen.findByRole("tabpanel");
    expect(within(panel).getByText("5,9000")).toBeInTheDocument();
    expect(within(panel).getByText("6,0000")).toBeInTheDocument();
    expect(panel).not.toHaveTextContent("TL");
  });

  it("önizlemeden sonra geçerlilik tarihi değişirse önizleme temizlenir; yeniden önizlemeden Uygula çıkmaz", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat listesi yükle" }));
    await u.upload(await screen.findByLabelText("Fiyat listesi dosyası"), new File(["x"], "liste.xlsx"));
    await u.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByRole("tab", { name: /Değişen \(1\)/ })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Geçerlilik tarihi"), { target: { value: "2026-01-15" } });
    await waitFor(() => expect(screen.queryByRole("tab", { name: /Değişen/ })).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Uygula" })).not.toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Önizle" }));
    expect(await screen.findByRole("button", { name: "Uygula" })).toBeInTheDocument();
  });

  it("negatif fiyat gönderilmez", async () => {
    const u = userEvent.setup();
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Fiyat değiştir M-001" }));
    const f = await screen.findByLabelText("Yeni fiyat");
    await u.clear(f);
    await u.type(f, "-1");
    await u.type(screen.getByLabelText("Neden"), "Deneme");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText(/negatif olamaz/)).toBeInTheDocument();
    expect(kayit.fiyat).toHaveLength(0);
  });

  it("geri al onay ister; sunucu hatası role=alert ile gösterilir", async () => {
    const u = userEvent.setup();
    sunucu.use(http.post("*/api/v1/malzemeler/:kod/fiyatlar", () => dogrulamaHatasi()));
    kurSayfa(<MalzemeFiyatlari />);
    await u.click(await screen.findByRole("button", { name: "Geçmiş M-001" }));
    const li = (await screen.findByText("Sezon başı")).closest("li") as HTMLElement;
    await u.click(within(li).getByRole("button", { name: /Geri al/ }));
    expect(await screen.findByText(/01\.01\.2026 tarihli 5,2000 TL değeri bugünden itibaren geçerli olacak/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Onayla" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/geçersiz/);
  });
});
