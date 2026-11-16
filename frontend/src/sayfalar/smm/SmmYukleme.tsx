import type { ReactNode } from "react";
import { SablonIndir, type SablonKimligi } from "@/bilesenler/SablonIndir";
import { YuklemeOzetiKutusu, type YuklemeOzetiT } from "@/bilesenler/YuklemeOzetiKutusu";
import { Button } from "@/bilesenler/ui/button";

/** Maliyet Muhasebesi yükleme kutularının kısa yardım satırı. */
export const SMM_YUKLEME_YARDIMI = "Canias raporunu olduğu gibi yükleyebilirsiniz; başlık adları büyük/küçük harf fark etmez.";

/** Aylık veri kaynağı -> indirilecek şablon (sablonlar/11-16-2026-10..16). */
export const KAYNAK_SABLONU: Record<string, SablonKimligi> = {
  alim: "smm_alim_satis",
  iade: "smm_iadeler",
  uretim: "smm_uretim",
  sayim: "smm_sayim",
  sahit: "smm_sahit_numune",
  gider_mizan: "smm_gider_mizani",
  stok_mizan: "smm_stok_mizani",
};

/** "Şablonu indir" + yardım satırı (şablonu olmayan yüklemede yalnız yardım). */
export function SmmYuklemeYardimi({ kimlik }: { kimlik?: SablonKimligi }) {
  return (
    <span className="flex flex-wrap items-center gap-2">
      {kimlik && <SablonIndir kimlik={kimlik} />}
      <span className="text-xs text-muted-foreground">{SMM_YUKLEME_YARDIMI}</span>
    </span>
  );
}

interface OnizlemeProps {
  /** Önizleme yanıtı (standart özet alanları: okunan, yeni, değişen, aynı, silinecek, atlanan, sorunlu, uyarılar). */
  ozet: YuklemeOzetiT;
  /** Sorunlu satırlar Excel'inin başlığı. */
  baslik: string;
  /** Sayıların üstünde ek bilgi (dönem, kalem sayıları...). */
  children?: ReactNode;
  uygulaMetni?: string;
  uygulanamaz?: boolean;
  bekliyor?: boolean;
  kilitNedeni?: string;
  onUygula: () => void;
  onVazgec: () => void;
}

/** Önizleme kutusu: sayılar, uyarılar, sorunlu satırlar (ilk 50 + "Tümünü Excel indir") ve "Uygula" / "Vazgeç". Hiçbir şey yazılmamıştır. */
export function SmmOnizlemeKutusu({
  ozet,
  baslik,
  children,
  uygulaMetni = "Uygula",
  uygulanamaz = false,
  bekliyor = false,
  kilitNedeni,
  onUygula,
  onVazgec,
}: OnizlemeProps) {
  return (
    <div role="region" aria-label="Önizleme" className="flex w-full flex-col gap-3 rounded-xl border border-dashed bg-muted/30 p-3">
      <p className="text-sm font-medium">Önizleme — henüz hiçbir şey yazılmadı.</p>
      {children}
      <YuklemeOzetiKutusu ozet={ozet} baslik={baslik} />
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={onVazgec}>
          Vazgeç
        </Button>
        <Button type="button" size="sm" disabled={uygulanamaz || bekliyor} title={kilitNedeni} onClick={onUygula}>
          {bekliyor ? "Yükleniyor…" : uygulaMetni}
        </Button>
      </div>
    </div>
  );
}
