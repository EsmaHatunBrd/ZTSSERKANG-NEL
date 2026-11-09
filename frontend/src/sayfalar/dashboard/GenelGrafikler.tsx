import { useMemo } from "react";
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DashboardSatiri } from "@/api/tipler";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const OLCU = { width: 560, height: 320 };

/** Uzun ürün adı eksende kısaltılır (tam ad ipucunda). */
const kisa = (ad: string, n = 34) => (ad.length > n ? `${ad.slice(0, n - 1)}…` : ad);

interface Nokta {
  ad: string;
  kisa: string;
  maliyet: number;
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Nokta }[] }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.ad}</div>
      <div className="tabular-nums">{paraBicimle(n.maliyet)}</div>
    </div>
  );
}

/** En yüksek birim maliyetli 10 ürün: yatay, değer etiketli sıralama çubukları. */
function EnPahali({ satirlar }: { satirlar: DashboardSatiri[] }) {
  const veri = useMemo<Nokta[]>(
    () =>
      satirlar
        .filter((s) => !s.hata && s.maliyet_tl !== null)
        .sort((a, b) => D(b.maliyet_tl).comparedTo(D(a.maliyet_tl)))
        .slice(0, 10)
        .map((s) => ({ ad: s.ad, kisa: kisa(s.ad), maliyet: D(s.maliyet_tl).toNumber() })),
    [satirlar],
  );
  if (veri.length === 0) return null;
  const ozet = veri.map((v) => `${v.ad}: ${paraBicimle(v.maliyet)}`).join("; ");
  return (
    <figure
      className="flex min-w-0 flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs"
      role="img"
      aria-label={`En yüksek maliyetli ürünler. ${ozet}`}
    >
      <figcaption className="text-base font-semibold">En yüksek maliyetli 10 ürün</figcaption>
      <div style={{ height: OLCU.height }}>
        <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
          <BarChart data={veri} layout="vertical" margin={{ left: 0, right: 64, top: 0, bottom: 0 }} barCategoryGap={6}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="kisa" tick={EKSEN} tickLine={false} axisLine={false} width={250} />
            <Tooltip content={<Ipucu />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
            <Bar dataKey="maliyet" fill="var(--chart-1)" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList
                dataKey="maliyet"
                position="right"
                formatter={(v: unknown) => paraBicimle(String(v), "TL", 0)}
                style={{ fontSize: 12, fill: "var(--foreground)", fontVariantNumeric: "tabular-nums" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

const KALEMLER = [
  { alan: "recete_maliyeti", ad: "Malzeme", renk: "var(--chart-1)" },
  { alan: "gug", ad: "Üretim gideri", renk: "var(--chart-2)" },
  { alan: "faaliyet", ad: "Faaliyet gideri", renk: "var(--chart-3)" },
  { alan: "finans", ad: "Finansman", renk: "var(--chart-4)" },
] as const;

/** Maliyet yapısı: tüm ürünlerin toplam birim maliyetinde her kalemin payı (yığılmış tek çubuk + kalem listesi). */
function MaliyetYapisi({ satirlar }: { satirlar: DashboardSatiri[] }) {
  const paylar = useMemo(() => {
    const gecerli = satirlar.filter((s) => !s.hata && s.maliyet_tl !== null);
    const toplam = gecerli.reduce((t, s) => t.plus(D(s.recete_maliyeti)).plus(D(s.gug)).plus(D(s.faaliyet)).plus(D(s.finans)), D(0));
    if (toplam.isZero()) return null;
    return KALEMLER.map((k) => {
      const tutar = gecerli.reduce((t, s) => t.plus(D(s[k.alan])), D(0));
      return { ...k, pay: tutar.dividedBy(toplam), ortalama: tutar.dividedBy(gecerli.length) };
    });
  }, [satirlar]);
  if (!paylar) return null;
  return (
    <section aria-label="Maliyet yapısı" className="flex min-w-0 flex-col gap-4 rounded-2xl border bg-card p-5 shadow-xs">
      <div>
        <h2 className="text-base font-semibold">Maliyet yapısı</h2>
        <p className="text-sm text-muted-foreground">
          Tüm ürünlerin birim maliyet toplamında kalemlerin payı ve ürün başına ortalama tutarı
        </p>
      </div>
      <div className="flex h-4 w-full overflow-hidden rounded-full" aria-hidden>
        {paylar.map((p) => (
          <span key={p.alan} style={{ width: `${p.pay.times(100).toFixed(2)}%`, background: p.renk }} />
        ))}
      </div>
      <ul className="flex flex-col gap-3">
        {paylar.map((p) => (
          <li key={p.alan} className="flex flex-col gap-1">
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <span className="flex items-center gap-2">
                <span className="size-2.5 rounded-sm" style={{ background: p.renk }} aria-hidden />
                {p.ad}
              </span>
              <span className="flex items-baseline gap-2 tabular-nums">
                <span className="text-xs text-muted-foreground">ürün başına ort. {paraBicimle(p.ortalama)}</span>
                <span className="font-semibold">{yuzdeBicimle(p.pay)}</span>
              </span>
            </span>
            <span className="h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
              <span className="block h-full rounded-full" style={{ width: `${p.pay.times(100).toFixed(2)}%`, background: p.renk }} />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Genel Bakış grafikleri: en yüksek maliyetli ürünler ve maliyet yapısı (yan yana; dar ekranda alt alta). */
export function GenelGrafikler({ satirlar }: { satirlar: DashboardSatiri[] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <EnPahali satirlar={satirlar} />
      <MaliyetYapisi satirlar={satirlar} />
    </div>
  );
}
