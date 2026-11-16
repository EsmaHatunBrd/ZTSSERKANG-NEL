import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SmmSarfOzetKalemi } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const FAZLA = "var(--chart-5)"; // kırmızı: fazla harcanan
const EKSIK = "var(--chart-1)"; // yeşil: az harcanan

type Nokta = { kod: string; ad: string; kisa: string; tutar: number };

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Nokta }[] }) {
  if (!active || !payload?.length) return null;
  const n = payload[0].payload;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.ad}</div>
      <div className="text-xs text-muted-foreground">{n.kod}</div>
      <div className="tabular-nums">
        {n.tutar > 0 ? "Fazla harcanan" : "Az harcanan"}: {paraBicimle(Math.abs(n.tutar), "TL", 0)}
      </div>
    </div>
  );
}

/** En büyük sarf farkları: fazla (kırmızı) sağa, eksik (yeşil) sola; sıfır ekseni ortada. Çubuğa tıklayınca o kalem seçilir. */
export function SarfFarkiGrafigi({ kalemler, onSec }: { kalemler: SmmSarfOzetKalemi[]; onSec: (kod: string) => void }) {
  const veri = useMemo<Nokta[]>(
    () =>
      kalemler.map((k) => {
        const ad = k.ad ?? k.kod;
        return { kod: k.kod, ad, kisa: ad.length > 28 ? `${ad.slice(0, 27)}…` : ad, tutar: D(k.fark_tutar).toDecimalPlaces(0).toNumber() };
      }),
    [kalemler],
  );
  if (veri.length === 0) return <p className="text-sm text-muted-foreground">Farkı olan kalem yok.</p>;
  const sinir = Math.max(...veri.map((n) => Math.abs(n.tutar)), 1);
  const yukseklik = 48 + veri.length * 28;
  const ozet = veri.map((n) => `${n.ad}: ${n.tutar > 0 ? "fazla" : "eksik"} ${paraBicimle(Math.abs(n.tutar), "TL", 0)}`).join("; ");
  return (
    <figure className="flex flex-col gap-2" role="img" aria-label={`En büyük ${veri.length} sarf farkı. ${ozet}`}>
      <figcaption className="text-sm font-semibold">
        En büyük {veri.length} fark <span className="font-normal text-muted-foreground">· sağda fazla harcanan, solda az harcanan</span>
      </figcaption>
      <div style={{ height: yukseklik }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height: yukseklik }}>
          <BarChart data={veri} layout="vertical" margin={{ left: 0, right: 24, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis
              type="number"
              domain={[-sinir, sinir]}
              tick={EKSEN}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              tickFormatter={(x: number) => paraBicimle(x, "", 0)}
            />
            <YAxis type="category" dataKey="kisa" tick={EKSEN} tickLine={false} axisLine={false} width={200} />
            <ReferenceLine x={0} stroke="var(--muted-foreground)" />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Bar
              dataKey="tutar"
              name="Fark tutarı"
              maxBarSize={16}
              isAnimationActive={false}
              cursor="pointer"
              onClick={(n: { payload?: Nokta }) => n.payload && onSec(n.payload.kod)}
            >
              {veri.map((n) => (
                <Cell key={n.kod} fill={n.tutar > 0 ? FAZLA : EKSIK} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
