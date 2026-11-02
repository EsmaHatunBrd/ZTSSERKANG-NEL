import { cn } from "@/lib/utils";
import { D, paraBicimle, type ParaBirimi } from "@/yardimcilar/para";

interface Props {
  /** API'den gelen tutar metni ("38.130789"); asla Number'a çevrilmez. */
  deger: string | null;
  paraBirimi?: ParaBirimi;
  basamak?: number;
  className?: string;
}

export function ParaHucresi({ deger, paraBirimi = "TL", basamak = 2, className }: Props) {
  if (deger === null || deger === undefined) {
    return <span className={cn("block text-right text-muted-foreground", className)}>—</span>;
  }
  const negatif = D(deger).isNegative() && !D(deger).isZero();
  return (
    <span className={cn("block text-right tabular-nums", negatif && "text-red-600 dark:text-red-400", className)}>
      {paraBicimle(deger, paraBirimi, basamak)}
    </span>
  );
}
