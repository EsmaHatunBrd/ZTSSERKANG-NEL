import { useId, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

/** Veri Girişi kartlarının ortak seçim kutusu sınıfı. */
export const SELECT =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50";

/** Veri Girişi sayfasındaki kart: başlık + simge + kısa açıklama; `region` olarak adlandırılır. */
export function Kart({
  baslik,
  aciklama,
  simge,
  children,
  className,
  tumu,
}: {
  baslik: string;
  aciklama: string;
  simge: ReactNode;
  children: ReactNode;
  className?: string;
  /** Aynı verinin tam listesi (ör. Malzeme Fiyatları sayfası): başlığın sağında bağlantı; seçili senaryo korunur. */
  tumu?: { yol: string; etiket: string };
}) {
  const id = useId();
  const { search } = useLocation();
  return (
    <section aria-labelledby={id} className={`flex flex-col gap-3 rounded-lg border bg-card p-4 ${className ?? ""}`}>
      <header>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id={id} className="flex items-center gap-2 text-base font-semibold">
            <span className="text-marka [&>svg]:size-4" aria-hidden>
              {simge}
            </span>
            {baslik}
          </h2>
          {tumu && (
            <Link to={`${tumu.yol}${search}`} className="text-xs font-medium text-primary underline-offset-4 hover:underline">
              Tüm liste: {tumu.etiket} →
            </Link>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground">{aciklama}</p>
      </header>
      {children}
    </section>
  );
}

export function Alan({ etiket, htmlFor, hata, children }: { etiket: string; htmlFor: string; hata?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {etiket}
      </label>
      {children}
      {hata && (
        <p role="alert" className="text-xs text-destructive">
          {hata}
        </p>
      )}
    </div>
  );
}
