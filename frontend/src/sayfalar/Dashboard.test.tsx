import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { dashboardSatirlari, senaryolar } from "@/test/fikstur/urunler";
import { tutarlilikSorunlu } from "@/test/fikstur/tutarlilik";
import Dashboard, { SUTUN_ANAHTARI } from "./Dashboard";

/** Tüm isteğe bağlı sütun gruplarını açık kaydeder (varsayılan tablo sadedir). */
function tumSutunlarAcik() {
  localStorage.setItem(SUTUN_ANAHTARI, JSON.stringify({ kirilim: true, firesiz: true, doviz: true, karsilastirma: true, uretim: true }));
}

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => {
  localStorage.clear();
  sunucu.use(http.get("*/api/v1/ambalaj-ozeti", () => HttpResponse.json({ turler: [], kapaklar: [] })));
});

function Yer() {
  const l = useLocation();
  return <output data-testid="yer">{l.pathname + l.search}</output>;
}

function kur() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/?senaryo=1"]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/urunler/:kod" element={<Yer />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Tablo yüklenene dek bekler. Ürün adı yalnız tabloda aranır: grafik kütüphanesi yazı ölçmek için gövdeye gizli bir alan ekler. */
async function yuklendi() {
  await within(await screen.findByRole("table")).findByText("Salatalık Turşusu 720 ml");
}

describe("Dashboard", () => {
  it("3 ürün satırını ve kartları gösterir", async () => {
    kur();
    await yuklendi();
    expect(within(screen.getByRole("table")).getByText("Biber Turşusu 370 ml")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Deneme Ürünü")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("38,13 TL")).toBeInTheDocument();
    const urunKarti = screen.getByText("Ürün sayısı").parentElement as HTMLElement;
    expect(within(urunKarti).getByText("3")).toBeInTheDocument();
    const hataKarti = screen.getByText("Hesaplanamayan ürün").parentElement as HTMLElement;
    expect(within(hataKarti).getByText("1")).toBeInTheDocument();
    await waitFor(() => {
      const k = screen.getByText("Fiyatsız malzeme").parentElement as HTMLElement;
      expect(within(k).getByText("0")).toBeInTheDocument();
    });
  });

  it("hata satırı kırmızı rozetle mesajı gösterir ve sayılar tire olur", async () => {
    tumSutunlarAcik();
    kur();
    await yuklendi();
    const satir = within(screen.getByRole("table")).getByText("Deneme Ürünü").closest("tr") as HTMLElement;
    const rozet = within(satir).getByText("Reçete bulunamadı");
    expect(rozet).toBeInTheDocument();
    expect(rozet.className).toMatch(/text-destructive/);
    expect(within(satir).getAllByText("—").length).toBeGreaterThanOrEqual(10);
  });

  it("Excel'e aktar bağlantısı doğru href ve download taşır", async () => {
    kur();
    await yuklendi();
    const a = screen.getByRole("link", { name: /Excel'e aktar/ });
    expect(a).toHaveAttribute("href", "/api/v1/disa-aktar/urunler.xlsx?senaryo=1");
    expect(a).toHaveAttribute("download");
  });

  it("Tüm maliyet kartları düğmesi doğru adresi çağırır, hazırlanırken 'Hazırlanıyor…' gösterir ve dosyayı indirir", async () => {
    const istekler: string[] = [];
    sunucu.use(
      http.get("*/api/v1/disa-aktar/maliyet-kartlari", async ({ request }) => {
        const u = new URL(request.url);
        istekler.push(u.pathname + u.search);
        await delay(60);
        return new HttpResponse(new Uint8Array([80, 75, 3, 4]), {
          headers: {
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Content-Disposition": 'attachment; filename="maliyet-kartlari-2026-2027-11-13-2026.xlsx"',
          },
        });
      }),
    );
    const adresler = URL as unknown as { createObjectURL?: unknown; revokeObjectURL?: unknown };
    const eski = { c: adresler.createObjectURL, r: adresler.revokeObjectURL };
    adresler.createObjectURL = vi.fn(() => "blob:deneme");
    adresler.revokeObjectURL = vi.fn();
    const indirilen: string[] = [];
    const tikla = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      indirilen.push(`${this.download}|${this.getAttribute("href")}`);
    });
    try {
      kur();
      await yuklendi();
      const dugme = screen.getByRole("button", { name: "Tüm maliyet kartları (ürün başına sayfa)" });
      await userEvent.click(dugme);
      const bekleyen = await screen.findByRole("button", { name: "Hazırlanıyor…" });
      expect(bekleyen).toBeDisabled();
      expect(await screen.findByRole("button", { name: "Tüm maliyet kartları (ürün başına sayfa)" })).toBeEnabled();
      expect(istekler).toEqual(["/api/v1/disa-aktar/maliyet-kartlari?senaryo=1"]);
      expect(indirilen).toEqual(["maliyet-kartlari-2026-2027-11-13-2026.xlsx|blob:deneme"]);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      // mevcut "Bu tablo" bağlantısı yerinde
      expect(screen.getByRole("link", { name: /Excel'e aktar/ })).toHaveAttribute("title", "Bu tablo");
    } finally {
      tikla.mockRestore();
      adresler.createObjectURL = eski.c;
      adresler.revokeObjectURL = eski.r;
    }
  });

  it("Tüm maliyet kartları: sunucu hata verirse mesaj gösterilir, düğme yeniden kullanılabilir", async () => {
    sunucu.use(
      http.get("*/api/v1/disa-aktar/maliyet-kartlari", () =>
        HttpResponse.json({ hata: "bulunamadi", mesaj: "senaryo yok", alanlar: {} }, { status: 404 }),
      ),
    );
    kur();
    await yuklendi();
    await userEvent.click(screen.getByRole("button", { name: "Tüm maliyet kartları (ürün başına sayfa)" }));
    expect(await screen.findByText("senaryo yok")).toHaveAttribute("role", "alert");
    expect(screen.getByRole("button", { name: "Tüm maliyet kartları (ürün başına sayfa)" })).toBeEnabled();
  });

  it("metin arama kod ve ada göre süzer", async () => {
    kur();
    await yuklendi();
    await userEvent.type(screen.getByRole("searchbox", { name: "Ürün ara" }), "biber");
    expect(within(screen.getByRole("table")).queryByText("Salatalık Turşusu 720 ml")).not.toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Biber Turşusu 370 ml")).toBeInTheDocument();
    await userEvent.clear(screen.getByRole("searchbox", { name: "Ürün ara" }));
    await userEvent.type(screen.getByRole("searchbox", { name: "Ürün ara" }), "urun-001");
    expect(within(screen.getByRole("table")).getByText("Salatalık Turşusu 720 ml")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).queryByText("Biber Turşusu 370 ml")).not.toBeInTheDocument();
  });

  it("hat seçimi süzer", async () => {
    kur();
    await yuklendi();
    await userEvent.selectOptions(screen.getByLabelText("Hat"), "Pet Hattı");
    expect(within(screen.getByRole("table")).queryByText("Salatalık Turşusu 720 ml")).not.toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Deneme Ürünü")).toBeInTheDocument();
  });

  it("geçici kodlu anahtarı gecici=true ile sorgular", async () => {
    kur();
    await yuklendi();
    await userEvent.click(screen.getByRole("checkbox", { name: "Geçici kodlu" }));
    await waitFor(() => expect(within(screen.getByRole("table")).queryByText("Salatalık Turşusu 720 ml")).not.toBeInTheDocument());
    expect(within(screen.getByRole("table")).getByText("Deneme Ürünü")).toBeInTheDocument();
  });

  it("toplam satırı yalnızca üretim adedini toplar, maliyet sütunlarında toplam yoktur", async () => {
    kur();
    await yuklendi();
    const alt = document.querySelector("tfoot") as HTMLElement;
    expect(within(alt).getByText("30.000")).toBeInTheDocument();
    expect(within(alt).queryByText(/TL|USD|EUR|%/)).toBeNull();
  });

  it("satıra tıklayınca ürün sayfasına senaryo ile gider", async () => {
    kur();
    await yuklendi();
    await userEvent.click(within(screen.getByRole("table")).getByText("Biber Turşusu 370 ml"));
    expect(await screen.findByTestId("yer")).toHaveTextContent("/urunler/URUN-002?senaryo=1");
  });

  it("uyarı rozeti tıklanınca ürünün uyarılarını listeler", async () => {
    kur();
    await yuklendi();
    await userEvent.click(screen.getByRole("button", { name: "1 uyarı" }));
    expect(await screen.findByText(/Kapak M-77 fiyat listesinde yok/)).toBeInTheDocument();
  });

  it("fiyatsız malzeme kartı Veri Kontrolü sayısını gösterir (tüm kartlar değil); pay uyarısı ayrı şerit olarak tekrarlanmaz", async () => {
    sunucu.use(
      http.get("*/api/v1/tutarlilik", () => HttpResponse.json(tutarlilikSorunlu)),
      http.get("*/api/v1/gider-havuzlari", () =>
        HttpResponse.json({ kayitlar: [], toplam: 0, pay_kontrol: [{ havuz: "uretim", toplam: "0.9" }] }),
      ),
    );
    kur();
    await yuklendi();
    await waitFor(() => {
      const k = screen.getByRole("link", { name: /Fiyatsız malzeme/ });
      expect(k).toHaveTextContent("2");
      expect(k).toHaveAttribute("href", "/veri-kontrolu?senaryo=1");
    });
    expect(screen.getByRole("status", { name: "Veri Kontrolü" })).toBeInTheDocument();
    expect(screen.queryByText(/Gider paylarının toplamı %100 değil/)).not.toBeInTheDocument();
  });

  it("M3: hiç senaryo yoksa boş veritabanı yönergesi ve Veri Aktar bağlantısı gösterilir", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: [], toplam: 0 })));
    kur();
    expect(await screen.findByText(/Henüz senaryo yok/)).toHaveTextContent("Veri Aktar ile Excel'i yükleyin");
    expect(screen.getByRole("link", { name: "Veri Aktar" })).toHaveAttribute("href", "/recete-aktar");
    // Faz 5c: Excel'siz yol — "Yeni çalışma" diyaloğu buradan da açılır.
    await userEvent.click(screen.getByRole("button", { name: "Yeni çalışma" }));
    expect(await screen.findByRole("dialog", { name: "Yeni çalışma" })).toBeInTheDocument();
  });

  it("Faz 5c: senaryo var ama ürün yok — boş durum, üç yol; kopyala düğmesi diyaloğu kopya sekmesiyle açar", async () => {
    sunucu.use(http.get("*/api/v1/urunler", () => HttpResponse.json({ kayitlar: [], toplam: 0, enflasyon_altinda_toplam: 0 })));
    kur();
    expect(await screen.findByRole("heading", { name: "Bu çalışmada henüz ürün yok" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Yeni ürün" })).toHaveAttribute("href", "/veri-girisi?senaryo=1");
    expect(screen.getByRole("link", { name: "Excel yükle" })).toHaveAttribute("href", "/recete-aktar?senaryo=1");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Ürün sayısı")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Geçen sezondan kopyala" }));
    const d = await screen.findByRole("dialog", { name: "Yeni çalışma" });
    expect(within(d).getByRole("tab", { name: "Geçen sezondan kopyala" })).toHaveAttribute("aria-selected", "true");
  });

  it("Faz 5c: tek senaryo varsa kopyala düğmesi görünmez, açıklama gösterilir", async () => {
    sunucu.use(
      http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: [senaryolar[0]], toplam: 1 })),
      http.get("*/api/v1/urunler", () => HttpResponse.json({ kayitlar: [], toplam: 0, enflasyon_altinda_toplam: 0 })),
    );
    kur();
    await screen.findByRole("heading", { name: "Bu çalışmada henüz ürün yok" });
    expect(screen.queryByRole("button", { name: "Geçen sezondan kopyala" })).not.toBeInTheDocument();
    expect(screen.getByText(/Kopyalanacak başka bir çalışma olmadığı için/)).toBeInTheDocument();
  });

  it("Faz 5c: 'Geçici kodlu' süzgeci 0 döndürünce boş durum değil tablo görünür", async () => {
    sunucu.use(
      http.get("*/api/v1/urunler", ({ request }) => {
        const gecici = new URL(request.url).searchParams.get("gecici");
        const k = gecici === "true" ? [] : dashboardSatirlari;
        return HttpResponse.json({ kayitlar: k, toplam: k.length, enflasyon_altinda_toplam: 0 });
      }),
    );
    kur();
    await yuklendi();
    await userEvent.click(screen.getByRole("checkbox", { name: "Geçici kodlu" }));
    expect(await screen.findByText("Ürün bulunamadı")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Bu çalışmada henüz ürün yok" })).not.toBeInTheDocument();
  });

  it("API hatasında hata mesajı gösterir", async () => {
    sunucu.use(
      http.get("*/api/v1/urunler", () => HttpResponse.json({ hata: "sunucu", mesaj: "sunucu hatası", alanlar: {} }, { status: 500 })),
    );
    kur();
    expect(await screen.findByRole("alert")).toHaveTextContent("sunucu hatası");
  });

  it("sayfa değişince hat seçimi sıfırlanır ve sayfa uyarıları görünür", async () => {
    const [a, b, c] = dashboardSatirlari;
    sunucu.use(
      http.get("*/api/v1/urunler", ({ request }) => {
        const sayfa = new URL(request.url).searchParams.get("sayfa");
        const k = sayfa === "2" ? [c] : [a, b];
        return HttpResponse.json({ kayitlar: k, toplam: 1200 });
      }),
    );
    kur();
    await yuklendi();
    expect(screen.getByText(/Bu sayfada 2 \/ 1200 ürün görüntüleniyor; arama ve süzgeçler yalnız bu sayfayı kapsar/)).toBeInTheDocument();
    const hatSecici = screen.getByLabelText("Hat") as HTMLSelectElement;
    await userEvent.selectOptions(hatSecici, "Cam Hattı");
    expect(hatSecici.value).toBe("Cam Hattı");
    await userEvent.click(screen.getByRole("button", { name: "Sonraki" }));
    await screen.findAllByText("Deneme Ürünü");
    expect((screen.getByLabelText("Hat") as HTMLSelectElement).value).toBe("");
    expect(screen.getByRole("option", { name: "Tüm hatlar" })).toBeInTheDocument();
  });
});

describe("Dashboard karşılaştırma sütunları", () => {
  beforeEach(() => tumSutunlarAcik());
  const satirOf = (ad: string) => within(screen.getByRole("table")).getByText(ad).closest("tr") as HTMLElement;

  it("geçen yıl, enflasyon rozeti ve hedef adetle maliyet dolu satırda görünür; null satırda tire", async () => {
    kur();
    await yuklendi();
    expect(screen.getByRole("columnheader", { name: /Geçen yıl \(TL\)/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Enf\. eşiği/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Hedef adetle maliyet \(TL\)/ })).toBeInTheDocument();

    const bir = satirOf("Salatalık Turşusu 720 ml");
    expect(within(bir).getByText("42,50 TL")).toBeInTheDocument();
    const altinda = within(bir).getByText("altında");
    expect(altinda.closest("[data-durum]")).toHaveAttribute("data-durum", "altinda");
    expect(within(bir).getByText("-6,7 %")).toBeInTheDocument();
    expect(within(bir).getByText("36,10 TL")).toBeInTheDocument();
    // Bütçe maliyetinden (38,13) fark: 36,10 - 38,130789 = -2,03
    expect(within(bir).getByText("-2,03 TL")).toBeInTheDocument();

    const iki = satirOf("Biber Turşusu 370 ml");
    expect(within(iki).getByText("üstünde").closest("[data-durum]")).toHaveAttribute("data-durum", "ustunde");
    expect(within(iki).getByText("+4,2 %")).toBeInTheDocument();
    expect(within(iki).getByText("0,00 TL")).toBeInTheDocument();

    // Hatalı satırda yeni sütunlar da tire.
    const hata = satirOf("Deneme Ürünü");
    expect(within(hata).queryByText("altında")).not.toBeInTheDocument();
    expect(within(hata).queryByText("üstünde")).not.toBeInTheDocument();
  });

  it("üst kart enflasyonun altındaki ürün sayısını gösterir", async () => {
    kur();
    await yuklendi();
    // Sunucudaki toplam (7); sayfadaki satırlardan sayılan değer (1) değil.
    const kart = screen.getByText("Enflasyonun altındaki ürün").parentElement as HTMLElement;
    expect(within(kart).getByText("7")).toBeInTheDocument();
  });

  it("ambalaj sütunu sunucu etiketini gösterir (lt ürünü 'ml' eki almaz)", async () => {
    kur();
    await yuklendi();
    expect(screen.getByRole("columnheader", { name: /^Ambalaj/ })).toBeInTheDocument();
    const lt = within(screen.getByRole("table")).getByText("Biber Turşusu 370 ml").closest("tr") as HTMLElement;
    expect(within(lt).getByText("5 lt")).toBeInTheDocument();
    expect(within(lt).queryByText(/5 ml|0,54 ml/)).not.toBeInTheDocument();
    // etiketsiz satır: hacim birimsiz
    const bos = within(screen.getByRole("table")).getByText("Deneme Ürünü").closest("tr") as HTMLElement;
    expect(within(bos).getByText("500")).toBeInTheDocument();
  });

  it("enflasyon süzgeci satırları süzer", async () => {
    kur();
    await yuklendi();
    await userEvent.selectOptions(screen.getByLabelText("Enflasyon eşiği"), "ustunde");
    expect(within(screen.getByRole("table")).queryByText("Salatalık Turşusu 720 ml")).not.toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Biber Turşusu 370 ml")).toBeInTheDocument();
  });

  it("Sütunlar menüsü grubu kapatır ve tercihi localStorage'a yazar", async () => {
    kur();
    await yuklendi();
    await userEvent.click(screen.getByText(/^Sütunlar/));
    await userEvent.click(screen.getByRole("checkbox", { name: /^Karşılaştırma/ }));
    expect(screen.queryByRole("columnheader", { name: /Geçen yıl \(TL\)/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Enf\. eşiği/ })).not.toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(SUTUN_ANAHTARI) ?? "{}")).toMatchObject({ karsilastirma: false, kirilim: true });
  });
});

describe("Dashboard varsayılan sade tablo", () => {
  it("kayıtlı tercih yoksa yalnız temel sütunlar ve üretim adedi görünür; menüden açılan sütun gelir", async () => {
    kur();
    await yuklendi();
    const basliklar = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(basliklar).toEqual(["Kod", "Ürün", "Ambalaj", "Hat", "Maliyet TL", "Satış TL", "Üretim Adedi", "Uyarı", "Durum"]);
    await userEvent.click(screen.getByText(/^Sütunlar/));
    await userEvent.click(screen.getByRole("checkbox", { name: /^Maliyet kırılımı/ }));
    expect(screen.getByRole("columnheader", { name: /GÜG/ })).toBeInTheDocument();
    expect(screen.getByText(/^Sütunlar \(2\)/)).toBeInTheDocument();
  });

  it("'Hesaplanamayan ürün' kartı tabloyu hatalılara süzer; süzgeçleri temizle geri getirir", async () => {
    kur();
    await yuklendi();
    await userEvent.click(screen.getByRole("button", { name: /Hesaplanamayan ürün/ }));
    expect(within(screen.getByRole("table")).queryByText("Salatalık Turşusu 720 ml")).not.toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Deneme Ürünü")).toBeInTheDocument();
    expect(screen.getByText("1 / 3 ürün")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Süzgeçleri temizle/ }));
    expect(within(screen.getByRole("table")).getByText("Salatalık Turşusu 720 ml")).toBeInTheDocument();
  });

  it("'Stokta kalanı olan' süzgeci yalnız stok etkili ürünleri bırakır; 'Ortalama maliyet' sütunu menüden açılır", async () => {
    sunucu.use(
      http.get("*/api/v1/urunler", () => {
        const k = dashboardSatirlari.map((s, i) => ({ ...s, stok_etkisi: i === 1, ortalama_maliyet_tl: i === 1 ? "19.5" : null }));
        return HttpResponse.json({ kayitlar: k, toplam: k.length, enflasyon_altinda_toplam: 0 });
      }),
    );
    kur();
    await yuklendi();
    await userEvent.click(screen.getByRole("checkbox", { name: "Stokta kalanı olan" }));
    expect(within(screen.getByRole("table")).queryByText("Salatalık Turşusu 720 ml")).not.toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Biber Turşusu 370 ml")).toBeInTheDocument();
    expect(screen.getByText("1 / 3 ürün")).toBeInTheDocument();

    await userEvent.click(screen.getByText(/^Sütunlar/));
    await userEvent.click(screen.getByRole("checkbox", { name: /^Ortalama maliyet/ }));
    expect(screen.getByRole("columnheader", { name: /Ortalama maliyet TL/ })).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("19,50 TL")).toBeInTheDocument();
  });
});
