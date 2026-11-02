import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HesapSatiri } from "@/api/tipler";
import { D, topla, yuzdeBicimle } from "@/yardimcilar/para";

const ILK_N = 12;
// Marka paleti (dataviz doğrulandı): seri 1 yeşil = maliyet payı, seri 2 mavi = satış payı. Tema token'ları açık/koyu için ayrı adımlardır.
const MALIYET_RENGI = "var(--chart-1)";
const SATIS_RENGI = "var(--chart-2)";

interface Veri {
  ad: string;
  maliyet: number;
  satis: number;
  maliyetMetni: string;
  satisMetni: string;
}

/** Yalnız çizim için sayıya çevrilir (yüzde puanı); tooltip ve toplamlar Decimal metninden gelir. */
const cizim = (d: string) => Number(D(d).times(100).toDecimalPlaces(3).toString());

function veriHazirla(satirlar: HesapSatiri[]): Veri[] {
  const payli = satirlar.filter((s) => s.maliyet_yuzdesi !== null || s.fiyat_yuzdesi !== null);
  const sirali = [...payli].sort((a, b) => D(b.maliyet_yuzdesi).comparedTo(D(a.maliyet_yuzdesi)));
  const ilk = sirali.slice(0, ILK_N);
  const kalan = sirali.slice(ILK_N);
  const veri: Veri[] = ilk.map((s) => ({
    ad: s.kalem,
    maliyet: cizim(s.maliyet_yuzdesi ?? "0"),
    satis: cizim(s.fiyat_yuzdesi ?? "0"),
    maliyetMetni: yuzdeBicimle(s.maliyet_yuzdesi ?? "0", 2),
    satisMetni: yuzdeBicimle(s.fiyat_yuzdesi ?? "0", 2),
  }));
  if (kalan.length > 0) {
    const m = topla(kalan.map((s) => s.maliyet_yuzdesi ?? "0"));
    const f = topla(kalan.map((s) => s.fiyat_yuzdesi ?? "0"));
    veri.push({
      ad: `Diğer (${kalan.length})`,
      maliyet: cizim(m.toFixed()),
      satis: cizim(f.toFixed()),
      maliyetMetni: yuzdeBicimle(m, 2),
      satisMetni: yuzdeBicimle(f, 2),
    });
  }
  return veri;
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Veri }[] }) {
  const v = payload?.[0]?.payload;
  if (!active || !v) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="mb-1 font-medium">{v.ad}</div>
      <div>Maliyet payı: {v.maliyetMetni}</div>
      <div>Satış payı: {v.satisMetni}</div>
    </div>
  );
}

export function YuzdeGrafigi({ satirlar }: { satirlar: HesapSatiri[] }) {
  const veri = useMemo(() => veriHazirla(satirlar), [satirlar]);
  if (veri.length === 0) return null;
  const ozet = veri
    .slice(0, 3)
    .map((v) => `${v.ad} maliyet ${v.maliyetMetni}, satış ${v.satisMetni}`)
    .join("; ");
  return (
    <section aria-label="Yüzde dağılımı" className="flex flex-col gap-2">
      <h2 className="text-base font-semibold">Maliyet ve satış payları</h2>
      <div
        role="img"
        aria-label={`Maliyet ve satış payları, yatay çubuk grafik. En büyük kalemler: ${ozet}`}
        style={{ height: Math.max(220, veri.length * 40 + 60) }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={veri} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--border)" />
            <XAxis type="number" unit=" %" tick={{ fontSize: 12 }} />
            <YAxis type="category" dataKey="ad" width={150} tick={{ fontSize: 12 }} />
            <Tooltip content={<Ipucu />} cursor={{ fillOpacity: 0.08 }} />
            <Legend />
            <Bar dataKey="maliyet" name="Maliyet payı" fill={MALIYET_RENGI} radius={[0, 4, 4, 0]} isAnimationActive={false} />
            <Bar dataKey="satis" name="Satış payı" fill={SATIS_RENGI} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
