import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { sunucu } from "@/test/msw/sunucu";
import { useUrun } from "./sorgular/urunler";
import { sorguIstemcisi } from "./sorguIstemcisi";
import { ApiHatasi } from "./istemci";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

describe("sorgu istemcisi yeniden deneme politikası", () => {
  it("404 sorgusu bekletmeden hata verir (4xx yeniden denenmez)", async () => {
    let istek = 0;
    sunucu.use(
      http.get("*/api/v1/urunler/:kod", () => {
        istek += 1;
        return HttpResponse.json({ hata: "bulunamadi", mesaj: "ürün yok", alanlar: {} }, { status: 404 });
      }),
    );
    const qc = sorguIstemcisi();
    const sarmal = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => useUrun("YOK", 1), { wrapper: sarmal });
    // Varsayılan yeniden deneme gecikmesi 1 sn: politika yanlışsa bu bekleme zaman aşımına düşer.
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 600 });
    expect(result.current.error).toBeInstanceOf(ApiHatasi);
    expect(istek).toBe(1);
  });

  it("yazma (mutation) varsayılanı yeniden denemez; sunucu hatası en fazla 2 kez denenir", () => {
    const o = sorguIstemcisi().getDefaultOptions();
    expect(o.mutations?.retry).toBe(0);
    const retry = o.queries?.retry as (n: number, e: unknown) => boolean;
    expect(retry(0, new ApiHatasi("sunucu", "x", {}, 500))).toBe(true);
    expect(retry(2, new ApiHatasi("sunucu", "x", {}, 500))).toBe(false);
    expect(retry(0, new ApiHatasi("ag", "x"))).toBe(true);
    expect(retry(0, new ApiHatasi("x", "x", {}, 422))).toBe(false);
  });
});
