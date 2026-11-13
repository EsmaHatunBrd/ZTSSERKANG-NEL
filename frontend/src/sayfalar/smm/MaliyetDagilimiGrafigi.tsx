import { useMemo } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { SmmKarsilastirma } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";

const UNSURLAR = [
  { anahtar: "ilk_madde", renk: "var(--chart-1)" },
  { anahtar: "iscilik", renk: "var(--chart-2)" },
  { anahtar: "gug", renk: "var(--chart-3)" },
] as const;

type Dilim = { ad: string; tutar: number; pay: number; renk: string };

const payMetni = (p: number) => `%${p.toFixed(1).replace(".", ",")}`;

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Dilim }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{d.ad}</div>
      <div className="tabular-nums">
        {paraBicimle(d.tutar, "TL", 0)} · {payMetni(d.pay)}
      </div>
    </div>
  );
}

/** Son dönemin üretim maliyeti dağılımı: ilk madde ve malzeme / direkt işçilik / genel üretim gideri (halka grafik). */
export function MaliyetDagilimiGrafigi({ veri }: { veri: SmmKarsilastirma }) {
  const son = veri.donemler[veri.donemler.length - 1];
  const dilimler = useMemo<Dilim[]>(() => {
    const ham = UNSURLAR.flatMap((u) => {
      const s = veri.satirlar.find((x) => x.anahtar === u.anahtar);
      const h = s?.hucreler[s.hucreler.length - 1];
      return s && h?.tutar != null ? [{ ad: s.ad, tutar: D(h.tutar).toNumber(), renk: u.renk }] : [];
    });
    const toplam = ham.reduce((a, x) => a + x.tutar, 0);
    return ham.map((x) => ({ ...x, pay: toplam ? (x.tutar / toplam) * 100 : 0 }));
  }, [veri]);
  if (!son || dilimler.length === 0) return null;
  const toplam = dilimler.reduce((a, x) => a + x.tutar, 0);
  const ozet = dilimler.map((d) => `${d.ad}: ${payMetni(d.pay)}`).join("; ");
  return (
    <figure className="flex flex-col gap-2" role="img" aria-label={`${son.ad} üretim maliyeti dağılımı. ${ozet}`}>
      <figcaption className="text-sm font-semibold">
        {son.ad}: üretim maliyeti dağılımı{" "}
        <span className="font-normal text-muted-foreground">(toplam {paraBicimle(toplam, "TL", 0)})</span>
      </figcaption>
      <div className="grid items-center gap-4 md:grid-cols-[minmax(0,320px)_1fr]">
        <div style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 320, height: 260 }}>
            <PieChart>
              <Pie
                data={dilimler}
                dataKey="tutar"
                nameKey="ad"
                innerRadius={62}
                outerRadius={104}
                paddingAngle={2}
                isAnimationActive={false}
              >
                {dilimler.map((d) => (
                  <Cell key={d.ad} fill={d.renk} stroke="var(--card)" />
                ))}
              </Pie>
              <Tooltip content={<Ipucu />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex flex-col gap-3">
          {dilimler.map((d) => (
            <li key={d.ad} className="flex flex-col gap-1">
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full" style={{ background: d.renk }} aria-hidden />
                  {d.ad}
                </span>
                <span className="tabular-nums">
                  <span className="text-muted-foreground">{paraBicimle(d.tutar, "TL", 0)}</span>{" "}
                  <span className="font-semibold">{payMetni(d.pay)}</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full" style={{ width: `${d.pay}%`, background: d.renk }} />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </figure>
  );
}
