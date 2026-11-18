import { useId, useState } from "react";
import { useUrun, useUrunler } from "@/api/sorgular/urunler";
import type { ParametreTanimi } from "@/api/tipler";
import { D, yuzdeBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { acikMi, bolenMi, EVET_HAYIR_BIRIMI, NEGATIF_OLABILIR, okunurAd, olaganDisiNeden, oranYuzdeye, yuzdeMi, yuzdeOrana } from "./ortak";
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

/**
 * Gösterim: oran yüzde; liste böleni (anahtar verilirse) düz sayı "0,63"; diğerleri Türkçe binlik ayraçla, en çok 4 ondalık
 * (CHF 63,291139… -> 63,2911). Saklanan değer değişmez.
 */
export function degerMetni(deger: string, birim: string | null | undefined, anahtar?: string): string {
  if (birim === EVET_HAYIR_BIRIMI) return acikMi(deger) ? "Açık" : "Kapalı";
  if (anahtar !== undefined && bolenMi(anahtar)) return degerMetni(deger, null);
  if (birim === "oran") return yuzdeBicimle(deger, 2);
  const metin = /^-?\d+(\.\d+)?$/.test(deger.trim())
    ? new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 4 }).format(D(deger).toDecimalPlaces(4).toFixed() as unknown as number)
    : deger.replace(".", ","); // sayı değilse olduğu gibi
  return birim ? `${metin} ${birim}` : metin;
}

/**
 * Parametre değiştirme: değer, geçerlilik, neden ve kapsam (genel / tek ürün). Oran türü parametreler yüzde olarak girilir ("25" = %25;
 * API'ye 0.25 gider); bölenler düz sayı. Değer olağan dışıysa (oran %100'ün üstü, kur %50'den fazla değişiyor) "Yine de kaydet" sorulur.
 */
export function ParametreDiyalogu({ tanim, mevcut, senaryo, gonderiliyor, hata, onGonder, onKapat }: Props) {
  const id = useId();
  const yuzde = yuzdeMi(tanim.anahtar, tanim.birim);
  const ad = okunurAd(tanim.anahtar, tanim.aciklama);
  const apiDegeri = (d: string) => (yuzde ? yuzdeOrana(d) : d);
  const [bekleyen, setBekleyen] = useState<{ v: ParametreGirdisi; neden: string } | null>(null);
  const [kapsam, setKapsam] = useState<"genel" | "urun">("genel");
  const [urunKod, setUrunKod] = useState("");
  const urunler = useUrunler(kapsam === "urun" ? senaryo : null, { boyut: 100 });
  const urun = useUrun(kapsam === "urun" ? urunKod : "", senaryo);

  const engel = kapsam === "urun" && !urun.data ? (urunKod ? "Ürün bilgisi yükleniyor…" : "Ürün kapsamı için bir ürün seçin.") : null;

  function gonder(v: ParametreGirdisi) {
    const neden = olaganDisiNeden(tanim.anahtar, tanim.birim, v.deger, mevcut || undefined);
    if (neden) setBekleyen({ v, neden });
    else onGonder(v);
  }

  return (
    <>
      <DegerDiyalogu
        baslik={`Değiştir: ${ad}`}
        aciklama={tanim.aciklama ?? undefined}
        degerEtiketi={`Yeni değer${
          yuzde
            ? " (yüzde, ör. %25 için 25)"
            : bolenMi(tanim.anahtar)
              ? " (bölen, ör. 0,63)"
              : tanim.birim && tanim.birim !== "oran"
                ? ` (${tanim.birim})`
                : ""
        }`}
        mevcut={yuzde ? oranYuzdeye(mevcut) : mevcut}
        birimEki={yuzde ? "%" : undefined}
        ozet={(d, t) =>
          `Özet: ${ad} ${degerMetni(apiDegeri(d), tanim.birim, tanim.anahtar)} olacak (${goster(t)} tarihinden itibaren, ${
            kapsam === "genel" ? "tüm ürünler" : `ürün ${urunKod || "?"}`
          }).`
        }
        gonderiliyor={gonderiliyor}
        hata={hata}
        engel={engel}
        negatifIzin={NEGATIF_OLABILIR.has(tanim.anahtar)}
        onKapat={onKapat}
        onGonder={(g) => {
          const v = { ...g, deger: apiDegeri(g.deger) };
          gonder(kapsam === "genel" ? { ...v, kapsam_tipi: "genel" } : { ...v, kapsam_tipi: "urun", kapsam_id: urun.data?.id });
        }}
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
      {bekleyen && (
        <OnayDiyalogu
          baslik="Değer olağan dışı görünüyor"
          onayMetni="Yine de kaydet"
          bekliyor={gonderiliyor}
          onOnayla={() => {
            onGonder(bekleyen.v);
            setBekleyen(null);
          }}
          onVazgec={() => setBekleyen(null)}
        >
          <p>
            {ad}: {mevcut ? degerMetni(mevcut, tanim.birim, tanim.anahtar) : "—"} →{" "}
            {degerMetni(bekleyen.v.deger, tanim.birim, tanim.anahtar)}
          </p>
          <p className="text-muted-foreground">{bekleyen.neden} Yanlış yazılmadıysa kaydedin.</p>
        </OnayDiyalogu>
      )}
    </>
  );
}
