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
import { OturumSaglayici } from "@/bilesenler/GirisKapisi";
import type { GirisKullanicisi, Rol } from "@/api/sorgular/kimlik";
import ReceteAktar from "./ReceteAktar";
import { RECETESIZ_KOD } from "@/test/fikstur/urunler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
let formYakalayici: ReturnType<typeof formAlanlariniYakala> | null = null;
afterEach(() => {
  sunucu.resetHandlers();
  formYakalayici?.geri();
  formYakalayici = null;
});
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

const kullanici = (rol: Rol) =>
  ({ id: 1, kullanici_adi: "k", ad: "K", rol, aktif: true, sifre_degismeli: false }) as unknown as GirisKullanicisi;

function kur(rol?: Rol) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const sayfa = (
    <MemoryRouter initialEntries={["/recete-aktar?senaryo=1"]}>
      <SenaryoSaglayici>
        <Routes>
          <Route path="/recete-aktar" element={<ReceteAktar />} />
        </Routes>
      </SenaryoSaglayici>
    </MemoryRouter>
  );
  return render(
    <QueryClientProvider client={qc}>
      {rol ? <OturumSaglayici deger={{ girisZorunlu: true, kullanici: kullanici(rol) }}>{sayfa}</OturumSaglayici> : sayfa}
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
    expect(uyari).not.toHaveTextContent("—"); // D6: alanlar eki gösterilmez
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
  it("sayfa başlığı Veri Aktar; ok tuşlarıyla yedi sekme arasında gezilir", async () => {
    kur();
    expect(screen.getByRole("heading", { name: "Veri Aktar" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(7);
    screen.getByRole("tab", { name: "Tüm çalışma kitabı" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Satın alma fiyat listesi" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Stokta kalan" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Ürün reçetesi" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Ürün kodu")).toBeInTheDocument();
  });

  it("satın alma rolü yalnız fiyat listesi sekmesini görür ve o sekme açık gelir", () => {
    kur("satin_alma");
    const sekmeler = screen.getAllByRole("tab");
    expect(sekmeler).toHaveLength(1);
    expect(sekmeler[0]).toHaveAccessibleName("Satın alma fiyat listesi");
    expect(sekmeler[0]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveAttribute("id", "panel-fiyat");
    expect(screen.queryByRole("tab", { name: "Tüm çalışma kitabı" })).not.toBeInTheDocument();
  });

  it("muhasebe rolü tüm sekmeleri görür", () => {
    kur("muhasebe");
    expect(screen.getAllByRole("tab")).toHaveLength(7);
    expect(screen.getByRole("tab", { name: "Tüm çalışma kitabı" })).toHaveAttribute("aria-selected", "true");
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
    await userEvent.type(screen.getByLabelText("Neden (zorunlu)"), "Yeni ürün reçetesi");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    const onay = await screen.findByRole("dialog");
    expect(onay).toHaveTextContent("Neden: Yeni ürün reçetesi");
    await userEvent.click(within(onay).getByRole("button", { name: "Onayla ve kaydet" }));
    expect(await screen.findByText(/Versiyon 4/)).toBeInTheDocument();
    await waitFor(() => expect(yakala).toHaveLength(1));
    expect(yakala[0].kod).toBe("URUN-001");
    expect(yakala[0].senaryo).toBe("1");
    expect(yakala[0].govde).toEqual({
      neden: "Yeni ürün reçetesi",
      satirlar: [{ malzeme_kodu: "M-001", ad: "Salatalık", miktar: "0.45", birim: "kg", dugum_tipi: "yaprak" }],
    });
  });

  it("zorunlu alanlar boşsa göndermez", async () => {
    const yakala: { kod: string; senaryo: string | null; govde: unknown }[] = [];
    sunucu.use(receteEkleYakala(yakala));
    kur();
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    expect(await screen.findByText("Ürün kodu zorunlu")).toBeInTheDocument();
    expect(screen.getByText("Malzeme kodu zorunlu")).toBeInTheDocument();
    expect(screen.getByText("Neden zorunlu: değişikliğin nedenini yazın")).toBeInTheDocument();
    expect(screen.getByLabelText("Neden (zorunlu)")).toHaveAttribute("aria-invalid", "true");
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
    await userEvent.type(screen.getByLabelText("Neden (zorunlu)"), "Deneme");
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
    await userEvent.type(screen.getByLabelText("Neden (zorunlu)"), "Fire düzeltmesi");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    expect(await screen.findByText("Fire % 0 ile 100 arasında olmalı (100 hariç)")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Fire % 1"));
    await userEvent.type(screen.getByLabelText("Fire % 1"), "5,5");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    await userEvent.click(await screen.findByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(yakala).toHaveLength(1));
    expect(yakala[0].govde).toEqual({
      neden: "Fire düzeltmesi",
      satirlar: [{ malzeme_kodu: "M-001", ad: "", miktar: "1", dugum_tipi: "yaprak", fire_override: "0.055" }],
    });
  });

  it("'Mevcut reçeteyi getir' seçili çalışmadaki aktif reçeteyi forma doldurur; düzenlenip gizli alanlar korunarak kaydedilir", async () => {
    const yakala: { kod: string; senaryo: string | null; govde: unknown }[] = [];
    const istenen: { kod: string; senaryo: string | null }[] = [];
    sunucu.use(
      receteEkleYakala(yakala),
      http.get("*/api/v1/urunler/:kod/recete", ({ params, request }) => {
        istenen.push({ kod: String(params.kod), senaryo: new URL(request.url).searchParams.get("senaryo") });
        return HttpResponse.json({
          id: 30,
          versiyon: 5,
          kaynak: "excel",
          satirlar: [
            {
              sira: 1,
              malzeme_kodu: "M-001",
              ad: "Pet Şişe",
              miktar: "1",
              birim: "adet",
              dugum_tipi: "yaprak",
              fire_override: null,
              brut_miktar_elle: null,
              birim_fiyat_elle: null,
              fire_orani: "0.02",
              fire_kaynagi: "tip:ambalaj",
              seviye: 1,
              zs_elle: null,
              para_birimi_elle: null,
            },
            {
              sira: 2,
              malzeme_kodu: "M-050",
              ad: "Salamura",
              miktar: "0.35",
              birim: "kg",
              dugum_tipi: "yaprak",
              fire_override: "0.055",
              brut_miktar_elle: null,
              birim_fiyat_elle: "12.4",
              fire_orani: "0.055",
              fire_kaynagi: "satir",
              seviye: 1,
              zs_elle: "Z",
              para_birimi_elle: "USD",
            },
          ],
        });
      }),
    );
    kur();
    await waitFor(() => expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("1"));
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    await userEvent.type(screen.getByLabelText("Ürün kodu"), "URUN-001");
    await userEvent.click(screen.getByRole("button", { name: "Mevcut reçeteyi getir" }));
    expect(await screen.findByText("Mevcut reçete getirildi: Versiyon 5, 2 satır. Düzenleyip kaydedin.")).toBeInTheDocument();
    expect(istenen.at(-1)).toEqual({ kod: "URUN-001", senaryo: "1" });
    expect(screen.getByLabelText("Malzeme kodu 1")).toHaveValue("M-001");
    expect(screen.getByLabelText("Fire % 1")).toHaveValue(""); // kuraldan gelen fire forma yazılmaz
    expect(screen.getByLabelText("Miktar 2")).toHaveValue("0,35");
    expect(screen.getByLabelText("Fire % 2")).toHaveValue("5,5");
    expect(screen.getByLabelText("Elle birim fiyat 2")).toHaveValue("12,4");

    // Düzenle: 2. satırın miktarı değişir, 1. satır silinir; dolu formda yeniden getirmek onay ister.
    await userEvent.clear(screen.getByLabelText("Miktar 2"));
    await userEvent.type(screen.getByLabelText("Miktar 2"), "0,4");
    await userEvent.click(screen.getByRole("button", { name: "Mevcut reçeteyi getir" }));
    const soru = await screen.findByRole("dialog", { name: "Formdaki satırlar değişecek" });
    await userEvent.click(within(soru).getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByLabelText("Miktar 2")).toHaveValue("0,4");
    await userEvent.click(screen.getByRole("button", { name: "Satır 1 sil" }));
    await userEvent.type(screen.getByLabelText("Neden (zorunlu)"), "Pet şişe çıkarıldı");
    await userEvent.click(screen.getByRole("button", { name: "Reçeteyi kaydet" }));
    await userEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Onayla ve kaydet" }));
    await waitFor(() => expect(yakala).toHaveLength(1));
    expect(yakala[0].govde).toEqual({
      neden: "Pet şişe çıkarıldı",
      satirlar: [
        {
          malzeme_kodu: "M-050",
          ad: "Salamura",
          miktar: "0.4",
          birim: "kg",
          dugum_tipi: "yaprak",
          fire_override: "0.055",
          birim_fiyat_elle: "12.4",
          seviye: 1,
          zs_elle: "Z",
          para_birimi_elle: "USD",
        },
      ],
    });
  });

  it("reçetesi olmayan ürün için getir bilgi verir; bilinmeyen ürün kodunda hata gösterir", async () => {
    kur();
    await waitFor(() => expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("1"));
    await userEvent.click(screen.getByRole("tab", { name: "Ürün reçetesi" }));
    await userEvent.type(screen.getByLabelText("Ürün kodu"), RECETESIZ_KOD);
    await userEvent.click(screen.getByRole("button", { name: "Mevcut reçeteyi getir" }));
    expect(await screen.findByText(RECETESIZ_KOD + " ürününün bu çalışmada reçetesi yok; satırları elle girin.")).toBeInTheDocument();
    await userEvent.clear(screen.getByLabelText("Ürün kodu"));
    await userEvent.type(screen.getByLabelText("Ürün kodu"), "YOK");
    await userEvent.click(screen.getByRole("button", { name: "Mevcut reçeteyi getir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/ürün yok|bulunamadı/i);
  });
});
