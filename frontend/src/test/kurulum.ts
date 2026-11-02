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

// globals: false oldugu icin otomatik temizlik yok.
afterEach(() => cleanup());
