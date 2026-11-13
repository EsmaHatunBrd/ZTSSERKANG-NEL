import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SmmKartAsamasi } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const UNSURLAR = [
  { anahtar: "malzeme", ad: "Malzeme", renk: "var(--chart-1)" },
  { anahtar: "iscilik", ad: "İşçilik", renk: "var(--chart-2)" },
  { anahtar: "gug", ad: "GÜG", renk: "var(--chart-3)" },
  { anahtar: "fire", ad: "Fire", renk: "var(--chart-5)" },
] as const;

type Nokta = { etiket: string; kod: string } & Record<string, number | string>;

function Ipucu({ active, payload }: { active?: boolean; payload?: { name: string; value: number; color: string; payload: Nokta }[] }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{payload[0].payload.etiket}</div>
      <div className="text-xs text-muted-foreground">{payload[0].payload.kod}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4 tabular-nums">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full" style={{ background: p.color }} aria-hidden />
            {p.name}
          </span>
          <span>{paraBicimle(p.value, "TL", 4)}</span>
        </div>
      ))}
    </div>
  );
}

/** Aşama başına yığılı yatay çubuk: malzeme / işçilik / GÜG / fire (ürünün kendi birimi başına TL). */
export function AsamaGrafigi({ asamalar }: { asamalar: SmmKartAsamasi[] }) {
  const veri = useMemo<Nokta[]>(
    () =>
      asamalar.map((a) => ({
        etiket: `${a.asama} · ${a.ad}`,
        kod: a.kod,
        // Aynı aşamada birden çok yarı mamul olabilir: eksen etiketi benzersiz olsun.
        eksen: asamalar.filter((x) => x.asama === a.asama).length > 1 ? `${a.asama} · ${a.kod}` : `${a.asama} · ${a.ad}`,
        ...Object.fromEntries(UNSURLAR.map((u) => [u.anahtar, D(a[u.anahtar]).toDecimalPlaces(4).toNumber()])),
      })),
    [asamalar],
  );
  const yukseklik = Math.max(140, 56 + veri.length * 44);
  const ozet = asamalar.map((a) => `${a.asama} ${a.ad} (${a.kod}): ${paraBicimle(a.birim_maliyet, "TL", 2)}`).join("; ");
  return (
    <figure className="flex flex-col gap-1" role="img" aria-label={`Aşamalara göre birim maliyet dökümü. ${ozet}`}>
      <div style={{ height: yukseklik }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height: yukseklik }}>
          <BarChart data={veri} layout="vertical" margin={{ left: 0, right: 16, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
            <YAxis type="category" dataKey="eksen" tick={EKSEN} tickLine={false} axisLine={false} width={150} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {UNSURLAR.map((u) => (
              <Bar
                key={u.anahtar}
                dataKey={u.anahtar}
                name={u.ad}
                stackId="maliyet"
                fill={u.renk}
                maxBarSize={28}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
