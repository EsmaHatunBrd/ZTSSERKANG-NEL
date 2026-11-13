import { lazy, Suspense, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GitCompareArrows, Percent, TrendingUp, Unlink } from "lucide-react";
import { type ApiHatasi } from "@/api/istemci";
import { useSmmButceKiyas } from "@/api/sorgular/smm";
import type { SmmButceKiyasSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";

const ButceKiyasGrafigi = lazy(() => import("./ButceKiyasGrafigi").then((m) => ({ default: m.ButceKiyasGrafigi })));
import { DonemSecici, DonemYok, Miktar, SECIM_SINIFI, useSmmDonemSecimi } from "./ortak";

/** Fark rengi: fiili bütçeyi aşıyorsa kırmızı, altındaysa yeşil. */
const farkSinifi = (fark: string | null) =>
  fark === null || D(fark).isZero()
    ? "text-muted-foreground"
    : D(fark).gt(0)
      ? "font-medium text-red-600 dark:text-red-400"
      : "text-green-700 dark:text-green-400";
const isaretli = (metin: string, fark: string) => (D(fark).gt(0) ? `+${metin}` : metin);

/**
 * Bütçe kıyası: Fiyat Çalışması senaryosundaki bütçe üretim maliyeti ile dönemin fiili (SMM) birim maliyeti, ürün koduyla eşlenir.
 * Satıra tıklayınca ürünün birim maliyet kartı açılır.
 */
export default function SmmButceKiyas() {
  const secim = useSmmDonemSecimi();
  const { senaryoId, senaryolar, sec } = useSenaryo();
  const git = useNavigate();
  const [suz, setSuz] = useState(false);
  const [esik, setEsik] = useState("10");
  const q = useSmmButceKiyas(secim.donemId, senaryoId);
  const v = q.data;
  const esikOran = D(esik).dividedBy(100);
  const kayitlar = useMemo(
    () => (v?.kayitlar ?? []).filter((x) => !suz || (x.fark_yuzde !== null && D(x.fark_yuzde).abs().gt(esikOran))),
    [v, suz, esikOran],
  );

  const sutunlar = useMemo<SutunTanimi<SmmButceKiyasSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex max-w-[24rem] min-w-[14rem] flex-col whitespace-normal">
            <span>{c.row.original.ad ?? c.row.original.kod}</span>
            <span className="text-xs text-muted-foreground">{c.row.original.kod}</span>
          </span>
        ),
      },
      {
        id: "butce",
        accessorFn: (r) => (r.butce_maliyet_tl === null ? null : Number(r.butce_maliyet_tl)),
        header: "Bütçe",
        meta: { hiza: "sag" },
        cell: (c) =>
          c.row.original.butce_maliyet_tl === null ? (
            <span className="block text-right text-xs text-muted-foreground" title={c.row.original.butce_hatasi ?? undefined}>
              hesaplanamadı
            </span>
          ) : (
            <ParaHucresi deger={c.row.original.butce_maliyet_tl} />
          ),
      },
      {
        id: "fiili",
        accessorFn: (r) => Number(r.fiili_birim_maliyet_tl),
        header: "Fiili",
        meta: { hiza: "sag" },
        cell: (c) => (
          <span className="flex flex-col items-end">
            <ParaHucresi deger={c.row.original.fiili_birim_maliyet_tl} className="font-semibold" />
            {!c.row.original.uretildi && <span className="text-xs text-muted-foreground">üretim yok</span>}
          </span>
        ),
      },
      {
        id: "fark_tl",
        accessorFn: (r) => (r.fark_tl === null ? null : Number(r.fark_tl)),
        header: "Fark TL",
        meta: { hiza: "sag" },
        cell: (c) => {
          const f = c.row.original.fark_tl;
          return (
            <span className={cn("block text-right tabular-nums", farkSinifi(f))}>
              {f === null ? "—" : isaretli(paraBicimle(f, "TL", 2), f)}
            </span>
          );
        },
      },
      {
        id: "fark_yuzde",
        accessorFn: (r) => (r.fark_yuzde === null ? null : Number(r.fark_yuzde)),
        header: "Fark %",
        meta: { hiza: "sag" },
        cell: (c) => {
          const f = c.row.original.fark_yuzde;
          return (
            <span className={cn("block text-right tabular-nums", farkSinifi(f))}>{f === null ? "—" : isaretli(yuzdeBicimle(f), f)}</span>
          );
        },
      },
      {
        id: "uretim",
        accessorFn: (r) => Number(r.uretim_miktar),
        header: "Üretim miktarı",
        meta: { hiza: "sag" },
        cell: (c) => <Miktar deger={c.row.original.uretim_miktar} birim={c.row.original.birim} />,
      },
    ],
    [],
  );

  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Bütçe Kıyası" />
        <DonemYok />
      </section>
    );
  }

  const o = v?.ozet;
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Bütçe Kıyası"
        altBaslik="Fiyat çalışmasındaki bütçe üretim maliyeti ile dönemin fiili birim maliyeti; ürün koduyla eşlenir."
        eylemler={
          <span className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Fiyat çalışması</span>
              <select
                aria-label="Fiyat çalışması"
                className={cn(SECIM_SINIFI, "max-w-[16rem]")}
                value={senaryoId ?? ""}
                onChange={(e) => sec(Number(e.target.value))}
              >
                {senaryolar.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.ad}
                  </option>
                ))}
              </select>
            </label>
            <DonemSecici secim={secim} />
          </span>
        }
      />

      {senaryolar.length === 0 && senaryoId === null && !q.isFetching && (
        <p className="rounded-2xl border border-dashed bg-card p-5 text-sm text-muted-foreground">
          Karşılaştırılacak fiyat çalışması yok. Önce Fiyat Çalışması bölümünde bir çalışma oluşturun.
        </p>
      )}

      {o && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kart
            baslik="Eşleşen ürün"
            deger={`${o.eslesen}${o.uretimsiz > 0 ? ` · ${o.karsilastirilan} üretildi` : ""}`}
            simge={GitCompareArrows}
            renk="acik"
          />
          <Kart
            baslik="Ortalama fark (fiili − bütçe)"
            deger={o.ortalama_fark_yuzde === null ? "—" : isaretli(yuzdeBicimle(o.ortalama_fark_yuzde), o.ortalama_fark_yuzde)}
            simge={Percent}
            renk="acik"
          />
          <Kart baslik="Fiili bütçeyi aşan ürün" deger={String(o.fiili_yuksek)} simge={TrendingUp} renk="acik" />
          <Kart baslik="Eşleşmeyen" deger={`${o.yalniz_butce} bütçede · ${o.yalniz_fiili} fiilide`} simge={Unlink} renk="acik" />
        </div>
      )}

      {v && (
        <p className="text-sm text-muted-foreground">
          Bütçe: malzeme + işçilik + genel üretim gideri (pazarlama, yönetim ve finansman hariç); yıllık çalışmanın enflasyon dahil
          fiyatlarıyla. Fiili: ürünün {v.donem.ad} dönemindeki son aşama birim maliyeti. Fark yalnız bu dönem üretilen ürünlerde hesaplanır.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={suz} onChange={(e) => setSuz(e.target.checked)} />
          Yalnız farkı %
          <Input
            aria-label="Fark eşiği (yüzde)"
            inputMode="decimal"
            className="h-8 w-16 text-right"
            value={esik}
            onChange={(e) => setEsik(e.target.value)}
          />
          üstü
        </label>
        <span className="ml-auto text-sm text-muted-foreground">{v ? `${kayitlar.length} / ${v.kayitlar.length} ürün` : ""}</span>
      </div>

      {v && v.kayitlar.length > 0 && (
        <section aria-label="Bütçe ve fiili grafiği" className="rounded-2xl border bg-card p-5 shadow-xs">
          <Suspense fallback={<p className="text-sm text-muted-foreground">Grafik yükleniyor…</p>}>
            <ButceKiyasGrafigi kayitlar={kayitlar} />
          </Suspense>
        </section>
      )}

      <VeriTablosu
        veri={kayitlar}
        sutunlar={sutunlar}
        yukleniyor={q.isPending && secim.donemId !== null && senaryoId !== null}
        hata={q.error as ApiHatasi | null}
        bosMetin={suz ? "Bu eşiğin üstünde fark yok" : "Kodu eşleşen ürün yok"}
        bosAciklama={suz ? undefined : "Bütçedeki ürün kodları ile dönemin SMM ürün kodları örtüşmüyor; aşağıdaki listelere bakın."}
        satirTikla={(u: SmmButceKiyasSatiri) => git(`/smm/urun/${encodeURIComponent(u.kod)}?donem=${secim.donemId}`)}
      />

      {v && (v.yalniz_butce.length > 0 || v.yalniz_fiili.length > 0) && (
        <details className="group rounded-2xl border bg-card shadow-xs">
          <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-1 px-5 py-4">
            <span className="text-base font-semibold">Eşleşmeyenler</span>
            <span className="text-sm text-muted-foreground">
              {v.yalniz_butce.length} ürün yalnız bütçede · {v.yalniz_fiili.length} üretilen ürün yalnız fiilide
            </span>
            <span className="ml-auto text-sm font-medium text-primary group-open:hidden">Göster</span>
          </summary>
          <div className="grid gap-5 border-t px-5 py-4 lg:grid-cols-2">
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold">Yalnız bütçede (dönemde aşama reçetesi yok)</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">Yalnız bütçede olan ürünler</caption>
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground uppercase">
                      <th className="py-1.5 font-medium">Ürün</th>
                      <th className="py-1.5 text-right font-medium">Bütçe</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {v.yalniz_butce.map((x) => (
                      <tr key={x.kod}>
                        <td className="py-1.5">
                          <span className="block">{x.ad ?? x.kod}</span>
                          <span className="block text-xs text-muted-foreground">
                            {x.kod}
                            {x.stok_kartinda && " · stok kartı var"}
                          </span>
                        </td>
                        <td className="py-1.5 text-right tabular-nums">
                          {x.butce_maliyet_tl === null ? "—" : paraBicimle(x.butce_maliyet_tl, "TL", 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold">Yalnız fiilide (bu dönem üretildi, bütçede yok)</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <caption className="sr-only">Yalnız fiilide olan ürünler</caption>
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground uppercase">
                      <th className="py-1.5 font-medium">Ürün</th>
                      <th className="py-1.5 text-right font-medium">Üretim</th>
                      <th className="py-1.5 text-right font-medium">Fiili</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {v.yalniz_fiili.map((x) => (
                      <tr key={x.kod}>
                        <td className="py-1.5">
                          <span className="block">{x.ad ?? x.kod}</span>
                          <span className="block text-xs text-muted-foreground">{x.kod}</span>
                        </td>
                        <td className="py-1.5">
                          <Miktar deger={x.uretim_miktar} />
                        </td>
                        <td className="py-1.5 text-right tabular-nums">{paraBicimle(x.fiili_birim_maliyet_tl, "TL", 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </details>
      )}
    </section>
  );
}
