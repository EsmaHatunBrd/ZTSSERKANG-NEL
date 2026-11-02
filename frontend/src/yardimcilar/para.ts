import Decimal from "decimal.js";

/** Bilinen para birimleri; gösterimde herhangi bir döviz metni de kabul edilir ("" = birim yazılmaz). */
export type ParaBirimi = "TL" | "USD" | "EUR" | "GBP" | "CHF" | (string & {});
export type Girdi = string | number | Decimal | null | undefined;

/** Girdiyi Decimal'e çevirir. null/boş -> 0. "1.234,56" ve "1234,56" desteklenir. */
export function D(x: Girdi): Decimal {
  if (x === null || x === undefined) return new Decimal(0);
  if (x instanceof Decimal) return x;
  if (typeof x === "number") return new Decimal(x);
  let s = x.trim().replace(/\s/g, "");
  if (s === "") return new Decimal(0);
  if (s.includes(",")) {
    s = s.replace(/\./g, "").replace(",", ".");
  } else if ((s.match(/\./g) ?? []).length > 1) {
    s = s.replace(/\./g, "");
  }
  try {
    return new Decimal(s);
  } catch {
    return new Decimal(0);
  }
}

export function topla(xs: (string | Decimal)[]): Decimal {
  return xs.reduce<Decimal>((t, x) => t.plus(D(x)), new Decimal(0));
}

function sayiBicimle(d: Decimal, basamak: number): string {
  const yuvarlak = d.toDecimalPlaces(basamak, Decimal.ROUND_HALF_UP).toFixed(basamak);
  const bicim = new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: basamak,
    maximumFractionDigits: basamak,
  });
  // Metin verilir: Intl kesin ondalık metni okur, Number() ile hassasiyet kaybı olmaz.
  return bicim.format(yuvarlak as unknown as number);
}

export function paraBicimle(x: Girdi, paraBirimi: ParaBirimi = "TL", basamak = 2): string {
  const sayi = sayiBicimle(D(x), basamak);
  return paraBirimi === "" ? sayi : `${sayi} ${paraBirimi}`;
}

/** Oran (0.19736) -> "19,7 %". */
export function yuzdeBicimle(oran: Girdi, basamak = 1): string {
  return `${sayiBicimle(D(oran).times(100), basamak)} %`;
}

/** API'ye gönderilecek düz metin (nokta ondalık, üstel gösterim yok). */
export function apiMetni(d: Decimal): string {
  return d.toFixed();
}
