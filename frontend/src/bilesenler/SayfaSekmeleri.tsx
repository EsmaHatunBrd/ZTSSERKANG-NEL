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

/** Analizler ve liste çalışması: menüde tek "Analiz" öğesi, işler arasında bu sekmelerle geçilir (sol panel şişmesin). */
export const ANALIZ_SEKMELERI: Sekme[] = [
  { yol: "/ya-olursa", etiket: "Ya olursa" },
  { yol: "/zam-etkisi", etiket: "Zam etkisi" },
  { yol: "/kur-riski", etiket: "Kur riski" },
  { yol: "/karlilik", etiket: "Kârlılık haritası" },
  { yol: "/hedef-fiyat", etiket: "Marjı koruyan fiyat" },
  { yol: "/liste-calismasi", etiket: "Liste çalışması" },
  { yol: "/fiyat-egilimi", etiket: "Fiyat eğilimi" },
];

/** Birbirine yakın sayfaları tek menü öğesi altında toplayan sekme çubuğu; seçili senaryoyu `?senaryo=` ile taşır. */
export function SayfaSekmeleri({ etiket, sekmeler }: { etiket: string; sekmeler: Sekme[] }) {
  const { senaryoId } = useSenaryo();
  return (
    <nav aria-label={etiket} className="flex w-fit max-w-full flex-wrap gap-1 rounded-xl border bg-muted p-1">
      {sekmeler.map((s) => (
        <NavLink
          key={s.yol}
          to={senaryoId === null ? s.yol : `${s.yol}?senaryo=${senaryoId}`}
          className={({ isActive }) =>
            cn(
              "rounded-lg px-4 py-2 text-[15px] font-medium text-muted-foreground transition-colors hover:bg-card/60 hover:text-foreground",
              isActive && "bg-card font-semibold text-foreground shadow-sm ring-1 ring-border hover:bg-card",
            )
          }
        >
          {s.etiket}
        </NavLink>
      ))}
    </nav>
  );
}
