import { Link } from "react-router-dom";
import type { ExcelTamYaniti } from "@/api/tipler";
import { buttonVariants } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";

function Kart({ baslik, deger, vurgu }: { baslik: string; deger: number; vurgu?: boolean }) {
  return (
    <div className="rounded-lg border p-3">
      <div data-kart-baslik className="text-sm text-muted-foreground">
        {baslik}
      </div>
      <div className={cn("text-2xl font-semibold tabular-nums", vurgu && deger > 0 && "text-amber-600 dark:text-amber-400")}>{deger}</div>
    </div>
  );
}

function Liste({ baslik, ogeler }: { baslik: string; ogeler: string[] }) {
  if (ogeler.length === 0) return null;
  return (
    <details className="rounded-lg border px-3 py-2">
      <summary className="cursor-pointer text-sm font-medium">
        {baslik} ({ogeler.length})
      </summary>
      <ul className="mt-2 list-disc pl-5 text-sm">
        {ogeler.map((o, i) => (
          <li key={`${o}-${i}`}>{o}</li>
        ))}
      </ul>
    </details>
  );
}

/** Tüm çalışma kitabı içe aktarma sonucu: sayaç kartları ve ayrıntı listeleri. */
export function ImportOzetiKartlari({ ozet }: { ozet: ExcelTamYaniti }) {
  return (
    <section aria-label="İçe aktarma özeti" role="region" className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold">{ozet.mod === "tamamla" ? "Mevcut senaryo tamamlandı" : "İçe aktarma tamamlandı"}</h2>
      {ozet.mod === "tamamla" && (
        <p className="text-sm text-muted-foreground">Yeni senaryo açılmadı; sayılar yalnızca eklenen kayıtları gösterir.</p>
      )}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Kart baslik="Malzeme" deger={ozet.malzeme} />
        <Kart baslik="Fiyat" deger={ozet.fiyat} />
        <Kart baslik="Revize fiyat (S.ALMA BF I)" deger={ozet.revize} />
        <Kart baslik="Havuz" deger={ozet.havuz} />
        <Kart baslik="Ambalaj" deger={ozet.ambalaj} />
        <Kart baslik="Ürün" deger={ozet.urun} />
        <Kart baslik="Reçete" deger={ozet.recete} />
        <Kart baslik="Parametre" deger={ozet.parametre} />
        <Kart baslik="Üretim adedi (kapasite)" deger={ozet.kapasite ?? 0} />
        <Kart baslik="Satış fiyatı notu" deger={ozet.satis_notu} />
        <Kart baslik="Atlanan" deger={ozet.atlanan.length} vurgu />
        <Kart baslik="Uyarılar" deger={ozet.uyarilar.length} vurgu />
        <Kart baslik="Kart farkları" deger={ozet.kart_farklari.length} />
        <Kart baslik="Yeniden adlandırılan" deger={ozet.yeniden_adlandirilan.length} />
        <Kart baslik="Ürün parametre farkları" deger={ozet.urun_parametre_farklari.length} />
      </div>
      <Liste baslik="Atlananlar" ogeler={ozet.atlanan} />
      <Liste baslik="Uyarı ayrıntıları" ogeler={ozet.uyarilar} />
      <Liste baslik="Kart farkı ayrıntıları" ogeler={ozet.kart_farklari.map((k) => `${k.tur} ${k.kod}: ${k.alanlar.join(", ")}`)} />
      <Liste baslik="Yeniden adlandırma ayrıntıları" ogeler={ozet.yeniden_adlandirilan.map((y) => `${y.eski} → ${y.yeni}`)} />
      <Liste
        baslik="Ürün parametre farkı ayrıntıları"
        ogeler={ozet.urun_parametre_farklari.map((p) => `${p.ad}: ${p.anahtar} = ${p.deger}`)}
      />
      <div>
        <Link to={`/genel-bakis?senaryo=${ozet.senaryo_id}`} className={buttonVariants()}>
          Genel Bakış&apos;a git
        </Link>
      </div>
    </section>
  );
}
