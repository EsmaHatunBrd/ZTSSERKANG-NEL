import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { ListeCalismasi as ListeVerisi } from "@/api/tipler";
import ListeCalismasi, { puanBicimle } from "./ListeCalismasi";

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

function veri(bolen = "0.63", gecmisli = true): ListeVerisi {
  const yeni = (Number("44.10") / Number(bolen)).toFixed(4);
  return {
    yil: 2026,
    bolen,
    bolen_kayitli: false,
    varsayilan_bolen: "0.63",
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
        onceki_yil: gecmisli ? 2025 : null,
        onceki_liste: gecmisli ? "50" : null,
        liste_artis: gecmisli ? "0.4" : null,
        maliyet_artis: gecmisli ? "0.5" : null,
        fark: gecmisli ? "-0.1" : null,
        gecmis: gecmisli ? [{ yil: 2025, liste_fiyati: "50", birim_maliyet: "24.5", ornek: true }] : [],
      },
      {
        kod: "URUN-002",
        ad: "Zeytin Ezmesi 300 ml",
        hat: "Herbort",
        hata: null,
        maliyet_tl: "20",
        satis_tl: "24",
        yeni_liste: "38.0952",
        onceki_yil: gecmisli ? 2025 : null,
        onceki_liste: gecmisli ? "27" : null,
        liste_artis: gecmisli ? "0.41" : null,
        maliyet_artis: gecmisli ? "0.3" : null,
        fark: gecmisli ? "0.11" : null,
        gecmis: gecmisli ? [{ yil: 2025, liste_fiyati: "27", birim_maliyet: null, ornek: true }] : [],
      },
    ],
  };
}

describe("Liste Çalışması", () => {
  it("puanBicimle oran farkını puan olarak yazar", () => {
    expect(puanBicimle("-0.1")).toBe("-10,0 puan");
    expect(puanBicimle(null)).toBe("—");
  });

  it("varsayılan bölen, örnek veri uyarısı, kartlar; geride kalanlar süzülür", async () => {
    sunucu.use(http.get(`${T}/liste-calismasi`, () => HttpResponse.json(veri())));
    kurSayfa(<ListeCalismasi />);
    expect(await screen.findByDisplayValue("0,63")).toHaveAccessibleName("Bölen");
    expect(screen.getByText(/Varsayılan bölen 0,63/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Örnek veri");
    expect(screen.getByText("-10,0 puan")).toBeInTheDocument(); // kart
    expect(screen.getByText("-10,0")).toBeInTheDocument(); // ürün satırı (sütun: Fark (puan))
    expect(screen.getByText("Zeytin Ezmesi 300 ml")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Yalnız maliyetin gerisinde kalanlar"));
    expect(screen.queryByText("Zeytin Ezmesi 300 ml")).not.toBeInTheDocument();
    expect(screen.getByText("Biber Turşusu 370 ml")).toBeInTheDocument();
  });

  it("bölen değişince kaydetmeden denenir; kaydet nedenle parametre yazar", async () => {
    const sorgular: (string | null)[] = [];
    let govde: unknown = null;
    sunucu.use(
      http.get(`${T}/liste-calismasi`, ({ request }) => {
        const b = new URL(request.url).searchParams.get("bolen");
        sorgular.push(b);
        return HttpResponse.json(veri(b ?? "0.63"));
      }),
      http.post(`${T}/parametreler/liste_bolen/degerler`, async ({ request }) => {
        govde = await request.json();
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    kurSayfa(<ListeCalismasi />);
    const kutu = await screen.findByDisplayValue("0,63");
    await userEvent.clear(kutu);
    await userEvent.type(kutu, "0,7");
    await waitFor(() => expect(sorgular).toContain("0.7"), { timeout: 3000 });
    await userEvent.click(await screen.findByRole("button", { name: "Bölen olarak kaydet" }));
    const d = await screen.findByRole("dialog");
    await userEvent.type(within(d).getByLabelText("Neden"), "yeni iskonto");
    await userEvent.click(within(d).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(govde).toMatchObject({ deger: "0.7", neden: "yeni iskonto", kapsam_tipi: "genel" }));
  });

  it("ürün satırına tıklayınca geçmiş çekmecesi açılır; örnek satır gerçek olarak kaydedilir, yeni yıl eklenir", async () => {
    const yazilan: unknown[] = [];
    sunucu.use(
      http.get(`${T}/liste-calismasi`, () => HttpResponse.json(veri())),
      http.put(`${T}/liste-fiyatlari`, async ({ request }) => {
        const g = (await request.json()) as Record<string, unknown>;
        yazilan.push(g);
        return HttpResponse.json({ ...g, ornek: false });
      }),
    );
    kurSayfa(<ListeCalismasi />);
    await userEvent.click(await screen.findByText("Biber Turşusu 370 ml"));
    const cekmece = await screen.findByRole("dialog");
    expect(within(cekmece).getByLabelText("Liste fiyatı 2025")).toHaveValue("50");
    await userEvent.click(within(cekmece).getByRole("button", { name: "Gerçek olarak kaydet" }));
    await waitFor(() => expect(yazilan[0]).toEqual({ urun_kodu: "URUN-001", yil: 2025, liste_fiyati: "50", birim_maliyet: "24.5" }));
    expect(within(cekmece).getByLabelText("Yıl")).toHaveValue("2024");
    await userEvent.type(within(cekmece).getByLabelText("Yeni liste fiyatı"), "35,9");
    await userEvent.click(within(cekmece).getByRole("button", { name: "Ekle" }));
    await waitFor(() => expect(yazilan[1]).toEqual({ urun_kodu: "URUN-001", yil: 2024, liste_fiyati: "35.9", birim_maliyet: null }));
  });

  it("geçmiş yoksa örnek veriyle göster düğmesi örnek üretir", async () => {
    let uretildi = false;
    sunucu.use(
      http.get(`${T}/liste-calismasi`, () => HttpResponse.json(veri("0.63", uretildi))),
      http.post(`${T}/liste-calismasi/ornek`, () => {
        uretildi = true;
        return HttpResponse.json({ yazilan: 6 });
      }),
    );
    kurSayfa(<ListeCalismasi />);
    await userEvent.click(await screen.findByRole("button", { name: "Örnek veriyle göster" }));
    expect(await screen.findByRole("note")).toHaveTextContent("Örnek veri");
  });
});
