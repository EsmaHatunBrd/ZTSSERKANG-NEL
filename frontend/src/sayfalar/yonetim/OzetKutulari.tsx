import { Boxes, CircleDollarSign, Handshake, Percent } from "lucide-react";
import type { YonetimOzeti } from "@/api/tipler";
import { Badge } from "@/bilesenler/ui/badge";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { puanMetni } from "./bicim";
import { OzetKutusu } from "./YonetimKarti";

const sayi = (n: number) => new Intl.NumberFormat("tr-TR").format(n);

/** Dört özet kutusu: ürün sayıları, ortalama kâr marjı (hedefle kıyas), kur riski, açık teklifler. */
export function OzetKutulari({ ozet }: { ozet: YonetimOzeti }) {
  const { urunler, marj, kur_riski: kur, teklifler } = ozet;
  const hedefUstu = marj.ortalama !== null && marj.hedef !== null ? D(marj.ortalama).greaterThanOrEqualTo(D(marj.hedef)) : null;
  const adetYok = marj.adetli_urun === 0;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <OzetKutusu
        baslik="Ürün"
        deger={sayi(urunler.toplam)}
        alt={`${sayi(urunler.hesaplanan)} hesaplanan · ${sayi(urunler.hatali)} hatalı`}
        simge={Boxes}
        ton={urunler.hatali > 0 ? "dikkat" : "sakin"}
      />
      <OzetKutusu
        baslik="Ortalama kâr marjı"
        deger={marj.ortalama === null ? "—" : yuzdeBicimle(marj.ortalama)}
        alt={
          <>
            adetle ağırlıklı {marj.agirlikli_ortalama === null ? "—" : yuzdeBicimle(marj.agirlikli_ortalama)}
            {adetYok ? " (adet yok)" : ` (${sayi(marj.adetli_urun)} ürün)`} · hedef {marj.hedef === null ? "—" : yuzdeBicimle(marj.hedef)}
          </>
        }
        rozet={
          hedefUstu === null ? undefined : hedefUstu ? (
            <Badge variant="secondary">Hedefin üstünde</Badge>
          ) : (
            <Badge variant="destructive">Hedefin altında</Badge>
          )
        }
        simge={Percent}
        ton={hedefUstu === false ? "hata" : "sakin"}
      />
      <OzetKutusu
        baslik="Kur riski"
        deger={puanMetni(kur.doviz_payi_yuzde)}
        alt={`döviz payı · kur +${yuzdeBicimle(kur.oran, 0)} yıllık etki ${paraBicimle(kur.yillik_etki_tl, "TL", 0)}`}
        simge={CircleDollarSign}
      />
      <OzetKutusu
        baslik="Açık teklifler"
        deger={sayi(teklifler.acik_sayi)}
        alt={`toplam ${paraBicimle(teklifler.acik_toplam_tl, "TL", 0)} · ${sayi(teklifler.toplam)} teklif`}
        simge={Handshake}
        ton={teklifler.acik_sayi > 0 ? "dikkat" : "sakin"}
      />
    </div>
  );
}
