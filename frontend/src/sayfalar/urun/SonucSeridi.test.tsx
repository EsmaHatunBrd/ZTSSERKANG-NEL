import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { Fiyatlar, Toplamlar } from "@/api/tipler";
import { SonucSeridi } from "./SonucSeridi";

const toplamlar = { malzeme: "23.33", uretim_gideri: "4.82", maliyet_tl: "35.32" } as unknown as Toplamlar;
const firesiz = { malzeme: "23.1", uretim_gideri: "4.82", maliyet_tl: "35.07" } as unknown as Toplamlar;
const fiyatlar = { satis_tl: "42.39", satis_usd: "0.728", satis_eur: "0.606", satis_kar_orani: "0.2" } as unknown as Fiyatlar;

describe("SonucSeridi", () => {
  it("maliyet, satış fiyatı (kâr oranıyla), döviz ve malzeme payını gösterir", () => {
    render(<SonucSeridi toplamlar={toplamlar} toplamlarFiresiz={firesiz} fiyatlar={fiyatlar} />);
    const bolge = screen.getByRole("region", { name: "Hesap sonucu" });
    expect(within(bolge).getByText("35,32 TL")).toBeInTheDocument();
    expect(within(bolge).getByText("Firesiz: 35,07 TL")).toBeInTheDocument();
    expect(within(bolge).getByText("Satış fiyatı (kâr %20)")).toBeInTheDocument();
    expect(within(bolge).getByText("42,39 TL")).toBeInTheDocument();
    expect(within(bolge).getByText("0,728 USD")).toBeInTheDocument();
    expect(within(bolge).getByText("EUR: 0,606 EUR")).toBeInTheDocument();
    expect(within(bolge).getByText("%66,1")).toBeInTheDocument();
  });

  it("bayat sonuç soluk gösterilir; firesiz yoksa alt satır yok", () => {
    render(<SonucSeridi toplamlar={toplamlar} toplamlarFiresiz={null} fiyatlar={fiyatlar} bayat />);
    expect(screen.getByRole("region", { name: "Hesap sonucu" })).toHaveClass("opacity-60");
    expect(screen.queryByText(/Firesiz:/)).not.toBeInTheDocument();
  });
});
