import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SayfaBasligi } from "./SayfaBasligi";

describe("SayfaBasligi", () => {
  it("başlığı h1, alt başlığı ve eylemleri gösterir", () => {
    render(<SayfaBasligi baslik="Teklifler" altBaslik="Alt metin" eylemler={<button>Yazdır</button>} />);
    expect(screen.getByRole("heading", { level: 1, name: "Teklifler" })).toBeInTheDocument();
    expect(screen.getByText("Alt metin")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yazdır" })).toBeInTheDocument();
  });
  it("alt başlık ve eylem olmadan da çalışır", () => {
    render(<SayfaBasligi baslik="Uyarılar" />);
    expect(screen.getByRole("heading", { name: "Uyarılar" })).toBeInTheDocument();
  });
});
