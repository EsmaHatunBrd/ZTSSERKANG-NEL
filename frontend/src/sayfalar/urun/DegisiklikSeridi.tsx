import { LoaderCircle } from "lucide-react";
import { Button } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";

export interface KayitDurumu {
  hesapId: number | null;
  /** "ürün kartı, 3 reçete satırı ..." gibi yazılan kayıtların özeti. */
  ozet: string;
  /** Sunucunun kayıt sırasında döndürdüğü uyarılar. */
  uyarilar: string[];
}

interface Props {
  /** Taslaktaki değişen alan sayısı. */
  sayi: number;
  hesaplaniyor: boolean;
  /** Hesap hatası (Türkçe); varsa kırmızı gösterilir. */
  hata: string | null;
  onKaydet: () => void;
  onVazgec: () => void;
  /** Kaydet kapalıysa nedeni (ipucu + erişilebilir açıklama). */
  kaydetKapali?: boolean;
  kaydetNedeni?: string;
  /** Son başarılı kayıt. */
  kayit: KayitDurumu | null;
}

/** Başlığın altında yapışkan şerit: değişiklik sayısı, Kaydet ve Vazgeç; hesap durumu. */
export function DegisiklikSeridi({ sayi, hesaplaniyor, hata, onKaydet, onVazgec, kaydetKapali = false, kaydetNedeni, kayit }: Props) {
  const kapali = sayi === 0 || kaydetKapali;
  return (
    <div
      role="region"
      aria-label="Değişiklik şeridi"
      className={cn(
        "sticky top-14 z-10 -mx-1 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-2 backdrop-blur",
        sayi > 0 ? "border-marka/70 bg-sari/90 shadow-md" : "border-transparent bg-background/80",
      )}
    >
      <span aria-live="polite" className={sayi > 0 ? "text-sm font-medium" : "text-sm text-muted-foreground"}>
        {sayi > 0 ? `${sayi} değişiklik` : "Değişiklik yok"}
      </span>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          size="sm"
          onClick={onKaydet}
          disabled={kapali}
          title={sayi > 0 && kaydetKapali ? kaydetNedeni : undefined}
          aria-description={sayi > 0 && kaydetKapali ? kaydetNedeni : undefined}
        >
          Kaydet
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onVazgec} disabled={sayi === 0}>
          Vazgeç
        </Button>
      </div>
      <div className="flex min-h-5 flex-1 items-center justify-end gap-3 text-sm" aria-live="polite">
        {hesaplaniyor && (
          <span role="status" aria-label="Hesaplanıyor" className="flex items-center gap-1.5 text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
            Hesaplanıyor
          </span>
        )}
        {hata && (
          <span role="alert" className="text-destructive">
            {hata}
          </span>
        )}
        {kayit && sayi === 0 && (
          <span
            role="status"
            aria-label="Kayıt durumu"
            className="rounded-md bg-green-50 px-2.5 py-1 text-green-900 dark:bg-green-950/40 dark:text-green-200"
          >
            {`Kaydedildi${kayit.hesapId !== null ? ` · Hesap #${kayit.hesapId}` : ""}${kayit.ozet ? ` · ${kayit.ozet}` : ""}`}
          </span>
        )}
      </div>
      {kayit && sayi === 0 && kayit.uyarilar.length > 0 && (
        <ul className="basis-full text-xs text-muted-foreground" aria-label="Kayıt uyarıları">
          {kayit.uyarilar.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
