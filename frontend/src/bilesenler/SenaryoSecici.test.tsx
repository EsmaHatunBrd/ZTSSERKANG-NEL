import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useLocation } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { senaryolar } from "@/test/fikstur/urunler";
import { SenaryoSecici, SenaryoSaglayici, useSenaryo } from "./SenaryoSecici";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function Gosterge() {
  const { senaryoId } = useSenaryo();
  const loc = useLocation();
  return (
    <>
      <output data-testid="id">{String(senaryoId)}</output>
      <output data-testid="arama">{loc.search}</output>
    </>
  );
}

function kur(yol = "/") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[yol]}>
        <SenaryoSaglayici>
          <SenaryoSecici />
          <Gosterge />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SenaryoSecici", () => {
  it("URL'de senaryo yoksa ilk senaryoyu seçer ve URL ile localStorage'a yazar", async () => {
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    // URL ve localStorage yazımı seçimden sonraki efekte düşer: yük altında bir sonraki commit'te gelebilir.
    await waitFor(() => expect(screen.getByTestId("arama")).toHaveTextContent("?senaryo=1"));
    expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("1");
  });

  it("seçenekler #id · sezon · ad · tür biçiminde gösterilir", async () => {
    kur();
    const secenekler = await screen.findAllByRole("option");
    expect(secenekler[0]).toHaveTextContent("#1 · 2026-2027 · Varsayılan · Fiyat çalışması");
    expect(secenekler[1]).toHaveTextContent("#2 · 2026-2027 · Gerçekleşen · Gerçekleşen");
  });

  it("URL'deki senaryoyu kullanır", async () => {
    kur("/?senaryo=2");
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("2"));
  });

  it("localStorage'daki son seçimi kullanır", async () => {
    localStorage.setItem("fiyat-calismasi.senaryo", "2");
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("2"));
  });

  it("seçim değişince URL ve localStorage güncellenir", async () => {
    const u = userEvent.setup();
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    await u.selectOptions(screen.getByLabelText("Senaryo"), "2");
    expect(screen.getByTestId("id")).toHaveTextContent("2");
    expect(screen.getByTestId("arama")).toHaveTextContent("?senaryo=2");
    expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("2");
  });
});

describe("SenaryoSecici — Faz 5c: yeni çalışma, düzenle, sil", () => {
  it("'Yeni çalışma' düğmesi diyaloğu açar", async () => {
    const u = userEvent.setup();
    kur();
    await u.click(await screen.findByRole("button", { name: "Yeni çalışma" }));
    expect(await screen.findByRole("dialog", { name: "Yeni çalışma" })).toBeInTheDocument();
  });

  it("Boş çalışma açılınca liste tazelenir ve seçim yeni senaryoya geçer (URL ?senaryo=3)", async () => {
    const u = userEvent.setup();
    let liste = [...senaryolar];
    sunucu.use(
      http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: liste, toplam: liste.length })),
      http.post("*/api/v1/senaryolar", async ({ request }) => {
        const g = (await request.json()) as { sezon_ad: string; ad: string; tur: "fiyat_calismasi" | "gerceklesen" };
        const yeni = { id: 3, sezon_ad: g.sezon_ad, ad: g.ad, tur: g.tur, kilitli: false, aciklama: null, urun_sayisi: 0 };
        liste = [...liste, yeni];
        return HttpResponse.json(yeni, { status: 201 });
      }),
    );
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    await u.click(screen.getByRole("button", { name: "Yeni çalışma" }));
    const d = await screen.findByRole("dialog", { name: "Yeni çalışma" });
    await u.type(within(d).getByLabelText("Sezon adı"), "2027-2028");
    await u.click(within(d).getByRole("button", { name: "Boş çalışma aç" }));
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("3"));
    expect(screen.getByTestId("arama")).toHaveTextContent("?senaryo=3");
    expect(localStorage.getItem("fiyat-calismasi.senaryo")).toBe("3");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByRole("option", { name: /#3 · 2027-2028 · Fiyat çalışması/ })).toBeInTheDocument();
  });

  it("senaryo yokken 'Senaryo yok' ve Yeni çalışma düğmesi görünür", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: [], toplam: 0 })));
    kur();
    expect(await screen.findByText("Senaryo yok")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeni çalışma" })).toBeInTheDocument();
  });

  it("menü → Düzenle: neden zorunlu; yalnız değişen alan + neden PATCH edilir ve diyalog kapanır", async () => {
    const u = userEvent.setup();
    const kayit: { yol: string; govde: Record<string, unknown> }[] = [];
    sunucu.use(
      http.patch("*/api/v1/senaryolar/:id", async ({ request }) => {
        kayit.push({ yol: new URL(request.url).pathname, govde: (await request.json()) as Record<string, unknown> });
        return HttpResponse.json({ ...senaryolar[0], ad: "Bütçe" });
      }),
    );
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    await u.click(screen.getByRole("button", { name: "Senaryo işlemleri" }));
    await u.click(screen.getByRole("menuitem", { name: "Düzenle…" }));
    const d = await screen.findByRole("dialog", { name: "Çalışmayı düzenle" });
    const ad = within(d).getByLabelText("Çalışma adı");
    expect(ad).toHaveValue("Varsayılan");
    await u.click(within(d).getByRole("button", { name: "Kaydet" }));
    expect(await within(d).findByRole("alert")).toHaveTextContent("Neden zorunlu");
    expect(kayit).toHaveLength(0);
    await u.clear(ad);
    await u.type(ad, "Bütçe");
    await u.type(within(d).getByLabelText("Neden"), "Ad düzeltme");
    await u.click(within(d).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(kayit).toHaveLength(1));
    expect(kayit[0]).toEqual({ yol: "/api/v1/senaryolar/1", govde: { ad: "Bütçe", neden: "Ad düzeltme" } });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("menü → Sil: onay diyaloğu; 409'da sunucu mesajı gösterilir, diyalog açık kalır, seçim değişmez", async () => {
    const u = userEvent.setup();
    kur("/?senaryo=2");
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("2"));
    await u.click(screen.getByRole("button", { name: "Senaryo işlemleri" }));
    await u.click(screen.getByRole("menuitem", { name: "Sil…" }));
    const d = await screen.findByRole("dialog", { name: /Çalışmayı sil: 2026-2027 · Gerçekleşen/ });
    expect(d).toHaveTextContent(/geri alınamaz/);
    expect(d).toHaveTextContent(/otomatik yedek/);
    await u.click(within(d).getByRole("button", { name: "Sil" }));
    expect(await within(d).findByRole("alert")).toHaveTextContent("Kayıtlı hesabı olan senaryo silinemez");
    expect(screen.getByTestId("id")).toHaveTextContent("2");
  });

  it("Sil başarılı: DELETE /senaryolar/{id} gider, seçim kalan senaryoya düşer", async () => {
    const u = userEvent.setup();
    let liste = [...senaryolar];
    const silinen: string[] = [];
    sunucu.use(
      http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: liste, toplam: liste.length })),
      http.delete("*/api/v1/senaryolar/:id", ({ params }) => {
        silinen.push(String(params.id));
        liste = liste.filter((s) => s.id !== Number(params.id));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    await u.click(screen.getByRole("button", { name: "Senaryo işlemleri" }));
    await u.click(screen.getByRole("menuitem", { name: "Sil…" }));
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(silinen).toEqual(["1"]));
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("2"));
    // Adres çubuğu senaryo durumundan bir render sonra güncellenir; yük altında ayrı beklenir.
    await waitFor(() => expect(screen.getByTestId("arama")).toHaveTextContent("?senaryo=2"));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("kilitli senaryoda Düzenle ve Sil pasiftir", async () => {
    const u = userEvent.setup();
    const kilitli = senaryolar.map((s) => (s.id === 1 ? { ...s, kilitli: true } : s));
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.json({ kayitlar: kilitli, toplam: 2 })));
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    await u.click(screen.getByRole("button", { name: "Senaryo işlemleri" }));
    const duzenle = screen.getByRole("menuitem", { name: "Düzenle…" });
    expect(duzenle).toHaveAttribute("aria-disabled", "true");
    expect(duzenle).toHaveAttribute("title", "Senaryo kilitli");
    expect(screen.getByRole("menuitem", { name: "Sil…" })).toHaveAttribute("aria-disabled", "true");
    // Pasif öğe tıklanınca diyalog açılmaz.
    await u.click(duzenle);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await u.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("menü klavyeyle kullanılır: açılınca odak ilk öğede, oklar dolaşır, Escape kapatıp odağı düğmeye döndürür", async () => {
    const u = userEvent.setup();
    kur();
    await waitFor(() => expect(screen.getByTestId("id")).toHaveTextContent("1"));
    const dugme = screen.getByRole("button", { name: "Senaryo işlemleri" });
    await u.click(dugme);
    expect(screen.getByRole("menuitem", { name: "Düzenle…" })).toHaveFocus();
    await u.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Sil…" })).toHaveFocus();
    await u.keyboard("{ArrowDown}");
    expect(screen.getByRole("menuitem", { name: "Düzenle…" })).toHaveFocus();
    await u.keyboard("{End}");
    expect(screen.getByRole("menuitem", { name: "Sil…" })).toHaveFocus();
    await u.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(dugme).toHaveFocus();
  });
});
