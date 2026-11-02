import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GecmisCekmecesi, type GecmisKaydi } from "./GecmisCekmecesi";

const kayitlar: GecmisKaydi[] = [
  { deger: "50", gecerlilik_basi: "2026-10-01", neden: "Yeni liste", olusturan: "Eşma", olusturma_zamani: "2026-10-01T08:00:00+00:00" },
  { deger: "45", gecerlilik_basi: "2026-01-01", neden: "Sezon başı", olusturan: "sistem", olusturma_zamani: "2026-01-01T08:00:00+00:00" },
];

describe("GecmisCekmecesi", () => {
  it("kayıtları listeler", () => {
    render(<GecmisCekmecesi acik baslik="Fiyat geçmişi" kayitlar={kayitlar} />);
    expect(screen.getByText("Fiyat geçmişi")).toBeInTheDocument();
    expect(screen.getByText("Yeni liste")).toBeInTheDocument();
    expect(screen.getByText("Sezon başı")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Geri al/ })).not.toBeInTheDocument();
  });

  it("'Geri al' eski kaydı callback'e verir ve otomatik neden üretir", async () => {
    const u = userEvent.setup();
    const geriAl = vi.fn();
    render(<GecmisCekmecesi acik baslik="Fiyat geçmişi" kayitlar={kayitlar} geriAl={geriAl} />);
    const satir = screen.getByText("Sezon başı").closest("li") as HTMLElement;
    await u.click(within(satir).getByRole("button", { name: /Geri al/ }));
    expect(geriAl).toHaveBeenCalledTimes(1);
    expect(geriAl).toHaveBeenCalledWith(kayitlar[1], "Geri alındı: 01.01.2026 değeri");
  });
});
