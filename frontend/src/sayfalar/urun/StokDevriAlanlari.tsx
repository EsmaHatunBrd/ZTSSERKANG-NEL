import { useId, type ChangeEvent, type ReactNode } from "react";
import { Girdi } from "@/bilesenler/Girdi";
import type { StokDevriFormDegeri, StokDevriHatalari } from "./stokDevriFormu";

interface Props {
  deger: StokDevriFormDegeri;
  onDegis: (d: StokDevriFormDegeri) => void;
  /** Gösterilecek hatalar (kullanıcı kaydet'e basınca ya da alana dokununca). */
  hatalar: StokDevriHatalari;
  devreDisi?: boolean;
}

function Alan({ id, etiket, ipucu, hata, children }: { id: string; etiket: string; ipucu?: string; hata?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">
        {etiket}
      </label>
      {children}
      {ipucu && !hata && <p className="text-xs text-muted-foreground">{ipucu}</p>}
      {hata && (
        <p role="alert" className="text-xs text-destructive">
          {hata}
        </p>
      )}
    </div>
  );
}

/** Dört sayı alanı + neden. Tutarlar sağa yaslı; hatalı alan kırmızı çerçeve ve Türkçe ileti. */
export function StokDevriAlanlari({ deger, onDegis, hatalar, devreDisi }: Props) {
  const id = useId();
  const alan = (k: keyof StokDevriFormDegeri) => ({
    id: `${id}-${k}`,
    value: deger[k],
    disabled: devreDisi,
    "aria-invalid": !!hatalar[k],
    onChange: (e: ChangeEvent<HTMLInputElement>) => onDegis({ ...deger, [k]: e.target.value }),
  });
  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Alan id={`${id}-adet`} etiket="Stok adedi" hata={hatalar.adet}>
          <Girdi {...alan("adet")} inputMode="decimal" className="text-right tabular-nums" />
        </Alan>
        <Alan id={`${id}-birimMaliyet`} etiket="Stok birim maliyeti (TL)" hata={hatalar.birimMaliyet}>
          <Girdi {...alan("birimMaliyet")} inputMode="decimal" className="text-right tabular-nums" />
        </Alan>
        <Alan
          id={`${id}-enflasyon`}
          etiket="Enflasyon (%)"
          ipucu="Boş bırakılırsa çalışmanın enflasyon parametresi"
          hata={hatalar.enflasyon}
        >
          <Girdi {...alan("enflasyon")} inputMode="decimal" placeholder="Parametreden" className="text-right tabular-nums" />
        </Alan>
        <Alan
          id={`${id}-uretimAdedi`}
          etiket="Bu yıl üretim adedi"
          ipucu="Boş bırakılırsa geçen yılın satış adedi"
          hata={hatalar.uretimAdedi}
        >
          <Girdi {...alan("uretimAdedi")} inputMode="decimal" placeholder="Geçen yıl satışından" className="text-right tabular-nums" />
        </Alan>
      </div>
      <Alan id={`${id}-neden`} etiket="Neden (zorunlu)" hata={hatalar.neden}>
        <Girdi {...alan("neden")} />
      </Alan>
    </div>
  );
}
