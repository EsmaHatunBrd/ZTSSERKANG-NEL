import type { ReactNode } from "react";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";

/** Kısa kullanım rehberi. Ana menüde yer almaz; sağ üstteki "?" simgesinden açılır (göz önünde değil, ulaşılabilir). */
const ESLEME: [string, string][] = [
  ["Teklif Kapak sayfası", 'Genel Bakış (ürün listesi, maliyet/satış, uyarılar); "Teklif Kapak indir" Teklifler sayfasında'],
  [
    "Ürün sayfaları (001…)",
    "Ürün Maliyeti → ürün seç: reçete, gider kalemleri, toplamlar, finansman, üretim bilgileri, kurlar, satış fiyatı tablosu, teklifler",
  ],
  [
    "Tek bir ürün sayfasının reçetesi",
    "Veri Aktar → Ürün reçetesi: dosyayı yükleyin, değişen sayfaları seçip uygulayın (eski reçete geçmişte kalır)",
  ],
  [
    "S.ALMA BF",
    'Malzeme Fiyatları (geçmişli); yükleme: Veri Aktar → Satın alma fiyat listesi. İkinci fiyat sütunu (I) = revize: "İlk bütçe" ve "Revize" sütunları, süzgeç "Yalnız revize edilenler"',
  ],
  [
    "S.ALMA BF Z/S (G sütunu)",
    '"Kaynak" sütunu: Ziraat (kendi tarımından; enflasyon uygulanmaz) / Satın alma (TL fiyata enflasyon, dövize kur)',
  ],
  [
    "Elle giriş (Excel'de yok)",
    "Veri Girişi: gider havuzu, malzeme fiyatı, parametre, ürün üretim bilgileri (vardiya üretim adedi, personel, mal kabul), hat kapasitesi ve yeni ürün tek sayfadan",
  ],
  [
    "Gider Dağıtım",
    'Gider Dağıtım (havuzlar, alt kalem tutarları, ambalaj sınıfları); yükleme: Veri Aktar → Gider dağıtım. Gider Toplamı "taban × çarpanlar" olarak girilebilir (örn. 1.000.000 × 1,35 × 1,30); Excel\'deki =taban*çarpan formülü de böyle okunur. Alt kalemler TL tutarıyla yazılır, Gider % otomatik (isterseniz "Yüzdeyle"). Toplam ürün ekranından doğrudan değiştirilirse çarpan bilgisi temizlenir ve uyarı verilir',
  ],
  ["Üretim Adetleri", "Üretim Adetleri; yükleme: Veri Aktar → Üretim adetleri"],
  [
    "Enflasyon, kurlar, faiz, stok süresi, kâr oranları",
    "Parametreler (okunur adlarıyla, tarihli geçmiş); ürün ekranındaki kutulardan da değişir",
  ],
  ["Ambalaj Özeti", 'Genel Bakış\'ta tablonun altındaki "Ambalaj ve kapak özeti" bölümü'],
  ["Gerçekleşen Excel'i", 'Veri Aktar → Tüm çalışma kitabı → tür "Gerçekleşen" (aynı sezon); kıyas Bütçe vs Gerçekleşen sayfasında'],
  ["(Excel'de yok)", "Bütçe vs Gerçekleşen, Satış Geçmişi, Karşılaştırma, Değişiklik Günlüğü, Arşiv"],
];

const MENU: [string, string][] = [
  ["Çalışma", "Günlük iş: Genel Bakış, Ürün Maliyeti, Teklifler, Karşılaştırma, Bütçe vs Gerçekleşen, Arşiv"],
  ["Veri girişi", "Veriyi nereden girerim: tek tek (Veri Girişi) ya da Excel'den toplu (Veri Aktar)"],
  [
    "Kayıtlar",
    "Girilen veriyi nerede görürüm: Malzeme Fiyatları, Parametreler, Gider Dağıtım, Üretim Adetleri, Satış Geçmişi — tam listeler, geçmiş ve düzeltme",
  ],
  [
    "Kontrol",
    "Veri Kontrolü (veri sorunlarının özeti ve nereden düzeltileceği), Uyarılar (ürün bazında hesap uyarıları) ve Değişiklik Günlüğü (kim, ne zaman, neyi, neden)",
  ],
];

function Bolum({ kimlik, baslik, children }: { kimlik: string; baslik: string; children: ReactNode }) {
  return (
    <section aria-labelledby={kimlik} className="rounded-xl border bg-card p-4 shadow-sm">
      <h2 id={kimlik} className="mb-2 text-base font-semibold">
        {baslik}
      </h2>
      {children}
    </section>
  );
}

function IkiliTablo({ satirlar, sol, sag }: { satirlar: [string, string][]; sol: string; sag: string }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left text-muted-foreground">
          <th className="py-1 pr-3 font-medium">{sol}</th>
          <th className="py-1 font-medium">{sag}</th>
        </tr>
      </thead>
      <tbody>
        {satirlar.map(([a, b]) => (
          <tr key={a} className="border-b last:border-0 odd:bg-muted/40">
            <td className="py-1.5 pr-3 align-top font-medium">{a}</td>
            <td className="py-1.5 align-top">{b}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function Yardim() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <SayfaBasligi baslik="Yardım" altBaslik="Excel'deki alışkanlıkların buradaki karşılığı ve temel akışlar." />

      <Bolum kimlik="y-ilk" baslik="İlk 10 dakika">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Sağ üstte adınızı girin: yaptığınız her değişiklik bu adla kaydedilir.</li>
          <li>
            Üst bardaki <b>Senaryo</b> seçicisinden çalışmayı seçin (örn. "2026-2027 · Fiyat çalışması").
          </li>
          <li>
            <b>Genel Bakış</b>: tüm ürünlerin maliyeti ve satış fiyatı. Üstteki kutucuklar dikkat gereken yerleri gösterir; tıklayınca
            ilgili listeye gider.
          </li>
          <li>
            Bir ürüne tıklayın: <b>Ürün Maliyeti</b> ekranı Excel'deki ürün sayfasının düzenindedir. Bir hücreyi değiştirin, sonuç anında
            yenilenir.
          </li>
          <li>
            Değişikliği tutmak için üst şeritte <b>Kaydet</b> → neden yazın → <b>Onayla ve kaydet</b>. Vazgeçerseniz hiçbir şey yazılmaz.
          </li>
        </ol>
      </Bolum>

      <Bolum kimlik="y-menu" baslik="Menü düzeni">
        <IkiliTablo satirlar={MENU} sol="Grup" sag="Ne için" />
      </Bolum>

      <Bolum kimlik="y-esleme" baslik="Excel'de neredeydi, burada nerede">
        <IkiliTablo satirlar={ESLEME} sol="Excel'de" sag="Burada" />
      </Bolum>

      <Bolum kimlik="y-sezon" baslik="Yeni sezon / yeni çalışma">
        <p className="mb-2 text-sm">
          Üst bardaki <b>Yeni çalışma</b> düğmesi üç yol sunar; Excel şart değildir:
        </p>
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>
            <b>Boş</b>: sezon adı, çalışma adı ve tür → <b>Boş çalışma aç</b>. Hiç verisi yoktur; ürünleri Veri Girişi'nden, fiyat /
            parametre / gider değerlerini ilgili sayfalardan girersiniz. İsterseniz <b>Parametreleri başka bir çalışmadan al</b> kutusuyla
            kur, faiz, enflasyon gibi değerleri hazır getirebilirsiniz.
          </li>
          <li>
            <b>Geçen sezondan kopyala</b>: kaynak çalışmayı seçin, kopyalanacakları işaretleyin (ürünler ve reçeteler, malzeme fiyatları,
            parametreler, gider dağıtımı ve ambalaj sınıfları, üretim bilgileri ve kapasite, fire kuralları), neden yazın →{" "}
            <b>Kopyala ve aç</b>. Bugün geçerli değerler tek kayıt olarak kopyalanır; kayıtlı hesaplar, teklifler ve kilit kopyalanmaz.
            Sonra yalnız değişenleri güncellersiniz.
          </li>
          <li>
            <b>Excel'den</b>: Veri Aktar → Tüm çalışma kitabı (ayrıntı aşağıda, "Excel'den aktarma").
          </li>
        </ol>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          <li>
            <b>Yeni ürün</b>: Veri Girişi → "Yeni ürün" kartı (kod, ad, ambalaj, hat, sınıf, süzme kg, pazar; ERP kodu henüz yoksa geçici
            bir kod yazın) → <b>Reçeteyi kur</b> bağlantısıyla ürün ekranında reçete satırlarını girin. Ürün, reçetesi kaydedilince
            çalışmaya dahil olur ve hesap gelir.
          </li>
          <li>
            Bir ürün listede görünmüyorsa Ürün Maliyeti sayfasında <b>Çalışma dışı ürünleri göster</b> anahtarını açın: bu çalışmada
            reçetesi olmayan ürünler "Çalışma dışı" rozetiyle listelenir.
          </li>
          <li>
            Çalışmayı adlandırmak ya da silmek için üst bardaki <b>⋯</b> menüsü: <b>Düzenle</b> (ad / sezon / açıklama + neden) ve{" "}
            <b>Sil</b> (yalnız kayıtlı hesabı olmayan, kilitsiz çalışma; silmeden önce otomatik yedek alınır).
          </li>
        </ul>
      </Bolum>

      <Bolum kimlik="y-aktar" baslik="Excel'den aktarma (Veri Aktar)">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            Her sekme aynı adımlarla çalışır: dosya → <b>Önizle</b> (ne değişecek) → neden → <b>Uygula</b>. Önizleme hiçbir şey yazmaz.
          </li>
          <li>
            <b>Tüm çalışma kitabı</b>: önce aktarım modunu seçin. <b>Yeni senaryo oluştur</b> = Excel'deki her şey ayrı, yeni bir çalışma
            olur; var olan çalışmalara dokunulmaz. <b>Mevcut senaryoyu tamamla</b> = seçili çalışmaya yalnız eksikler eklenir, var olan
            hiçbir kayıt değişmez. Yükleme yaklaşık 1 dakika sürer.
          </li>
          <li>
            <b>Kartları güncelle</b>: işaretlerseniz ürün ve malzeme kartlarının bilgileri (ad, birim, hat, ambalaj…) Excel'dekiyle değişir;
            işaretlemezseniz yalnız yeni kartlar açılır, farklar özette listelenir.
          </li>
          <li>
            <b>Ürün reçetesi</b>: bir ya da birkaç ürün sayfası (tam kitap da olur, kopyalanmış tek sayfa da) okunur ve her sayfa için durum
            gösterilir: <i>Yeni ürün</i>, <i>Yeni reçete</i>, <i>Değişti</i> (eklenen / çıkan / değişen satır sayısıyla) ya da <i>Aynı</i>.
            Değişenler seçili gelir. "(2)" ekli sayfalar (aynı ürünün alternatif hesabı) varsayılan seçili değildir; aynı ürün için yalnız
            bir sayfa seçilebilir. Uygulanınca yeni reçete versiyonu açılır, eski versiyon geçmişte kalır.
          </li>
          <li>
            Excel'de elle yazılmış brüt miktar ve birim fiyatlar sistemde de "elle" kalır (ürün ekranında kaynak rozetiyle görünür). Kodu
            olmayan ürün sayfaları geçici <b>SAYFA-056</b> gibi bir kodla alınır; ERP kodu belli olunca ürün ekranından değiştirin.
          </li>
        </ul>
      </Bolum>

      <Bolum kimlik="y-genel" baslik="Genel Bakış">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            Arama, hat ve enflasyon süzgeçleri tablonun üstünde; "N / M ürün" kaç ürünün göründüğünü söyler, "Süzgeçleri temizle" hepsini
            açar.
          </li>
          <li>
            <b>Sütunlar</b> menüsü ek sütun gruplarını açar: Maliyet kırılımı (reçete, GÜG, faaliyet, finans, gider %), Firesiz maliyet,
            Maliyet USD / EUR, Karşılaştırma (geçen yıl, enflasyon eşiği, hedef adetle maliyet), Üretim adedi. Seçiminiz bu bilgisayarda
            hatırlanır.
          </li>
          <li>
            Aynı sezonda gerçekleşen çalışması varsa üstte tek satırlık <b>Gerçekleşen kıyası</b> özeti ve Bütçe vs Gerçekleşen bağlantısı
            görünür.
          </li>
        </ul>
      </Bolum>

      <Bolum kimlik="y-urun" baslik="Ürün ekranında çalışma">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            En üstteki şerit sonucu özetler: birim maliyet (finansman dahil, yanında firesiz), satış fiyatı, döviz karşılıkları ve malzeme
            payı.
          </li>
          <li>
            Hücreye yazın (miktar, fire %, brüt, birim fiyat, gider oranı, kur, faiz, üretim bilgileri): hesap <b>anında yenilenir</b>,
            henüz kaydedilmez.
          </li>
          <li>
            Üst şeritte <b>"N değişiklik · Kaydet · Vazgeç"</b>. Kaydet → değişiklik listesi ve etki (Bu ürün / Senaryo geneli) →{" "}
            <b>Neden</b> yazmak zorunlu → <b>Onayla ve kaydet</b>. Neden boşsa onay düğmesi pasiftir.
          </li>
          <li>Senaryo geneli parametreler (kur, enflasyon) tüm ürünleri etkiler; diyalogda "yalnız bu ürün için yaz" seçilebilir.</li>
          <li>
            Reçetede fiyatı olmayan malzemenin yanında küçük bir nokta vardır; fiyatı Malzeme Fiyatları'ndan ya da hücreye elle girin.
          </li>
          <li>Kaydedilen her hesap numaralı ve tarihlidir; teklif turları kayıtlı hesaba bağlanır.</li>
          <li>
            Sağ üstteki <b>Uyarılar</b> düğmesi bu ürünün uyarılarını gösterir (fiyatsız malzeme, bulunamayan hat, fire kuralı vb.).
          </li>
        </ul>
      </Bolum>

      <Bolum kimlik="y-malzeme" baslik="Malzeme fiyatları: kaynak ve revize">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <b>Kaynak (Excel Z/S)</b>: <b>Ziraat</b> = kendi tarımından gelen malzeme, fiyatına enflasyon uygulanmaz. <b>Satın alma</b> =
            dışarıdan alınan; TL fiyata enflasyon, döviz fiyata kur uygulanır. Ziraat kaynaklı ama döviz fiyatlı malzeme uyarı üretir (kur
            uygulanmaz, kontrol edin).
          </li>
          <li>
            <b>Revize fiyat (S.ALMA BF I sütunu)</b>: Excel'de sonradan yapılan güncelleme sağdaki ikinci fiyat sütununa yazılır; soldaki
            (F) ilk bütçedir. İçe aktarmada ikisi aynı güne iki ayrı fiyat kaydı olur, hesap <b>revizeyi</b> kullanır. Malzeme Fiyatları'nda
            "İlk bütçe" ve "Revize" sütunları, geçmiş çekmecesinde her iki kayıt görünür.
          </li>
          <li>Aynı dosya yeniden yüklenirse geçerli fiyatla kıyaslanır; değişmeyen kalem için yeni kayıt yazılmaz.</li>
        </ul>
      </Bolum>

      <Bolum kimlik="y-gerceklesen" baslik="Bütçe vs Gerçekleşen">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            Gerçekleşen Excel'i (fiyat çalışmasıyla aynı düzende, gerçekleşen değerlerle) Veri Aktar → Tüm çalışma kitabı →{" "}
            <b>Yeni senaryo oluştur</b>, tür <b>Gerçekleşen</b>, aynı sezon adıyla yükleyin. Gerçekleşen çalışmada enflasyon her zaman
            0'dır.
          </li>
          <li>
            Sayfa açılınca A (bütçe) ve B (gerçekleşen) aynı sezondan kendiliğinden seçilir; üstten değiştirebilirsiniz. Tabloda her
            hücrenin üstünde gerçekleşen, altında bütçe değeri vardır.
          </li>
          <li>
            <b>Sapma %</b> = (gerçekleşen − bütçe) / bütçe, finansman dahil birim maliyet TL üzerinden. <b>Sapma eşiği</b> (varsayılan ±%5)
            dışındaki ürünler kalın yazılır ve "±%5 dışında" kutucuğunda sayılır; <b>Yalnız sapanlar</b> yalnız onları gösterir. Liste
            Excel'e aktarılabilir.
          </li>
          <li>
            Bir ürüne tıklayınca <b>Sapmanın kaynağı</b>: farkın ne kadarının malzeme fiyatlarından, reçeteden (miktar, fire, elle fiyat),
            üretim bilgilerinden, gider oranlarından, kurlardan, enflasyondan ve diğer parametrelerden geldiği. Kalemlerin toplamı toplam
            farka eşittir. Altında toplamlar, reçete ve giderler yan yana; değişen hücreler sarı, altında bütçe değeri.
          </li>
        </ul>
      </Bolum>

      <Bolum kimlik="y-diger" baslik="Diğer sayfalar">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <b>Karşılaştırma</b>: ürün ailesi seç → ambalaj büyüdükçe birim fiyat ve kg fiyatı. Geçen yıl satış fiyatı, enflasyon eşiği ve
            hedef adetle maliyet Genel Bakış'ta "Sütunlar" → "Karşılaştırma" grubundadır (geçen yıl için Satış Geçmişi yüklü olmalı). Aile
            adı ürün ekranındaki "Aile" rozetinden değiştirilir: yazdığınız ad olduğu gibi görünür, eşleştirmede büyük/küçük harf farkı
            gözetilmez.
          </li>
          <li>
            <b>Satış Geçmişi</b>: "Şablonu indir" → doldur → yükle (ürün kodu, müşteri, tarih, fiyat, para birimi, adet). Geçen yıl kıyası
            sezon başlangıcından (1 Haziran) önceki 12 ayın satışlarına bakar.
          </li>
          <li>
            <b>Veri Kontrolü</b>: çalışmadaki veri sorunları tek ekranda — hesaplanamayan ürün, fiyatı olmayan malzeme, eksik malzeme kartı,
            %100 olmayan gider payı, gideri eksik hesaplanan ürün, reçetesi olmayan ürün, geçici kodlu ürün, Üretim Adetleri'nde eşleşmeyen
            kod. Her birinin yanında düzeltileceği sayfanın bağlantısı; "Kayıtlar" ile ilgili ürün ve malzemeler listelenir, tıklayınca
            doğrudan o kayda gidilir. Sorun varsa Genel Bakış'ta tek satırlık özet çıkar.
          </li>
          <li>
            <b>Uyarılar</b>: türe göre gruplu; fiyatı olmayan malzemeler en altta malzeme başına toplanır (hangi ürünlerde kullanıldığıyla).
            Alt satırları olan bir reçete kaleminin (maliyeti alt satırlardan gelen) fiyatsız olması uyarı sayılmaz.
          </li>
          <li>
            <b>Değişiklik Günlüğü</b>: kim, ne zaman, neyi, neden; süzgeç; geri al; Excel'e aktar.
          </li>
          <li>
            <b>Arşiv</b>: sezon → senaryo → tarihli kayıtlı hesaplar; iki kaydı kıyasla; <b>Kilitle</b> (kapanan sezon değiştirilemez).
          </li>
          <li>
            <b>Teklifler</b>: senaryo geneli teklif listesi, durum; <b>Teklif Kapak indir</b>. Teklif turu ürün ekranında, hesap
            kaydedildikten sonra "Teklif turları" bölümünden açılır.
          </li>
        </ul>
      </Bolum>

      <p className="text-xs text-muted-foreground">
        Yedek: her açılışta günlük otomatik yedek alınır (son 14 gün); çalışma silinmeden önce ayrıca yedek alınır, bunlar da 14 gün
        tutulur. Sorun olursa sistem yöneticinize başvurun.
      </p>
    </div>
  );
}
