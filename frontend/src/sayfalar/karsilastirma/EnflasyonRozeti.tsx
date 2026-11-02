import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { D, yuzdeBicimle } from "@/yardimcilar/para";

/** "altinda" (kiremit, aşağı ok) ve "ustunde" (yeşil, yukarı ok): renk tek başına anlam taşımaz, simge ve metin de vardır. */
export function EnflasyonRozeti({ durum, farkYuzde }: { durum: string | null | undefined; farkYuzde?: string | null }) {
  if (durum !== "altinda" && durum !== "ustunde") {
    return <span className="block text-center text-muted-foreground">—</span>;
  }
  const altinda = durum === "altinda";
  const Simge = altinda ? ArrowDown : ArrowUp;
  return (
    <span
      data-durum={durum}
      className={cn(
        "inline-flex w-fit items-center gap-1 rounded-4xl border px-2 py-0.5 text-xs font-medium whitespace-nowrap tabular-nums text-foreground",
        altinda ? "border-chart-5/50 bg-chart-5/15" : "border-chart-1/50 bg-chart-1/15",
      )}
    >
      <Simge className={cn("size-3", altinda ? "text-chart-5" : "text-chart-1")} aria-hidden />
      {altinda ? "altında" : "üstünde"}
      {farkYuzde != null && (
        <span className="text-muted-foreground">
          {D(farkYuzde).isPositive() && !D(farkYuzde).isZero() ? "+" : ""}
          {yuzdeBicimle(D(farkYuzde).div(100), 1)}
        </span>
      )}
    </span>
  );
}
