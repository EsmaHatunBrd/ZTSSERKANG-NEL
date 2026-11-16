import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem } from "@/api/tipler";
import { OturumSaglayici } from "@/bilesenler/GirisKapisi";
import SmmDonemler from "./SmmDonemler";
import SmmVeri from "./SmmVeri";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const ortak = { kaynak_dosya: null, finansman: "0", kalem_sayisi: 2, olusturan: "Esma", recete_kaynagi: "ana", excel_kontrol: null };
const eylul = {
  ...ortak,
  id: 6,
  yil: 2026,
  ay: 9,
  ad: "Eylül 2026",
  devir_donem_id: null,
  kilitli: false,
  kilitleyen: null,
} as unknown as SmmDonem;
const ekim = {
  ...ortak,
  id: 7,
  yil: 2026,
  ay: 10,
  ad: "Ekim 2026",
  devir_donem_id: 6,
  kilitli: false,
  kilitleyen: null,
} as unknown as SmmDonem;

function durum(donem: SmmDonem, devir: unknown = null) {
  return {
    donem,
    donem_basi: { kaynak: "devir", dolu: 2, tutar: "480", hazir: true },
    kaynaklar: [{ kaynak: "alim", ad: "Alım ve satış", zorunlu: true, yuklendi: true, dolu: 2, son: null, elle: 0, elle_uyari: null }],
    eksik: [],
    ayarlar: { finansman: "0", gider_720: "2000", gider_730: "3000" },
    turler: [],
    grupsuz: { kalem: 0, alim_tutar: "0", dbs_tutar: "0", ornek: [] },
    devir,
  };
}

function oturumla(rol: string, eleman: React.ReactElement) {
  const kullanici = { id: 1, kullanici_adi: "x", ad: "X", rol, rol_ad: rol, aktif: true, sifre_degismeli: false } as never;
  return <OturumSaglayici deger={{ girisZorunlu: true, kullanici }}>{eleman}</OturumSaglayici>;
}

describe("SMM ay devri ve ay kilidi", () => {
  it("devir uyumsuzsa uyarır; farklar görülür; devir nedenle yenilenir ve elle değerler korunur", async () => {
    let uyumlu = false;
    let govde: unknown = null;
    const devirDurumu = {
      onceki: { id: 6, ad: "Eylül 2026", kilitli: false },
      uyumlu: false,
      fark_kalem: 2,
      fark_tutar: "219",
      acilis_tutar: "579",
      kapanis_tutar: "360",
      elle_kalem: 1,
      ornek: [
        { kod: "HM-1", ad: "Biber", acilis_miktar: "40", kapanis_miktar: "30", acilis_tutar: "480", kapanis_tutar: "360", elle: false },
        { kod: "AMB-1", ad: "Kavanoz", acilis_miktar: "5", kapanis_miktar: "0", acilis_tutar: "99", kapanis_tutar: "0", elle: true },
      ],
    };
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [ekim, eylul] })),
      http.get(`${T}/smm/donemler/:id/veri`, () =>
        HttpResponse.json(
          durum(ekim, {
            uyumlu,
            fark_kalem: uyumlu ? 0 : 2,
            fark_tutar: uyumlu ? "0" : "219",
            onceki_ad: "Eylül 2026",
            onceki_kilitli: false,
          }),
        ),
      ),
      http.get(`${T}/smm/donemler/:id/devir-durumu`, () => HttpResponse.json(devirDurumu)),
      http.post(`${T}/smm/donemler/:id/devir-yenile`, async ({ request }) => {
        govde = await request.json();
        uyumlu = true;
        return HttpResponse.json({
          donem: ekim,
          guncellenen: 1,
          eklenen: 0,
          elle_kalem: 1,
          elle_korundu: true,
          durum: { ...devirDurumu, fark_kalem: 1 },
        });
      }),
    );
    kurSayfa(<SmmVeri />);
    const uyari = await screen.findByRole("region", { name: "Devir uyarısı" });
    expect(uyari).toHaveTextContent("Açılış stoku Eylül 2026 kapanışıyla uyuşmuyor (2 kalem, fark 219,00 TL)");
    expect(uyari).toHaveTextContent("Eylül 2026 henüz kapatılmadı");

    await userEvent.click(within(uyari).getByRole("button", { name: "Farkları gör" }));
    const tablo = await within(uyari).findByRole("table", { name: "Devir farkları" });
    expect(within(tablo).getByText("HM-1")).toBeInTheDocument();
    expect(within(within(tablo).getByText("AMB-1").closest("tr") as HTMLElement).getByText("elle")).toBeInTheDocument();
    expect(within(tablo).getByText("120,00")).toBeInTheDocument();

    await userEvent.click(within(uyari).getByRole("button", { name: /Devri yenile/ }));
    const diyalog = await screen.findByRole("dialog", { name: "Devir yenilensin mi?" });
    expect(diyalog).toHaveTextContent("Elle girdiğiniz açılış değerleri korunur.");
    const onay = within(diyalog).getByRole("button", { name: "Devri yenile" });
    expect(onay).toBeDisabled(); // neden zorunlu
    await userEvent.type(within(diyalog).getByLabelText("Neden (zorunlu)"), "Eylül sayımı düzeltildi");
    await userEvent.click(onay);
    await waitFor(() => expect(govde).toEqual({ neden: "Eylül sayımı düzeltildi", elle_ez: false }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Devir yenilendi: 1 kalem güncellendi, 0 kalem eklendi. 1 elle açılış değeri korundu.",
    );
    await waitFor(() => expect(screen.queryByRole("region", { name: "Devir uyarısı" })).not.toBeInTheDocument());
  });

  it("kapanışta eksikler listelenir; 'Yine de kapat' zorla gönderir", async () => {
    const govdeler: unknown[] = [];
    let kilitli = false;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [{ ...ekim, kilitli }, eylul] })),
      http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(durum({ ...ekim, kilitli, kilitleyen: kilitli ? "Esma" : null }))),
      http.put(`${T}/smm/donemler/:id/kilit`, async ({ request }) => {
        const g = (await request.json()) as { kilitli: boolean; zorla?: boolean };
        govdeler.push(g);
        if (!g.zorla) {
          return HttpResponse.json(
            {
              hata: "catisma",
              mesaj: "Ekim 2026 kapatılmadan önce eksikler var",
              kod: "kapanis_eksik",
              alanlar: { eksikler: ["Eksik veri: Sayım (dönem sonu stok)", "3 kalemin türü / mizan kodu boş; SMM tablosuna girmiyor"] },
            },
            { status: 409 },
          );
        }
        kilitli = true;
        return HttpResponse.json({ ...ekim, kilitli: true, kilitleyen: "Esma", kilit_zamani: "2026-11-13T09:00:00+00:00", uyari: null });
      }),
    );
    kurSayfa(<SmmVeri />);
    await userEvent.click(await screen.findByRole("button", { name: /Dönemi kapat/ }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Kapat ve kilitle" }));
    const eksikOnayi = await screen.findByRole("dialog", { name: "Ekim 2026 eksiklerle kapatılsın mı?" });
    const liste = within(eksikOnayi).getByRole("list", { name: "Kapanış eksikleri" });
    expect(
      within(liste)
        .getAllByRole("listitem")
        .map((x) => x.textContent),
    ).toEqual(["Eksik veri: Sayım (dönem sonu stok)", "3 kalemin türü / mizan kodu boş; SMM tablosuna girmiyor"]);
    expect(within(eksikOnayi).queryByRole("alert")).not.toBeInTheDocument();
    await userEvent.click(within(eksikOnayi).getByRole("button", { name: "Yine de kapat" }));
    await waitFor(() => expect(govdeler).toEqual([{ kilitli: true }, { kilitli: true, zorla: true }]));
    // Sayfadaki kapanış bandı ve düzenleme kilidi şeridindeki dönem uyarısı ikisi de "kapatıldı" der.
    expect(await screen.findByText(/kapatıldı.*veriler değiştirilemez/)).toBeInTheDocument();
    expect(screen.getByTestId("duzenleme-engel")).toHaveTextContent("Dönem kapatıldı; değişiklik için önce kilidi açın.");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("kilidi yalnız Genel Direktör açar; onayda sonraki dönem uyarısı görünür", async () => {
    let govde: unknown = null;
    let kilitli = true;
    const kapaliEylul = () => ({ ...eylul, kilitli, kilitleyen: kilitli ? "Esma" : null });
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [kapaliEylul(), ekim] })),
      http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(durum(kapaliEylul()))),
      http.put(`${T}/smm/donemler/:id/kilit`, async ({ request }) => {
        govde = await request.json();
        kilitli = false;
        return HttpResponse.json({
          ...eylul,
          uyari: "Ekim 2026 açılışı bu dönemden devralındı; değişiklik sonrası devri yenileyin",
        });
      }),
    );
    // muhasebe: düğme devre dışı, ipucu görünür
    const { unmount } = kurSayfa(oturumla("muhasebe", <SmmVeri />));
    const dugme = await screen.findByRole("button", { name: /Kilidi aç/ });
    expect(dugme).toBeDisabled();
    expect(dugme).toHaveAttribute("title", "Dönem kilidini yalnız Genel Direktör açabilir");
    expect(screen.getByText("Dönem kilidini yalnız Genel Direktör açabilir.")).toBeInTheDocument();
    unmount();

    // Genel Direktör: onay diyaloğunda zincir uyarısı, sonra kilit açılır
    kurSayfa(oturumla("genel_direktor", <SmmVeri />));
    const ac = await screen.findByRole("button", { name: /Kilidi aç/ });
    expect(ac).toBeEnabled();
    await userEvent.click(ac);
    const onay = await screen.findByRole("dialog", { name: "Eylül 2026 kilidi açılsın mı?" });
    expect(onay).toHaveTextContent("Ekim 2026 açılışı bu dönemden devralındı; değişiklik sonrası Ekim 2026 döneminde devri yenileyin.");
    await userEvent.click(within(onay).getByRole("button", { name: "Kilidi aç" }));
    await waitFor(() => expect(govde).toEqual({ kilitli: false }));
    expect(await screen.findByRole("status")).toHaveTextContent("Kilit açıldı. Ekim 2026 açılışı bu dönemden devralındı");
    expect(screen.getByRole("link", { name: "Ekim 2026 veri girişine git" })).toHaveAttribute("href", "/smm/veri?donem=7");
  });

  it("dönem listesi: açılışın kaynağı, önceki ay kapalı değil rozeti ve kapanış bilgisi", async () => {
    const kasim = { ...ekim, id: 8, ay: 11, ad: "Kasım 2026", devir_donem_id: 7 } as unknown as SmmDonem;
    const kapaliEkim = { ...ekim, kilitli: true, kilitleyen: "Esma", kilit_zamani: "2026-11-13T09:00:00+00:00" } as unknown as SmmDonem;
    sunucu.use(http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [kasim, kapaliEkim, eylul] })));
    kurSayfa(<SmmDonemler />);
    const satirlar = await within(await screen.findByRole("region", { name: "Yüklü dönemler" })).findAllByRole("listitem");
    expect(satirlar[0]).toHaveTextContent("Açılış: Ekim 2026 kapanışından");
    expect(satirlar[0]).not.toHaveTextContent("kapalı değil");
    expect(satirlar[1]).toHaveTextContent("Açılış: Eylül 2026 kapanışından");
    expect(satirlar[1]).toHaveTextContent("Eylül 2026 kapalı değil");
    expect(satirlar[1]).toHaveTextContent("Kapalı · Esma · 13.11.2026");
    expect(satirlar[2]).not.toHaveTextContent("Açılış:");
  });
});
