import { Download } from "lucide-react";

/** Backend `excel_ortak.SABLONLAR` kimlikleri (sablonlar/ altındaki 16 şablon). */
export type SablonKimligi =
  | "satin_alma_fiyat_listesi"
  | "malzeme_fiyat_listesi"
  | "uretim_adetleri"
  | "gider_dagitim"
  | "urun_recetesi"
  | "stokta_kalan"
  | "satis_gecmisi"
  | "liste_fiyatlari"
  | "canias_urun_agaci"
  | "smm_alim_satis"
  | "smm_iadeler"
  | "smm_uretim"
  | "smm_sayim"
  | "smm_sahit_numune"
  | "smm_gider_mizani"
  | "smm_stok_mizani";

export function sablonAdresi(kimlik: SablonKimligi): string {
  return `/api/v1/sablonlar/${kimlik}.xlsx`;
}

/** Yükleme ekranlarındaki küçük "Şablonu indir" bağlantı düğmesi (oturum çereziyle düz indirme). */
export function SablonIndir({ kimlik, metin = "Şablonu indir" }: { kimlik: SablonKimligi; metin?: string }) {
  return (
    <a
      href={sablonAdresi(kimlik)}
      download
      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-input bg-background px-2.5 text-sm font-medium hover:bg-muted"
    >
      <Download className="size-4" aria-hidden />
      {metin}
    </a>
  );
}

/** Her yükleme ekranındaki kısa yardım satırı. */
export function YuklemeYardimi() {
  return (
    <p className="text-xs text-muted-foreground">Kendi Excel&apos;inizi de yükleyebilirsiniz; başlık adları büyük/küçük harf fark etmez.</p>
  );
}
