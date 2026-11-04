import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { girisModunuAyarla } from "@/api/istemci";
import { kurSayfa } from "@/test/kur-ayarlar";
import AnaSayfa from "@/sayfalar/AnaSayfa";
import Kullanicilar from "@/sayfalar/Kullanicilar";
import { GirisKapisi, OturumSaglayici, useOturum } from "./GirisKapisi";
import type { GirisKullanicisi } from "@/api/sorgular/kimlik";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  sunucu.resetHandlers();
  girisModunuAyarla(false);
});
afterAll(() => sunucu.close());

const T = "*/api/v1";
const gd: GirisKullanicisi = {
  id: 1,
  kullanici_adi: "genel.direktor",
  ad: "Genel Direktör",
  rol: "genel_direktor",
  rol_ad: "Genel Direktör",
  aktif: true,
  sifre_degismeli: false,
};
const yetkisiz = () => HttpResponse.json({ hata: "giris", mesaj: "giriş yapılmamış", alanlar: {}, kod: null }, { status: 401 });

function Icerik() {
  const { kullanici } = useOturum();
  return <p>uygulama: {kullanici?.ad ?? "girişsiz"}</p>;
}

function kapi() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <GirisKapisi>
        <Icerik />
      </GirisKapisi>
    </QueryClientProvider>,
  );
}

describe("GirisKapisi", () => {
  it("oturum yoksa giriş ekranı; doğru girişte uygulama açılır, yanlışta mesaj", async () => {
    let govde: unknown = null;
    sunucu.use(
      http.get(`${T}/kimlik/ben`, yetkisiz),
      http.post(`${T}/kimlik/giris`, async ({ request }) => {
        govde = await request.json();
        const g = govde as { sifre: string };
        if (g.sifre !== "dogru-sifre") {
          return HttpResponse.json({ hata: "giris", mesaj: "kullanıcı adı ya da şifre yanlış", alanlar: {}, kod: null }, { status: 401 });
        }
        return HttpResponse.json({ giris_zorunlu: true, kullanici: gd });
      }),
    );
    kapi();
    const u = userEvent.setup();
    await u.type(await screen.findByLabelText("Kullanıcı adı"), "genel.direktor");
    await u.type(screen.getByLabelText("Şifre"), "yanlis");
    await u.click(screen.getByRole("button", { name: /Giriş yap/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("kullanıcı adı ya da şifre yanlış");
    await u.clear(screen.getByLabelText("Şifre"));
    await u.type(screen.getByLabelText("Şifre"), "dogru-sifre");
    await u.click(screen.getByRole("button", { name: /Giriş yap/ }));
    expect(await screen.findByText("uygulama: Genel Direktör")).toBeInTheDocument();
    expect(govde).toEqual({ kullanici_adi: "genel.direktor", sifre: "dogru-sifre" });
  });

  it("giriş ekranındayken oturum yeniden sorulursa form sökülmez, yazılanlar silinmez", async () => {
    sunucu.use(http.get(`${T}/kimlik/ben`, yetkisiz));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <GirisKapisi>
          <Icerik />
        </GirisKapisi>
      </QueryClientProvider>,
    );
    const u = userEvent.setup();
    await u.type(await screen.findByLabelText("Kullanıcı adı"), "genel.direktor");
    await u.type(screen.getByLabelText("Şifre"), "yarim");
    await qc.invalidateQueries({ queryKey: ["kimlik", "ben"] });
    expect(screen.queryByText("Yükleniyor…")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Kullanıcı adı")).toHaveValue("genel.direktor");
    expect(screen.getByLabelText("Şifre")).toHaveValue("yarim");
  });

  it("geçici şifreyle girilmişse önce kendi şifresini belirler", async () => {
    sunucu.use(
      http.get(`${T}/kimlik/ben`, () => HttpResponse.json({ giris_zorunlu: true, kullanici: { ...gd, sifre_degismeli: true } })),
      http.post(`${T}/kimlik/sifre`, () => HttpResponse.json(gd)),
    );
    kapi();
    const u = userEvent.setup();
    await u.type(await screen.findByLabelText("Geçici şifre"), "gecici12");
    await u.type(screen.getByLabelText("Yeni şifre"), "kisa");
    expect(screen.getByRole("alert")).toHaveTextContent("en az 8 karakter");
    await u.clear(screen.getByLabelText("Yeni şifre"));
    await u.type(screen.getByLabelText("Yeni şifre"), "yeni-sifre-1");
    await u.type(screen.getByLabelText("Yeni şifre (tekrar)"), "yeni-sifre-1");
    await u.click(screen.getByRole("button", { name: /Şifreyi kaydet/ }));
    expect(await screen.findByText("uygulama: Genel Direktör")).toBeInTheDocument();
  });

  it("girişi zorunlu tutmayan sunucuda uygulama doğrudan açılır", async () => {
    sunucu.use(http.get(`${T}/kimlik/ben`, () => HttpResponse.json({ giris_zorunlu: false, kullanici: null })));
    kapi();
    expect(await screen.findByText("uygulama: girişsiz")).toBeInTheDocument();
  });

  it("oturum düşerse (bir istek 401) giriş ekranına dönülür", async () => {
    let girisli = true;
    sunucu.use(http.get(`${T}/kimlik/ben`, () => (girisli ? HttpResponse.json({ giris_zorunlu: true, kullanici: gd }) : yetkisiz())));
    kapi();
    expect(await screen.findByText("uygulama: Genel Direktör")).toBeInTheDocument();
    girisli = false;
    sunucu.use(http.get(`${T}/senaryolar`, yetkisiz));
    const { api } = await import("@/api/istemci");
    await api.GET("/api/v1/senaryolar");
    expect(await screen.findByLabelText("Kullanıcı adı")).toBeInTheDocument();
  });
});

describe("Ana Sayfa", () => {
  it("menüdeki bölümler kart olarak, seçili çalışmayla; izleyici Veri girişi kartlarını görmez", async () => {
    kurSayfa(
      <OturumSaglayici deger={{ girisZorunlu: true, kullanici: { ...gd, rol: "izleyici", rol_ad: "İzleyici", ad: "Ali" } }}>
        <AnaSayfa />
      </OturumSaglayici>,
    );
    expect(await screen.findByRole("heading", { name: "Hoş geldiniz" })).toBeInTheDocument();
    const calisma = screen.getByRole("region", { name: "Çalışma" });
    expect(within(calisma).getByRole("link", { name: /Genel Bakış/ })).toHaveAttribute("href", expect.stringMatching(/^\/genel-bakis/));
    expect(within(calisma).queryByRole("link", { name: /Ana Sayfa/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Veri girişi" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Yönetim" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(within(calisma).getByRole("link", { name: /Genel Bakış/ })).toHaveAttribute("href", "/genel-bakis?senaryo=1"),
    );
  });
});

describe("Kullanıcılar", () => {
  it("Genel Direktör kullanıcı ekler; geçici şifre bilgisi gösterilir; rol değişikliği gönderilir", async () => {
    let eklenen: Record<string, string> | null = null;
    let yama: unknown = null;
    const kayitlar = [gd, { ...gd, id: 2, kullanici_adi: "ayse", ad: "Ayşe", rol: "muhasebe" as const, rol_ad: "Muhasebe" }];
    sunucu.use(
      http.get(`${T}/kullanicilar`, () => HttpResponse.json({ kayitlar, toplam: 2, roller: {} })),
      http.post(`${T}/kullanicilar`, async ({ request }) => {
        eklenen = (await request.json()) as Record<string, string>;
        return HttpResponse.json(
          { ...gd, id: 3, ad: eklenen.ad, kullanici_adi: eklenen.kullanici_adi, rol: "satin_alma", sifre_degismeli: true },
          { status: 201 },
        );
      }),
      http.patch(`${T}/kullanicilar/2`, async ({ request }) => {
        yama = await request.json();
        return HttpResponse.json(kayitlar[1]);
      }),
    );
    kurSayfa(
      <OturumSaglayici deger={{ girisZorunlu: true, kullanici: gd }}>
        <Kullanicilar />
      </OturumSaglayici>,
    );
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Ad soyad"), "Mehmet Kaya");
    await u.type(screen.getByLabelText("Kullanıcı adı"), "Mehmet.Kaya");
    await u.selectOptions(screen.getByLabelText("Rol"), "satin_alma");
    const sifre = (screen.getByLabelText("Geçici şifre") as HTMLInputElement).value;
    expect(sifre).toHaveLength(10);
    await u.click(screen.getByRole("button", { name: /Kullanıcıyı ekle/ }));
    expect(await screen.findByRole("status")).toHaveTextContent(`geçici şifre: ${sifre}`);
    expect(eklenen).toEqual({ ad: "Mehmet Kaya", kullanici_adi: "mehmet.kaya", rol: "satin_alma", gecici_sifre: sifre });
    await u.selectOptions(await screen.findByLabelText("Rol — Ayşe"), "izleyici");
    await waitFor(() => expect(yama).toEqual({ rol: "izleyici" }));
    // kendini pasifleştiremez
    const benimSatir = screen.getByText("siz").closest("tr") as HTMLElement;
    expect(within(benimSatir).getByRole("button", { name: "Pasifleştir" })).toBeDisabled();
  });

  it("Genel Direktör olmayana sayfa kapalı", () => {
    kurSayfa(
      <OturumSaglayici deger={{ girisZorunlu: true, kullanici: { ...gd, rol: "muhasebe", rol_ad: "Muhasebe" } }}>
        <Kullanicilar />
      </OturumSaglayici>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("yalnız Genel Direktör");
  });
});
