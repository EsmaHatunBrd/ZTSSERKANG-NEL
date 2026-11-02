import { AktarimFormu } from "./AktarimFormu";
import { FarkTablosu, Sayac } from "./FarkTablosu";

/** Üretim Adetleri sayfası (tam kitaptaki sayfa veya tek sayfalık dosya) tek başına yüklenir. */
export function UretimAdetleriAktar() {
  return (
    <AktarimFormu
      tip="uretim-adetleri"
      ad="Üretim adetlerini içe aktar"
      aciklama="Üretim Adetleri sayfası (tam çalışma kitabı veya yalnız bu sayfayı içeren tek sayfalık dosya). Senaryodaki mevcut kapasiteyle karşılaştırılır; yalnız yeni ve değişen ürünler yazılır, her değişiklik geçmişe kaydedilir."
      onizlemeGoster={(o) => (
        <>
          <FarkTablosu
            baslik="Yeni ürünler"
            sutunlar={["Ürün kodu", "Ürün adı", "Hedef üretim"]}
            satirlar={o.yeni.map((y) => [y.urun_kodu, y.urun_ad, y.alanlar.hedef_uretim])}
            sagda={[2]}
          />
          <FarkTablosu
            baslik="Değişen alanlar"
            sutunlar={["Ürün kodu", "Alan", "Eski", "Yeni"]}
            satirlar={o.degisen.map((d) => [d.urun_kodu, d.alan, d.eski ?? "—", d.yeni ?? "—"])}
            sagda={[2, 3]}
          />
          <Sayac etiket="Aynı" deger={o.ayni} />
          {o.uyarilar.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-amber-700 dark:text-amber-400">
              {o.uyarilar.map((u, i) => (
                <li key={i}>{u}</li>
              ))}
            </ul>
          )}
        </>
      )}
      yazilacakVar={(o) => o.yeni.length + o.degisen.length > 0}
      ozetKartlari={(u) => [
        { baslik: "Eklenen", deger: u.eklenen },
        { baslik: "Güncellenen", deger: u.guncellenen },
        { baslik: "Uyarılar", deger: u.uyarilar.length },
      ]}
      uyarilar={(u) => u.uyarilar}
    />
  );
}
