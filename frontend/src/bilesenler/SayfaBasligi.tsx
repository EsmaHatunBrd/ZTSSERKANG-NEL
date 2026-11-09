import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  baslik: ReactNode;
  altBaslik?: ReactNode;
  /** Sağ taraftaki eylemler (düğmeler). */
  eylemler?: ReactNode;
  /** Sayfanın ana başlığı renk geçişli bant içinde (özet sayfaları için); verilmezse sade başlık + ince ayraç. */
  bant?: boolean;
  className?: string;
}

/** Tüm sayfaların ortak başlığı: başlık, alt başlık ve sağda eylemler. */
export function SayfaBasligi({ baslik, altBaslik, eylemler, bant = false, className }: Props) {
  if (bant) {
    return (
      <div
        className={cn(
          "flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-6 py-5 shadow-xs",
          className,
        )}
      >
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">{baslik}</h1>
          {altBaslik && <p className="mt-1 text-sm text-muted-foreground">{altBaslik}</p>}
        </div>
        {eylemler && <div className="flex flex-wrap items-center gap-2">{eylemler}</div>}
      </div>
    );
  }
  return (
    <div className={cn("flex flex-col gap-3 pb-1", className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{baslik}</h1>
          {altBaslik && <p className="mt-1 text-sm text-muted-foreground">{altBaslik}</p>}
        </div>
        {eylemler && <div className="flex flex-wrap items-center gap-2">{eylemler}</div>}
      </div>
      {/* Düz ince ayraç. */}
      <div aria-hidden className="h-px w-full bg-border" />
    </div>
  );
}
