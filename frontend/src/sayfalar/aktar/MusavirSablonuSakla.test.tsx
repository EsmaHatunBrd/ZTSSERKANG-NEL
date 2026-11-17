import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { SenaryoSaglayici } from "@/bilesenler/SenaryoSecici";
import { MusavirSablonuSakla } from "./MusavirSablonuSakla";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

function kur() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/recete-aktar?senaryo=1"]}>
        <SenaryoSaglayici>
          <MusavirSablonuSakla />
        </SenaryoSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const kitap = () => new File(["x"], "kitap.xl" + "sx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

describe("MusavirSablonuSakla", () => {
  it("denetler (sayfalar, ürün sayfası) sonra yalnız şablon olarak saklar", async () => {
    kur();
    await waitFor(() => expect(screen.getByLabelText("Fiyat Çalışması kitabı")).toBeInTheDocument());
    const sakla = screen.getByRole("button", { name: "Şablon olarak sakla" });
    expect(sakla).toBeDisabled();
    await userEvent.upload(screen.getByLabelText("Fiyat Çalışması kitabı"), kitap());
    await userEvent.click(screen.getByRole("button", { name: "Denetle" }));
    expect(await screen.findByTestId("musavir-sablon-onizleme")).toHaveTextContent("3 sayfa, 1 ürün sayfası");
    await userEvent.click(sakla);
    expect(await screen.findByRole("status")).toHaveTextContent("Saklandı: kitap.xl" + "sx");
  });

  it("kitap değilse sunucunun reddi gösterilir, saklanamaz", async () => {
    sunucu.use(
      http.post("*/api/v1/import/excel-tam/musavir-sablonu/onizle", () =>
        HttpResponse.json(
          {
            hata: "dogrulama",
            mesaj: "Çalışma kitabı beklenen yapıda değil: şu sayfalar bulunamadı: S.ALMA BF",
            alanlar: {},
            kod: "eksik_sayfa",
          },
          { status: 422 },
        ),
      ),
    );
    kur();
    await waitFor(() => expect(screen.getByLabelText("Fiyat Çalışması kitabı")).toBeInTheDocument());
    await userEvent.upload(screen.getByLabelText("Fiyat Çalışması kitabı"), kitap());
    await userEvent.click(screen.getByRole("button", { name: "Denetle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("şu sayfalar bulunamadı");
    expect(screen.getByRole("button", { name: "Şablon olarak sakla" })).toBeDisabled();
  });
});
