import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kopyalananSayilar, senaryolar } from "@/test/fikstur/urunler";
import { KOPYA_BOLUMLERI, kopyaOzeti, YeniCalismaDiyalogu, type YeniCalismaSekmesi } from "./YeniCalismaDiyalogu";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function kur(sekme?: YeniCalismaSekmesi, liste = senaryolar) {
  const onKapat = vi.fn();
  const onOlusturuldu = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <YeniCalismaDiyalogu sekme={sekme} senaryolar={liste} seciliId={1} onKapat={onKapat} onOlusturuldu={onOlusturuldu} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { onKapat, onOlusturuldu, qc };
}

/** Son POST/PATCH gövdesini ve yolunu yakalar. */
function yakala(yontem: "post" | "patch", yol: string) {
  const kayit: { yol: string; govde: Record<string, unknown> }[] = [];
  sunucu.use(
    http[yontem](`*/api/v1${yol}`, async ({ request }) => {
      kayit.push({ yol: new URL(request.url).pathname, govde: (await request.json()) as Record<string, unknown> });
      if (yontem === "post" && yol.endsWith("kopyala")) {
        const g = kayit[kayit.length - 1].govde;
        return HttpResponse.json(
          { id: 4, sezon_ad: g.sezon_ad, ad: g.ad, tur: g.tur, kilitli: false, urun_sayisi: 67, kopyalanan: kopyalananSayilar },
          { status: 201 },
        );
      }
      return HttpResponse.json({ id: 3, sezon_ad: "x", ad: "y", tur: "fiyat_calismasi", kilitli: false }, { status: 201 });
    }),
  );
  return kayit;
}

describe("YeniCalismaDiyalogu (Faz 5c)", () => {
  it("üç sekme vardır; varsayılan Boş, `sekme` ile kopya sekmesi açılır", () => {
    kur();
    const sekmeler = screen.getAllByRole("tab");
    expect(sekmeler.map((s) => s.textContent)).toEqual(["Boş", "Geçen sezondan kopyala", "Excel'den"]);
    expect(screen.getByRole("tab", { name: "Boş" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("form", { name: "Boş çalışma" })).toBeInTheDocument();
  });

  it("kopya sekmesiyle açılınca o sekme seçilidir ve 6 kutu işaretlidir", () => {
    kur("kopya");
    expect(screen.getByRole("tab", { name: "Geçen sezondan kopyala" })).toHaveAttribute("aria-selected", "true");
    const kutular = screen.getAllByRole("checkbox");
    expect(kutular).toHaveLength(KOPYA_BOLUMLERI.length);
    for (const k of kutular) expect(k).toBeChecked();
    // Kaynak seçici üye ürün sayısını gösterir.
    expect(screen.getByRole("option", { name: /#1 · 2026-2027 · Varsayılan · Fiyat çalışması \(3 ürün\)/ })).toBeInTheDocument();
  });

  it("Boş: sezon adı zorunlu; doldurunca POST /senaryolar gövdesi, onOlusturuldu(id) ve kapanış", async () => {
    const u = userEvent.setup();
    const kayit = yakala("post", "/senaryolar");
    const { onKapat, onOlusturuldu } = kur();
    await u.click(screen.getByRole("button", { name: "Boş çalışma aç" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sezon adı zorunlu");
    expect(kayit).toHaveLength(0);
    // Backend YYYY-YYYY ister: biçim hatası sunucuya gitmeden gösterilir.
    await u.type(screen.getByLabelText("Sezon adı"), "Sezon 27");
    await u.click(screen.getByRole("button", { name: "Boş çalışma aç" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sezon adı YYYY-YYYY biçiminde olmalı");
    expect(kayit).toHaveLength(0);
    await u.clear(screen.getByLabelText("Sezon adı"));
    await u.type(screen.getByLabelText("Sezon adı"), "2027-2028");
    expect(screen.getByText(/Özet: "2027-2028 · Fiyat çalışması" \(Fiyat çalışması\) boş bir çalışma/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Boş çalışma aç" }));
    await waitFor(() => expect(kayit).toHaveLength(1));
    expect(kayit[0].yol).toBe("/api/v1/senaryolar");
    expect(kayit[0].govde).toEqual({ sezon_ad: "2027-2028", ad: "Fiyat çalışması", tur: "fiyat_calismasi", aciklama: null });
    await waitFor(() => expect(onOlusturuldu).toHaveBeenCalledWith(3));
    expect(onKapat).toHaveBeenCalled();
  });

  it("Boş: 'Parametreleri başka bir çalışmadan al' yalnız parametreleri kopyalar (B2)", async () => {
    const u = userEvent.setup();
    const bos = yakala("post", "/senaryolar");
    const kopya = yakala("post", "/senaryolar/:id/kopyala");
    const { onKapat, onOlusturuldu } = kur();
    expect(screen.queryByLabelText("Parametre kaynağı")).not.toBeInTheDocument();
    await u.click(screen.getByRole("checkbox", { name: /Parametreleri başka bir çalışmadan al/ }));
    expect(screen.getByLabelText("Parametre kaynağı")).toHaveValue("1"); // varsayılan: seçili çalışma
    await u.type(screen.getByLabelText("Sezon adı"), "2027-2028");
    expect(screen.getByText(/parametreler "#1 · 2026-2027 · Varsayılan · Fiyat çalışması" çalışmasından alınacak/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Parametrelerle aç" }));
    await waitFor(() => expect(kopya).toHaveLength(1));
    expect(bos).toHaveLength(0);
    expect(kopya[0].yol).toBe("/api/v1/senaryolar/1/kopyala");
    expect(kopya[0].govde).toMatchObject({
      sezon_ad: "2027-2028",
      ad: "Fiyat çalışması",
      tur: "fiyat_calismasi",
      kopyala: { receteler: false, fiyatlar: false, parametreler: true, gider: false, uretim: false, fire_kurallari: false, sablon: false },
    });
    expect(String(kopya[0].govde.neden)).toMatch(/parametreler/);
    await waitFor(() => expect(onOlusturuldu).toHaveBeenCalledWith(4));
    expect(onKapat).toHaveBeenCalled();
  });

  it("B4: sekme değiştirip dönünce Boş ve Kopya sekmelerine yazılanlar korunur", async () => {
    const u = userEvent.setup();
    kur();
    await u.type(screen.getByLabelText("Sezon adı"), "2027-2028");
    await u.clear(screen.getByLabelText("Çalışma adı"));
    await u.type(screen.getByLabelText("Çalışma adı"), "Revize bütçe");
    await u.click(screen.getByRole("checkbox", { name: /Parametreleri başka bir çalışmadan al/ }));
    await u.click(screen.getByRole("tab", { name: "Geçen sezondan kopyala" }));
    await u.type(screen.getByLabelText("Neden"), "sezon açılışı");
    await u.click(screen.getByRole("checkbox", { name: /Fire kuralları/ }));
    await u.click(screen.getByRole("tab", { name: "Excel'den" }));
    await u.click(screen.getByRole("tab", { name: "Boş" }));
    expect(screen.getByLabelText("Sezon adı")).toHaveValue("2027-2028");
    expect(screen.getByLabelText("Çalışma adı")).toHaveValue("Revize bütçe");
    expect(screen.getByRole("checkbox", { name: /Parametreleri başka bir çalışmadan al/ })).toBeChecked();
    await u.click(screen.getByRole("tab", { name: "Geçen sezondan kopyala" }));
    expect(screen.getByLabelText("Neden")).toHaveValue("sezon açılışı");
    expect(screen.getByRole("checkbox", { name: /Fire kuralları/ })).not.toBeChecked();
  });

  it("Boş: hiç çalışma yoksa parametre kısayolu görünmez", () => {
    kur("bos", []);
    expect(screen.queryByRole("checkbox", { name: /Parametreleri başka bir çalışmadan al/ })).not.toBeInTheDocument();
  });

  it("Kopya: neden zorunlu; bir kutu kaldırılınca gövde ve 'Kopyalandı' özeti", async () => {
    const u = userEvent.setup();
    const kayit = yakala("post", "/senaryolar/:id/kopyala");
    const { onKapat, onOlusturuldu } = kur("kopya");
    await u.type(screen.getByLabelText("Sezon adı"), "2027-2028");
    await u.click(screen.getByRole("button", { name: "Kopyala ve aç" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Neden zorunlu");
    expect(kayit).toHaveLength(0);
    await u.click(screen.getByRole("checkbox", { name: /Fire kuralları/ }));
    expect(screen.getByText(/6\/7 bölüm "2027-2028 · Varsayılan" adıyla/)).toBeInTheDocument();
    await u.type(screen.getByLabelText("Neden"), "Yeni sezon açılışı");
    await u.click(screen.getByRole("button", { name: "Kopyala ve aç" }));
    await waitFor(() => expect(kayit).toHaveLength(1));
    expect(kayit[0].yol).toBe("/api/v1/senaryolar/1/kopyala");
    expect(kayit[0].govde).toEqual({
      sezon_ad: "2027-2028",
      ad: "Varsayılan",
      tur: "fiyat_calismasi",
      aciklama: null,
      neden: "Yeni sezon açılışı",
      kopyala: { receteler: true, fiyatlar: true, parametreler: true, gider: true, uretim: true, fire_kurallari: false, sablon: true },
    });
    const durum = await screen.findByRole("status");
    expect(durum).toHaveTextContent(
      "Kopyalandı: 67 reçete, 661 malzeme fiyatı, 12 parametre, 3 metin parametresi, 8 gider havuzu, 4 ambalaj sınıfı, 67 üretim hedefi, 5 kapasite kaydı, 2 fire kuralı, 1 Excel şablonu.",
    );
    expect(durum).toHaveTextContent("Yeni çalışma seçildi: #4 · 2027-2028 · Varsayılan");
    expect(onOlusturuldu).toHaveBeenCalledWith(4);
    expect(onKapat).not.toHaveBeenCalled();
    await u.click(screen.getByRole("button", { name: "Kapat" }));
    expect(onKapat).toHaveBeenCalled();
  });

  it("Kopya: sunucu hatası diyalogda gösterilir", async () => {
    const u = userEvent.setup();
    sunucu.use(
      http.post("*/api/v1/senaryolar/:id/kopyala", () =>
        HttpResponse.json({ hata: "catisma", mesaj: "Aynı adda çalışma var", alanlar: {} }, { status: 409 }),
      ),
    );
    kur("kopya");
    await u.type(screen.getByLabelText("Sezon adı"), "2027-2028");
    await u.type(screen.getByLabelText("Neden"), "deneme");
    await u.click(screen.getByRole("button", { name: "Kopyala ve aç" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Aynı adda çalışma var");
  });

  it("kopyalanacak çalışma yoksa kopya sekmesi yönlendirme metni gösterir", async () => {
    const u = userEvent.setup();
    kur("bos", []);
    await u.click(screen.getByRole("tab", { name: "Geçen sezondan kopyala" }));
    expect(await screen.findByText(/Kopyalanacak bir çalışma yok/)).toBeInTheDocument();
  });

  it("Excel sekmesi Veri Aktar bağlantısını seçili senaryoyla taşır ve tıklanınca kapatır", async () => {
    const u = userEvent.setup();
    const { onKapat } = kur("excel");
    const a = screen.getByRole("link", { name: /Veri Aktar → Tüm çalışma kitabı/ });
    expect(a).toHaveAttribute("href", "/recete-aktar?senaryo=1");
    await u.click(a);
    expect(onKapat).toHaveBeenCalled();
  });

  it("kopyaOzeti sıfır bölümleri atlar; hepsi sıfırsa açıklayıcı metin", () => {
    expect(kopyaOzeti({ ...kopyalananSayilar, metin: 0, kapasite: 0 })).toBe(
      "Kopyalandı: 67 reçete, 661 malzeme fiyatı, 12 parametre, 8 gider havuzu, 4 ambalaj sınıfı, 67 üretim hedefi, 2 fire kuralı, 1 Excel şablonu.",
    );
    expect(
      kopyaOzeti({ recete: 0, fiyat: 0, parametre: 0, metin: 0, havuz: 0, ambalaj: 0, hedef: 0, kapasite: 0, fire: 0, sablon: 0 }),
    ).toMatch(/Kopyalanacak kayıt bulunmadı/);
    expect(within(document.body).queryByRole("dialog")).toBeNull();
  });
});
