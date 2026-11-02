import { paraBicimle } from "@/yardimcilar/para";
import { AktarimFormu } from "./AktarimFormu";
import { FarkTablosu, Sayac } from "./FarkTablosu";

/** S.ALMA BF (malzeme kartı + bütçe birim fiyatı) tek başına yüklenir; fiyatlar geçerlilik tarihiyle eklenir (eskiler silinmez). */
export function SatinAlmaAktar() {
  return (
    <AktarimFormu
      tip="satin-alma"
      satinAlma
      ad="Satın alma fiyat listesini içe aktar"
      aciklama="S.ALMA BF sayfası (tam çalışma kitabı veya tek sayfalık dosya). Yeni malzeme kartları açılır, fiyatlar seçilen geçerlilik tarihiyle eklenir; eski fiyatlar geçmişte kalır. Sağdaki ikinci fiyat sütunu (I) revize sayılır: ilk bütçe (F) ve revize aynı güne iki kayıt olarak yazılır, geçerli olan revizedir. Var olan kartlar yalnız Kartları güncelle işaretliyse değişir."
      hatalar={(o) => o.hatali}
      onizlemeGoster={(o) => (
        <>
          <FarkTablosu
            baslik="Yeni malzemeler"
            sutunlar={["Kod", "Ad", "Birim", "Para"]}
            satirlar={o.yeni_malzeme.map((y) => [y.kod, y.ad, y.birim ?? "—", y.para_birimi ?? "—"])}
          />
          <FarkTablosu
            baslik="Kart farkları"
            sutunlar={["Kod", "Değişen alanlar"]}
            satirlar={o.kart_farki.map((k) => [k.kod, k.alanlar.join(", ")])}
          />
          <FarkTablosu
            baslik="Yeni fiyatlar"
            sutunlar={["Kod", "Fiyat", "Para"]}
            satirlar={o.fiyat_yeni.map((f) => [f.kod, paraBicimle(f.yeni, "", 4), f.para ?? "—"])}
            sagda={[1]}
          />
          <FarkTablosu
            baslik="Değişen fiyatlar"
            sutunlar={["Kod", "Eski", "Yeni", "Para"]}
            satirlar={o.fiyat_degisen.map((f) => [f.kod, paraBicimle(f.eski, "", 4), paraBicimle(f.yeni, "", 4), f.para ?? "—"])}
            sagda={[1, 2]}
          />
          <FarkTablosu
            baslik="Revize fiyatlar (S.ALMA BF I)"
            sutunlar={["Kod", "İlk bütçe (F)", "Revize (I)"]}
            satirlar={o.revize.map((r) => [r.kod, r.ilk ? paraBicimle(r.ilk, "", 4) : "—", paraBicimle(r.revize, "", 4)])}
            sagda={[1, 2]}
          />
          <Sayac etiket="Revize edilen" deger={o.revize_sayisi} />
          <Sayac etiket="Aynı" deger={o.ayni} />
          {o.hatali.length > 0 && (
            <section aria-label="Hatalı satırlar" className="flex flex-col gap-1">
              <h3 className="text-sm font-medium text-destructive">Hatalı ({o.hatali.length})</h3>
              <ul className="list-disc pl-5 text-sm text-destructive">
                {o.hatali.map((k, i) => (
                  <li key={i}>{k}: fiyat sayı değil veya negatif</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      yazilacakVar={(o) => o.yeni_malzeme.length + o.fiyat_yeni.length + o.fiyat_degisen.length + o.kart_farki.length > 0}
      ozetKartlari={(u) => [
        { baslik: "Eklenen malzeme", deger: u.malzeme_eklenen },
        { baslik: "Güncellenen kart", deger: u.kart_guncellenen },
        { baslik: "Yazılan fiyat", deger: u.fiyat_yazilan },
        { baslik: "Revize (I) yazılan", deger: u.revize_yazilan },
        { baslik: "Aynı", deger: u.ayni },
      ]}
    />
  );
}
