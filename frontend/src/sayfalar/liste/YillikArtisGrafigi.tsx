import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ListeYilSatiri } from "@/api/tipler";
import { D, yuzdeBicimle } from "@/yardimcilar/para";

const OLCU = { width: 640, height: 240 };
const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const SERI = [
  { anahtar: "liste", ad: "Liste fiyatı artışı", renk: "var(--chart-1)" },
  { anahtar: "maliyet", ad: "Maliyet artışı", renk: "var(--chart-2)" },
] as const;

interface Nokta {
  yil: string;
  liste: number | null;
  maliyet: number | null;
  urun: number;
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Nokta }[] }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.yil} (önceki yıla göre)</div>
      {SERI.map((s) => (
        <div key={s.anahtar} className="flex items-center gap-2 tabular-nums">
          <span className="size-2.5 rounded-sm" style={{ background: s.renk }} aria-hidden />
          {s.ad}: {n[s.anahtar] === null ? "—" : yuzdeBicimle(n[s.anahtar] / 100)}
        </div>
      ))}
      <div className="text-xs text-muted-foreground">{n.urun} ürünün ortalaması</div>
    </div>
  );
}

/** Yıllara göre ortalama liste fiyatı artışı ile maliyet artışı yan yana (her yıl önceki yıla göre, yüzde). */
export function YillikArtisGrafigi({ yillar }: { yillar: ListeYilSatiri[] }) {
  const veri = useMemo<Nokta[]>(
    () =>
      yillar.map((y) => ({
        yil: String(y.yil),
        liste: y.liste_artis_ort === null ? null : D(y.liste_artis_ort).times(100).toNumber(),
        maliyet: y.maliyet_artis_ort === null ? null : D(y.maliyet_artis_ort).times(100).toNumber(),
        urun: y.urun_sayisi,
      })),
    [yillar],
  );
  const ozet = yillar
    .map(
      (y) =>
        `${y.yil}: liste ${y.liste_artis_ort === null ? "—" : yuzdeBicimle(y.liste_artis_ort)}, maliyet ${y.maliyet_artis_ort === null ? "—" : yuzdeBicimle(y.maliyet_artis_ort)}`,
    )
    .join("; ");
  return (
    <figure className="flex flex-col gap-2 rounded-xl border bg-card p-4" role="img" aria-label={`Yıllara göre artış. ${ozet}`}>
      <figcaption className="text-sm font-medium">Yıllara göre ortalama artış (önceki yıla göre, %)</figcaption>
      <div style={{ height: OLCU.height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
          <BarChart data={veri} margin={{ left: 0, right: 16, top: 8, bottom: 4 }} barGap={2}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="yil" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
            <YAxis tick={EKSEN} tickLine={false} axisLine={false} width={40} tickFormatter={(v: number) => `%${v}`} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {SERI.map((s) => (
              <Bar
                key={s.anahtar}
                dataKey={s.anahtar}
                name={s.ad}
                fill={s.renk}
                radius={[4, 4, 0, 0]}
                maxBarSize={36}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
