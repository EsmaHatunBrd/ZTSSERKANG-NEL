import { useId } from "react";
import { Girdi } from "@/bilesenler/Girdi";
import { NEDEN_IPUCU, nedenGecerli } from "@/yardimcilar/neden";

interface Props {
  deger: string;
  onDegis: (deger: string) => void;
  /** Kutunun erişilebilir adı/etiketi; aynı ekranda birden çok neden kutusu varsa ayırt etmek için. */
  etiket?: string;
  autoFocus?: boolean;
  disabled?: boolean;
}

/**
 * Denetim izine (Değişiklik Günlüğü) yazılan zorunlu "Neden" kutusu. Boşken altında "Neden girin" ipucu görünür; onay düğmesini
 * pasifleştirmek çağıranın işidir (`nedenGecerli`).
 */
export function NedenAlani({ deger, onDegis, etiket = "Neden (zorunlu)", autoFocus, disabled }: Props) {
  const kimlik = useId();
  const bos = !nedenGecerli(deger);
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={`${kimlik}-neden`} className="font-medium">
        {etiket}
      </label>
      <Girdi
        id={`${kimlik}-neden`}
        value={deger}
        autoFocus={autoFocus}
        disabled={disabled}
        autoComplete="off"
        maxLength={500}
        aria-required
        aria-describedby={bos ? `${kimlik}-ipucu` : undefined}
        onChange={(e) => onDegis(e.target.value)}
      />
      {bos && (
        <p id={`${kimlik}-ipucu`} className="text-xs text-muted-foreground">
          {NEDEN_IPUCU}
        </p>
      )}
    </div>
  );
}
