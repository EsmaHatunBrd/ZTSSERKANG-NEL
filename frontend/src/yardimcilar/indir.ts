/** `Content-Disposition: attachment; filename="..."` başlığından dosya adı; yoksa null. */
export function dosyaAdi(baslik: string | null): string | null {
  const m = /filename="?([^";]+)"?/i.exec(baslik ?? "");
  return m ? m[1] : null;
}

/**
 * Sunucunun ürettiği dosyayı indirir ve bitince döner (düğmede "Hazırlanıyor…" göstermek için; düz `<a download>` bitişi bildirmez).
 * Hata yanıtında sunucunun mesajıyla `Error` fırlatır.
 */
export async function dosyaIndir(adres: string, varsayilanAd: string): Promise<void> {
  let yanit: Response;
  try {
    yanit = await globalThis.fetch(adres, { credentials: "same-origin" });
  } catch {
    throw new Error("Sunucuya ulaşılamadı");
  }
  if (!yanit.ok) {
    let mesaj = `Dosya hazırlanamadı (HTTP ${yanit.status})`;
    try {
      const g = (await yanit.json()) as { mesaj?: unknown };
      if (typeof g.mesaj === "string") mesaj = g.mesaj;
    } catch {
      /* gövde JSON değil */
    }
    throw new Error(mesaj);
  }
  const blob = await yanit.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = dosyaAdi(yanit.headers.get("Content-Disposition")) ?? varsayilanAd;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
