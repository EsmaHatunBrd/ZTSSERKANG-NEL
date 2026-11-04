import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { tamamlaOzeti } from "@/test/fikstur/aktar";
import {
  excelTamBasarili,
  excelTamHatasi,
  formAlanlariniYakala,
  receteEkleYakala,
  type YakalananImport,
} from "@/test/msw/isleyiciler-aktar";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import ReceteAktar from "./ReceteAktar";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
let formYakalayici: ReturnType<typeof formAlanlariniYakala> | null = null;
afterEach(() => {
  sunucu.resetHandlers();
  formYakalayici?.geri();
  formYakalayici = null;
});
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function kur() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/recete-aktar?senaryo=1"]}>
        <SenaryoSaglayici>
          <Routes>
            <Route path="/recete-aktar" element={<ReceteAktar />} />
          </Routes>
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const xlsx = () => new File(["x"], "fiyat.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

describe("ReceteAktar - tüm çalışma kitabı", () => {
  it("dosyasız gönderilmez ve hata gösterir", async () => {
    const yakala: YakalananImport[] = [];
    sunucu.use(excelTamBasarili(yakala));
    kur();
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    expect(await screen.findByText("Excel dosyası seçin")).toBeInTheDocument();
    expect(yakala).toHaveLength(0);
  });

  it(".xlsx olmayan dosyayı ve hatalı sezonu reddeder", async () => {
    const yakala: YakalananImport[] = [];
    sunucu.use(excelTamBasarili(yakala));
    kur();
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), new File(["x"], "a.csv", { type: "text/csv" }), {
      applyAccept: false,
    });
    const sezon = screen.getByLabelText("Sezon adı");
    await userEvent.clear(sezon);
    await userEvent.type(sezon, "2026");
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    expect(await screen.findByText("Yalnızca .xlsx dosyası yüklenebilir")).toBeInTheDocument();
    expect(screen.getByText("Sezon YYYY-YYYY biçiminde olmalı")).toBeInTheDocument();
    expect(yakala).toHaveLength(0);
  });

  it("başarıda form alanlarını gönderir ve özet kartlarını gösterir", async () => {
    const yakala: YakalananImport[] = [];
    const form = (formYakalayici = formAlanlariniYakala());
    sunucu.use(excelTamBasarili(yakala));
    kur();
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await userEvent.click(screen.getByLabelText("Kartları güncelle"));
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));

    const ozet = await screen.findByRole("region", { name: "İçe aktarma özeti" });
    const kart = (ad: string) => within(ozet).getByText(ad, { selector: "[data-kart-baslik]" }).parentElement as HTMLElement;
    expect(within(kart("Malzeme")).getByText("412")).toBeInTheDocument();
    expect(within(kart("Ürün")).getByText("85")).toBeInTheDocument();
    expect(within(kart("Atlanan")).getByText("2")).toBeInTheDocument();
    expect(within(kart("Uyarılar")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Kart farkları")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Yeniden adlandırılan")).getByText("1")).toBeInTheDocument();
    expect(within(kart("Revize fiyat (S.ALMA BF I)")).getByText("23")).toBeInTheDocument();
    expect(within(ozet).getByText("Cam 720 → Cam 720 ml")).toBeInTheDocument();
    const link = within(ozet).getByRole("link", { name: "Genel Bakış'a git" });
    expect(link).toHaveAttribute("href", "/genel-bakis?senaryo=7");

    expect(yakala).toHaveLength(1);
    expect(yakala[0].icerikTuru).toMatch(/^multipart\/form-data; boundary=/);
    const a = form.alanlar;
    expect((a.dosya as File).name).toBe("fiyat.xlsx");
    expect(a.sezon_ad).toBe("2026-2027");
    expect(a.tur).toBe("fiyat_calismasi");
    expect(a.kartlari_guncelle).toBe("true");
  });

  it("422 hata gövdesini Türkçe gösterir", async () => {
    sunucu.use(excelTamHatasi());
    kur();
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    const uyari = await screen.findByRole("alert");
    expect(uyari).toHaveTextContent("Dosya beklenen çalışma kitabı yapısında değil");
    expect(uyari).toHaveTextContent("sayfa");
  });
});

describe("ReceteAktar - mevcut senaryoyu tamamla", () => {
  it("varsayılan mod yok; yeni senaryo seçilince sezon/senaryo/tür gider, senaryo_id gitmez", async () => {
    const yakala: YakalananImport[] = [];
    const form = (formYakalayici = formAlanlariniYakala());
    sunucu.use(excelTamBasarili(yakala));
    kur();
    // Varsayılan mod yok: seçilmeden İçe aktar kapalı ve sezon alanları görünmez.
    expect(screen.getByRole("radio", { name: "Yeni senaryo oluştur" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Mevcut senaryoyu tamamla (seçili senaryo)" })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "İçe aktar" })).toBeDisabled();
    expect(screen.getByText("Önce aktarım modunu seçin.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Sezon adı")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    await screen.findByRole("region", { name: "İçe aktarma özeti" });
    expect(form.alanlar.senaryo_ad).toBe("Fiyat Çalışması");
    expect("senaryo_id" in form.alanlar).toBe(false);
  });

  it("tamamla modunda sezon/senaryo/tür gizlenir; yalnız dosya ve senaryo_id gider; özet kapasite, parametre ve notu gösterir", async () => {
    const yakala: YakalananImport[] = [];
    const form = (formYakalayici = formAlanlariniYakala());
    sunucu.use(excelTamBasarili(yakala, tamamlaOzeti));
    kur();
    await userEvent.click(screen.getByRole("radio", { name: "Mevcut senaryoyu tamamla (seçili senaryo)" }));
    expect(screen.queryByLabelText("Sezon adı")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Senaryo adı")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Tür")).not.toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));

    const ozet = await screen.findByRole("region", { name: "İçe aktarma özeti" });
    expect(within(ozet).getByRole("heading", { name: "Mevcut senaryo tamamlandı" })).toBeInTheDocument();
    const kart = (ad: string) => within(ozet).getByText(ad, { selector: "[data-kart-baslik]" }).parentElement as HTMLElement;
    expect(within(kart("Üretim adedi (kapasite)")).getByText("71")).toBeInTheDocument();
    expect(within(kart("Parametre")).getByText("3")).toBeInTheDocument();
    expect(within(kart("Satış fiyatı notu")).getByText("1")).toBeInTheDocument();

    expect(yakala).toHaveLength(1);
    expect(Object.keys(form.alanlar).sort()).toEqual(["dosya", "senaryo_id"]);
    expect(form.alanlar.senaryo_id).toBe("1");
  });

  it("tamamla modunda dosyasız gönderilmez", async () => {
    const yakala: YakalananImport[] = [];
    sunucu.use(excelTamBasarili(yakala, tamamlaOzeti));
    kur();
    await userEvent.click(screen.getByRole("radio", { name: "Mevcut senaryoyu tamamla (seçili senaryo)" }));
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    expect(await screen.findByText("Excel dosyası seçin")).toBeInTheDocument();
    expect(yakala).toHaveLength(0);
  });
});

describe("ReceteAktar - tam kitap onayı", () => {
  const ayniAdliSenaryo = () =>
    http.get("*/api/v1/senaryolar", () =>
      HttpResponse.json({
        kayitlar: [{ id: 9, sezon_ad: "2026-2027", tur: "fiyat_calismasi", ad: "Fiyat Çalışması" }],
        toplam: 1,
      }),
    );

  it("aynı sezon ve adda senaryo varsa onay ister; vazgeçilirse yüklenmez, onaylanırsa yüklenir", async () => {
    const yakala: YakalananImport[] = [];
    sunucu.use(ayniAdliSenaryo(), excelTamBasarili(yakala));
    kur();
    await waitFor(() => expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("9"));
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("Aynı adda senaryo var (#9). Yine de yeni senaryo oluşturulsun mu?");
    expect(yakala).toHaveLength(0);
    await userEvent.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(yakala).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Yine de oluştur" }));
    await waitFor(() => expect(yakala).toHaveLength(1));
  });

  it("senaryo adı farklıysa onay sormadan yükler", async () => {
    const yakala: YakalananImport[] = [];
    sunucu.use(ayniAdliSenaryo(), excelTamBasarili(yakala));
    kur();
    await waitFor(() => expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("9"));
    await userEvent.click(screen.getByRole("radio", { name: "Yeni senaryo oluştur" }));
    await userEvent.upload(screen.getByLabelText("Excel dosyası"), xlsx());
    const ad = screen.getByLabelText("Senaryo adı");
    await userEvent.clear(ad);
    await userEvent.type(ad, "Başka Ad");
    await userEvent.click(screen.getByRole("button", { name: "İçe aktar" }));
    await waitFor(() => expect(yakala).toHaveLength(1));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("ReceteAktar - Veri Aktar sekmeleri", () => {
  it("sayfa başlığı Veri Aktar; ok tuşlarıyla altı sekme arasında gezilir", async () => {
    kur();
    expect(screen.getByRole("heading", { name: "Veri Aktar" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(6);
    screen.getByRole("tab", { name: "Tüm çalışma kitabı" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Satın alma fiyat listesi" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Ürün reçetesi" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Ürün kodu")).toBeInTheDocument();
  });
});

describe("ReceteAktar - elle reçete satırı", () => {
  it("satırı senaryo ile gönderir ve sonucu gösterir", async () => {
    const yakala: { kod: string; senaryo: string | null; govde: unknown }[] = [];
    sunucu.use(receteEkleYakala(yakala));
    kur();
    await waitFor(() => expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("1"));
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    // Sekmede önce dosyadan aktarım, altında elle giriş: "yakında" notu kalktı.
    expect(screen.getByRole("form", { name: "Dosyadan reçete aktar" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Elle reçete girişi" })).toBeInTheDocument();
    expect(screen.queryByText(/yakında/)).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Ürün kodu"), "URUN-001");
    await userEvent.type(screen.getByLabelText("Malzeme kodu 1"), "M-001");
    await userEvent.type(screen.getByLabelText("Ad 1"), "Salatalık");
    await userEvent.type(screen.getByLabelText("Miktar 1"), "0,45");
    await userEvent.type(screen.getByLabelText("Birim 1"), "kg");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    const onay = await screen.findByRole("dialog");
    await userEvent.click(within(onay).getByRole("button", { name: "Onayla ve kaydet" }));
    expect(await screen.findByText(/Versiyon 4/)).toBeInTheDocument();
    await waitFor(() => expect(yakala).toHaveLength(1));
    expect(yakala[0].kod).toBe("URUN-001");
    expect(yakala[0].senaryo).toBe("1");
    expect(yakala[0].govde).toEqual([{ malzeme_kodu: "M-001", ad: "Salatalık", miktar: "0.45", birim: "kg", dugum_tipi: "yaprak" }]);
  });

  it("zorunlu alanlar boşsa göndermez", async () => {
    const yakala: { kod: string; senaryo: string | null; govde: unknown }[] = [];
    sunucu.use(receteEkleYakala(yakala));
    kur();
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    expect(await screen.findByText("Ürün kodu zorunlu")).toBeInTheDocument();
    expect(screen.getByText("Malzeme kodu zorunlu")).toBeInTheDocument();
    expect(yakala).toHaveLength(0);
  });

  it("kaydetmeden önce mevcut ve yeni satır sayısını gösteren onay ister; vazgeçilirse gönderilmez", async () => {
    const yakala: { kod: string; senaryo: string | null; govde: unknown }[] = [];
    sunucu.use(receteEkleYakala(yakala));
    kur();
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    await userEvent.type(screen.getByLabelText("Ürün kodu"), "URUN-001");
    await userEvent.type(screen.getByLabelText("Malzeme kodu 1"), "M-001");
    await userEvent.type(screen.getByLabelText("Miktar 1"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    const onay = await screen.findByRole("dialog");
    await waitFor(() => expect(onay).toHaveTextContent("Mevcut reçete 1 satır → yeni 1 satır; tüm reçete değiştirilecek"));
    expect(yakala).toHaveLength(0);
    await userEvent.click(within(onay).getByRole("button", { name: "Vazgeç" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(yakala).toHaveLength(0);
  });

  it("fire yüzde (0-100) olarak girilir ve orana çevrilerek gönderilir; 100 ve üstü reddedilir", async () => {
    const yakala: { kod: string; senaryo: string | null; govde: unknown }[] = [];
    sunucu.use(receteEkleYakala(yakala));
    kur();
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    await userEvent.type(screen.getByLabelText("Ürün kodu"), "URUN-001");
    await userEvent.type(screen.getByLabelText("Malzeme kodu 1"), "M-001");
    await userEvent.type(screen.getByLabelText("Miktar 1"), "1");
    await userEvent.type(screen.getByLabelText("Fire % 1"), "150");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    expect(await screen.findByText("Fire % 0 ile 100 arasında olmalı (100 hariç)")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Fire % 1"));
    await userEvent.type(screen.getByLabelText("Fire % 1"), "5,5");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    await userEvent.click(await screen.findByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(yakala).toHaveLength(1));
    expect(yakala[0].govde).toEqual([{ malzeme_kodu: "M-001", ad: "", miktar: "1", dugum_tipi: "yaprak", fire_override: "0.055" }]);
  });
});
