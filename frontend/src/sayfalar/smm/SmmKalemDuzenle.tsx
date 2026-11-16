import { useId, useState } from "react";
import { hataMetniVarsa } from "@/api/istemci";
import { useSmmKalemEkle, useSmmKalemGuncelle, type SmmKalemAlanlari } from "@/api/sorgular/smmStok";
import type { SmmStokSatiri } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";
import { sayiApi } from "@/yardimcilar/sayi";
import { useSmmYazmaKilidi } from "./SmmDuzenlemeKilidi";

/** Düzenlenebilir sayısal alanlar (Excel TABLO/DBS/HM-YM/DSS/ŞAHİT sütunlarının karşılığı). */
const SAYISAL: { anahtar: keyof SmmKalemAlanlari; etiket: string }[] = [
  { anahtar: "dbs_miktar", etiket: "Dönem başı miktar" },
  { anahtar: "dbs_tutar", etiket: "Dönem başı tutar (TL)" },
  { anahtar: "alim_miktar", etiket: "Alım miktar" },
  { anahtar: "alim_tutar", etiket: "Alım tutar (TL)" },
  { anahtar: "iade_miktar", etiket: "İade miktar" },
  { anahtar: "iade_tutar", etiket: "İade tutar (TL)" },
  { anahtar: "uretim_miktar", etiket: "Üretim girişi (miktar)" },
  { anahtar: "sayim_miktar", etiket: "Sayım miktarı" },
  { anahtar: "sahit_miktar", etiket: "Şahit numune (miktar)" },
];
const METIN: { anahtar: "ad" | "birim" | "tur" | "mizan_kodu"; etiket: string }[] = [
  { anahtar: "ad", etiket: "Ad" },
  { anahtar: "birim", etiket: "Birim" },
  { anahtar: "tur", etiket: "Tür (mizan adı)" },
  { anahtar: "mizan_kodu", etiket: "Mizan kodu" },
];

type Degerler = Record<string, string>;

function baslangic(k: SmmStokSatiri | null): Degerler {
  const d: Degerler = {};
  for (const a of METIN) d[a.anahtar] = (k?.[a.anahtar] as string | null | undefined) ?? "";
  for (const a of SAYISAL) {
    const v = (k as Record<string, unknown> | null)?.[a.anahtar];
    d[a.anahtar] = v == null ? "" : String(v);
  }
  return d;
}

interface Props {
  donemId: number;
  /** Düzenlenen kalem; null ise yeni kalem formu. */
  kalem: SmmStokSatiri | null;
  onKapat: () => void;
  onKaydedildi: (mesaj: string) => void;
}

/**
 * Stok kalemini düzenleme / yeni kalem diyaloğu. Yalnız değişen alanlar gönderilir; neden zorunlu. Sayılar Türkçe (1.234,56) ya da
 * nokta ondalıkla yazılabilir. Kaydedince sarf, DSS ve SMM özeti sunucuda yeniden hesaplanır.
 */
export function SmmKalemDuzenle({ donemId, kalem, onKapat, onKaydedildi }: Props) {
  const id = useId();
  const yeni = kalem === null;
  const guncelle = useSmmKalemGuncelle();
  const ekle = useSmmKalemEkle();
  const yazma = useSmmYazmaKilidi();
  const [kod, setKod] = useState("");
  const [degerler, setDegerler] = useState<Degerler>(() => baslangic(kalem));
  const [neden, setNeden] = useState("");
  const ilk = baslangic(kalem);
  const gonderiliyor = guncelle.isPending || ekle.isPending;

  const hatalar: string[] = [];
  if (yeni && !kod.trim()) hatalar.push("Kod zorunlu");
  for (const a of SAYISAL) {
    const v = degerler[a.anahtar];
    if (v.trim() !== "" && sayiApi(v) === null) hatalar.push(`${a.etiket} geçerli bir sayı olmalı`);
  }
  const degisenler = Object.keys(degerler).filter((k) => degerler[k] !== ilk[k]);
  const kaydedilebilir = hatalar.length === 0 && neden.trim() !== "" && (yeni || degisenler.length > 0) && !gonderiliyor && !yazma.kilitli;

  function govde(): SmmKalemAlanlari {
    const out: Record<string, unknown> = {};
    for (const k of yeni ? Object.keys(degerler) : degisenler) {
      const v = degerler[k].trim();
      if (SAYISAL.some((a) => a.anahtar === k)) {
        if (v === "" && !yeni) out[k] = k === "sahit_miktar" ? null : undefined;
        else if (v !== "") out[k] = sayiApi(v);
      } else out[k] = v === "" ? null : v;
    }
    for (const k of Object.keys(out)) if (out[k] === undefined) delete out[k];
    return out as SmmKalemAlanlari;
  }

  function kaydet() {
    if (!kaydedilebilir) return;
    const onSuccess = () => {
      onKaydedildi(yeni ? `${kod.trim()} eklendi.` : `${kalem!.kod} güncellendi (${degisenler.length} alan).`);
      onKapat();
    };
    if (yeni) ekle.mutate({ donemId, kod: kod.trim(), alanlar: govde(), neden: neden.trim() }, { onSuccess });
    else guncelle.mutate({ donemId, kod: kalem!.kod, alanlar: govde(), neden: neden.trim() }, { onSuccess });
  }

  const hata = hataMetniVarsa(guncelle.error) ?? hataMetniVarsa(ekle.error);

  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{yeni ? "Yeni stok kalemi" : `Kalemi düzenle: ${kalem!.kod}`}</DialogTitle>
          <DialogDescription>
            {yeni
              ? "Excel'de olmayan bir kalem açın. Miktar ve tutarlar boş bırakılırsa 0 alınır."
              : 'Değişen alanlar nedenle günlüğe düşer; sarf, dönem sonu stok ve SMM özeti yeniden hesaplanır. Excel\'den gelen değer için kalem "elle" işaretlenir.'}
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            kaydet();
          }}
        >
          {yeni && (
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-kod`} className="text-sm font-medium">
                Kod *
              </label>
              <Input id={`${id}-kod`} value={kod} onChange={(e) => setKod(e.target.value)} className="h-8 font-mono" />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {METIN.map((a) => (
              <div key={a.anahtar} className="flex flex-col gap-1">
                <label htmlFor={`${id}-${a.anahtar}`} className="text-xs text-muted-foreground">
                  {a.etiket}
                </label>
                <Input
                  id={`${id}-${a.anahtar}`}
                  value={degerler[a.anahtar]}
                  onChange={(e) => setDegerler((d) => ({ ...d, [a.anahtar]: e.target.value }))}
                  className="h-8"
                />
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {SAYISAL.map((a) => (
              <div key={a.anahtar} className="flex flex-col gap-1">
                <label htmlFor={`${id}-${a.anahtar}`} className="text-xs text-muted-foreground">
                  {a.etiket}
                  {!yeni && degerler[a.anahtar] !== ilk[a.anahtar] && <span className="ml-1 text-primary">(değişti)</span>}
                </label>
                <Input
                  id={`${id}-${a.anahtar}`}
                  inputMode="decimal"
                  value={degerler[a.anahtar]}
                  onChange={(e) => setDegerler((d) => ({ ...d, [a.anahtar]: e.target.value }))}
                  className="h-8 text-right tabular-nums"
                />
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-neden`} className="text-sm font-medium">
              Neden *
            </label>
            <Input
              id={`${id}-neden`}
              value={neden}
              onChange={(e) => setNeden(e.target.value)}
              placeholder="Örn. sayım tutanağına göre düzeltme"
              className="h-8"
            />
          </div>
          {hatalar.map((h) => (
            <p key={h} className="text-xs text-destructive">
              {h}
            </p>
          ))}
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onKapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={!kaydedilebilir} title={yazma.neden}>
              {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
