import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import { useOnayliFiyatEkle } from "@/bilesenler/FiyatSapmaOnayi";
import type { AnalizSatiri } from "@/api/tipler";
import { malzemeler } from "@/test/fikstur/urunler";
import YaOlursa from "./YaOlursa";
import ZamEtkisi from "./ZamEtkisi";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";

function satir(kod: string, ad: string, fark: string, kar: string, esikAlti: boolean): AnalizSatiri {
  return {
    kod,
    ad,
    hat: "Niko",
    hata: null,
    maliyet_once: "30",
    maliyet_sonra: String(30 * (1 + Number(fark))),
    fark_tl: String(30 * Number(fark)),
    fark_yuzde: fark,
    satis_once: "36",
    satis_sonra: String(36 * (1 + Number(fark))),
    kar_orani: "0.2",
    mevcut_fiyatla_kar: kar,
    esik_alti: esikAlti,
  };
}

const ozet = (n: number, esikAlti: number) => ({
  urun_sayisi: n,
  etkilenen: n,
  ort_fark_yuzde: "0.08",
  en_yuksek_fark_yuzde: "0.15",
  esik_alti: esikAlti,
  hatali: 0,
});

describe("Ya olursa", () => {
  it("yüzde varsayımlar oran olarak gider; eşik altı ürünler işaretlenir ve süzülür", async () => {
    let sorgu: URLSearchParams | null = null;
    sunucu.use(
      http.get(`${T}/analiz/ya-olursa`, ({ request }) => {
        sorgu = new URL(request.url).searchParams;
        return HttpResponse.json({
          varsayimlar: { kur: "0.1", ambalaj: "0", hammadde: "0", adet: "-0.05" },
          marj_esigi: "0.10",
          ozet: ozet(2, 1),
          kayitlar: [satir("U1", "Biber Turşusu", "0.15", "0.04", true), satir("U2", "Zeytin Ezmesi", "0.02", "0.18", false)],
        });
      }),
    );
    kurSayfa(<YaOlursa />);
    await userEvent.type(screen.getByLabelText("Döviz kuru değişimi (%)"), "10");
    await userEvent.type(screen.getByLabelText("Üretim adedi değişimi (%)"), "-5");
    await userEvent.click(screen.getByRole("button", { name: "Hesapla" }));
    expect(await screen.findByText("Zeytin Ezmesi")).toBeInTheDocument();
    const q = sorgu as unknown as URLSearchParams;
    expect(["senaryo", "kur", "ambalaj", "hammadde", "adet"].map((k) => q.get(k))).toEqual(["1", "0.1", "0", "0", "-0.05"]);
    expect(screen.getByLabelText("Eşiğin altında")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/Yalnız kârı 10\s%\saltına düşenler/));
    expect(screen.queryByText("Zeytin Ezmesi")).not.toBeInTheDocument();
    expect(screen.getByText("Biber Turşusu")).toBeInTheDocument();
  });

  it("geçersiz yüzde hesaplatmaz", async () => {
    kurSayfa(<YaOlursa />);
    await userEvent.type(screen.getByLabelText("Ambalaj fiyatları değişimi (%)"), "on");
    expect(screen.getByRole("alert")).toHaveTextContent("Ambalaj fiyatları");
    expect(screen.getByRole("button", { name: "Hesapla" })).toBeDisabled();
  });
});

describe("Zam etkisi", () => {
  it("malzeme aranır, seçilir; zam oranıyla etkilenen ürünler listelenir", async () => {
    let sorgu: URLSearchParams | null = null;
    sunucu.use(
      http.get(`${T}/analiz/zam-etkisi`, ({ request }) => {
        sorgu = new URL(request.url).searchParams;
        return HttpResponse.json({
          malzeme: {
            kod: "M-001",
            ad: "Cam Kavanoz",
            tip: "0008-Ambalaj Malzeme",
            birim: "AD",
            fiyat: "5.9",
            para_birimi: "TL",
            yeni_fiyat: "6.49",
          },
          oran: "0.1",
          marj_esigi: "0.10",
          ozet: ozet(1, 0),
          kayitlar: [satir("U1", "Biber Turşusu", "0.03", "0.16", false)],
        });
      }),
    );
    kurSayfa(<ZamEtkisi />);
    await userEvent.type(screen.getByLabelText("Malzeme"), "M-0");
    const secenekler = await screen.findByRole("list", { name: "Malzeme seçenekleri" });
    await userEvent.click((await within(secenekler).findAllByRole("button"))[0]);
    // Zam kutusu 10 ile dolu gelir (yer tutucu değil): doğrudan hesaplanabilir
    expect(screen.getByLabelText("Zam oranı (%)")).toHaveValue("10");
    await userEvent.click(screen.getByRole("button", { name: "Hesapla" }));
    expect(await screen.findByText("Biber Turşusu")).toBeInTheDocument();
    expect(sorgu!.get("oran")).toBe("0.1");
    expect(screen.getByText(/Bu malzemeyi 1 ürün kullanıyor/)).toBeInTheDocument();
  });

  it("fiyatı 0 olan kalem seçilirse uyarı çıkar ve hesaplanmaz", async () => {
    const ilk = malzemeler.filter((m) => !m.kart_yok)[0];
    sunucu.use(
      http.get(`${T}/malzemeler`, () =>
        HttpResponse.json({ kayitlar: [{ ...ilk, kod: "YM-9", ad: "Yarı mamul", fiyat: "0" }], toplam: 1 }),
      ),
    );
    kurSayfa(<ZamEtkisi />);
    await userEvent.type(screen.getByLabelText("Malzeme"), "YM");
    const secenekler = await screen.findByRole("list", { name: "Malzeme seçenekleri" });
    expect(await within(secenekler).findByText("fiyat yok")).toBeInTheDocument();
    await userEvent.click(within(secenekler).getByRole("button"));
    expect(screen.getByRole("alert")).toHaveTextContent("satın alma fiyatı yok");
    expect(screen.getByRole("button", { name: "Hesapla" })).toBeDisabled();
  });
});

function FiyatFormu() {
  const ekle = useOnayliFiyatEkle();
  return (
    <div>
      <button
        type="button"
        onClick={() =>
          ekle.mutate(
            { kod: "M-001", senaryo: 1, govde: { fiyat: "9", gecerlilik_basi: "2026-11-06", neden: "zam", onay: false } },
            { onSuccess: () => document.body.setAttribute("data-kaydedildi", "1") },
          )
        }
      >
        Gönder
      </button>
      {ekle.error && <p role="alert">{ekle.error.message}</p>}
      {ekle.onayDiyalogu}
    </div>
  );
}

describe("Fiyat girişi sapma onayı", () => {
  it("eşik aşılırsa önceki ve yeni fiyat sorulur; onaylanınca onay: true ile yeniden gider", async () => {
    const govdeler: Record<string, unknown>[] = [];
    sunucu.use(
      http.post(`${T}/malzemeler/:kod/fiyatlar`, async ({ request }) => {
        const g = (await request.json()) as Record<string, unknown>;
        govdeler.push(g);
        if (!g.onay)
          return HttpResponse.json(
            {
              hata: "dogrulama",
              mesaj: "fiyat eşikten fazla farklı",
              alanlar: { eski_fiyat: "5.9", yeni_fiyat: "9", para_birimi: "TL", oran: "0.5254", esik: "0.15" },
              kod: "fiyat_sapma",
            },
            { status: 422 },
          );
        return HttpResponse.json({ id: 9, fiyat: "9", gecerlilik_basi: "2026-11-06" }, { status: 201 });
      }),
    );
    kurSayfa(<FiyatFormu />);
    await userEvent.click(screen.getByRole("button", { name: "Gönder" }));
    const d = await screen.findByRole("dialog");
    expect(d).toHaveTextContent("5,9000 TL → 9,0000 TL");
    expect(d).toHaveTextContent(/eşiği 15\s%/);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(within(d).getByRole("button", { name: "Yine de kaydet" }));
    await waitFor(() => expect(document.body.getAttribute("data-kaydedildi")).toBe("1"));
    expect(govdeler.map((g) => g.onay)).toEqual([false, true]);
  });
});
