# Sezon senaryosu: öngörüden gerçekleşene bir sezonun hikâyesi

Bu senaryo uygulamayı bir sezonu baştan sona yaşar gibi dener: Eylül'de bütçe kurulur, Ekim'de teklif verilir ve ay kapanır, Kasım'da kavanoz zamlanır ve dolar yükselir, sezon sonunda gerçekleşen rakamlar gelir. Fiyat Çalışması ile Maliyet Muhasebesi (SMM) aynı hikâyenin iki yüzüdür: aynı ürünler, aynı adetler, aynı fiyatlar.

Test verisi uydurmadır ve **bilerek** kurgulanmıştır. Bütçe ile gerçekleşen arasında yalnız dört fark vardır (kur, fiyat, fire, adet). Diğer her şey aynıdır. Bu yüzden her ekranda "neden değişti?" sorusunun cevabı bellidir ve rakamla yazılmıştır.

**Beklenen sayılar nereden geliyor?**
- Test verisini üreten betik (`test-dongusu\uret.py`) her ürünün maliyetini Excel formülleriyle kendisi hesaplar; uygulama kodunu kullanmaz. Bilinen farkların beklenen etkisini `test-dongusu\11-16-2026-beklenen-sapmalar.json` dosyasına yazar.
- Bütün yükleme ve sayı adımları API üzerinden, rollerle ve giriş zorunlu modda gerçekten koşturuldu (kuru koşu: `test-dongusu\kuru_kosu_sezon.py`, 16.11.2026). Kuru koşu 206 kontrol yaptı; **206'sı tuttu**. Sonuçlar `test-dongusu\11-16-2026-sezon-kuru-kosu-sonuclari.json` dosyasında.
- **API ✓**: sayı kuru koşuda doğrulandı. **Ekran ☐**: tıklama ve görünüm ilk kez sizin denemenizle doğrulanacak.

Sayılar adımlar **bu sırayla** yapılırsa tutar. Bir adımı atlarsanız ya da farklı değer girerseniz sonraki sayılar değişir; sapmayı "Not" alanına yazın. Ekranda 2 haneye yuvarlanmış tutarlarda ±0,01 fark normaldir.

---

## Bir bakışta

### Hikâye (zaman çizgisi)

| Ne zaman | Ne olur | Kim | Bölüm |
|---|---|---|---|
| Eylül | Bütçe kitabı yüklenir. Enflasyon %25, USD 42,00, EUR 48,00, satış kârı %20, teklif kârları %20 / %17 / %14. Satın alma eksik iki fiyatı tamamlar. Şirket toplamı okunur, bütçe kilitlenir, çalışma kopyası "Güncel" açılır. | Muhasebe, Satın alma | 1 |
| Ekim | İki müşteriye teklif verilir. Market 2. turda (%17) kabul eder, 1. turu reddetmişti. Toptan'ın teklifi (%20) açık kalır. | Muhasebe | 2 |
| Kasım başı | Tedarikçi "Test Kavanoz 370 ml"e **%15** zam yapar. Dolar **%8** yükselir. Muhasebe etkisini önce ölçer, sonra işler. Genel Direktör marj kaybını görür. | Satın alma → Muhasebe → Genel Direktör | 3 |
| Ekim ve Kasım sonu | Aylık SMM kapanışı. Ekim'de hıyar sayımı 3.000 kg eksik çıkar. Kasım'da zam fiilî maliyete yansır. | Muhasebe (kilit açma: Genel Direktör) | 4 |
| Sezon sonu | Gerçekleşen kitabı gelir. Bütçeyle farkın tamamı dört nedene ayrışır: kur, fiyat, fire, adet. | Muhasebe → Genel Direktör | 5 |
| Sezon sonu | Raporlar müşavire gider. Günlükte kim ne değiştirdi görülür. Yedek alınır. | Genel Direktör | 6 |

### Bilerek konan dört fark (bütçe → gerçekleşen)

| # | Neden | Ne değişti | Hangi ürün | Yıllık etki (TL) |
|---|---|---|---|---|
| a | Kur | USD 42,00 → 45,36 (+%8); EUR 48,00 → 50,40 (+%5) | dövizli malzemesi olan 5 ürün | +120.915,07 |
| b | Fiyat | Kavanoz 370 ml +%15 (maliyete giren 8,00 → 9,20 TL); Kapya Biber −%10 (32,00 → 28,80 TL) | 001, 003, 007 (kavanoz); 003 (biber) | +7.076.679,84 (kavanoz +8.203.636,36; biber −1.126.956,52) |
| c | Fire | Test Sirke firesi %2 → %5 | yalnız 03.99.002 | +87.699,25 |
| d | Adet | Vardiya üretim adedi 18.000 → 14.400 (hedefin %80'i) | yalnız 03.99.007 | +416.616,00 |
| | **Toplam** | | | **+7.701.910,16** |

Yıllık etki = birim maliyet farkı × yıllık adet. Yıllık adet, geçen yılın satış adedidir (uygulama yıllık adedi Satış Geçmişi'nden alır):

| Kod | Ürün | Yıllık adet | Ayda | Geçen yıl satış fiyatı (TL) |
|---|---|---|---|---|
| 03.99.001 | Test Berrak Turşu 370 ml | 3.600.000 | 300.000 | 28,95 |
| 03.99.002 | Test Berrak Turşu 720 ml | 1.440.000 | 120.000 | 42,50 |
| 03.99.003 | Test Közlenmiş Biber 370 ml | 1.080.000 | 90.000 | 35,00 |
| 03.99.004 | Test Domates Sos 340 g | 1.320.000 | 110.000 | 29,50 |
| 03.99.005 | Test Siyah Zeytin 500 g | 480.000 | 40.000 | 95,20 |
| 03.99.006 | Test Karışık Turşu 2,5 kg | 120.000 | 10.000 | 88,65 |
| 03.99.007 | Test Berrak Kornişon 370 ml | 960.000 | 80.000 | 30,60 |

SMM'de Ekim ve Kasım üretimi bu aylık adetlerin aynısıdır (005 ve 006 SMM'de üretilmez).

### Roller

| Kullanıcı | Rol | Ne yapar |
|---|---|---|
| `direktor` | Genel Direktör | Kullanıcıları açar. Yönetim Özeti'ni okur. Kapanmış SMM dönemini açar. Müşavir raporunu indirir. |
| `muhasebe1` | Muhasebe | Kitapları yükler, analizleri yapar, teklif verir, SMM kapanışlarını yapar. |
| `satinalma1` | Satın alma | Malzeme fiyatlarını girer, fiyat listesi yükler. |
| `izleyici1` | İzleyici | Yalnız okur ve rapor indirir. |

Her kullanıcıyı ayrı bir tarayıcı profilinde (ya da gizli pencerede) açın; aksi yazılmadıkça adımları **muhasebe1** ile yapın.

### Süre

| Bölüm | Süre |
|---|---|
| 0. Hazırlık | 15 dk |
| 1. Sezon başı: öngörü | 45 dk |
| 2. Teklif dönemi | 20 dk |
| 3. Sezon içi şok | 45 dk |
| 4. Ay kapanışları (Ekim, Kasım) | 75 dk |
| 5. Sezon sonu: gerçekleşen | 35 dk |
| 6. Yönetime ve müşavire rapor | 30 dk |
| 7. Kapanış | 10 dk |
| **Toplam** | **yaklaşık 4,5 saat** (iki oturuma bölünebilir: 0-3 ve 4-7) |

### Hangi dosya hangi adımda

Dosyalar `test-dongusu\excel\` klasöründedir; hepsi uydurma veridir. Yeniden üretmek için proje kökünde `.venv\Scripts\python.exe test-dongusu\uret.py` çalıştırın.

| Dosya | Ne | Adım |
|---|---|---|
| `11-16-2026-sezon-fiyat-calismasi-butce.xlsx` | Bütçe kitabı: 7 ürün sayfası (ayrıca atlanacak "001 (2)"), S.ALMA BF (32 malzeme, 2'si bilerek fiyatsız), Gider Dağıtım, Üretim Adetleri | 1.1 |
| `11-16-2026-sezon-satin-alma-eksik-fiyatlar.xlsx` | Fiyatsız iki malzemenin fiyatı (68,00 ve 0,35) | 1.4 |
| `11-16-2026-sezon-satis-gecmisi.xlsx` | Geçen yılın satışları (Haziran 2025 - Mayıs 2026, 168 satır) | 1.6 |
| `11-16-2026-sezon-liste-fiyatlari-gecmis.xlsx` | Berrak ürünlerinin 2023-2025 liste fiyatları (18 satır) | 1.10 |
| `11-16-2026-sezon-fiyat-listesi-kasim-revize.xlsx` | Kasım revize listesi: yalnız kavanoz 370 ml 6,40 → 7,36 | 3.2 |
| `11-16-2026-sezon-smm-ekim-2026.xlsx` | Ekim 2026 tam SMM Excel'i | 4.1 |
| `11-16-2026-sezon-smm-receteler-canias.xlsx` | Canias ürün ağacı dökümü (14 ürün, 63 satır) | 4.10 |
| `11-16-2026-sezon-smm-kasim-2026-*.xlsx` (7 dosya) | Kasım aylık kaynakları: alım-satış, iadeler, üretim, sayım, şahit numune, gider mizanı, stok mizanı | 4.12 |
| `11-16-2026-sezon-fiyat-calismasi-gerceklesen.xlsx` | Gerçekleşen kitabı (sezon sonu) | 5.1 |

**Kodlar:** malzemeler `99.xx.xxx`; ürünler `03.99.00x` (mamul), `02.99.00x` (dolu kavanoz yarı mamulü), `01.99.00x` (ara mamul / salamura).

---

## 0. Hazırlık

**0.1 Test ortamını sıfırlayın ve açın** · Windows Gezgini
- Neden sıfırlanmalı? Eski test veritabanında aynı sezon (2026-2027), aynı ürün kodları ve Ekim/Kasım 2026 SMM dönemleri var. Üzerine devam edilirse Ekim yüklemesi "dönem zaten var" diye reddedilir ve sayılar tutmaz.
- Yapın:
  1. "Fiyat Calismasi TEST Sunucusu (8047)" penceresi açıksa kapatın.
  2. Eski test verisini saklamak isterseniz önce 6.5'teki yedek komutunu çalıştırın.
  3. `test-dongusu\11-16-2026-test-ortamini-sifirla.bat` dosyasına çift tıklayın ve `EVET` yazın.
  4. `test-dongusu\11-16-2026-test-ortamini-ac.bat` dosyasına çift tıklayın.
- Beklenen:
  - Sıfırlama yalnız `veri\test-dongusu.db`, `-wal` ve `-shm` dosyalarını siler. `veri\fiyat.db`'ye dokunmaz.
  - Açılışta siyah pencerede "kullanıcı adı: direktor, geçici şifre: …" yazar. Şifreyi not edip bir tuşa basın.
  - Tarayıcı `http://localhost:8047` adresinde açılır.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**0.2 İlk giriş** · Giriş ekranı (direktor)
- Yapın: `direktor` ve geçici şifreyle girin. Yeni şifreyi iki kez yazıp "Şifreyi kaydet" deyin.
- Beklenen: ana sayfa açılır. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**0.3 Kullanıcıları açın** · Yönetim › Kullanıcılar (direktor)
- Yapın: "Yeni kullanıcı" ile `muhasebe1` (Muhasebe), `satinalma1` (Satın alma), `izleyici1` (İzleyici) açın. Her biriyle kendi tarayıcı profilinde bir kez girip şifre belirleyin.
- Beklenen: tabloda 4 kullanıcı, hepsi "Aktif". **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 1. Sezon başı: öngörü (Eylül · Muhasebe, Satın alma)

> **Hikâye.** Eylül. Yeni sezonun bütçesi hazır: Excel kitabında 7 ürünün reçetesi, 32 malzemenin fiyatı, gider havuzları ve parametreler var. Muhasebe kitabı yükleyecek, varsayımları gözden geçirecek ve şirketin bir yılda ne kadar harcayacağını görecek. Satın alma, fiyatı eksik kalan iki malzemeyi tamamlayacak. Sonunda bütçe "sabitlenecek": kilitlenecek ve sezon boyunca kıyas için el değmeden kalacak. Günlük işler kopyası üzerinde yürüyecek.
>
> **İş sorusu:** Bu sezon bir yılda ne kadar maliyet bekliyoruz, kârımız ne olur, kur riskimiz ne kadar?

**1.1 Bütçe kitabını yükleyin** · Veri Girişi › Veri Aktar › Tüm çalışma kitabı
- Yapın: "Yeni senaryo oluştur". Sezon `2026-2027`, Senaryo `Test Bütçe 2026-2027`, Tür **Fiyat çalışması**. Dosya `11-16-2026-sezon-fiyat-calismasi-butce.xlsx`. "İçe aktar".
- Beklenen içe aktarma özeti **API ✓**:
  - Malzeme 32, fiyat 30 (iki malzeme bilerek fiyatsız), revize 0
  - Gider havuzu 11, ambalaj sınıfı 5
  - Ürün 7, reçete 7, parametre 17, üretim kapasitesi 7, satış fiyatı notu 1
  - Atlanan sayfa "001 (2)"; ürün parametre farkı yok; uyarı yok
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.2 Varsayımları gözden geçirin** · Veri Girişi › Parametreler
- Beklenen **API ✓**:
  - Enflasyon 0,25; satış kârı 0,20; vardiya saati 7,5
  - Kurlar: USD 42, EUR 48, GBP 55, CHF 50
  - Faiz TL 0,40, stok süresi 6 ay
  - Teklif kâr oranları 0,20 / 0,17 / 0,14
- Ne anlama gelir: stoklu (S) TL malzemelerin fiyatı maliyete %25 enflasyon payıyla girer. Örneğin kavanoz 370 ml listede 6,40 TL'dir, maliyete 8,00 TL girer. Ziraat (Z) malzemelerinde ve dövizli malzemelerde enflasyon payı yoktur.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.3 Veri Kontrolü: eksikleri bulun** · Kontrol › Veri Kontrolü
- Beklenen özet: hata 0 · dikkat 2 · tamam 12 · bilgi 1. **API ✓**
  - "Fiyatı olmayan malzeme" **2**: 99.11.010 Test Biber Salçası, 99.20.015 Test Shrink Kılıf
  - "Eksik fiyattan etkilenen ürün" **2**: 03.99.002, 03.99.004
  - "Elle girilmiş hücre" 3 (bilgi): 03.99.003, 03.99.004, 03.99.005
- Genel Bakış'ta bu iki ürün eksik fiyatla düşük görünür: 03.99.002 **38,83**, 03.99.004 **29,03**. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.4 Satın alma eksik fiyatları tamamlar** · satinalma1 ile
- Yapın (önce toplu yol): Veri Girişi › Veri Aktar › Satın alma fiyat listesi. Senaryo Test Bütçe, dosya `11-16-2026-sezon-satin-alma-eksik-fiyatlar.xlsx`, geçerlilik `01.09.2026`. "Önizle", sonra Neden `Sezon başı: eksik satın alma fiyatları`, "Uygula".
- Beklenen:
  - Önizleme: yeni fiyat 2 (99.11.010 → 68, 99.20.015 → 0,35). **API ✓**
  - **"Uygula" reddedilir: "Satın alma rolünün bu işleme izni yok".** Kuru koşuda bulunan uygulama hatası (Kapanış bölümü, bulgu 1). Ekranda farklı davranırsa Not'a yazın.
- Yapın (geçici çözüm): Malzeme Fiyatları'nda iki fiyatı tek tek girin. 99.11.010 için `68,00`, 99.20.015 için `0,35`; geçerlilik `01.09.2026`, Neden `Sezon başı: eksik satın alma fiyatı`. Gerekirse önce "Düzenlemeyi aç".
- Beklenen: ikisi de kaydedilir (201). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.5 Veri Kontrolü temiz mi?** · Kontrol › Veri Kontrolü (muhasebe1)
- Beklenen: hata 0 · dikkat 0 · tamam 14 · bilgi 1 (yalnız elle hücre bilgisi). **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.6 Ürün maliyetleri ve geçen yılın satışları** · Çalışma › Genel Bakış; Veri Girişi › Satış Geçmişi
- Beklenen Genel Bakış (bütçe, TL, finansman dahil) **API ✓**. Maliyetleri üreticinin bağımsız hesabı da aynen buldu.

  | Kod | Maliyet | Satış (×1,20) |
  |---|---|---|
  | 03.99.001 | 24,53 | 29,44 |
  | 03.99.002 | 39,35 | 47,22 |
  | 03.99.003 | 31,25 | 37,50 |
  | 03.99.004 | 31,07 | 37,28 |
  | 03.99.005 | 73,24 | 87,89 |
  | 03.99.006 | 83,62 | 100,34 |
  | 03.99.007 | 26,61 | 31,93 |

- Ürün Maliyeti › 03.99.001 dökümü **API ✓**: malzeme 17,7586 · direkt işçilik 0,6456 · GÜG 1,0134 · pazarlama + yönetim 1,0269 · finansman 4,0889 · maliyet **24,5334 TL** (0,5014 USD).
- Yapın: Satış Geçmişi › "Excel'den yükle" ile `11-16-2026-sezon-satis-gecmisi.xlsx` dosyasını yükleyin.
- Beklenen: **168** satır eklendi, hata yok. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.7 Şirket toplamı: bir yılda ne harcayacağız?** · Çalışma › Yönetim Özeti; Analiz › Kur riski
- Beklenen Yönetim Özeti (Test Bütçe) **API ✓**:
  - Ortalama kâr marjı **%20,0**; adetle ağırlıklı da %20,0 (satış fiyatı maliyet × 1,20 olduğu için)
  - Maliyet yapısı: malzeme %73,96 · üretim %7,15 · faaliyet %2,22 · finansman %16,67
  - Kur riski: döviz payı %0,73; kurlar +%10 olursa yıllık etki **212.382 TL**
  - Veri Kontrolü: hata 0, dikkat 0
- Beklenen Analiz › Kur riski (kur artışı %10) **API ✓**:
  - **"Yıllık maliyet" 290.474.014 TL**. Şirketin bütçelenen yıllık maliyeti budur (birim maliyet × yıllık adet). Bölüm 3 ve 5'te bu sayıyla kıyaslayacağız; **not edin**.
  - Para birimi kırılımı: EUR 163.302,91 · USD 49.079,52
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.8 Kâr nerede?** · Analiz › Kârlılık haritası
- Hikâye: Satış fiyatlarını geçen yılın fiyatıyla tutarsak hangi ürün kazandırır?
- Beklenen: marj eşiği %10, adet eşiği 1.080.000. **API ✓**

  | Bölge | Ürünler (marj) |
  |---|---|
  | Çok adet, yüksek marj | 001 (%18,00), 003 (%12,01) |
  | Çok adet, düşük marj ("fiyatı gözden geçir") | 002 (%8,00), 004 (**−%5,04**, maliyetin altında satılıyor) |
  | Az adet, yüksek marj | 005 (%29,99), 007 (%15,00) |
  | Az adet, düşük marj | 006 (%6,02) |

- Yıllık kâr toplamı (tablodaki "Yıllık kâr" sütunlarının toplamı): **37.395.986,40 TL**. **API ✓** Bölüm 3'te bu sayı düşecek.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.9 Önemli malzemeler (80/20)** · Analiz › Önemli malzemeler
- Beklenen: yıllık malzeme tutarı 213.769.000 TL; eşik %80 içinde **9** malzeme. **API ✓**
  - 1. 99.20.001 Test Kavanoz 370 ml %21,32 (yıllık 45.575.758 TL)
  - 2. 99.10.001 Test Taze Hıyar %13,75 (kümülatif %35,07)
  - 3. 99.10.005 Test Siyah Zeytin %11,31 (kümülatif %46,38)
  - 9. 99.20.007 Test Koli 12'li (kümülatif %80,83)
- İş anlamı: en büyük tek kalem kavanoz 370 ml. Bu malzemeye gelecek bir zam en çok etkiyi yapar (bölüm 3).
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.10 Liste fiyatı çalışması** · Analiz › Liste çalışması
- Yapın: "Excel'den yükle" ile `11-16-2026-sezon-liste-fiyatlari-gecmis.xlsx`.
- Beklenen: **18** satır yazılır. Yurtiçi, bölen 0,63: Berrak 3 ürün. **API ✓**

  | Ürün | Yeni liste | 2025 liste | Liste artışı | Maliyet artışı |
  |---|---|---|---|---|
  | 03.99.001 | 46,73 | 49,90 | −%6,35 | %11,52 |
  | 03.99.002 | 74,95 | 72,90 | %2,81 | %12,43 |
  | 03.99.007 | 50,68 | 52,90 | −%4,20 | %13,23 |

  Üç üründe de liste artışı maliyetin **gerisinde**.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**1.11 Bütçeyi sabitleyin: kopya + kilit** · Senaryo seçici › Yeni çalışma › "Geçen sezondan kopyala"; Kıyasla › Geçmiş kayıtlar
- Yapın:
  1. Kaynak çalışma Test Bütçe 2026-2027, sezon `2026-2027`, ad `Test Güncel 2026-2027`, tür Fiyat çalışması. Kopyalanacakların hepsini işaretleyin. Neden `Sezon içi çalışma kopyası`. "Kopyala ve aç".
  2. Kıyasla › Geçmiş kayıtlar › Test Bütçe › "Kilitle", Neden `Bütçe sabitlendi (Eylül öngörüsü)`.
  3. Senaryo seçicide Test Bütçe'yi seçip bir fiyat değiştirmeyi deneyin.
- Beklenen **API ✓**:
  - Kopya: reçete 7, fiyat 32, parametre 17, metin 1, havuz 11, ambalaj 5, üretim hedefi 7, kapasite 7, fire kuralı 5.
  - Test Güncel'in Genel Bakış'ı bütçeyle kuruşu kuruşuna aynı.
  - Kilitli bütçeye yazma "senaryo kilitli" ile reddedilir (409).
- **Bundan sonra Fiyat Çalışması adımlarını Test Güncel 2026-2027 üzerinde yapın** (aksi yazılmadıkça).
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 2. Teklif dönemi (Ekim · Muhasebe)

> **Hikâye.** Ekim. İki zincir 370 ml Berrak Turşu (03.99.001) için fiyat istiyor. Muhasebe bütçe maliyetiyle (24,53 TL) teklif hazırlar. Test Market ilk teklifi (%20 kâr) pahalı bulur ve reddeder, ikinci turu (%17) kabul eder. Test Toptan'a verilen %20'lik teklif cevap beklerken açık kalır. Bu açık teklif bölüm 3'te "eskiyecek".
>
> **İş sorusu:** Hangi fiyatı verdik, hangisi kabul edildi, hangisi hâlâ açık?

**2.1 Hesabı kaydedin** · Ürün Maliyeti › 03.99.001 (Test Güncel)
- Yapın: "Hesabı kaydet".
- Beklenen: kayıtlı hesap oluşur, tarih bugün, maliyet 24,53 TL. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.2 Teklif turlarını açın** · Ürün Maliyeti › 03.99.001 › Teklif turları
- Yapın: kayıtlı hesabı seçin ve üç tur açın:
  1. Kâr `%20`, Müşteri `Test Market A.Ş.`, Not `1. tur`
  2. Kâr `%17`, Müşteri `Test Market A.Ş.`, Not `2. tur`
  3. Kâr `%20`, Müşteri `Test Toptan Ltd.`, Not `1. tur`
- Beklenen **API ✓**:
  - Market %20: **29,44 TL** (0,6017 USD)
  - Market %17: **28,70 TL** (0,5866 USD)
  - Toptan %20: **29,44 TL**
  - Tur numaraları 1, 2, **3**. Numara müşteriye göre değil, kayıtlı hesaba göre artar; Toptan'ın ilk teklifi "3. tur" görünür (bulgu 6).
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.3 Cevaplar gelir** · Teklif turları / Çalışma › Teklifler
- Yapın: Market 1. tur → Gönderildi → **Red**. Market 2. tur → Gönderildi → **Kabul**. Toptan → **Gönderildi**. Her durumu "Onayla" ile onaylayın.
- Beklenen süzgeçler: Tümü **3**, Kabul 1, Red 1, Gönderildi 1, Taslak 0. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**2.4 Taslak rapor** · Genel Bakış › "İndir" › Rapor (Excel)
- Beklenen: dosya iner (yaklaşık 47 KB). Her sayfanın başında kırmızı **"TASLAK — çalışma kapatılmadı"** damgası var, çünkü Test Güncel kilitli değil. **API ✓** "İndir" penceresindeki üç seçeneği (Genel Bakış tablosu / Tüm maliyet kartları / Rapor) görün. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 3. Sezon içi şok (Kasım başı · Satın alma → Muhasebe → Genel Direktör)

> **Hikâye.** Kasım'ın ilk günü tedarikçi kavanoz 370 ml'ye **%15** zam yaptığını bildirir (6,40 → 7,36 TL). Aynı hafta dolar **%8** yükselir (42,00 → 45,36). Başka hiçbir fiyat değişmez; bu yüzden etkiler temiz ölçülür. Muhasebe önce zammın etkisini ölçer, sonra satın alma listeyi yükler ve ölçülenle gerçekleşen karşılaştırılır. Dolar için de aynısı yapılır. Genel Direktör kârın ne kadar eridiğini görür. Toptan'a verilen açık teklifin artık zararına olduğu fark edilir.
>
> **İş sorusu:** Bu zam bize kaça mal olur? Fiyatı ne yapmalıyız?

**3.1 Zam gelmeden ölçün** · Analiz › Zam etkisi (muhasebe1, Test Güncel)
- Yapın: Malzeme `99.20.001 Test Kavanoz 370 ml`, Zam oranı `%15`, "Hesapla".
- Beklenen **API ✓**:
  - Fiyat 6,40 → 7,36. Etkilenen **3** ürün; her birinde birim maliyet **+1,4545 TL**. Bu tutar şöyle çıkar: 1,0101 adet (fireli) × 0,96 TL zam × 1,25 enflasyon payı × 1,20 finansman.
  - 03.99.001: 24,53 → 25,99 · fiyat aynı kalırsa kâr **%13,28**
  - 03.99.007: 26,61 → 28,06 · %13,78
  - 03.99.003: 31,25 → 32,70 · %14,66
- Yıllık etki = 1,4545 × (3.600.000 + 1.080.000 + 960.000) = **8.203.636 TL**. Bu sayıyı ekranda toplam olarak görmeyiz; 3.6'da Kur riski "Yıllık maliyet" kartından doğrulanır.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.2 Satın alma revize listeyi yükler** · Malzeme Fiyatları › Fiyat listesi yükle (satinalma1, Test Güncel)
- Yapın: "Düzenlemeyi aç" → "Düzenleme açılsın mı?" sorusuna "Evet, aç". Dosya `11-16-2026-sezon-fiyat-listesi-kasim-revize.xlsx`, Geçerlilik `01.11.2026`, "Önizle". Neden `Kasım revize fiyat listesi: kavanoz 370 ml +%15`, "Uygula".
- Beklenen **API ✓**:
  - Düzenleme kilidi satın almaya açılır (201).
  - Önizleme: değişen **1** (99.20.001 6,4 → 7,36), yeni 0, aynı 31, hatalı 0, revize 1.
  - Uygula: "1 fiyat yazıldı".
  - Zam tam %15 olduğu için "büyük değişiklik" uyarısı çıkmaz. Eşik %15'i **aşan** değişiklikte uyarır.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.3 Ölçülen = gerçekleşen mi?** · Genel Bakış (muhasebe1, Test Güncel)
- Beklenen: yalnız 001, 003, 007 değişir; her biri **+1,4545**. Zam etkisinin dediği çıkar. **API ✓**
  - 001 24,53 → **25,99** · 003 31,25 → **32,70** · 007 26,61 → **28,06** · diğerleri aynı
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.4 Dolar +%8 olursa?** · Analiz › Ya olursa; Analiz › Kur riski
- Yapın: Ya olursa'da Döviz kuru `%8`, diğerleri 0, "Hesapla".
- Beklenen **API ✓**: etkilenen 5 ürün. Birim etki: 004 **+0,0737** · 007 +0,0383 · 005 +0,0136 · 001 +0,0064 · 002 +0,0044. Eşik altına düşen yok.
- Dikkat: Ya olursa'daki kur kutusu **bütün** dövizlere uygulanır (USD, EUR ve diğerleri). Yalnız doları görmek için Kur riski'ne geçin.
- Yapın: Kur riski'nde Kur artışı `%8`, "Hesapla".
- Beklenen **API ✓**: yıllık etki 169.906 TL. Para birimi kırılımı: EUR 130.642,33 · **USD 39.263,62**. Doların tek başına yıllık etkisi budur.
- İş anlamı: dövizli malzeme payımız çok küçük (yaklaşık %0,7). Kur şoku kavanoz zammının yanında küçük kalır.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.5 Doları parametrede güncelleyin** · Veri Girişi › Parametreler (Test Güncel)
- Yapın: kur.USD için yeni değer `45,36`, geçerlilik `01.11.2026`, Neden `Kasım: USD +%8 (42,00 -> 45,36)`.
- Beklenen Genel Bakış: 001 +0,0064 · 002 +0,0044 (39,36) · 004 +0,0059 · 007 +0,0022 (28,07). 003, 005, 006 değişmez (USD'li malzemeleri yok). **API ✓**
- Şok sonrası Test Güncel maliyetleri: 001 **25,99** · 002 **39,36** · 003 **32,70** · 004 31,07 · 005 73,24 · 006 83,62 · 007 **28,07**. Üretici aynısını hesapladı. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.6 Genel Direktör kârın ne kadar eridiğini görür** · Yönetim Özeti; Kur riski; Kârlılık haritası (direktor, Test Güncel)
- Beklenen **API ✓**:
  - Kur riski "Yıllık maliyet": 290.474.014 → **298.716.914 TL**. Şokun şirkete yıllık maliyeti **+8.242.900 TL**: kavanoz 8.203.636 + dolar 39.264.
  - Kârlılık haritası (satış fiyatları geçen yılın fiyatıyla sabit): yıllık kâr toplamı 37.395.986 → **29.153.086 TL** (**−8.242.900**). 001'in marjı %18,00 → %11,37. 003 (%7,03) ve 007 (%9,03) %10 eşiğinin altına düşer. Bölgeler: çok adet-yüksek marj 1, çok adet-düşük marj 3, az adet-yüksek marj 1, az adet-düşük marj 2.
  - Yönetim Özeti'nde ortalama kâr marjı **%20,0'da kalır**. Bu sayı "satış fiyatı = maliyet × 1,20" hesabından gelir; satış fiyatı maliyetle birlikte yükseldiği için marj değişmez. Fiyat sabitken marjın düştüğü Yönetim Özeti'nde görünmez; Kârlılık haritasında ve Ya olursa / Zam etkisi'ndeki "Fiyat aynı kalırsa kâr" sütununda görünür (bulgu 4).
- Yapın: Yönetim Özeti › "Yazdır / PDF". **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.7 Marjı koruyan fiyat** · Analiz › Marjı koruyan fiyat (muhasebe1)
- Yapın: Hedef marj `%20`, "Hesapla".
- Beklenen: zam gereken **6** ürün, ciro ağırlıklı ortalama zam %9,33, zam yapılırsa yıllık ek gelir yaklaşık **34,10 milyon TL**. **API ✓**

  | Ürün | Maliyet | Geçen yıl fiyatı | Hedef fiyat | Gereken zam | Yurtiçi liste |
  |---|---|---|---|---|---|
  | 03.99.004 | 31,07 | 29,50 | 37,29 | %26,39 | — |
  | 03.99.001 | 25,99 | 28,95 | 31,19 | %7,75 | 49,51 |
  | 03.99.002 | 39,36 | 42,50 | 47,23 | %11,12 | 74,96 |
  | 03.99.003 | 32,70 | 35,00 | 39,24 | %12,12 | — |
  | 03.99.007 | 28,07 | 30,60 | 33,68 | %10,06 | 53,46 |
  | 03.99.006 | 83,62 | 88,65 | 100,34 | %13,19 | — |
  | 03.99.005 | 73,24 | 95,20 | 87,89 | zam gerekmez (−%7,68) | — |

- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.8 Önce / sonra: geçmiş hesaplar** · Ürün Maliyeti › 03.99.001 › "Hesabı kaydet", sonra Kıyasla › Geçmiş kayıtlar › iki kaydı kıyasla
- Beklenen: malzeme toplamı 17,7586 → **18,9761** (+1,2175: kavanoz +1,2121, dolar +0,0053). Direkt işçilik ve GÜG aynı. Maliyet 24,53 → 25,99. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.9 Zam enflasyonu aştı mı?** · Analiz › Fiyat eğilimi
- Beklenen: pencere 12 ay, enflasyon eşiği **%25**. İlk sırada 99.20.001 Kavanoz 370 ml 6,40 → 7,36, **+%15,00**, "aşmıyor" (2 kayıt). Diğer malzemelerde değişim 0. **API ✓**
- İş anlamı: zam büyük görünse de yıllık enflasyon varsayımının içinde kalıyor. Bütçe bu zammı "beklenen" saymıştı; gerçek sorun, kavanozun bütçedeki 8,00 TL yerine 9,20 TL'ye mal olması.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**3.10 Açık teklif eskidi** · Çalışma › Teklifler; Yönetim Özeti › En eski açık teklifler
- Beklenen: Yönetim Özeti'nde açık teklif **1**: Test Toptan Ltd., 03.99.001, Gönderildi, **29,44 TL**, hesap tarihi bugün. **API ✓**
- Hesap: bugünkü maliyetle (25,99) aynı %20 kâr için fiyat **31,19 TL** olmalı. Toptan kabul ederse kârımız %20 değil **%13,26** olur.
- Uygulamada "maliyet değişti, teklif eskidi" uyarısı **yok**; teklif takibi henüz yok (bulgu 5). Ekranda böyle bir uyarı görürseniz Not'a yazın.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 4. Her ay kapanış (Ekim ve Kasım sonu · Muhasebe)

> **Hikâye.** Ekim kapanışı: SMM Excel'i yüklenir. Ekim'de malzeme bütçenin öngördüğü fiyattan alınmıştır: stoklu TL malzemede liste × 1,25 (kavanoz 8,00 TL), dövizlide bütçe kuru. Üretim yıllık adedin 1/12'sidir. İşçilik (720) ve genel üretim gideri (730) bütçenin birim işçilik ve GÜG'ünden türetilmiştir; %5'i ürünlere dağıtılmaz. Depoda sayım yapılır, hıyar **3.000 kg eksik** çıkar. Kasım'da üretim ve giderler aynıdır, yalnız kavanoz (+%15) ve dolar (+%8) değişir. Kasım'ın fiilî maliyetindeki artış zammın etkisidir.
>
> **İş sorusu:** Ay kaça mal oldu? Bütçeye göre neredeyiz? Zam fiilî maliyete ne kadar yansıdı?

> Sol panelde "Maliyet Muhasebesi" ile çalışma alanını değiştirin.

### Ekim

**4.1 Ekim'i yükleyin** · Dönemler › "SMM Excel'inden yükle"
- Yapın: dosya `11-16-2026-sezon-smm-ekim-2026.xlsx`, Ay **Ekim**, Yıl **2026**. "Yükle".
- Beklenen **API ✓**: Ekim 2026, **37** kalem, finansman 0. Excel TABLO kontrolü 37 karşılaştırıldı, **37 eşit**. Reçete kaynağı "Excel'deki".
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.2 Kontrol listesi** · Veri Girişi
- Beklenen **API ✓**:
  - Eksik yok. Dolu satır: alım ve satış 23 · alım iadeleri 1 · üretim 14 · sayım 37 · şahit numune 2 · gider mizanı 5 · stok mizanı 6
  - Dönem başı stok 28 kalem, **8.439.054,88 TL**
  - 720 = **520.000**, 730 = **792.000**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.3 Stok ve envanter** · Stok ve Envanter
- Beklenen toplamlar **API ✓**: dönem başı 8.439.054,88 · alım 15.002.972,69 · iade 19.200,00 · sayım × ortalama 9.490.258,60 · sarf 13.932.568,97 · üretime giden 13.951.768,97 · kontrol uyarısı 0.
- Örnek satırlar: 99.10.001 Hıyar ortalama **18,50**, sarf 131.226,2 kg, sayım 48.290,5 kg · 99.20.001 Kavanoz 370 ml ortalama **8,00**, sarf 477.548 adet.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.4 Üretim maliyeti ve gider dağıtımı** · Üretim Maliyeti
- Beklenen birim maliyetler **API ✓**:
  - 20 Sebze kabul: 01.99.001 **21,2602** (116.400 kg) · 01.99.002 29,5222 · 01.99.003 41,5901 · 01.99.004 27,8401
  - 40 Üretim hattı: 02.99.001 **17,5477** · 02.99.002 27,8868 · 02.99.003 22,4490 · 02.99.004 20,9691 · 02.99.007 19,4325
  - 50 Etiketleme: 03.99.001 **19,7279** (300.000) · 03.99.002 31,1826 · 03.99.003 24,6762 · 03.99.004 23,1433 · 03.99.007 21,6183
- Beklenen gider dağıtımı bölümü **API ✓**:
  - Mizan 720 + 730 = 1.312.000. Dağıtılan **1.246.000**, dağıtılmayan **66.000 (%5,03)**.
  - Kırılım: 720 → 40 işçilik 296.000 · 730 → 40 GÜG 752.000 · 20 ve 50 aşamaları birleşik 198.000
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.5 Sarf farkı: hıyar nereye gitti?** · Sarf Farkı
- Beklenen **API ✓**:
  - "En büyük farklar"da ilk sırada **99.10.001 Test Taze Hıyar**: reçeteye göre 128.226,24 kg, stoktan 131.226,20 kg. Fark **+2.999,96 kg / 55.499,26 TL** (fazla sarf: sayım eksik çıktı).
  - Sonraki kalemler 21 TL'nin altında (yalnız yuvarlama).
  - Toplam: fazla 55.534,77 · eksik −27,69.
- İş anlamı: 3.000 kg hıyar reçeteye göre tüketilmesi gerekenden fazla gitmiş (fire, çürüme ya da sayım hatası). Üretimle konuşulmalı.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.6 SMM özeti ve fiş** · SMM Özeti
- Beklenen **API ✓**:
  - 710 ilk madde **15.058.521,63** · üretim maliyeti 16.370.521,63 · üretilen mamul 16.277.870,64 · **620 SMM 15.158.553,39**
  - Dönem sonu stok 9.564.633,84
  - Stok mizanı ile sayım: 150 · 151 · 152 farkı **0,00**
  - Fiş borç = alacak = 62.865.467,29
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.7 Bütçeye göre neredeyiz?** · Bütçe Kıyası (Fiyat çalışması: **Test Bütçe 2026-2027**)
- Not: bütçe tarafı "toplam birim maliyet"tir (malzeme + üretim gideri; pazarlama, yönetim ve finansman hariç). Fiilî tarafla aynı kapsamdadır.
- Beklenen **API ✓** (bütçe → fiilî, fark):

  | Ürün | Bütçe | Fiilî | Fark | Fark % |
  |---|---|---|---|---|
  | 03.99.002 | 31,1494 | 31,1826 | +0,0332 | +%0,11 |
  | 03.99.001 | 19,4176 | 19,7279 | +0,3103 | +%1,60 |
  | 03.99.003 | 25,0127 | 24,6762 | −0,3365 | −%1,35 |
  | 03.99.007 | 21,1477 | 21,6183 | +0,4706 | +%2,23 |
  | 03.99.004 | 24,9642 | 23,1433 | **−1,8209** | **−%7,29** |

  Yalnız bütçede 2 ürün (005, 006: SMM'de üretilmiyor). Ortalama fark −%0,94.
- Fark nedenleri:
  - Dört üründe fark %2,3'ün altında. Bunun nedeni iki reçetenin (Fiyat Çalışması ile SMM aşama reçeteleri) fire ve miktarlarının birebir aynı olmaması ve işçiliğin aşamalara farklı anahtarla dağıtılmasıdır.
  - 03.99.004'teki büyük farkın ana nedeni: Fiyat Çalışması reçetesinde **0,02 kg Test Biber Salçası** var (0,02 × 68 × 1,25 = **1,70 TL**). SMM reçetesinde (01.99.004 Domates Sos Bazı) bu satır yok. Reçeteler gözden geçirilmeli.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.8 Ürün maliyet kartı** · Bütçe Kıyası'nda 03.99.001'e tıklayın
- Beklenen: birim maliyet **19,7279**. Zincir **API ✓**:
  - 50 aşaması (03.99.001): malzeme 19,5077 · işçilik 0,1617 · fire 0,0585
  - 40 aşaması (02.99.001): malzeme 16,0257 · işçilik 0,3872 · GÜG 0,9746 · fire 0,1603 = 17,5477
  - 20 aşaması (01.99.001): malzeme 20,4609 · işçilik 0,3901 · fire 0,4092 = 21,2602
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.9 Ekim'i kapatın** · Veri Girişi › "Dönemi kapat (kilitle)" › "Kapat ve kilitle"
- Beklenen **API ✓**:
  - Eksik yok, kilitlenir.
  - Sonra bir sayım düzeltmesi "dönem kilitli" ile reddedilir (409).
  - SMM Özeti › "İndir" › Rapor (Excel) iner ve damgası **KESİN**.
  - muhasebe1 kilidi açmayı denerse: "Dönem kilidini yalnız Genel Direktör açabilir" (403).
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

### Kasım

**4.10 Canias reçeteleri** · Ana veriler › Reçeteler › "Canias ürün ağacı dökümünü yükle"
- Yapın: dosya `11-16-2026-sezon-smm-receteler-canias.xlsx`, "Önizle", sonra "Yükle".
- Beklenen: 63 satır, **14** ürün (aşama 20: 4, 40: 5, 50: 5), alternatifli ürün 1 (03.99.001: 00 ve 01), eklenecek 14. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.11 Kasım dönemi ve devir** · Dönemler › Yeni dönem aç (Kasım 2026)
- Beklenen **API ✓**:
  - 37 kalem. Devir **37 kalem, 9.564.633,84 TL** (Ekim kapanışı); "kapatılmadı" uyarısı yok.
  - Reçete kaynağı "Canias (kalıcı)".
  - Veri Girişi'nde eksikler: alım ve satış, üretim, sayım, gider mizanı.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.12 Kasım kaynaklarını yükleyin** · Veri Girişi › her satırda "Yükle"
- Yapın: 7 dosya: `11-16-2026-sezon-smm-kasim-2026-alim-satis`, `-iadeler`, `-uretim`, `-sayim`, `-sahit-numune`, `-gider-mizan`, `-stok-mizan`.
- Beklenen dolu satır: 23 · 1 · 14 · 37 · 2 · 5 · 6. Son dosyadan sonra eksik yok. **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.13 Zam fiilî maliyete ne kadar yansıdı?** · Stok ve Envanter; Üretim Maliyeti › 50
- Beklenen **API ✓**:
  - Kavanoz 370 ml ortalama fiyat 8,00 → **8,8615**. Açılış stoku eski fiyattan (8,00), Kasım alımı yeni fiyattan (9,20) geldiği için 1,20 TL'lik zammın ortalamaya yalnız yaklaşık %72'si yansır.
  - Dağıtılan 1.246.000, dağıtılmayan 66.000. Ekim'le aynı.
  - 50 aşamasında birim maliyet (Kasım, Ekim'e göre fark, üreticinin beklediği fark):

    | Ürün | Kasım | Fark | Beklenen |
    |---|---|---|---|
    | 03.99.001 | 20,6019 | +0,8740 | +0,8766 |
    | 03.99.003 | 25,5463 | +0,8701 | +0,8727 |
    | 03.99.007 | 22,4897 | +0,8714 | +0,8740 |
    | 03.99.002 | 31,1854 | +0,0028 | +0,0028 |
    | 03.99.004 | 23,1468 | +0,0035 | +0,0035 |

  - Beklenen fark = kavanoz ortalama fiyat artışı (0,8615) × 1,01 × 1,003 aşama firesi + dolar etkisi. Kuru koşu ±0,01 içinde tuttu. Kalan yaklaşık 0,003 TL'lik fark muhtemelen açılıştaki yarı mamullerin Ekim maliyetiyle girmesinden geliyor.
- İş anlamı: Fiyat Çalışması zammı birim başına 1,45 TL gösterdi (enflasyon payı ve finansman dahil, tam yıl). SMM'de Kasım'da 0,87 TL görünür, çünkü eski fiyatlı stok henüz bitmedi. Stok yenilendikçe fark büyüyecek.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.14 Kasım SMM özeti ve devir** · SMM Özeti (Kasım 2026); Veri Girişi
- Beklenen **API ✓**:
  - 710 **15.416.446,04** · üretim maliyeti 16.728.446,04 · **620 SMM 15.406.839,90**
  - Dönem sonu stok 11.122.626,84
  - Mizan farkları 150 · 151 · 152 **0,00**
  - Devir uyumlu: açılış = Ekim kapanışı = 9.564.633,84
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.15 Bütçe Kıyası Kasım** · Bütçe Kıyası (Test Bütçe 2026-2027)
- Beklenen **API ✓**. Kavanozlu ürünlerde fark Ekim'e göre +0,87 TL büyür:

  | Ürün | Fiilî | Fark | Fark % | Ekim'e göre |
  |---|---|---|---|---|
  | 03.99.007 | 22,4897 | +1,3420 | +%6,35 | +0,8714 |
  | 03.99.001 | 20,6019 | +1,1843 | +%6,10 | +0,8740 |
  | 03.99.003 | 25,5463 | +0,5336 | +%2,13 | +0,8701 |
  | 03.99.002 | 31,1854 | +0,0360 | +%0,12 | +0,0028 |
  | 03.99.004 | 23,1468 | −1,8174 | −%7,28 | +0,0035 |

  Fiilî yüksek: 4 ürün (Ekim'de 3). Ortalama fark +%1,48.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.16 Aylar arası** · Aylar Arası
- Beklenen **API ✓**:
  - 710: 15.058.521,63 → 15.416.446,04 (**+357.924,41**, +%2,38)
  - 720 ve 730: değişmedi (520.000 ve 792.000)
  - Üretim maliyeti +%2,19 · 620 SMM 15.158.553,39 → 15.406.839,90 (+%1,64)
- İş anlamı: üretim ve işçilik aynıyken ilk madde 358 bin TL arttı. Bunun nedeni kavanoz zammı ve dolar.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**4.17 Kilit kuralları** · Dönemler
- Yapın ve beklenen **API ✓**:
  1. Kasım'ı muhasebe1 ile kapatın: eksik yok, kilitlenir.
  2. direktor ile Ekim'in kilidini açmayı deneyin: **"önce Kasım 2026 kilidini açın; açılışı bu dönemden devralındı"** (reddedilir).
  3. direktor ile önce Kasım'ın, sonra Ekim'in kilidini açın. Ekim açılırken şu uyarı çıkar: "Kasım 2026 açılışı bu dönemden devralındı; değişiklik sonrası devri yenileyin".
  4. muhasebe1 ile önce Ekim'i, sonra Kasım'ı yeniden kapatın.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 5. Sezon sonu: gerçekleşen (Muhasebe → Genel Direktör)

> **Hikâye.** Sezon bitti; muhasebe yılın fiilî rakamlarını gerçekleşen kitabına işledi. Kitapta stoklu TL malzemelerin fiyatları sezonun ortalama alış fiyatlarıdır. Bütçenin öngördüğü %25 artış aynen gerçekleşmiştir (fiyat = bütçe fiyatı × 1,25). Uygulama gerçekleşen çalışmada enflasyon payı uygulamaz. Böylece TL maliyet, dört bilinen fark dışında bütçeyle birebir aynıdır:
> - kur: USD +%8, EUR +%5
> - kavanoz +%15 (Kasım zammı sürdü), Kapya Biber −%10 (iyi hasat)
> - 720 ml'de sirke firesi %2'den %5'e çıktı
> - Kornişon hattı ham madde sıkıntısıyla vardiyada hedefin %80'ini üretebildi; işçilik ve genel gider daha az ürüne bölündü
>
> **İş sorusu:** Bütçeden ne kadar saptık, neden saptık?

**5.1 Gerçekleşen kitabını yükleyin** · Veri Aktar › Tüm çalışma kitabı (muhasebe1)
- Yapın: "Yeni senaryo oluştur". Sezon `2026-2027`, Senaryo `Test Gerçekleşen 2026-2027`, Tür **Gerçekleşen**. **"Kartları güncelle" işaretini kaldırın.** Dosya `11-16-2026-sezon-fiyat-calismasi-gerceklesen.xlsx`.
- Beklenen: malzeme 32, fiyat 32, ürün 7, reçete 7, parametre 17, kart farkı yok, uyarı yok, atlanan "001 (2)". **API ✓**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**5.2 Bütçe vs Gerçekleşen** · Kıyasla › Bütçe vs Gerçekleşen (A: **Test Bütçe**, B: Test Gerçekleşen, eşik %5)
- Beklenen **API ✓** (üreticinin bağımsız hesabıyla aynı):
  - Karşılaştırılan 7, eşiği aşan **2**, ortalama sapma +%2,11

  | Ürün | Bütçe | Gerçekleşen | Fark | Sapma % |
  |---|---|---|---|---|
  | 03.99.001 | 24,5334 | 25,9943 | +1,4610 | **+5,95** (eşik üstü) |
  | 03.99.002 | 39,3510 | 39,4162 | +0,0653 | +0,17 |
  | 03.99.003 | 31,2475 | 31,6586 | +0,4111 | +1,32 |
  | 03.99.004 | 31,0661 | 31,1143 | +0,0483 | +0,16 |
  | 03.99.005 | 73,2385 | 73,2470 | +0,0085 | +0,01 |
  | 03.99.006 | 83,6189 | 83,6189 | 0,0000 | 0,00 |
  | 03.99.007 | 26,6096 | 28,5228 | +1,9133 | **+7,19** (eşik üstü) |

- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**5.3 Neden değişti? (Sapmanın kaynağı)** · Bütçe vs Gerçekleşen'de her ürüne tıklayın
- Beklenen satırlar **API ✓**. Gider ve Diğer satırları her üründe **0**.

  | Ürün | Malzeme fiyatları | Reçete | Üretim bilgileri | Döviz kurları | Enflasyon | Toplam |
  |---|---|---|---|---|---|---|
  | 001 | +5,8405 | 0 | 0 | +0,0064 | −4,3859 | **+1,4610** |
  | 002 | +5,9904 | **+0,0761** | 0 | +0,0044 | −6,0056 | **+0,0653** |
  | 003 | +4,9625 | 0 | 0 | 0 | −4,5515 | **+0,4111** |
  | 004 | +4,2900 | 0 | 0 | +0,0483 | −4,2900 | **+0,0483** |
  | 005 | +1,8930 | 0 | 0 | +0,0085 | −1,8930 | **+0,0085** |
  | 006 | +11,2927 | 0 | 0 | 0 | −11,2927 | **0** |
  | 007 | +5,8389 | 0 | **+0,4340** | +0,0248 | −4,3843 | **+1,9133** |

- Doğrulananlar **API ✓**:
  - Reçete satırı (fire) **yalnız 03.99.002'de** doludur. Ekranın Reçete bölümünde 99.11.002 Sirke'nin fire hücresi değişmiş görünür.
  - Üretim bilgileri satırı (adet) **yalnız 03.99.007'de** doludur. Üretim bilgileri bölümünde "Vardiya üretim adedi" 18000 → 14400 değişmiş görünür.
  - Döviz kurları satırı bilinen kur etkisine eşittir.
  - Her üründe satırların toplamı toplam farka kuruşu kuruşuna eşittir.
- **Nasıl okunur (önemli).** "Malzeme fiyatları" ve "Enflasyon" satırları büyük ve ters işaretlidir. Uygulama önce fiilî fiyatı bütçenin %25 enflasyonuyla bir kez daha çarpar, sonra Enflasyon satırında geri alır. Bu iki satırı **birlikte** okuyun. Reçete satırı da aynı nedenle gerçek fire etkisinin 1,25 katıdır (bulgu 2). İş diliyle dört neden şöyledir (üreticinin kapalı hesabı; uygulamanın satırlarıyla toplamı tutar **API ✓**):

  | Ürün | Kur | Fiyat | Fire | Adet | Toplam |
  |---|---|---|---|---|---|
  | 001 | +0,0064 | +1,4545 (kavanoz) | 0 | 0 | +1,4610 |
  | 002 | +0,0044 | 0 | +0,0609 (sirke) | 0 | +0,0653 |
  | 003 | 0 | +0,4111 (kavanoz +1,4545, biber −1,0435) | 0 | 0 | +0,4111 |
  | 004 | +0,0483 | 0 | 0 | 0 | +0,0483 |
  | 005 | +0,0085 | 0 | 0 | 0 | +0,0085 |
  | 006 | 0 | 0 | 0 | 0 | 0 |
  | 007 | +0,0248 | +1,4545 (kavanoz) | 0 | +0,4340 | +1,9133 |

- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**5.4 Şirket toplamı: bütçeden ne kadar saptık?** · Analiz › Kur riski (önce Test Bütçe, sonra Test Gerçekleşen); Kârlılık haritası
- Kıyasla ekranında şirket toplamı yok (bulgu 3). Toplamı iki çalışmanın "Yıllık maliyet" kartından okuyun.
- Beklenen **API ✓**:
  - Yıllık maliyet: bütçe **290.474.014** → gerçekleşen **298.175.924** → sapma **+7.701.910 TL** (%2,65)
  - Nedenlere göre (yıllık):

    | Neden | Yıllık TL | Ürün ürün |
    |---|---|---|
    | Fiyat | +7.076.680 | kavanoz (001, 003, 007) +8.203.636 · biber (003) −1.126.957 |
    | Adet | +416.616 | yalnız 007 |
    | Kur | +120.915 | 001, 002, 004, 005, 007 |
    | Fire | +87.699 | yalnız 002 |
    | **Toplam** | **+7.701.910** | |

  - Ürüne göre yıllık fark: 001 +5.259.443 · 007 +1.836.746 · 003 +443.953 · 002 +93.970 · 004 +63.707 · 005 +4.092 · 006 0
  - Uygulamanın satır toplamları (yıllık): malzeme fiyatları +48.543.181 · reçete +109.624 · üretim +416.616 · kur +120.915 · enflasyon −41.488.426. Toplamları aynı: +7.701.910.
- Kârlılık haritası (Test Gerçekleşen): yıllık kâr **29.694.076 TL**, bütçeye göre **−7.701.910**. 001 %11,37 · 003 %10,55 · 007 %7,28 · 002 %7,82 · 004 −%5,19 · 005 %29,97 · 006 %6,02.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**5.5 Şoktan sonra kalan fark** · Kıyasla › Bütçe vs Gerçekleşen (A: **Test Güncel**, B: Test Gerçekleşen)
- Beklenen **API ✓**: kavanoz ve dolar Güncel'de zaten işlendiği için kalan farklar bölüm 3'te bilinmeyenlerdir:
  - 001 0,0000 · 002 +0,0609 (fire) · 003 −1,0435 (biber) · 004 +0,0423 (EUR) · 005 +0,0085 (EUR) · 006 0 · 007 +0,4566 (adet 0,4340 + EUR 0,0226)
  - Eşiği aşan 0
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**5.6 Genel Direktör: öngörü mü, gerçekleşen mi?** · Yönetim Özeti (direktor; önce Test Bütçe, sonra Test Gerçekleşen)
- Beklenen **API ✓**:
  - Ortalama kâr marjı iki çalışmada da %20,0 (satış = maliyet × 1,20; bulgu 4)
  - Kur riski döviz payı %0,731 → %0,753
  - Fark Kur riski / Kârlılık haritası'nda okunur (5.4)
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 6. Yönetime ve müşavire rapor (Genel Direktör)

> **Hikâye.** Sezon kapandı. Gerçekleşen kesinleşir ve kilitlenir. Genel Direktör bütçeyi ve gerçekleşeni müşavire KESİN damgalı raporla gönderir. Günlükte sezon boyunca kimin neyi değiştirdiğine bakar. İzleyici rolündeki kişi yalnız okuyabildiğini doğrular. Son olarak test veritabanının yedeği alınır ve geri yüklenir.
>
> **İş sorusu:** Müşavire ne gönderiyoruz, kim neyi değiştirdi?

**6.1 Gerçekleşeni kilitleyin, raporu alın** · Kıyasla › Geçmiş kayıtlar › Test Gerçekleşen › "Kilitle"; Genel Bakış › "İndir" › Rapor
- Yapın: Neden `Sezon sonu gerçekleşen kesinleşti`. Sonra direktor ile Test Bütçe ve Test Gerçekleşen için Rapor'u Excel ve PDF olarak indirin.
- Beklenen **API ✓**:
  - Dört dosya iner (Excel yaklaşık 48 KB, PDF yaklaşık 114 KB). Damga **KESİN — çalışma kapatıldı**.
  - Dikkat: dosya adı iki çalışmada da aynı (`onay-ciktisi-fiyat-2026-2027-11-16-2026.xlsx`). İkinci indirme birincinin üzerine yazabilir (bulgu 7).
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.2 Yönetim Özeti yazdır** · Yönetim Özeti › "Yazdır / PDF" (Test Gerçekleşen)
- Beklenen: yaklaşık 2 sayfa, düzgün görünüm. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.3 Kim ne değiştirdi?** · Kontrol › Değişiklik Günlüğü
- Beklenen (kuru koşuda son 30 gün **225** kayıt; ekrandan yapılan kilit açmalar nedeniyle sizde biraz fazla olabilir) **API ✓**:
  - muhasebe1 en çok (166): içe aktarmalar, kopya, kilitler, teklifler, kur.USD parametresi, SMM yüklemeleri
  - satinalma1 (5): 99.11.010 → 68,00 ve 99.20.015 → 0,35 (Test Bütçe, "Sezon başı: eksik satın alma fiyatı"); düzenleme kilidi (Test Güncel, sayfa fiyatlar); 99.20.001 6,4 → 7,36 (Test Güncel, "Kasım revize fiyat listesi…"); şifre değiştirme
  - direktor (6): 3 kullanıcı ekleme, şifre değiştirme, Ekim ve Kasım dönem kilidini açma
  - import (36): kitapların parametreleri
- Yapın: "Kullanıcı adı" süzgecine `satinalma1` yazın; senaryoyu Test Güncel yapın. Kavanoz fiyat kaydı (6,4 → 7,36, Neden "Kasım revize fiyat listesi…") görünmeli. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.4 İzleyici yalnız okur** · izleyici1 ile
- Beklenen **API ✓**:
  - Yönetim Özeti açılır (200). Rapor indirilebilir (200).
  - Fiyat yazma ve "Düzenlemeyi aç" reddedilir (403). "Düzenlemeyi aç" düğmesi ve Veri Girişi menüsü görünmez. **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

**6.5 Yedek ve geri yükleme (test veritabanında)** · PowerShell, proje kökünde
- Yapın (yedek):
  `powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-yedekle.ps1 -AyarDosyasi test-dongusu\11-16-2026-test-ayarlar.env`
- Beklenen: "Yerel yedek: …\veri\yedek\AA-GG-YYYY-SSDDSS-yedek-test-dongusu.db", çıkış kodu 0.
- Yapın: Malzeme Fiyatları'nda Test Güncel'de bir fiyatı değiştirin ve yeni değeri not edin. Test sunucusu penceresini kapatın, sonra:
  `powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-geri-yukle.ps1 -AyarDosyasi test-dongusu\11-16-2026-test-ayarlar.env`
  Listeden az önceki yedeği seçin ve `EVET` yazın.
- Beklenen:
  - Sunucu açıkken "Port 8047 dinleniyor … geri yükleme yapılmaz" (kod 2). Kapalıyken "Geri yüklendi" (kod 0).
  - Betiğin sonundaki "baslat.ps1" önerisini **kullanmayın**: o asıl uygulamayı (8000) açar. Test ortamını `11-16-2026-test-ortamini-ac.bat` ile açın.
  - Değiştirdiğiniz fiyat eski haline dönmüş olmalı.
- Not: betikler bu kuru koşuda yeniden çalıştırılmadı; önceki test döngüsünde geçici veritabanıyla denendi (kod 2 ve kod 0). **Ekran ☐**
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

---

## 7. Kapanış

**7.1 Temizlik**
- Yapın: test sunucusu penceresini kapatın. `test-dongusu\11-16-2026-test-ortamini-sifirla.bat` çalıştırıp `EVET` yazın. `veri\yedek\*test-dongusu.db` yedeklerini elle silin.
- Beklenen: yalnız test veritabanı silinir; `veri\fiyat.db`'ye dokunulmaz.
- Sonuç: ☐ Geçti ☐ Kaldı · Not: ____

### Bulunan hatalar

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

### Kuru koşuda önceden görülen noktalar (karar bekliyor)

1. **Satın alma rolü Veri Aktar › Satın alma fiyat listesini uygulayamıyor** (1.4). Önizleme çalışıyor, "Uygula" 403 veriyor. Neden: `backend/servisler/kimlik_servisi.py` içindeki `_SATIN_ALMA_YAZAR` deseni `satin-alma/uygula` bekliyor, gerçek yol `/api/v1/aktarim/satin-alma/uygula`. Bu bir uygulama hatası; test verisinden kaynaklanmıyor.
2. **Bütçe vs Gerçekleşen ayrıştırmasında satırlar tek tek yanıltıcı** (5.3). Uygulama gerçekleşende enflasyonu 0 alıyor (doğru). Ancak sıra "fiyat → … → kur → enflasyon" olduğu için Malzeme fiyatları adımı fiilî fiyatı bütçenin %25 enflasyonuyla yeniden çarpıyor; Enflasyon adımı bunu geri alıyor. 001'de +5,84 / −4,39 TL görünüyor, gerçek fiyat etkisi +1,45. Reçete (fire) satırı da gerçek etkinin 1,25 katı. Toplamlar doğru. Öneri: gerçekleşen kıyasında enflasyon adımını fiyattan önce koymak ya da fiyat ve reçete adımlarını B'nin enflasyonuyla hesaplamak.
3. **Kıyasla ekranında şirket toplamı yok.** Yalnız ürün bazında fark ve "ortalama sapma %" var. Yıllık adetle ağırlıklı toplam sapma (7,70 milyon TL) ancak iki çalışmanın Kur riski "Yıllık maliyet" kartlarından elle çıkarılıyor.
4. **Yönetim Özeti'nde marj her zaman %20.** Satış fiyatı maliyet × 1,20 hesaplandığı için şok sonrasında da marj düşmüyor. Fiyat sabitken marj kaybı yalnız Kârlılık haritasında ve "Fiyat aynı kalırsa kâr" sütununda görülüyor.
5. **Teklif takibi yok.** Maliyet değiştikten sonra açık teklifin eskidiğine dair uyarı ya da işaret yok (3.10).
6. **Teklif tur numarası müşteriye göre değil, kayıtlı hesaba göre artıyor.** Toptan'ın ilk teklifi "3. tur" görünüyor (2.2).
7. **Rapor dosya adında çalışma adı yok.** Bütçe ve gerçekleşen raporu aynı adla iniyor (6.1).
8. **Ya olursa'da tek bir kur seçilemiyor** (3.4). Kur kutusu bütün dövizlere uygulanıyor; doların tek başına etkisi için Kur riski'ndeki para birimi kırılımına bakmak gerekiyor.
