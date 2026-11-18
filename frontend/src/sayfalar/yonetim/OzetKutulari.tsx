import { Boxes, CircleDollarSign, Handshake, Percent } from "lucide-react";
import type { YonetimOzeti } from "@/api/tipler";
import { Badge } from "@/bilesenler/ui/badge";
import { paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { puanMetni } from "./bicim";
import { OzetKutusu } from "./YonetimKarti";

const sayi = (n: number) => new Intl.NumberFormat("tr-TR").format(n);

/** "toplam 9 teklif (5 kabul, 1 red)": sonuçlanan teklif yoksa parantez yazılmaz. */
function teklifAltMetni(t: YonetimOzeti["teklifler"]): string {
  const sonuc = (["kabul", "red"] as const).filter((d) => (t.durumlar[d] ?? 0) > 0).map((d) => `${sayi(t.durumlar[d])} ${d}`);
  return `toplam ${sayi(t.toplam)} teklif${sonuc.length ? ` (${sonuc.join(", ")})` : ""}`;
}

/**
 * Dört özet kutusu: ürün sayıları, kâr marjı, kur riski, açık teklifler. Kâr marjı iki sayıdır: geçen yılın satış fiyatıyla (büyük;
 * Kârlılık haritasıyla aynı formül, adetle ağırlıklı) ve hesaplanan satış fiyatıyla (küçük; maliyet x (1 + satış kâr oranı) olduğu için
 * kâr oranına eşittir). Rozet marj eşiğinin altındaki ürün sayısıdır. Açık tekliflerin TL toplamı gösterilmez (birim fiyatların toplamı
 * anlamlı bir tutar değildir).
 */
export function OzetKutulari({ ozet }: { ozet: YonetimOzeti }) {
  const { urunler, marj, kur_riski: kur, teklifler } = ozet;
  const gecenYil = marj.gecen_yil_agirlikli_ortalama ?? null;
  const hesapMarji = marj.agirlikli_ortalama ?? marj.ortalama;
  const esikAlti = ozet.hedef_alti.toplam;
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
        baslik="Kâr marjı"
        deger={
          <>
            {gecenYil === null ? "—" : yuzdeBicimle(gecenYil)}{" "}
            <span className="text-sm font-normal text-muted-foreground">geçen yılın satış fiyatıyla</span>
          </>
        }
        alt={
          <>
            <span className="block">
              {gecenYil === null ? "satış geçmişi olan ürün yok" : `adetle ağırlıklı · ${sayi(marj.gecen_yil_urun ?? 0)} ürün`}
            </span>
            <span className="block">Hesaplanan satış fiyatıyla {hesapMarji === null ? "—" : yuzdeBicimle(hesapMarji)}</span>
          </>
        }
        rozet={
          esikAlti > 0 ? (
            <Badge variant="destructive">Marj eşiğinin altında {sayi(esikAlti)} ürün</Badge>
          ) : (
            <Badge variant="secondary">Marj eşiğinin altında ürün yok</Badge>
          )
        }
        simge={Percent}
        ton={esikAlti > 0 ? "dikkat" : "sakin"}
      />
      <OzetKutusu
        baslik="Kur riski"
        deger={puanMetni(kur.doviz_payi_yuzde)}
        alt={`döviz payı · kur +${yuzdeBicimle(kur.oran, 0)} yıllık etki ${paraBicimle(kur.yillik_etki_tl, "TL", 0)}`}
        simge={CircleDollarSign}
      />
      <OzetKutusu
        baslik="Teklifler"
        deger={`${sayi(teklifler.acik_sayi)} açık teklif`}
        alt={teklifAltMetni(teklifler)}
        simge={Handshake}
        ton={teklifler.acik_sayi > 0 ? "dikkat" : "sakin"}
      />
    </div>
  );
}
