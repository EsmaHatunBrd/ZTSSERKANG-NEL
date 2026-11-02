import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KullaniciAyari } from "./KullaniciAyari";
import * as kullanici from "@/yardimcilar/kullanici";

describe("KullaniciAyari ilk açılış", () => {
  it("kayıtlı ad yoksa diyalog açılır; ad girilene kadar kapanmaz", async () => {
    localStorage.removeItem("fiyat-calismasi.kullanici");
    const u = userEvent.setup();
    render(<KullaniciAyari />);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent(/adınızı girin/i);

    await u.keyboard("{Escape}");
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(kullanici.kayitliMi()).toBe(false);

    await u.type(screen.getByLabelText("Adınız"), "sistem");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await u.clear(screen.getByLabelText("Adınız"));
    await u.type(screen.getByLabelText("Adınız"), "Ayşe");
    await u.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(kullanici.al()).toBe("Ayşe");
    expect(screen.getByRole("button", { name: /Kullanıcı: Ayşe/ })).toBeInTheDocument();
  });

  it("kayıtlı ad varsa diyalog açılmaz", () => {
    kullanici.kaydet("Ayşe");
    render(<KullaniciAyari />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
