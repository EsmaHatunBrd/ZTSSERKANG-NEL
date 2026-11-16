import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SmmGiderAsamasi } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };

type Nokta = { ad: string; iscilik: number; gug: number; birlesik: number };

function Ipucu({ active, payload }: { active?: boolean; payload?: { name: string; value: number; color: string; payload: Nokta }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{payload[0].payload.ad}</div>
      {payload
        .filter((p) => p.value)
        .map((p) => (
          <div key={p.name} className="flex items-center justify-between gap-4 tabular-nums">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: p.color }} aria-hidden />
              {p.name}
            </span>
            <span>{paraBicimle(p.value, "TL", 0)}</span>
          </div>
        ))}
    </div>
  );
}

/** Aşama başına dağıtılan işçilik ve GÜG, yatay yığılı çubuk. 20 ve 50'de havuz birleşik (işçilik + GÜG) olduğundan ayrı renk. */
export function GiderDagitimGrafigi({ asamalar }: { asamalar: SmmGiderAsamasi[] }) {
  const veri = useMemo<Nokta[]>(
    () =>
      asamalar.map((a) => ({
        ad: `${a.asama} · ${a.ad}`,
        iscilik: a.birlesik ? 0 : D(a.iscilik).toDecimalPlaces(0).toNumber(),
        gug: a.birlesik ? 0 : D(a.gug).toDecimalPlaces(0).toNumber(),
        birlesik: a.birlesik ? D(a.toplam).toDecimalPlaces(0).toNumber() : 0,
      })),
    [asamalar],
  );
  if (veri.every((n) => n.iscilik + n.gug + n.birlesik === 0)) {
    return <p className="text-sm text-muted-foreground">Grafik için dağıtılmış gider yok.</p>;
  }
  const yukseklik = 72 + veri.length * 44;
  const ozet = veri
    .map((n) =>
      n.birlesik
        ? `${n.ad}: işçilik + GÜG ${paraBicimle(n.birlesik, "TL", 0)}`
        : `${n.ad}: işçilik ${paraBicimle(n.iscilik, "TL", 0)}, GÜG ${paraBicimle(n.gug, "TL", 0)}`,
    )
    .join("; ");
  return (
    <figure className="flex flex-col gap-2" role="img" aria-label={`Aşamalara dağıtılan işçilik ve genel üretim gideri. ${ozet}`}>
      <figcaption className="text-sm font-semibold">Aşamalara dağıtılan işçilik ve GÜG</figcaption>
      <div style={{ height: yukseklik }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height: yukseklik }}>
          <BarChart data={veri} layout="vertical" margin={{ left: 0, right: 24, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis
              type="number"
              tick={EKSEN}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              tickFormatter={(x: number) => paraBicimle(x, "", 0)}
            />
            <YAxis type="category" dataKey="ad" tick={EKSEN} tickLine={false} axisLine={false} width={150} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="iscilik" name="İşçilik (720)" stackId="g" fill="var(--chart-2)" maxBarSize={22} isAnimationActive={false} />
            <Bar dataKey="gug" name="GÜG (730)" stackId="g" fill="var(--chart-3)" maxBarSize={22} isAnimationActive={false} />
            <Bar
              dataKey="birlesik"
              name="İşçilik + GÜG (ayrılmamış)"
              stackId="g"
              fill="var(--chart-4)"
              maxBarSize={22}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
