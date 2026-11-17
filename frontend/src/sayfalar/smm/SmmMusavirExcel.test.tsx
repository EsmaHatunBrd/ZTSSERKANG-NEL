import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem, SmmMusavirExcelDurumu } from "@/api/tipler";
import SmmDonemler from "./SmmDonemler";
import SmmOzet from "./SmmOzet";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

const T = "*/api/v1";
const donem: SmmDonem = {
  id: 8,
  yil: 2026,
  ay: 11,
  ad: "Kasım 2026",
  kaynak_dosya: null,
  finansman: "0",
  kalem_sayisi: 40,
  olusturan: "Esma",
  recete_kaynagi: "ana",
  devir_donem_id: 7,
  kilitli: false,
  kilitleyen: null,
  excel_kontrol: null,
};
const sablonlu: SmmMusavirExcelDurumu = {
  sablon: { dosya_adi: "10-2026 SMM v1.xlsx", zaman: "2026-11-17T09:30:00", olusturan: "esma", boyut: 1234 },
  kaynak_donem: "Ekim 2026",
  kaynak_donem_id: 7,
  kendi: false,
  taslak: true,
};
const sablonsuz: SmmMusavirExcelDurumu = { sablon: null, kaynak_donem: null, kaynak_donem_id: null, kendi: false, taslak: true };

function ozetIsleyicileri(durum: SmmMusavirExcelDurumu) {
  sunucu.use(
    http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
    http.get(`${T}/smm/donemler/:id/ozet`, () =>
      HttpResponse.json({ hata: "x", mesaj: "hesap yok", alanlar: {}, kod: null }, { status: 404 }),
    ),
    http.get(`${T}/smm/donemler/:id/musavir-excel/durum`, () => HttpResponse.json(durum)),
  );
}

describe("SMM müşavir Excel'i", () => {
  it("şablon varsa SMM Özeti'nde indirme bağlantısı ve şablon bilgisi (önceki ayın dosyası, taslak)", async () => {
    ozetIsleyicileri(sablonlu);
    kurSayfa(<SmmOzet />);
    const baglanti = await screen.findByRole("link", { name: "Müşavir Excel'i" });
    expect(baglanti).toHaveAttribute("href", "/api/v1/smm/donemler/8/musavir-excel.xlsx");
    expect(baglanti).toHaveAttribute("download");
    const not = screen.getByRole("note", { name: "Müşavir Excel'i" });
    expect(not).toHaveTextContent("Şablon: 10-2026 SMM v1.xlsx, 17.11.2026 (Ekim 2026 dosyası; bu ayın Excel'i yüklenmedi)");
    expect(not).toHaveTextContent("TASLAK — dönem kapatılmadı");
    expect(not).toHaveTextContent("Excel açıldığında toplamlar yeniden hesaplanır");
  });

  it("şablon yoksa düğme pasif ve nedeni yazılı", async () => {
    ozetIsleyicileri(sablonsuz);
    kurSayfa(<SmmOzet />);
    const not = await screen.findByRole("note", { name: "Müşavir Excel'i" });
    expect(not).toHaveTextContent("Şablon yok: Dönemler › SMM Excel'inden yükle");
    const dugme = screen.getByRole("button", { name: "Müşavir Excel'i" });
    expect(dugme).toBeDisabled();
    expect(dugme).toHaveAttribute("title", expect.stringContaining("Şablon yok"));
    expect(screen.queryByRole("link", { name: "Müşavir Excel'i" })).not.toBeInTheDocument();
  });

  it("Dönemler'de yalnız şablon olarak saklanır: önce önizleme, sonra sakla", async () => {
    let saklandi = false;
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/musavir-excel/durum`, () => HttpResponse.json(saklandi ? { ...sablonlu, kendi: true } : sablonsuz)),
      http.post(`${T}/smm/donemler/:id/musavir-excel/sablon/onizle`, () =>
        HttpResponse.json({ dosya_adi: "11-2026 SMM.xlsx", sayfalar: ["ENVANTER", "DBS", "TABLO"], donem: "Kasım 2026", mevcut: null }),
      ),
      http.post(`${T}/smm/donemler/:id/musavir-excel/sablon`, ({ params }) => {
        expect(params.id).toBe("8");
        saklandi = true;
        return HttpResponse.json({
          ...sablonlu,
          kendi: true,
          kaynak_donem: "Kasım 2026",
          sablon: { ...sablonlu.sablon!, dosya_adi: "11-2026 SMM.xlsx" },
        });
      }),
    );
    kurSayfa(<SmmDonemler />);
    const kart = await screen.findByRole("region", { name: "Müşavir Excel'i şablonu" });
    expect(await within(kart).findByText(/Bu dönem için şablon yok/)).toBeInTheDocument();
    await userEvent.upload(within(kart).getByLabelText("Müşavir şablonu dosyası"), new File(["x"], "11-2026 SMM.xlsx"));
    await userEvent.click(within(kart).getByRole("button", { name: "Şablonu önizle" }));
    const on = await within(kart).findByRole("region", { name: "Şablon önizlemesi" });
    expect(on).toHaveTextContent("11-2026 SMM.xlsx Kasım 2026 için müşavir şablonu olarak saklanacak; dönemin verileri değişmez.");
    expect(on).toHaveTextContent("Sayfalar: ENVANTER, DBS, TABLO");
    await userEvent.click(within(on).getByRole("button", { name: "Yalnız şablon olarak sakla" }));
    expect(await within(kart).findByRole("status")).toHaveTextContent("Şablon saklandı. Şablon: 11-2026 SMM.xlsx, 17.11.2026");
    await waitFor(() => expect(saklandi).toBe(true));
  });

  it("SMM Excel'i olmayan dosya önizlemede reddedilir", async () => {
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [donem] })),
      http.get(`${T}/smm/donemler/:id/musavir-excel/durum`, () => HttpResponse.json(sablonsuz)),
      http.post(`${T}/smm/donemler/:id/musavir-excel/sablon/onizle`, () =>
        HttpResponse.json(
          {
            hata: "dogrulama",
            mesaj: "Bu dosya SMM dönem Excel'i değil: beklenen sayfalar yok (DBS).",
            alanlar: {},
            kod: "smm_excel_degil",
          },
          { status: 422 },
        ),
      ),
    );
    kurSayfa(<SmmDonemler />);
    const kart = await screen.findByRole("region", { name: "Müşavir Excel'i şablonu" });
    await userEvent.upload(within(kart).getByLabelText("Müşavir şablonu dosyası"), new File(["x"], "sayim.xlsx"));
    await userEvent.click(within(kart).getByRole("button", { name: "Şablonu önizle" }));
    expect(await within(kart).findByRole("alert")).toHaveTextContent("SMM dönem Excel'i değil");
    expect(within(kart).queryByRole("button", { name: "Yalnız şablon olarak sakla" })).not.toBeInTheDocument();
  });
});
