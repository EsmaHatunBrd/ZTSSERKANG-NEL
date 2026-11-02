import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  baslik: ReactNode;
  altBaslik?: ReactNode;
  /** Sağ taraftaki eylemler (düğmeler). */
  eylemler?: ReactNode;
  className?: string;
}

/** Tüm sayfaların ortak başlığı: başlık, alt başlık ve sağda eylemler (çizgisiz, sade). */
export function SayfaBasligi({ baslik, altBaslik, eylemler, className }: Props) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3 pb-1", className)}>
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{baslik}</h1>
        {altBaslik && <p className="mt-1 text-sm text-muted-foreground">{altBaslik}</p>}
      </div>
      {eylemler && <div className="flex flex-wrap items-center gap-2">{eylemler}</div>}
    </div>
  );
}
