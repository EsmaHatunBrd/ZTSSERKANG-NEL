import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DegisiklikSeridi } from "./DegisiklikSeridi";

const temel = {
  sayi: 0,
  hesaplaniyor: false,
  hata: null,
  onKaydet: () => {},
  onVazgec: () => {},
  kayit: null,
};

describe("DegisiklikSeridi", () => {
  it("değişiklik yokken Kaydet ve Vazgeç pasiftir", () => {
    render(<DegisiklikSeridi {...temel} />);
    expect(screen.getByText("Değişiklik yok")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeDisabled();
  });

  it("sayıyı gösterir; düğmeler çağrı yapar", async () => {
    const onKaydet = vi.fn();
    const onVazgec = vi.fn();
    render(<DegisiklikSeridi {...temel} sayi={3} onKaydet={onKaydet} onVazgec={onVazgec} />);
    expect(screen.getByText("3 değişiklik")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(onKaydet).toHaveBeenCalledOnce();
    expect(onVazgec).toHaveBeenCalledOnce();
  });

  it("Kaydet kapalıysa nedeni ipucu olarak verilir", () => {
    render(<DegisiklikSeridi {...temel} sayi={1} kaydetKapali kaydetNedeni="Önce hatayı düzeltin" />);
    const d = screen.getByRole("button", { name: "Kaydet" });
    expect(d).toBeDisabled();
    expect(d).toHaveAttribute("title", "Önce hatayı düzeltin");
  });

  it("hesaplanırken simge, hata varsa kırmızı uyarı gösterir", () => {
    render(<DegisiklikSeridi {...temel} sayi={1} hesaplaniyor hata="Geçersiz fire" />);
    expect(screen.getByRole("status", { name: "Hesaplanıyor" })).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Geçersiz fire");
  });

  it("kayıt sonrası 'Kaydedildi · Hesap #id' ve yazılan özeti ile uyarıları gösterir", () => {
    render(
      <DegisiklikSeridi
        {...temel}
        kayit={{
          hesapId: 9,
          ozet: "2 parametre",
          uyarilar: ["Fiyatı olmayan satır"],
        }}
      />,
    );
    expect(screen.getByRole("status", { name: "Kayıt durumu" })).toHaveTextContent("Kaydedildi · Hesap #9 · 2 parametre");
    expect(screen.getByText("Fiyatı olmayan satır")).toBeInTheDocument();
  });
});
