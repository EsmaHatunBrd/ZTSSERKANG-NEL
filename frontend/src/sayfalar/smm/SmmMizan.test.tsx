import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem, SmmMizanSatiri } from "@/api/tipler";
import SmmVeri from "./SmmVeri";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem = {
  id: 7,
  yil: 2026,
  ay: 10,
  ad: "Ekim 2026",
  kaynak_dosya: null,
  finansman: "0",
  kalem_sayisi: 2,
  olusturan: "Esma",
  recete_kaynagi: "ana",
  devir_donem_id: 6,
  excel_kontrol: null,
  kilitli: false,
  kilitleyen: null,
} as unknown as SmmDonem;

/** Küçük bir sahte sunucu: gider mizanı satırlarını bellekte tutar. */
function kur(baslangic: SmmMizanSatiri[], secenek: { kilitli?: boolean; grupsuz?: boolean } = {}) {
  let satirlar = [...baslangic];
  const istekler: { yontem: string; hesap?: string; govde?: unknown; neden?: string | null }[] = [];
  const elle = () => satirlar.filter((x) => x.elle).length;
  const mizan = () => ({
    donem: { ...donem, kilitli: Boolean(secenek.kilitli) },
    tur: "gider",
    ad: "Gider mizanı (720 / 730)",
    kayitlar: satirlar,
    toplam: String(satirlar.reduce((t, x) => t + Number(x.bakiye), 0)),
    elle: elle(),
    elle_uyari: elle() ? `${elle()} elle satır var, yükleme bunları siler` : null,
  });
  const durum = () => ({
    donem: { ...donem, kilitli: Boolean(secenek.kilitli) },
    donem_basi: { kaynak: "devir", dolu: 2, tutar: "480", hazir: true },
    kaynaklar: [
      { kaynak: "alim", ad: "Alım ve satış", zorunlu: true, yuklendi: true, dolu: 2, son: null, elle: 0, elle_uyari: null },
      {
        kaynak: "gider_mizan",
        ad: "Gider mizanı (720 / 730)",
        zorunlu: true,
        yuklendi: satirlar.length > 0,
        dolu: satirlar.length,
        son: null,
        elle: elle(),
        elle_uyari: elle() ? `${elle()} elle satır var, yükleme bunları siler` : null,
      },
    ],
    eksik: [],
    ayarlar: { finansman: "0", gider_720: "2000", gider_730: "3000" },
    turler: [],
    grupsuz: secenek.grupsuz
      ? { kalem: 1, alim_tutar: "30", dbs_tutar: "0", ornek: ["YENI-1"] }
      : { kalem: 0, alim_tutar: "0", dbs_tutar: "0", ornek: [] },
  });
  sunucu.use(
    http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [{ ...donem, kilitli: Boolean(secenek.kilitli) }] })),
    http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(durum())),
    http.get(`${T}/smm/donemler/:id/mizan/:tur`, () => HttpResponse.json(mizan())),
    http.post(`${T}/smm/donemler/:id/mizan/:tur`, async ({ request }) => {
      const g = (await request.json()) as { hesap: string; ad: string | null; bakiye: string };
      istekler.push({ yontem: "POST", govde: g });
      satirlar = [...satirlar, { hesap: g.hesap, ad: g.ad, bakiye: g.bakiye, elle: true }];
      return HttpResponse.json(mizan(), { status: 201 });
    }),
    http.patch(`${T}/smm/donemler/:id/mizan/:tur/:hesap`, async ({ request, params }) => {
      const g = (await request.json()) as { ad?: string | null; bakiye?: string };
      istekler.push({ yontem: "PATCH", hesap: params.hesap as string, govde: g });
      satirlar = satirlar.map((x) => (x.hesap === params.hesap ? { ...x, ...g, elle: true } : x)) as SmmMizanSatiri[];
      return HttpResponse.json({ ...mizan(), degisti: Object.keys(g).filter((a) => a !== "neden") });
    }),
    http.delete(`${T}/smm/donemler/:id/mizan/:tur/:hesap`, ({ request, params }) => {
      istekler.push({ yontem: "DELETE", hesap: params.hesap as string, neden: new URL(request.url).searchParams.get("neden") });
      satirlar = satirlar.filter((x) => x.hesap !== params.hesap);
      return HttpResponse.json(mizan());
    }),
    http.post(`${T}/smm/donemler/:id/veri/:kaynak`, ({ params }) => {
      istekler.push({ yontem: "YUKLE", hesap: params.kaynak as string });
      satirlar = [{ hesap: "720", ad: "Direkt İşçilik Giderleri", bakiye: "2000", elle: false }];
      return HttpResponse.json(durum());
    }),
  );
  return istekler;
}

const EXCEL: SmmMizanSatiri[] = [
  { hesap: "720", ad: "Direkt İşçilik Giderleri", bakiye: "2000", elle: false },
  { hesap: "730", ad: "Genel Üretim Giderleri", bakiye: "3000.5", elle: false },
];

async function bolumuAc() {
  await userEvent.click(await screen.findByRole("button", { name: "Satırları gör / düzenle" }));
  return screen.findByRole("region", { name: "Gider mizanı (720 / 730) satırları" });
}

describe("SMM mizan satırları (elle giriş)", () => {
  it("satırlar listelenir: hesap, ad, bakiye, toplam; yalnız mizan kaynaklarında düğme vardır", async () => {
    kur(EXCEL);
    kurSayfa(<SmmVeri />);
    const bolum = await bolumuAc();
    expect(screen.getAllByRole("button", { name: /Satırları/ })).toHaveLength(1); // alım satırında yok
    expect(await within(bolum).findByText("Genel Üretim Giderleri")).toBeInTheDocument();
    expect(within(bolum).getByText("720")).toBeInTheDocument();
    expect(bolum).toHaveTextContent("3.000,50");
    expect(bolum).toHaveTextContent("Toplam");
    expect(bolum).toHaveTextContent("5.000,50 TL");
    expect(within(bolum).queryByText("elle")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Satırları gizle" }));
    expect(screen.queryByRole("region", { name: "Gider mizanı (720 / 730) satırları" })).not.toBeInTheDocument();
  });

  it("satır eklenir: neden zorunlu, bakiye sayı olmalı; eklenen satır 'elle' rozetiyle görünür", async () => {
    const istekler = kur(EXCEL);
    kurSayfa(<SmmVeri />);
    const bolum = await bolumuAc();
    await userEvent.click(within(bolum).getByRole("button", { name: /Satır ekle/ }));
    const form = await screen.findByRole("dialog");
    const kaydet = within(form).getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled();
    await userEvent.type(within(form).getByLabelText("Hesap kodu *"), "731");
    await userEvent.type(within(form).getByLabelText("Bakiye (TL) *"), "abc");
    expect(form).toHaveTextContent("Bakiye geçerli bir sayı olmalı");
    await userEvent.clear(within(form).getByLabelText("Bakiye (TL) *"));
    await userEvent.type(within(form).getByLabelText("Bakiye (TL) *"), "-3000,5");
    expect(kaydet).toBeDisabled(); // neden yok
    await userEvent.type(within(form).getByLabelText("Neden *"), "yansıtma");
    await userEvent.click(kaydet);
    await waitFor(() =>
      expect(istekler).toEqual([{ yontem: "POST", govde: { hesap: "731", ad: null, bakiye: "-3000.5", neden: "yansıtma" } }]),
    );
    expect(await within(bolum).findByText("731 eklendi.")).toBeInTheDocument();
    expect(await within(bolum).findByText("elle")).toBeInTheDocument();
    expect(await screen.findByText(/1 kayıt|3 kayıt/)).toBeInTheDocument();
    await waitFor(() => expect(bolum).toHaveTextContent("1 elle satır"));
  });

  it("satır düzenlenir (yalnız değişen alan gider) ve nedenle silinir", async () => {
    const istekler = kur(EXCEL);
    kurSayfa(<SmmVeri />);
    const bolum = await bolumuAc();
    await userEvent.click(await within(bolum).findByRole("button", { name: "720 satırını düzenle" }));
    const form = await screen.findByRole("dialog");
    expect(within(form).queryByLabelText("Hesap kodu *")).not.toBeInTheDocument();
    const bakiye = within(form).getByLabelText("Bakiye (TL) *");
    expect(bakiye).toHaveValue("2000");
    await userEvent.clear(bakiye);
    await userEvent.type(bakiye, "2750");
    await userEvent.type(within(form).getByLabelText("Neden *"), "mizan kesinleşti");
    await userEvent.click(within(form).getByRole("button", { name: "Kaydet" }));
    await waitFor(() =>
      expect(istekler[0]).toEqual({ yontem: "PATCH", hesap: "720", govde: { bakiye: "2750", neden: "mizan kesinleşti" } }),
    );
    expect(await within(bolum).findByText("720 güncellendi.")).toBeInTheDocument();
    await waitFor(() => expect(bolum).toHaveTextContent("2.750,00"));

    await userEvent.click(within(bolum).getByRole("button", { name: "730 satırını sil" }));
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("730 satırı silinsin mi?");
    const silDugmesi = within(onay).getByRole("button", { name: "Satırı sil" });
    expect(silDugmesi).toBeDisabled(); // neden yok
    await userEvent.type(within(onay).getByLabelText("Silme nedeni"), "yanlış hesap");
    await userEvent.click(silDugmesi);
    await waitFor(() => expect(istekler[1]).toEqual({ yontem: "DELETE", hesap: "730", neden: "yanlış hesap" }));
    expect(await within(bolum).findByText("730 silindi.")).toBeInTheDocument();
    await waitFor(() => expect(within(bolum).queryByText("Genel Üretim Giderleri")).not.toBeInTheDocument());
  });

  it("elle satır varken yükleme onay ister; onaylanınca yüklenir", async () => {
    const istekler = kur([{ ...EXCEL[0], elle: true }, EXCEL[1]]);
    kurSayfa(<SmmVeri />);
    expect(await screen.findByText(/1 elle satır/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("Gider mizanı (720 / 730) dosyası"), new File(["x"], "mizan.xlsx"));
    await userEvent.click(screen.getAllByRole("button", { name: /Yeniden yükle/ })[1]);
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("1 elle satır var, yükleme bunları siler");
    expect(istekler).toEqual([]);
    await userEvent.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(istekler).toEqual([]);
    await userEvent.click(screen.getAllByRole("button", { name: /Yeniden yükle/ })[1]);
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Yükle ve elle satırları sil" }));
    await waitFor(() => expect(istekler).toEqual([{ yontem: "YUKLE", hesap: "gider_mizan" }]));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText(/1 elle satır/)).not.toBeInTheDocument());
  });

  it("elle satır yokken yükleme onaysız gider", async () => {
    const istekler = kur(EXCEL);
    kurSayfa(<SmmVeri />);
    await userEvent.upload(await screen.findByLabelText("Gider mizanı (720 / 730) dosyası"), new File(["x"], "mizan.xlsx"));
    await userEvent.click(screen.getAllByRole("button", { name: /Yeniden yükle/ })[1]);
    await waitFor(() => expect(istekler).toEqual([{ yontem: "YUKLE", hesap: "gider_mizan" }]));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("kilitli dönemde satırlar yalnız görülür; türsüz kalem uyarısı gösterilir", async () => {
    kur(EXCEL, { kilitli: true, grupsuz: true });
    kurSayfa(<SmmVeri />);
    await userEvent.click(await screen.findByRole("button", { name: "Satırları gör" }));
    const bolum = await screen.findByRole("region", { name: "Gider mizanı (720 / 730) satırları" });
    expect(await within(bolum).findByText("Genel Üretim Giderleri")).toBeInTheDocument();
    expect(within(bolum).queryByRole("button", { name: /Satır ekle/ })).not.toBeInTheDocument();
    expect(within(bolum).queryByRole("button", { name: /düzenle/ })).not.toBeInTheDocument();
    expect(screen.getByText(/1 kalemin türü \/ mizan kodu boş/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Stok ve Envanter'de türünü girin/ })).toHaveAttribute("href", "/smm/stok?donem=7");
  });
});
