import { Download } from "lucide-react";
import { Link } from "react-router-dom";
import { buttonVariants } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";

const SABLON_ADRESI = "/api/v1/satis-gecmisi/sablon.xlsx";

/** Satış geçmişi zaten kendi sayfasından yüklenir (şablon + CSV/xlsx); burada yalnız yönlendirme vardır. */
export function SatisGecmisiYonlendirme() {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Geçen yılın satış fiyatları şablonla toplu yüklenir veya satır satır elle eklenir. Karşılaştırma ekranları bu veriyi kullanır.
        Yükleme işlemi Satış Geçmişi sayfasındadır.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/satis-gecmisi" className={cn(buttonVariants())}>
          Satış Geçmişi sayfasına git
        </Link>
        <a href={SABLON_ADRESI} download className={cn(buttonVariants({ variant: "outline" }))}>
          <Download aria-hidden />
          Şablonu indir
        </a>
      </div>
    </div>
  );
}
