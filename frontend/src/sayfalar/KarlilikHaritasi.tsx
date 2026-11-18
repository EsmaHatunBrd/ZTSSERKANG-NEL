import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowRight, Download, TriangleAlert, X } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { karlilikXlsxAdresi, useKarlilik } from "@/api/sorgular/analiz";
import type { KarlilikBolgesi, KarlilikSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { MaliyetHucresi } from "@/bilesenler/MaliyetHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button, buttonVariants } from "@/bilesenler/ui/button";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { D, paraBicimle, topla, yuzdeBicimle } from "@/yardimcilar/para";

interface BolgeTanimi {
  ad: KarlilikBolgesi;
  etiket: string;
  aciklama: string;
  renk: string;
  uyari?: boolean;
}

/** Sıra: önce müdahale gereken (çok satan, marjı zayıf). */
const BOLGELER: BolgeTanimi[] = [
  {
    ad: "yuksek_adet_dusuk_marj",
    etiket: "Fiyatı gözden geçir",
    aciklama: "Çok satan, marjı zayıf",
    renk: "var(--chart-5)",
    uyari: true,
  },
  { ad: "yuksek_adet_yuksek_marj", etiket: "Yıldız", aciklama: "Çok satan, marjı iyi", renk: "var(--chart-1)" },
  { ad: "dusuk_adet_yuksek_marj", etiket: "Büyütülebilir", aciklama: "Az satan, marjı iyi", renk: "var(--chart-2)" },
  { ad: "dusuk_adet_dusuk_marj", etiket: "Sorgula", aciklama: "Az satan, marjı zayıf", renk: "var(--chart-4)" },
];
const BOLGE = Object.fromEntries(BOLGELER.map((b) => [b.ad, b])) as Record<string, BolgeTanimi>;
const SIRA = Object.fromEntries(BOLGELER.map((b, i) => [b.ad, i])) as Record<string, number>;

const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const OLCU = { width: 720, height: 380 };
const sayi = (x: string | null) => (x === null ? null : Number(x));
const adetBicimle = (x: string | number) => paraBicimle(String(x), "", 0);

/** Görünen (bölge ve arama süzgecinden geçmiş) satırların toplamı; Decimal ile, boş değerler atlanır. */
function toplamSatiri(satirlar: KarlilikSatiri[]) {
  const adet = topla(satirlar.flatMap((r) => (r.adet === null ? [] : [r.adet])));
  const kar = topla(satirlar.flatMap((r) => (r.yillik_kar === null ? [] : [r.yillik_kar])));
  return {
    ad: `Toplam (${satirlar.length} ürün)`,
    adet: <ParaHucresi deger={adet.toString()} paraBirimi="" basamak={0} />,
    yillik_kar: <ParaHucresi deger={kar.toString()} basamak={0} className="font-semibold" />,
  };
}

interface Nokta {
  kod: string;
  ad: string;
  adet: number;
  marj: number;
  adetMetni: string;
  marjMetni: string;
}

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: Nokta }[] }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.ad}</div>
      <div className="text-xs text-muted-foreground">{n.kod}</div>
      <div className="tabular-nums">
        {adetBicimle(n.adetMetni)} adet · marj {yuzdeBicimle(n.marjMetni)}
      </div>
    </div>
  );
}

/**
 * Kârlılık haritası: ürünler yıllık adet ve marja göre dört bölgede (çizgiler: medyan adet, hedef marj). Bölge kartı tabloyu süzer;
 * en önemlisi "Fiyatı gözden geçir" (çok satan ama marjı zayıf). Yıllık adeti olmayan ürünler grafikte yok, tabloda sonda.
 */
export default function KarlilikHaritasi() {
  const { senaryoId } = useSenaryo();
  const gezin = useNavigate();
  const q = useKarlilik(senaryoId);
  const [secili, setSecili] = useState<KarlilikBolgesi | null>(null);
  const v = q.data;

  const noktalar = useMemo(() => {
    const g: Record<string, Nokta[]> = Object.fromEntries(BOLGELER.map((b) => [b.ad, []]));
    for (const k of v?.kayitlar ?? []) {
      if (!k.bolge || !g[k.bolge] || k.adet === null || k.marj === null) continue;
      g[k.bolge].push({
        kod: k.kod,
        ad: k.ad,
        adet: Number(k.adet),
        marj: D(k.marj).times(100).toNumber(),
        adetMetni: k.adet,
        marjMetni: k.marj,
      });
    }
    return g;
  }, [v]);

  // Bölgesi olanlar önce (önemli bölge üstte, içinde yıllık kâra göre), bölgesizler sonda.
  const kayitlar = useMemo(() => {
    const k = [...(v?.kayitlar ?? [])].filter((r) => secili === null || r.bolge === secili);
    return k.sort((a, b) => {
      const sa = a.bolge && a.bolge in SIRA ? SIRA[a.bolge] : 99;
      const sb = b.bolge && b.bolge in SIRA ? SIRA[b.bolge] : 99;
      if (sa !== sb) return sa - sb;
      return D(b.yillik_kar ?? "-1e30").comparedTo(D(a.yillik_kar ?? "-1e30"));
    });
  }, [v, secili]);

  const sutunlar = useMemo<SutunTanimi<KarlilikSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex flex-col">
            <span>{c.row.original.ad}</span>
            <span className="text-xs text-muted-foreground">
              {c.row.original.hata ? <span className="text-destructive">{c.row.original.hata}</span> : c.row.original.kod}
            </span>
          </span>
        ),
      },
      { accessorKey: "aile", header: "Aile", cell: (c) => c.row.original.aile ?? <span className="text-muted-foreground">—</span> },
      {
        id: "adet",
        accessorFn: (r) => sayi(r.adet),
        header: "Adet",
        cell: (c) => <ParaHucresi deger={c.row.original.adet} paraBirimi="" basamak={0} />,
      },
      {
        id: "maliyet",
        accessorFn: (r) => sayi(r.maliyet),
        header: "Maliyet",
        cell: (c) => <MaliyetHucresi deger={c.row.original.maliyet} kaynak={c.row.original.maliyet_kaynagi} />,
      },
      {
        id: "satis_fiyati",
        accessorFn: (r) => sayi(r.satis_fiyati),
        header: "Satış fiyatı",
        cell: (c) => (
          <span className="flex flex-col items-end">
            <ParaHucresi deger={c.row.original.satis_fiyati} />
            {c.row.original.fiyat_kaynagi && (
              <span className="text-[11px] text-muted-foreground">
                {c.row.original.fiyat_kaynagi === "satis_gecmisi" ? "geçen yıl" : "hesap"}
              </span>
            )}
          </span>
        ),
      },
      {
        id: "marj",
        accessorFn: (r) => sayi(r.marj),
        header: "Marj",
        cell: (c) => <YuzdeHucresi deger={c.row.original.marj} className="font-medium" />,
      },
      {
        id: "yillik_kar",
        accessorFn: (r) => sayi(r.yillik_kar),
        header: "Yıllık kâr",
        cell: (c) => <ParaHucresi deger={c.row.original.yillik_kar} basamak={0} className="font-semibold" />,
      },
      {
        id: "bolge",
        accessorFn: (r) => (r.bolge && r.bolge in SIRA ? SIRA[r.bolge] : 99),
        header: "Bölge",
        cell: (c) => {
          const b = c.row.original.bolge ? BOLGE[c.row.original.bolge] : undefined;
          if (!b) return <span className="text-muted-foreground">bölge yok</span>;
          return (
            <span className="flex items-center gap-1.5 whitespace-nowrap">
              <span className="size-2.5 rounded-full" style={{ background: b.renk }} aria-hidden />
              {b.etiket}
            </span>
          );
        },
      },
    ],
    [],
  );

  const ozet = v?.ozet;
  const grafikVar = BOLGELER.some((b) => noktalar[b.ad].length > 0);
  const esikAdet = v?.esik_adet ? Number(v.esik_adet) : null;
  const esikMarj = v ? D(v.esik_marj).times(100).toNumber() : null;
  const grafikOzeti = ozet ? BOLGELER.map((b) => `${b.etiket}: ${ozet[b.ad]} ürün`).join("; ") : "";

  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Kârlılık haritası"
        altBaslik="Ürünler yıllık adet ve marja göre dört bölgede. Çizgiler: medyan adet ve hedef marj."
        eylemler={
          senaryoId !== null && (
            <a href={karlilikXlsxAdresi(senaryoId, secili)} download className={cn(buttonVariants({ variant: "outline" }))}>
              <Download aria-hidden />
              Excel'e indir
            </a>
          )
        }
      />

      {ozet && (
        <div role="group" aria-label="Bölgeler" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {BOLGELER.map((b) => {
            const acik = secili === b.ad;
            return (
              <button
                key={b.ad}
                type="button"
                aria-pressed={acik}
                onClick={() => setSecili(acik ? null : b.ad)}
                className={cn(
                  "flex items-start gap-3 rounded-xl border bg-card p-4 text-left shadow-xs transition-colors hover:border-foreground/20 hover:bg-accent/40",
                  b.uyari && ozet[b.ad] > 0 && "border-transparent bg-kart-turuncu",
                  acik && "ring-2 ring-ring",
                )}
              >
                <span className="mt-1.5 size-3 shrink-0 rounded-full" style={{ background: b.renk }} aria-hidden />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="flex items-center gap-1.5 text-sm font-medium">
                    {b.etiket}
                    {b.uyari && ozet[b.ad] > 0 && <TriangleAlert className="size-3.5 text-amber-700 dark:text-amber-400" aria-hidden />}
                  </span>
                  <span className="text-2xl font-semibold tabular-nums">{ozet[b.ad]}</span>
                  <span className="text-xs text-muted-foreground">{b.aciklama}</span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {v && (ozet?.adetsiz || ozet?.hatali) ? (
        <p className="text-sm text-muted-foreground">
          {ozet.adetsiz > 0 && (
            <>
              {ozet.adetsiz} ürünün yıllık adeti yok; grafikte görünmez, tabloda "bölge yok" ile sonda listelenir (yıllık adet geçen yılın
              satış adedidir; Satış Geçmişi'ne satışı girilince haritaya eklenir).{" "}
            </>
          )}
          {ozet.hatali > 0 && <>{ozet.hatali} ürünün maliyeti hesaplanamadı.</>}
        </p>
      ) : null}

      {v && grafikVar && (
        <figure
          className="flex min-w-0 flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs"
          role="img"
          aria-label={`Kârlılık haritası. ${grafikOzeti}. Ayrıntı aşağıdaki tabloda.`}
        >
          <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="text-base font-semibold">Adet ve marj</span>
            <span className="text-xs text-muted-foreground">
              Dikey çizgi: medyan adet {v.esik_adet ? adetBicimle(v.esik_adet) : "—"} · Yatay çizgi: hedef marj{" "}
              {yuzdeBicimle(v.esik_marj, 0)}
            </span>
          </figcaption>
          <div style={{ height: OLCU.height }}>
            <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
              <ScatterChart margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="adet"
                  name="Adet"
                  tick={EKSEN}
                  tickFormatter={(x: number) => adetBicimle(x)}
                  label={{ value: "Yıllık adet", position: "insideBottom", offset: -4, ...EKSEN }}
                />
                <YAxis
                  type="number"
                  dataKey="marj"
                  name="Marj"
                  tick={EKSEN}
                  unit=" %"
                  width={56}
                  label={{ value: "Marj", angle: -90, position: "insideLeft", ...EKSEN }}
                />
                <Tooltip content={<Ipucu />} cursor={{ strokeDasharray: "3 3" }} />
                {esikAdet !== null && <ReferenceLine x={esikAdet} stroke="var(--muted-foreground)" strokeDasharray="4 4" />}
                {esikMarj !== null && <ReferenceLine y={esikMarj} stroke="var(--muted-foreground)" strokeDasharray="4 4" />}
                {BOLGELER.map((b) => (
                  <Scatter
                    key={b.ad}
                    name={b.etiket}
                    data={noktalar[b.ad]}
                    fill={b.renk}
                    fillOpacity={secili === null || secili === b.ad ? 0.85 : 0.15}
                    isAnimationActive={false}
                    onClick={(n: unknown) => {
                      const kod = (n as { payload?: Nokta } | undefined)?.payload?.kod;
                      if (kod) gezin(`/urunler/${encodeURIComponent(kod)}${senaryoId === null ? "" : `?senaryo=${senaryoId}`}`);
                    }}
                    className="cursor-pointer"
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-hidden>
            {BOLGELER.map((b) => (
              <li key={b.ad} className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-full" style={{ background: b.renk }} />
                {b.etiket}
              </li>
            ))}
          </ul>
        </figure>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Satış fiyatı geçen yılın satışından ("geçen yıl") ya da yoksa hesaplanan fiyattan ("hesap") alınır. Ürün ekranına gitmek için
          satıra tıklayın.
        </p>
        {secili && (
          <span className="flex flex-wrap items-center gap-2">
            <Link
              to={`/hedef-fiyat?bolge=${secili}${senaryoId === null ? "" : `&senaryo=${senaryoId}`}`}
              className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-2 hover:underline"
            >
              Bu ürünlerin hedef fiyatları
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
            <Button type="button" variant="outline" size="sm" onClick={() => setSecili(null)}>
              <X className="size-3.5" aria-hidden />
              Süzmeyi kaldır ({BOLGE[secili].etiket})
            </Button>
          </span>
        )}
      </div>
      <VeriTablosu
        veri={kayitlar}
        sutunlar={sutunlar}
        yukleniyor={q.isPending && senaryoId !== null}
        hata={q.error as ApiHatasi | null}
        bosMetin={secili ? `"${BOLGE[secili].etiket}" bölgesinde ürün yok` : "Ürün yok"}
        aramaAlani="ad"
        toplamSatiri={toplamSatiri}
        satirTikla={(r) => gezin(`/urunler/${encodeURIComponent(r.kod)}${senaryoId === null ? "" : `?senaryo=${senaryoId}`}`)}
      />
    </section>
  );
}
