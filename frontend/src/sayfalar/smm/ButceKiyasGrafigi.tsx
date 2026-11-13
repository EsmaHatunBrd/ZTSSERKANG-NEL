import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SmmButceKiyasSatiri } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const EN_COK = 15;

type Nokta = { ad: string; kod: string; kisa: string; butce: number; fiili: number };

function Ipucu({ active, payload }: { active?: boolean; payload?: { name: string; value: number; color: string; payload: Nokta }[] }) {
  if (!active || !payload?.length) return null;
  const n = payload[0].payload;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.ad}</div>
      <div className="text-xs text-muted-foreground">{n.kod}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4 tabular-nums">
          <span className="flex items-center gap-1.5">
            <span className="size-2 rounded-full" style={{ background: p.color }} aria-hidden />
            {p.name}
          </span>
          <span>{paraBicimle(p.value, "TL", 2)}</span>
        </div>
      ))}
      <div className="mt-1 border-t pt-1 text-xs tabular-nums">Fark: {paraBicimle(n.fiili - n.butce, "TL", 2)}</div>
    </div>
  );
}

/** Bütçe ve fiili birim maliyet yan yana: farkı (mutlak TL) en büyük ürünler; yalnız dönemde üretilmiş ve farkı hesaplanmış olanlar. */
export function ButceKiyasGrafigi({ kayitlar }: { kayitlar: SmmButceKiyasSatiri[] }) {
  const veri = useMemo<Nokta[]>(
    () =>
      kayitlar
        .filter((k) => k.fark_tl != null && k.butce_maliyet_tl != null && k.fiili_birim_maliyet_tl != null)
        .sort((a, b) => D(b.fark_tl).abs().comparedTo(D(a.fark_tl).abs()))
        .slice(0, EN_COK)
        .map((k) => ({
          ad: k.ad,
          kod: k.kod,
          kisa: k.ad.length > 30 ? `${k.ad.slice(0, 29)}…` : k.ad,
          butce: D(k.butce_maliyet_tl).toDecimalPlaces(2).toNumber(),
          fiili: D(k.fiili_birim_maliyet_tl).toDecimalPlaces(2).toNumber(),
        })),
    [kayitlar],
  );
  if (veri.length === 0) return <p className="text-sm text-muted-foreground">Grafik için farkı hesaplanmış ürün yok.</p>;
  const yukseklik = 72 + veri.length * 38;
  const ozet = veri.map((n) => `${n.ad}: bütçe ${n.butce}, fiili ${n.fiili}`).join("; ");
  return (
    <figure
      className="flex flex-col gap-2"
      role="img"
      aria-label={`Bütçe ve fiili birim maliyet, farkı en büyük ${veri.length} ürün. ${ozet}`}
    >
      <figcaption className="text-sm font-semibold">Bütçe ve fiili birim maliyet: farkı en büyük {veri.length} ürün</figcaption>
      <div style={{ height: yukseklik }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height: yukseklik }}>
          <BarChart data={veri} layout="vertical" margin={{ left: 0, right: 24, top: 4, bottom: 4 }} barGap={2}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} unit=" TL" />
            <YAxis type="category" dataKey="kisa" tick={EKSEN} tickLine={false} axisLine={false} width={210} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="butce" name="Bütçe" fill="var(--chart-2)" maxBarSize={14} isAnimationActive={false} />
            <Bar dataKey="fiili" name="Fiili" fill="var(--chart-1)" maxBarSize={14} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
