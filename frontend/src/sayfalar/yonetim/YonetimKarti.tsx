import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/** Yönetim Özeti'ndeki her bölümün ortak çerçevesi: başlık, kısa açıklama, sağda bağlantı; kâğıtta bölünmez. */
export function YonetimKarti({
  baslik,
  aciklama,
  bagla,
  baglaMetni = "Ayrıntı",
  children,
  className,
}: {
  baslik: string;
  aciklama?: string;
  /** Sayfanın tam görünümüne bağlantı (ör. /hedef-fiyat?senaryo=1). */
  bagla?: string;
  baglaMetni?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section aria-label={baslik} className={cn("flex min-w-0 flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs", className)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{baslik}</h2>
          {aciklama && <p className="text-xs text-muted-foreground">{aciklama}</p>}
        </div>
        {bagla && (
          <Link to={bagla} className="inline-flex items-center gap-1 text-xs font-medium text-primary underline-offset-4 hover:underline">
            {baglaMetni}
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}

/** Üst şeritteki özet kutusu: başlık, büyük değer, altında açıklama satırı ve isteğe bağlı rozet. */
export function OzetKutusu({
  baslik,
  deger,
  alt,
  rozet,
  simge: Simge,
  ton = "sakin",
}: {
  baslik: string;
  deger: ReactNode;
  alt?: ReactNode;
  rozet?: ReactNode;
  simge: LucideIcon;
  ton?: "sakin" | "dikkat" | "hata";
}) {
  return (
    <div role="group" aria-label={baslik} className="flex items-start gap-3 rounded-xl border bg-card p-4 shadow-xs">
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-lg",
          ton === "hata"
            ? "bg-destructive/10 text-destructive"
            : ton === "dikkat"
              ? "bg-sari text-foreground"
              : "bg-muted text-muted-foreground",
        )}
        aria-hidden
      >
        <Simge className="size-[18px]" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="text-sm text-muted-foreground">{baslik}</span>
        <span className={cn("text-2xl font-semibold tabular-nums", ton === "hata" && "text-destructive")}>{deger}</span>
        {alt && <span className="text-xs text-muted-foreground tabular-nums">{alt}</span>}
        {rozet && <span className="mt-1">{rozet}</span>}
      </div>
    </div>
  );
}
