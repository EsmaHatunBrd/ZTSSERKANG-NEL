import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";

/** Yüzde metni ("5.3" = %5,3) -> "+5,3 %"; eşik aşılıyorsa kalın. Renksiz: maliyette eksi iyi, satışta kötü; işaret yeterli. */
export function FarkYuzdesi({ deger, esik, className }: { deger: string | null; esik?: number; className?: string }) {
  if (deger === null) return <span className={cn("block text-right text-muted-foreground", className)}>—</span>;
  const d = D(deger);
  const asti = esik !== undefined && d.abs().greaterThan(esik);
  return (
    <span className={cn("block text-right tabular-nums", asti && "font-semibold", className)}>
      {d.isPositive() && !d.isZero() ? "+" : ""}
      {paraBicimle(d, "", 1)} %
    </span>
  );
}
