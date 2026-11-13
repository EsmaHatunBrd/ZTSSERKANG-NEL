import { lazy, Suspense, useState } from "react";
import { Info } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useSmmDonemleri, useSmmKarsilastirma } from "@/api/sorgular/smm";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { cn } from "@/lib/utils";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { DonemYok } from "./ortak";

const MaliyetDagilimiGrafigi = lazy(() => import("./MaliyetDagilimiGrafigi").then((m) => ({ default: m.MaliyetDagilimiGrafigi })));
const AylarArasiGrafigi = lazy(() => import("./AylarArasiGrafigi").then((m) => ({ default: m.AylarArasiGrafigi })));

const tl = (x: string) => paraBicimle(x, "TL", 0);
const isaretli = (metin: string, deger: string) => (D(deger).gt(0) ? `+${metin}` : metin);
/** Değişim rengi: maliyet artışı kırmızı, azalışı yeşil. */
const degisimSinifi = (x: string | null) =>
  x === null || D(x).isZero()
    ? "text-muted-foreground"
    : D(x).gt(0)
      ? "text-red-600 dark:text-red-400"
      : "text-green-700 dark:text-green-400";

/**
 * Aylar arası SMM: satırlar SMM tablosunun ana kalemleri, sütunlar dönemler (en eski solda); her hücrede tutar ve bir önceki
 * döneme göre değişim. Dönem seçilmezse son 6 dönem.
 */
export default function SmmAylarArasi() {
  const donemler = useSmmDonemleri();
  const liste = donemler.data?.kayitlar ?? [];
  const [secili, setSecili] = useState<number[]>([]);
  const q = useSmmKarsilastirma(secili);
  const v = q.data;

  if (donemler.data && liste.length === 0) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Aylar Arası" />
        <DonemYok />
      </section>
    );
  }

  const gosterilen = new Set(v?.donemler.map((d) => d.id) ?? []);
  const degistir = (id: number) => {
    // İlk tıklamada görünen (varsayılan) dönemlerden başlanır; hiç dönem kalmazsa varsayılana dönülür.
    const taban = secili.length ? secili : [...gosterilen];
    setSecili(taban.includes(id) ? taban.filter((x) => x !== id) : [...taban, id]);
  };

  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Aylar Arası"
        altBaslik="Satılan mamul maliyeti tablosunun ana kalemleri dönem dönem; her hücrede bir önceki döneme göre değişim."
      />

      {liste.length > 1 && (
        <div role="group" aria-label="Dönemler" className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Dönemler</span>
          {[...liste].reverse().map((d) => (
            <button
              key={d.id}
              type="button"
              aria-pressed={gosterilen.has(d.id)}
              onClick={() => degistir(d.id)}
              className={cn(
                "h-8 rounded-lg border px-3 text-sm",
                gosterilen.has(d.id) ? "border-marka bg-kart-yesil font-medium" : "text-muted-foreground hover:bg-accent",
              )}
            >
              {d.ad}
            </button>
          ))}
          {secili.length > 0 && (
            <button type="button" className="text-sm font-medium text-primary hover:underline" onClick={() => setSecili([])}>
              Son 6 dönem
            </button>
          )}
        </div>
      )}

      {q.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}
      {q.isPending && <p className="text-sm text-muted-foreground">Hesaplanıyor…</p>}

      {v && v.donemler.length === 1 && (
        <p role="note" className="flex items-start gap-2 rounded-xl bg-muted px-4 py-2 text-sm">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
          Karşılaştırma için ikinci dönem gerekir. Şimdilik yalnız {v.donemler[0].ad} gösteriliyor.
        </p>
      )}

      {v && v.donemler.length > 0 && (
        <section aria-label="Maliyet dağılımı" className="rounded-2xl border bg-card p-5 shadow-xs">
          <Suspense fallback={<p className="text-sm text-muted-foreground">Grafik yükleniyor…</p>}>
            <MaliyetDagilimiGrafigi veri={v} />
          </Suspense>
        </section>
      )}

      {v && v.donemler.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border bg-card shadow-xs">
          <table className="w-full text-sm">
            <caption className="sr-only">Dönemlere göre SMM tablosu</caption>
            <thead>
              <tr className="border-b text-xs text-muted-foreground uppercase">
                <th scope="col" className="px-5 py-2.5 text-left font-medium">
                  Kalem
                </th>
                {v.donemler.map((d) => (
                  <th key={d.id} scope="col" className="px-3 py-2.5 text-right font-medium whitespace-nowrap">
                    {d.ad}
                  </th>
                ))}
                {v.donemler.length > 1 && (
                  <th scope="col" className="px-5 py-2.5 text-right font-medium whitespace-nowrap">
                    Son iki ay farkı
                  </th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y">
              {v.satirlar.map((s) => (
                <tr key={s.anahtar} className={cn(s.vurgulu && "bg-kart-yesil font-semibold")}>
                  <th scope="row" className="min-w-[14rem] px-5 py-2 text-left font-[inherit]">
                    {s.ad}
                  </th>
                  {s.hucreler.map((h) => (
                    <td key={h.donem_id} className="px-3 py-2 text-right whitespace-nowrap tabular-nums">
                      <span className="block">{tl(h.tutar)}</span>
                      {h.degisim_tl !== null && (
                        <span className={cn("block text-xs font-normal", degisimSinifi(h.degisim_yuzde ?? h.degisim_tl))}>
                          {h.degisim_yuzde === null ? "—" : isaretli(yuzdeBicimle(h.degisim_yuzde), h.degisim_yuzde)}
                        </span>
                      )}
                    </td>
                  ))}
                  {v.donemler.length > 1 && (
                    <td className={cn("px-5 py-2 text-right whitespace-nowrap tabular-nums", degisimSinifi(s.son_fark_tl))}>
                      <span className="block">{s.son_fark_tl === null ? "—" : isaretli(tl(s.son_fark_tl), s.son_fark_tl)}</span>
                      {s.son_fark_yuzde !== null && (
                        <span className="block text-xs font-normal">{isaretli(yuzdeBicimle(s.son_fark_yuzde), s.son_fark_yuzde)}</span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {v && v.donemler.length > 1 && (
        <section aria-label="Grafik" className="rounded-2xl border bg-card p-5 shadow-xs">
          <Suspense fallback={<p className="text-sm text-muted-foreground">Grafik yükleniyor…</p>}>
            <AylarArasiGrafigi veri={v} />
          </Suspense>
        </section>
      )}
    </section>
  );
}
