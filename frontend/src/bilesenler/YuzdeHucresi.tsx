import { cn } from "@/lib/utils";
import { D, yuzdeBicimle } from "@/yardimcilar/para";

interface Props {
  /** Oran metni ("0.19736" -> "19,7 %"). */
  deger: string | null;
  basamak?: number;
  className?: string;
}

export function YuzdeHucresi({ deger, basamak = 1, className }: Props) {
  if (deger === null || deger === undefined) {
    return <span className={cn("block text-right text-muted-foreground", className)}>—</span>;
  }
  const negatif = D(deger).isNegative() && !D(deger).isZero();
  return (
    <span className={cn("block text-right tabular-nums", negatif && "text-red-600 dark:text-red-400", className)}>
      {yuzdeBicimle(deger, basamak)}
    </span>
  );
}
