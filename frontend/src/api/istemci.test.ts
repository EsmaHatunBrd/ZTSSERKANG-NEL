import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { sunucu } from "@/test/msw/sunucu";
import { api, ApiHatasi, cagir, hataMetni } from "./istemci";
import * as kullanici from "@/yardimcilar/kullanici";

beforeAll(() => sunucu.listen({ onUnhandledFrame: "error" }));
afterEach(() => sunucu.resetHandlers());
afterAll(() => sunucu.close());
beforeEach(() => localStorage.clear());

describe("api istemcisi", () => {
  it("200 yanıtında veriyi döndürür", async () => {
    const v = await cagir(api.GET("/api/v1/senaryolar"));
    expect(v.toplam).toBeGreaterThan(0);
    expect(v.kayitlar[0].ad).toBeTruthy();
  });

  it("404 gövdesini ApiHatasi'ne çevirir", async () => {
    sunucu.use(
      http.get("*/api/v1/urunler/:kod", () =>
        HttpResponse.json(
          { hata: "bulunamadi", mesaj: "Ürün bulunamadı", alanlar: { kod: "X" } },
          { status: 404 },
        ),
      ),
    );
    const hata = await cagir(api.GET("/api/v1/urunler/{kod}", { params: { path: { kod: "X" } } })).catch(
      (e: unknown) => e,
    );
    expect(hata).toBeInstanceOf(ApiHatasi);
    const h = hata as ApiHatasi;
    expect(h.hata).toBe("bulunamadi");
    expect(h.mesaj).toBe("Ürün bulunamadı");
    expect(h.durum).toBe(404);
    expect(h.alanlar).toEqual({ kod: "X" });
    expect(h.kod).toBeNull();
  });

  it("kararlı hata kodunu (kod) taşır", async () => {
    sunucu.use(
      http.get("*/api/v1/urunler/:kod", () =>
        HttpResponse.json(
          { hata: "bulunamadi", mesaj: "metin değişebilir", alanlar: {}, kod: "hedef_yok" },
          { status: 404 },
        ),
      ),
    );
    const h = (await cagir(api.GET("/api/v1/urunler/{kod}", { params: { path: { kod: "X" } } })).catch(
      (e: unknown) => e,
    )) as ApiHatasi;
    expect(h.kod).toBe("hedef_yok");
  });

  it("422 doğrulama hatasında alanları taşır", async () => {
    kullanici.kaydet("Eşma");
    sunucu.use(
      http.post("*/api/v1/senaryolar", () =>
        HttpResponse.json(
          { hata: "dogrulama", mesaj: "istek gövdesi geçersiz", alanlar: { ad: "zorunlu" } },
          { status: 422 },
        ),
      ),
    );
    const hata = (await cagir(
      api.POST("/api/v1/senaryolar", { body: { sezon_ad: "2026", tur: "fiyat_calismasi", ad: "" } }),
    ).catch((e: unknown) => e)) as ApiHatasi;
    expect(hata.hata).toBe("dogrulama");
    expect(hata.alanlar).toEqual({ ad: "zorunlu" });
    expect(hata.durum).toBe(422);
  });

  it("ağ hatasında 'ag' kodlu ApiHatasi üretir", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.error()));
    const hata = (await cagir(api.GET("/api/v1/senaryolar")).catch((e: unknown) => e)) as ApiHatasi;
    expect(hata).toBeInstanceOf(ApiHatasi);
    expect(hata.hata).toBe("ag");
    expect(hata.mesaj).toBe("Sunucuya ulaşılamadı");
  });

  it("X-Kullanici başlığı yüzde kodlanır", async () => {
    let gelen: string | null = null;
    sunucu.use(
      http.get("*/api/v1/senaryolar", ({ request }) => {
        gelen = request.headers.get("x-kullanici");
        return HttpResponse.json({ kayitlar: [], toplam: 0 });
      }),
    );
    kullanici.kaydet("Eşma");
    await cagir(api.GET("/api/v1/senaryolar"));
    expect(gelen).toBe("E%C5%9Fma");
  });

  it("JSON olmayan 502 gövdesini Türkçe mesajlı ApiHatasi'ne çevirir", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => HttpResponse.text("<html>", { status: 502 })));
    const h = (await cagir(api.GET("/api/v1/senaryolar")).catch((e: unknown) => e)) as ApiHatasi;
    expect(h).toBeInstanceOf(ApiHatasi);
    expect(h.durum).toBe(502);
    expect(h.mesaj).toMatch(/sunucu/i);
  });

  it("boş gövdeli 500 için 'sunucu' kodu üretir", async () => {
    sunucu.use(http.get("*/api/v1/senaryolar", () => new HttpResponse(null, { status: 500 })));
    const h = (await cagir(api.GET("/api/v1/senaryolar")).catch((e: unknown) => e)) as ApiHatasi;
    expect(h.hata).toBe("sunucu");
    expect(h.durum).toBe(500);
  });
});

describe("hataMetni", () => {
  it("alanlar yoksa yalnızca mesajı verir", () => {
    expect(hataMetni(new ApiHatasi("x", "Bir şey oldu"))).toBe("Bir şey oldu");
  });

  it("alanlar doluysa mesajın ardına 'alan: değer' çiftlerini ekler", () => {
    const e = new ApiHatasi("dogrulama", "İstek geçersiz", { fire: "0-100 olmalı", ad: "zorunlu" }, 422);
    expect(hataMetni(e)).toBe("İstek geçersiz — fire: 0-100 olmalı; ad: zorunlu");
  });

  it("nesne değerleri JSON olarak yazılır, bilinmeyen hata için genel mesaj döner", () => {
    expect(hataMetni(new ApiHatasi("d", "M", { detail: [1] }))).toBe("M — detail: [1]");
    expect(hataMetni(new Error("düz"))).toBe("düz");
    expect(hataMetni("garip")).toBe("Beklenmeyen hata");
  });
});

describe("kullanıcı adı olmadan yazma", () => {
  it("ad 'sistem' iken yazma isteği ağa gitmeden 'Önce üst bardan adınızı girin' ile reddedilir", async () => {
    localStorage.removeItem("fiyat-calismasi.kullanici");
    let istekSayisi = 0;
    sunucu.use(
      http.post("*/api/v1/senaryolar", () => {
        istekSayisi += 1;
        return HttpResponse.json({ id: 3 }, { status: 201 });
      }),
    );
    const h = (await cagir(
      api.POST("/api/v1/senaryolar", { body: { sezon_ad: "2026-2027", tur: "fiyat_calismasi", ad: "x" } }),
    ).catch((e: unknown) => e)) as ApiHatasi;
    expect(h).toBeInstanceOf(ApiHatasi);
    expect(h.mesaj).toBe("Önce üst bardan adınızı girin");
    expect(h.durum).toBe(400);
    expect(istekSayisi).toBe(0);
  });

  it("okuma ve hesapla çağrıları ad olmadan da çalışır", async () => {
    localStorage.removeItem("fiyat-calismasi.kullanici");
    await cagir(api.GET("/api/v1/senaryolar"));
    sunucu.use(http.post("*/api/v1/urunler/:kod/hesapla", () => HttpResponse.json({ ok: true })));
    await cagir(api.POST("/api/v1/urunler/{kod}/hesapla", { params: { path: { kod: "A" } }, body: { senaryo_id: 1 } }));
  });

  it("ad girilince yazma isteği gider", async () => {
    sunucu.use(http.post("*/api/v1/senaryolar", () => HttpResponse.json({ id: 3 }, { status: 201 })));
    kullanici.kaydet("Eşma");
    const v = await cagir(
      api.POST("/api/v1/senaryolar", { body: { sezon_ad: "2026-2027", tur: "fiyat_calismasi", ad: "x" } }),
    );
    expect(v).toBeTruthy();
  });
});

