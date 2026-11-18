import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { OnayCiktisiDiyalogu, type OnayKapsami } from "./OnayCiktisiDiyalogu";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

const FIYAT: OnayKapsami = {
  modul: "fiyat",
  senaryoId: 7,
  senaryoAdi: "2026-2027 · Bütçe",
  kilitli: false,
  urunler: [
    { kod: "U-1", ad: "Biber turşusu" },
    { kod: "U-2", ad: "Salatalık turşusu" },
    { kod: "U-3", ad: "Karışık turşu" },
  ],
};
const SMM: OnayKapsami = {
  modul: "smm",
  donemId: 2,
  donemler: [
    { id: 2, ad: "Ekim 2026", kilitli: false },
    { id: 1, ad: "Eylül 2026", kilitli: true },
  ],
};

/** POST gövdelerini yakalar; dosya yanıtı döner. */
function yakala(modul: "fiyat" | "smm", durum = 200) {
  const govdeler: Record<string, unknown>[] = [];
  sunucu.use(
    http.post(`*/api/v1/onay-ciktisi/${modul}`, async ({ request }) => {
      govdeler.push((await request.json()) as Record<string, unknown>);
      await delay(300); // "Hazırlanıyor…" durumu yük altında da görülebilsin
      if (durum !== 200) return HttpResponse.json({ hata: "bulunamadi", mesaj: "dönem bulunamadı", alanlar: {} }, { status: durum });
      return new HttpResponse(new Uint8Array([37, 80, 68, 70]), {
        headers: { "Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="rapor-smm-2026-10.pdf"' },
      });
    }),
  );
  return govdeler;
}

function indirmeyiYakala() {
  const adresler = URL as unknown as { createObjectURL?: unknown; revokeObjectURL?: unknown };
  const eski = { c: adresler.createObjectURL, r: adresler.revokeObjectURL };
  adresler.createObjectURL = vi.fn(() => "blob:deneme");
  adresler.revokeObjectURL = vi.fn();
  const indirilen: string[] = [];
  const tikla = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    indirilen.push(this.download);
  });
  return {
    indirilen,
    geriAl: () => {
      tikla.mockRestore();
      adresler.createObjectURL = eski.c;
      adresler.revokeObjectURL = eski.r;
    },
  };
}

describe("OnayCiktisiDiyalogu", () => {
  it("Fiyat'ta varsayılan Genel Bakış tablosu; Rapor seçilince türler ve ekler görünür", async () => {
    render(<OnayCiktisiDiyalogu kapsam={FIYAT} onKapat={() => {}} />);
    expect(screen.getByRole("dialog", { name: "İndir" })).toBeInTheDocument();
    expect(screen.queryByText(/müşavir/)).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Genel Bakış tablosu/ })).toBeChecked();
    expect(screen.queryByRole("radio", { name: "Excel" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: /^Rapor/ }));
    expect(screen.getByRole("radio", { name: "Excel" })).toBeChecked();
    // bitmemiş "formüllü Excel" seçeneği gösterilmez
    expect(screen.queryByRole("radio", { name: /formüllü/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Yakında")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "PDF" }));
    expect(screen.getByRole("radio", { name: "PDF" })).toBeChecked();
    // ekler varsayılan açık; Fiyat'ta mutabakat yok
    for (const ad of ["Kapak sayfası", "Elle yapılan değişiklikler", "Değişiklik günlüğü özeti (son 90 gün)"]) {
      expect(screen.getByRole("checkbox", { name: ad })).toBeChecked();
    }
    expect(screen.queryByRole("checkbox", { name: "Mutabakat" })).not.toBeInTheDocument();
  });

  it("taslak / kesin uyarısı dönem seçimine göre değişir", async () => {
    render(<OnayCiktisiDiyalogu kapsam={SMM} onKapat={() => {}} />);
    expect(screen.getByTestId("onay-durumu")).toHaveTextContent("Bu dönem kapatılmadığı için çıktı TASLAK damgalı olur.");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Dönem" }), "1");
    expect(screen.getByTestId("onay-durumu")).toHaveTextContent("Bu dönem kapatıldı: çıktı KESİN olarak işaretlenir.");
    expect(screen.getByRole("checkbox", { name: "Mutabakat" })).toBeChecked();
  });

  it("Fiyat: seçili ürünler, ek ve imza seçimleri gövdeye doğru gider; 'Hazırlanıyor…' gösterilir", async () => {
    const govdeler = yakala("fiyat");
    const ind = indirmeyiYakala();
    try {
      render(<OnayCiktisiDiyalogu kapsam={FIYAT} onKapat={() => {}} />);
      await userEvent.click(screen.getByRole("radio", { name: /^Rapor/ }));
      expect(screen.getByTestId("onay-durumu")).toHaveTextContent("Bu çalışma kapatılmadığı için çıktı TASLAK damgalı olur.");
      await userEvent.click(screen.getByRole("radio", { name: /Yalnız seçtiğim ürünler/ }));
      // seçim yokken indirilemez
      expect(screen.getByRole("button", { name: "İndir" })).toBeDisabled();
      await userEvent.type(screen.getByRole("textbox", { name: "Ürün ara" }), "turşusu");
      expect(screen.queryByText("Karışık turşu")).not.toBeInTheDocument();
      await userEvent.click(screen.getByRole("checkbox", { name: /U-1/ }));
      await userEvent.click(screen.getByRole("checkbox", { name: /U-2/ }));
      await userEvent.click(screen.getByRole("checkbox", { name: "Elle yapılan değişiklikler" }));
      await userEvent.type(screen.getByRole("textbox", { name: "Hazırlayan" }), "  Ayşe Deneme ");
      await userEvent.click(screen.getByRole("radio", { name: "PDF" }));
      await userEvent.click(screen.getByRole("button", { name: "İndir" }));
      expect(await screen.findByRole("button", { name: "Hazırlanıyor…" })).toBeDisabled();
      await waitFor(() => expect(screen.getByRole("button", { name: "İndir" })).toBeEnabled());
      expect(govdeler).toEqual([
        {
          senaryo_id: 7,
          tur: "pdf",
          urunler: ["U-1", "U-2"],
          ekler: { kapak: true, mutabakat: true, elle_degisiklikler: false, gunluk_ozeti: true },
          imzalar: { hazirlayan: "Ayşe Deneme" },
        },
      ]);
      expect(ind.indirilen).toEqual(["rapor-smm-2026-10.pdf"]);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    } finally {
      ind.geriAl();
    }
  });

  it("Fiyat: Tüm maliyet kartları seçilince ilgili Excel indirilir", async () => {
    const istekler: string[] = [];
    sunucu.use(
      http.get("*/api/v1/disa-aktar/maliyet-kartlari", ({ request }) => {
        const u = new URL(request.url);
        istekler.push(u.pathname + u.search);
        return new HttpResponse(new Uint8Array([80, 75, 3, 4]), {
          headers: { "Content-Disposition": 'attachment; filename="maliyet-kartlari-deneme.xl' + 'sx"' },
        });
      }),
    );
    const ind = indirmeyiYakala();
    const kapat = vi.fn();
    try {
      render(<OnayCiktisiDiyalogu kapsam={FIYAT} onKapat={kapat} />);
      await userEvent.click(screen.getByRole("radio", { name: /Tüm maliyet kartları/ }));
      await userEvent.click(screen.getByRole("button", { name: "İndir" }));
      await waitFor(() => expect(kapat).toHaveBeenCalled());
      expect(istekler).toEqual(["/api/v1/disa-aktar/maliyet-kartlari?senaryo=7"]);
      expect(ind.indirilen).toEqual(["maliyet-kartlari-deneme.xl" + "sx"]);
    } finally {
      ind.geriAl();
    }
  });

  it("Fiyat: şablon yoksa Müşavir Excel'i en üstte pasif, nedeni ve Veri Aktar bağlantısı görünür", async () => {
    render(<OnayCiktisiDiyalogu kapsam={FIYAT} onKapat={() => {}} />);
    const musavir = screen.getByRole("radio", { name: /Fiyat Çalışması Excel'i \(kendi kitabınızın düzeninde\)/ });
    expect(screen.getAllByRole("radio")[0]).toBe(musavir);
    await waitFor(() => expect(screen.getByText(/Bu çalışma için şablon yok/)).toBeInTheDocument());
    expect(musavir).toBeDisabled();
    expect(screen.getByRole("link", { name: "Veri Aktar'a git" })).toHaveAttribute("href", "/recete-aktar");
    expect(screen.getByRole("radio", { name: /Genel Bakış tablosu/ })).toBeChecked();
  });

  it("Fiyat: şablon varsa adı ve tarihi görünür; seçilince müşavir Excel'i indirilir, uyarılar istenirse listelenir", async () => {
    const istekler: string[] = [];
    sunucu.use(
      http.get("*/api/v1/disa-aktar/musavir/fiyat-kitabi/durum", ({ request }) => {
        const u = new URL(request.url);
        istekler.push(u.pathname + u.search);
        return HttpResponse.json({
          sablon: { dosya_adi: "Fiyat Çalışma - Test.xl" + "sx", zaman: "2026-11-16T10:00:00", olusturan: "esma", boyut: 1234 },
          uyarilar_ozeti:
            u.searchParams.get("uyarilar") === "true"
              ? {
                  sayi: 1,
                  uyarilar: ["001!M9 (99.20.003 birim fiyat): uygulamada 2,5, Excel'de formül var"],
                  degisen_hucre: 3,
                  urun_sayfasi: 7,
                  yazilan_urun: 7,
                }
              : null,
        });
      }),
      http.get("*/api/v1/disa-aktar/musavir/fiyat-kitabi.xl" + "sx", ({ request }) => {
        const u = new URL(request.url);
        istekler.push(u.pathname + u.search);
        return new HttpResponse(new Uint8Array([80, 75, 3, 4]), {
          headers: {
            "Content-Disposition":
              'attachment; filename="Fiyat Calisma - Test - uygulama 17.11.2026.xl' +
              "sx\"; filename*=UTF-8''Fiyat%20%C3%87al%C4%B1%C5%9Fma%20-%20Test%20-%20uygulama%2017.11.2026.xl" +
              "sx",
          },
        });
      }),
    );
    const ind = indirmeyiYakala();
    const kapat = vi.fn();
    try {
      render(<OnayCiktisiDiyalogu kapsam={FIYAT} onKapat={kapat} />);
      expect(await screen.findByTestId("musavir-sablon")).toHaveTextContent("Şablon: Fiyat Çalışma - Test.xl" + "sx, 16.11.2026");
      expect(screen.getByText(/Excel açıldığında toplamlar hesaplanır/)).toBeInTheDocument();
      const musavir = screen.getByRole("radio", { name: /Fiyat Çalışması Excel'i/ });
      expect(musavir).toBeEnabled();
      await userEvent.click(musavir);
      await userEvent.click(screen.getByRole("button", { name: "Kitaba yazılamayan değerleri göster" }));
      expect(await screen.findByTestId("musavir-uyarilar")).toHaveTextContent("1 değer kitaba yazılamıyor");
      await userEvent.click(screen.getByRole("button", { name: "İndir" }));
      await waitFor(() => expect(kapat).toHaveBeenCalled());
      expect(istekler).toEqual([
        "/api/v1/disa-aktar/musavir/fiyat-kitabi/durum?senaryo_id=7",
        "/api/v1/disa-aktar/musavir/fiyat-kitabi/durum?senaryo_id=7&uyarilar=true",
        "/api/v1/disa-aktar/musavir/fiyat-kitabi.xl" + "sx?senaryo_id=7",
      ]);
      expect(ind.indirilen).toEqual(["Fiyat Çalışma - Test - uygulama 17.11.2026.xl" + "sx"]);
    } finally {
      ind.geriAl();
    }
  });

  it("SMM: Müşavir Excel'i (fiyat kitabı) seçeneği yok", () => {
    render(<OnayCiktisiDiyalogu kapsam={SMM} onKapat={() => {}} />);
    expect(screen.queryByRole("radio", { name: /kendi kitabınızın düzeninde/ })).not.toBeInTheDocument();
  });

  it("SMM: tüm seçimlerle gövde; sunucu hatası role=alert ile gösterilir", async () => {
    const govdeler = yakala("smm", 404);
    render(<OnayCiktisiDiyalogu kapsam={SMM} onKapat={() => {}} />);
    await userEvent.click(screen.getByRole("checkbox", { name: "Kapak sayfası" }));
    await userEvent.click(screen.getByRole("button", { name: "İndir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("dönem bulunamadı");
    expect(govdeler).toEqual([
      { donem_id: 2, tur: "excel", ekler: { kapak: false, mutabakat: true, elle_degisiklikler: true, gunluk_ozeti: true }, imzalar: {} },
    ]);
  });
});
