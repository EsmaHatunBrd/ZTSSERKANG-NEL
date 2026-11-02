import type { ReactNode } from "react";
import type { Fiyatlar, Toplamlar } from "@/api/tipler";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";

interface Props {
  toplamlar: Toplamlar;
  toplamlarFiresiz: Toplamlar | null;
  fiyatlar: Fiyatlar;
  /** Sonuç son geçerli hesaptan (taslak hesaplanamadı): soluk gösterilir. */
  bayat?: boolean;
}

const para = (d: string | null | undefined, pb: string, basamak = 2) => (d == null ? "—" : paraBicimle(d, pb, basamak));

/** Kâr oranı (0.2) -> "%20". */
const oranMetni = (o: string | null | undefined) =>
  o == null ? null : `%${D(o).times(100).toDecimalPlaces(1).toFixed().replace(".", ",")}`;

/** Pay (a / b) -> "%61,3"; b 0 ya da yoksa null. */
function pay(a: string | null | undefined, b: string | null | undefined): string | null {
  if (a == null || b == null || D(b).isZero()) return null;
  return `%${D(a).div(D(b)).times(100).toDecimalPlaces(1).toFixed(1).replace(".", ",")}`;
}

function Kutu({ baslik, deger, alt, vurgu }: { baslik: string; deger: ReactNode; alt?: ReactNode; vurgu?: boolean }) {
  return (
    <div
      className={cn("flex min-w-0 flex-col gap-0.5 rounded-xl border bg-card px-4 py-3 shadow-xs", vurgu && "border-marka/60 bg-accent/40")}
    >
      <span className="text-sm text-muted-foreground">{baslik}</span>
      <span className="text-2xl font-semibold tracking-tight tabular-nums">{deger}</span>
      {alt && <span className="text-xs text-muted-foreground tabular-nums">{alt}</span>}
    </div>
  );
}

/**
 * Ürün ekranının cevabı en üstte: finansman dahil birim maliyet, satış fiyatı (TL ve döviz), malzeme/gider dağılımı.
 * Ayrıntı (Toplamlar, Satış fiyatı tabloları) sayfanın aşağısında kalır; buradaki rakamlar onlarla aynı alanlardır.
 */
export function SonucSeridi({ toplamlar: t, toplamlarFiresiz: tf, fiyatlar: f, bayat }: Props) {
  const kar = oranMetni(f.satis_kar_orani);
  return (
    <section aria-label="Hesap sonucu" className={cn("grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4", bayat && "opacity-60")}>
      <Kutu
        baslik="Birim maliyet (finansman dahil)"
        deger={para(t.maliyet_tl, "TL")}
        alt={tf ? `Firesiz: ${para(tf.maliyet_tl, "TL")}` : undefined}
      />
      <Kutu baslik={kar ? `Satış fiyatı (kâr ${kar})` : "Satış fiyatı"} deger={para(f.satis_tl, "TL")} vurgu />
      <Kutu baslik="Satış fiyatı (döviz)" deger={para(f.satis_usd, "USD", 3)} alt={`EUR: ${para(f.satis_eur, "EUR", 3)}`} />
      <Kutu
        baslik="Maliyet dağılımı"
        deger={
          <span className="flex items-baseline gap-2 text-xl">
            <span title="Hammadde ve yardımcı malzeme">{pay(t.malzeme, t.maliyet_tl) ?? "—"}</span>
            <span className="text-sm font-normal text-muted-foreground">malzeme</span>
          </span>
        }
        alt={`Malzeme ${para(t.malzeme, "TL")} · Gider ${para(t.uretim_gideri, "TL")}`}
      />
    </section>
  );
}
