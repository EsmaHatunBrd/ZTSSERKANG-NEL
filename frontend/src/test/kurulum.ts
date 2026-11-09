import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";

// findBy*/waitFor varsayılanı 1 sn; tam süit yükünde (20 dosya, lazy import + MSW) ilk render bunu aşabiliyor.
configure({ asyncUtilTimeout: 5000 });
import { afterEach, beforeEach } from "vitest";

const KULLANICI_ANAHTARI = "fiyat-calismasi.kullanici";

// Yazma istekleri kullanıcı adı ister (api/istemci): testlerde varsayılan olarak bir ad kayıtlıdır.
// Birçok test `localStorage.clear()` çağırır; temizlik kullanıcı adını silmesin diye clear() adı yeniden yazar.
// Adsız durumu denemek için `localStorage.removeItem(...)` kullanılır.
const gercekClear = Storage.prototype.clear;
Storage.prototype.clear = function clear(this: Storage) {
  gercekClear.call(this);
  if (this === globalThis.localStorage) this.setItem(KULLANICI_ANAHTARI, "Test Kullanıcı");
};

beforeEach(() => {
  try {
    localStorage.setItem(KULLANICI_ANAHTARI, "Test Kullanıcı");
  } catch {
    /* localStorage yok */
  }
});

// jsdom'da ResizeObserver yok; grafik (recharts ResponsiveContainer) içeren sayfalar onsuz çizilemez. Testlerin kendi sahtesi
// varsa o kullanılır; yoksa sabit boyut bildiren bu varsayılan.
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    cb: ResizeObserverCallback;
    constructor(cb: ResizeObserverCallback) {
      this.cb = cb;
    }
    observe(hedef: Element) {
      this.cb(
        [{ target: hedef, contentRect: { width: 600, height: 300 } } as unknown as ResizeObserverEntry],
        this as unknown as ResizeObserver,
      );
    }
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// globals: false oldugu icin otomatik temizlik yok.
afterEach(() => cleanup());
