import { useState } from "react";
import { ArrowRight, ChevronDown, CircleAlert, CircleCheck, TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useTutarlilik } from "@/api/sorgular/tutarlilik";
import type { TutarlilikKontrolu } from "@/api/tipler";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";

const DURUM = {
  hata: { etiket: "Hata", simge: CircleAlert, sinif: "bg-destructive/10 text-destructive" },
  dikkat: { etiket: "Dikkat", simge: TriangleAlert, sinif: "bg-sari text-foreground" },
  tamam: { etiket: "Tamam", simge: CircleCheck, sinif: "bg-muted text-muted-foreground" },
} as const;
const SIRA = { hata: 0, dikkat: 1, tamam: 2 } as const;

/** Arayüz yoluna seçili senaryoyu ekler (`/fiyatlar?fiyatsiz=1` -> `/fiyatlar?fiyatsiz=1&senaryo=5`). */
export function senaryoluYol(yol: string, senaryoId: number | null): string {
  if (senaryoId === null) return yol;
  return `${yol}${yol.includes("?") ? "&" : "?"}senaryo=${senaryoId}`;
}

function Kontrol({ k, senaryoId }: { k: TutarlilikKontrolu; senaryoId: number | null }) {
  const [acik, setAcik] = useState(k.durum === "hata");
  const d = DURUM[k.durum];
  const Simge = d.simge;
  const listeId = `kontrol-${k.kod}`;
  return (
    <section aria-labelledby={`${listeId}-baslik`} className="rounded-xl border bg-card shadow-xs">
      <div className="flex flex-wrap items-start gap-3 p-4">
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", d.sinif)} aria-hidden>
          <Simge className="size-[18px]" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <h2 id={`${listeId}-baslik`} className="font-medium">
              {k.baslik}
            </h2>
            <span className="text-sm text-muted-foreground">
              {d.etiket}
              {k.sayi > 0 && ` · ${k.sayi} kayıt`}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{k.aciklama}</p>
        </div>
        {k.sayi > 0 && (
          <div className="flex shrink-0 items-center gap-2 self-center">
            <Link
              to={senaryoluYol(k.cozum.yol, senaryoId)}
              className="inline-flex items-center gap-1 text-sm font-medium underline-offset-4 hover:underline"
            >
              {k.cozum.etiket}
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
            <Button type="button" variant="ghost" size="sm" aria-expanded={acik} aria-controls={listeId} onClick={() => setAcik((a) => !a)}>
              {acik ? "Gizle" : "Kayıtlar"}
              <ChevronDown className={cn("transition-transform", acik && "rotate-180")} aria-hidden />
            </Button>
          </div>
        )}
      </div>
      {acik && k.ogeler.length > 0 && (
        <ul id={listeId} className="flex max-h-80 flex-col overflow-y-auto border-t px-4 py-2 text-sm">
          {k.ogeler.map((o, i) => (
            <li key={`${o.etiket}-${i}`} className="flex flex-wrap items-baseline gap-x-2 border-b py-1.5 last:border-0">
              <Link to={senaryoluYol(o.yol, senaryoId)} className="font-medium underline-offset-4 hover:underline">
                {o.etiket}
              </Link>
              <span className="text-muted-foreground">{o.aciklama}</span>
            </li>
          ))}
          {k.sayi > k.ogeler.length && <li className="py-1.5 text-muted-foreground">… ve {k.sayi - k.ogeler.length} kayıt daha</li>}
        </ul>
      )}
    </section>
  );
}

export default function VeriKontrolu() {
  const { senaryoId } = useSenaryo();
  const q = useTutarlilik(senaryoId);
  const kontroller = [...(q.data?.kontroller ?? [])].sort((a, b) => SIRA[a.durum] - SIRA[b.durum]);
  const o = q.data?.ozet;

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaBasligi baslik="Veri Kontrolü" altBaslik="Çalışmadaki veri sorunları tek yerde; her birinin yanında nereden düzeltileceği." />
      {q.error ? (
        <div role="alert" className="rounded-md border border-destructive/40 p-3 text-sm text-destructive">
          {hataMetni(q.error as ApiHatasi)}
        </div>
      ) : !q.data ? (
        <div role="status" aria-label="Yükleniyor" className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} aria-hidden className="h-20 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : (
        <>
          <p role="status" className="text-sm">
            {o && o.hata + o.dikkat === 0 ? (
              <span className="font-medium">Tüm kontroller tamam.</span>
            ) : (
              <>
                <span className="font-medium">{o!.hata + o!.dikkat} konu</span> ilgi bekliyor
                {o!.hata > 0 && <> ({o!.hata} tanesi hesabı engelliyor)</>}; {o!.tamam} kontrol tamam. Satırlardaki ürün ve malzeme adlarına
                tıklayarak doğrudan ilgili kayda gidebilirsiniz.
              </>
            )}
          </p>
          <div className="flex flex-col gap-3">
            {kontroller.map((k) => (
              <Kontrol key={k.kod} k={k} senaryoId={senaryoId} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
