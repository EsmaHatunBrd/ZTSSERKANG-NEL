import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";
import { ilkTema, temaUygula } from "./yardimcilar/tema";

temaUygula(ilkTema(), false);

// Uygulama yeniden derlenince açık sekmedeki eski sayfa parçaları sunucuda kalmaz; o sekmede yeni bir sayfaya geçerken parça yüklenemez
// ve sayfa açılmaz. Böyle olunca sayfa bir kez kendiliğinden yenilenir (yeni sürüm gelir). Döngüye girmesin diye 30 sn'de en çok bir kez.
window.addEventListener("vite:preloadError", (olay) => {
  const anahtar = "fiyat-calismasi.surum-yenileme";
  try {
    const son = Number(sessionStorage.getItem(anahtar) ?? 0);
    if (Date.now() - son < 30_000) return;
    sessionStorage.setItem(anahtar, String(Date.now()));
  } catch {
    // depolama kapalıysa yine de bir kez yenile
  }
  olay.preventDefault();
  window.location.reload();
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
