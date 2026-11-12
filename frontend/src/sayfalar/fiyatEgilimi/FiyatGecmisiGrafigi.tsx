import { useMemo } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FiyatKaydi } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const OLCU = { width: 560, height: 240 };
const FIYAT_RENGI = "var(--chart-1)";
const ESIK_RENGI = "var(--chart-5)";

interface Nokta {
  tarih: string;
  etiket: string;
  fiyat: number;
  fiyatMetni: string;
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Nokta }[] }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.etiket}</div>
      <div className="tabular-nums">{n.fiyatMetni}</div>
    </div>
  );
}

interface Props {
  kayitlar: FiyatKaydi[];
  paraBirimi: string;
  /** Pencere başındaki fiyat (eşik çizgisi bunun üstüne kurulur). */
  ilkFiyat: string;
  /** Yüzde metni ("40.00" = %40). */
  esikYuzde: string;
}

/**
 * Malzemenin fiyat geçmişi: x tarih (geçerlilik başı), y fiyat. Kesikli referans çizgisi = ilk fiyat x (1 + eşik): bu çizginin üstü
 * senaryo enflasyonunu aşan fiyat. Çizim için sayıya çevrilir; ipucu ve eksen metinleri Decimal'den biçimlenir.
 */
export function FiyatGecmisiGrafigi({ kayitlar, paraBirimi, ilkFiyat, esikYuzde }: Props) {
  const veri = useMemo<Nokta[]>(
    () =>
      [...kayitlar]
        .sort((a, b) => a.gecerlilik_basi.localeCompare(b.gecerlilik_basi))
        .map((k) => ({
          tarih: k.gecerlilik_basi,
          etiket: goster(k.gecerlilik_basi),
          fiyat: D(k.fiyat).toNumber(),
          fiyatMetni: paraBicimle(k.fiyat, k.para_birimi ?? paraBirimi, 4),
        })),
    [kayitlar, paraBirimi],
  );
  const esik = D(ilkFiyat).times(D(1).plus(D(esikYuzde).dividedBy(100)));
  const esikMetni = paraBicimle(esik, paraBirimi, 4);
  if (veri.length === 0) return null;
  const ozet = veri.map((v) => `${v.etiket}: ${v.fiyatMetni}`).join("; ");
  return (
    <figure
      role="img"
      aria-label={`Fiyat geçmişi çizgi grafiği. Enflasyon eşiği ${esikMetni}. ${ozet}`}
      className="flex min-w-0 flex-col gap-2"
    >
      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded" style={{ background: FIYAT_RENGI }} aria-hidden />
          Fiyat
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded border-t border-dashed" style={{ borderColor: ESIK_RENGI }} aria-hidden />
          Enflasyon eşiği ({esikMetni})
        </span>
      </figcaption>
      <div style={{ height: OLCU.height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
          <LineChart data={veri} margin={{ left: 8, right: 16, top: 12, bottom: 4 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="etiket" tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} minTickGap={24} />
            <YAxis
              tick={EKSEN}
              tickLine={false}
              axisLine={false}
              width={72}
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => paraBicimle(v, "", 2)}
            />
            <Tooltip content={<Ipucu />} cursor={{ stroke: "var(--muted-foreground)", strokeDasharray: "3 3" }} />
            <ReferenceLine
              y={esik.toNumber()}
              stroke={ESIK_RENGI}
              strokeDasharray="4 4"
              ifOverflow="extendDomain"
              label={{ value: "Enflasyon eşiği", position: "insideTopRight", fontSize: 11, fill: ESIK_RENGI }}
            />
            <Line
              type="stepAfter"
              dataKey="fiyat"
              name="Fiyat"
              stroke={FIYAT_RENGI}
              strokeWidth={2}
              dot={{ r: 3, fill: FIYAT_RENGI, strokeWidth: 0 }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
