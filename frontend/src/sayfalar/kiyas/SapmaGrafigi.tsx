import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BgSatir } from "@/api/tipler";
import { D } from "@/yardimcilar/para";

// Tek seri (ürün sayısı) tek renk; durum renkleri ayrılmış olduğundan sapan/sapmayan ayrımı renkle yapılmaz.
const RENK = "var(--chart-1)";
const OLCU = { width: 640, height: 200 };
const ADIM = 5; // yüzde puan
const UC = 20; // ±%20 dışı tek kutu

export interface Kutu {
  etiket: string;
  alt: number;
  ust: number;
  adet: number;
}

/** Maliyet TL sapma yüzdesini 5 puanlık kutulara sayar; ±%20 dışı uç kutulara düşer. Sapması olmayan satırlar sayılmaz. */
export function kutular(satirlar: BgSatir[]): Kutu[] {
  const out: Kutu[] = [{ etiket: `< -${UC}`, alt: -Infinity, ust: -UC, adet: 0 }];
  for (let x = -UC; x < UC; x += ADIM)
    out.push({ etiket: `${x > 0 ? "+" : ""}${x}…${x + ADIM > 0 ? "+" : ""}${x + ADIM}`, alt: x, ust: x + ADIM, adet: 0 });
  out.push({ etiket: `> +${UC}`, alt: UC, ust: Infinity, adet: 0 });
  for (const s of satirlar) {
    if (s.sapma_yuzde === null) continue;
    const v = D(s.sapma_yuzde).toNumber();
    const k = out.find((b) => v >= b.alt && v < b.ust) ?? out[out.length - 1];
    k.adet += 1;
  }
  return out;
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Kutu }[] }) {
  const k = payload?.[0]?.payload;
  if (!active || !k) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">Sapma {k.etiket} %</div>
      <div className="tabular-nums">{k.adet} ürün</div>
    </div>
  );
}

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };

/** Sapma dağılımı: x = maliyet TL sapması (yüzde kutusu), y = ürün sayısı. */
export function SapmaGrafigi({ satirlar }: { satirlar: BgSatir[] }) {
  const veri = useMemo(() => kutular(satirlar), [satirlar]);
  const ozet = veri.map((k) => `${k.etiket} %: ${k.adet}`).join("; ");
  return (
    <figure className="flex flex-col gap-1" role="img" aria-label={`Maliyet sapması dağılımı, ürün sayısı. ${ozet}`}>
      <figcaption className="text-sm font-medium">Maliyet sapması dağılımı (yüzde, ürün sayısı)</figcaption>
      <div style={{ height: OLCU.height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
          <BarChart data={veri} margin={{ left: 0, right: 16, top: 8, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="etiket" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval={0} />
            <YAxis tick={EKSEN} tickLine={false} axisLine={false} width={32} allowDecimals={false} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Bar dataKey="adet" name="Ürün sayısı" fill={RENK} radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
