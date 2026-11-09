import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Boxes, CircleAlert, PackageX, TrendingDown, TriangleAlert, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Ton = "sakin" | "dikkat" | "hata";
/** Kart zemini: türüne göre açık pastel ton (verilmezse beyaz kart). */
export type KartRengi = "yesil" | "turuncu" | "sari" | "mavi" | "acik";
const ZEMIN: Record<KartRengi, string> = {
  yesil: "border-transparent bg-kart-yesil",
  turuncu: "border-transparent bg-kart-turuncu",
  sari: "border-transparent bg-kart-sari",
  mavi: "border-transparent bg-kart-mavi",
  acik: "border-transparent bg-card/85 shadow-none",
};

/** Özet kutucuğu: sayı her zaman okunur renkte; yalnız müdahale gereken durumda küçük renkli işaret ve "İncele" görünür. */
export function Kart({
  baslik,
  deger,
  simge: Simge,
  ton = "sakin",
  hedef,
  onTikla,
  eylem = "İncele",
  renk,
}: {
  baslik: string;
  deger: ReactNode;
  simge: LucideIcon;
  ton?: Ton;
  /** Kart bağlantısı (ör. /uyarilar?senaryo=1). */
  hedef?: string;
  /** Bağlantı yerine eylem (ör. tabloyu süz). */
  onTikla?: () => void;
  eylem?: string;
  renk?: KartRengi;
}) {
  const icerik = (
    <>
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-lg",
          renk
            ? "bg-card/70 text-foreground shadow-xs"
            : ton === "hata"
              ? "bg-destructive/10 text-destructive"
              : ton === "dikkat"
                ? "bg-sari text-foreground"
                : "bg-muted text-muted-foreground",
        )}
        aria-hidden
      >
        <Simge className="size-[18px]" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-sm text-muted-foreground">{baslik}</span>
        <span
          className={cn(
            "font-semibold tabular-nums",
            renk ? "text-3xl tracking-tight" : "text-2xl",
            ton === "hata" ? "text-destructive" : "text-foreground",
          )}
        >
          {deger}
        </span>
      </span>
      {ton !== "sakin" && (hedef || onTikla) && (
        <span className="flex items-center gap-1 self-end text-xs font-medium text-muted-foreground group-hover:text-foreground">
          {eylem}
          <ArrowRight className="size-3.5" aria-hidden />
        </span>
      )}
    </>
  );
  const sinif = cn(
    "group flex items-center gap-3 rounded-xl border bg-card p-4 text-left text-card-foreground shadow-xs transition-colors",
    renk && cn(ZEMIN[renk], "p-5"),
  );
  const etkin = ton !== "sakin" && (hedef || onTikla);
  if (etkin && hedef) {
    return (
      <Link to={hedef} className={cn(sinif, "hover:border-foreground/20 hover:bg-accent/40")}>
        {icerik}
      </Link>
    );
  }
  if (etkin && onTikla) {
    return (
      <button type="button" onClick={onTikla} className={cn(sinif, "hover:border-foreground/20 hover:bg-accent/40")}>
        {icerik}
      </button>
    );
  }
  return <div className={sinif}>{icerik}</div>;
}

interface Props {
  urunSayisi: number | null;
  /** Hesabı yapılamayan ürün sayısı; 0 ya da null ise kart gösterilmez. */
  hataSayisi: number | null;
  /** Reçetede kullanılan fiyatsız malzeme sayısı (Veri Kontrolü ile aynı). */
  fiyatsizMalzeme: number | null;
  /** Uyarısı olan ürün sayısı (veri yoksa null -> "—"). */
  uyariliUrun?: number | null;
  /** Enflasyon eşiğinin altında kalan ürün sayısı (tüm ürünler, sunucudan; veri yoksa null -> "—"). */
  enflasyonAltinda?: number | null;
  /** Bağlantılara `?senaryo=` eklemek için. */
  senaryoId?: number | null;
  /** "Enflasyonun altında" kartı: tabloyu bu ürünlere süzer. */
  onEnflasyonSuz?: () => void;
  /** "Hesaplanamayan ürün" kartı: tabloyu hatalı ürünlere süzer. */
  onHataSuz?: () => void;
}

export function UstKartlar({
  urunSayisi,
  hataSayisi,
  fiyatsizMalzeme,
  uyariliUrun = null,
  enflasyonAltinda = null,
  senaryoId = null,
  onEnflasyonSuz,
  onHataSuz,
}: Props) {
  const goster = (n: number | null) => (n === null ? "—" : new Intl.NumberFormat("tr-TR").format(n));
  const sorgu = senaryoId === null ? "" : `senaryo=${senaryoId}`;
  const yol = (p: string, ek = "") => {
    const q = [sorgu, ek].filter(Boolean).join("&");
    return q ? `${p}?${q}` : p;
  };
  return (
    // Özetler tek açık yeşil kutuda toplanır (Power BI tarzı özet paneli); kutucuklar içinde açık zeminli.
    <div className="flex flex-col gap-3">
      <div className={cn("grid flex-1 auto-rows-fr grid-cols-1 gap-3 sm:grid-cols-2", hataSayisi ? "2xl:grid-cols-3" : "")}>
        <Kart baslik="Ürün sayısı" deger={goster(urunSayisi)} simge={Boxes} renk="acik" />
        {!!hataSayisi && (
          <Kart baslik="Hesaplanamayan ürün" deger={goster(hataSayisi)} simge={CircleAlert} ton="hata" onTikla={onHataSuz} eylem="Göster" />
        )}
        <Kart
          baslik="Uyarılı ürün"
          deger={goster(uyariliUrun)}
          simge={TriangleAlert}
          ton={uyariliUrun ? "dikkat" : "sakin"}
          hedef={yol("/uyarilar")}
          renk="acik"
        />
        <Kart
          baslik="Fiyatsız malzeme"
          deger={goster(fiyatsizMalzeme)}
          simge={PackageX}
          ton={fiyatsizMalzeme ? "dikkat" : "sakin"}
          hedef={yol("/veri-kontrolu")}
          renk="acik"
        />
        <Kart
          baslik="Enflasyonun altındaki ürün"
          deger={goster(enflasyonAltinda)}
          simge={TrendingDown}
          ton={enflasyonAltinda ? "dikkat" : "sakin"}
          onTikla={onEnflasyonSuz}
          eylem="Göster"
          renk="acik"
        />
      </div>
    </div>
  );
}
