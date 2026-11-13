import { useMemo } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SmmKarsilastirma } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const OLCU = { width: 640, height: 280 };
const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
/** Üç maliyet unsuru yığılı çubuk, SMM toplamı çizgi. */
const SERILER = [
  { anahtar: "ilk_madde", ad: "İlk madde ve malzeme", renk: "var(--chart-1)" },
  { anahtar: "iscilik", ad: "Direkt işçilik", renk: "var(--chart-2)" },
  { anahtar: "gug", ad: "Genel üretim gideri", renk: "var(--chart-3)" },
] as const;
const SMM = { anahtar: "smm", ad: "SMM (620)", renk: "var(--chart-5)" } as const;

type Nokta = { donem: string } & Record<string, number | string>;
const mn = (x: number) => `${paraBicimle(x, "", 1)} mn`;

function Ipucu({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4 tabular-nums">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full" style={{ background: p.color }} aria-hidden />
            {p.name}
          </span>
          <span>{mn(p.value)} TL</span>
        </div>
      ))}
    </div>
  );
}

/** Dönemlere göre üç maliyet unsuru (yığılı) ve SMM toplamı (çizgi), milyon TL. */
export function AylarArasiGrafigi({ veri }: { veri: SmmKarsilastirma }) {
  const noktalar = useMemo<Nokta[]>(
    () =>
      veri.donemler.map((d, i) => {
        const n: Nokta = { donem: d.ad };
        for (const s of [...SERILER, SMM]) {
          const satir = veri.satirlar.find((x) => x.anahtar === s.anahtar);
          n[s.anahtar] = D(satir?.hucreler[i]?.tutar).dividedBy(1_000_000).toDecimalPlaces(3).toNumber();
        }
        return n;
      }),
    [veri],
  );
  const ozet = noktalar.map((n) => `${n.donem}: SMM ${mn(Number(n.smm))} TL`).join("; ");
  return (
    <figure className="flex flex-col gap-1" role="img" aria-label={`Dönemlere göre maliyet unsurları ve SMM. ${ozet}`}>
      <figcaption className="text-sm font-medium">Maliyet unsurları ve SMM (milyon TL)</figcaption>
      <div style={{ height: OLCU.height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
          <ComposedChart data={noktalar} margin={{ left: 0, right: 16, top: 8, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="donem" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
            <YAxis tick={EKSEN} tickLine={false} axisLine={false} width={56} tickFormatter={(x: number) => paraBicimle(x, "", 0)} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {SERILER.map((s) => (
              <Bar
                key={s.anahtar}
                dataKey={s.anahtar}
                name={s.ad}
                stackId="unsur"
                fill={s.renk}
                maxBarSize={56}
                isAnimationActive={false}
              />
            ))}
            <Line
              dataKey={SMM.anahtar}
              name={SMM.ad}
              stroke={SMM.renk}
              strokeWidth={2}
              dot={{ r: 3, fill: SMM.renk }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
