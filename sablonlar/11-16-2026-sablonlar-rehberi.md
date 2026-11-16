# Excel yükleme şablonları rehberi

Uygulamada Excel yüklenen her yer için bir şablon: doldurulacak sayfa (adı uygulamanın aradığı ad, kitabın ilk sayfası), **Örnek** sayfası (uydurma örnek satırlar) ve **Açıklama** sayfası (her sütun ne demek, sık hatalar). Şablonu doldurup dosyayı doğrudan yükleyebilirsiniz; Örnek ve Açıklama sayfaları dosyada kalabilir, uygulama onları okumaz.

Dosyalar: `sablonlar/` klasörü (proje kökünde). Tarih: 16.11.2026. Okuyucu: muhasebe ekibi ve Esma.

**Renkler:** koyu yeşil başlık = zorunlu sütun · açık gri = isteğe bağlı · soluk italik = uygulama okumaz (yerini korumak için durur, boş kalabilir). Gider dağıtım ve ürün reçetesi sabit hücre düzenindedir: yeşil hücreler zorunlu, gri hücreler isteğe bağlıdır.

**Genel kurallar:** dosya .xlsx olmalı (satış geçmişi ve liste fiyatları .csv de kabul eder). Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı bazı yüklemelerde hata verir, bazılarında uyarısız 0 okunur. Başlık metinlerini ve sayfa adlarını değiştirmeyin. Boyut sınırı: Veri Aktar ve Malzeme Fiyatları 25 MB, satış geçmişi ve liste fiyatları 10 MB, Maliyet Muhasebesi 60 MB.

## Sezon başında sırayla

- [ ] Fiyat Çalışması kitabının tamamı varsa: **Veri Aktar › Tüm çalışma kitabı** (malzeme, fiyat, gider, ürün, reçete, parametre, üretim adetleri tek seferde; şablonu yok, kendi Excel'iniz). Varsa sonraki adımlardan yalnız eksik kalanlar yapılır.
- [ ] **01 Satın alma fiyat listesi**: malzeme kartları ve bütçe fiyatları. Reçeteden önce gelir: reçetedeki malzemelerin kartı ve fiyatı olsun.
- [ ] **04 Gider dağıtım**: gider havuzları, hat / sınıf / ambalaj payları (adlar ürün kartlarıyla birebir aynı).
- [ ] **05 Ürün reçetesi**: her ürün için bir sayfa ('001', '002'...). Yeni ürünün kartı ve üretim bilgileri de buradan açılır.
- [ ] **03 Üretim adetleri**: vardiya kapasitesi ve hedef üretim.
- [ ] **06 Stokta kalan**: geçen yıldan devreden stok (ürün kartları açıldıktan sonra).
- [ ] **07 Satış geçmişi**: geçen yılın satış fiyatları.
- [ ] **08 Liste fiyatları**: Berrak ürünlerinin önceki yıllardaki liste fiyatları.
- [ ] Kontrol: **Veri Kontrolü** ekranında fiyatsız malzeme, eksik üretim bilgisi uyarılarını giderin.
- [ ] Maliyet Muhasebesi tarafı: Canias'ta reçete değiştiyse **09 Canias ürün ağacı** dökümünü yükleyin.

Sezon içinde gerektikçe: **02 Malzeme fiyat listesi** (fiyat değişince, revize gelince), **05 Ürün reçetesi** (reçete değişince).

## Her ay sonunda sırayla

- [ ] **Maliyet Muhasebesi › Dönemler › Yeni dönem aç** (açılış stoku önceki ayın sayımından devreder). O ayın SMM Excel'i hazırsa onun yerine 'SMM Excel'inden yükle' (şablonu yok, kendi Excel'iniz; aşağıya bakın).
- [ ] **Veri Girişi**'nde dönemi seçin, kaynakları yükleyin: **10 Alım ve satış** (zorunlu).
- [ ] **11 Alım iadeleri** (iade varsa).
- [ ] **12 Üretim miktarları** (zorunlu).
- [ ] **13 Sayım** (zorunlu).
- [ ] **14 Şahit numune** (varsa).
- [ ] **15 Gider mizanı** (zorunlu; 720 / 730).
- [ ] **16 Stok mizanı** (150 / 151 / 152; SMM özetindeki stok kıyası için).
- [ ] Finansman tutarını Veri Girişi'nde elle girin; 'eksik veri', 'türü boş kalem' ve açılış-devir uyarılarını giderin.
- [ ] Stok ve Envanter, Sarf Farkı ve SMM Özeti'ni kontrol edin; dönemi kapatın (kilit).
- [ ] Fiyat Çalışması tarafında ay içinde fiyat değiştiyse **02 Malzeme fiyat listesi**; istenirse **07 Satış geçmişi** (ayın satışları).

## Şablonlar

| No | Ne için | Uygulamada nereye yüklenir | Dosya | Kim doldurur | Ne sıklıkla |
|---|---|---|---|---|---|
| — | Tüm çalışma kitabı (Fiyat Çalışması) | Fiyat Çalışması › Veri Aktar › Tüm çalışma kitabı | Şablon yok: kendi Excel'iniz (aşağıda) | Muhasebe | Sezon başında |
| 01 | Satın alma fiyat listesi (malzeme kartı + bütçe fiyatı) | Fiyat Çalışması › Veri Aktar › 'Satın alma fiyat listesi' sekmesi | `11-16-2026-01-satin-alma-fiyat-listesi.xlsx` | Satın alma (muhasebe kontrol eder) | Sezon başında; yeni malzeme açılınca |
| 02 | Malzeme fiyat listesi (fiyat güncelleme / revize) | Fiyat Çalışması › Malzeme Fiyatları › 'Fiyat listesi yükle' | `11-16-2026-02-malzeme-fiyat-listesi.xlsx` | Satın alma | Gerektikçe (fiyat değişince, revize gelince) |
| 03 | Üretim adetleri (vardiya kapasitesi ve hedef üretim) | Fiyat Çalışması › Veri Aktar › 'Üretim adetleri' sekmesi | `11-16-2026-03-uretim-adetleri.xlsx` | Muhasebe (üretim planlamadan gelen değerlerle) | Sezon başında; üretim planı değişince |
| 04 | Gider dağıtım (gider havuzları, dağıtım bazları, ambalaj sınıfları) | Fiyat Çalışması › Veri Aktar › 'Gider dağıtım' sekmesi | `11-16-2026-04-gider-dagitim.xlsx` | Muhasebe | Sezon başında (bütçe); gider bütçesi revize olunca |
| 05 | Ürün reçetesi (Fiyat Çalışması ürün sayfası düzeni) | Fiyat Çalışması › Veri Aktar › 'Ürün reçetesi' sekmesi | `11-16-2026-05-urun-recetesi.xlsx` | Muhasebe (Ar-Ge / üretimden gelen reçeteyle) | Gerektikçe (yeni ürün, reçete değişikliği) |
| 06 | Stokta kalan (geçen yıldan devreden ürün stoku) | Fiyat Çalışması › Veri Aktar › 'Stokta kalan' sekmesi | `11-16-2026-06-stokta-kalan.xlsx` | Muhasebe | Sezon başında |
| 07 | Satış geçmişi (geçen yıl satış fiyatları) | Fiyat Çalışması › Satış Geçmişi › dosya seç | `11-16-2026-07-satis-gecmisi.xlsx` | Muhasebe (satış raporundan) | Sezon başında (geçen yılın tamamı); istenirse ay sonunda ek |
| 08 | Geçmiş yılların liste fiyatları (yalnız Berrak) | Fiyat Çalışması › Analiz › 'Liste çalışması' sekmesi › 'Excel'den yükle' | `11-16-2026-08-liste-fiyatlari.xlsx` | Muhasebe / satış | Sezon başında (yılda bir; önceki yılların listesi) |
| 09 | Canias ürün ağacı dökümü (kalıcı üretim reçeteleri) | Maliyet Muhasebesi › Reçeteler › 'Canias ürün ağacı dökümünü yükle' | `11-16-2026-09-canias-urun-agaci.xlsx` | Muhasebe | Gerektikçe (Canias'ta reçete değişince); her ay yeniden yüklenmez |
| 10 | SMM · Alım ve satış (HM-YM ALIŞ SATIŞ) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Alım ve satış' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-10-smm-alim-satis.xlsx` | Muhasebe (Canias alış / satış raporundan) | Her ay sonunda (zorunlu kaynak) |
| 11 | SMM · Alım iadeleri (İADELER) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Alım iadeleri' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-11-smm-iadeler.xlsx` | Muhasebe | Her ay sonunda (iade varsa) |
| 12 | SMM · Üretim miktarları (ÜRETİM) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Üretim miktarları' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-12-smm-uretim.xlsx` | Muhasebe (Canias üretim raporundan) | Her ay sonunda (zorunlu kaynak) |
| 13 | SMM · Dönem sonu sayım (DSS) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Sayım (dönem sonu stok)' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-13-smm-sayim.xlsx` | Muhasebe (sayım tutanağından) | Her ay sonunda (zorunlu kaynak) |
| 14 | SMM · Şahit numune (ŞAHİT) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Şahit numune' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-14-smm-sahit-numune.xlsx` | Muhasebe (kalite / şahit numune listesinden) | Her ay sonunda (varsa) |
| 15 | SMM · Gider mizanı (GİDER MİZAN, 720 / 730) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Gider mizanı (720 / 730)' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-15-smm-gider-mizani.xlsx` | Muhasebe (Canias mizanından) | Her ay sonunda (zorunlu kaynak) |
| 16 | SMM · Stok mizanı (STOK MİZAN, 150 / 151 / 152) | Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Stok mizanı (150 / 151 / 152)' satırı › 'Yükle' / 'Yeniden yükle' | `11-16-2026-16-smm-stok-mizani.xlsx` | Muhasebe (Canias mizanından) | Her ay sonunda |
| — | SMM dönem Excel'i | Maliyet Muhasebesi › Dönemler › SMM Excel'inden yükle | Şablon yok: kendi Excel'iniz (aşağıda) | Muhasebe | Ay sonunda, Excel'le çalışılan aylarda |

### 01 · Satın alma fiyat listesi (malzeme kartı + bütçe fiyatı)

- **Nereye:** Fiyat Çalışması › Veri Aktar › 'Satın alma fiyat listesi' sekmesi → dosya seç → Önizle → neden + geçerlilik tarihi → Uygula
- **Dosya:** `sablonlar/11-16-2026-01-satin-alma-fiyat-listesi.xlsx` · doldurulacak sayfa: 'S.ALMA BF'
- **Kim / ne sıklıkla:** Satın alma (muhasebe kontrol eder) · Sezon başında; yeni malzeme açılınca
- **Sütunlar:** Zorunlu: A Malzeme, B Açıklama, E Para Birimi, F Bütçe Birim Fiyatları. İsteğe bağlı: C Malzeme Tipi, D Stok Birimi, G Z/S, I Revize Bütçe Birim Fiyatı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'S.ALMA BF' adlı sayfa okunur; dosyada tek sayfa varsa adı ne olursa olsun o sayfa okunur. Birden çok sayfa varsa ve hiçbiri 'S.ALMA BF' değilse dosya reddedilir.
    - 1. satır başlıktır ve sırası sabittir: A Malzeme, B Açıklama, E Para..., F ...fiyat... başlıkları denetlenir (büyük/küçük ve Türkçe harf duyarsız).
    - Sütunlar SIRAYLA okunur (başlık adıyla değil): A kod, B ad, C tip, D birim, E para birimi, F fiyat, G Z/S, I revize fiyat.
    - Sistemde olmayan kod için malzeme kartı açılır; var olan kartın farkları yalnız 'kartları güncelle' işaretliyse yazılır.
    - Fiyatlar seçilen geçerlilik tarihiyle EKLENİR (eski fiyat silinmez, geçmişte kalır). Fiyatı sayı olmayan satır varsa hiçbir şey yazılmaz.
- **Sık hatalar:**
    - Fiyatı metin olarak yazmak ('18,50 TL', '18.50 ₺'): satır 'hatalı' listesine düşer ve uygula reddedilir. Hücreyi sayı yapın.
    - Başlık satırını silmek ya da sütun eklemek: 'S.ALMA BF sayfası beklenen düzen değil' hatası.
    - Kodun başında/sonunda boşluk: uygulama kırpar, ama Excel'deki VLOOKUP'lar bulamaz; kodları temiz yazın.
    - Aynı kod iki kez: son satır geçerli olur (önizlemede görünmez); tekrarları silin.
- **Boş yüklenirse:** Hata vermez; önizleme boş gelir (yazılacak bir şey yok).
- **Uygulamada 'Şablonu indir':** Veri Aktar › Satın alma fiyat listesi sekmesinin açıklama kutusuna (AktarimFormu) 'Şablonu indir'

### 02 · Malzeme fiyat listesi (fiyat güncelleme / revize)

- **Nereye:** Fiyat Çalışması › Malzeme Fiyatları › 'Fiyat listesi yükle' → dosya + geçerlilik tarihi → Önizle → neden → Uygula
- **Dosya:** `sablonlar/11-16-2026-02-malzeme-fiyat-listesi.xlsx` · doldurulacak sayfa: 'S.ALMA BF'
- **Kim / ne sıklıkla:** Satın alma · Gerektikçe (fiyat değişince, revize gelince)
- **Sütunlar:** Zorunlu: A Malzeme, F Bütçe Birim Fiyatları. İsteğe bağlı: I Revize Bütçe Birim Fiyatı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - İLK sayfa okunur (adı önemsiz); 1. satır başlık sayılır ve denetlenmez, veri 2. satırdan başlar.
    - Yalnız üç sütun okunur, SIRAYLA: A malzeme kodu, F bütçe birim fiyatı, I revize fiyat. B–E, G, H bilgi içindir.
    - Revize (I) doluysa ve F'den farklıysa geçerli fiyat I'dır; F 'ilk bütçe' olarak yanına kaydedilir.
    - Yalnız sistemde fiyatı olan ve fiyatı DEĞİŞEN kodlar yazılır. Kartı / fiyatı olmayan kodlar önizlemede 'yeni' görünür ama YAZILMAZ: onlar için şablon 01 (Veri Aktar › Satın alma fiyat listesi) kullanılır.
    - Bu dosya şablon 01 ile aynı düzendedir: aynı dosya Veri Aktar'a da yüklenebilir (orada kart bilgileri de okunur).
- **Sık hatalar:**
    - CSV ya da eski .xls yüklemek: ekran bu uzantıları seçtirse de uygulama yalnız .xlsx okur ('dosya geçerli bir .xlsx değil').
    - Fiyatı metin olarak yazmak: satır 'hatalı' listesine düşer.
    - Yeni malzemeyi bu ekrandan eklemeye çalışmak: 'yeni' satırlar yazılmaz; Veri Aktar › Satın alma fiyat listesi kullanın.
    - Sütunları kaydırmak (ör. fiyatı E'ye yazmak): fiyat F'den okunur, yanlış sütun sessizce boş sayılır.
- **Boş yüklenirse:** Hata vermez; önizleme boş gelir.
- **Uygulamada 'Şablonu indir':** Malzeme Fiyatları › 'Fiyat listesi yükle' penceresine (FiyatListesiYukle) 'Şablonu indir'

### 03 · Üretim adetleri (vardiya kapasitesi ve hedef üretim)

- **Nereye:** Fiyat Çalışması › Veri Aktar › 'Üretim adetleri' sekmesi → dosya → Önizle → neden → Uygula
- **Dosya:** `sablonlar/11-16-2026-03-uretim-adetleri.xlsx` · doldurulacak sayfa: 'Üretim Adetleri'
- **Kim / ne sıklıkla:** Muhasebe (üretim planlamadan gelen değerlerle) · Sezon başında; üretim planı değişince
- **Sütunlar:** Zorunlu: A ÜRÜN KODU, B ÜRÜN ADI, G HEDEF VARDİYALIK ÜRETİM. İsteğe bağlı: C NET SÜREDEKİ VARDİYALIK KAPASİTE, D NET SÜRE, E TOPLAM SÜREDEKİ KAPASİTE, F TOPLAM SÜRE, H ORTALAMA İŞÇİ SAYISI.
- **Uygulama nasıl okur:**
    - 'Üretim Adetleri' adlı sayfa okunur; dosyada tek sayfa varsa o sayfa okunur.
    - Başlık 2. satırdadır, 3. satır birim satırıdır (okunmaz), veri 4. satırdan başlar. 1. satır serbesttir.
    - A2 'ÜRÜN KODU', B2 'ÜRÜN ADI', G2 'HEDEF VARDİYALIK ÜRETİM' birebir denetlenir ve BÜYÜK HARF olmalıdır (İ noktalı): 'Hedef vardiyalık üretim' gibi küçük harfle yazılırsa dosya reddedilir.
    - Sütunlar SIRAYLA okunur: A kod, B ad, C net süredeki vardiyalık kapasite, D net süre, E toplam süredeki kapasite, F toplam süre, G hedef vardiyalık üretim, H ortalama işçi sayısı.
    - Sayı olmayan hücreler ('-', '#DIV/0!', metin olarak yazılmış sayı) uyarısız 0 okunur. Aynı kod iki kez varsa ilk satır alınır.
- **Sık hatalar:**
    - Başlıkları küçük harfle ya da noktasız I ile yazmak ('VARDIYALIK'): 'beklenen sütun düzeninde değil' hatası.
    - Birim satırını (3. satır) silmek: ilk ürün satırı birim satırı sanılıp atlanır.
    - Sayıları metin olarak girmek: uyarısız 0 okunur; önizlemede değerleri kontrol edin.
    - Ürün kodu ürün kartındaki kodla aynı olmalı; farklı yazılan kod ayrı satır olarak kaydedilir.
- **Boş yüklenirse:** Hata: 'Üretim Adetleri sayfasında satır yok'.
- **Uygulamada 'Şablonu indir':** Veri Aktar › Üretim adetleri sekmesi (AktarimFormu) ve Fiyat Çalışması › Üretim Adetleri sayfası başlığı

### 04 · Gider dağıtım (gider havuzları, dağıtım bazları, ambalaj sınıfları)

- **Nereye:** Fiyat Çalışması › Veri Aktar › 'Gider dağıtım' sekmesi → dosya → Önizle → neden → Uygula
- **Dosya:** `sablonlar/11-16-2026-04-gider-dagitim.xlsx` · doldurulacak sayfa: 'Gider Dağıtım'
- **Kim / ne sıklıkla:** Muhasebe · Sezon başında (bütçe); gider bütçesi revize olunca
- **Sütunlar:** Sabit hücreler: toplamlar D4, A6, D13, D18, A20, D27, D38, D49, D60, D64, D67; saniye bazları F4, F13, F18, F27; paylar C7:G9, C21:G23, A30:G37, A41:G48, A52:G59; ambalaj A70:D91.
- **Uygulama nasıl okur:**
    - 'Gider Dağıtım' adlı sayfa okunur; dosyada tek sayfa varsa o sayfa okunur.
    - Değerler SABİT HÜCRE adreslerinden okunur (tablo değil): satır / sütun eklemek ya da silmek değerleri kaydırır.
    - Düzen denetimi: D3, D12, D17, D26, D63, D66 'Gider Toplamı' ile, A69 'Ambalaj' ile başlamalı; tüm toplamlar boşsa dosya reddedilir.
    - Toplam hücresine '=49024334,97*1,35*1,3' gibi taban × çarpan formülü yazılırsa çarpanlar uygulamada ayrı ayrı düzenlenebilir kalır; düz sayı da olur. Formüllü dosyayı Excel'de kaydedip yükleyin (uygulama formülün son hesaplanan değerini okur).
    - Önizleme yalnız değişen havuzları gösterir; uygula değişen havuzları ve ambalaj tablosunu seçili çalışmaya yazar.
- **Sık hatalar:**
    - Saniye bazlı havuzda (dolum, etiket, endirekt, diğer GÜG) F hücresini boş bırakmak: uygula 'dağıtım bazı 0'dan büyük olmalı' der.
    - Sınıf / hat / ambalaj adını ürün kartındakinden farklı yazmak ('Turşu / Turşu' ile 'Turşu/Turşu'): o ürüne pay düşmez.
    - Satır eklemek: tüm değerler kayar ve yanlış havuza yazılır. Boş satırları kullanın, satır eklemeyin.
    - Formüllü kitabı Excel dışı bir araçla kaydedip yüklemek: formüllerin hesaplanmış değeri yoksa toplamlar 0 okunur.
- **Boş yüklenirse:** Hata: 'Gider Dağıtım sayfası beklenen düzen değil' (bütün toplamlar boş).
- **Uygulamada 'Şablonu indir':** Veri Aktar › Gider dağıtım sekmesi (AktarimFormu)

### 05 · Ürün reçetesi (Fiyat Çalışması ürün sayfası düzeni)

- **Nereye:** Fiyat Çalışması › Veri Aktar › 'Ürün reçetesi' sekmesi → dosya → Önizle (sayfa sayfa fark) → yazılacak sayfaları seç → neden → Uygula
- **Dosya:** `sablonlar/11-16-2026-05-urun-recetesi.xlsx` · doldurulacak sayfa: '001'
- **Kim / ne sıklıkla:** Muhasebe (Ar-Ge / üretimden gelen reçeteyle) · Gerektikçe (yeni ürün, reçete değişikliği)
- **Sütunlar:** Ürün: D6 kod, E6 ad. Reçete 7. satırdan: A seviye, D malzeme kodu (zorunlu), E ad, I miktar (zorunlu), J fire, K brüt (formül, dokunmayın), L birim, M birim fiyat (boş = fiyat listesinden). Üretim bilgileri I104, E136-E146; P118/P119 pazarlama-yönetim formülü.
- **Uygulama nasıl okur:**
    - En kolay yol: Fiyat Çalışması kitabını olduğu gibi yükleyin ve önizlemede yalnız değişen sayfaları seçin. Bu şablon, kitabı olmayan tek bir ürün için hazırlanmıştır.
    - Adı üç haneli sayı olan sayfalar ('001', '015 (2)') ürün sayfası sayılır; hiç yoksa ve dosya tek sayfalıysa o sayfa okunur.
    - Satırlar D sütunundaki ETİKETLERLE bulunur: reçete 6. satırdan 'HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI' etiketine kadardır. Etiketlerden biri eksikse sayfa 'ürün sayfası düzeninde değil' diye hatalı listesine düşer.
    - Dosyada S.ALMA BF sayfası varsa 'elle fiyat' ayrımı fiyat listesine göre yapılır (M boş = listeden). Bu şablonda o sayfa boş durur.
    - Var olan ürünün kartına ve üretim bilgilerine dokunulmaz, yalnız yeni reçete versiyonu açılır (eski versiyon geçmişte kalır). Sistemde olmayan ürün için kart ve üretim bilgileri bu sayfadan açılır.
- **Sık hatalar:**
    - S.ALMA BF sayfasını silmek ya da ürün sayfasını tek başına kaydetmek: boş birim fiyat hücreleri 'elle fiyat 0' okunur, maliyet düşük çıkar. Önizlemede 'elle fiyat' sayısı reçete satır sayısına eşitse bu olmuştur.
    - K (brüt miktar) formülünü silmek: boş K 'elle brüt miktar 0' sayılır. Formülü geri kopyalayın.
    - Dosyayı Excel'de açıp kaydetmeden (ör. başka araçla doldurup) yüklemek: K formüllerinin değeri hesaplanmamış olur.
    - D sütunundaki etiket metinlerini değiştirmek ya da satır ekleyip etiketleri reçete alanına kaydırmak.
    - Reçeteye 93'ten fazla malzeme: 100. satırdaki etiketin üstüne satır ekleyin (etiket aşağı kayar, sorun olmaz).
- **Boş yüklenirse:** Önizlemede '001' sayfası 'reçete satırı yok' diye hatalı listesinde görünür; yazılacak sayfa olmaz.
- **Uygulamada 'Şablonu indir':** Veri Aktar › Ürün reçetesi sekmesi (ReceteDosyaAktar)

### 06 · Stokta kalan (geçen yıldan devreden ürün stoku)

- **Nereye:** Fiyat Çalışması › Veri Aktar › 'Stokta kalan' sekmesi → dosya → Önizle → neden → Uygula
- **Dosya:** `sablonlar/11-16-2026-06-stokta-kalan.xlsx` · doldurulacak sayfa: 'Stokta Kalan'
- **Kim / ne sıklıkla:** Muhasebe · Sezon başında
- **Sütunlar:** Zorunlu: A urun_kodu, B stok_adet, C stok_birim_maliyet. İsteğe bağlı: D enflasyon, E uretim_adedi.
- **Uygulama nasıl okur:**
    - İLK sayfa okunur; 1. satır başlıktır. Sütunlar BAŞLIK ADIYLA bulunur (sıra serbest; büyük/küçük, Türkçe harf ve boşluk/alt çizgi farkı önemsiz).
    - Zorunlu başlıklar: urun_kodu, stok_adet, stok_birim_maliyet. İsteğe bağlı: enflasyon, uretim_adedi.
    - Ürün sistemde olmalı ve dosyada bir kez geçmeli. Hatalı satır varsa önizlemede listelenir ve hiçbir satır yazılmaz.
    - Kayıtlar seçili çalışmaya yazılır; yeni çalışma kopyalanırken taşınmaz.
    - Uygulamadaki 'Şablonu indir' bağlantısı aynı başlıkları verir (Veri Aktar › Stokta kalan).
- **Sık hatalar:**
    - Enflasyonu yüzde sayı olarak yazmak (40): %4000 sayılır ve reddedilir; 0,40 ya da %40 yazın.
    - stok_adet > 0 iken birim maliyeti boş bırakmak.
    - Ürün kodunu ürün kartından farklı yazmak: 'ürün bulunamadı'.
    - Başlık satırı olmadan veri yapıştırmak: 'zorunlu sütun bulunamadı'.
- **Boş yüklenirse:** Hata vermez; önizleme 0 satır gösterir.
- **Uygulamada 'Şablonu indir':** Var (Veri Aktar › Stokta kalan › 'Şablonu indir'); bu dosyayla değiştirilebilir

### 07 · Satış geçmişi (geçen yıl satış fiyatları)

- **Nereye:** Fiyat Çalışması › Satış Geçmişi › dosya seç → Yükle (aynı kart: Veri Aktar › 'Satış geçmişi' sekmesi)
- **Dosya:** `sablonlar/11-16-2026-07-satis-gecmisi.xlsx` · doldurulacak sayfa: 'Satış Geçmişi'
- **Kim / ne sıklıkla:** Muhasebe (satış raporundan) · Sezon başında (geçen yılın tamamı); istenirse ay sonunda ek
- **Sütunlar:** Zorunlu: A urun_kodu, B musteri, C tarih, D fiyat, E para_birimi, F adet.
- **Uygulama nasıl okur:**
    - İLK sayfa okunur; 1. satır başlıktır. Sütunlar BAŞLIK ADIYLA bulunur (sıra serbest; 'Ürün Kodu', 'urun_kodu', 'URUNKODU' aynı).
    - Altı başlık da zorunludur: urun_kodu, musteri, tarih, fiyat, para_birimi, adet. .csv (; ya da ,) da kabul edilir.
    - Tarih: Excel tarih hücresi, YYYY-AA-GG ya da GG.AA.YYYY. Sayı: Excel sayı hücresi, 1234.56, 1234,56 ya da 1.234,56.
    - Tek işlem: herhangi bir satır hatalıysa hiçbir satır eklenmez, hatalar satır numarasıyla listelenir. En çok 20.000 satır.
    - Yükleme ekler (var olanın yerine geçmez): aynı dosyayı iki kez yüklemek satırları ikiler.
    - Uygulamadaki 'Şablonu indir' bağlantısı aynı başlıkları verir.
- **Sık hatalar:**
    - Belirsiz sayı: '2.000' (nokta + 3 hane, virgülsüz) ve '1,234.56' reddedilir; Excel sayı hücresi kullanın.
    - Para birimini 'TRY' ya da '₺' yazmak: TL, USD, EUR, GBP, CHF, RUB, ZAR'dan biri olmalı.
    - Ürün kodu sistemde yok: 'ürün bulunamadı' (önce ürün kartı açılmalı).
    - Aynı dosyayı iki kez yüklemek: satırlar ikilenir; yanlış yüklemede Satış Geçmişi listesinden silin.
- **Boş yüklenirse:** Hata: 'dosyada veri satırı yok'.
- **Uygulamada 'Şablonu indir':** Var (Satış Geçmişi ve Veri Aktar › Satış geçmişi › 'Şablonu indir'); bu dosyayla değiştirilebilir

### 08 · Geçmiş yılların liste fiyatları (yalnız Berrak)

- **Nereye:** Fiyat Çalışması › Analiz › 'Liste çalışması' sekmesi › 'Excel'den yükle' → dosya → Yükle
- **Dosya:** `sablonlar/11-16-2026-08-liste-fiyatlari.xlsx` · doldurulacak sayfa: 'Liste Fiyatları'
- **Kim / ne sıklıkla:** Muhasebe / satış · Sezon başında (yılda bir; önceki yılların listesi)
- **Sütunlar:** Zorunlu: A urun_kodu, B yil, C liste_fiyati. İsteğe bağlı: D birim_maliyet, E pazar.
- **Uygulama nasıl okur:**
    - İLK sayfa okunur; 1. satır başlıktır. Sütunlar BAŞLIK ADIYLA bulunur (satış geçmişi okuyucusuyla aynı kurallar). .csv de olur.
    - Zorunlu başlıklar: urun_kodu, yil, liste_fiyati. İsteğe bağlı: birim_maliyet, pazar.
    - Yalnız Berrak markalı ürünler kabul edilir (ürün kartında marka: Berrak).
    - Aynı ürün + yıl + pazar yeniden yüklenirse eski değerin yerine geçer. Herhangi bir satır hatalıysa hiçbir satır yazılmaz.
    - Uygulamadaki 'Şablonu indir' bağlantısı aynı başlıkları verir.
- **Sık hatalar:**
    - Berrak olmayan ürün: 'liste fiyatı yalnız Berrak markalı ürünlere girilir'.
    - Pazarı 'İhracat' yazmak: yalnız Yurtiçi, Yurtdışı ya da boş (boş = Yurtiçi).
    - Liste fiyatını KDV dahil girmek: liste fiyatları KDV hariçtir.
    - Aynı ürün, yıl ve pazar dosyada iki kez: satır hatası.
- **Boş yüklenirse:** Hata: 'dosyada veri satırı yok'.
- **Uygulamada 'Şablonu indir':** Var (Liste çalışması › Excel'den yükle › 'Şablonu indir'); bu dosyayla değiştirilebilir

### 09 · Canias ürün ağacı dökümü (kalıcı üretim reçeteleri)

- **Nereye:** Maliyet Muhasebesi › Reçeteler › 'Canias ürün ağacı dökümünü yükle' → dosya → Önizle → Yükle
- **Dosya:** `sablonlar/11-16-2026-09-canias-urun-agaci.xlsx` · doldurulacak sayfa: 'TBLRESULT'
- **Kim / ne sıklıkla:** Muhasebe · Gerektikçe (Canias'ta reçete değişince); her ay yeniden yüklenmez
- **Sütunlar:** Zorunlu: A Alternatif Numarası, B Malzeme Kodu, C Malzeme Açıklaması, D Satır No, E Ürün Ağacı Kalem Tipi, F Tüketim Malzeme Kodu, G Tüketim Malzeme Adı, H Tüketim Miktarı, I Tüketim Birimi, J Fire Oranı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - Canias'tan böyle alınır: ürün ağacı raporu (sonuç tablosu 'TBLRESULT') Excel'e aktarılır; başlıklar bu şablondakiyle aynıdır. Canias dökümünü olduğu gibi yükleyebilirsiniz; bu şablon elle hazırlanacak ya da düzeltilecek dökümler içindir.
    - İLK sayfa okunur; 1. satır başlıktır. Sütunlar BAŞLIK ADIYLA bulunur (sıra serbest) ama başlık metni BİREBİR aynı olmalı (büyük/küçük harf ve Türkçe harf dahil; 'Fire Oranı' ≠ 'Fire Orani').
    - Zorunlu başlıklar: Alternatif Numarası, Malzeme Kodu, Malzeme Açıklaması, Satır No, Ürün Ağacı Kalem Tipi, Tüketim Malzeme Kodu, Tüketim Malzeme Adı, Tüketim Miktarı, Tüketim Birimi, Fire Oranı. 'Fireli Miktar' okunmaz.
    - Tüketim Malzeme Kodu boş satır ürün başlığıdır, atlanır. Aşama koddan bulunur: 02 ile başlayan → 40 (üretim hattı), 03 → 50 (etiketleme), diğerleri → 20.
    - Yükleme TÜM kalıcı reçeteleri dosyadakilerle değiştirir; ürün başına alternatif seçimleri ve elle düzeltilmiş ürünler korunur.
- **Sık hatalar:**
    - Alternatif numarasını sayı olarak girmek: Excel '00'ı 0 yapar ve varsayılan alternatif '00' bulunamaz. Sütun metin biçimlidir; '00' yazın.
    - Fire oranını oran olarak yazmak (0,02): yüzde beklenir (2 = %2); 0,02 yazılırsa %0,02 sayılır.
    - Miktarı metin olarak yazmak ('1,05' metin): uyarısız 0 okunur. Sayı hücresi kullanın.
    - Başlıkları Türkçe harfsiz ya da farklı yazmak: 'Canias ürün ağacı dökümü bekleniyor; sütun eksik'.
- **Boş yüklenirse:** Hata: 'dosyada reçete satırı yok'.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Reçeteler › 'Canias ürün ağacı dökümünü yükle' kartına (SmmReceteler)

### 10 · SMM · Alım ve satış (HM-YM ALIŞ SATIŞ)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Alım ve satış' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-10-smm-alim-satis.xlsx` · doldurulacak sayfa: 'HM-YM ALIŞ SATIŞ'
- **Kim / ne sıklıkla:** Muhasebe (Canias alış / satış raporundan) · Her ay sonunda (zorunlu kaynak)
- **Sütunlar:** Zorunlu: B Malzeme(Sınıf)Kodu, G Giriş Miktarı, K Tutar (TL), T Hareket Türü. İsteğe bağlı: C Malzeme Açıklaması, F Birim, L Çıkış Miktarı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'HM-YM ALIŞ SATIŞ' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'Malzeme(Sınıf)Kodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - Kod B sütunundadır. Okunan: B kod, C ad, F birim, G giriş (alım) miktarı, K tutar (TL), L çıkış miktarı, T hareket türü.
    - Aynı kodun satırları toplanır. T 'Satış' ise L satılan miktara eklenir; diğer satırlarda G ve K alıma eklenir.
    - Tutar (K) TL'dir: dövizli alımda kur çevrimini satırda yapın.
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Başlığı 'Malzeme (Sınıf) Kodu' (boşluklu) yazmak: bu kaynakta boşluksuz 'Malzeme(Sınıf)Kodu' aranır ('başlık bulunamadı').
    - Satış satırında T'yi 'SATIŞ' ya da 'Satis' yazmak: yalnız birebir 'Satış' satış sayılır.
    - Tutarı döviz olarak bırakmak: K TL kabul edilir, ortalama maliyet bozulur.
    - Sütun eklemek / silmek: miktar ve tutar yanlış sütundan okunur.
- **Boş yüklenirse:** DİKKAT: hata vermez. Yükleme başarılı görünür ve bu kaynağın dönemdeki değerlerini SIFIRLAR (0 kalem). Yanlışlıkla boş ya da yanlış dosya yüklenirse doğru dosyayı yeniden yükleyin.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Alım ve satış' satırının yanına (SmmVeri KaynakSatiri)

### 11 · SMM · Alım iadeleri (İADELER)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Alım iadeleri' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-11-smm-iadeler.xlsx` · doldurulacak sayfa: 'İADELER'
- **Kim / ne sıklıkla:** Muhasebe · Her ay sonunda (iade varsa)
- **Sütunlar:** Zorunlu: A Malzeme (Sınıf) Kodu, H İade Miktarı, I İade Tutarı. İsteğe bağlı: B Malzeme Açıklaması, E Birim. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'İADELER' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'Malzeme (Sınıf) Kodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - Kod A sütunundadır. Okunan: A kod, B ad, E birim, H iade miktarı, I iade tutarı (TL). Aynı kodun satırları toplanır.
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Başlığı boşluksuz 'Malzeme(Sınıf)Kodu' yazmak: bu kaynakta BOŞLUKLU 'Malzeme (Sınıf) Kodu' aranır.
    - İade miktarını eksi yazmak: iade zaten düşülür; artı yazın.
    - Tutar sütununu (I) boş bırakmak: iade tutarı 0 sayılır.
- **Boş yüklenirse:** DİKKAT: hata vermez. Yükleme başarılı görünür ve bu kaynağın dönemdeki değerlerini SIFIRLAR (0 kalem). Yanlışlıkla boş ya da yanlış dosya yüklenirse doğru dosyayı yeniden yükleyin.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Alım iadeleri' satırının yanına (SmmVeri KaynakSatiri)

### 12 · SMM · Üretim miktarları (ÜRETİM)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Üretim miktarları' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-12-smm-uretim.xlsx` · doldurulacak sayfa: 'ÜRETİM'
- **Kim / ne sıklıkla:** Muhasebe (Canias üretim raporundan) · Her ay sonunda (zorunlu kaynak)
- **Sütunlar:** Zorunlu: A MalzemeKodu, O Üretim Miktarı. İsteğe bağlı: B Malzeme Açıklaması. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'ÜRETİM' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'MalzemeKodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - Kod A sütunundadır. Okunan: A kod, B ad, O üretim miktarı (15. sütun). Aynı kodun satırları toplanır.
    - Hem mamul (03...) hem yarı mamul (02...) hem ara mamul (01...) üretimleri yazılır.
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Üretim miktarını C ya da başka bir sütuna yazmak: yalnız O sütunu okunur (C-N boş kalabilir).
    - Başlığı 'Malzeme Kodu' (boşluklu) yazmak: bu kaynakta boşluksuz 'MalzemeKodu' aranır.
    - O sütununa yıl içi toplamı yazmak: SMM Excel'inde bu sütun 'yıl içi toplam' diye anılıyor; dönem hesabında ayın üretimi olarak kullanılır (muhasebeyle teyit edilmeli, rehberdeki açık soruya bakın).
- **Boş yüklenirse:** DİKKAT: hata vermez. Yükleme başarılı görünür ve bu kaynağın dönemdeki değerlerini SIFIRLAR (0 kalem). Yanlışlıkla boş ya da yanlış dosya yüklenirse doğru dosyayı yeniden yükleyin.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Üretim miktarları' satırının yanına (SmmVeri KaynakSatiri)

### 13 · SMM · Dönem sonu sayım (DSS)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Sayım (dönem sonu stok)' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-13-smm-sayim.xlsx` · doldurulacak sayfa: 'DSS'
- **Kim / ne sıklıkla:** Muhasebe (sayım tutanağından) · Her ay sonunda (zorunlu kaynak)
- **Sütunlar:** Zorunlu: A StokKartıKodu, C Sayım Miktarı. İsteğe bağlı: B StokKartıAdı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'DSS' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'StokKartıKodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - Kod A sütunundadır. Okunan: A kod, B ad, C sayım miktarı. Aynı kodun satırları toplanır.
    - Sayımda olmayan kalemin sayımı 0 olur (yükleme o kaynağı baştan yazar).
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Başlığı 'Stok Kartı Kodu' (boşluklu) yazmak: birebir 'StokKartıKodu' aranır.
    - Sayım miktarını D ya da E sütununa yazmak: yalnız C okunur.
    - Sıfır sayımlı kalemi listeden çıkarmak sorun değildir; ama yanlışlıkla bir kalemi atlamak onu 0 yapar.
- **Boş yüklenirse:** DİKKAT: hata vermez. Yükleme başarılı görünür ve bu kaynağın dönemdeki değerlerini SIFIRLAR (0 kalem). Yanlışlıkla boş ya da yanlış dosya yüklenirse doğru dosyayı yeniden yükleyin.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Sayım (dönem sonu stok)' satırının yanına (SmmVeri KaynakSatiri)

### 14 · SMM · Şahit numune (ŞAHİT)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Şahit numune' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-14-smm-sahit-numune.xlsx` · doldurulacak sayfa: 'ŞAHİT'
- **Kim / ne sıklıkla:** Muhasebe (kalite / şahit numune listesinden) · Her ay sonunda (varsa)
- **Sütunlar:** Zorunlu: A StokKodu, J Toplam Miktar. İsteğe bağlı: B StokAdı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'ŞAHİT' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'StokKodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - Kod A sütunundadır. Okunan: A kod, B ad, J toplam miktar (10. sütun, sayı hücresi). Aynı kodun satırları toplanır.
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Miktarı C-I sütunlarına yazmak: yalnız J okunur.
    - J'yi metin olarak yazmak: o satır atlanır (sayı hücresi değilse okunmaz).
    - Başlığı 'Stok Kodu' yazmak: birebir 'StokKodu' aranır.
- **Boş yüklenirse:** DİKKAT: hata vermez. Yükleme başarılı görünür ve bu kaynağın dönemdeki değerlerini SIFIRLAR (0 kalem). Yanlışlıkla boş ya da yanlış dosya yüklenirse doğru dosyayı yeniden yükleyin.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Şahit numune' satırının yanına (SmmVeri KaynakSatiri)

### 15 · SMM · Gider mizanı (GİDER MİZAN, 720 / 730)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Gider mizanı (720 / 730)' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-15-smm-gider-mizani.xlsx` · doldurulacak sayfa: 'GİDER MİZAN'
- **Kim / ne sıklıkla:** Muhasebe (Canias mizanından) · Her ay sonunda (zorunlu kaynak)
- **Sütunlar:** Zorunlu: A Hesap Kodu, G Bakiye. İsteğe bağlı: B Hesap Adı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'GİDER MİZAN' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'Hesap Kodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - A hesap kodu, G bakiye. Yalnız 3 haneli hesaplar (710, 720, 730, 760, 770...) okunur; alt hesaplar (720.01) atlanır.
    - 720 ve / veya 730 bulunmazsa dosya reddedilir. Aynı hesap iki kez varsa ilk satır alınır.
    - 720 / 730 aşama işçilik ve genel üretim gideri dağıtımına gider; Veri Girişi'nde elle de düzeltilebilir.
    - Yükleme bu mizanın elle girilmiş satırlarını SİLER (ekran önce sorar).
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Hesap kodunu sayı olarak yazmak sorun değildir (720), ama alt hesapları sayı yazarsanız 720.10 → 720.1 olur; sütun metin biçimlidir.
    - Bakiyeyi G dışında bir sütuna yazmak: yalnız G okunur.
    - Yalnız alt hesapları (720.01, 720.02) vermek: 3 haneli ana hesap satırı gerekir.
- **Boş yüklenirse:** Hata: 'gider mizanında 720 / 730 bulunamadı'.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Gider mizanı (720 / 730)' satırının yanına (SmmVeri KaynakSatiri)

### 16 · SMM · Stok mizanı (STOK MİZAN, 150 / 151 / 152)

- **Nereye:** Maliyet Muhasebesi › Veri Girişi › (dönemi seçin) › 'Stok mizanı (150 / 151 / 152)' satırı › 'Yükle' / 'Yeniden yükle'
- **Dosya:** `sablonlar/11-16-2026-16-smm-stok-mizani.xlsx` · doldurulacak sayfa: 'STOK MİZAN'
- **Kim / ne sıklıkla:** Muhasebe (Canias mizanından) · Her ay sonunda
- **Sütunlar:** Zorunlu: A Hesap Kodu, G Bakiye. İsteğe bağlı: B Hesap Adı. Diğer sütunlar okunmaz (yer tutucu).
- **Uygulama nasıl okur:**
    - 'STOK MİZAN' adlı sayfa okunur; yoksa İLK sayfa okunur (SMM Excel'inin tamamı da, tek sayfalık rapor da olur).
    - Başlık satırı ilk 8 satırda 'Hesap Kodu' hücresiyle bulunur (BİREBİR, boşluk ve büyük/küçük harf dahil); veri onun altından başlar.
    - Diğer sütunlar SIRAYLA okunur (başlık metni önemsiz): sütun yerlerini değiştirmeyin.
    - A hesap kodu, B hesap adı, G bakiye. Yalnız '15' ile başlayan hesaplar okunur (150.01, 151.01, 152.01...).
    - 15x hesabı yoksa dosya reddedilir. Mizan, SMM özetinde stok değerlemesiyle karşılaştırılır.
    - Yükleme bu mizanın elle girilmiş satırlarını SİLER (ekran önce sorar).
    - Sayılar Excel sayı hücresi olmalı: metin olarak yazılmış sayı ('1.234,56') uyarısız 0 okunur.
    - Yükleme o kaynağın dönemdeki eski verisinin YERİNE geçer (yeniden yüklemek güvenlidir). Kilitli (kapatılmış) döneme yüklenemez.
- **Sık hatalar:**
    - Hesap kodunu sayı yazmak: 150.10 → 150.1 olur; sütun metin biçimlidir.
    - Toplam satırını da '15' ile başlayan kodla yazmak: toplam ikinci kez sayılır. Toplam satırı koymayın ya da A'yı boş bırakın.
    - Bakiyeyi G dışında bir sütuna yazmak.
- **Boş yüklenirse:** Hata: 'stok mizanında 15x hesabı bulunamadı'.
- **Uygulamada 'Şablonu indir':** Maliyet Muhasebesi › Veri Girişi › 'Stok mizanı (150 / 151 / 152)' satırının yanına (SmmVeri KaynakSatiri)

## Şablonu olmayan iki yükleme: kendi Excel'inizi olduğu gibi yükleyin

### Tüm çalışma kitabı (Fiyat Çalışması)

**Nereye:** Fiyat Çalışması › Veri Aktar › 'Tüm çalışma kitabı' → dosya, sezon adı (YYYY-YYYY), çalışma adı, tür (Fiyat çalışması / Gerçekleşen) → Yükle. 'Mevcut çalışmayı tamamla' seçilirse yeni çalışma açılmaz, yalnız eksikler yazılır, var olan hiçbir şey ezilmez.

Muhasebenin kendi Fiyat Çalışması kitabı olduğu gibi yüklenir. Uygulamanın aradığı sayfalar ve hücreler:

| Sayfa | Zorunlu mu | Uygulamanın okuduğu |
|---|---|---|
| S.ALMA BF | Evet | 1. satır başlık; A kod, B ad, C tip, D birim, E para birimi, F bütçe fiyatı, G Z/S, I revize fiyat (şablon 01 ile aynı düzen) |
| Gider Dağıtım | Evet | Sabit hücreler (şablon 04 ile aynı): D4/F4, A6 + C7:G9, D13/F13, D18/F18, A20 + C21:G23, D27/F27, A30:G37 + D38, A41:G48 + D49, A52:G59 + D60, D64, D67, ambalaj A70:D91. Toplam formülü '=taban*çarpan' kalıbındaysa çarpanlar ayrı saklanır |
| Ürün sayfaları ('001', '002'...) | En az bir | Şablon 05 düzeni; satırlar D sütunundaki etiketlerle bulunur. '(2)' ekli sayfalar bu yüklemede atlanır. D6 boşsa ürüne geçici 'SAYFA-001' kodu verilir |
| İlk ürün sayfası | Evet | Genel parametreler: F148 enflasyon, E150:F155 kurlar, I124:K128 faiz ve stok süresi, L145:L147 teklif kâr oranları, 'Maliyet Sapma' satırının F hücresi (bu etiket ZORUNLU), 'Süzme Miktar'dan sonraki satırın G hücresi (satış fiyatı notu). Diğer sayfalarda farklı olan parametreler o ürüne özel yazılır |
| Üretim Adetleri | Hayır | Şablon 03 düzeni; sayfa yoksa kapasite boş kalır |
| Diğer sayfalar (Teklif Kapak vb.) | — | Okunmaz |

Kritik: kitap Excel'de kaydedilmiş olmalı (uygulama formüllerin son hesaplanan değerini okur). Kitabın beklenen yapıda olmaması 'çalışma kitabı beklenen yapıda değil' hatası verir ve hiçbir şey yazılmaz. Uydurma örnek kitap: `test-dongusu/excel/11-16-2026-fiyat-calismasi-butce.xlsx` (gerçekleşen için `11-16-2026-fiyat-calismasi-gerceklesen.xlsx`). Bu klasör test döngüsü için yeniden üretilir; dosya adları değişirse aynı klasördeki 'fiyat-calismasi' dosyalarına bakın.

### SMM dönem Excel'i (Maliyet Muhasebesi)

**Nereye:** Maliyet Muhasebesi › Dönemler › 'SMM Excel'inden yükle (isteğe bağlı)' → dosya → yıl / ay (dosya adında '09-2026' gibi geçiyorsa oradan bulunur) → Yükle. Dönem zaten yüklüyse üzerine yazma onayı istenir; kilitli döneme yüklenemez.

Muhasebenin aylık SMM Excel'i olduğu gibi yüklenir. Veri sayfalarında başlık 2. satırda, veri 3. satırdan başlar (aylık kaynak şablonları 10-16 da bu düzendedir; sayfaları SMM Excel'ine kopyalanabilir). Aranan sayfalar:

| Sayfa | Zorunlu mu | Uygulamanın okuduğu (3. satırdan) |
|---|---|---|
| DBS | Evet | Dönem başı stok: A kod, B ad, C miktar, D tutar |
| HM-YM ALIŞ SATIŞ | Evet | Şablon 10: B kod, C ad, F birim, G giriş miktarı, K tutar, L çıkış miktarı, T hareket türü ('Satış') |
| DSS | Evet | Şablon 13: A kod, B ad, C sayım miktarı; E sayım tutarı (Excel'le kıyas için) |
| TABLO | Evet | J1 finansman tutarı; B kod; D, H, O, U, V, W Excel'in kendi stok tablosu değerleri (uygulamanın hesabıyla kıyaslanır) |
| ENVANTER | Hayır | A kod, B ad, C birim, D malzeme türü, E mizan kodu; P sütunundaki formülün baktığı '20 KOD' / '40 KOD' / '50 KOD' sayfası üretim aşamasını belirler |
| İADELER, ÜRETİM, ŞAHİT | Hayır | Şablon 11, 12, 14 ile aynı sütunlar |
| GİDER MİZAN | Hayır | Şablon 15: 3 haneli hesaplar, G bakiye (720 / 730 aşama dağıtımına gider) |
| STOK MİZAN | Hayır | Şablon 16: 15x hesaplar, G bakiye; J2 mizan (fiş) tarihi |
| 20 KOD, 40 KOD, 50 KOD | Hayır | Aşama reçeteleri. 1. satırda dağıtım havuzları (20 KOD: P1, S1 · 40 KOD: P1, U1, Z1, AC1 · 50 KOD: P1, U1). 3. satırdan A ana kod, B ana ad, C ana miktar, D ana birim, E malzeme kodu, F ad, G miktar, H birim; fire oranı 20 KOD X, 40 KOD AF, 50 KOD Z; Excel'in aşama birim maliyeti 20 KOD U, 40 / 50 KOD W |
| 51 | Hayır | Üretim süreleri: B mamul, C yarı mamul, D ad, J vardiya üretim, L dolum işçi, M etiket işçi, P-S dolum / etiket saniyeleri |

Kritik: DBS, HM-YM ALIŞ SATIŞ, DSS ve TABLO sayfalarından biri eksikse dosya reddedilir ('SMM Excel'inde beklenen sayfalar yok'). Uydurma örnek kitap: `test-dongusu/excel/11-16-2026-smm-ekim-2026.xlsx`; aylık kaynak örnekleri aynı klasörde `11-16-2026-smm-kasim-2026-*.xlsx` (klasör test döngüsü için yeniden üretilir; adlar değişirse 'smm' ile başlayan dosyalara bakın).

## Muhasebeye açık sorular

- **ÜRETİM sayfası O sütunu:** uygulama bu sütunu dönemin (ayın) üretim miktarı olarak kullanıyor; SMM Excel'indeki açıklamada 'yıl içi toplam' deniyor. Aylık kaynakta ayın üretimi mi, yıl başından toplam mı yazılacak? Şablon 12 şimdilik 'dönemde üretilen miktar' diyor.
- **Üretim Adetleri 'NET SÜRE' / 'TOPLAM SÜRE' birimi:** şablonda saat (vardiya başına) varsayıldı; Excel'inizdeki birimle teyit edin.

## Doğrulama

Her şablon uygulamanın kendi okuyucularıyla (sunucu açılmadan, bellek içi veritabanında) üç biçimde denendi: şablon boşken, yalnız Örnek sayfası tek sayfalık dosya olarak ve doldurulacak sayfaya örnek yazılmış kitap (Örnek / Açıklama sayfaları dosyadayken; uygula / yükle dahil). 16 şablonun 16'sı hatasız okundu ve satır sayıları örnekle aynı çıktı. Ayrıntı: `sablonlar/11-16-2026-dogrulama-sonucu.txt`. Yeniden denemek için proje kökünden: `.venv\Scripts\python.exe sablonlar\11-16-2026-dogrula.py`.

Bir uyarı: ürün reçetesi (05) şablonunun yalnız Örnek sayfası tek başına yüklenirse 7 satırın 7'si 'elle fiyat' sayıldı (boş birim fiyat = 0). Bu yüzden şablonda boş 'S.ALMA BF' sayfası durur; silinmemeli.
