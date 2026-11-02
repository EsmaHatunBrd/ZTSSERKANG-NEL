import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { sunucu } from "@/test/msw/sunucu";
import { useUrunler } from "./urunler";
import { useMalzemeler, useFiyatGecmisi, useFiyatEkle } from "./malzemeler";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());

function sarmal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Sarmal = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  return Sarmal;
}

describe("senaryo değişimi", () => {
  it("useUrunler: ikinci senaryo yüklenirken ilk senaryonun verisi gösterilmez", async () => {
    let birak: () => void = () => {};
    const bekle = new Promise<void>((r) => (birak = r));
    sunucu.use(
      http.get("*/api/v1/urunler", async ({ request }) => {
        const sen = new URL(request.url).searchParams.get("senaryo");
        if (sen === "2") {
          await bekle;
          return HttpResponse.json({ kayitlar: [], toplam: 0 });
        }
        return HttpResponse.json({ kayitlar: [{ kod: "S1" }], toplam: 1 });
      }),
    );
    const { result, rerender } = renderHook(({ s }) => useUrunler(s), {
      wrapper: sarmal(),
      initialProps: { s: 1 },
    });
    await waitFor(() => expect(result.current.data?.toplam).toBe(1));
    rerender({ s: 2 });
    expect(result.current.data).toBeUndefined();
    expect(result.current.isPlaceholderData).toBe(false);
    birak();
    await waitFor(() => expect(result.current.data?.toplam).toBe(0));
  });

  it("useMalzemeler: senaryo değişince eski veri tutulmaz, sayfa değişince tutulur", async () => {
    let birak: () => void = () => {};
    const bekle = new Promise<void>((r) => (birak = r));
    sunucu.use(
      http.get("*/api/v1/malzemeler", async ({ request }) => {
        const u = new URL(request.url).searchParams;
        if (u.get("senaryo") === "2" || u.get("sayfa") === "2") await bekle;
        return HttpResponse.json({ kayitlar: [{ kod: "M" }], toplam: 1 });
      }),
    );
    const { result, rerender } = renderHook(({ s, p }) => useMalzemeler(s, { sayfa: p }), {
      wrapper: sarmal(),
      initialProps: { s: 1, p: 1 },
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    rerender({ s: 1, p: 2 });
    expect(result.current.isPlaceholderData).toBe(true);
    birak();
    await waitFor(() => expect(result.current.isPlaceholderData).toBe(false));
    rerender({ s: 2, p: 1 });
    expect(result.current.data).toBeUndefined(); // başka senaryonun verisi tutulmaz
    expect(result.current.isPlaceholderData).toBe(false);
    await waitFor(() => expect(result.current.data).toBeDefined());
  });
});

describe("geçersiz kılma", () => {
  it("useFiyatEkle başarısı malzemeler ve fiyat-gecmisi sorgularını yeniler", async () => {
    let malzemeSayisi = 0;
    let gecmisSayisi = 0;
    sunucu.use(
      http.get("*/api/v1/malzemeler", () => {
        malzemeSayisi++;
        return HttpResponse.json({ kayitlar: [], toplam: 0 });
      }),
      http.get("*/api/v1/malzemeler/:kod/fiyatlar", () => {
        gecmisSayisi++;
        return HttpResponse.json({ kayitlar: [], toplam: 0 });
      }),
    );
    const { result } = renderHook(
      () => ({
        m: useMalzemeler(1),
        g: useFiyatGecmisi("M-001", 1),
        ekle: useFiyatEkle(),
      }),
      { wrapper: sarmal() },
    );
    await waitFor(() => expect(result.current.m.isSuccess && result.current.g.isSuccess).toBe(true));
    const once = [malzemeSayisi, gecmisSayisi];
    await act(async () => {
      await result.current.ekle.mutateAsync({
        kod: "M-001",
        senaryo: 1,
        govde: { fiyat: "6", gecerlilik_basi: "2026-10-21", neden: "Test" },
      });
    });
    await waitFor(() => {
      expect(malzemeSayisi).toBeGreaterThan(once[0]);
      expect(gecmisSayisi).toBeGreaterThan(once[1]);
    });
  });
});
