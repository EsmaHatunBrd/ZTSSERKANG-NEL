import type { HesapSatiri } from "@/api/tipler";
import { kaynakMetni } from "@/bilesenler/KaynakRozeti";
import { D, paraBicimle } from "@/yardimcilar/para";
import { MALZEME, sayiGoster } from "./yardimci";

/** Reçete satırındaki tutarların "bu sayı nereden geldi" açıklamaları (hücre `title` ve klavye ipucu). */
export interface FormulIpuclari {
  brut?: string;
  firesiz?: string;
  fireli?: string;
}

/** Motorun kur uyguladığı para birimleri (fiyat_motoru/malzeme.py DOVIZLER). */
const DOVIZLER = ["USD", "EUR", "GBP", "CHF"];

const yuzde = (oran: string) => `%${sayiGoster(D(oran).times(100).toFixed(), 4)}`;

/**
 * Satırdaki alanlardan formül metni üretir; kur ve enflasyon değerleri satırda olmadığı için uydurulmaz:
 * çarpım TL tutara eşitse "=", değilse "→ … (kur/enflasyon uygulanmış)" yazılır.
 * Formülü olmayan satırlarda (gider, ara mamul, eksik alan) boş nesne döner.
 */
export function formulIpucu(s: HesapSatiri): FormulIpuclari {
  if (s.grup !== MALZEME || s.dugum_tipi === "ara_mamul") return {};
  if (s.miktar == null || s.brut_miktar == null || s.birim_fiyat == null) return {};
  const birim = s.birim ? ` ${s.birim}` : "";
  const doviz = s.doviz ?? "TL";
  const miktar = sayiGoster(s.miktar, 6);
  const brut = sayiGoster(s.brut_miktar, 6);
  const fiyat = `${sayiGoster(s.birim_fiyat, 4)} ${doviz}`;
  const elleBrut = s.miktar_kaynagi === "elle" || s.brut_miktar_elle != null;
  const fire = s.fire_orani != null && !D(s.fire_orani).isZero() ? s.fire_orani : null;
  const miktarTuru = s.miktar_kaynagi ?? (elleBrut ? "elle" : "fire");
  const miktarKaynagi = miktarTuru === "fire" ? "Fire kuralı" : kaynakMetni(miktarTuru);
  const fiyatKaynagi = kaynakMetni(s.fiyat_kaynagi ?? "liste");

  const sonuc = (carpanHam: string, tutar: string | null) => {
    const carpan = sayiGoster(carpanHam, 6);
    if (tutar == null) return `${carpan}${birim} × ${fiyat}`;
    const tl = paraBicimle(tutar, "TL", 2);
    const esit = D(carpanHam)
      .times(s.birim_fiyat as string)
      .toDecimalPlaces(2)
      .eq(D(tutar).toDecimalPlaces(2));
    if (esit) return `${carpan}${birim} × ${fiyat} = ${tl}`;
    const neden = DOVIZLER.includes(doviz) ? "kur uygulanmış" : doviz === "TL" ? "enflasyon uygulanmış" : "katsayı uygulanmış";
    return `${carpan}${birim} × ${fiyat} → ${tl} (${neden})`;
  };

  const brutAciklama = elleBrut
    ? `Brüt elle girildi: ${brut}${birim} (fire uygulanmaz)`
    : fire
      ? `Brüt = miktar ÷ (1 − fire): ${miktar} ÷ (1 − ${yuzde(fire)}) = ${brut}${birim}`
      : `Brüt = miktar (fire %0): ${brut}${birim}`;
  const brutKisa = elleBrut ? "brüt elle girildi" : fire ? `brüt = ${miktar} ÷ (1 − ${yuzde(fire)} fire)` : "brüt = miktar (fire %0)";

  return {
    brut: `${brutAciklama}${miktarKaynagi ? ` · miktar: ${miktarKaynagi}` : ""}`,
    firesiz: `Tutar (firesiz) = miktar × birim fiyat: ${sonuc(s.miktar, s.tutar_firesiz)}${fiyatKaynagi ? ` · fiyat: ${fiyatKaynagi} (${doviz})` : ""}`,
    fireli: `Tutar (fireli) = brüt × birim fiyat: ${sonuc(s.brut_miktar, s.tutar)} · ${brutKisa}`,
  };
}
