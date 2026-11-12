import { useEffect } from "react";

export const AYRILMA_UYARISI = "Kaydedilmemiş değişiklikler var. Sayfadan ayrılmak istiyor musunuz?";

/**
 * `aktif` iken sekmeyi kapatma / yenileme / adres değiştirme girişiminde tarayıcının
 * "ayrılmak istiyor musunuz?" diyaloğunu açar (metni tarayıcı belirler; özelleştirilemez).
 * Uygulama içi (react-router) gezinme için ayrıca `useBlocker` + `OnayDiyalogu` kullanılır.
 */
export function useAyrilmaUyarisi(aktif: boolean) {
  useEffect(() => {
    if (!aktif) return;
    const engel = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Eski tarayıcılar için (Chrome < 119): returnValue dolu olmalı.
      e.returnValue = AYRILMA_UYARISI;
    };
    window.addEventListener("beforeunload", engel);
    return () => window.removeEventListener("beforeunload", engel);
  }, [aktif]);
}
