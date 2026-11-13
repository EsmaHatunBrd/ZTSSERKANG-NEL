import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import type { GirisKullanicisi, Rol } from "@/api/sorgular/kimlik";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import { senaryolar } from "@/test/fikstur/urunler";
import { GirdiHucresi } from "@/sayfalar/urun/GirdiHucresi";
import {
  DUZENLEME_ANAHTARI,
  DUZENLEME_SURESI_MS,
  DuzenlemeKilidi,
  DuzenlemeKilidiSaglayici,
  duzenlemeyiKilitle,
  kalanMetni,
  useDuzenlemeKilidi,
  useYazmaKilidi,
} from "./DuzenlemeKilidi";
import { OturumSaglayici } from "./GirisKapisi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  sunucu.resetHandlers();
  vi.useRealTimers();
});
afterAll(() => sunucu.close());

// Test kurulumu kilidi varsayılan AÇIK başlatır; bu dosya gerçek varsayılanı (kilitli) sınar.
beforeEach(() => {
  duzenlemeyiKilitle();
  sessionStorage.removeItem(DUZENLEME_ANAHTARI);
});

/** Kilidin sayfalara verdiği bayrağı ve bir düzenleme hücresini gösteren deneme içeriği. */
function Deneme() {
  const { kilitli, neden } = useYazmaKilidi();
  return (
    <>
      <DuzenlemeKilidi />
      <output data-testid="bayrak">{kilitli ? `kilitli:${neden}` : "acik"}</output>
      <GirdiHucresi etiket="Miktar" deger="1" onMetin={() => {}} />
    </>
  );
}

function acIstegiYakala() {
  const govdeler: unknown[] = [];
  sunucu.use(
    http.post("*/api/v1/duzenleme-kilidi/ac", async ({ request }) => {
      govdeler.push(await request.json());
      return HttpResponse.json({ kayit_id: 1, sayfa: "/", senaryo_id: 1, kullanici: "Test Kullanıcı" }, { status: 201 });
    }),
  );
  return govdeler;
}

const kullanici = (rol: Rol) =>
  ({ id: 1, kullanici_adi: "k", ad: "K", rol, aktif: true, sifre_degismeli: false }) as unknown as GirisKullanicisi;

describe("Düzenleme kilidi şeridi", () => {
  it("varsayılan kilitlidir: şerit nedeni söyler, hücre devre dışıdır", async () => {
    kurSayfa(<Deneme />);
    const serit = await screen.findByRole("group", { name: "Düzenleme kilidi" });
    expect(serit).toHaveAttribute("data-durum", "kilitli");
    expect(serit).toHaveTextContent("Düzenleme kilitli. Değişiklik yapmak için kilidi açın.");
    expect(screen.getByRole("button", { name: "Düzenlemeyi aç" })).toBeEnabled();
    expect(screen.getByTestId("bayrak")).toHaveTextContent("kilitli:Düzenleme kilitli");
    const hucre = screen.getByRole("textbox", { name: "Miktar" });
    expect(hucre).toBeDisabled();
    expect(hucre).toHaveAttribute("title", "Düzenleme kilitli");
  });

  it("Düzenlemeyi aç: sunucuya bildirilir, şerit açık olur, hücre etkinleşir; Kilitle geri kapatır", async () => {
    const govdeler = acIstegiYakala();
    kurSayfa(<Deneme />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Düzenlemeyi aç" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    const serit = await screen.findByRole("group", { name: "Düzenleme kilidi" });
    expect(serit).toHaveAttribute("data-durum", "acik");
    expect(serit).toHaveTextContent("Düzenleme açık");
    expect(serit).toHaveTextContent("15 dk kaldı");
    await waitFor(() => expect(govdeler).toHaveLength(1));
    expect(govdeler[0]).toMatchObject({ sayfa: "/" });
    expect(screen.getByTestId("bayrak")).toHaveTextContent("acik");
    expect(screen.getByRole("textbox", { name: "Miktar" })).toBeEnabled();
    expect(Number(sessionStorage.getItem(DUZENLEME_ANAHTARI))).toBeGreaterThan(Date.now());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Kilitle" }));
    expect(screen.getByRole("group", { name: "Düzenleme kilidi" })).toHaveAttribute("data-durum", "kilitli");
    expect(screen.getByRole("textbox", { name: "Miktar" })).toBeDisabled();
    expect(sessionStorage.getItem(DUZENLEME_ANAHTARI)).toBeNull();
  });

  it("bildirim ucu başarısız olursa kilit yine açılır ve uyarı gösterilir", async () => {
    sunucu.use(http.post("*/api/v1/duzenleme-kilidi/ac", () => HttpResponse.error()));
    kurSayfa(<Deneme />);
    await userEvent.click(await screen.findByRole("button", { name: "Düzenlemeyi aç" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Kilit açıldı ancak bu işlem Değişiklik Günlüğü'ne yazılamadı");
    expect(screen.getByRole("group", { name: "Düzenleme kilidi" })).toHaveAttribute("data-durum", "acik");
    expect(screen.getByRole("textbox", { name: "Miktar" })).toBeEnabled();
  });

  it("izleyici rolünde düğme yoktur ve depoda açık kayıt olsa da kilit açık sayılmaz", () => {
    sessionStorage.setItem(DUZENLEME_ANAHTARI, String(Date.now() + DUZENLEME_SURESI_MS));
    render(
      <MemoryRouter>
        <OturumSaglayici deger={{ girisZorunlu: true, kullanici: kullanici("izleyici") }}>
          <Deneme />
        </OturumSaglayici>
      </MemoryRouter>,
    );
    expect(screen.getByRole("group", { name: "Düzenleme kilidi" })).toHaveTextContent("İzleyici rolüyle değişiklik yapılamaz");
    expect(screen.queryByRole("button", { name: "Düzenlemeyi aç" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kilitle" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Miktar" })).toBeDisabled();
  });

  it("satın alma rolü kilidi açabilir", () => {
    render(
      <MemoryRouter>
        <OturumSaglayici deger={{ girisZorunlu: true, kullanici: kullanici("satin_alma") }}>
          <Deneme />
        </OturumSaglayici>
      </MemoryRouter>,
    );
    expect(screen.getByRole("button", { name: "Düzenlemeyi aç" })).toBeEnabled();
  });

  it("senaryo kilitliyken açılamaz ve nedenini söyler", async () => {
    const kilitli = senaryolar.map((s) => (s.id === 1 ? { ...s, kilitli: true } : s));
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: kilitli, toplam: kilitli.length })));
    kurSayfa(<Deneme />);
    expect(await screen.findByText("Düzenleme kilitli. Bu senaryo kilitli olduğu için düzenleme açılamaz.")).toBeInTheDocument();
    const dugme = screen.getByRole("button", { name: "Düzenlemeyi aç" });
    expect(dugme).toBeDisabled();
    expect(dugme).toHaveAttribute("title", "Senaryo kilitli: düzenleme açılamaz");
    expect(screen.getByTestId("bayrak")).toHaveTextContent("kilitli:Senaryo kilitli");
  });
});

describe("Düzenleme kilidi süresi (sahte zamanlayıcı)", () => {
  function Yalin() {
    const { acik, sureDoldu } = useDuzenlemeKilidi();
    return (
      <DuzenlemeKilidiSaglayici>
        <DuzenlemeKilidi />
        <output data-testid="durum">{acik ? "acik" : sureDoldu ? "doldu" : "kilitli"}</output>
        <input aria-label="Serbest alan" />
        <GirdiHucresi etiket="Miktar" deger="1" onMetin={() => {}} />
      </DuzenlemeKilidiSaglayici>
    );
  }
  const kur = () =>
    render(
      <MemoryRouter>
        <Yalin />
      </MemoryRouter>,
    );

  it("15 dakika işlem yapılmazsa kendiliğinden kilitlenir; şerit süre dolduğunu söyler, sonra yeniden açılabilir", async () => {
    acIstegiYakala();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
    kur();
    fireEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    expect(screen.getByTestId("durum")).toHaveTextContent("acik");
    act(() => {
      vi.advanceTimersByTime(DUZENLEME_SURESI_MS - 30_000);
    });
    expect(screen.getByTestId("durum")).toHaveTextContent("acik");
    expect(screen.getByRole("group", { name: "Düzenleme kilidi" })).toHaveTextContent("30 sn kaldı");
    act(() => {
      vi.advanceTimersByTime(31_000);
    });
    expect(screen.getByTestId("durum")).toHaveTextContent("doldu");
    expect(screen.getByRole("group", { name: "Düzenleme kilidi" })).toHaveTextContent("Süre doldu; kaydetmek için kilidi yeniden açın.");
    expect(screen.getByRole("textbox", { name: "Miktar" })).toBeDisabled();
    expect(sessionStorage.getItem(DUZENLEME_ANAHTARI)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    expect(screen.getByTestId("durum")).toHaveTextContent("acik");
  });

  it("kullanıcı bir alana yazdıkça süre yenilenir", () => {
    acIstegiYakala();
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"] });
    kur();
    fireEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    act(() => {
      vi.advanceTimersByTime(DUZENLEME_SURESI_MS - 60_000);
    });
    fireEvent.input(screen.getByRole("textbox", { name: "Serbest alan" }), { target: { value: "a" } });
    act(() => {
      vi.advanceTimersByTime(DUZENLEME_SURESI_MS - 60_000);
    });
    // İlk açılıştan 28 dakika sonra: yazma süreyi yenilediği için hâlâ açık.
    expect(screen.getByTestId("durum")).toHaveTextContent("acik");
    act(() => {
      vi.advanceTimersByTime(61_000);
    });
    expect(screen.getByTestId("durum")).toHaveTextContent("doldu");
  });

  it("veri yazan başarılı istek süreyi yeniler; okuma isteği yenilemez", async () => {
    sunucu.use(
      http.put("*/api/v1/deneme-yaz", () => HttpResponse.json({})),
      http.get("*/api/v1/deneme-oku", () => HttpResponse.json({})),
    );
    const { api } = await import("@/api/istemci");
    const gevsek = api as unknown as Record<"GET" | "PUT", (yol: string, s?: object) => Promise<unknown>>;
    const ilk = Date.now() + 1000;
    sessionStorage.setItem(DUZENLEME_ANAHTARI, String(ilk));
    await gevsek.GET("/api/v1/deneme-oku");
    expect(Number(sessionStorage.getItem(DUZENLEME_ANAHTARI))).toBe(ilk);
    await gevsek.PUT("/api/v1/deneme-yaz", { body: {} });
    expect(Number(sessionStorage.getItem(DUZENLEME_ANAHTARI))).toBeGreaterThan(ilk + DUZENLEME_SURESI_MS - 5000);
  });

  it("giriş ve çıkış kilidi kapatır (yeniden girişte kilitli başlar)", async () => {
    sunucu.use(http.post("*/api/v1/kimlik/cikis", () => HttpResponse.json({})));
    const { api } = await import("@/api/istemci");
    sessionStorage.setItem(DUZENLEME_ANAHTARI, String(Date.now() + DUZENLEME_SURESI_MS));
    await (api as unknown as { POST: (yol: string) => Promise<unknown> }).POST("/api/v1/kimlik/cikis");
    expect(sessionStorage.getItem(DUZENLEME_ANAHTARI)).toBeNull();
  });

  it("kalan süre metni: dakikadan uzunsa dakika, son dakikada saniye", () => {
    expect(kalanMetni(900)).toBe("15 dk kaldı");
    expect(kalanMetni(61)).toBe("2 dk kaldı");
    expect(kalanMetni(60)).toBe("60 sn kaldı");
    expect(kalanMetni(5)).toBe("5 sn kaldı");
  });
});
