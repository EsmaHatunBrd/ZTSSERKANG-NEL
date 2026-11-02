import { KILIT_KAPSAM_NOTU } from "@/bilesenler/KilitSeridi";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { gunlukIsleyicileri, yeniGunlukIstekleri, type GunlukIstekleri } from "@/test/msw/isleyiciler-gunluk";
import { kurSayfa } from "@/test/kur-ayarlar";
import { arsivKiyasi } from "@/test/fikstur/gunluk";
import Arsiv from "./Arsiv";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let istek: GunlukIstekleri;
beforeEach(() => {
  localStorage.clear();
  istek = yeniGunlukIstekleri();
  sunucu.use(...gunlukIsleyicileri(istek));
});

describe("Arşiv", () => {
  it("sezon → senaryo ağacı: tür rozeti, tarih, kaynak dosya, sayılar, kilit simgesi", async () => {
    kurSayfa(<Arsiv />);
    const agac = within(await screen.findByRole("navigation", { name: "Arşiv ağacı" }));
    const s26 = within(await agac.findByRole("group", { name: "Sezon 2026-27" }));
    const v = within(s26.getByRole("button", { name: "Senaryo Varsayılan" }));
    expect(v.getByText("Fiyat çalışması")).toBeInTheDocument();
    expect(v.getByText("02.06.2026 · Esma")).toBeInTheDocument();
    expect(v.getByText("berrak-2026.xlsx")).toBeInTheDocument();
    expect(v.getByText("3 ürün · 2 hesap · 1 teklif")).toBeInTheDocument();
    expect(v.queryByLabelText("Kilitli")).not.toBeInTheDocument();
    const g = within(s26.getByRole("button", { name: "Senaryo Gerçekleşen" }));
    expect(g.getByLabelText("Kilitli")).toBeInTheDocument();
    expect(g.getAllByText("Gerçekleşen")).toHaveLength(2);   // ad + tür rozeti
    expect(agac.getByRole("group", { name: "Sezon 2025-26" })).toHaveTextContent("Senaryo yok");
  });

  it("seçili senaryonun kayıtlı hesapları tarih sırasıyla; satır hesap görünümüne bağlanır", async () => {
    kurSayfa(<Arsiv />);
    const tablo = within(await screen.findByRole("region", { name: "Kayıtlı hesaplar" }));
    await tablo.findByText("Kur revizyonu");
    const satirlar = tablo.getAllByRole("row");
    expect(satirlar).toHaveLength(3);   // başlık + 2 kayıt
    expect(within(satirlar[1]).getByText("21.10.2026")).toBeInTheDocument();
    expect(within(satirlar[1]).getByText("Kur revizyonu")).toBeInTheDocument();
    expect(within(satirlar[1]).getByText("38,13 TL")).toBeInTheDocument();
    expect(within(satirlar[1]).getByText("45,76 TL")).toBeInTheDocument();
    expect(within(satirlar[2]).getByText("15.09.2026")).toBeInTheDocument();
    expect(within(satirlar[1]).getAllByRole("link", { name: "Salatalık Turşusu 720 ml" })[0]).toHaveAttribute("href", "/hesaplar/11");
    expect(istek.arsivKayitlari[0]).toMatchObject({ id: "1", sayfa: "1", boyut: "50" });
  });

  it("ağaçtan başka senaryo seçilince onun kayıtları istenir (URL ?senaryo= ile uyumlu)", async () => {
    const u = userEvent.setup();
    kurSayfa(<Arsiv />);
    await screen.findByRole("region", { name: "Kayıtlı hesaplar" });
    await u.click(screen.getByRole("button", { name: "Senaryo Gerçekleşen" }));
    expect(await screen.findByText("Bu senaryoda kayıtlı hesap yok")).toBeInTheDocument();
    expect(istek.arsivKayitlari.at(-1)).toMatchObject({ id: "2" });
    expect(screen.getByRole("heading", { name: /Gerçekleşen/ })).toHaveTextContent("Kilitli");
  });

  it("iki satır seçilince Kıyasla açılır; yan yana kart Decimal farklarıyla gelir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Arsiv />);
    const kiyasla = await screen.findByRole("button", { name: "Kıyasla" });
    expect(kiyasla).toBeDisabled();
    await u.click(await screen.findByLabelText("Kıyas için seç URUN-001 2026-10-21"));
    expect(kiyasla).toBeDisabled();
    expect(screen.getByText("Kıyaslamak için bir kayıt daha seçin.")).toBeInTheDocument();
    await u.click(screen.getByLabelText("Kıyas için seç URUN-001 2026-09-15"));
    expect(kiyasla).toBeEnabled();
    await u.click(kiyasla);
    const kart = within(await screen.findByRole("region", { name: "Kıyas" }));
    expect(istek.kiyas[0]).toEqual({ hesap_a: "11", hesap_b: "10" });   // seçim sırası A, B
    expect(await kart.findByText("Malzeme toplamı")).toBeInTheDocument();
    const mal = within(kart.getByRole("region", { name: "Toplamlar" }));
    expect(mal.getByText("1,7500 TL")).toBeInTheDocument();
    expect(mal.getByText("1,6308 TL")).toBeInTheDocument();
    const satirlar = within(kart.getByRole("region", { name: "Malzeme satırları" }));
    expect(satirlar.getByText("Yalnız B")).toBeInTheDocument();
    expect(satirlar.getByText("KAP-01")).toBeInTheDocument();
    expect(kart.queryByRole("status")).not.toBeInTheDocument();   // uyarı yok
    // üçüncü seçim engellenir
    expect(screen.queryAllByRole("checkbox").filter((c) => !(c as HTMLInputElement).checked).every((c) => (c as HTMLInputElement).disabled)).toBe(true);
  });

  it("farklı ürün uyarısı kıyas kartında görünür", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.get("*/api/v1/arsiv/kiyas", () =>
        HttpResponse.json({ ...arsivKiyasi, uyari: "Farklı ürünler kıyaslanıyor: A ve B." }),
      ),
    );
    kurSayfa(<Arsiv />);
    await u.click(await screen.findByLabelText("Kıyas için seç URUN-001 2026-10-21"));
    await u.click(screen.getByLabelText("Kıyas için seç URUN-001 2026-09-15"));
    await u.click(screen.getByRole("button", { name: "Kıyasla" }));
    expect(await screen.findByText("Farklı ürünler kıyaslanıyor: A ve B.")).toBeInTheDocument();
  });

  it("Kilitle: neden zorunlu; onayda kilitle ucuna neden gönderilir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Arsiv />);
    await u.click(await screen.findByRole("button", { name: "Kilitle" }));
    const d = await screen.findByRole("dialog");
    expect(within(d).getByText("Senaryoyu kilitle")).toBeInTheDocument();
    expect(within(d).getByText(KILIT_KAPSAM_NOTU)).toBeInTheDocument();
    await u.click(within(d).getByRole("button", { name: "Kilitle" }));
    expect(await within(d).findByRole("alert")).toHaveTextContent("Neden zorunlu");
    expect(istek.kilit).toHaveLength(0);
    await u.type(within(d).getByLabelText("Neden"), "Teklif gönderildi");
    await u.click(within(d).getByRole("button", { name: "Kilitle" }));
    await waitFor(() => expect(istek.kilit).toEqual([{ yol: "kilitle/1", govde: { neden: "Teklif gönderildi" } }]));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("kilitli senaryoda düğme 'Kilidi aç' olur ve kilit-ac ucuna neden gönderir", async () => {
    const u = userEvent.setup();
    kurSayfa(<Arsiv />, 2);
    await u.click(await screen.findByRole("button", { name: "Kilidi aç" }));
    const d = await screen.findByRole("dialog");
    expect(within(d).getByText("Senaryonun kilidini aç")).toBeInTheDocument();
    await u.type(within(d).getByLabelText("Neden"), "Revizyon gerekti");
    await u.click(within(d).getByRole("button", { name: "Kilidi aç" }));
    await waitFor(() => expect(istek.kilit).toEqual([{ yol: "kilit-ac/2", govde: { neden: "Revizyon gerekti" } }]));
  });

  it("kilit hatasında diyalog açık kalır", async () => {
    const u = userEvent.setup();
    sunucu.use(http.post("*/api/v1/senaryolar/:id/kilitle", () => HttpResponse.json({ hata: "dogrulama", mesaj: "senaryo zaten kilitli", alanlar: {} }, { status: 422 })));
    kurSayfa(<Arsiv />);
    await u.click(await screen.findByRole("button", { name: "Kilitle" }));
    const d = await screen.findByRole("dialog");
    await u.type(within(d).getByLabelText("Neden"), "x");
    await u.click(within(d).getByRole("button", { name: "Kilitle" }));
    expect(await within(d).findByRole("alert")).toHaveTextContent("senaryo zaten kilitli");
  });
});
