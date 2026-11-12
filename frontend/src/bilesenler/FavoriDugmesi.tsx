import { Star } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  secili: boolean;
  onDegistir: () => void;
  className?: string;
}

/** Tablo satırı başındaki yıldız: favoriye ekler/çıkarır; tıklama satır gezinmesine ulaşmaz. */
export function FavoriDugmesi({ secili, onDegistir, className }: Props) {
  return (
    <button
      type="button"
      aria-pressed={secili}
      aria-label="Favorilere ekle/çıkar"
      title={secili ? "Favorilerden çıkar" : "Favorilere ekle"}
      onClick={(e) => {
        e.stopPropagation();
        onDegistir();
      }}
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
        secili && "text-amber-500 hover:text-amber-600 dark:text-amber-400",
        className,
      )}
    >
      <Star className={cn("size-4", secili && "fill-current")} aria-hidden />
    </button>
  );
}
