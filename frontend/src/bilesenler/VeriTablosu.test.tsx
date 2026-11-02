import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiHatasi } from "@/api/istemci";
import { paraBicimle, topla } from "@/yardimcilar/para";
import { VeriTablosu, type SutunTanimi } from "./VeriTablosu";
import { ParaHucresi } from "./ParaHucresi";

interface Satir {
  kod: string;
  ad: string;
  tutar: string;
}

const veri: Satir[] = [
  { kod: "A", ad: "Zeytin", tutar: "10" },
  { kod: "B", ad: "Biber", tutar: "9" },
  { kod: "C", ad: "Salatalık", tutar: "100" },
];

const sutunlar: SutunTanimi<Satir>[] = [
  { id: "kod", accessorKey: "kod", header: "Kod" },
  { id: "ad", accessorKey: "ad", header: "Ad" },
  { id: "tutar", accessorKey: "tutar", header: "Tutar", cell: ({ row }) => <ParaHucresi deger={row.original.tutar} /> },
];

function kodlar(): string[] {
  const govde = screen.getAllByRole("row").filter((r) => within(r).queryAllByRole("cell").length > 0 && !r.closest("tfoot"));
  return govde.map((r) => within(r).getAllByRole("cell")[0].textContent ?? "");
}

describe("VeriTablosu", () => {
  it("sütun başlığına tıklayınca sırayı değiştirir ve aria-sort günceller", async () => {
    const u = userEvent.setup();
    render(<VeriTablosu veri={veri} sutunlar={sutunlar} />);
    expect(kodlar()).toEqual(["A", "B", "C"]);
    const baslik = screen.getByRole("columnheader", { name: /Tutar/ });
    expect(baslik).toHaveAttribute("aria-sort", "none");
    await u.click(within(baslik).getByRole("button"));
    expect(baslik).toHaveAttribute("aria-sort", "ascending");
    expect(kodlar()).toEqual(["B", "A", "C"]); // sayısal: 9 < 10 < 100
    await u.click(within(baslik).getByRole("button"));
    expect(baslik).toHaveAttribute("aria-sort", "descending");
    expect(kodlar()).toEqual(["C", "A", "B"]);
  });

  it("toplam satırını Decimal ile hesaplar", () => {
    render(
      <VeriTablosu
        veri={[
          { kod: "A", ad: "x", tutar: "0.1" },
          { kod: "B", ad: "y", tutar: "0.2" },
        ]}
        sutunlar={sutunlar}
        toplamSatiri={(s) => ({ kod: "Toplam", tutar: paraBicimle(topla(s.map((x) => x.tutar))) })}
      />,
    );
    expect(screen.getByText("0,30 TL", { selector: "tfoot *" })).toBeInTheDocument();
    expect(screen.getByText("Toplam", { selector: "tfoot *" })).toBeInTheDocument();
  });

  it("hata durumunda ApiHatasi.mesaj gösterir", () => {
    render(
      <VeriTablosu veri={[]} sutunlar={sutunlar} hata={new ApiHatasi("sunucu", "Beklenmeyen hata oluştu", {}, 500)} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Beklenmeyen hata oluştu");
  });

  it("boş ve yükleniyor durumlarını gösterir", () => {
    const { rerender } = render(<VeriTablosu veri={[]} sutunlar={sutunlar} bosMetin="Ürün yok" />);
    expect(screen.getByText("Ürün yok")).toBeInTheDocument();
    rerender(<VeriTablosu veri={[]} sutunlar={sutunlar} yukleniyor />);
    expect(screen.getByRole("status")).toHaveTextContent("Yükleniyor");
  });

  it("metin aramasıyla satırları süzer", async () => {
    const u = userEvent.setup();
    render(<VeriTablosu veri={veri} sutunlar={sutunlar} aramaAlani="ad" />);
    await u.type(screen.getByRole("searchbox"), "bib");
    expect(kodlar()).toEqual(["B"]);
  });

  it("ok tuşlarıyla gezinir, Enter satirTikla çağırır", async () => {
    const u = userEvent.setup();
    const tikla = vi.fn();
    render(<VeriTablosu veri={veri} sutunlar={sutunlar} satirTikla={tikla} />);
    const satirlar = screen.getAllByRole("row").filter((r) => r.getAttribute("tabindex") !== null);
    expect(satirlar).toHaveLength(3);
    satirlar[0].focus();
    await u.keyboard("{ArrowDown}");
    expect(satirlar[1]).toHaveFocus();
    await u.keyboard("{ArrowDown}{ArrowUp}");
    expect(satirlar[1]).toHaveFocus();
    await u.keyboard("{Enter}");
    expect(tikla).toHaveBeenCalledWith(veri[1]);
  });

  it("satır içindeki düğmede Enter satirTikla çağırmaz; satırda çağırır", async () => {
    const u = userEvent.setup();
    const tikla = vi.fn();
    const ic: SutunTanimi<Satir>[] = [
      ...sutunlar,
      { id: "islem", header: "İşlem", cell: () => <button type="button">Düzenle</button> },
    ];
    render(<VeriTablosu veri={veri} sutunlar={ic} satirTikla={tikla} />);
    const dugme = screen.getAllByRole("button", { name: "Düzenle" })[0];
    dugme.focus();
    await u.keyboard("{Enter}");
    expect(tikla).not.toHaveBeenCalled();
    await u.click(dugme);
    expect(tikla).not.toHaveBeenCalled();
    const satir = dugme.closest("tr") as HTMLElement;
    satir.focus();
    await u.keyboard("{Enter}");
    expect(tikla).toHaveBeenCalledWith(veri[0]);
  });
});
