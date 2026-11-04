import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import { useSenaryo } from "./SenaryoSecici";

export interface Sekme {
  yol: string;
  etiket: string;
}

/** Kıyas işleri: menüde tek "Kıyasla" öğesi, sayfalar arasında bu sekmelerle geçilir. */
export const KIYAS_SEKMELERI: Sekme[] = [
  { yol: "/butce-gerceklesen", etiket: "Bütçe vs Gerçekleşen" },
  { yol: "/karsilastirma", etiket: "Ürün aileleri" },
  { yol: "/arsiv", etiket: "Geçmiş kayıtlar" },
];

/** Kontrol işleri: menüde tek "Veri Kontrolü" öğesi; ürün bazında hesap uyarıları ikinci sekmede. */
export const KONTROL_SEKMELERI: Sekme[] = [
  { yol: "/veri-kontrolu", etiket: "Özet" },
  { yol: "/uyarilar", etiket: "Ürün uyarıları" },
];

/** Birbirine yakın sayfaları tek menü öğesi altında toplayan sekme çubuğu; seçili senaryoyu `?senaryo=` ile taşır. */
export function SayfaSekmeleri({ etiket, sekmeler }: { etiket: string; sekmeler: Sekme[] }) {
  const { senaryoId } = useSenaryo();
  return (
    <nav aria-label={etiket} className="-mb-1 flex flex-wrap gap-1 border-b">
      {sekmeler.map((s) => (
        <NavLink
          key={s.yol}
          to={senaryoId === null ? s.yol : `${s.yol}?senaryo=${senaryoId}`}
          className={({ isActive }) =>
            cn(
              "-mb-px border-b-2 border-transparent px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground",
              isActive && "border-marka font-semibold text-foreground",
            )
          }
        >
          {s.etiket}
        </NavLink>
      ))}
    </nav>
  );
}
