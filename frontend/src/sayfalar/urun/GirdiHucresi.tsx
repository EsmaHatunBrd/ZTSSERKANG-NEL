import { useState } from "react";
import { Input } from "@/bilesenler/ui/input";
import { cn } from "@/lib/utils";

interface Props {
  etiket: string;
  /** Odakta değilken gösterilen değer (taslak uygulanmış). */
  deger: string;
  /** Her tuş vuruşunda yerel metinle çağrılır. */
  onMetin: (metin: string) => void;
  disabled?: boolean;
  className?: string;
  title?: string;
  aciklama?: string;
  /** Odaktan çıkınca (yerel metin gösterilen değere dönerken) çağrılır. */
  onCik?: () => void;
  /** Taslakta değişmiş hücre: vurgulanır ve `eski` değeri ipucu olur. */
  degisti?: boolean;
  /** Değişmeden önceki (kayıtlı) değerin okunur metni. */
  eski?: string;
  /** İlk çizimde odaklan (metinden girdiye geçilen hücre). */
  otomatikOdak?: boolean;
}

/** Değişen hücrenin vurgusu (ortak sınıf: kenarlık + sarı zemin). */
export const DEGISTI_SINIFI = "border-marka bg-sari";

/**
 * Satır/alan içi sayı girdisi: yazarken yerel metni korur (boşaltıp yeniden yazmaya izin verir),
 * odaktan çıkınca gösterilen değere döner. Değişen hücre vurgulanır, ipucu eski değeri söyler.
 */
export function GirdiHucresi({ etiket, deger, onMetin, disabled, className, title, aciklama, onCik, degisti, eski, otomatikOdak }: Props) {
  const [metin, setMetin] = useState<string | null>(null);
  return (
    <Input
      aria-label={etiket}
      autoFocus={otomatikOdak}
      title={title ?? (degisti && eski !== undefined ? `Eski değer: ${eski}` : undefined)}
      aria-description={aciklama}
      data-degisti={degisti ? "true" : undefined}
      inputMode="decimal"
      disabled={disabled}
      value={metin ?? deger}
      onChange={(e) => {
        setMetin(e.target.value);
        onMetin(e.target.value);
      }}
      onBlur={() => {
        setMetin(null);
        onCik?.();
      }}
      className={cn(
        "h-7 w-20 border-transparent bg-muted/60 px-1.5 text-right tabular-nums shadow-none hover:border-input focus-visible:bg-card dark:bg-muted/40",
        degisti && DEGISTI_SINIFI,
        className,
      )}
    />
  );
}
