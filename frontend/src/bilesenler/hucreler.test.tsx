import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { KaynakRozeti } from "./KaynakRozeti";
import { MaliyetHucresi, ORTALAMA_IPUCU } from "./MaliyetHucresi";
import { ParaHucresi } from "./ParaHucresi";
import { UyariRozeti } from "./UyariRozeti";
import { YuzdeHucresi } from "./YuzdeHucresi";

describe("KaynakRozeti", () => {
  it.each([
    ["fire", "Fire"],
    ["elle", "Elle"],
    ["liste", "Liste"],
    ["satir", "Satır"],
    ["malzeme", "Malzeme"],
    ["yok", "Yok"],
    ["import", "İçe aktarma"],
    ["grup:Hassas", "Grup: Hassas"],
    ["tip:ambalaj", "Tip: ambalaj"],
  ] as const)("%s -> %s", (tur, metin) => {
    render(<KaynakRozeti tur={tur} />);
    expect(screen.getByText(metin)).toBeInTheDocument();
  });

  it("'-' için bir şey çizmez", () => {
    const { container } = render(<KaynakRozeti tur="-" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("KaynakRozeti bos girdiler", () => {
  it("KaynakRozeti null ve undefined için hiçbir şey göstermez", () => {
    const { container } = render(
      <>
        <KaynakRozeti tur={null} />
        <KaynakRozeti tur={undefined} />
        <KaynakRozeti tur="-" />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ParaHucresi", () => {
  it("tutarı Türkçe biçimler", () => {
    render(<ParaHucresi deger="1234.5" />);
    expect(screen.getByText("1.234,50 TL")).toBeInTheDocument();
  });
  it("null için tire gösterir", () => {
    render(<ParaHucresi deger={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
  it("negatif tutar kırmızıdır", () => {
    render(<ParaHucresi deger="-5" paraBirimi="USD" basamak={3} />);
    const el = screen.getByText("-5,000 USD");
    expect(el.className).toMatch(/red/);
  });
});

describe("YuzdeHucresi", () => {
  it("oranı yüzde olarak gösterir", () => {
    render(<YuzdeHucresi deger="0.19736" />);
    expect(screen.getByText("19,7 %")).toBeInTheDocument();
  });
  it("null için tire", () => {
    render(<YuzdeHucresi deger={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("UyariRozeti", () => {
  it("sayı sıfırsa çizmez", () => {
    const { container } = render(<UyariRozeti sayi={0} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("sayıyı ve erişilebilir metni gösterir", () => {
    render(<UyariRozeti sayi={3} />);
    expect(screen.getByLabelText("3 uyarı")).toHaveTextContent("3");
  });
});

describe("MaliyetHucresi", () => {
  it("ortalama kaynağında 'ort.' rozeti ve ipucu, bu yılda düz tutar", () => {
    const { rerender } = render(<MaliyetHucresi deger="19.5" kaynak="ortalama" />);
    expect(screen.getByText("ort.")).toHaveAttribute("title", ORTALAMA_IPUCU);
    expect(screen.getByText("19,50 TL")).toBeInTheDocument();
    rerender(<MaliyetHucresi deger="19.5" kaynak="bu_yil" />);
    expect(screen.queryByText("ort.")).not.toBeInTheDocument();
    expect(screen.getByText("19,50 TL")).toBeInTheDocument();
  });
});
