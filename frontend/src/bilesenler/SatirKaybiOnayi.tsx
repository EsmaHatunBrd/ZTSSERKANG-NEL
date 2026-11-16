import { useState } from "react";
import { ApiHatasi } from "@/api/istemci";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";

/** Backend `excel_ortak.satir_kaybi_denetle` 409 yanıtı: yeni dosya mevcut veriden belirgin biçimde az satır içeriyor. */
export const SATIR_KAYBI_KODU = "satir_kaybi_onayi";

export interface SatirKaybi {
  mevcut: number;
  yeni: number;
  silinecek: number;
  mesaj: string;
}

/** Hata satır kaybı onayı istiyorsa ayrıntısı; değilse null. Sayfalar bu durumda kendi hata kutusunu göstermez. */
export function satirKaybi(e: unknown): SatirKaybi | null {
  if (!(e instanceof ApiHatasi) || e.durum !== 409 || e.kod !== SATIR_KAYBI_KODU) return null;
  const sayi = (v: unknown) => (typeof v === "number" ? v : Number(v) || 0);
  return { mevcut: sayi(e.alanlar.mevcut), yeni: sayi(e.alanlar.yeni), silinecek: sayi(e.alanlar.silinecek), mesaj: e.mesaj };
}

interface Props {
  kayip: SatirKaybi;
  bekliyor?: boolean;
  onOnayla: () => void;
  onVazgec: () => void;
}

/** "N kalem silinecek. Emin misiniz?" diyaloğu. */
export function SatirKaybiOnayi({ kayip, bekliyor = false, onOnayla, onVazgec }: Props) {
  return (
    <OnayDiyalogu
      baslik={`${kayip.silinecek} kalem silinecek. Emin misiniz?`}
      onayMetni="Evet, yükle"
      bekliyor={bekliyor}
      onOnayla={onOnayla}
      onVazgec={onVazgec}
    >
      <p>
        Yeni dosyada {kayip.yeni} satır var, mevcut veride {kayip.mevcut}. Yüklerseniz {kayip.silinecek} kalem silinecek.
      </p>
      <p className="text-muted-foreground">
        Yanlış dosya seçtiyseniz Vazgeç deyin. Yükledikten sonra &quot;Geri al&quot; ile eski duruma dönebilirsiniz.
      </p>
    </OnayDiyalogu>
  );
}

/**
 * Ortak 409 akışı. Kullanım:
 *   const kayip = useSatirKaybiOnayi();
 *   uygula.mutate(d, { onError: (e) => kayip.yakala(e, () => uygula.mutate({ ...d, onay: true })) });
 *   ...{kayip.diyalog}
 * `yakala` hata satır kaybı onayıysa diyaloğu açar ve true döner; Onayla → `yenidenGonder` çağrılır.
 */
export function useSatirKaybiOnayi() {
  const [bekleyen, setBekleyen] = useState<{ kayip: SatirKaybi; gonder: () => void } | null>(null);

  function yakala(e: unknown, yenidenGonder: () => void): boolean {
    const k = satirKaybi(e);
    if (!k) return false;
    setBekleyen({ kayip: k, gonder: yenidenGonder });
    return true;
  }

  const diyalog = bekleyen ? (
    <SatirKaybiOnayi
      kayip={bekleyen.kayip}
      onOnayla={() => {
        const g = bekleyen.gonder;
        setBekleyen(null);
        g();
      }}
      onVazgec={() => setBekleyen(null)}
    />
  ) : null;

  return { yakala, diyalog, acik: bekleyen !== null };
}
