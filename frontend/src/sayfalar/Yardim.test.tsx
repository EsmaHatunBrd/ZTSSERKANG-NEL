import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Yardim from "./Yardim";

describe("Yardım", () => {
  it("tüm bölümler başlıklarıyla bölge olarak görünür; yeni özellikler anlatılır", () => {
    render(<Yardim />);
    for (const b of [
      "İlk 10 dakika",
      "Menü düzeni",
      "Excel'de neredeydi, burada nerede",
      "Yeni sezon / yeni çalışma",
      "Excel'den aktarma (Veri Aktar)",
      "Genel Bakış",
      "Ürün ekranında çalışma",
      "Malzeme fiyatları: kaynak ve revize",
      "Bütçe vs Gerçekleşen",
      "Diğer sayfalar",
    ]) {
      expect(screen.getByRole("region", { name: b })).toBeInTheDocument();
    }
    expect(screen.getByRole("region", { name: "Bütçe vs Gerçekleşen" })).toHaveTextContent("Sapmanın kaynağı");
    expect(screen.getByRole("region", { name: "Excel'den aktarma (Veri Aktar)" })).toHaveTextContent("Kartları güncelle");
    expect(screen.getByRole("region", { name: "Diğer sayfalar" })).toHaveTextContent("Veri Kontrolü");
    expect(screen.queryByText(/dashboard/i)).not.toBeInTheDocument();
  });
});
