import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { gunlukIsleyicileri, yeniGunlukIstekleri, type GunlukIstekleri } from "@/test/msw/isleyiciler-gunluk";
import { kurSayfa } from "@/test/kur-ayarlar";
import { gunlukSatirlari } from "@/test/fikstur/gunluk";
import Gunluk from "./Gunluk";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

let istek: GunlukIstekleri;
beforeEach(() => {
  localStorage.clear();
  istek = yeniGunlukIstekleri();
  sunucu.use(...gunlukIsleyicileri(istek));
});

const akis = () => within(screen.getByRole("region", { name: "Değişiklik akışı" }));

describe("Değişiklik Günlüğü", () => {
  it("akışı çizer: tür rozeti, ürün, eski → yeni, neden; parametre anahtarı okunur etiketle", async () => {
    kurSayfa(<Gunluk />);
    expect(await screen.findByText("Parametre: USD kuru")).toBeInTheDocument();
    const satir = within(screen.getByTestId("gunluk-parametre:12"));
    expect(satir.getByText("Parametre")).toBeInTheDocument();   // tür rozeti
    expect(satir.getByText("Esma")).toBeInTheDocument();
    expect(satir.getByText("50")).toBeInTheDocument();
    expect(satir.getByText("55")).toBeInTheDocument();
    expect(satir.getByText("Kur güncellemesi")).toBeInTheDocument();
    const hesap = within(screen.getByTestId("gunluk-hesap:5"));
    expect(hesap.getByText("URUN-001")).toBeInTheDocument();
    expect(hesap.getByText("maliyet 38.130789 TL")).toBeInTheDocument();
    // satır türleri
    for (const t of ["Parametre", "Fire", "Hesap", "Ürün kartı"]) expect(akis().getAllByText(t).length).toBeGreaterThan(0);
  });

  it("ilk istek seçili senaryo ve sayfalama ile; Son 7 gün kartları özetten gelir", async () => {
    kurSayfa(<Gunluk />);
    await screen.findByText("Parametre: USD kuru");
    expect(istek.liste[0]).toMatchObject({ senaryo: "1", sayfa: "1", boyut: "50" });
    expect(await screen.findByTestId("ozet-toplam")).toHaveTextContent("4");
    expect(istek.ozet[0]).toMatchObject({ senaryo: "1", gun: "7" });
    const kart = within(screen.getByRole("region", { name: "Son 7 gün" }));
    expect(kart.getByText("Esma")).toBeInTheDocument();
    expect(kart.getByText("Parametre · 1")).toBeInTheDocument();
  });

  it("süzgeçler istek parametrelerine yansır (tarih aralığı, kullanıcı, çoklu tür, ürün kodu, arama)", async () => {
    const u = userEvent.setup();
    kurSayfa(<Gunluk />);
    await screen.findByText("Parametre: USD kuru");
    await u.type(screen.getByLabelText("Başlangıç"), "2026-10-01");
    await u.type(screen.getByLabelText("Bitiş"), "2026-10-31");
    await u.type(screen.getByLabelText("Kullanıcı"), "Esma");
    await u.click(screen.getByLabelText("Parametre"));
    await u.click(screen.getByLabelText("Hesap"));
    await u.type(screen.getByLabelText("Ürün kodu"), "URUN");
    await u.type(screen.getByLabelText("Ara"), "kur");
    await waitFor(() => {
      const son = istek.liste[istek.liste.length - 1];
      expect(son).toMatchObject({ senaryo: "1", bas: "2026-10-01", son: "2026-10-31", kullanici: "Esma", tur: ["parametre", "hesap"], urun_kodu: "URUN", q: "kur", sayfa: "1" });
    });
    // süzülmüş akış: Esma'nın parametre + hesap satırları
    await waitFor(() => expect(akis().queryByText("Fire kuralı: malzeme KAV")).not.toBeInTheDocument());
    expect(akis().getByText("Hesap kaydedildi (2026-10-21)")).toBeInTheDocument();
    // "Tüm senaryolar" senaryo süzgecini kaldırır
    await u.click(screen.getByLabelText("Tüm senaryolar"));
    await waitFor(() => expect(istek.liste[istek.liste.length - 1]).not.toHaveProperty("senaryo"));
  });

  it("Excel'e aktar bağlantısı aynı süzgeçleri taşır (sayfa/boyut hariç)", async () => {
    const u = userEvent.setup();
    kurSayfa(<Gunluk />);
    await screen.findByText("Parametre: USD kuru");
    await u.click(screen.getByLabelText("Fire"));
    const bag = screen.getByRole("link", { name: /Excel'e aktar/ });
    await waitFor(() => expect(bag.getAttribute("href")).toBe("/api/v1/disa-aktar/gunluk.xlsx?senaryo=1&tur=fire"));
  });

  it("geri al yalnız geri alınabilir satırda; onaydan sonra geri_al yoluna gövdeyle POST eder", async () => {
    const u = userEvent.setup();
    const alinan: { url: string; govde: unknown }[] = [];
    sunucu.use(
      http.post("*/api/v1/parametreler/:anahtar/degerler", async ({ request }) => {
        alinan.push({ url: new URL(request.url).pathname + new URL(request.url).search, govde: await request.json() });
        return HttpResponse.json({ id: 99, deger: "50", gecerlilik_basi: "2026-10-22" }, { status: 201 });
      }),
    );
    kurSayfa(<Gunluk />);
    await screen.findByText("Parametre: USD kuru");
    expect(screen.getAllByRole("button", { name: /^Geri al / })).toHaveLength(1);   // fire/hesap/ürün: düğme yok
    await u.click(screen.getByRole("button", { name: "Geri al parametre:12" }));
    const diyalog = await screen.findByRole("dialog");
    expect(within(diyalog).getByText(/Parametre: USD kuru: 50 değeri bugünden itibaren yeniden geçerli olacak/)).toBeInTheDocument();
    expect(alinan).toHaveLength(0);   // onay öncesi istek yok
    await u.click(within(diyalog).getByRole("button", { name: "Onayla" }));
    await waitFor(() => expect(alinan).toHaveLength(1));
    expect(alinan[0].url).toBe("/api/v1/parametreler/kur.USD/degerler?senaryo=1");
    expect(alinan[0].govde).toEqual(gunlukSatirlari[0].geri_al?.govde);
    expect(await screen.findByText(/Parametre: USD kuru geri alındı/)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("geri alma hatasında onay penceresi açık kalır ve hata gösterir", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.post("*/api/v1/parametreler/:anahtar/degerler", () =>
        HttpResponse.json({ hata: "cakisma", mesaj: "senaryo kilitli", alanlar: {} }, { status: 409 }),
      ),
    );
    kurSayfa(<Gunluk />);
    await u.click(await screen.findByRole("button", { name: "Geri al parametre:12" }));
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Onayla" }));
    expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent("senaryo kilitli");
  });

  it("sayfalar arası geçiş sayfa parametresini değiştirir", async () => {
    const cok = Array.from({ length: 60 }, (_, i) => ({ ...gunlukSatirlari[1], id: `fire:${i + 100}` }));
    sunucu.use(...gunlukIsleyicileri(istek, cok));
    const u = userEvent.setup();
    kurSayfa(<Gunluk />);
    await screen.findByText("Sayfa 1 / 2");
    await u.click(screen.getByRole("button", { name: "Sonraki" }));
    await screen.findByText("Sayfa 2 / 2");
    expect(istek.liste[istek.liste.length - 1]).toMatchObject({ sayfa: "2" });
  });

  it("boş sonuçta ve hatada ileti gösterir", async () => {
    sunucu.use(http.get("*/api/v1/gunluk", () => HttpResponse.json({ hata: "dogrulama", mesaj: "bilinmeyen tür", alanlar: {} }, { status: 422 })));
    kurSayfa(<Gunluk />);
    expect(await screen.findByRole("alert")).toHaveTextContent("bilinmeyen tür");
  });
});
