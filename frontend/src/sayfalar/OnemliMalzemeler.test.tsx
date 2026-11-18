import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import type { OnemliMalzemeSatiri } from "@/api/tipler";
import OnemliMalzemeler from "./OnemliMalzemeler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

function satir(sira: number, kod: string, ad: string, ek: Partial<OnemliMalzemeSatiri> = {}): OnemliMalzemeSatiri {
  return {
    sira,
    kod,
    ad,
    tip: "0001-Hammadde",
    para_birimi: "TL",
    birim: "KG",
    yillik_miktar: "1000",
    yillik_tutar_tl: "0",
    pay_yuzde: "0.00",
    kumulatif_yuzde: "0.00",
    esik_icinde: false,
    kullanan_urun_sayisi: 1,
    birim_fiyat: "1",
    ...ek,
  };
}

/** Toplam 1.000.000 TL: Salatalık %60, Kavanoz %25 (kümülatif %85), Kapak %10 (%95), Tuz %5 (%100), fiyatsız Etiket. */
const HAM: [string, string, string, string, string, Partial<OnemliMalzemeSatiri>][] = [
  ["M1", "Salatalık", "600000", "60.00", "60.00", { yillik_miktar: "120000.5", birim_fiyat: "4.2", kullanan_urun_sayisi: 12 }],
  ["M2", "Kavanoz", "250000", "25.00", "85.00", { birim: "AD", para_birimi: "USD", birim_fiyat: "0.1234", kullanan_urun_sayisi: 8 }],
  ["M3", "Kapak", "100000", "10.00", "95.00", { birim: "AD", yillik_miktar: "0" }],
  ["M4", "Tuz", "50000", "5.00", "100.00", {}],
  ["M5", "Etiket", "0", "0.00", "100.00", { birim_fiyat: null, para_birimi: null }],
];

function satirlar(esik: number): OnemliMalzemeSatiri[] {
  let onceki = 0;
  return HAM.map(([kod, ad, tutar, pay, kum, ek], i) => {
    const icinde = Number(tutar) > 0 && onceki < esik * 100;
    onceki = Number(kum);
    return satir(i + 1, kod, ad, { yillik_tutar_tl: tutar, pay_yuzde: pay, kumulatif_yuzde: kum, esik_icinde: icinde, ...ek });
  });
}

function kur(istekler: (string | null)[] = [], ek: { bos?: boolean; adetsiz?: number } = {}) {
  sunucu.use(
    http.get(`${T}/analiz/onemli-malzemeler`, ({ request }) => {
      const esik = new URL(request.url).searchParams.get("esik");
      istekler.push(esik);
      const s = ek.bos ? [] : satirlar(Number(esik ?? "0.8"));
      return HttpResponse.json({
        senaryo_id: 1,
        esik: esik ?? "0.8",
        tarih: "2026-11-13",
        adet_kaynagi: "satis_gecmisi",
        toplam_tutar_tl: ek.bos ? "0" : "1000000",
        adetsiz_urun: ek.adetsiz ?? 0,
        hatali_urun: 0,
        satirlar: s,
        esik_icindeki_sayi: s.filter((x) => x.esik_icinde).length,
      });
    }),
  );
}

function Yer() {
  const l = useLocation();
  return <output data-testid="yer">{l.pathname + l.search}</output>;
}

function ciz(adres = "/onemli-malzemeler?senaryo=1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[adres]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/onemli-malzemeler" element={<OnemliMalzemeler />} />
            <Route path="/fiyatlar" element={<Yer />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const tablo = () => screen.findByRole("table", { name: "Önemli malzemeler" });
const satirOf = (t: HTMLElement, ad: string) => within(t).getByText(ad).closest("tr") as HTMLElement;

describe("Önemli malzemeler", () => {
  it("başlık, özet şerit ve tablo: sıra, kod, maliyete giren birim fiyat, yıllık miktar/tutar, pay, kümülatif, kullanan ürün", async () => {
    kur();
    ciz();
    const t = await tablo();
    await within(t).findByText("Salatalık");
    expect(screen.getByRole("heading", { name: "Önemli malzemeler" })).toBeInTheDocument();
    expect(screen.getByText("Maliyetin %80'ini oluşturan malzemeler, yıllık üretim adediyle ağırlıklı")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Özet" })).toHaveTextContent(
      "2 malzeme toplam tutarın %80'ini oluşturuyor (5 malzemeden) · yıllık malzeme tutarı 1.000.000 TL",
    );
    const m1 = satirOf(t, "Salatalık");
    expect(m1).toHaveTextContent("M1");
    // maliyete giren = yıllık tutar ÷ yıllık miktar (600.000 ÷ 120.000,5); altında liste fiyatı
    expect(within(t).getByRole("columnheader", { name: "Maliyete giren birim fiyat (TL)" })).toBeInTheDocument();
    expect(m1).toHaveTextContent("5,0000 TL");
    expect(m1).toHaveTextContent("liste 4,2000 TL");
    expect(m1).toHaveTextContent("120.001 KG");
    expect(m1).toHaveTextContent("600.000 TL");
    expect(m1).toHaveTextContent("%60,0");
    expect(within(m1).getAllByRole("cell").at(-1)).toHaveTextContent("12");
    const m2 = satirOf(t, "Kavanoz");
    expect(m2).toHaveTextContent("250,0000 TL");
    expect(m2).toHaveTextContent("liste 0,1234 USD");
    // yıllık miktar 0: maliyete giren birim fiyat hesaplanmaz
    expect(within(satirOf(t, "Kapak")).getByText("—")).toBeInTheDocument();
    expect(m2).toHaveTextContent("%25,0");
    expect(m2).toHaveTextContent("%85,0");
    // fiyatsız: birim fiyat —, liste fiyatı yok, pay %0
    const m5 = satirOf(t, "Etiket");
    expect(within(m5).getByText("—")).toBeInTheDocument();
    expect(m5).not.toHaveTextContent("liste");
    expect(m5).toHaveTextContent("%0,0");
    expect(screen.getByText(/Tutarı 0 olan 1 kalem/)).toBeInTheDocument();
    // sunucu sırası korunur
    const adlar = within(t)
      .getAllByRole("row")
      .filter((r) => r.hasAttribute("data-esik-icinde"))
      .map((r) => within(r).getAllByRole("cell")[1].textContent);
    expect(adlar).toEqual(["M1", "M2", "M3", "M4", "M5"]);
    // Pareto grafiği
    expect(await screen.findByRole("img", { name: /Pareto grafiği\. Eşik %80\./ })).toBeInTheDocument();
  });

  it("eşik içindeki satırlar vurgulu; eşik sınırında ayraç", async () => {
    kur();
    ciz();
    const t = await tablo();
    await within(t).findByText("Salatalık");
    expect(satirOf(t, "Salatalık")).toHaveAttribute("data-esik-icinde", "evet");
    expect(satirOf(t, "Salatalık").className).toMatch(/bg-primary\/5/);
    expect(satirOf(t, "Kavanoz")).toHaveAttribute("data-esik-icinde", "evet"); // eşiği aşan ilk satır
    expect(satirOf(t, "Kapak")).toHaveAttribute("data-esik-icinde", "hayir");
    expect(satirOf(t, "Kapak").className).not.toMatch(/bg-primary\/5/);
    const ayrac = within(t).getByTestId("esik-ayraci");
    expect(ayrac).toHaveTextContent("Eşik sınırı — yukarıdaki 2 malzeme toplam tutarın %80'ini oluşturuyor");
    // ayraç Kavanoz ile Kapak arasında
    const sirali = within(t).getAllByRole("row");
    expect(sirali.indexOf(ayrac)).toBe(sirali.indexOf(satirOf(t, "Kavanoz")) + 1);
    expect(sirali.indexOf(ayrac)).toBe(sirali.indexOf(satirOf(t, "Kapak")) - 1);
  });

  it("eşik değişimi yeniden sorgular; özet, alt başlık ve Excel bağlantısı güncellenir", async () => {
    const istekler: (string | null)[] = [];
    kur(istekler);
    ciz();
    await within(await tablo()).findByText("Salatalık");
    expect(istekler).toEqual(["0.8"]);
    const excel = () => screen.getByRole("link", { name: /Excel'e aktar/ });
    expect(excel()).toHaveAttribute("href", "/api/v1/disa-aktar/onemli-malzemeler?senaryo=1&esik=0.8");
    expect(excel()).toHaveAttribute("download");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Eşik" }), "90");
    await waitFor(() => expect(istekler).toEqual(["0.8", "0.9"]));
    await waitFor(() =>
      expect(screen.getByRole("status", { name: "Özet" })).toHaveTextContent("3 malzeme toplam tutarın %90'ını oluşturuyor (5 malzemeden)"),
    );
    expect(screen.getByText("Maliyetin %90'ını oluşturan malzemeler, yıllık üretim adediyle ağırlıklı")).toBeInTheDocument();
    expect(excel()).toHaveAttribute("href", "/api/v1/disa-aktar/onemli-malzemeler?senaryo=1&esik=0.9");
    expect(satirOf(await tablo(), "Kapak")).toHaveAttribute("data-esik-icinde", "evet");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Eşik" }), "70");
    await waitFor(() => expect(istekler).toEqual(["0.8", "0.9", "0.7"]));
  });

  it("adresteki eşik (?esik=70) ilk sorguda kullanılır; geçersiz değer %80'e düşer", async () => {
    const istekler: (string | null)[] = [];
    kur(istekler);
    const { unmount } = ciz("/onemli-malzemeler?senaryo=1&esik=70");
    await within(await tablo()).findByText("Salatalık");
    expect(istekler).toEqual(["0.7"]);
    expect(screen.getByRole("combobox", { name: "Eşik" })).toHaveValue("70");
    unmount();
    ciz("/onemli-malzemeler?senaryo=1&esik=abc");
    await within(await tablo()).findByText("Salatalık");
    expect(istekler).toEqual(["0.7", "0.8"]);
  });

  it("arama kod ve ada göre süzer; arama sırasında ayraç gizlenir", async () => {
    kur();
    ciz();
    const t = await tablo();
    await within(t).findByText("Salatalık");
    await userEvent.type(screen.getByRole("searchbox", { name: "Malzeme ara" }), "kap");
    expect(within(t).getByText("Kapak")).toBeInTheDocument();
    expect(within(t).queryByText("Salatalık")).not.toBeInTheDocument();
    expect(within(t).queryByTestId("esik-ayraci")).not.toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox", { name: "Malzeme ara" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Malzeme ara" }), "m4");
    expect(within(t).getByText("Tuz")).toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox", { name: "Malzeme ara" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Malzeme ara" }), "yokböyle");
    expect(within(t).getByText("Aramaya uyan malzeme yok")).toBeInTheDocument();
  });

  it("satıra tıklayınca malzemenin fiyat kaydına gider", async () => {
    kur();
    ciz();
    const t = await tablo();
    await userEvent.click(await within(t).findByText("Kavanoz"));
    expect(await screen.findByTestId("yer")).toHaveTextContent("/fiyatlar?senaryo=1&arama=M2");
  });

  it("adetsiz ürün varsa bilgi notu gösterilir; yoksa gösterilmez", async () => {
    kur([], { adetsiz: 3 });
    const { unmount } = ciz();
    await within(await tablo()).findByText("Salatalık");
    expect(screen.getByTestId("adetsiz-notu")).toHaveTextContent("3 ürünün yıllık adedi (geçen yıl satışı) olmadığı için hesaba girmedi.");
    unmount();
    kur();
    ciz();
    await within(await tablo()).findByText("Salatalık");
    expect(screen.queryByTestId("adetsiz-notu")).not.toBeInTheDocument();
  });

  it("boş durum: yıllık adedi olan ürün yoksa tablo ve grafik yerine yönlendirme", async () => {
    kur([], { bos: true, adetsiz: 5 });
    ciz();
    expect(await screen.findByText("Bu çalışmada yıllık adedi olan ürün yok")).toBeInTheDocument();
    expect(screen.getByText(/önce Satış Geçmişi'ni yükleyin/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Pareto/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Özet" })).not.toBeInTheDocument();
    expect(screen.getByTestId("adetsiz-notu")).toHaveTextContent("5 ürünün");
  });

  it("sunucu hatası mesajla gösterilir", async () => {
    sunucu.use(
      http.get(`${T}/analiz/onemli-malzemeler`, () =>
        HttpResponse.json({ hata: "dogrulama", mesaj: "eşik 0 ile 1 arasında olmalı (0.8 = %80)", alanlar: {} }, { status: 422 }),
      ),
    );
    ciz();
    expect(await screen.findByRole("alert")).toHaveTextContent("eşik 0 ile 1 arasında olmalı");
  });
});
