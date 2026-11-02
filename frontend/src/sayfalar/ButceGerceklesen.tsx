import { lazy, Suspense, useMemo, useState } from "react";
import { Download, Equal, Scale, Search, Sigma, TriangleAlert } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import type { ApiHatasi } from "@/api/istemci";
import { useKarsiSenaryo, useKiyasListesi } from "@/api/sorgular/kiyas";
import type { BgDeger, BgSatir, Senaryo } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { buttonVariants } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { senaryoEtiketi } from "@/yardimcilar/senaryo";
import { Kart } from "./dashboard/UstKartlar";
import { FarkYuzdesi } from "./kiyas/FarkYuzdesi";
import { varsayilanCift } from "./kiyasCifti";

// recharts yalnız grafik çizilirken indirilir.
const SapmaGrafigi = lazy(() => import("./kiyas/SapmaGrafigi").then((m) => ({ default: m.SapmaGrafigi })));

const SECIM =
  "h-9 rounded-lg border border-input bg-card px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";
const tr = (s: string) => s.toLocaleLowerCase("tr");
const ESIK_DESENI = /^\d+(\.\d+)?$/;

/** A | B hücresi: üstte B (gerçekleşen), altta küçük A (bütçe). */
function AbHucresi({ v, paraBirimi = "TL", basamak = 2 }: { v: BgDeger | undefined; paraBirimi?: string; basamak?: number }) {
  if (!v) return <span className="block text-right text-muted-foreground">—</span>;
  return (
    <span className="flex flex-col items-end leading-tight">
      <ParaHucresi deger={v.b} paraBirimi={paraBirimi} basamak={basamak} />
      <span className="text-xs text-muted-foreground tabular-nums">
        bütçe <ParaHucresi deger={v.a} paraBirimi="" basamak={basamak} className="inline" />
      </span>
    </span>
  );
}

const DURUM_METNI: Record<string, string> = { yalniz_a: "Yalnız bütçede", yalniz_b: "Yalnız gerçekleşende" };

function sutunlar(esik: number): SutunTanimi<BgSatir>[] {
  const ab = (alan: keyof NonNullable<BgSatir["alanlar"]>, baslik: string, paraBirimi = "TL", basamak = 2): SutunTanimi<BgSatir> => ({
    id: alan,
    header: baslik,
    accessorFn: (s) => s.alanlar?.[alan].b ?? null,
    cell: ({ row }) => <AbHucresi v={row.original.alanlar?.[alan]} paraBirimi={paraBirimi} basamak={basamak} />,
  });
  return [
    {
      accessorKey: "kod",
      header: "Kod",
      cell: ({ getValue }) => <span className="text-xs whitespace-nowrap">{getValue() as string}</span>,
    },
    { accessorKey: "ad", header: "Ürün", cell: ({ getValue }) => <span className="block min-w-40">{getValue() as string}</span> },
    ab("maliyet_tl", "Maliyet TL"),
    {
      id: "fark",
      header: "Maliyet farkı",
      accessorFn: (s) => s.alanlar?.maliyet_tl.fark ?? null,
      cell: ({ row }) => <ParaHucresi deger={row.original.alanlar?.maliyet_tl.fark ?? null} />,
    },
    {
      accessorKey: "sapma_yuzde",
      header: "Sapma %",
      cell: ({ row }) =>
        row.original.durum === "iki" ? (
          <FarkYuzdesi deger={row.original.sapma_yuzde} esik={esik} />
        ) : (
          <span className={cn("block text-right text-sm", row.original.hata ? "text-destructive" : "text-muted-foreground")}>
            {row.original.hata ? (
              <span className="inline-flex items-center gap-1">
                <TriangleAlert className="size-4 shrink-0" aria-hidden />
                {row.original.hata}
              </span>
            ) : (
              DURUM_METNI[row.original.durum]
            )}
          </span>
        ),
    },
    ab("recete_maliyeti", "Reçete"),
    ab("gug", "GÜG"),
    ab("faaliyet", "Faaliyet"),
    ab("finans", "Finans"),
    ab("maliyet_usd", "Maliyet USD", "USD", 3),
    ab("satis_tl", "Satış TL"),
  ];
}

export default function ButceGerceklesen() {
  const { senaryoId, senaryo, senaryolar, yukleniyor } = useSenaryo();
  const [params, setParams] = useSearchParams();
  const gezin = useNavigate();
  const karsi = useKarsiSenaryo(senaryoId);
  const vars = varsayilanCift(senaryo, karsi.data?.karsi?.id ?? null);
  const sayi = (k: string) => (params.get(k) && /^\d+$/.test(params.get(k) as string) ? Number(params.get(k)) : null);
  const a = sayi("a") ?? vars.a;
  const b = sayi("b") ?? vars.b;
  const esikMetni = ESIK_DESENI.test(params.get("esik") ?? "") ? (params.get("esik") as string) : "5";
  const esik = Number(esikMetni);
  const yalnizSapan = params.get("sapan") === "1";
  const [arama, setArama] = useState("");
  // Eşik kutusu yazılırken boş/yarım kalabilir; yalnız geçerli sayı URL'ye (ve isteğe) yazılır.
  const [esikGirdi, setEsikGirdi] = useState(esikMetni);
  const liste = useKiyasListesi(a, b, esikMetni);

  function ayarla(degisim: Record<string, string | null>) {
    setParams(
      (onceki) => {
        const yeni = new URLSearchParams(onceki);
        for (const [k, v] of Object.entries(degisim)) {
          if (v === null || v === "") yeni.delete(k);
          else yeni.set(k, v);
        }
        return yeni;
      },
      { replace: true },
    );
  }

  const gorunen = useMemo(() => {
    const q = tr(arama.trim());
    return (liste.data?.satirlar ?? []).filter((s) => (!yalnizSapan || s.sapan) && (!q || tr(s.ad).includes(q) || tr(s.kod).includes(q)));
  }, [liste.data, arama, yalnizSapan]);
  const sutun = useMemo(() => sutunlar(esik), [esik]);

  const gerceklesenVar = senaryolar.some((s) => s.tur === "gerceklesen");
  const ozet = liste.data?.ozet;
  const secenek = (s: Senaryo) => (
    <option key={s.id} value={s.id}>
      {senaryoEtiketi(s)}
    </option>
  );
  const sorgu = senaryoId === null ? "" : `?senaryo=${senaryoId}`;

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaBasligi baslik="Bütçe vs Gerçekleşen" altBaslik="Fiyat çalışması ile gerçekleşenin ürün bazında farkı ve sapmanın kaynağı" />

      {yukleniyor ? (
        <div role="status" className="text-sm text-muted-foreground">
          Yükleniyor…
        </div>
      ) : !gerceklesenVar ? (
        <div className="rounded-xl border border-dashed p-8 text-center">
          <p className="font-medium">Henüz gerçekleşen çalışması yok.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Gerçekleşen Excel&apos;ini{" "}
            <Link to={`/recete-aktar${sorgu}`} className="text-primary underline-offset-4 hover:underline">
              Veri Aktar
            </Link>{" "}
            → Tüm çalışma kitabı → tür <strong>Gerçekleşen</strong> ile aynı sezona yükleyin; kıyas burada görünür.
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-muted-foreground">A — Bütçe (fiyat çalışması)</span>
                <select aria-label="Bütçe senaryosu" value={a ?? ""} onChange={(e) => ayarla({ a: e.target.value })} className={SECIM}>
                  <option value="">Seçin</option>
                  {senaryolar.filter((s) => s.tur === "fiyat_calismasi").map(secenek)}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-muted-foreground">B — Gerçekleşen</span>
                <select
                  aria-label="Gerçekleşen senaryosu"
                  value={b ?? ""}
                  onChange={(e) => ayarla({ b: e.target.value })}
                  className={SECIM}
                >
                  <option value="">Seçin</option>
                  {senaryolar.filter((s) => s.tur === "gerceklesen").map(secenek)}
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-56 flex-1">
                <Search
                  className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
                  aria-hidden
                />
                <Input
                  type="search"
                  aria-label="Ürün ara"
                  placeholder="Ürün adı ya da kodu ara"
                  value={arama}
                  onChange={(e) => setArama(e.target.value)}
                  className="pl-8"
                />
              </div>
              <label className="flex h-9 items-center gap-2 text-sm">
                Sapma eşiği ±%
                <Input
                  type="number"
                  min={0}
                  step={0.5}
                  aria-label="Sapma eşiği (yüzde)"
                  value={esikGirdi}
                  onChange={(e) => {
                    setEsikGirdi(e.target.value);
                    if (ESIK_DESENI.test(e.target.value)) ayarla({ esik: e.target.value === "5" ? null : e.target.value });
                  }}
                  className="h-9 w-20"
                />
              </label>
              <label className="flex h-9 items-center gap-2 rounded-lg px-1 text-sm">
                <input
                  type="checkbox"
                  checked={yalnizSapan}
                  onChange={(e) => ayarla({ sapan: e.target.checked ? "1" : null })}
                  className="size-4 accent-primary"
                />
                Yalnız sapanlar
              </label>
              {a !== null && b !== null && a !== b && (
                <a
                  href={`/api/v1/disa-aktar/butce-gerceklesen.xlsx?a=${a}&b=${b}&esik=${esikMetni}${yalnizSapan ? "&yalniz_sapan=true" : ""}`}
                  download
                  className={cn(buttonVariants({ variant: "outline" }), "h-9")}
                >
                  <Download aria-hidden />
                  Excel&apos;e aktar
                </a>
              )}
            </div>
          </div>

          {a === null || b === null ? (
            <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
              Kıyas için bir bütçe ve bir gerçekleşen senaryosu seçin.
            </p>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Kart baslik="Karşılaştırılan ürün" deger={ozet ? ozet.karsilastirilan : "—"} simge={Scale} />
                <Kart
                  baslik={`±%${esikMetni.replace(".", ",")} dışında`}
                  deger={ozet ? ozet.sapan : "—"}
                  simge={TriangleAlert}
                  ton={ozet?.sapan ? "dikkat" : "sakin"}
                  onTikla={() => ayarla({ sapan: "1" })}
                  eylem="Göster"
                />
                <Kart
                  baslik="Ortalama maliyet sapması"
                  deger={ozet?.ortalama_sapma_yuzde ? <FarkYuzdesi deger={ozet.ortalama_sapma_yuzde} /> : "—"}
                  simge={Sigma}
                />
                <Kart
                  baslik="Yalnız bir tarafta / hatalı"
                  deger={ozet ? `${ozet.yalniz_a + ozet.yalniz_b} / ${ozet.hatali}` : "—"}
                  simge={Equal}
                  ton={ozet && ozet.yalniz_a + ozet.yalniz_b + ozet.hatali > 0 ? "dikkat" : "sakin"}
                />
              </div>

              {liste.data && ozet && ozet.karsilastirilan > 0 && (
                <div className="rounded-xl border bg-card p-3 shadow-xs sm:p-4">
                  <Suspense
                    fallback={
                      <div role="status" className="text-sm text-muted-foreground">
                        Grafik yükleniyor…
                      </div>
                    }
                  >
                    <SapmaGrafigi satirlar={liste.data.satirlar} />
                  </Suspense>
                </div>
              )}

              <p className="text-sm text-muted-foreground">
                Hücrelerde üstte gerçekleşen, altta bütçe. Sapma = (gerçekleşen − bütçe) / bütçe, finansman dahil birim maliyet TL
                üzerinden. Ayrıntı ve sapmanın kaynağı için satıra tıklayın.
              </p>
              <div className="overflow-x-auto">
                <VeriTablosu
                  veri={gorunen}
                  sutunlar={sutun}
                  yukleniyor={liste.isPending}
                  hata={(liste.error as ApiHatasi | null) ?? null}
                  bosMetin={yalnizSapan ? "Eşiği aşan ürün yok" : "Karşılaştırılacak ürün yok"}
                  satirTikla={(s) =>
                    s.durum === "iki" &&
                    gezin(`/butce-gerceklesen/${encodeURIComponent(s.kod)}?a=${a}&b=${b}${senaryoId ? `&senaryo=${senaryoId}` : ""}`)
                  }
                  className="text-[13px]"
                />
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}
