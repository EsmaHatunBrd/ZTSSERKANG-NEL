import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface Props {
  /** "Bu sayı nereden geldi" metni: fareye `title`, klavye odağına küçük popover olarak gider. */
  metin: string;
  className?: string;
  children: ReactNode;
}

/**
 * Hücre içeriğini odaklanabilir bir sarmalayıcıya alır. Fare üstüne gelince ve klavye odağında aynı balon hemen açılır
 * (tarayıcının gecikmeli gri `title` ipucu fark edilmiyordu); balon açıkken `title` kaldırılır ki iki ipucu üst üste binmesin.
 * Sayı noktalı alt çizgiyle işaretlenir: açıklaması olan hücre belli olsun.
 * shadcn/Base UI Tooltip'i kullanılmadı: portal + aktif tetikleyici kaydı jsdom'da odakla açılmıyor; bu sürüm
 * kütüphanesiz ve deterministik (Escape ile kapanır, odak kalkınca kaybolur).
 */
export function FormulIpucu({ metin, className, children }: Props) {
  const id = useId();
  const [odak, setOdak] = useState(false);
  const [fare, setFare] = useState(false);
  const acik = odak || fare;
  return (
    <span
      tabIndex={0}
      title={acik ? undefined : metin}
      data-formul
      aria-describedby={acik ? id : undefined}
      onFocus={() => setOdak(true)}
      onBlur={() => setOdak(false)}
      onMouseEnter={() => setFare(true)}
      onMouseLeave={() => setFare(false)}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          setOdak(false);
          setFare(false);
        }
      }}
      className={cn(
        "relative block cursor-help rounded-sm underline decoration-muted-foreground/50 decoration-dotted underline-offset-4 outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        className,
      )}
    >
      {children}
      {acik && (
        <span
          role="tooltip"
          id={id}
          className="pointer-events-none absolute top-1/2 right-full z-30 mr-2 w-max max-w-sm -translate-y-1/2 rounded-md bg-foreground px-3 py-1.5 text-left text-xs font-normal whitespace-normal text-background shadow-md"
        >
          {metin}
        </span>
      )}
    </span>
  );
}
