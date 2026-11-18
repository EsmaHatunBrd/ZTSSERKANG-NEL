import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import type { ListeCalismasi as ListeVerisi } from "@/api/tipler";
import ListeCalismasi, { puanBicimle } from "./ListeCalismasi";
import { yuvarlamaEtiketi } from "./liste/listeYardimci";

beforeAll(() => {
  globalThis.ResizeObserver = class {
    cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }
    observe(hedef: Element) {
      this.cb(
        [{ target: hedef, contentRect: { width: 600, height: 240 } } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  sunucu.listen({ onUnhandledFrame: "error" });
});
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

/** Sayfayı verilen adresle açar (ör. `?pazar=yurtdisi`). */
function ciz(adres: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[adres]}>
        <SenaryoSaglayici>
          <ListeCalismasi />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

type Pazar = "yurtici" | "yurtdisi";

interface VeriSecenekleri {
  pazar?: Pazar;
  bolen?: string;
  yuvarlama?: string;
  gecmisli?: boolean;
  berrakDisi?: number;
}

function veri({ pazar = "yurtici", bolen, yuvarlama = "0.05", gecmisli = true, berrakDisi = 0 }: VeriSecenekleri = {}): ListeVerisi {
  const varsayilan = pazar === "yurtici" ? "0.63" : "0.90";
  const b = bolen ?? varsayilan;
  const ham = (Number("44.10") / Number(b)).toFixed(4);
  const adim = Number(yuvarlama);
  const yeni = (Math.round(Number(ham) / adim) * adim).toFixed(2);
  return {
    yil: 2026,
    pazar,
    bolen: b,
    bolenler: { yurtici: pazar === "yurtici" ? b : "0.63", yurtdisi: pazar === "yurtdisi" ? b : "0.90" },
    bolen_kayitli: false,
    varsayilan_bolen: varsayilan,
    yuvarlama,
    yuvarlama_kayitli: false,
    varsayilan_yuvarlama: "0.05",
    yuvarlama_secenekleri: ["0.01", "0.05", "0.10", "0.25", "0.50", "1", "5"],
    berrak_disi: berrakDisi,
    ornek_var: gecmisli,
    ozet: gecmisli
      ? { liste_artis_ort: "0.4", maliyet_artis_ort: "0.5", fark: "-0.1", karsilastirilan: 2, urun_sayisi: 2, gerisinde: 1 }
      : { liste_artis_ort: null, maliyet_artis_ort: null, fark: null, karsilastirilan: 0, urun_sayisi: 2, gerisinde: 0 },
    yillar: gecmisli ? [{ yil: 2026, liste_artis_ort: "0.4", maliyet_artis_ort: "0.5", urun_sayisi: 2 }] : [],
    kayitlar: [
      {
        kod: "URUN-001",
        ad: "Biber Turşusu 370 ml",
        hat: "Niko",
        hata: null,
        maliyet_tl: "36.75",
        satis_tl: "44.10",
        yeni_liste: yeni,
        yeni_liste_ham: ham,
        onceki_yil: gecmisli ? 2025 : null,
        onceki_liste: gecmisli ? "50" : null,
        liste_artis: gecmisli ? "0.4" : null,
        maliyet_artis: gecmisli ? "0.5" : null,
        fark: gecmisli ? "-0.1" : null,
        gecmis: gecmisli ? [{ yil: 2025, pazar, liste_fiyati: "50", birim_maliyet: "24.5", bolen: "0.63", ornek: true }] : [],
      },
      {
        kod: "URUN-002",
        ad: "Zeytin Ezmesi 300 ml",
        hat: "Herbort",
        hata: null,
        maliyet_tl: "20",
        satis_tl: "24",
        yeni_liste: "38.10",
        yeni_liste_ham: "38.0952",
        onceki_yil: gecmisli ? 2025 : null,
        onceki_liste: gecmisli ? "27" : null,
        liste_artis: gecmisli ? "0.41" : null,
        maliyet_artis: gecmisli ? "0.3" : null,
        fark: gecmisli ? "0.11" : null,
        gecmis: gecmisli ? [{ yil: 2025, pazar, liste_fiyati: "27", birim_maliyet: null, bolen: null, ornek: true }] : [],
      },
    ],
  };
}

/** İstek adresindeki pazar/bölen/yuvarlama. */
function sorguOku(request: Request) {
  const q = new URL(request.url).searchParams;
  return {
    pazar: (q.get("pazar") ?? "yurtici") as Pazar,
    bolen: q.get("bolen") ?? undefined,
    yuvarlama: q.get("yuvarlama") ?? undefined,
  };
}

describe("Liste Çalışması", () => {
  it("puanBicimle oran farkını puan olarak yazar", () => {
    expect(puanBicimle("-0.1")).toBe("-10,0 puan");
    expect(puanBicimle(null)).toBe("—");
  });

  it("yuvarlama etiketleri", () => {
    expect(yuvarlamaEtiketi("0.05")).toBe("En yakın 0,05 TL");
    expect(yuvarlamaEtiketi("0.10")).toBe("En yakın 0,10 TL");
    expect(yuvarlamaEtiketi("5")).toBe("En yakın 5 TL");
  });

  it("varsayılan bölen, hesap kuralı, örnek veri uyarısı, kartlar; geride kalanlar süzülür", async () => {
    const pazarlar: Pazar[] = [];
    sunucu.use(
      http.get(`${T}/liste-calismasi`, ({ request }) => {
        pazarlar.push(sorguOku(request).pazar);
        return HttpResponse.json(veri());
      }),
    );
    kurSayfa(<ListeCalismasi />);
    expect(await screen.findByDisplayValue("0,63")).toHaveAccessibleName("Yurtiçi böleni");
    expect(pazarlar[0]).toBe("yurtici");
    expect(screen.getByText(/Varsayılan yurtiçi böleni 0,63/)).toBeInTheDocument();
    expect(screen.getByLabelText("Hesap kuralı")).toHaveTextContent(
      "Yalnız Berrak ürünleri · KDV hariç · liste fiyatı = satış fiyatı ÷ bölen, en yakın 0,05 TL'ye yuvarlanır",
    );
    expect(screen.queryByText(/Berrak olmadığı için/)).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Yeni liste fiyatı/ })).toBeInTheDocument();
    expect(screen.getByText("70,00 TL").closest("[title]")).toHaveAttribute("title", "Yuvarlamasız: 70,0000 TL");
    expect(screen.getByRole("note")).toHaveTextContent("Örnek veri");
    expect(screen.getByText("-10,0 puan")).toBeInTheDocument(); // kart
    expect(screen.getByText("-10,0")).toBeInTheDocument(); // ürün satırı (sütun: Fark (puan))
    expect(screen.getByText("Zeytin Ezmesi 300 ml")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Yalnız maliyetin gerisinde kalanlar"));
    expect(screen.queryByText("Zeytin Ezmesi 300 ml")).not.toBeInTheDocument();
    expect(screen.getByText("Biber Turşusu 370 ml")).toBeInTheDocument();
  });

  it("Berrak dışı ürün sayısı notu", async () => {
    sunucu.use(http.get(`${T}/liste-calismasi`, () => HttpResponse.json(veri({ berrakDisi: 12 }))));
    kurSayfa(<ListeCalismasi />);
    expect(await screen.findByText("12 ürün Berrak olmadığı için listede yok.")).toBeInTheDocument();
  });

  it("pazar Yurtdışı seçilince istek pazar=yurtdisi ile gider ve yurtdışı böleni görünür", async () => {
    const pazarlar: Pazar[] = [];
    sunucu.use(
      http.get(`${T}/liste-calismasi`, ({ request }) => {
        const q = sorguOku(request);
        pazarlar.push(q.pazar);
        return HttpResponse.json(veri(q));
      }),
    );
    kurSayfa(<ListeCalismasi />);
    expect(await screen.findByDisplayValue("0,63")).toBeInTheDocument();
    const grup = screen.getByRole("group", { name: "Pazar" });
    expect(within(grup).getByRole("button", { name: "Yurtiçi" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(within(grup).getByRole("button", { name: "Yurtdışı" }));
    await waitFor(() => expect(pazarlar).toContain("yurtdisi"));
    expect(await screen.findByDisplayValue("0,9")).toHaveAccessibleName("Yurtdışı böleni");
    expect(within(grup).getByRole("button", { name: "Yurtdışı" })).toHaveAttribute("aria-pressed", "true");
  });

  it("bölen ve yuvarlama kaydetmeden denenir; kaydet nedenle seçili pazarın bölenini ve yuvarlamayı yazar", async () => {
    const sorgular: ReturnType<typeof sorguOku>[] = [];
    const yazilan: Record<string, unknown> = {};
    sunucu.use(
      http.get(`${T}/liste-calismasi`, ({ request }) => {
        const q = sorguOku(request);
        sorgular.push(q);
        return HttpResponse.json(veri(q));
      }),
      http.post(`${T}/parametreler/:anahtar/degerler`, async ({ request, params }) => {
        yazilan[String(params.anahtar)] = await request.json();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    ciz("/?senaryo=1&pazar=yurtdisi");
    const kutu = await screen.findByDisplayValue("0,9");
    expect(screen.queryByRole("button", { name: "Ayarı kaydet" })).not.toBeInTheDocument();
    await userEvent.clear(kutu);
    await userEvent.type(kutu, "0,85");
    await waitFor(() => expect(sorgular.some((q) => q.bolen === "0.85" && q.pazar === "yurtdisi")).toBe(true), { timeout: 3000 });
    await userEvent.selectOptions(screen.getByLabelText("Yuvarlama"), "En yakın 0,10 TL");
    await waitFor(() => expect(sorgular.some((q) => q.yuvarlama === "0.10" && q.bolen === "0.85")).toBe(true));
    await userEvent.click(await screen.findByRole("button", { name: "Ayarı kaydet" }));
    const d = await screen.findByRole("dialog");
    expect(d).toHaveTextContent("Yurtdışı böleni 0,9 yerine 0,85 olacak.");
    expect(d).toHaveTextContent("Yuvarlama en yakın 0,05 tl yerine en yakın 0,10 tl olacak.");
    await userEvent.type(within(d).getByLabelText("Neden"), "yeni iskonto");
    await userEvent.click(within(d).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(Object.keys(yazilan).sort()).toEqual(["liste_bolen_yurtdisi", "liste_yuvarlama"]));
    expect(yazilan.liste_bolen_yurtdisi).toMatchObject({ deger: "0.85", neden: "yeni iskonto", kapsam_tipi: "genel" });
    expect(yazilan.liste_yuvarlama).toMatchObject({ deger: "0.10", neden: "yeni iskonto", kapsam_tipi: "genel" });
  });

  it("geçmiş çekmecesi seçili pazarla çalışır: örnek satır gerçek olarak kaydedilir, yeni yıl eklenir, silinir", async () => {
    const yazilan: unknown[] = [];
    const silinen: string[] = [];
    sunucu.use(
      http.get(`${T}/liste-calismasi`, ({ request }) => HttpResponse.json(veri(sorguOku(request)))),
      http.put(`${T}/liste-fiyatlari`, async ({ request }) => {
        const g = (await request.json()) as Record<string, unknown>;
        yazilan.push(g);
        return HttpResponse.json({ ...g, ornek: false });
      }),
      http.delete(`${T}/liste-fiyatlari/:kod/:yil`, ({ request, params }) => {
        silinen.push(`${String(params.kod)}/${String(params.yil)}?${new URL(request.url).searchParams.toString()}`);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    ciz("/?senaryo=1&pazar=yurtdisi");
    await userEvent.click(await screen.findByText("Biber Turşusu 370 ml"));
    const cekmece = await screen.findByRole("dialog");
    expect(cekmece).toHaveTextContent("2026 yurtdışı liste fiyatı");
    expect(within(cekmece).getByLabelText("Liste fiyatı 2025")).toHaveValue("50");
    expect(within(cekmece).getByText("Bölen 0,63")).toBeInTheDocument();
    // D7: her yazma işleminde neden zorunlu; boşken düğme pasif ve "Neden girin" ipucu görünür
    const gercek = within(cekmece).getByRole("button", { name: "Gerçek olarak kaydet" });
    expect(gercek).toBeDisabled();
    await userEvent.type(within(cekmece).getByLabelText("Neden (zorunlu) — 2025"), "Eski fiyat listesinden");
    await userEvent.click(gercek);
    await waitFor(() =>
      expect(yazilan[0]).toEqual({
        urun_kodu: "URUN-001",
        yil: 2025,
        pazar: "yurtdisi",
        liste_fiyati: "50",
        birim_maliyet: "24.5",
        neden: "Eski fiyat listesinden",
      }),
    );
    expect(within(cekmece).getByLabelText("Yıl")).toHaveValue("2024");
    await userEvent.type(within(cekmece).getByLabelText("Yeni liste fiyatı"), "35,9");
    const ekle = within(cekmece).getByRole("button", { name: "Ekle" });
    expect(ekle).toBeDisabled();
    expect(within(within(cekmece).getByRole("form", { name: "Yıl ekle" })).getByText("Neden girin")).toBeInTheDocument();
    await userEvent.type(within(cekmece).getByLabelText("Neden (zorunlu)"), "2024 listesi");
    await userEvent.click(ekle);
    await waitFor(() =>
      expect(yazilan[1]).toEqual({
        urun_kodu: "URUN-001",
        yil: 2024,
        pazar: "yurtdisi",
        liste_fiyati: "35.9",
        birim_maliyet: null,
        neden: "2024 listesi",
      }),
    );
    // Sil artık onay penceresi açar; neden girilmeden silmez
    await userEvent.click(within(cekmece).getByRole("button", { name: "Sil" }));
    const onay = await screen.findByRole("dialog", { name: "2025 yurtdışı liste fiyatı silinsin mi?" });
    expect(silinen).toEqual([]);
    expect(within(onay).getByRole("button", { name: "Sil" })).toBeDisabled();
    await userEvent.type(within(onay).getByLabelText("Neden (zorunlu)"), "Hatalı yıl");
    await userEvent.click(within(onay).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(silinen).toEqual(["URUN-001/2025?pazar=yurtdisi&neden=Hatal%C4%B1+y%C4%B1l"]));
  });

  it("geçmiş yoksa örnek veriyle göster düğmesi örnek üretir", async () => {
    let uretildi = false;
    sunucu.use(
      http.get(`${T}/liste-calismasi`, () => HttpResponse.json(veri({ gecmisli: uretildi }))),
      http.post(`${T}/liste-calismasi/ornek`, () => {
        uretildi = true;
        return HttpResponse.json({ yazilan: 6 });
      }),
    );
    kurSayfa(<ListeCalismasi />);
    await userEvent.click(await screen.findByRole("button", { name: "Örnek veriyle göster" }));
    expect(await screen.findByRole("note")).toHaveTextContent("Örnek veri");
  });

  it("düzenleme kilidi: kilitliyken ayar kaydı ve örnek veri üretimi devre dışı, kilit açılınca etkin", async () => {
    sessionStorage.removeItem("fiyat-calismasi.duzenleme-acik-bitis");
    sunucu.use(
      http.get(`${T}/liste-calismasi`, ({ request }) => HttpResponse.json(veri({ ...sorguOku(request), gecmisli: false }))),
      http.post(`${T}/duzenleme-kilidi/ac`, () =>
        HttpResponse.json({ kayit_id: 1, sayfa: "/", senaryo_id: 1, kullanici: "Test Kullanıcı" }, { status: 201 }),
      ),
    );
    kurSayfa(<ListeCalismasi />);
    const ornek = await screen.findByRole("button", { name: "Örnek veriyle göster" });
    expect(ornek).toBeDisabled();
    expect(ornek).toHaveAttribute("title", "Düzenleme kilitli");
    // Bölen denemesi (kayıt yapmaz) serbesttir; kalıcı "Ayarı kaydet" kilitlidir.
    const bolen = screen.getByLabelText(/bölen/i);
    await userEvent.clear(bolen);
    await userEvent.type(bolen, "0,70");
    const kaydet = await screen.findByRole("button", { name: "Ayarı kaydet" });
    expect(kaydet).toBeDisabled();
    expect(kaydet).toHaveAttribute("title", "Düzenleme kilitli");

    await userEvent.click(screen.getByRole("button", { name: "Düzenlemeyi aç" }));
    await userEvent.click(await screen.findByRole("button", { name: "Evet, aç" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Ayarı kaydet" })).toBeEnabled());
    expect(screen.getByRole("button", { name: "Örnek veriyle göster" })).toBeEnabled();
  });
});
