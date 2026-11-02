import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Boxes, CircleAlert, PackageX, TrendingDown, TriangleAlert, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { yuzdeBicimle } from "@/yardimcilar/para";

type Ton = "sakin" | "dikkat" | "hata";

/** Özet kutucuğu: sayı her zaman okunur renkte; yalnız müdahale gereken durumda küçük renkli işaret ve "İncele" görünür. */
export function Kart({
  baslik,
  deger,
  simge: Simge,
  ton = "sakin",
  hedef,
  onTikla,
  eylem = "İncele",
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
}) {
  const icerik = (
    <>
      <span
        className={cn(
          "flex size-9 shrink-0 items-center justify-center rounded-lg",
          ton === "hata"
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
        <span className={cn("text-2xl font-semibold tabular-nums", ton === "hata" ? "text-destructive" : "text-foreground")}>{deger}</span>
      </span>
      {ton !== "sakin" && (hedef || onTikla) && (
        <span className="flex items-center gap-1 self-end text-xs font-medium text-muted-foreground group-hover:text-foreground">
          {eylem}
          <ArrowRight className="size-3.5" aria-hidden />
        </span>
      )}
    </>
  );
  const sinif = "group flex items-center gap-3 rounded-xl border bg-card p-4 text-left text-card-foreground shadow-xs transition-colors";
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
  fiyatsizMalzeme: number | null;
  /** Uyarısı olan ürün sayısı (veri yoksa null -> "—"). */
  uyariliUrun?: number | null;
  /** Enflasyon eşiğinin altında kalan ürün sayısı (tüm ürünler, sunucudan; veri yoksa null -> "—"). */
  enflasyonAltinda?: number | null;
  /** Payları 1'e eşit olmayan havuzlar. */
  payKontrol: { havuz: string; toplam: string }[];
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
  payKontrol,
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
    <div className="flex flex-col gap-3">
      <div className={cn("grid grid-cols-1 gap-3 sm:grid-cols-2", hataSayisi ? "xl:grid-cols-5" : "xl:grid-cols-4")}>
        <Kart baslik="Ürün sayısı" deger={goster(urunSayisi)} simge={Boxes} />
        {!!hataSayisi && (
          <Kart baslik="Hesaplanamayan ürün" deger={goster(hataSayisi)} simge={CircleAlert} ton="hata" onTikla={onHataSuz} eylem="Göster" />
        )}
        <Kart
          baslik="Uyarılı ürün"
          deger={goster(uyariliUrun)}
          simge={TriangleAlert}
          ton={uyariliUrun ? "dikkat" : "sakin"}
          hedef={yol("/uyarilar")}
        />
        <Kart
          baslik="Fiyatsız malzeme"
          deger={goster(fiyatsizMalzeme)}
          simge={PackageX}
          ton={fiyatsizMalzeme ? "dikkat" : "sakin"}
          hedef={yol("/fiyatlar", "fiyatsiz=1")}
        />
        <Kart
          baslik="Enflasyonun altındaki ürün"
          deger={goster(enflasyonAltinda)}
          simge={TrendingDown}
          ton={enflasyonAltinda ? "dikkat" : "sakin"}
          onTikla={onEnflasyonSuz}
          eylem="Göster"
        />
      </div>
      {payKontrol.length > 0 && (
        <div role="status" className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border bg-sari/60 px-3 py-2 text-sm">
          <TriangleAlert className="size-4 shrink-0" aria-hidden />
          <span>
            <span className="font-medium">Gider paylarının toplamı %100 değil:</span>{" "}
            {payKontrol.map((p) => `${p.havuz} (${yuzdeBicimle(p.toplam)})`).join(", ")}
          </span>
          <Link to={yol("/gider")} className="ml-auto inline-flex items-center gap-1 font-medium underline-offset-4 hover:underline">
            Gider Dağıtım&apos;da düzelt
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      )}
    </div>
  );
}
