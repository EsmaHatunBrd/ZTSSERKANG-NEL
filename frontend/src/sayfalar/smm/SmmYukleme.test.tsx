import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { kurSayfa } from "@/test/kur-ayarlar";
import type { SmmDonem } from "@/api/tipler";
import SmmReceteler from "./SmmReceteler";
import SmmVeri from "./SmmVeri";

// Excel yükleme güvenliği (Maliyet Muhasebesi): önizleme → uygula, sorunlu satırlar, 409 satır kaybı onayı, son yüklemeyi geri al,
// şablon bağlantısı; düzenleme kilidi ve dönem kilidi.

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
  devir_donem_id: null,
  kilitli: false,
  kilitleyen: null,
  excel_kontrol: null,
} as unknown as SmmDonem;

function durum(d: SmmDonem = donem) {
  return {
    donem: d,
    donem_basi: { kaynak: "devir", dolu: 2, tutar: "480", hazir: true },
    kaynaklar: [
      { kaynak: "sayim", ad: "Sayım (dönem sonu stok)", zorunlu: true, yuklendi: true, dolu: 4, son: null, elle: 0, elle_uyari: null },
    ],
    eksik: [],
    ayarlar: { finansman: "0", gider_720: "0", gider_730: "0" },
    turler: [],
    grupsuz: { kalem: 0, alim_tutar: "0", dbs_tutar: "0", ornek: [] },
    devir: null,
  };
}

const sorunlu = Array.from({ length: 60 }, (_, i) => ({
  satir: i + 3,
  kod: `K-${i + 1}`,
  alan: "Sayım Miktarı",
  deger: "abc",
  neden: "Sayım Miktarı: 'abc' sayıya çevrilemedi; satır yazılmadı",
}));

const onizleme = {
  ...{
    okunan: 62,
    yeni: 1,
    degisen: 1,
    ayni: 0,
    silinecek: 3,
    atlanan: 60,
    sorunlu,
    uyarilar: ["3 kalemin sayım değeri dosyada yok; yüklenirse sıfırlanır."],
  },
  ...{ kaynak: "sayim", ad: "Sayım (dönem sonu stok)", donem, mevcut: 4, dosyadaki: 2, elle_silinecek: 0, yeni_kalem: 1 },
};

const son = {
  id: 11,
  zaman: "2026-11-16T11:20:00",
  olusturan: "esma",
  ozet: "Sayım (dönem sonu stok): 4 kalem",
  kaynak_dosya: "sayim-ekim.xlsx",
};

/** Veri Girişi sunucusu: önizleme, yükleme (ilk istek 409 satır kaybı), son yükleme ve geri al. */
function kur(secenek: { kilitli?: boolean } = {}) {
  const istekler: { yol: string }[] = [];
  let geriAlindi = false;
  sunucu.use(
    http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [{ ...donem, kilitli: Boolean(secenek.kilitli) }] })),
    http.get(`${T}/smm/donemler/:id/veri`, () => HttpResponse.json(durum({ ...donem, kilitli: Boolean(secenek.kilitli) }))),
    http.post(`${T}/smm/donemler/:id/veri/:kaynak/onizle`, () => {
      istekler.push({ yol: "onizle" });
      return HttpResponse.json(onizleme);
    }),
    http.post(`${T}/smm/donemler/:id/veri/:kaynak`, () => {
      // ilk gönderim 409 satır kaybı; onaydan sonraki ikinci gönderim (onay=true) yazar
      const ilk = !istekler.some((x) => x.yol === "yukle");
      istekler.push({ yol: "yukle" });
      if (ilk)
        return HttpResponse.json(
          {
            hata: "catisma",
            mesaj: "Yeni dosyada 2 kalem var, mevcut veride 4. Yüklerseniz 2 kalem silinecek. Emin misiniz?",
            alanlar: { mevcut: 4, yeni: 2, silinecek: 2 },
            kod: "satir_kaybi_onayi",
          },
          { status: 409 },
        );
      return HttpResponse.json({ ...durum(), yukleme: { ...onizleme } });
    }),
    http.get(`${T}/smm/donemler/:id/veri/:kaynak/son-yukleme`, () => HttpResponse.json({ son: geriAlindi ? null : son })),
    http.post(`${T}/smm/donemler/:id/veri/:kaynak/son-yuklemeyi-geri-al`, () => {
      istekler.push({ yol: "geri-al" });
      geriAlindi = true;
      return HttpResponse.json({ geri_alinan: son, mesaj: "Sayım (dönem sonu stok) son yüklemeden önceki hâline döndü." });
    }),
  );
  return istekler;
}

describe("SMM yükleme güvenliği", () => {
  it("Veri Girişi: önizleme sayıları, sorunlu satırlar (ilk 50), şablon bağlantısı; Uygula 409 onayıyla yazılır", async () => {
    const istekler = kur();
    kurSayfa(<SmmVeri />);
    expect(await screen.findByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/sablonlar/smm_sayim.xlsx");
    expect(screen.getByText(/Canias raporunu olduğu gibi yükleyebilirsiniz/)).toBeInTheDocument();
    await userEvent.upload(screen.getByLabelText("Sayım (dönem sonu stok) dosyası"), new File(["x"], "sayim.xlsx"));
    await userEvent.click(screen.getByRole("button", { name: "Önizle — Sayım (dönem sonu stok)" }));
    const on = await screen.findByRole("region", { name: "Önizleme" });
    expect(on).toHaveTextContent("henüz hiçbir şey yazılmadı");
    expect(on).toHaveTextContent("Dosyada 2 kalem; dönemde şu an 4.");
    const ozet = within(on).getByLabelText("Yükleme özeti");
    expect(ozet).toHaveTextContent("Okunan:62");
    expect(ozet).toHaveTextContent("Silinecek:3");
    expect(ozet).toHaveTextContent("Atlanan:60");
    expect(within(on).getByLabelText("Uyarılar")).toHaveTextContent("sıfırlanır");
    const tablo = within(on).getByRole("table", { name: "Sorunlu satırlar" });
    expect(within(tablo).getAllByRole("row")).toHaveLength(51); // başlık + ilk 50
    expect(on).toHaveTextContent("ilk 50 / 60");
    expect(within(on).getByRole("button", { name: "Tümünü Excel indir" })).toBeInTheDocument();
    expect(istekler).toEqual([{ yol: "onizle" }]); // önizleme yazmaz

    await userEvent.click(within(on).getByRole("button", { name: /Uygula/ }));
    const onay = await screen.findByRole("dialog", { name: "2 kalem silinecek. Emin misiniz?" });
    expect(onay).toHaveTextContent("Yeni dosyada 2 satır var, mevcut veride 4.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // 409 onayı hata kutusunda görünmez
    await userEvent.click(within(onay).getByRole("button", { name: "Evet, yükle" }));
    await waitFor(() => expect(istekler.filter((x) => x.yol === "yukle")).toHaveLength(2));
    // yazılmayan sorunlu satırlar yükleme sonrası da söylenir
    expect(await screen.findByText(/60 sorunlu satır yazılmadı/)).toBeInTheDocument();
  });

  it("Veri Girişi: son yükleme şeridi; Geri al onay sorar ve geri alır", async () => {
    const istekler = kur();
    kurSayfa(<SmmVeri />);
    const serit = await screen.findByLabelText("Son yükleme");
    expect(serit).toHaveTextContent("16.11.2026");
    expect(serit).toHaveTextContent("esma, Sayım (dönem sonu stok): 4 kalem (sayim-ekim.xlsx)");
    await userEvent.click(within(serit).getByRole("button", { name: "Geri al" }));
    const d = await screen.findByRole("dialog", { name: "Son yüklemeyi geri al" });
    expect(istekler).toEqual([]);
    await userEvent.click(within(d).getByRole("button", { name: "Geri al" }));
    await waitFor(() => expect(istekler).toEqual([{ yol: "geri-al" }]));
    expect(await screen.findByText("Sayım (dönem sonu stok) son yüklemeden önceki hâline döndü.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Son yükleme")).not.toBeInTheDocument());
  });

  it("Veri Girişi: düzenleme kilitliyken dosya seçimi ve Geri al kapalı", async () => {
    sessionStorage.removeItem("fiyat-calismasi.duzenleme-acik-bitis");
    kur();
    kurSayfa(<SmmVeri />);
    const serit = await screen.findByLabelText("Son yükleme");
    expect(within(serit).getByRole("button", { name: "Geri al" })).toBeDisabled();
    expect(screen.getByLabelText("Sayım (dönem sonu stok) dosyası")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Önizle — Sayım (dönem sonu stok)" })).toBeDisabled();
  });

  it("Veri Girişi: kapanmış dönemde yükleme alanı, şablon bağlantısı ve Geri al görünmez", async () => {
    kur({ kilitli: true });
    kurSayfa(<SmmVeri />);
    expect(await screen.findByText(/veriler değiştirilemez/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Sayım (dönem sonu stok) dosyası")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Şablonu indir/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Son yükleme")).not.toBeInTheDocument();
  });

  it("Reçeteler: önizlemede sorunlu satırlar; az ürünlü döküm 409 onayıyla yüklenir; Canias şablon bağlantısı", async () => {
    const yuklemeler: (string | null)[] = [];
    const recete = {
      satir_sayisi: 2,
      urun_sayisi: 1,
      asama: { "20": 1 },
      alternatifli_urun: 0,
      mevcut_urun: 4,
      eklenecek_urun: 0,
      kalkacak_urun: 3,
      degisecek_urun: 1,
      korunan: [],
      ornek: [],
      ...{ okunan: 3, yeni: 0, degisen: 1, ayni: 0, silinecek: 3, atlanan: 1, uyarilar: [] },
      sorunlu: [
        { satir: 4, kod: "02-1 / AMB-1", alan: "Tüketim Miktarı", deger: "abc", neden: "Tüketim Miktarı: 'abc' sayıya çevrilemedi" },
      ],
    };
    sunucu.use(
      http.get(`${T}/smm/donemler`, () => HttpResponse.json({ kayitlar: [] })),
      http.get(`${T}/smm/receteler`, () =>
        HttpResponse.json({ son_yukleme: null, asama_sayilari: {}, alternatifli_urun: 0, kayitlar: [] }),
      ),
      http.get(`${T}/smm/receteler/son-yukleme`, () => HttpResponse.json({ son: null })),
      http.post(`${T}/smm/receteler/onizle`, () => HttpResponse.json(recete)),
      http.post(`${T}/smm/receteler/yukle`, () => {
        yuklemeler.push(null);
        if (yuklemeler.length === 1)
          return HttpResponse.json(
            { hata: "catisma", mesaj: "…", alanlar: { mevcut: 4, yeni: 1, silinecek: 3 }, kod: "satir_kaybi_onayi" },
            { status: 409 },
          );
        return HttpResponse.json(recete);
      }),
    );
    kurSayfa(<SmmReceteler />);
    expect(await screen.findByRole("link", { name: /Şablonu indir/ })).toHaveAttribute("href", "/api/v1/sablonlar/canias_urun_agaci.xlsx");
    await userEvent.upload(screen.getByLabelText("Reçete dosyası"), new File(["x"], "Reçete.xlsx"));
    await userEvent.click(screen.getByRole("button", { name: "Önizle" }));
    const on = await screen.findByRole("region", { name: "Önizleme" });
    expect(within(on).getByRole("table", { name: "Sorunlu satırlar" })).toHaveTextContent("02-1 / AMB-1");
    expect(within(on).getByLabelText("Yükleme özeti")).toHaveTextContent("Silinecek:3");
    await userEvent.click(screen.getByRole("button", { name: "Yükle" }));
    const onay = await screen.findByRole("dialog", { name: "3 kalem silinecek. Emin misiniz?" });
    await userEvent.click(within(onay).getByRole("button", { name: "Evet, yükle" }));
    await waitFor(() => expect(yuklemeler).toHaveLength(2));
    expect(await screen.findByRole("status")).toHaveTextContent("Yüklendi: 1 ürün");
  });
});
