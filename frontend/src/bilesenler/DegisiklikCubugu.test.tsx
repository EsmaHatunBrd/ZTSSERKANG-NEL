import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DegisiklikCubugu } from "./DegisiklikCubugu";

const temel = { satirSayisi: 0, kaydediyor: false, onKaydet: () => {}, onVazgec: () => {} };
const bolge = () => screen.queryByRole("region", { name: "Kaydedilmemiş değişiklikler" });

describe("DegisiklikCubugu", () => {
  it("değişiklik yokken hiç çizilmez", () => {
    render(<DegisiklikCubugu {...temel} />);
    expect(bolge()).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
  });

  it("satır sayısını söyler; Kaydet ve Vazgeç çağrı yapar", async () => {
    const onKaydet = vi.fn();
    const onVazgec = vi.fn();
    render(<DegisiklikCubugu {...temel} satirSayisi={2} onKaydet={onKaydet} onVazgec={onVazgec} />);
    const b = bolge();
    expect(b).toBeInTheDocument();
    expect(b).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("2 satırda değişiklik")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(onKaydet).toHaveBeenCalledOnce();
    expect(onVazgec).toHaveBeenCalledOnce();
  });

  it("fire ve diğer alan sayılarını ekler", () => {
    const { rerender } = render(<DegisiklikCubugu {...temel} satirSayisi={1} fireSayisi={1} />);
    expect(screen.getByText("1 satırda değişiklik · 1 fire")).toBeInTheDocument();
    rerender(<DegisiklikCubugu {...temel} satirSayisi={2} fireSayisi={1} alanSayisi={3} />);
    expect(screen.getByText("2 satırda ve 3 alanda değişiklik · 1 fire")).toBeInTheDocument();
    rerender(<DegisiklikCubugu {...temel} satirSayisi={0} alanSayisi={1} />);
    expect(screen.getByText("1 alanda değişiklik")).toBeInTheDocument();
  });

  it("Kaydet kapalıysa nedeni ipucu ve erişilebilir açıklama olarak verilir", () => {
    render(<DegisiklikCubugu {...temel} satirSayisi={1} kaydetKapali kaydetNedeni="Senaryo kilitli" />);
    const d = screen.getByRole("button", { name: "Kaydet" });
    expect(d).toBeDisabled();
    expect(d).toHaveAttribute("title", "Senaryo kilitli");
    expect(d).toHaveAttribute("aria-description", "Senaryo kilitli");
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeEnabled();
  });

  it("kaydederken iki düğme de kapalıdır ve 'Kaydediliyor' durumu görünür", () => {
    render(<DegisiklikCubugu {...temel} satirSayisi={1} kaydediyor />);
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeDisabled();
    expect(screen.getByRole("status", { name: "Kaydediliyor" })).toBeInTheDocument();
  });

  it("hata verilirse çubukta role=alert ile gösterilir", () => {
    render(<DegisiklikCubugu {...temel} satirSayisi={1} hata="Geçersiz fire" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Geçersiz fire");
  });
});
