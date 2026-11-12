import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import type { FiyatEgilimiSatiri } from "@/api/tipler";
import FiyatEgilimi from "./FiyatEgilimi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

function satir(kod: string, ad: string, ek: Partial<FiyatEgilimiSatiri> = {}): FiyatEgilimiSatiri {
  return {
    kod,
    ad,
    tip: "hammadde",
    para_birimi: "TL",
    ilk_fiyat: "5",
    ilk_tarih: "2025-11-12",
    son_fiyat: "9",
    son_tarih: "2026-10-01",
    kayit_sayisi: 3,
    degisim_yuzde: "80.00",
    yillik_yuzde: "80.00",
    esik_yuzde: "40.00",
    enflasyonu_asiyor: true,
    kullanan_urun_sayisi: 12,
    ...ek,
  };
}

const SATIRLAR = [
  satir("M1", "Tuz"),
  satir("M2", "Sirke", { ilk_fiyat: "10", son_fiyat: "14.05", degisim_yuzde: "40.50", yillik_yuzde: "40.50", enflasyonu_asiyor: false }),
  satir("M3", "Kapak", {
    para_birimi: "USD",
    ilk_fiyat: "0.1",
    son_fiyat: "0.1",
    degisim_yuzde: "0.00",
    yillik_yuzde: "0.00",
    esik_yuzde: "0.00",
    enflasyonu_asiyor: false,
    kullanan_urun_sayisi: 3,
  }),
  satir("M4", "Etiket", { ilk_fiyat: "0", degisim_yuzde: null, yillik_yuzde: null, enflasyonu_asiyor: false, kayit_sayisi: 1 }),
];

interface Istek {
  ay: string | null;
  yalniz_asan: string | null;
}

function kur(istekler: Istek[] = [], satirlar: FiyatEgilimiSatiri[] = SATIRLAR) {
  sunucu.use(
    http.get(`${T}/analiz/fiyat-egilimi`, ({ request }) => {
      const p = new URL(request.url).searchParams;
      istekler.push({ ay: p.get("ay"), yalniz_asan: p.get("yalniz_asan") });
      const yalniz = p.get("yalniz_asan") === "true" || p.get("yalniz_asan") === "1";
      const gorunen = yalniz ? satirlar.filter((s) => s.enflasyonu_asiyor) : satirlar;
      return HttpResponse.json({
        senaryo_id: 1,
        ay: Number(p.get("ay") ?? 12),
        tarih: "2026-11-12",
        pencere_basi: "2025-11-12",
        enflasyon_yuzde: "40.00",
        satirlar: gorunen,
        asan_sayisi: satirlar.filter((s) => s.enflasyonu_asiyor).length,
        toplam: satirlar.length,
      });
    }),
  );
}

function ciz(adres = "/fiyat-egilimi?senaryo=1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[adres]}>
        <SenaryoSaglayici>
          <FiyatEgilimi />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Fiyat eğilimi", () => {
  it("satırları, rozetleri (Aşıyor / Sınırda / Normal), boş yüzdede — ve özet şeridi gösterir", async () => {
    kur();
    ciz();
    const tablo = await screen.findByRole("table");
    const tuz = (await within(tablo).findByText("Tuz")).closest("tr") as HTMLElement;
    expect(within(tuz).getByText("Aşıyor").className).toMatch(/text-destructive/);
    expect(tuz).toHaveTextContent("80,0 %");
    expect(tuz).toHaveTextContent("5,0000 TL");
    expect(tuz).toHaveTextContent("12");
    const sirke = within(tablo).getByText("Sirke").closest("tr") as HTMLElement;
    expect(within(sirke).getByText("Sınırda")).toBeInTheDocument();
    const kapak = within(tablo).getByText("Kapak").closest("tr") as HTMLElement;
    expect(within(kapak).getByText("Normal")).toBeInTheDocument();
    expect(kapak).toHaveTextContent("0,1000 USD");
    const etiket = within(tablo).getByText("Etiket").closest("tr") as HTMLElement;
    expect(within(etiket).getAllByText("—").length).toBeGreaterThanOrEqual(2);
    const ozet = screen.getByRole("status", { name: "Özet" });
    expect(ozet).toHaveTextContent("4 malzeme");
    expect(ozet).toHaveTextContent("1 enflasyonu aşıyor");
    expect(ozet).toHaveTextContent(/eşik %40/);
  });

  it("?arama= ile gelen değer kutuya dolar ve tabloyu süzer", async () => {
    kur();
    ciz("/fiyat-egilimi?senaryo=1&arama=M2");
    const tablo = await screen.findByRole("table");
    expect(await within(tablo).findByText("Sirke")).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "Malzeme ara" })).toHaveValue("M2");
    expect(within(tablo).queryByText("Tuz")).not.toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox", { name: "Malzeme ara" }));
    expect(await within(tablo).findByText("Tuz")).toBeInTheDocument();
  });

  it("pencere seçimi ay= ile, anahtar yalniz_asan ile yeniden sorgular", async () => {
    const istekler: Istek[] = [];
    kur(istekler);
    ciz();
    expect(await screen.findByText("Tuz")).toBeInTheDocument();
    expect(istekler[0]).toEqual({ ay: "12", yalniz_asan: null });
    await userEvent.click(screen.getByRole("checkbox", { name: "Yalnız enflasyonu aşanlar" }));
    await waitFor(() => expect(istekler.at(-1)?.yalniz_asan).toBe("true"));
    await waitFor(() => expect(screen.queryByText("Sirke")).not.toBeInTheDocument());
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Pencere" }), "6");
    await waitFor(() => expect(istekler.at(-1)?.ay).toBe("6"));
  });

  it("satıra tıklayınca geçmiş paneli açılır ve kayıt listesini gösterir", async () => {
    kur();
    ciz();
    const tablo = await screen.findByRole("table");
    await userEvent.click(await within(tablo).findByText("Tuz"));
    const panel = await screen.findByRole("region", { name: /Fiyat geçmişi: Tuz/ });
    const liste = await within(panel).findByRole("table", { name: "Fiyat kayıtları" });
    expect(liste).toHaveTextContent("Yeni liste");
    expect(liste).toHaveTextContent("Sezon başı");
    expect(liste).toHaveTextContent("01.10.2026");
    expect(liste).toHaveTextContent("5,9000 TL");
    await userEvent.click(within(panel).getByRole("button", { name: "Paneli kapat" }));
    expect(screen.queryByRole("region", { name: /Fiyat geçmişi/ })).not.toBeInTheDocument();
  });

  it("boş durumu gösterir", async () => {
    kur([], []);
    ciz();
    expect(await screen.findByText("Bu çalışmada fiyat kaydı yok.")).toBeInTheDocument();
  });

  it("sunucu hatasında role=alert", async () => {
    sunucu.use(
      http.get(`${T}/analiz/fiyat-egilimi`, () =>
        HttpResponse.json({ hata: "sunucu", mesaj: "Enflasyon parametresi yok", alanlar: {} }, { status: 422 }),
      ),
    );
    ciz();
    expect(await screen.findByRole("alert")).toHaveTextContent("Enflasyon parametresi yok");
  });
});
