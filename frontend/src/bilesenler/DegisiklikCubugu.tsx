import { LoaderCircle } from "lucide-react";
import { Button } from "@/bilesenler/ui/button";

interface Props {
  /** Taslakta değişen reçete satırı sayısı. */
  satirSayisi: number;
  /** Ne-olur fire override'ı olan satır sayısı (varsa "· M fire" eklenir). */
  fireSayisi?: number;
  /** Satır dışı değişiklik (parametre, üretim bilgisi, gider) sayısı. */
  alanSayisi?: number;
  /** Kayıt isteği sürüyor: iki düğme de kapalı, "Kaydediliyor" durumu görünür. */
  kaydediyor: boolean;
  /** Kaydet kapalıysa nedeni (ipucu + erişilebilir açıklama). */
  kaydetKapali?: boolean;
  kaydetNedeni?: string;
  /** Hesap hatası (Türkçe); varsa çubukta role=alert ile gösterilir. */
  hata?: string | null;
  onKaydet: () => void;
  onVazgec: () => void;
}

/** "2 satırda ve 3 alanda değişiklik · 1 fire" gibi özet. */
export function degisiklikOzeti(satirSayisi: number, fireSayisi = 0, alanSayisi = 0): string {
  const nerede = [satirSayisi > 0 && `${satirSayisi} satırda`, alanSayisi > 0 && `${alanSayisi} alanda`].filter(Boolean).join(" ve ");
  return `${nerede} değişiklik${fireSayisi > 0 ? ` · ${fireSayisi} fire` : ""}`;
}

/**
 * Ekranın altına yapışık Kaydet/Vazgeç çubuğu. Yalnız taslakta değişiklik varken çizilir;
 * kayıt başarılı olup taslak sıfırlanınca kendiliğinden kaybolur.
 */
export function DegisiklikCubugu({
  satirSayisi,
  fireSayisi = 0,
  alanSayisi = 0,
  kaydediyor,
  kaydetKapali = false,
  kaydetNedeni,
  hata = null,
  onKaydet,
  onVazgec,
}: Props) {
  if (satirSayisi + alanSayisi + fireSayisi === 0) return null;
  const neden = kaydetKapali && !kaydediyor ? kaydetNedeni : undefined;
  return (
    <div
      role="region"
      aria-label="Kaydedilmemiş değişiklikler"
      aria-live="polite"
      className="sticky bottom-0 z-20 -mx-4 -mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-marka/40 bg-card/95 px-4 py-3 shadow-[0_-4px_16px_rgba(0,0,0,0.08)] backdrop-blur lg:-mx-8 lg:px-8"
    >
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <span className="font-medium">{degisiklikOzeti(satirSayisi, fireSayisi, alanSayisi)}</span>
        {kaydediyor && (
          <span role="status" aria-label="Kaydediliyor" className="flex items-center gap-1.5 text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
            Kaydediliyor
          </span>
        )}
        {hata && (
          <span role="alert" className="text-destructive">
            {hata}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button type="button" size="sm" variant="outline" onClick={onVazgec} disabled={kaydediyor}>
          Vazgeç
        </Button>
        <Button type="button" size="sm" onClick={onKaydet} disabled={kaydediyor || kaydetKapali} title={neden} aria-description={neden}>
          Kaydet
        </Button>
      </div>
    </div>
  );
}
