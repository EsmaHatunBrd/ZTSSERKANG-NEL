import { lazy, Suspense, useMemo, useState } from "react";
import { Search, TriangleAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useAileTrendi, useAileler } from "@/api/sorgular/karsilastirma";
import type { AileSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KIYAS_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { ambalajMetni } from "@/yardimcilar/ambalaj";
import { D, yuzdeBicimle } from "@/yardimcilar/para";

// recharts yalnızca grafik çizilirken indirilir.
const AileGrafigi = lazy(() => import("./karsilastirma/AileGrafigi").then((m) => ({ default: m.AileGrafigi })));

const tr = (s: string) => s.toLocaleLowerCase("tr");

function FarkHucresi({ deger }: { deger: string | null }) {
  if (deger === null) return <span className="block text-right text-muted-foreground">—</span>;
  const d = D(deger);
  return (
    <span className={cn("block text-right tabular-nums", d.isNegative() && !d.isZero() && "text-red-600 dark:text-red-400")}>
      {d.isPositive() && !d.isZero() ? "+" : ""}
      {yuzdeBicimle(d.div(100), 1)}
    </span>
  );
}

const sutunlar: SutunTanimi<AileSatiri>[] = [
  { accessorKey: "kod", header: "Kod" },
  { accessorKey: "ad", header: "Ürün" },
  {
    accessorKey: "ambalaj_ml",
    header: "Ambalaj",
    cell: ({ row }) => (
      <span className="block text-right tabular-nums">{ambalajMetni(row.original.ambalaj_etiket, row.original.ambalaj_hacmi)}</span>
    ),
  },
  {
    accessorKey: "suzme_kg",
    header: "Süzme kg",
    cell: ({ getValue }) => <ParaHucresi deger={getValue() as string | null} paraBirimi="" basamak={3} />,
  },
  {
    accessorKey: "satis_tl",
    header: "Satış TL",
    cell: ({ getValue }) => <ParaHucresi deger={getValue() as string | null} />,
  },
  {
    accessorKey: "satis_usd",
    header: "Satış USD",
    cell: ({ getValue }) => <ParaHucresi deger={getValue() as string | null} paraBirimi="USD" basamak={3} />,
  },
  {
    accessorKey: "kg_basi_satis_tl",
    header: "Kg başı satış TL",
    cell: ({ getValue }) => <ParaHucresi deger={getValue() as string | null} />,
  },
  {
    accessorKey: "suzme_kg_fiyati",
    header: "Süzme kg fiyatı",
    cell: ({ getValue }) => <ParaHucresi deger={getValue() as string | null} />,
  },
  {
    accessorKey: "onceki_ile_fark_yuzde",
    header: "Önceki ile fark",
    cell: ({ getValue }) => <FarkHucresi deger={getValue() as string | null} />,
  },
  {
    id: "durum",
    header: "Durum",
    enableSorting: false,
    cell: ({ row }) =>
      row.original.hata ? (
        <span className="inline-flex items-center gap-1 text-sm text-destructive">
          <TriangleAlert className="size-4 shrink-0" aria-hidden />
          <span>{row.original.hata}</span>
        </span>
      ) : null,
  },
];

export default function Karsilastirma() {
  const { senaryoId, senaryolar, yukleniyor: senaryoYukleniyor } = useSenaryo();
  const [params, setParams] = useSearchParams();
  const secili = params.get("aile");
  const [arama, setArama] = useState("");

  const aileler = useAileler(senaryoId);
  const trend = useAileTrendi(secili, senaryoId);

  const gorunen = useMemo(() => {
    const q = tr(arama.trim());
    const hepsi = aileler.data ?? [];
    return q
      ? hepsi.filter((a) => tr(a.aile_ad).includes(q) || a.urunler.some((u) => tr(u.ad).includes(q) || tr(u.kod).includes(q)))
      : hepsi;
  }, [aileler.data, arama]);

  function aileSec(aile: string) {
    // Geri/ileri çalışsın diye replace edilmez.
    setParams((onceki) => {
      const yeni = new URLSearchParams(onceki);
      yeni.set("aile", aile);
      return yeni;
    });
  }

  if (senaryoId === null) {
    return (
      <section className="p-4">
        <SayfaSekmeleri etiket="Kıyas türü" sekmeler={KIYAS_SEKMELERI} />
        <SayfaBasligi baslik="Karşılaştırma" />
        <p className="mt-2 text-muted-foreground">
          {!senaryoYukleniyor && senaryolar.length === 0 ? (
            <>
              Henüz senaryo yok —{" "}
              <Link to="/recete-aktar" className="text-primary underline-offset-4 hover:underline">
                Veri Aktar
              </Link>{" "}
              ile Excel&apos;i yükleyin.
            </>
          ) : (
            "Başlamak için yukarıdan bir senaryo seçin."
          )}
        </p>
      </section>
    );
  }

  const satirlar = trend.data?.satirlar ?? [];
  const grafikSatirSayisi = satirlar.filter((s) => !s.hata).length;

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaSekmeleri etiket="Kıyas türü" sekmeler={KIYAS_SEKMELERI} />
      <SayfaBasligi baslik="Karşılaştırma" altBaslik="Aynı ailedeki ürünlerin ambalaj hacmine göre satış fiyatları" />
      <p role="note" className="rounded-lg border border-marka/40 bg-accent/40 px-3 py-2 text-sm text-muted-foreground">
        Bu sayfa yüklü fiyat çalışmasını kullanır: aileler ürün adlarından otomatik kurulur, fiyatlar bu yılın hesabıdır. Geçen yıl kıyası
        ve enflasyon eşiği için{" "}
        <Link
          to={senaryoId === null ? "/satis-gecmisi" : `/satis-gecmisi?senaryo=${senaryoId}`}
          className="text-primary underline-offset-4 hover:underline"
        >
          Satış Geçmişi
        </Link>{" "}
        yükleyin.
      </p>
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <nav aria-label="Aile listesi" className="flex flex-col gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input
              type="search"
              aria-label="Aile ara"
              placeholder="Aile veya ürün ara"
              value={arama}
              onChange={(e) => setArama(e.target.value)}
              className="pl-8"
            />
          </div>
          {aileler.error ? (
            <div role="alert" className="text-sm text-destructive">
              {hataMetni(aileler.error as ApiHatasi)}
            </div>
          ) : aileler.isPending ? (
            <div role="status" aria-label="Yükleniyor" className="flex flex-col gap-2">
              {[0, 1, 2, 3, 4].map((i) => (
                <div key={i} aria-hidden className="h-9 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : gorunen.length === 0 ? (
            <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
              {arama ? "Aramaya uyan aile yok" : "Aile bulunamadı — ürün ekranından aile atayabilirsiniz."}
            </p>
          ) : (
            <ul className="flex max-h-[70vh] flex-col gap-1 overflow-y-auto">
              {gorunen.map((a) => (
                <li key={a.aile}>
                  <button
                    type="button"
                    aria-current={a.aile === secili ? "true" : undefined}
                    onClick={() => aileSec(a.aile)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
                      a.aile === secili ? "border-marka bg-accent font-medium text-accent-foreground" : "border-transparent",
                      a.tek_uyeli && a.aile !== secili && "opacity-60",
                    )}
                  >
                    <span className="min-w-0 truncate">{a.aile_ad}</span>
                    <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
                      {a.tek_uyeli ? "tek ürün" : `${a.urun_sayisi} ürün`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="flex min-w-0 flex-col gap-4">
          {!secili ? (
            <div className="rounded-xl border border-dashed p-10 text-center text-muted-foreground">Soldan bir aile seçin.</div>
          ) : (
            <>
              <h2 className="text-base font-semibold">
                {trend.data?.aile_ad ?? aileler.data?.find((a) => a.aile === secili)?.aile_ad ?? secili}
              </h2>
              {aileler.data?.find((a) => a.aile === secili)?.tek_uyeli && (
                <p role="note" data-testid="tek-uyeli-notu" className="text-sm text-muted-foreground">
                  Bu aile tek üyeli: karşılaştırılacak başka ambalaj yok. Aynı ürünün diğer ambalajlarını ürün ekranından bu aileye
                  atayabilirsiniz.
                </p>
              )}
              <div className="overflow-x-auto">
                <VeriTablosu
                  veri={satirlar}
                  sutunlar={sutunlar}
                  yukleniyor={trend.isPending}
                  hata={(trend.error as ApiHatasi | null) ?? null}
                  bosMetin="Bu ailede ürün yok"
                />
              </div>
              {grafikSatirSayisi > 0 && (
                <Suspense
                  fallback={
                    <div role="status" className="text-sm text-muted-foreground">
                      Grafik yükleniyor…
                    </div>
                  }
                >
                  <AileGrafigi satirlar={satirlar} aile={trend.data?.aile_ad ?? secili} />
                </Suspense>
              )}
              {trend.data && grafikSatirSayisi === 0 && satirlar.length > 0 && (
                <p className="text-sm text-muted-foreground">Hesap hatası nedeniyle grafik çizilemedi.</p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
