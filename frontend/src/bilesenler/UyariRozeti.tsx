import { Badge } from "@/bilesenler/ui/badge";

/** Uyarı sayısı rozeti; sayı 0/boşsa hiçbir şey çizmez. */
export function UyariRozeti({ sayi }: { sayi: number | null | undefined }) {
  if (!sayi) return null;
  return (
    <Badge variant="destructive" aria-label={`${sayi} uyarı`} title={`${sayi} uyarı`}>
      {sayi}
    </Badge>
  );
}
