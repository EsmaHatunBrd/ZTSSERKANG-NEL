import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem, SmmStokTablosu } from "@/api/tipler";
import SmmStok from "./SmmStok";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem = {
  id: 7,
  yil: 2026,
  ay: 9,
  ad: "Eylül 2026",
  kaynak_dosya: "09-2026 SMM v1.xlsx",
  finansman: "0",
  kalem_sayisi: 2,
  olusturan: "Esma",
  recete_kaynagi: "excel",
  devir_donem_id: null,
  excel_kontrol: null,
} as unknown as SmmDonem;

function satir(kod: string, ad: string) {
  return {
    kod,
    ad,
    birim: "KG",
    tur: "0001-Hammadde",
    mizan_kodu: "150.01.001",
    dbs_miktar: "100",
    dbs_tutar: "1000",
    alim_miktar: "100",
    alim_tutar: "1400",
    iade_miktar: "0",
    iade_tutar: "0",
    uretim_miktar: "0",
    sayim_miktar: "40",
    finansman_payi: "0",
    toplam_miktar: "200",
    toplam_tutar: "2400",
    ortalama_fiyat: "12",
    kalan_miktar: "200",
    kalan_tutar: "2400",
    dss_tutar: "480",
    sarf_miktar: "160",
    sarf_tutar: "1920",
    uretime_giden: "1920",
    kontrol: false,
  };
}
const stok = {
  donem,
  toplamlar: {
    dbs_tutar: "1000",
    alim_tutar: "1400",
    finansman_payi: "0",
    iade_tutar: "0",
    dss_tutar: "480",
    sarf_tutar: "1920",
    uretime_giden: "1920",
  },
  kontrol_sayisi: 0,
  turler: [{ tur: "0001-Hammadde", kalem: 2, dbs_tutar: "1000", alim_tutar: "1400", dss_tutar: "480", sarf_tutar: "1920" }],
  kayitlar: [satir("HM-1", "Biber"), satir("HM-2", "Zeytin")],
} as unknown as SmmStokTablosu;

function kur(istekler: { patch: unknown[]; post: unknown[] }) {
  sunucu.use(
    http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
    http.get(`${T}/smm/donemler/:id/stok`, () => HttpResponse.json(stok)),
    http.get(`${T}/smm/donemler/:id/stok/elle`, () =>
      HttpResponse.json({
        kayitlar: { "HM-2": { alanlar: ["sayim_miktar"], zaman: "2026-11-09T10:00:00+00:00", kullanici: "esma", kayit: 1 } },
      }),
    ),
    http.patch(`${T}/smm/donemler/:id/stok/:kod`, async ({ request, params }) => {
      istekler.patch.push({ kod: params.kod, govde: await request.json() });
      return HttpResponse.json({ ...satir(String(params.kod), "Biber"), sayim_miktar: "45", degisti: ["sayim_miktar"] });
    }),
    http.post(`${T}/smm/donemler/:id/stok`, async ({ request }) => {
      istekler.post.push(await request.json());
      return HttpResponse.json({ ...satir("YENI-1", "Yeni"), degisti: ["ekle"] }, { status: 201 });
    }),
  );
  kurSayfa(<SmmStok />);
}

describe("SMM stok elle düzenleme", () => {
  it("elle değişen kalem rozet alır; Düzenle → yalnız değişen alan + neden PATCH ile gider; mesaj gösterilir", async () => {
    const istekler = { patch: [] as unknown[], post: [] as unknown[] };
    kur(istekler);
    const u = userEvent.setup();
    expect(await screen.findByText("Biber")).toBeInTheDocument();
    expect(screen.getByText("elle")).toBeInTheDocument(); // HM-2
    await u.click(screen.getByRole("button", { name: "Düzenle HM-1" }));
    const d = await screen.findByRole("dialog", { name: "Kalemi düzenle: HM-1" });
    const sayim = within(d).getByLabelText(/Sayım miktarı/);
    expect(sayim).toHaveValue("40");
    const kaydet = within(d).getByRole("button", { name: "Kaydet" });
    expect(kaydet).toBeDisabled(); // değişiklik ve neden yok
    await u.clear(sayim);
    await u.type(sayim, "45");
    expect(within(d).getByText("(değişti)")).toBeInTheDocument();
    expect(kaydet).toBeDisabled(); // neden yok
    await u.type(within(d).getByLabelText("Neden *"), "Sayım tutanağı");
    await u.click(kaydet);
    await waitFor(() => expect(istekler.patch).toHaveLength(1));
    expect(istekler.patch[0]).toEqual({ kod: "HM-1", govde: { sayim_miktar: "45", neden: "Sayım tutanağı" } });
    expect(await screen.findByRole("status")).toHaveTextContent("HM-1 güncellendi (1 alan).");
  });

  it("Kalem ekle → kod zorunlu, POST gövdesi kod + alanlar + neden", async () => {
    const istekler = { patch: [] as unknown[], post: [] as unknown[] };
    kur(istekler);
    const u = userEvent.setup();
    await screen.findByText("Biber");
    await u.click(screen.getByRole("button", { name: /Kalem ekle/ }));
    const d = await screen.findByRole("dialog", { name: "Yeni stok kalemi" });
    const kaydet = within(d).getByRole("button", { name: "Kaydet" });
    await u.type(within(d).getByLabelText("Neden *"), "Excel'de yoktu");
    expect(kaydet).toBeDisabled(); // kod yok
    await u.type(within(d).getByLabelText("Kod *"), "YENI-1");
    await u.type(within(d).getByLabelText("Ad"), "Yeni kavanoz");
    await u.type(within(d).getByLabelText(/Dönem başı miktar/), "10");
    await u.click(kaydet);
    await waitFor(() => expect(istekler.post).toHaveLength(1));
    expect(istekler.post[0]).toEqual({
      kod: "YENI-1",
      ad: "Yeni kavanoz",
      birim: null,
      tur: null,
      mizan_kodu: null,
      dbs_miktar: "10",
      neden: "Excel'de yoktu",
    });
    expect(await screen.findByRole("status")).toHaveTextContent("YENI-1 eklendi.");
  });
});
