import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AileSatiri } from "@/api/tipler";
import { ambalajMetni } from "@/yardimcilar/ambalaj";
import { D, paraBicimle } from "@/yardimcilar/para";

// Marka paleti (--chart-* token'ları açık/koyu tema için ayrı adımlardır): çubuk = yeşil, çizgi = mavi.
const CUBUK_RENGI = "var(--chart-1)";
const CIZGI_RENGI = "var(--chart-2)";
const OLCU = { width: 640, height: 220 };

interface Nokta {
  kod: string;
  hacim: string;
  ad: string;
  satis: number | null;
  kgBasi: number | null;
  satisMetni: string;
  kgBasiMetni: string;
}

/** Yalnız çizim için sayıya çevrilir; tooltip metinleri Decimal'den biçimlenir. */
const cizim = (d: string | null) => (d === null ? null : Number(D(d).toDecimalPlaces(4).toString()));

/** Hatasız satırlar sunucu sırasıyla (ambalaj_ml) noktalara çevrilir; kategori anahtarı ürün kodudur (hatalı satır grafik dışıdır). */
export function noktalar(satirlar: AileSatiri[]): Nokta[] {
  return satirlar
    .filter((s) => !s.hata)
    .map((s) => ({
      kod: s.kod,
      hacim: ambalajMetni(s.ambalaj_etiket, s.ambalaj_hacmi),
      ad: s.ad,
      satis: cizim(s.satis_tl),
      kgBasi: cizim(s.kg_basi_satis_tl),
      satisMetni: s.satis_tl === null ? "—" : paraBicimle(s.satis_tl, "TL", 2),
      kgBasiMetni: s.kg_basi_satis_tl === null ? "—" : paraBicimle(s.kg_basi_satis_tl, "TL", 2),
    }));
}

function Ipucu({ active, payload, etiket, alan }: { active?: boolean; payload?: { payload: Nokta }[]; etiket: string; alan: "satisMetni" | "kgBasiMetni" }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.hacim}</div>
      <div className="text-xs text-muted-foreground">{n.ad}</div>
      <div className="mt-1">
        {etiket}: <span className="tabular-nums">{n[alan]}</span>
      </div>
    </div>
  );
}

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const sayiEkseni = (v: number) => new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 }).format(v);

/**
 * Tek eksen kuralı (dataviz): iki ölçü (birim satış TL ve kg başı satış TL) farklı ölçekte olduğundan
 * çift eksenli tek grafik yerine ortak kategorik x eksenli iki üst üste panel çizilir.
 */
export function AileGrafigi({ satirlar, aile }: { satirlar: AileSatiri[]; aile: string }) {
  const veri = useMemo(() => noktalar(satirlar), [satirlar]);
  if (veri.length === 0) return null;
  const etiketOf = (kod: string) => veri.find((n) => n.kod === kod)?.hacim ?? kod;
  const ozet = veri.map((n) => `${n.hacim}: birim satış ${n.satisMetni}, kg başı satış ${n.kgBasiMetni}`).join("; ");
  const kenar = { left: 8, right: 16, top: 8, bottom: 4 };
  return (
    <div className="flex flex-col gap-4" role="img" aria-label={`${aile} ailesi, ambalaj hacmine göre birim satış ve kg başı satış grafiği. ${ozet}`}>
      <figure className="flex flex-col gap-1" data-grafik="birim-satis">
        <figcaption className="text-sm font-medium">
          <span className="mr-2 inline-block size-2.5 rounded-sm align-middle" style={{ background: CUBUK_RENGI }} aria-hidden />
          Birim satış fiyatı (TL)
        </figcaption>
        <div style={{ height: OLCU.height }}>
          <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
            <BarChart data={veri} margin={kenar}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="kod" tickFormatter={etiketOf} tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
              <YAxis tick={EKSEN} tickLine={false} axisLine={false} width={56} tickFormatter={sayiEkseni} />
              <Tooltip content={<Ipucu etiket="Birim satış" alan="satisMetni" />} cursor={{ fill: "var(--muted)", fillOpacity: 0.5 }} />
              <Bar dataKey="satis" name="Birim satış (TL)" fill={CUBUK_RENGI} radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </figure>
      <figure className="flex flex-col gap-1" data-grafik="kg-basi">
        <figcaption className="text-sm font-medium">
          <span className="mr-2 inline-block h-0.5 w-4 align-middle" style={{ background: CIZGI_RENGI }} aria-hidden />
          Kg başı satış (TL)
        </figcaption>
        <div style={{ height: OLCU.height }}>
          <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
            <LineChart data={veri} margin={kenar}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="kod" tickFormatter={etiketOf} tick={EKSEN} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
              <YAxis tick={EKSEN} tickLine={false} axisLine={false} width={56} tickFormatter={sayiEkseni} domain={["auto", "auto"]} />
              <Tooltip content={<Ipucu etiket="Kg başı satış" alan="kgBasiMetni" />} cursor={{ stroke: "var(--border)" }} />
              <Line
                type="monotone"
                dataKey="kgBasi"
                name="Kg başı satış (TL)"
                stroke={CIZGI_RENGI}
                strokeWidth={2}
                dot={{ r: 4, fill: CIZGI_RENGI, stroke: "var(--card)", strokeWidth: 2 }}
                activeDot={{ r: 5, fill: CIZGI_RENGI, stroke: "var(--card)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </figure>
    </div>
  );
}
