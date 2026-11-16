import { useMemo } from "react";
import { Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { OnemliMalzemeSatiri } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const OLCU = { width: 720, height: 300 };
const TUTAR_RENGI = "var(--chart-1)";
const KUMULATIF_RENGI = "var(--chart-2)";
const ESIK_RENGI = "var(--chart-5)";
/** Grafikte gösterilen malzeme sayısı (en büyük tutarlılar). */
export const PARETO_ADEDI = 20;

interface Nokta {
  sira: number;
  etiket: string;
  ad: string;
  tutar: number;
  tutarMetni: string;
  kumulatif: number;
  kumulatifMetni: string;
  payMetni: string;
  icinde: boolean;
}

/** Büyük tutarlar için kısa eksen metni: 1.250.000 -> "1,3 Mn", 45.000 -> "45 B". */
function kisaTutar(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${paraBicimle(v / 1_000_000, "", 1).trim()} Mn`;
  if (Math.abs(v) >= 1_000) return `${paraBicimle(v / 1_000, "", 0).trim()} B`;
  return paraBicimle(v, "", 0).trim();
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Nokta }[] }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="max-w-64 rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">
        {n.sira}. {n.ad}
      </div>
      <div className="text-xs text-muted-foreground">{n.etiket}</div>
      <div className="tabular-nums">Yıllık tutar: {n.tutarMetni}</div>
      <div className="tabular-nums">
        Pay: {n.payMetni} · Kümülatif: {n.kumulatifMetni}
      </div>
    </div>
  );
}

interface Props {
  satirlar: OnemliMalzemeSatiri[];
  /** Eşik yüzdesi (80). */
  esik: number;
}

/**
 * Pareto grafiği: ilk 20 malzemenin yıllık tutarı (çubuk, sol eksen) ve kümülatif payı (çizgi, sağ eksen %); kesikli çizgi eşiktir.
 * Eşiğin dışında kalan malzemelerin çubuğu soluk çizilir. Çizim için sayıya çevrilir; metinler Decimal'den biçimlenir.
 */
export function ParetoGrafigi({ satirlar, esik }: Props) {
  const veri = useMemo<Nokta[]>(
    () =>
      satirlar.slice(0, PARETO_ADEDI).map((r) => ({
        sira: r.sira,
        etiket: r.kod || r.ad,
        ad: r.ad,
        tutar: D(r.yillik_tutar_tl).toNumber(),
        tutarMetni: paraBicimle(r.yillik_tutar_tl, "TL", 0),
        kumulatif: D(r.kumulatif_yuzde).toNumber(),
        kumulatifMetni: `%${paraBicimle(r.kumulatif_yuzde, "", 1).trim()}`,
        payMetni: `%${paraBicimle(r.pay_yuzde, "", 1).trim()}`,
        icinde: r.esik_icinde,
      })),
    [satirlar],
  );
  if (veri.length === 0) return null;
  const son = veri[veri.length - 1];
  const ozet = `İlk ${veri.length} malzeme toplam tutarın ${son.kumulatifMetni} kadarını oluşturuyor. En büyük: ${veri[0].ad}, ${veri[0].tutarMetni} (${veri[0].payMetni}).`;
  return (
    <figure role="img" aria-label={`Pareto grafiği. Eşik %${esik}. ${ozet}`} className="flex min-w-0 flex-col gap-2">
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: TUTAR_RENGI }} aria-hidden />
          Yıllık tutar (TL)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded" style={{ background: KUMULATIF_RENGI }} aria-hidden />
          Kümülatif pay (%)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded border-t border-dashed" style={{ borderColor: ESIK_RENGI }} aria-hidden />
          Eşik (%{esik})
        </span>
        <span>İlk {veri.length} malzeme</span>
      </figcaption>
      <div style={{ height: OLCU.height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
          <ComposedChart data={veri} margin={{ left: 8, right: 8, top: 12, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="sira" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} interval={0} />
            <YAxis yAxisId="tutar" tick={EKSEN} tickLine={false} axisLine={false} width={64} tickFormatter={kisaTutar} />
            <YAxis
              yAxisId="yuzde"
              orientation="right"
              domain={[0, 100]}
              ticks={[0, 20, 40, 60, 80, 100]}
              tick={EKSEN}
              tickLine={false}
              axisLine={false}
              width={44}
              tickFormatter={(v: number) => `%${v}`}
            />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", opacity: 0.5 }} />
            <Bar yAxisId="tutar" dataKey="tutar" name="Yıllık tutar" radius={[3, 3, 0, 0]} isAnimationActive={false}>
              {veri.map((n) => (
                <Cell key={n.sira} fill={TUTAR_RENGI} fillOpacity={n.icinde ? 1 : 0.35} />
              ))}
            </Bar>
            <ReferenceLine
              yAxisId="yuzde"
              y={esik}
              stroke={ESIK_RENGI}
              strokeDasharray="4 4"
              label={{ value: `%${esik}`, position: "insideTopLeft", fontSize: 11, fill: ESIK_RENGI }}
            />
            <Line
              yAxisId="yuzde"
              type="monotone"
              dataKey="kumulatif"
              name="Kümülatif pay"
              stroke={KUMULATIF_RENGI}
              strokeWidth={2}
              dot={{ r: 2.5, fill: KUMULATIF_RENGI, strokeWidth: 0 }}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
