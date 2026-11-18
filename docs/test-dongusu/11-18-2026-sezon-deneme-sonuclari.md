# Sezon senaryosu: ekran denemesi sonuçları (18.11.2026)

Senaryo: `docs/test-dongusu/11-16-2026-sezon-senaryosu.md`. Deneme Chrome üzerinden, ekrandan tıklanarak ve dosyalar dosya seçme kutusuyla yüklenerek yapıldı (Claude). Ayrı geçici veritabanı, port 8048, giriş zorunlu. Gerçek `veri/fiyat.db` ve `veri/test-dongusu.db` kullanılmadı.

Kullanıcılar: `direktor`, `muhasebe1`, `satinalma1`, `izleyici1` (her biri ayrı tarayıcı profilinde).

## Sonuçlar

| Adım | Sonuç | Not |
|---|---|---|
| 0.2 İlk giriş | Geçti | Geçici şifre ekranında geçici şifre ikinci kez soruluyor (bilinçli olabilir). |
| 0.3 Kullanıcılar | Geçti | 4 kullanıcı, ilk girişten sonra hepsi "Aktif". |
| 1.1 Bütçe kitabı | Geçti | Malzeme 32, fiyat 30, revize 0, havuz 11, ambalaj 5, ürün 7, reçete 7, parametre 17, kapasite 7, satış notu 1, atlanan 1, uyarı 0. |
| 1.2 Parametreler | Geçti | Bulgu B1. |
| 1.3 Veri Kontrolü | Geçti | Dikkat 2 (99.11.010, 99.20.015), 12 tamam, 3 elle hücre; Genel Bakış 38,83 ve 29,03. |
| 1.4 Eksik fiyatlar (satinalma1) | Geçti | **Senaryodaki bilinen hata düzelmiş:** toplu yükleme satın alma rolüyle uygulandı (2 fiyat). Geçici çözüme gerek kalmadı. Bulgu B2. |
| 1.5 Veri Kontrolü temiz | Geçti | 14 tamam, 1 bilgi. |
| 1.6 Maliyetler, satış geçmişi | Geçti | 7 ürünün maliyet ve satışı kuruşu kuruşuna aynı; 03.99.001 dökümü aynı (24,53 TL, 0,5014 USD); 168 satış satırı eklendi. |
| 1.7 Yönetim Özeti, kur riski | Geçti | Marj %20,0; yapı %74,0 / 7,2 / 2,2 / 16,7; kur etkisi 212.382 TL; yıllık maliyet 290.474.014 TL; EUR 163.303 / USD 49.080. Bulgu B6. |
| 1.8 Kârlılık haritası | Geçti | Bölgeler ve marjlar aynı; yıllık kâr toplamı 37.395.987 TL (elle toplandı). Bulgu B4. |
| 1.9 Önemli malzemeler | Geçti | 213.769.000 TL, 9 malzeme, kavanoz %21,3, koli kümülatif %80,8. Bulgu B5. |
| 1.10 Liste çalışması | Geçti | 18 satır; 46,73 / 74,95 / 50,68; liste artışı −%6,4 / %2,8 / −%4,2. |
| 1.11 Kopya + kilit | Geçti | Kopya sayıları aynı; Test Güncel Genel Bakış'ı bütçeyle aynı; kilitli bütçede fiyat düğmeleri pasif, API 409 "senaryo kilitli". Bulgu B3, B7. |
| 2.1 Hesabı kaydet | Geçti | Düğmenin adı artık "Güncel hesabı kaydet" (teklif panelinde). Hesap #1, 24,53 TL. |
| 2.2 Teklif turları | Geçti | 29,44 / 28,70 / 29,44 TL; tur no 1, 2, 3 (Toptan "Tur 3", bilinen bulgu 6). USD 2 hane gösteriliyor (0,60). |
| 2.3 Durumlar | Geçti | Süzgeç Tümü 3, Taslak 0, Gönderildi 1, Kabul 1, Red 1. "Gönderildi" onay sormuyor, Kabul/Red soruyor. |
| 2.4 Taslak rapor | Geçti | 47 KB, 15 sayfa, her sayfada "TASLAK — çalışma kapatılmadı". İndir penceresinde 4 seçenek var (senaryodaki 3 + "Fiyat Çalışması Excel'i"). Bulgu B7, B8. |
| 3.1 Zam etkisi | Geçti | 3 ürün, her biri +1,45; 25,99 / 28,06 / 32,70; fiyat aynı kalırsa kâr %13,3 / %13,8 / %14,7. |
| 3.2 Revize liste (satinalma1) | Geçti | Değişen 1, aynı 31, revize 1; "1 fiyat yazıldı"; büyük değişiklik uyarısı çıkmadı. |
| 3.3 Ölçülen = gerçekleşen | Geçti | Yalnız 001, 003, 007 değişti: 25,99 / 32,70 / 28,06. |
| 3.4 Dolar +%8 | Geçti | Ya olursa 5 ürün etkilenir; Kur riski %8 etkisi 169.906 TL, EUR 130.642, USD 39.264. |
| 3.5 USD parametresi | Geçti | Şok sonrası 25,99 / 39,36 / 32,70 / 31,07 / 73,24 / 83,62 / 28,07. |
| 3.6 Direktör görünümü | Geçti | Yıllık maliyet 298.716.914 TL; yıllık kâr toplamı 29.153.087 TL; bölgeler 3 / 1 / 1 / 2; Yönetim Özeti marj %20,0; "Yazdır / PDF" yazdırmayı çağırıyor. Bulgu B9. |
| 3.7 Marjı koruyan fiyat | Geçti | 6 / 7 zam gerekli, ort. %9,3, ek gelir 34.100.925 TL; hedef fiyatlar ve liste fiyatları (49,51 / 74,96 / 53,46) aynı. |
| 3.8 Önce / sonra | Geçti | Malzeme 17,7586 → 18,9761, kavanoz 1,2121, dolar 0,0053; maliyet 24,5334 → 25,9943. Bulgu B10. |
| 3.9 Fiyat eğilimi | Geçti | Kavanoz 6,40 → 7,36, %15,0, "Normal"; 0 malzeme enflasyonu aşıyor. |
| 3.10 Açık teklif eskidi | Geçti | Yönetim Özeti'nde 1 açık teklif: Test Toptan, Gönderildi, 29,44 TL. "Teklif eskidi" uyarısı yok (beklenen; Serkan Bey'in 9. önerisi). |

## Bulgular

Hata değil, kullanıcıyı şaşırtabilecek noktalar; düzeltilip düzeltilmeyeceği Esma'nın kararı.

- **B1 · Parametreler:** "Dağıtım çarpanları" bölümünde geliştirici dili görünüyor: "Faz 3", "Salt okunur: dağıtım çarpanları Faz 3 kapsamında yönetilecek". Değerlerin hepsi "—".
- **B2 · Veri Aktar, satın alma rolü:** Satın alma kullanıcısı tüm sekmeleri (Tüm çalışma kitabı, Gider dağıtım, Ürün reçetesi…) görüyor; yetkisi olmayan işlemler ancak uygulamada reddediliyor olabilir.
- **B3 · Arşiv kartı:** Test Bütçe kartında son yüklenen dosyanın adı (`…satin-alma-eksik-fiyatlar.xlsx`) açıklama gibi duruyor; ne olduğu yazmıyor.
- **B4 · Kârlılık haritası:** Aile adları küçük harf ve Türkçe karakter hatalı ("test karişik turşu"). Tabloda toplam satırı yok; yıllık kâr toplamını görmek için elle toplamak gerekiyor.
- **B5 · Önemli malzemeler:** "Birim fiyat" sütunu liste fiyatını gösteriyor (kavanoz 6,40 TL), yıllık tutar ise enflasyonlu fiyatla (8,00 TL) hesaplanıyor. Miktar × birim fiyat, yıllık tutarı vermiyor.
- **B6 · Yönetim Özeti:** Aynı sayfada iki ayrı "hedef" var: "Ortalama kâr marjı · hedef %20" (satış kâr oranı) ve "Hedefin altındaki ürünler · %10 eşik" (marj eşiği).

- **B7 · Kopyalanan çalışmada Excel şablonu yok:** "Geçen sezondan kopyala" ile açılan Test Güncel'de İndir › "Fiyat Çalışması Excel'i" için "Bu çalışma için şablon yok" yazıyor; bütçedeki şablon kopyaya geçmiyor.
- **B8 · İndir › Rapor:** "Excel (formüllü)" seçeneği "Yakında" etiketiyle görünüyor (bitmemiş özellik kullanıcıya açık). İnen dosyanın adı hâlâ `onay-ciktisi-…xlsx`; ekrandaki adı "Rapor".
- **B9 · Yönetim Özeti, Açık teklifler kartı:** "1 · toplam 29 TL · 3 teklif" yazıyor. "Toplam 29 TL" birim fiyatların toplamı (anlamsız bir tutar); "3 teklif" ile büyük "1" yan yana kafa karıştırıyor.
- **B10 · Kayıt kıyası:** İki kayıt seçilince yeni kayıt A, eski kayıt B oluyor; "Fark (B − A)" eksi çıkıyor (−1,2175). Önce/sonra okumak için ters; fark "sonra − önce" olmalı.

## Senaryo belgesinde güncellenecekler

- 1.4: "Uygula reddedilir" beklentisi artık geçersiz; satın alma rolü toplu fiyat listesini uygulayabiliyor.
- 2.1: düğmenin adı "Hesabı kaydet" değil, "Güncel hesabı kaydet" (Teklif turları bölümünde).
- 2.4: İndir penceresinde 4 seçenek var.

## 2. deneme: direktör hesabıyla ayrıntılı deneme (18.11.2026 öğleden sonra)

Ortam: yeni test veritabanı `test-dongusu/deneme/11-18-2026-direktor-deneme.db` (uydurma veri, git dışı), port 8048, giriş zorunlu. 0-3. bölümlerin verisi `scripts/11-18-2026-direktor-deneme-hazirla.py` ile API üzerinden yüklendi. Ekle / değiştir / sil denemeleri Test Güncel'in kopyası olan "Test CRUD 2026-2027" (#3) üzerinde yapıldı.

### Düzeltmelerin kontrolü (B1-B10)

Hepsi ekranda düzelmiş görüldü. B8'de bir eksik kaldı: PDF raporun içindeki başlık hâlâ "Fiyat Çalışması Onay Çıktısı" (bkz. D14). Ayrıca 38 ekran geliştirici dili için tarandı; yalnız Değişiklik Günlüğü'nde teknik ifade kaldı (D5).

### Doğru çalışanlar

- Giriş: yanlış şifre reddediliyor. Pasifleştirilen kullanıcının açık oturumu hemen kapanıyor. Son direktörün rolü düşürülemiyor.
- Kullanıcı adı kuralları: tekrar eden ad, boşluk ve Türkçe karakter reddediliyor; büyük harf küçültülüyor.
- Kilit: kilitli bütçenin raporu "KESİN, Kapatan: muhasebe1", TASLAK damgası yok. Kilitsiz çalışmanın raporu Excel ve PDF'te her sayfada TASLAK damgalı. PDF dosya adı `rapor-fiyat-…`.
- Parametrede negatif sayı, harf ve boş neden reddediliyor; liste böleni 1'in üstünde reddediliyor. Parametre "Geri al" doğru çalışıyor.
- Yeni ürün → reçete → üretim bilgisi akışı çalışıyor. Ürün Genel Bakış'a, Yönetim Özeti'ne (8 ürün), Liste çalışmasına, Zam etkisine ve Kârlılık haritasına doğru yansıyor.
- Ürün ekranında hücre değiştir → Kaydet (neden + hesabı da kaydet) doğru.
- Malzeme fiyatında %15'i aşan değişiklik uyarı veriyor. Değişiklik yalnız o çalışmayı etkiliyor; kullanan ürünler, fiyat eğilimi ve önemli malzemeler güncelleniyor. Geri al tam eski haline getiriyor.
- Satış satırı ekle/sil → Kârlılık haritası ve Marjı koruyan fiyat hemen değişiyor.
- Teklif ekle → durum → sil → Teklifler ve Yönetim Özeti tutarlı.
- Stokta kalan ekle/değiştir/kaldır: ortalama maliyet elle hesapla aynı (26,20 TL). Genel Bakış ve Yönetim Özeti'nde stok etkisi görünüyor. "Satış ortalamadan" açılınca satış, liste, hedef fiyat ortalamadan hesaplanıyor ve ürün ekranında not çıkıyor.
- Gider havuzunda pay toplamı %100 değilse kayıt engelleniyor. Değişiklik yalnız ilgili hattın ürünlerine yansıyor.
- Liste fiyatı (geçmiş yıl) ekle/değiştir/sil → artış oranları hemen değişiyor.
- Kayıtlı hesabı olan çalışma silinemiyor.

### Yeni bulgular (önem sırasıyla)

**Yüksek**
- **D1 · Parametrelerde makul değer kontrolü yok.**
  - USD kuru **0** kabul edildi.
  - Enflasyona **250** yazınca uyarısız **%25.000** olarak kaydedildi.
  - Kutu oran istiyor (0,25 = %25); kullanıcı alışkanlıkla 25 yazarsa %2.500 olur.
  - Bu iki giriş 03.99.001'in maliyetini 25,99 TL'den **3.531 TL**'ye çıkardı. Veri Kontrolü yalnız kur için uyarı verdi.
- **D2 · Yönetim Özeti gerçek marjı göstermiyor.** "Marj eşiğinin altında ürün yok" diyor; oysa Kârlılık haritasında geçen yılın satış fiyatıyla 3 ürün eşiğin altında (003 %7, 004 −%5, 007 %9). Özet, satış fiyatını maliyet × 1,20 aldığı için marj hep %20 çıkıyor. Direktör yanlış güvene kapılabilir (senaryodaki bulgu 4).
- **D3 · Reçeteye satır eklemenin ve silmenin kolay yolu yok.** Ürün ekranında yalnız miktar, fire, brüt ve fiyat değişiyor. Veri Aktar › Elle reçete girişi bütün reçeteyi baştan yazdırıyor; ürün kodu girilince mevcut satırlar gelmiyor.
- **D4 · Kabul edilmiş teklif silinebiliyor.** Silinen teklif günlükte kalıyor.

**Orta**
- **D5 · Değişiklik Günlüğü'nde ham veri görünüyor:**
  - `senaryo_id: 2`, `enflasyon: None`, `atlanan_kayitli: 0`.
  - Kod çıktıları: `{'yurtici': '0.63'}`, `anahtarlar: [["Kavanoz Hattı", "0.55", …]]`.
  - 26 haneli sayılar: `maliyet 30.81388087306671547542783930 TL`.
  - Nokta ondalık: `6.4 → 7.36`.
- **D6 · Hata mesajlarında teknik ekler var:**
  - "— kullanici_adi: muhasebe1"
  - "üretim hedefi yok — urun: 03.99.008; senaryo_id: 3"
  - "— senaryo_id: 3; hesap_sayisi: 1"
  - "— bolen: 1.5"
  - Mesajların bir kısmı küçük harfle başlıyor.
- **D7 · "Neden" sorulmayan değişiklikler:** reçete kaydı (ilk ve yeni versiyon), satış satırı ekleme/silme, liste fiyatı ekleme/silme, teklif silme. Günlüğe nedensiz düşüyorlar.
- **D8 · Onay sormayan işlemler:** kullanıcı pasifleştirme, şifre sıfırlama, rol değiştirme, liste fiyatı silme.
- **D9 · İzleyici yetkisinin olmadığı düğmeleri görüyor.** "Yeni çalışma" düğmesini görüyor ve formu doldurabiliyor; ancak en sonda "İzleyici rolünün bu işleme izni yok" ile reddediliyor.
- **D10 · Gider havuzunda toplam değişince diğer kalemler de değişiyor.** "Tutarla" modunda toplam değiştirilince öbür alt kalemlerin tutarı kendiliğinden ölçekleniyor (1.500.000 → 1.750.000); pay toplamı %106 çıkıyor.
- **D11 · Teknik anahtarlar ekranda görünüyor:**
  - Havuz adlarında: "Amortisman (amortisman)", "Dolum doğrudan işçilik (dolum_iscilik)".
  - Parametre özetinde: "satis_kar", "liste_bolen_yurtici".
  - Liste böleni yüzde gibi gösteriliyor (1,5 → "%150").

**Düşük**
- **D12 · Geri alma da uyarı açıyor:** Fiyat geri alma "büyük değişiklik" uyarısını tetikliyor; üst üste üç pencere açılıyor.
- **D13 · Üretim bilgileri kartı:** "Kaydet" Neden boşken pasif ama nedenini söylemiyor. Neden kutusu onay kutusunun altında gözden kaçıyor.
- **D14 · Rapor PDF:** Başlık "Fiyat Çalışması Onay Çıktısı", ekrandaki adı "Rapor". "Uygulama sürümü 5ee1527" gibi kod sürümü görünüyor. Kopyalanan çalışmada "Kaynak dosya kaydı yok".
- **D15 · Pasif kullanıcı mesajı:** giriş ekranı "kullanıcı adı ya da şifre yanlış" diyor.
- **D16 · Erişilebilirlik:** Satış Geçmişi › Satır ekle formunda etiketler alanlara bağlı değil (ekran okuyucu).
- **D17 · İngilizce sözcük:** Ürün ekranında "dashboard" geçiyor ("bu çalışmanın dashboard ve hesaplarına").
- **D18 · Geri alınamayan işlemler (bilgi):** Gider havuzu değişikliği, stokta kalan, satış ve liste fiyatı silme günlükten geri alınamıyor; elle yeniden girmek gerekiyor.

### Kritik bulguların düzeltilmesi (18.11.2026 akşam, ekranda doğrulandı)

- **D1 · Düzeltildi.**
  - Yüzde parametreler yüzde olarak giriliyor ("25" = %25).
  - Sunucu reddediyor: kur ≤ 0, eksi kâr, %300 üstü oran, 0 vardiya. Mesajlar sade.
  - %100 üstü oran ve kurda %50'den büyük değişim "Değer olağan dışı görünüyor · Yine de kaydet" onayı istiyor.
  - Veri Kontrolü'ne "Olağan dışı parametre" eklendi.
  - Bölen "0,65" olarak gösteriliyor, özette okunur ad var.
- **D2 · Düzeltildi.** Yönetim Özeti "%9,8 geçen yılın satış fiyatıyla", küçük satırda "Hesaplanan satış fiyatıyla %20". Marj eşiğinin altında 5 ürün listeleniyor (002, 003, 004, 006, 007); Kârlılık haritasıyla aynı.
- **D3 · Düzeltildi.**
  - Ürün ekranında her satırda "Sil" ve tablonun altında "Satır ekle" var.
  - Kaydet penceresi "Satır silindi / Satır eklendi" diye listeliyor; neden zorunlu, yeni reçete versiyonu açılıyor (v4), Genel Bakış güncelleniyor.
  - Veri Aktar › Elle reçete girişinde "Mevcut reçeteyi getir" satırları dolduruyor; Neden alanı var.
  - **Kalan küçük nokta (D3b):** Satır ekle formunda öneriden seçmeden yazılan metin (ör. "Etiket 370") malzeme kodu sayılıp reçeteye 0 TL ile ekleniyor; uyarı yok.
- **D4 · Düzeltildi.** Kabul edilmiş teklifin "Sil" düğmesi pasif, ipucunda neden yazıyor; sunucu 409 "Kabul edilmiş teklif silinemez; önce durumunu değiştirin."

Kontroller: frontend `tsc` temiz, `vitest` 72 dosya / 658 test geçti. Ajanların koştuğu ilgili backend testleri (247 + 204) geçti; tam pytest süiti koşulmadı.

### Acil düzeltmeler 2. tur (18.11.2026 akşam, ekranda doğrulandı)

Kontrol betiği: `test-dongusu/deneme/11-18-2026-acil-duzeltme-kontrol.cjs`. 12 kontrolün 12'si geçti.

- **D3b · Düzeltildi.** Satır ekle'de olmayan kod reddediliyor: "Bu kodda malzeme yok; önce Veri Girişi › Yeni malzeme ile açın." Sunucu da 422 veriyor.
- **D5 · Düzeltildi.**
  - Günlük okunur Türkçe: "Maliyet: 28,27 TL", "Sayfa: /urunler/…".
  - Parametre başlığı okunur adla yazılıyor ("Parametre: Enflasyon öngörüsü"); değer %25 olarak görünüyor.
  - Kullanıcı kayıtları "Kullanıcı kendi şifresini değiştirdi" diye görünüyor.
  - Ham `_id`, `None`, sözlük dökümü ve uzun ondalık kalmadı.
- **D6 · Düzeltildi.** Hata mesajları teknik ek olmadan, kendi başına anlaşılır; örnek: "muhasebe1 kullanıcı adı zaten var; başka bir ad seçin." Backend'de yaklaşık 200 mesaj elden geçti.
- **D7 · Düzeltildi.** Neden zorunlu oldu: satış satırı ekle/sil, geçmiş liste fiyatı ekle/değiştir/sil, teklif silme. Neden günlükte görünüyor.
- **D8 · Düzeltildi.** Pasifleştirme, etkinleştirme, şifre sıfırlama ve rol değişikliği onay soruyor; Vazgeç'te hiçbir şey değişmiyor.
- **D9 · Düzeltildi.**
  - İzleyicide "Yeni çalışma" ve çalışma menüsü gizli, sayfalarda "Salt okunur: izleyici rolü değişiklik yapamaz" yazıyor.
  - Satın alma yalnız Malzeme Fiyatları, Veri Aktar › Satın alma ve Veri Girişi'ndeki malzeme/fiyat kartlarında düzenleyebiliyor; diğer sayfalarda salt okunur.

Kontroller: frontend `tsc` temiz, `vitest` 72 dosya / 669 test geçti. Backend'de ilgili testler geçti (son birleştirmede `test_faz5_gunluk` ve `test_kimlik` 34 geçti); tam süit koşulmadı.

## Bölüm 4-7: SMM, gerçekleşen, raporlar (18.11.2026 akşam)

Sezon kuru koşusu, bugünkü düzeltmelerin üzerinde baştan sona koşturuldu. Betik `test-dongusu/kuru_kosu_sezon.py`'nin kopyası; veritabanı `veri/` yerine `test-dongusu/deneme/` altında. Kopya: `test-dongusu/deneme/11-18-2026-kuru-kosu-sezon.py`, sonuç dosyası: `test-dongusu/deneme/11-18-2026-sezon-kuru-kosu-sonuclari.json`.

**Sonuç: 206 kontrolün 206'sı tuttu, hata 0.** Düzeltmeler hiçbir hesabı bozmadı.
- Ekim ve Kasım SMM kapanışları geçti. SMM Kasım 15.406.839,90 TL. Stok mizanı ile sayım farkı 0. Devir uyumlu.
- Kilit sırası doğru: Kasım kilitliyken Ekim'in kilidi açılamıyor ("Önce Kasım 2026 kilidini açın…").
- Gerçekleşen kitabı içe aktarıldı.
- Bütçe ile gerçekleşen farkı 7.701.910,16 TL ve dört nedene doğru ayrışıyor: kur 120.915,07, adet 416.616,00, fire 87.699,25, fiyat 7.076.679,84.
- Raporlar: kilitli bütçe ve gerçekleşen için Excel ve PDF iniyor, Excel "KESİN" damgalı.
- İzleyici rapor indirebiliyor ama fiyat yazamıyor ve kilit açamıyor (403).

**SMM ekranları:** Test sunucusunda Ekim dönemi yüklenip 8 SMM ekranı muhasebe1 ile tarandı (`11-18-2026-smm-ekran-tarama.cjs`). Hepsinde hata ya da geliştirici dili yok.

**Küçük kalanlar (düşük önem):**
- Günlük'te birkaç ham değer kaldı: "Rol: satin_alma", "Metin parametresi: satis_fiyati_notu", "Sayfa: fiyatlar" / "Sayfa: /urunler/03.99.008".
- Kullanıcı ekleme gibi genel olaylar her çalışmanın günlük süzgecinde de görünüyor.
- SMM Üretim Maliyeti kartlarında Excel kıyası olmayan dönemde "Excel'le 0/0 aynı" yazıyor.

## Kalan

SMM ekranlarında elle ekle/değiştir/sil denemesi (stok kalemi düzeltme, mizan elle girişi, üretim süresi) yapılmadı. Test sunucusu 8048'de açık; veritabanı `test-dongusu/deneme/11-18-2026-direktor-deneme.db`.
