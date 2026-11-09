import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import type { DashboardSatiri } from "@/api/tipler";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";

/** Cümle içindeki rakam/ad: altı noktalı çizgiyle vurgulanır (okurken göz rakamı yakalasın). */
function V({ children }: { children: ReactNode }) {
  return <b className="border-b border-dotted border-marka font-semibold text-foreground">{children}</b>;
}

interface Props {
  satirlar: DashboardSatiri[];
  /** Ürün kodu -> uyarı listesi. */
  uyarilar: Map<string, string[]>;
}

/**
 * "Öne çıkanlar": seçili çalışmanın rakamlarından otomatik kurulan kısa cümleler (Power BI'daki akıllı anlatım gibi). Yeni hesap yok;
 * Genel Bakış satırlarındaki maliyet, gider payı, hat ve uyarılardan uç değerler seçilir. Veri yoksa hiçbir şey çizilmez.
 */
export function OneCikanlar({ satirlar, uyarilar }: Props) {
  const gecerli = satirlar.filter((s) => !s.hata && s.maliyet_tl !== null);
  if (gecerli.length === 0) return null;
  const maliyet = [...gecerli].sort((a, b) => D(b.maliyet_tl).comparedTo(D(a.maliyet_tl)));
  const pahali = maliyet[0];
  const ucuz = maliyet[maliyet.length - 1];
  const giderli = gecerli.filter((s) => s.gider_yuzdesi !== null);
  const ortGider = giderli.length ? giderli.reduce((t, s) => t.plus(D(s.gider_yuzdesi)), D(0)).dividedBy(giderli.length) : null;
  const enGider = [...giderli].sort((a, b) => D(b.gider_yuzdesi).comparedTo(D(a.gider_yuzdesi)))[0];
  const hatSayisi = new Map<string, number>();
  for (const s of gecerli) hatSayisi.set(s.hat ?? "—", (hatSayisi.get(s.hat ?? "—") ?? 0) + 1);
  const [buyukHat, hatAdet] = [...hatSayisi.entries()].sort((a, b) => b[1] - a[1])[0];
  const enUyarili = [...uyarilar.entries()].sort((a, b) => b[1].length - a[1].length)[0];
  const uyariliAd = enUyarili ? (satirlar.find((s) => s.kod === enUyarili[0])?.ad ?? enUyarili[0]) : null;

  return (
    <section aria-label="Öne çıkanlar" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <h2 className="flex items-center gap-2 text-base font-semibold">
        <Sparkles className="size-4 text-marka" aria-hidden />
        Öne çıkanlar
      </h2>
      <ul className="flex flex-col gap-3 text-sm leading-relaxed text-muted-foreground">
        <li>
          {gecerli.length} ürünün birim maliyeti <V>{paraBicimle(ucuz.maliyet_tl)}</V> ile <V>{paraBicimle(pahali.maliyet_tl)}</V> arasında;
          en pahalısı <V>{pahali.ad}</V>.
        </li>
        {ortGider && enGider && (
          <li>
            Maliyetin ortalama <V>{yuzdeBicimle(ortGider)}</V> kadarı gider payı (işçilik, genel üretim, faaliyet, finansman); en yüksek pay{" "}
            <V>{enGider.ad}</V> ürününde (<V>{yuzdeBicimle(enGider.gider_yuzdesi)}</V>).
          </li>
        )}
        {enUyarili && (
          <li>
            <V>{uyarilar.size}</V> ürünün hesabında uyarı var; en çok uyarı <V>{uyariliAd}</V> ürününde (<V>{enUyarili[1].length}</V>).
          </li>
        )}
        <li>
          En çok ürün <V>{buyukHat}</V> hattında (<V>{hatAdet}</V> ürün).
        </li>
      </ul>
    </section>
  );
}
