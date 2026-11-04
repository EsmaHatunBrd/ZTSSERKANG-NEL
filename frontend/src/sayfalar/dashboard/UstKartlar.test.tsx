import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { ComponentProps } from "react";
import { UstKartlar } from "./UstKartlar";

function kur(props: ComponentProps<typeof UstKartlar>) {
  return render(
    <MemoryRouter>
      <UstKartlar {...props} />
    </MemoryRouter>,
  );
}

describe("UstKartlar", () => {
  it("veri yoksa kartlarda — gösterir; hesaplanamayan ürün kartı yalnız sayı > 0 iken görünür", () => {
    kur({ urunSayisi: null, hataSayisi: null, fiyatsizMalzeme: null });
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.queryByText("Hesaplanamayan ürün")).not.toBeInTheDocument();
  });

  it("kartları ve değerlerini gösterir; sıfır olan kart bağlantı değildir", () => {
    kur({ urunSayisi: 12, hataSayisi: 0, fiyatsizMalzeme: 3, uyariliUrun: 0, enflasyonAltinda: 2, senaryoId: 1 });
    expect(screen.getByText("Ürün sayısı").nextSibling).toHaveTextContent("12");
    expect(screen.getByText("Uyarılı ürün").nextSibling).toHaveTextContent("0");
    expect(screen.getByText("Fiyatsız malzeme").nextSibling).toHaveTextContent("3");
    expect(screen.getByText("Enflasyonun altındaki ürün").nextSibling).toHaveTextContent("2");
    expect(screen.queryByRole("link", { name: /Uyarılı ürün/ })).not.toBeInTheDocument();
  });

  it("dikkat isteyen kartlar ilgili sayfaya senaryoyla bağlanır; binlik ayraç Türkçe", () => {
    kur({ urunSayisi: 1200, hataSayisi: 0, fiyatsizMalzeme: 502, uyariliUrun: 64, senaryoId: 1 });
    expect(screen.getByText("Ürün sayısı").nextSibling).toHaveTextContent("1.200");
    expect(screen.getByRole("link", { name: /Uyarılı ürün/ })).toHaveAttribute("href", "/uyarilar?senaryo=1");
    expect(screen.getByRole("link", { name: /Fiyatsız malzeme/ })).toHaveAttribute("href", "/veri-kontrolu?senaryo=1");
  });

  it("enflasyon ve hesaplanamayan kartları tıklanınca süzgeç geri çağrılarını çalıştırır", async () => {
    const enf = vi.fn();
    const hata = vi.fn();
    kur({ urunSayisi: 3, hataSayisi: 1, fiyatsizMalzeme: 0, enflasyonAltinda: 2, onEnflasyonSuz: enf, onHataSuz: hata });
    await userEvent.click(screen.getByRole("button", { name: /Enflasyonun altındaki ürün/ }));
    await userEvent.click(screen.getByRole("button", { name: /Hesaplanamayan ürün/ }));
    expect(enf).toHaveBeenCalledOnce();
    expect(hata).toHaveBeenCalledOnce();
  });
});
