import { paraBicimle } from "@/yardimcilar/para";
import { AktarimFormu } from "./AktarimFormu";
import { FarkTablosu, Sayac } from "./FarkTablosu";

const yok = (v: string | null | undefined) => (v == null ? "—" : paraBicimle(v, "", 2));

/** Gider Dağıtım sayfası (havuz toplamları, dağıtım anahtarları, ambalaj sınıfları) tek başına yüklenir. */
export function GiderDagitimAktar() {
  return (
    <AktarimFormu
      tip="gider-dagitim"
      sablon="gider_dagitim"
      ad="Gider dağıtımını içe aktar"
      aciklama="Gider Dağıtım sayfası (tam çalışma kitabı veya tek sayfalık dosya). Havuz toplamları, dağıtım bazları, anahtarlar ve ambalaj sınıfları mevcut değerlerle karşılaştırılır; yalnız değişenler yazılır ve geçmişe kaydedilir. Gider oranları değişeceği için hesaplar yeniden hesaplanır."
      onizlemeGoster={(o) => {
        const degisen = o.havuz.filter((h) => h.degisti);
        return (
          <>
            <FarkTablosu
              baslik="Değişen havuzlar"
              sutunlar={["Havuz", "Eski toplam", "Yeni toplam", "Eski baz", "Yeni baz", "Anahtarlar"]}
              satirlar={degisen.map((h) => [
                h.ad,
                yok(h.eski_toplam),
                yok(h.yeni_toplam),
                yok(h.eski_baz),
                yok(h.yeni_baz),
                h.anahtar_farki ? "değişti" : "aynı",
              ])}
              sagda={[1, 2, 3, 4]}
            />
            <Sayac etiket="Aynı havuz" deger={o.havuz.length - degisen.length} />
            <p className="text-sm">
              Ambalaj sınıfı: {o.ambalaj.eski_adet} → {o.ambalaj.yeni_adet}
            </p>
            <FarkTablosu
              baslik="Ambalaj farkları"
              sutunlar={["Sınıf", "Alan", "Eski", "Yeni"]}
              satirlar={o.ambalaj.degisen.map((a) => [a.ad, a.alan, a.eski ?? "—", a.yeni ?? "—"])}
              sagda={[2, 3]}
            />
          </>
        );
      }}
      yazilacakVar={(o) => o.havuz.some((h) => h.degisti) || o.ambalaj.degisen.length > 0}
      ozetKartlari={(u) => [
        { baslik: "Yazılan havuz", deger: u.havuz },
        { baslik: "Yazılan ambalaj sınıfı", deger: u.ambalaj },
      ]}
    />
  );
}
