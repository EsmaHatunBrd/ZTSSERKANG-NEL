import type { ReactNode } from "react";
import { Button } from "@/bilesenler/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/bilesenler/ui/sheet";
import { goster } from "@/yardimcilar/tarih";

export interface GecmisKaydi {
  deger: string;
  gecerlilik_basi: string;
  neden: string;
  olusturan: string;
  olusturma_zamani: string;
}

interface Props {
  acik: boolean;
  onAcikDegisti?: (acik: boolean) => void;
  baslik: string;
  kayitlar: GecmisKaydi[];
  /** Değeri göstermek için isteğe bağlı biçimleyici (örn. para). */
  degerGoster?: (deger: string) => ReactNode;
  /**
   * "Geri al": eski kaydı ve otomatik nedeni verir. Çağıran bunu YENİ kayıt olarak ekler
   * (kayıtlar asla güncellenmez). Verilmezse düğme çizilmez.
   */
  geriAl?: (kayit: GecmisKaydi, neden: string) => void;
}

export function geriAlNedeni(k: GecmisKaydi): string {
  return `Geri alındı: ${goster(k.gecerlilik_basi)} değeri`;
}

/** Yeniden eskiye sıralı değişiklik geçmişi; ilk kayıt güncel değerdir. */
export function GecmisCekmecesi({ acik, onAcikDegisti, baslik, kayitlar, degerGoster, geriAl }: Props) {
  return (
    <Sheet open={acik} onOpenChange={onAcikDegisti}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>{baslik}</SheetTitle>
          <SheetDescription>Kayıtlar silinmez; geri alma yeni bir kayıt olarak eklenir.</SheetDescription>
        </SheetHeader>
        <ul className="flex flex-col gap-3 overflow-y-auto px-4 pb-4">
          {kayitlar.length === 0 && <li className="text-muted-foreground">Geçmiş kaydı yok.</li>}
          {kayitlar.map((k, i) => (
            <li key={`${k.olusturma_zamani}-${i}`} className="rounded-md border p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-medium tabular-nums">{degerGoster ? degerGoster(k.deger) : k.deger}</span>
                <span className="text-xs text-muted-foreground">{goster(k.gecerlilik_basi)} tarihinden itibaren</span>
              </div>
              <p className="mt-1 text-sm">{k.neden}</p>
              <p className="text-xs text-muted-foreground">
                {k.olusturan} · {goster(k.olusturma_zamani)}
              </p>
              {geriAl && i > 0 && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => geriAl(k, geriAlNedeni(k))}
                >
                  Geri al
                </Button>
              )}
            </li>
          ))}
        </ul>
      </SheetContent>
    </Sheet>
  );
}
