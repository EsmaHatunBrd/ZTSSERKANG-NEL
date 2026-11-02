import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KaydetDiyalogu } from "./KaydetDiyalogu";
import type { DegisiklikSatiri } from "./Taslak";

const satirlar: DegisiklikSatiri[] = [
  {
    alan: "urun.hat",
    etiket: "Üretim hattı",
    eski: "Niko",
    yeni: "Herbort",
    etki: "urun",
    kalici: true,
  },
  {
    alan: "parametre.kur.USD",
    etiket: "USD kuru",
    eski: "50",
    yeni: "52",
    etki: "senaryo",
    kalici: true,
    parametre: "kur.USD",
  },
  {
    alan: "gider.elektrik_sn.Niko",
    etiket: "Elektrik (sn) — Niko",
    eski: "—",
    yeni: "0,001",
    etki: "urun",
    kalici: false,
    not: "kalıcı yazım Gider Dağıtım sayfasından",
  },
];

const kur = (ek: Partial<Parameters<typeof KaydetDiyalogu>[0]> = {}) => {
  const onGonder = vi.fn();
  const onKapat = vi.fn();
  render(
    <KaydetDiyalogu
      acik
      satirlar={satirlar}
      dusenFire={[]}
      gonderiliyor={false}
      hata={null}
      onGonder={onGonder}
      onKapat={onKapat}
      {...ek}
    />,
  );
  return { onGonder, onKapat };
};

describe("KaydetDiyalogu", () => {
  it("üç etki türünü ayrı rozetle gösterir; kalıcı olmayan satırda açıklama vardır", () => {
    kur();
    const d = screen.getByRole("dialog");
    expect(within(d).getByText("Bu ürün")).toBeInTheDocument();
    expect(within(d).getByText("Senaryo geneli — tüm ürünleri etkiler")).toBeInTheDocument();
    expect(within(d).getByText("Yalnız bu hesapta")).toBeInTheDocument();
    expect(within(d).getByText("kalıcı yazım Gider Dağıtım sayfasından")).toBeInTheDocument();
    // yalnız senaryo geneli parametre satırında kapsam seçeneği var
    expect(within(d).getAllByRole("checkbox", { name: /Yalnız bu ürün için yaz/ })).toHaveLength(1);
  });

  it("senaryo geneli rozeti gerçek ürün sayısını söyler; sayı yüklenmediyse genel metin görünür", () => {
    kur({ urunSayisi: 12 });
    expect(within(screen.getByRole("dialog")).getByText("Senaryo geneli — 12 ürünü etkiler")).toBeInTheDocument();
  });

  it("neden boşken onay pasiftir; yazılınca kapsam seçimi ve 'hesabı da kaydet' ile gönderir", async () => {
    const { onGonder } = kur();
    const user = userEvent.setup();
    const onay = screen.getByRole("button", { name: "Onayla ve kaydet" });
    expect(onay).toBeDisabled();
    await user.type(screen.getByLabelText("Neden"), "   ");
    expect(onay).toBeDisabled();
    await user.type(screen.getByLabelText("Neden"), " Sebep ");
    await user.click(screen.getByLabelText("Yalnız bu ürün için yaz — USD kuru"));
    await user.click(screen.getByLabelText("Hesabı da kaydet"));
    await user.click(onay);
    expect(onGonder).toHaveBeenCalledWith({
      neden: "Sebep",
      hesabiKaydet: false,
      kapsamSecimi: { "kur.USD": "urun" },
    });
  });

  it("düşen fire uyarısı ve sunucu hatası gösterilir; gönderilirken onay pasiftir", async () => {
    kur({
      dusenFire: [{ sira: 2 }],
      hata: "Sunucu reddetti",
      gonderiliyor: true,
    });
    expect(screen.getByText("Satır 2: fire düşer (elle brüt)")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Sunucu reddetti");
    await userEvent.setup().type(screen.getByLabelText("Neden"), "x");
    expect(screen.getByRole("button", { name: "Onayla ve kaydet" })).toBeDisabled();
  });

  it("gönderim sürerken Vazgeç pasiftir ve Escape diyaloğu kapatmaz", async () => {
    const { onKapat } = kur({ gonderiliyor: true });
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeDisabled();
    await userEvent.setup().keyboard("{Escape}");
    expect(onKapat).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("Vazgeç kapatır", async () => {
    const { onKapat } = kur();
    await userEvent.setup().click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(onKapat).toHaveBeenCalled();
  });
});
