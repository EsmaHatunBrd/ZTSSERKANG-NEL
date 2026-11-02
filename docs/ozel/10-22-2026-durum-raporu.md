# Fiyat Çalışması Otomasyonu — Durum Raporu

Tarih: 22 Ekim 2026 · Hazırlayan: Esma Akbulut (BT) · Kapsam: Zeytursan Berrak serisi fiyat çalışması

## 1. Özet
Muhasebenin yıllık fiyat çalışması Excel'i (67 ürün, 833 malzeme, gider dağıtımı, finansman, teklifler) web tabanlı bir uygulamaya **eksiksiz** taşındı. Excel'deki 67 ürün sayfasının tamamı birebir aynı sonucu veriyor (otomatik parite testi). Uygulama şirket içi sunucuda çalışıyor; Excel'e göre ek olarak değişiklik geçmişi, karşılaştırma analizleri, çoklu senaryo ve arşiv sağlıyor.

## 2. Bugün itibarıyla hazır olanlar
| Alan | Durum |
|---|---|
| Hesap motoru (reçete, fire, gider dağıtımı, finansman, kur, satış fiyatı, teklif turları) | Tamam; Excel ile birebir |
| Ürün ekranı: hücreye yaz → anında hesap → tek **Kaydet** (neden zorunlu, geçmiş tutulur) | Tamam |
| Teklif Kapak (dashboard) + Excel çıktısı | Tamam |
| Veri yükleme: tüm çalışma kitabı; ayrı ayrı satın alma fiyat listesi, üretim adetleri, gider dağıtımı, satış geçmişi | Tamam (önizleme → onay → uygula) |
| Parametreler (enflasyon, kurlar, faiz, stok süresi, kâr oranları) tarihli geçmişle | Tamam |
| Karşılaştırma: geçen yıl fiyatı, enflasyonun altında/üstünde, ambalaj büyüdükçe kg fiyatı, hedef adetle maliyet | Tamam (geçen yıl verisi yüklenince dolar) |
| Değişiklik Günlüğü (kim, ne zaman, neyi, neden; geri al) | Tamam |
| Arşiv: sezon → senaryo → tarihli kayıtlar; sezon kilidi | Tamam |
| Zeytursan kurumsal görünüm, Yardım sayfası | Tamam |
| Günlük otomatik yedek | Tamam |
| Performans: ana ekran açılışı ~1,6 sn, sonrası anlık | Tamam |

Kalite: 330 arayüz testi, 326+ sunucu testi, 23 uçtan uca tarayıcı testi; tümü geçiyor. Her faz bağımsız kod incelemesinden geçti.

## 3. Sırada
1. **Gerçekleşen kıyası (Faz 6):** gerçekleşen değerlerle doldurulmuş Excel gelince, bütçe ile gerçekleşen ürün ürün yan yana; sapmanın kaynağı (fiyat / miktar-fire / gider / kur). Plan hazır, dosya bekleniyor.
2. Kullanıcı tercihine göre: kaydetmeden önce etki önizlemesi, kullanıcı girişi ve roller, kur simülasyonu, hammadde etki haritası, müşteriye PDF teklif, hızlı arama.

## 4. Muhasebeden beklenenler
- Gerçekleşen Excel dosyası.
- "Geçen yıl kaça sattım" verisinin kaynağı (ERP mi, ayrı liste mi); şimdilik şablonla yükleniyor.
- Açık sorular listesi (13 madde: fiyatsız malzemeler, Z/S bayrağı, yurtdışı finansman kuralı, 2 aylık stok süresi olan 3 ürün vb.) için kısa bir görüşme.

## 5. Riskler / notlar
- Tek sunucu, SQLite; çok kullanıcılı yoğun kullanımda geçiş gerekebilir (şimdilik yeterli).
- Kullanıcı girişi henüz yok (isim seçimi var); dışa açmadan önce eklenmeli.
- Kilitli sezon korunur; ürün/malzeme kartı gibi senaryodan bağımsız veriler kilitten etkilenmez.
- Bugün veritabanı test amacıyla sıfırlanıp yeniden yüklendi; önceki verinin tam yedeği saklı.
