# Uçtan uca test senaryosu: Fiyat Çalışması ve Maliyet Muhasebesi

Bu senaryo uygulamayı baştan sona gerçek bir kullanıcı gibi denemek içindir. Ayrı bir test veritabanı (`veri\test-dongusu.db`) ve uydurma test verisi kullanılır. Gerçek veritabanına (`veri\fiyat.db`) ve 8000 portundaki uygulamaya dokunulmaz.

**Beklenen sayılar nereden geliyor?** Yükleme yapan ve sayı içeren adımlar aynı dosyalarla ve aynı sırayla API üzerinden gerçekten koşturuldu (kuru koşu: `test-dongusu\kuru_kosu.py`, 16.11.2026). Beklenen sayılar bu koşudan alındı, tahmin değil. Her adımda iki etiketten biri var:
- **API ✓**: sayı kuru koşuda doğrulandı.
- **Ekran ☐**: tıklama ve görünüm kuru koşuda denenmedi; ilk kez sizin denemeniz doğrulayacak.

Sayılar adımlar **bu sırayla** yapılırsa tutar. Bir adımı atlarsanız ya da farklı değer girerseniz sonraki sayılar değişir; o zaman sapmayı "Not" alanına yazın. Ekranda 2 haneye yuvarlanmış görünen tutarlarda ±0,01 fark normaldir.

## Ne denenecek, ne kadar sürer (özet)

| Bölüm | Ne denenir | Tahmini süre |
|---|---|---|
| 0. Hazırlık | Test ortamını açma, ilk Genel Direktör, 3 kullanıcı (Muhasebe, Satın alma, İzleyici) | 15 dk |
| 1. Fiyat Çalışması kurulumu | Tüm kitabı yükleme, içe aktarma özeti, Genel Bakış, Veri Kontrolü, gider havuzları | 20 dk |
| 2. Günlük işler | Düzenleme kilidi, fiyat listesi ve tek fiyat (büyük değişiklik uyarısı), reçete değişikliği, elle hücre, formül ipucu, katlama, klavye, Kaydet + neden, geçmiş hesaplar, Veri Aktar sekmeleri, stokta kalan | 70 dk |
| 3. Teklif | Tur açma, durum, süzgeçler, Teklif Kapak, kayıtlı hesabı yazdırma | 15 dk |
| 4. Analiz | Ya olursa, zam etkisi, kur riski, kârlılık haritası, marjı koruyan fiyat, fiyat eğilimi, önemli malzemeler, liste çalışması | 30 dk |
| 5. Kıyasla | Gerçekleşen senaryosu, Bütçe vs Gerçekleşen | 15 dk |
| 6. Yönetim | Yönetim Özeti, toplu maliyet kartları, Değişiklik Günlüğü, roller, çalışma kilidi | 25 dk |
| 7. Maliyet Muhasebesi | Ekim dönemi (yükleme → SMM özeti → bütçe kıyası → kapanış), Canias reçeteleri, Kasım yeni dönem, devir, kilit kuralları | 75 dk |
| 8. Yedek ve geri yükleme | Test veritabanının yedeği ve geri yüklenmesi | 15 dk |
| 9. Temizlik | Test ortamını silme | 5 dk |
| **Toplam** | | **yaklaşık 4,5 saat** (iki oturuma bölünebilir: 0-4 ve 5-9) |

**Test dosyaları** (`test-dongusu\excel\`, hepsi uydurma veridir; yeniden üretmek için `.venv\Scripts\python.exe test-dongusu\uret.py`):

| Dosya | Ne için | Adım |
|---|---|---|
| `11-16-2026-fiyat-calismasi-butce.xlsx` | Tüm çalışma kitabı: 7 ürün sayfası (001-007, ayrıca atlanacak "001 (2)"), S.ALMA BF (32 malzeme), Gider Dağıtım, Üretim Adetleri, Teklif Kapak | 1.2 |
| `11-16-2026-fiyat-listesi-revize.xlsx` | Revize fiyat listesi (8 fiyat %10-40 arttı; Streç Film %40) | 2.3 |
| `11-16-2026-satin-alma-yeni-malzeme.xlsx` | Fiyatsız 2 malzemeye fiyat + 1 yeni malzeme kartı | 2.6 |
| `11-16-2026-uretim-adetleri.xlsx` | 2 hedef adet değişikliği + kartı olmayan 1 kod | 2.12 |
| `11-16-2026-gider-dagitim.xlsx` | Elektrik havuzuna 1,15 çarpanı, 720 ml üretim adedi %10 düşük | 2.13 |
| `11-16-2026-urun-recetesi-004.xlsx` | Tek ürün sayfası (Domates Sos): 1 satır değişti, 1 çıktı, 1 eklendi | 2.14 |
| `11-16-2026-satis-gecmisi.xlsx` | 255 satış satırı (Haziran 2025 - Ekim 2026) | 2.15 |
| `11-16-2026-stokta-kalan.xlsx` | 3 ürünün geçen yıldan kalan stoku | 2.16 |
| `11-16-2026-liste-fiyatlari-gecmis.xlsx` | Berrak ürünlerinin 2023-2025 liste fiyatları (18 satır) | 4.8 |
| `11-16-2026-fiyat-calismasi-gerceklesen.xlsx` | Aynı ürünler, gerçekleşen fiyat/kur/gider | 5.1 |
| `11-16-2026-smm-ekim-2026.xlsx` | Ekim 2026 tam SMM Excel'i (ENVANTER, DBS, alış, iade, üretim, sayım, şahit, TABLO, 20/40/50 KOD, 51, mizanlar) | 7.1 |
| `11-16-2026-smm-receteler-canias.xlsx` | Canias ürün ağacı dökümü (14 ürün, 63 satır) | 7.15 |
| `11-16-2026-smm-kasim-2026-*.xlsx` (7 dosya) | Kasım aylık kaynakları: alım-satış, iadeler, üretim, sayım, şahit numune, gider mizanı, stok mizanı | 7.17 |

**Kodlar:** malzemeler `99.xx.xxx`; ürünler `03.99.00x` (mamul), `02.99.00x` (dolu kavanoz yarı mamulü), `01.99.00x` (ara mamul / salamura). Ürün kodlarının 01/02/03 ile başlaması zorunlu: Canias reçetelerinde aşama koddan bulunur (01 → 20, 02 → 40, 03 → 50).

---

## 0. Hazırlık

**0.1 Test ortamını açın** · Windows Gezgini
- Yapın: `test-dongusu\11-16-2026-test-ortamini-ac.bat` dosyasına çift tıklayın. 8000'deki asıl uygulama açık kalabilir.
- Beklenen: küçültülmüş "Fiyat Calismasi TEST Sunucusu (8047)" penceresi açılır. Test veritabanı yoksa siyah pencerede "Genel Direktör hesabı açıldı. kullanıcı adı: direktor, geçici şifre: …" yazar. Şifreyi not edip bir tuşa basın. Tarayıcı `http://localhost:8047` adresinde açılır. `veri\test-dongusu.db` dosyası oluşur. Başlatıcının bir kopyası 8048'de denendi.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**0.2 İlk giriş** · Giriş ekranı
- Yapın: Kullanıcı adı `direktor` ve geçici şifreyle "Giriş yap". "Hoş geldiniz" ekranında yeni şifreyi iki kez yazın (en az 8 karakter) ve "Şifreyi kaydet" deyin.
- Beklenen: ana sayfa açılır. Şifre değiştirilmeden yapılan her kayıt "önce kendi şifrenizi belirleyin" hatası verir. **API ✓** (kod `sifre_degismeli`)
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**0.3 Kullanıcıları açın** · Yönetim › Kullanıcılar
- Yapın: "Yeni kullanıcı" ile üç kullanıcı ekleyin:
  - `muhasebe1`, rol Muhasebe
  - `satinalma1`, rol Satın alma
  - `izleyici1`, rol İzleyici

  Geçici şifreleri not edin. Her biriyle ayrı bir tarayıcı profilinde (ya da gizli pencerede) bir kez girip şifre belirleyin.
- Beklenen: tabloda 4 kullanıcı görünür. Durum önce "İlk giriş bekleniyor", şifre belirlenince "Aktif" olur. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

> 1-7. bölümlerdeki adımları, aksi yazılmadıkça **muhasebe1** ile yapın.

## 1. Fiyat Çalışması kurulumu

**1.1 Boş başlangıç** · Ana Sayfa
- Beklenen: hiç çalışma yok; üst çubuktaki Senaryo seçici boş. Sayfalar hata vermeden boş durum gösterir (ne yazdığını Not'a geçirin). **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.2 Tüm çalışma kitabını yükleyin** · Veri girişi › Veri Aktar › Tüm çalışma kitabı
- Yapın: "Yeni senaryo oluştur"u seçin. Sezon adı `2026-2027`, Senaryo adı `Test Bütçe 2026-2027`, Tür Fiyat çalışması. Dosya `11-16-2026-fiyat-calismasi-butce.xlsx`. "İçe aktar"a basın.
- Beklenen (içe aktarma özeti) **API ✓**:
  - Malzeme 32, fiyat 30 (2 malzeme bilerek fiyatsız), revize 2
  - Gider havuzu 11, ambalaj sınıfı 5
  - Ürün 7, reçete 7, parametre 17, üretim kapasitesi 7, satış fiyatı notu 1
  - Atlanan sayfa: **"001 (2)"**
  - Ürün parametre farkı: **006 · enflasyon 0,25** (diğer sayfalarda 0,30)
  - Uyarı yok
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.3 Genel Bakış** · Çalışma › Genel Bakış (senaryo: Test Bütçe 2026-2027)
- Beklenen: ürün sayısı **7**. Maliyet (TL, finansman dahil) ve satış fiyatı **API ✓**:

| Kod | Ürün | Maliyet TL | Satış TL |
|---|---|---|---|
| 03.99.001 | Test Berrak Turşu 370 ml | 25,49 | 30,58 |
| 03.99.002 | Test Berrak Turşu 720 ml | 39,91 | 47,89 |
| 03.99.003 | Test Közlenmiş Biber 370 ml | 32,20 | 38,64 |
| 03.99.004 | Test Domates Sos 340 g | 29,89 | 35,86 |
| 03.99.005 | Test Siyah Zeytin 500 g | 73,54 | 88,25 |
| 03.99.006 | Test Karışık Turşu 2,5 kg | 84,19 | 101,03 |
| 03.99.007 | Test Berrak Kornişon 370 ml | 27,57 | 33,08 |

- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.4 Ürün maliyeti dökümü** · Çalışma › Ürün Maliyeti › 03.99.001
- Beklenen **API ✓**:
  - Malzeme 18,55; direkt işçilik 0,65; GÜG 1,01; üretim gideri 1,66
  - Diğer (pazarlama + yönetim) 1,03; giydirilmiş 21,24
  - Finansman 4,25; maliyet 25,49 TL (0,51 USD / 0,45 EUR)
  - Reçetede "Test Fermente Hıyar (ara mamul)" satırı ve altında 3 alt satır (hıyar, tuz, kalsiyum klorür)

  Diğer ürünlerde:
  - **03.99.006**'da diğer giderler **0,00** (pazarlama/yönetim uygulanmıyor).
  - **03.99.002**'de uyarı "99.20.015 (Test Shrink Kılıf): birim fiyatı 0".
  - **03.99.004**'te uyarı "99.11.010 (Test Biber Salçası): birim fiyatı 0".
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.5 Veri Kontrolü** · Kontrol › Veri Kontrolü
- Beklenen özet: hata 0 · dikkat 2 · tamam 12 · bilgi 1. **API ✓**
  - "Fiyatı olmayan malzeme" **2**: 99.11.010 Test Biber Salçası, 99.20.015 Test Shrink Kılıf
  - "Eksik fiyattan etkilenen ürün" **2**: 03.99.002, 03.99.004
  - "Elle girilmiş hücre" **3** (bilgi): 03.99.003 (sarımsak elle fiyat 92), 03.99.004 (elektrik elle birim fiyat), 03.99.005 (zeytin elle brüt 0,53)
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.6 Gider havuzları ve parametreler** · Kayıtlar › Gider Dağıtım, Kayıtlar › Parametreler
- Beklenen gider havuzları **API ✓**. Çarpanlar Excel formülünden ayrıştırılır ve düzenlenebilir görünür:
  - Dolum işçilik 9.720.000 (= 6.000.000 × 1,35 × 1,2)
  - Endirekt işçilik 5.000.000 (4.000.000 × 1,25)
  - Diğer GÜG 4.000.000 (3.200.000 × 1,25)
  - Elektrik 3.640.000 (2.600.000 × 1,4)
  - Doğalgaz 1.500.000 (1.000.000 × 1,5)
  - Amortisman 6.000.000 (çarpansız)
  - Yönetim 10.400.000 (8.000.000 × 1,3)
  - Pazarlama 12.500.000 (10.000.000 × 1,25)
  - Mal kabul işçilik 2.400.000 ve mal kabul GÜG 1.200.000 (pay tablolu)

  Parametreler: enflasyon 0,30; USD 42,5; EUR 49; GBP 56; CHF 52; faiz TL 0,40 / USD 0,06 / EUR 0,06; stok süresi 6 ay; teklif kâr oranları 0,20 / 0,17 / 0,14; maliyet sapma 0,03.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 2. Günlük işler

**2.1 Düzenleme kilidi** · Ürün Maliyeti (ya da Malzeme Fiyatları)
- Yapın: sayfa başlığının altında "Düzenleme kilitli…" şeridini görün. "Düzenlemeyi aç"a basın.
- Beklenen:
  - "Düzenleme açılsın mı? Değişiklik yapmak üzeresiniz. Emin misiniz?" sorusu çıkar. "Evet, aç" deyince şerit "Düzenleme açık · 15 dk kaldı" olur.
  - Değişiklik Günlüğü'ne "kilit açıldı" kaydı düşer. **API ✓** (Muhasebe 201)
  - İzleyici ile bu düğme hiç görünmez (sunucu 403 verir). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.2 Formül ipucu, katlama, klavye** · Ürün Maliyeti › 03.99.001 · **Ekran ☐**
- Yapın:
  - Tutar (fireli) hücresinin üzerine gelin.
  - "Test Fermente Hıyar (ara mamul)" satırındaki oka basın.
  - Bir Miktar hücresinde Enter / ↓ / Shift+Enter / Esc tuşlarını deneyin.
- Beklenen:
  - "Bu sayı nereden geldi" ipucu açılır, Esc kapatır.
  - Ok basılınca 3 alt satır gizlenir ve açılır. Satır 1 (ürünün kendisi) katlanmaz.
  - Enter/↓ alta, Shift+Enter/↑ üste geçer; Esc hücreyi eski değerine döndürür.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.3 Fiyat listesiyle revizyon** · Kayıtlar › Malzeme Fiyatları › Fiyat listesi yükle
- Yapın: Dosya `11-16-2026-fiyat-listesi-revize.xlsx`, Geçerlilik tarihi `15.11.2026`. "Önizle"ye basın.
- Beklenen önizleme **API ✓**:
  - Değişen **8**, Yeni 0, Aynı 22, Hatalı 0. "Revize fiyatlar" kutusunda 9 satır.
  - Değişenler: 99.10.001 18,5→20,72 · 99.10.004 14→16,1 · 99.11.002 22,5→23,1 · 99.11.006 38→44,84 · 99.20.001 6,4→7,3 · 99.20.002 9,1→10,1 · 99.20.007 11,5→13,8 · **99.20.011 Streç Film 95→133 (+%40)**
- Yapın: Neden `Test: Kasım revize fiyat listesi` yazıp "Uygula"ya basın.
- Beklenen: **"8 fiyat yazıldı."** **API ✓** Genel Bakış'ta maliyetler değişir:

  | Kod | Önce | Sonra |
  |---|---|---|
  | 001 | 25,49 | 27,85 |
  | 002 | 39,91 | 42,77 |
  | 003 | 32,20 | 33,94 |
  | 004 | 29,89 | 31,84 |
  | 005 | 73,54 | 73,54 (değişmez) |
  | 006 | 84,19 | 86,39 |
  | 007 | 27,57 | 29,32 |

- **Dikkat (bulgu):** %40 artışta liste yüklemesinde "büyük değişiklik" uyarısı **çıkmaz**; uyarı yalnız tek fiyat girişinde var (adım 2.5). Uyarıyı görürseniz Not'a yazın.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.4 Tek fiyat (küçük değişiklik)** · Malzeme Fiyatları › 99.10.001 › Fiyat değiştir
- Yapın: Yeni fiyat `21,50`, Geçerlilik tarihi bugün (16.11.2026), Neden `Test: hıyar alım fiyatı`. "Kaydet"e basın.
- Beklenen: uyarısız kaydedilir (+%3,8). "99.10.001 fiyatı kaydedildi." iletisi görünür. 03.99.001 maliyeti 27,85 → **28,07**. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.5 Tek fiyat (büyük değişiklik uyarısı)** · Malzeme Fiyatları › 99.20.004 Test Kapak 82 mm › Fiyat değiştir
- Yapın: Yeni fiyat `3,60` (eski 2,90), Neden `Test: kapak 82 mm zammı`. "Kaydet"e basın.
- Beklenen: **"Fiyat büyük ölçüde değişiyor"** penceresi açılır: "99.20.004: 2,90 → 3,60 (+%24,1) … uyarı eşiği %15". "Yine de kaydet" ile kaydedilir. **API ✓** (ilk deneme 422 `fiyat_sapma`, onayla 201)
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.6 Eksik fiyatlar ve yeni kart** · Veri Aktar › Satın alma fiyat listesi
- Yapın: Dosya `11-16-2026-satin-alma-yeni-malzeme.xlsx`, Geçerlilik `15.11.2026`. "Önizle"ye basın, Neden `Test: eksik fiyatlar` yazın, "Uygula"ya basın.
- Beklenen: önizlemede yeni malzeme 1 (99.20.016 Test Kavanoz 1000 ml) ve yeni fiyat 3 (99.11.010, 99.20.015, 99.20.016). Sonuç: malzeme eklendi 1, fiyat yazıldı 3.
- Veri Kontrolü: "Fiyatı olmayan malzeme" **0 (tamam)**; özet hata 0 · dikkat 0 · tamam 13 · bilgi 2 ("Enflasyonu aşan fiyat artışı" bilgi olarak eklendi). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.7 Reçete değişikliği + Kaydet + neden** · Ürün Maliyeti › 03.99.001
- Yapın: "Test Taze Hıyar" alt satırında (ara mamulün altında) Miktar'ı `0,22` → `0,23` yapın. Alttaki "1 satırda … değişiklik" çubuğunda "Kaydet"e basın. "Değişiklikleri kaydet" penceresinde:
  - Eski → Yeni (0,22 → 0,23) satırını görün.
  - Neden: `Test: hıyar miktarı 0,22 -> 0,23`
  - "Hesabı da kaydet" işaretli kalsın.
  - "Onayla ve kaydet"e basın.
- Beklenen: maliyet 28,07 → **28,34 TL**. Kayıtlı hesap #1 açılır. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.8 Elle hücre ve listeye/formüle dönüş** · Ürün Maliyeti › 03.99.001 ve 03.99.004
- Yapın: 03.99.001'de "Test Kapak 63 mm" Birim fiyatını `2,50` yapın ve Kaydet'e basın (Neden `Test: kapak elle fiyat`).
- Beklenen: maliyet **28,65**, Kaynak sütununda "Elle" rozeti görünür.
- Yapın: "Elle" rozetine basın ("Listeye dön") ve Kaydet'e basın (Neden `Test: kapak listeye dön`).
- Beklenen: maliyet **28,34**. **API ✓**
- Yapın: 03.99.004'te Gider kalemleri › Elektrik satırındaki elle birim fiyatı (0,11) formüle döndürün ve kaydedin (Neden `Test: elektrik formüle dön`).
- Beklenen: maliyet 33,96 → **33,98**. Veri Kontrolü "Elle girilmiş hücre" 3 → **2** (03.99.003 ve 03.99.005 kalır). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.9 Geçmiş hesaplar ve kıyas** · Ürün Maliyeti › 03.99.001 › Geçmiş hesaplar
- Beklenen: 03.99.001'in **3** kayıtlı hesabı var: 28,34 (2.7), 28,65 (elle kapak) ve 28,34 (listeye dön). **API ✓**
- Yapın: 28,65 ve son 28,34 hesaplarını "Kıyas için seç" ile işaretleyin.
- Beklenen: Kalem / A / B / Fark tablosunda fark yalnız malzeme toplamındadır (kapak 2,50 → 2,30). Maliyet farkı yaklaşık −0,31 TL; finansmanla birlikte. **Ekran ☐** Kıyas ucu iki hesapla API ✓.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.10 Onay çıktısı** · *(yakında eklenecek: ayrı bir çalışmada geliştiriliyor; bu adımı şimdilik atlayın)*
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.11 Kaydetmeden çıkma** · Ürün Maliyeti · **Ekran ☐**
- Yapın: bir miktarı değiştirip "Vazgeç"e basın.
- Beklenen: değişiklik geri alınır, kayıt oluşmaz.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.12 Üretim adetleri aktarımı** · Veri Aktar › Üretim adetleri
- Yapın: Dosya `11-16-2026-uretim-adetleri.xlsx`. "Önizle"ye basın, Neden `Test: hedef adetler` yazın, "Uygula"ya basın.
- Beklenen önizleme: yeni **1** (03.99.099), değişen 2 alan (03.99.001 hedef 18000→19800; 03.99.004 20000→18000), aynı 5. Uygula sonrası eklenen 1, güncellenen 2.
- Veri Kontrolü: "Üretim Adetleri'nde eşleşmeyen kod" **1** (03.99.099 · Test Eşleşmeyen Ürün). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.13 Gider dağıtım aktarımı** · Veri Aktar › Gider dağıtım
- Yapın: Dosya `11-16-2026-gider-dagitim.xlsx`. "Önizle"ye basın, Neden `Test: elektrik zammı` yazın, "Uygula"ya basın.
- Beklenen önizleme: yalnız **Elektrik** havuzu değişti, 3.640.000 → 4.186.000 (çarpanlar 1,4 ve 1,15). Ambalaj: 720 ml üretim adedi 4.000.000 → 3.600.000.
- Uygula sonrası: havuz 1, ambalaj 5. Maliyetler biraz artar: 001 28,34→28,40 · 002 44,86→44,96 · 003 33,94→34,01 · 004 33,98→34,04 · 005 73,54→73,65 · 006 87,08→87,32 · 007 29,32→29,38. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.14 Tek ürün reçetesi aktarımı** · Veri Aktar › Ürün reçetesi
- Yapın: Dosya `11-16-2026-urun-recetesi-004.xlsx`. "Önizle"ye basın.
- Beklenen önizleme: sayfa 004 · 03.99.004 · durum **değişti**, 11 satır, elle fiyat 0, uyarı yok:
  - eklenen: 99.11.004 Test Sarımsak
  - çıkan: 99.11.006 Test Toz Şeker
  - değişen: 99.10.004 Test Domates (miktar)
- Yapın: Neden `Test: sos reçetesi revizyonu` yazın, "Uygula"ya basın.
- Beklenen: versiyon 2 açılır. 03.99.004 maliyeti 34,04 → **33,69**. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.15 Satış geçmişi** · Kayıtlar › Satış Geçmişi (ya da Veri Aktar › Satış geçmişi › "Satış Geçmişi sayfasına git")
- Yapın: "Şablonu indir" bağlantısının çalıştığını görün. Sonra `11-16-2026-satis-gecmisi.xlsx` dosyasını yükleyin.
- Beklenen: **255** satır eklenir, hata yok. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.16 Stokta kalan (stok devri)** · Veri Aktar › Stokta kalan
- Yapın: Dosya `11-16-2026-stokta-kalan.xlsx`. "Önizle"ye basın (yeni 3), Neden `Test: geçen yıldan stok` yazın, "Uygula"ya basın.
- Beklenen: eklenen 3. **API ✓** Ürün Maliyeti › 03.99.001'deki stok etkisi kartı:
  - Stok 25.000 adet × 15,80 TL
  - Enflasyon çalışmanınki %30 → güncel stok maliyeti **20,54**
  - Bu yıl üretim adedi satış geçmişinden **588.200**
  - Bu yılın maliyeti **28,40**, ortalama maliyet **28,08**

  03.99.003'te: 8.000 × 17,20, enflasyon %35, üretim 120.000 (elle). Güncel **23,22**, bu yıl **34,01**, ortalama **33,34**.
- Yapın: 03.99.004 kartında "Kaldır" deyip Neden girin, sonra kaydı geri ekleyin. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 3. Teklif

**3.1 Tur açma** · Ürün Maliyeti › 03.99.001 › Teklif turları
- Yapın: Kayıtlı hesap olarak en son hesabı (28,34) seçin. Kâr `%20`, Müşteri `Test Market A.Ş.`, Not `1. tur` yazıp "Yeni tur"a basın. Sonra Kâr `%17`, Not `2. tur` ile ikinci turu açın.
- Beklenen:
  - 1. tur: 34,00 TL / 0,6868 USD / 0,5957 EUR
  - 2. tur: **33,15 TL** / 0,6696 USD
  - İkisi de "Taslak". **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.2 Durum değiştirme** · Teklif turları / Teklifler
- Yapın: 1. turu Gönderildi, sonra **Red** yapın ("Teklif durumunu onayla" → "Onayla"). 2. turu **Kabul** yapın.
- Beklenen: durumlar kaydedilir. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.3 Teklifler süzgeçleri** · Çalışma › Teklifler
- Beklenen: Durum Tümü **2**, Kabul 1, Red 1, Taslak 0. "Müşteri ara" ile `Test Market` yazınca 2 satır kalır. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.4 Teklif Kapak ve yazdırma** · Teklifler › "Teklif Kapak indir"; bir satıra tıklayıp Kayıtlı hesap › "Yazdır"
- Beklenen: `teklif-kapak.xlsx` iner (yaklaşık 7 KB) **API ✓**. Kayıtlı hesap sayfası açılır ve yazdırma önizlemesi düzgün görünür. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 4. Analiz

**4.1 Ya olursa** · Analiz › Ya olursa
- Yapın: Döviz kuru `%10`, diğerleri 0. "Hesapla"ya basın.
- Beklenen: etkilenen 5 ürün. En çok etkilenen **03.99.004**: 33,69 → 33,78 (+%0,28). Eşik altı 0. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.2 Zam etkisi** · Analiz › Zam etkisi
- Yapın: Malzeme `99.20.001 Test Kavanoz 370 ml`, Zam oranı `%10`. "Hesapla"ya basın.
- Beklenen: fiyat 7,30 → 8,03. Etkilenen **3** ürün (001, 003, 007). 03.99.001: 28,40 → 29,55 (+%4,05). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.3 Kur riski** · Analiz › Kur riski
- Yapın: Kur artışı `%10`, "Hesapla"ya basın.
- Beklenen: yıllık etki **48.386,39 TL**: EUR %81,9, USD %18,1. En riskli ürün 03.99.004. Ortalama döviz payı %0,78. **API ✓** "Excel'e indir" çalışır.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.4 Kârlılık haritası** (satış geçmişi yüklü) · Analiz › Kârlılık haritası
- Beklenen: marj eşiği %10, adet eşiği 125.400. **API ✓**

  | Bölge | Ürünler |
  |---|---|
  | Yıldız (çok adet, yüksek marj) | 001 (%26,5), 007 (%16,3) |
  | Fiyatı gözden geçir (çok adet, düşük marj) | 002 (%7,7), 004 (**−%13,6**) |
  | Büyütülebilir (az adet, yüksek marj) | 005 (%38,5) |
  | Sorgula (az adet, düşük marj) | 003 (%1,3), 006 (%7,4) |

- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.5 Marjı koruyan fiyat** · Analiz › Marjı koruyan fiyat
- Yapın: Hedef marj `%25`, "Hesapla"ya basın.
- Beklenen: zam gereken **5** ürün, ortalama zam %10,5, yıllık ek gelir yaklaşık 8,78 milyon TL. **API ✓**
  - 03.99.004: geçen yıl 29,11 → hedef 42,11 (+%44,7)
  - 03.99.001: zam gerekmez (−%1,2)
  - 03.99.005: zam gerekmez (−%9,7)
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.6 Fiyat eğilimi** · Analiz › Fiyat eğilimi
- Beklenen: pencere 12 ay, enflasyon eşiği %30. **Aşıyor 1**: 99.20.011 Test Streç Film +%40,00. Sonraki sıralar 99.20.004 +%24,14 · 99.20.007 +%20,00 · 99.11.006 +%18,00 · 99.10.001 +%16,22. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.7 Önemli malzemeler (80/20)** · Analiz › Önemli malzemeler
- Beklenen: eşik %80 içinde **9** malzeme. İlk üçü 99.20.001 Kavanoz 370 ml %17,84 · 99.10.001 Taze Hıyar %13,59 (kümülatif %31,43) · 99.10.005 Siyah Zeytin %13,02. 9. sırada 99.11.002 Sirke (kümülatif %81,93). "Excel'e aktar" çalışır. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.8 Liste çalışması** · Analiz › Liste çalışması
- Yapın: "Excel'den yükle" ile `11-16-2026-liste-fiyatlari-gecmis.xlsx` dosyasını yükleyin.
- Beklenen: **18** satır yazılır. Yurtiçi, bölen 0,63: Berrak 3 ürün (Berrak dışı 4). **API ✓**

  | Ürün | Yeni liste | 2025 liste | Liste artışı | Maliyet artışı |
  |---|---|---|---|---|
  | 03.99.001 | 54,10 | 49,90 | %8,4 | %29,1 |
  | 03.99.002 | 85,64 | 72,90 | %17,5 | %28,5 |
  | 03.99.007 | 55,97 | 52,90 | %5,8 | %25,0 |

  Üç üründe de liste artışı maliyetin **gerisinde**.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 5. Kıyasla

**5.1 Gerçekleşen senaryosu** · Veri Aktar › Tüm çalışma kitabı
- Yapın: Yeni senaryo, Sezon `2026-2027`, Senaryo `Test Gerçekleşen 2026-2027`, Tür **Gerçekleşen**. **"Kartları güncelle" işaretini kaldırın.** Dosya `11-16-2026-fiyat-calismasi-gerceklesen.xlsx`.
- Beklenen: ürün 7, malzeme 32, fiyat 30, atlanan "001 (2)", kart farkı yok. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**5.2 Bütçe vs Gerçekleşen** · Kıyasla › Bütçe vs Gerçekleşen (A: Test Bütçe, B: Test Gerçekleşen, eşik %5)
- Beklenen maliyet TL (A → B, fark %) **API ✓**:
  - 001 28,40 → 23,68 (−16,64)
  - 002 44,96 → 37,85 (−15,82)
  - 003 34,01 → 30,42 (−10,56)
  - 004 33,69 → 29,34 (−12,91)
  - 005 73,65 → 67,46 (−8,41)
  - 006 87,32 → 88,00 (**+0,78**, eşik altında)
  - 007 29,38 → 24,50 (−16,60)

  Gerçekleşende enflasyon 0 olduğu için çoğu ürün daha ucuz çıkar.
- Yapın: 03.99.001'e tıklayın ("Sapmanın kaynağı").
- Beklenen: reçete maliyeti 20,93 → 17,11 (−%18,23); GÜG 1,68 → 1,59; finansman 4,73 → 3,95. "Excel'e aktar" çalışır.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 6. Yönetim

**6.1 Yönetim Özeti** · Çalışma › Yönetim Özeti (senaryo: Test Bütçe)
- Beklenen **API ✓**:
  - 7 ürün, 7 hesaplanan; ortalama marj %20; hedef altı 0
  - Maliyet yapısı: malzeme %74,4 · üretim %6,8 · faaliyet %2,1 · finansman %16,7
  - Kur riski yıllık 48.386 TL
- Yapın: "Yazdır / PDF" ile PDF olarak kaydedin. Beklenen: yaklaşık 2 sayfa ve düzgün görünüm. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.2 Toplu maliyet kartları** · Genel Bakış › "Tüm maliyet kartları (ürün başına sayfa)"
- Beklenen: Excel iner; sayfalar **Özet + 7 ürün** (03.99.001 … 03.99.007). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.3 Değişiklik Günlüğü** · Kontrol › Değişiklik Günlüğü
- Beklenen:
  - Bu noktada **100'den fazla** kayıt var (kuru koşuda 108; ekrandan yapılan kilit açmalar nedeniyle biraz daha fazla olabilir). En üstte "Liste fiyatı toplu yüklendi" kaydı.
  - "Kullanıcı adı" süzgecine `muhasebe1` yazınca liste daralır; "Ürün kodu" `03.99.001` ile yalnız o ürünün kayıtları kalır.
  - Bir fiyat kaydında "Geri al" → "Geri almayı onayla" çalışır. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.4 Roller** · ayrı tarayıcı profillerinde
- **izleyici1** **API ✓**:
  - "Düzenlemeyi aç" düğmesi yok; Veri girişi menüsü yok; Kullanıcılar sayfası kapalı.
  - Sunucu her yazmayı "İzleyici rolünün bu işleme izni yok" diye reddeder.
- **satinalma1** **API ✓**:
  - Malzeme Fiyatları'nda 99.11.007'ye `74` fiyatını (Neden `Test: satın alma fiyat girişi`) **kaydedebilir**.
  - Ürün Maliyeti'nde reçete kaydı "Satın alma rolünün bu işleme izni yok" hatası verir.
  - **Bulgu:** Satın alma "Veri girişi" menüsünü ve "Düzenlemeyi aç" düğmesini görür; kilit açma da kaydedilir (201). Bu beklenen mi, Not'a yazın.
- **muhasebe1** **API ✓**: Kullanıcılar sayfasına giremez ("yalnız Genel Direktör'e açıktır").
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.5 Çalışma kilitleme** · Kıyasla › Geçmiş kayıtlar (Arşiv) › Test Gerçekleşen › "Kilitle"
- Yapın: Neden `Test: gerçekleşen kesinleşti` yazıp kilitleyin. Sonra senaryo seçiciden Test Gerçekleşen'i seçip bir fiyat değiştirmeyi deneyin.
- Beklenen: kilitleme yapılır. Kayıt "senaryo kilitli" hatasıyla reddedilir; ekranda "Bu senaryo kilitli olduğu için düzenleme açılamaz" görünür. **API ✓** Okuma ve hesaplama serbesttir.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 7. Maliyet Muhasebesi (SMM)

> Sol paneldeki "Maliyet Muhasebesi" ile çalışma alanını değiştirin. Adımları muhasebe1 ile yapın; kilit açma adımları direktor ile.

**7.1 Ekim dönemini yükleme** · Dönemler › "SMM Excel'inden yükle"
- Yapın: Dosya `11-16-2026-smm-ekim-2026.xlsx`, Ay **Ekim**, Yıl **2026**. Dosya adından dönem çıkarılamaz; elle seçin. "Yükle"ye basın.
- Beklenen **API ✓**:
  - Ekim 2026: **37** kalem, finansman 85.000
  - Excel TABLO kontrolü: 37 karşılaştırıldı, **37 eşit**, 0 farklı
  - Reçete kaynağı "Excel'deki"
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.2 Veri kontrol listesi** · Veri Girişi
- Beklenen: tüm kaynaklar yüklü, eksik yok. **API ✓**
  - Dolu satır sayısı: Alım ve satış 23 · Alım iadeleri 2 · Üretim miktarları 14 · Sayım 37 · Şahit numune 2 · Gider mizanı 5 · Stok mizanı 6
  - Dönem başı stok 37 kalem, **9.100.125,00 TL**
  - Gider tutarları: 720 = 1.850.000, 730 = 2.450.000
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.3 Stok ve envanter** · Stok ve Envanter
- Beklenen toplamlar **API ✓**:
  - Dönem başı 9.100.125,00
  - Alım 12.670.925,16; finansman payı 85.000,00; iade 50.602,90
  - Sayım × ortalama 9.296.034,52
  - Sarf 12.510.826,82; üretime giden 12.561.429,72
  - Kontrol uyarısı 0
  - Türler: Hammadde 5, Yarı Mamul 5, Mamul 5, Ambalaj 10, Üretim Yarı Mamulü 4, Yardımcı 8

  Örnek satırlar:
  - 99.10.001 Test Taze Hıyar: ortalama fiyat 18,7122, sarf 137.616,8 kg
  - 99.20.001 Kavanoz 370 ml: ortalama fiyat 6,4612, sarf 491.895 adet
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.4 SMM özeti (düzeltme öncesi)** · SMM Özeti
- Beklenen **API ✓**:
  - 620 SMM **16.387.031,91**; üretim maliyeti 18.007.801,13; 710 ilk madde 13.707.801,13
  - Dönem sonu stok 9.707.834,60
  - Stok mizanı ile sayım: 150 farkı **3.230,60** · 151 farkı 0,00 · 152 farkı 1.885,80
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.5 Elle kalem düzeltme** · Stok ve Envanter › 99.20.001 › Düzenle
- Yapın: Sayım miktarını 191.170 → `191.670` yapın. Neden `Test: sayım tutanağına göre düzeltme`. "Kaydet"e basın.
- Beklenen: sarf 491.895 → 491.395. Satırda "elle" işareti görünür. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.6 Mizan elle satır** · Veri Girişi › Stok mizanı › "Satırları gör / düzenle" › "Satır ekle"
- Yapın: Hesap `153.01`, Ad `Test Ticari Mal`, Bakiye `12.500`, Neden `Test: elle satır`.
- Beklenen: satır eklenir ve elle işaretli görünür. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.7 Üretim maliyeti 20 / 40 / 50** · Üretim Maliyeti
- Beklenen birim maliyetler (TL) **API ✓**:
  - 20 Sebze kabul: 01.99.001 Fermente Hıyar **24,14** (120.700 kg) · 01.99.002 33,20 · 01.99.003 45,73 · 01.99.004 30,95
  - 40 Üretim hattı: 02.99.001 **18,64** · 02.99.002 30,27 · 02.99.003 23,81 · 02.99.004 22,75 · 02.99.007 20,64
  - 50 Etiketleme: 03.99.001 **21,01** (320.000 adet) · 03.99.002 34,04 · 03.99.003 26,18 · 03.99.004 24,93 · 03.99.007 22,95
  - 50 aşaması toplamı 17.741.731,70
  - Dağıtım: dağıtılan 4.300.000 = mizan 720 + 730; dağıtılmayan **0**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.8 Aşamada elle değer ve formüle dönüş** · Üretim Maliyeti › 50 › 03.99.002
- Yapın: İşçilik değerini kalemle `1,25` yapıp kaydedin. Sonra "Formüle dön"e basın.
- Beklenen: birim maliyet 34,04 → **34,24**. Formüle dönünce yeniden **34,04**. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.9 Sarf farkı** · Sarf Farkı
- Beklenen: fazla sarf **150.165,65 TL**, eksik sarf −48.629,22 TL, birim uyumsuz 0. **API ✓** En üstteki satırlar:
  - 99.10.001 Hıyar: reçeteye göre 132.963,12, sayıma göre 137.616,80 kg; fark +4.653,68 kg = +87.080,44 TL
  - 99.20.001 Kavanoz: −6.474,4 adet = −41.832,48 TL
  - 99.11.002 Sirke: +28.239,46 TL
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.10 SMM özeti (düzeltme sonrası) ve fiş** · SMM Özeti
- Beklenen **API ✓**:
  - 620 SMM **16.383.801,31**; üretim maliyeti 18.004.570,53; 710 13.704.570,53
  - Üretilen mamul 17.841.854,37; dönem sonu stok 9.711.065,20
  - Stok mizanı ile sayım: 150 farkı **0,00** (düzeltme farkı kapattı) · 151 0,00 · 152 1.885,80 · 153 12.500 (elle satır)
  - Fiş taslağı 12 satır; borç = alacak = 65.934.796,75
- Yapın: "SMM fişini Excel olarak indir". Beklenen: dosya iner. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.11 Bütçe kıyası** · Bütçe Kıyası (Fiyat çalışması: Test Bütçe 2026-2027)
- Beklenen: eşleşen 5, yalnız bütçede 2 (03.99.005, 03.99.006). Bütçe üretim maliyeti → fiili **API ✓**:
  - 004: 27,12 → 24,93 (−%8,06)
  - 001: 22,61 → 21,01 (−%7,11)
  - 002: 35,78 → 34,04 (−%4,84)
  - 003: 27,31 → 26,18 (−%4,15)
  - 007: 23,43 → 22,95 (−%2,02)
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.12 Ürün maliyet kartı** · Bütçe Kıyası ya da Üretim Maliyeti'nden 03.99.001'e tıklayın
- Beklenen: birim maliyet **21,01**, üretim 320.000. 50 aşamasında malzeme 20,25, işçilik 0,70, fire 0,06. Altında 40 (02.99.001) ve 20 (01.99.001) aşamaları zincir olarak görünür. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.13 Kapanış ön kontrolü ve kilit** · Dönemler (ya da Veri Girişi) › "Dönemi kapat (kilitle)"
- Yapın: "Kapat ve kilitle"ye basın.
- Beklenen: eksik yok, doğrudan kilitlenir. Sonra bir kalem düzeltmesi "dönem kilitli" hatasıyla reddedilir. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.14 Ekim kilidini Muhasebe ile açma denemesi** · Dönemler
- Beklenen: Muhasebe'de "Dönem kilidini yalnız Genel Direktör açabilir." yazar (sunucu 403). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.15 Canias reçeteleri** · Ana veriler › Reçeteler › "Canias ürün ağacı dökümünü yükle"
- Yapın: Dosya `11-16-2026-smm-receteler-canias.xlsx`. "Önizle"ye basın, sonra "Yükle"ye basın.
- Beklenen: 63 satır, **14** ürün (aşama 20: 4, 40: 5, 50: 5). Alternatifli ürün 1 (03.99.001: 00 ve 01). Eklenecek 14. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.16 Kasım yeni dönem** · Dönemler › Yeni dönem aç (Kasım 2026)
- Beklenen **API ✓**:
  - Kasım 2026 açılır: 37 kalem, devir **37 kalem, 9.711.065,20 TL**; "kapatılmadı" uyarısı yok (Ekim kilitli)
  - Reçete kaynağı "Canias (kalıcı)"
  - Veri Girişi'nde eksik 4: Alım ve satış, Üretim, Sayım, Gider mizanı
  - Devir uyumlu
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.17 Kasım aylık kaynakları** · Veri Girişi › her satırda "Yükle"
- Yapın: 7 dosyayı sırayla yükleyin: `11-16-2026-smm-kasim-2026-alim-satis`, `-iadeler`, `-uretim`, `-sayim`, `-sahit-numune`, `-gider-mizan`, `-stok-mizan`.
- Beklenen dolu satır: 23 · 1 · 14 · 37 · 2 · 5 · 6. Son dosyadan sonra eksik yok. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.18 Dağıtım havuzlarını Kasım mizanına eşitleme** · Üretim Maliyeti › Dağıtım › "Göster / değiştir"
- Beklenen önce: dağıtılan 4.300.000 (Ekim'den kopyalandı); mizan 720 = 1.920.000, 730 = 2.450.000; **dağıtılmayan 70.000**. **API ✓**
- Yapın: "40 · Üretim GÜG" havuzunu 1.900.000 → `1.970.000` yapıp "Kaydet ve yeniden hesapla"ya basın.
- Beklenen: dağıtılan 4.370.000, dağıtılmayan **0**. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.19 Kasım SMM özeti** · SMM Özeti (Kasım 2026)
- Beklenen **API ✓**:
  - 620 SMM **16.393.436,34**; üretim maliyeti 17.981.182,92; 710 13.611.182,92
  - Dönem sonu stok 11.834.195,32
  - Mizan farkları: 150 0,00 · 151 0,00 · 152 1.385,93
  - Devir durumu uyumlu: açılış = Ekim kapanışı = 9.711.065,20
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.20 Aylar arası** · Aylar Arası
- Beklenen: Ekim ve Kasım sütunları. 710 satırı 13.704.570,53 → 13.611.182,92 (−93.387,61 TL, −%0,68). 720 satırı 1.850.000 → 1.920.000. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.21 Kilit kuralları** · Dönemler (direktor ile)
- Yapın ve beklenen **API ✓**:
  1. Kasım'ı muhasebe1 ile kapatın: eksik yok, kilitlenir.
  2. direktor ile Ekim kilidini açmayı deneyin: **"önce Kasım 2026 kilidini açın; açılışı bu dönemden devralındı"** (reddedilir).
  3. direktor ile önce Kasım'ın kilidini, sonra Ekim'inkini açın. Ekim açılırken şu uyarı çıkar: "Kasım 2026 açılışı bu dönemden devralındı; değişiklik sonrası devri yenileyin".
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**7.22 Devir uyumsuzluğu ve devri yenile** · Ekim › Stok ve Envanter, sonra Kasım › Veri Girişi
- Yapın: Ekim'de 99.10.001 Hıyar sayımını `5.000` yapın (Neden `Test: Ekim sayım düzeltmesi`). Kasım'a geçin.
- Beklenen **API ✓**:
  - Sarı şerit: "Açılış stoku Ekim 2026 kapanışıyla uyuşmuyor" (1 kalem, fark 648.659,16 TL).
  - Kasım'ı kapatmayı denerseniz bu madde eksik olarak listelenir.
- Yapın: "Devri yenile" deyin, Neden `Test: Ekim düzeltmesi sonrası` yazın.
- Beklenen: güncellenen 1 kalem, devir uyumlu. **API ✓** Not: Kasım SMM tutarları bu düzeltmeyle değişir; 7.19'daki sayılar artık geçerli değildir.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 8. Yedek ve geri yükleme (test veritabanında)

**8.1 Yedek alma** · PowerShell, proje kökünde
- Yapın:
  `powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-yedekle.ps1 -AyarDosyasi test-dongusu\11-16-2026-test-ayarlar.env`
- Beklenen: "Yerel yedek: …\veri\yedek\AA-GG-YYYY-SSDDSS-yedek-test-dongusu.db" ve "Ağ paylaşımı ayarlı değil … yalnız yerel yedek alındı.", çıkış kodu 0. Sunucu açıkken de çalışır. Aynı betik geçici bir test veritabanıyla denendi: kod 0.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**8.2 Yedekten sonra değişiklik** · uygulama
- Yapın: Malzeme Fiyatları'nda bir fiyatı değiştirin ve yeni değeri not edin.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**8.3 Geri yükleme** · PowerShell
- Yapın: önce "Fiyat Calismasi TEST Sunucusu (8047)" penceresini kapatın. Sonra:
  `powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-geri-yukle.ps1 -AyarDosyasi test-dongusu\11-16-2026-test-ayarlar.env`
  Listeden 8.1'deki yedeği seçin ve `EVET` yazın.
- Beklenen:
  - Sunucu açıkken "Port 8047 dinleniyor … geri yükleme yapılmaz" (kod 2).
  - Kapalıyken önce "geri-yukleme-oncesi" yedeği alınır, sonra "Geri yüklendi" yazar (kod 0).
  - Betiğin sonundaki "baslat.ps1" önerisini **kullanmayın**: o asıl uygulamayı (8000) başlatır. Test ortamını yeniden `11-16-2026-test-ortamini-ac.bat` ile açın.
  - 8.2'deki fiyat değişikliği kaybolmuş olmalı.
- Doğrulama: aynı akış geçici veritabanıyla denendi; kod 2 ve kod 0 görüldü.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

## 9. Temizlik

**9.1 Test ortamını kapatıp silme**
- Yapın: test sunucusu penceresini kapatın. `test-dongusu\11-16-2026-test-ortamini-sifirla.bat` dosyasını çalıştırıp `EVET` yazın.
- Beklenen: yalnız `veri\test-dongusu.db`, `-wal` ve `-shm` silinir; `veri\fiyat.db`'ye dokunulmaz. Sunucu açıksa betik çalışmaz.
- Yedek klasöründeki test yedeklerini (`veri\yedek\*test-dongusu.db`) elle silin: otomatik günlük yedek, 8.1 ve 8.3'ün yedekleri.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## Bulunan hatalar

| # | Adım | Ekran | Ne oldu | Ne bekleniyordu |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |

**Kuru koşuda önceden görülen noktalar (karar bekliyor):**
- **Liste yüklemesinde büyük değişiklik uyarısı yok** (adım 2.3). Streç Film +%40 uyarısız yazıldı. Uyarı yalnız tek fiyat girişinde var (`backend/servisler/import_servisi.py` `fiyat_listesi_uygula`).
- **Fiyat listesi önceki elle değişiklikleri geri alabilir.** Listede yalnız F (bütçe) sütunu dolu olan satır, o tarihten sonra elle girilmiş fiyatı F'ye geri yazar. Kuru koşunun ilk denemesinde 99.20.004 3,60 → 2,90'a döndü. Senaryoda bu yüzden liste tek fiyattan önce yüklenir.
- **Satın alma rolü** "Veri girişi" menüsünü ve "Düzenlemeyi aç" düğmesini görür, ama reçete kaydı reddedilir (adım 6.4).
- **Geri yükleme betiği** test ayar dosyasıyla çalışsa da sonunda `baslat.ps1` önerir; o betik asıl uygulamayı açar (adım 8.3).
