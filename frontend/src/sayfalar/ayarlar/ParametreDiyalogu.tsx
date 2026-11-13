import { useId, useState } from "react";
import { useUrun, useUrunler } from "@/api/sorgular/urunler";
import type { ParametreTanimi } from "@/api/tipler";
import { D, yuzdeBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { acikMi, EVET_HAYIR_BIRIMI, NEGATIF_OLABILIR } from "./ortak";
import { DegerDiyalogu, type DegerGirdisi } from "./DegerDiyalogu";

export interface ParametreGirdisi extends DegerGirdisi {
  kapsam_tipi: "genel" | "urun";
  kapsam_id?: number;
}

interface Props {
  tanim: ParametreTanimi;
  mevcut: string;
  senaryo: number;
  gonderiliyor: boolean;
  hata: string | null;
  onGonder: (v: ParametreGirdisi) => void;
  onKapat: () => void;
}

/** Gösterim: oran yüzde; diğerleri Türkçe binlik ayraçla, en çok 4 ondalık (CHF 63,291139… -> 63,2911). Saklanan değer değişmez. */
export function degerMetni(deger: string, birim: string | null | undefined): string {
  if (birim === EVET_HAYIR_BIRIMI) return acikMi(deger) ? "Açık" : "Kapalı";
  if (birim === "oran") return yuzdeBicimle(deger, 2);
  const metin = /^-?\d+(\.\d+)?$/.test(deger.trim())
    ? new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 4 }).format(D(deger).toDecimalPlaces(4).toFixed() as unknown as number)
    : deger.replace(".", ","); // sayı değilse olduğu gibi
  return birim ? `${metin} ${birim}` : metin;
}

/** Parametre değiştirme: değer, geçerlilik, neden ve kapsam (genel / tek ürün). */
export function ParametreDiyalogu({ tanim, mevcut, senaryo, gonderiliyor, hata, onGonder, onKapat }: Props) {
  const id = useId();
  const [kapsam, setKapsam] = useState<"genel" | "urun">("genel");
  const [urunKod, setUrunKod] = useState("");
  const urunler = useUrunler(kapsam === "urun" ? senaryo : null, { boyut: 100 });
  const urun = useUrun(kapsam === "urun" ? urunKod : "", senaryo);

  const engel = kapsam === "urun" && !urun.data ? (urunKod ? "Ürün bilgisi yükleniyor…" : "Ürün kapsamı için bir ürün seçin.") : null;

  return (
    <DegerDiyalogu
      baslik={`Değiştir: ${tanim.anahtar}`}
      aciklama={tanim.aciklama ?? undefined}
      degerEtiketi={`Yeni değer${tanim.birim === "oran" ? " (oran, örn. 0,25 = %25)" : tanim.birim ? ` (${tanim.birim})` : ""}`}
      mevcut={mevcut}
      ozet={(d, t) =>
        `Özet: ${tanim.anahtar} ${degerMetni(d, tanim.birim)} olacak (${goster(t)} tarihinden itibaren, ${
          kapsam === "genel" ? "tüm ürünler" : `ürün ${urunKod || "?"}`
        }).`
      }
      gonderiliyor={gonderiliyor}
      hata={hata}
      engel={engel}
      negatifIzin={NEGATIF_OLABILIR.has(tanim.anahtar)}
      onKapat={onKapat}
      onGonder={(v) =>
        onGonder(kapsam === "genel" ? { ...v, kapsam_tipi: "genel" } : { ...v, kapsam_tipi: "urun", kapsam_id: urun.data?.id })
      }
    >
      <fieldset className="flex flex-col gap-2">
        <legend className="text-sm font-medium">Kapsam</legend>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name={`${id}-kapsam`} checked={kapsam === "genel"} onChange={() => setKapsam("genel")} />
          Genel (tüm ürünler)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name={`${id}-kapsam`} checked={kapsam === "urun"} onChange={() => setKapsam("urun")} />
          Yalnızca bir ürün için
        </label>
        {kapsam === "urun" && (
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-urun`} className="text-sm font-medium">
              Ürün
            </label>
            <select
              id={`${id}-urun`}
              className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2 text-sm"
              value={urunKod}
              onChange={(e) => setUrunKod(e.target.value)}
            >
              <option value="">Seçin…</option>
              {(urunler.data?.kayitlar ?? []).map((u) => (
                <option key={u.kod} value={u.kod}>
                  {u.kod} — {u.ad}
                </option>
              ))}
            </select>
          </div>
        )}
      </fieldset>
    </DegerDiyalogu>
  );
}
