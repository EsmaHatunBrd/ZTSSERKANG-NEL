export type Tema = "light" | "dark";
const ANAHTAR = "fiyat-calismasi.tema";

export function kayitliTema(): Tema | null {
  try {
    const v = localStorage.getItem(ANAHTAR);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

export function ilkTema(): Tema {
  const k = kayitliTema();
  if (k) return k;
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function temaUygula(t: Tema, kalici = true): void {
  document.documentElement.classList.toggle("dark", t === "dark");
  document.documentElement.style.colorScheme = t;
  if (kalici) {
    try {
      localStorage.setItem(ANAHTAR, t);
    } catch {
      /* localStorage kullanilamiyor */
    }
  }
}
