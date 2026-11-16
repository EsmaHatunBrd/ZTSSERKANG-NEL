import { Link } from "react-router-dom";
import { SablonIndir } from "@/bilesenler/SablonIndir";
import { SatisYuklemeKarti } from "@/bilesenler/SatisYuklemeKarti";
import { buttonVariants } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";

/** Veri Aktar → Satış geçmişi: dosya yükleme burada da yapılır (Satış Geçmişi sayfasıyla aynı kart); elle satır ve liste o sayfadadır. */
export function SatisGecmisiYonlendirme() {
  return (
    <div className="flex max-w-3xl flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Geçen yılın satış fiyatları şablonla toplu yüklenir veya Satış Geçmişi sayfasında satır satır elle eklenir. Karşılaştırma ekranları
        ve kârlılık haritası bu veriyi kullanır.
      </p>
      <SatisYuklemeKarti />
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/satis-gecmisi" className={cn(buttonVariants({ variant: "outline" }))}>
          Satış Geçmişi sayfasına git
        </Link>
        <SablonIndir kimlik="satis_gecmisi" />
      </div>
    </div>
  );
}
