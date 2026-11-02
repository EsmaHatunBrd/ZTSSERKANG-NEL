# Fiyat Çalışması Otomasyonu — Muhasebe Direktörüne Sorular

Tarih: 21.10.2026
Kaynak: `Fiyat Çalışma - 2026-2027 - Berrak.xlsx` incelemesi ve sistemin kurulumu sırasında ortaya çıkan noktalar.
Her soruda: neden sorduğumuz, Excel'de nereye bakılacağı ve sistemin **şu anki varsayılan davranışı**. Cevap gelene kadar sistem bu varsayılanlarla çalışıyor ve ilgili yerlerde uyarı gösteriyor.

Önerilen görüşme sırası: 1-3 kritik (rakamları değiştirir), 4-7 önemli (ekran ve kural), 8-12 bilgi/doğrulama, 13 ek özellik tercihleri.

---

## A. Kritik — cevabı maliyet rakamlarını değiştirir

### 1. Fiyatı boş olan 299 malzeme: eksik veri mi, bilerek 0 mı?
- **Neden:** `S.ALMA BF` sayfasında 833 malzemenin 299'unun fiyatı boş (`F` sütunu). Ürün sayfalarındaki formül fiyat bulamayınca sessizce **0 TL** yazıyor; o satırın maliyeti 0 çıkıyor. Bir kısmı ara mamul (salamura, turşu) olduğu için bilerek 0; bir kısmı eksik veri olabilir.
- **Excel'de bakılacak yer:** `S.ALMA BF` → `F` sütununu "boş" diye filtreleyin. Ürün sayfasında etkisi: `001` sayfası `M12`, `M18`, `M19` → 0; `P12`, `P18`, `P19` tutarları 0.
- **Sorular:** (a) Hangi malzeme tipleri bilerek fiyatsız (ara mamul)? (b) Hammadde/ambalaj olup fiyatı boş olanlar için fiyat nereden gelecek? (c) Reçetede ürünün kendi kodu da bir satır olarak geçiyor (57 sayfada 6. satır) — bu satır bilerek mi?
- **Şu an sistem:** 0 TL alıyor ve "fiyat listesinde yok" uyarısı veriyor; ürünün kendi satırı ve ara mamul satırları için uyarı susturuluyor.

### 2. Z/S bayrağı ne anlama geliyor; taze hammaddeye neden enflasyon uygulanmıyor?
- **Neden:** `S.ALMA BF` `G` sütunu ("Departman") her malzemeyi `Z` (79 malzeme, çoğu `10.` kodlu taze hammadde) veya `S` (754 malzeme) olarak işaretliyor. Formül: `S` + TL fiyat → fiyat × (1 + %25 enflasyon); `S` + döviz → fiyat × kur; `Z` → fiyat olduğu gibi, enflasyon ve kur yok.
- **Excel'de bakılacak yer:** `001` sayfası `P13` (kavanoz, S, 5,9 TL → 7,53 enflasyonlu) ile `P17` (taze biberiye, Z, 65 TL → 12,36 enflasyonsuz) karşılaştırması. Formül `P8` hücresinde.
- **Sorular:** (a) Z ve S açılımı nedir (Ziraat/Satınalma? İç üretim/Satın alınan?). (b) Taze hammaddeye enflasyon uygulanmaması bilinçli mi (sezonluk fiyat, zaten güncel)? (c) Z bayraklı ama **döviz fiyatlı 2 malzeme** var; `043` ve `044` sayfalarında kullanılıyor ve biri `N14` hücresine elle "s" yazarak kuru zorlamış. Doğrusu: kur uygulansın mı?
- **Şu an sistem:** Excel'le aynı (Z → kur ve enflasyon yok), ancak Z + döviz durumunda uyarı veriyor.

### 3. Sayfadan sayfaya değişen finansman parametreleri: ürün bazlı karar mı, hata mı?
- **Neden:** 66 sayfada stok süresi 6 ay; `012` ve `013`'te TL için 2 ay; `040`'ta tüm para birimleri için 2 ay. Faiz %40 (TL) / %6 (döviz) her yerde aynı.
- **Excel'de bakılacak yer:** `012` sayfası `K124` (2) ile `001` sayfası `K124` (6).
- **Sorular:** (a) Bu üç ürün gerçekten daha hızlı mı dönüyor (bilinçli), yoksa unutulmuş bir değişiklik mi? (b) Stok süresi ürün bazında mı belirlenmeli, ürün grubuna göre mi?
- **Şu an sistem:** Sezon varsayılanı 6 ay; bu üç ürün için **ürün bazlı override** olarak 2 ay taşındı (değiştirilebilir, geçmişi tutulur).

---

## B. Önemli — ekran davranışını ve kuralları belirler

### 4. Fire kuralı: varsayılanlar doğru mu, kim değiştirebilmeli?
- **Neden:** Excel'de fire oranları tutarsız girilmiş (bazı satırlarda yazılı ama uygulanmamış, bazılarında yazılmadan uygulanmış). Karar verildi: elle yazılan değer elle kalır, fire yazılan satırda fire uygulanır. Sistem yeni satırlar için **tip bazlı varsayılan** fire kullanıyor.
- **Excel'den çıkan dağılım:** etiket/kapak/kavanoz/shrink/levha/karton/koli/şişe/teneke → %2 (yüzlerce satır), folyo (torba) → %4, taze hammadde → bazı satırlarda %5, yardımcı malzeme → %0.
- **Sorular:** (a) Bu varsayılanlar doğru mu? (b) Taze hammaddede %5 fire hangi durumda uygulanıyor? (c) Fire oranını kim değiştirebilmeli; değişiklik için "neden" zorunlu olsun mu?
- **Şu an sistem:** Tip varsayılanları yukarıdaki gibi; reçete satırında elle değer > grup kuralı > malzeme kuralı > tip kuralı önceliği; her değişiklik tarih ve nedenle kaydediliyor.

### 5. Kâr oranları: satış fiyatı %20 ile teklif turları (%20/17/14) ayrı mı kalsın?
- **Neden:** Excel'de satış fiyatı `P137 = P130 × 1,2` (sabit %20, TL üzerinden); teklif turları ise USD maliyet üzerinden ayrı hücrelerde (%20, %17, %14). Siz "ayrı kalsın" dediniz; teyit istiyoruz.
- **Sorular:** (a) Satış fiyatındaki %20 ile 1. teklifin %20'si aynı şey mi? (b) Teklif turu genelde 3'te bitiyor dediniz; 4. tur olabilir mi, asgari kâr sınırı var mı? (c) Teklif yalnızca USD mi, TL/EUR teklif de verilir mi?
- **Şu an sistem:** İki ayrı parametre; tur sayısı sınırsız; asgari kâr kontrolü yok.

### 6. [KAPANDI] Sağ blok (Z-AO sütunları) - sağ blok deneme, önemsiz — kullanıcı 22.10
- Kapandı: sağ blok deneme, önemsiz — kullanıcı 22.10.2026. Eski not: **Neden:** Sağ blok sol bloğun kopyası ama bağımsız değil (`AL131` sol bloğun `P122/P125` hücrelerini okuyor), bazı girdileri farklı (`001`: vardiya adedi solda 65.000, sağda 61.846; `AA138` 14 sayfada 1.000.000), bir sayfada kırık referans (`AA145` → `#REF!`). Siz "firesiz hesap" dediniz.
- ~~Sorular~~ kapandı (gerek yok): **Sorular:** (a) Sağ bloktaki farklı girdiler eski/bayat veri mi? (b) Firesiz hesap raporlarda nerede kullanılıyor (teklif kapak Q sütunu)? (c) Teklif Kapak'ta hangi sütun müşteriye gidiyor: fireli mi firesiz mi?
- **Şu an sistem:** Firesiz hesap aynı üretim girdileriyle, tüm fireler 0 alınarak üretiliyor ve tek tabloda fireli tutarın yanında gösteriliyor.

### 7. Yurtdışı ürünler: yüzde ve finansman kuralı nasıl?
- **Neden:** Her ürün sayfasında `P2` hücresi "Yurtiçi"; Excel'de hiç "Yurtdışı" örneği yok. Formüller Yurtdışı için USD üzerinden yüzde ve %6 döviz finansmanı kullanıyor ama doğrulanamadı.
- **Sorular:** (a) İhracat ürünleri için ayrı sayfa var mı? (b) Yurtdışı fiyat hangi para biriminde, finansman hangi oranla? (c) "İhracat destekleri düşülmemiş" notu (`G137`) ne anlama geliyor; destek düşülmeli mi?
- **Şu an sistem:** Yurtdışı seçilirse hesap yapılır ama "doğrulanmadı" uyarısı gösterilir.

---

## C. Bilgi ve doğrulama

### 8. 056-067 sayfalarındaki ürünlerin ERP kodu yok
- **Neden:** Bu 12 sayfada ürün kodu hücresi (`D6`) boş; başlıktaki kod ilk reçete satırından geliyor. Ürün adları relish, şekerleme, "ARG." kodlu malzemeler — ARGE ürünleri gibi görünüyor.
- **Sorular:** (a) Bunların ERP kodları var mı, atanacak mı? (b) Teklif çalışmasına dahil mi, yoksa deneme mi?
- **Şu an sistem:** `SAYFA-056` gibi geçici kod; gerçek kod gelince tek tıkla yeniden adlandırma.

### 9. Gider dağıtımındaki çarpanlar ve pay toplamları
- **Neden:** Havuz toplamları formülde sabit çarpanlarla hesaplanıyor (örn. `D4 = 49.024.334,97 × 1,35 × 1,3`; `D27 = (10.875.000 + 3.571.433) × 1,4 × 1,25`). Elektrik payları toplamı %100,1 (`G38`), doğalgaz %99,5 (`G49`).
- **Sorular:** (a) 1,35 / 1,3 / 1,4 / 1,25 gibi çarpanlar ne (zam, enflasyon, kapasite)? Her sezon kim günceller? Ekranda hangi isimle görünsün? (b) Elektrik/doğalgaz payları düzeltilsin mi?
- **Şu an sistem:** Havuz toplamı hesaplanmış değer olarak giriliyor; çarpanlar parametre olarak hazır ama kullanılmıyor (isim bekliyor). Pay toplamı %100 değilse kırmızı uyarı.

### 10. "Geçen sene aynı malı kaça sattım" verisi nerede?
- **Neden:** Karlılık ve enflasyon karşılaştırması için gerekli. Fiyat Çalışma dosyasında yok.
- **Sorular:** (a) ERP'den mi, ayrı Excel'den mi gelecek? (b) Müşteri bazında mı, ürün bazında mı? (c) Hangi para biriminde?
- **Şu an sistem:** Tablo hazır, veri yok; karşılaştırma ekranı Faz 5'te.

### 11. Ekrandaki 4,15066 değeri
- **Neden:** Teklif bloğunun sağında, formüle bağlı olmayan bir sayı (3,736 USD'nin yanında). Yan hesap gibi görünüyor.
- **Soru:** Bu nedir, sistemde bir alan olarak gerekli mi?

### 12. Mal kabul miktarı hangi reçete satırına bağlı?
- **Neden:** `I104` (mal kabul kg) Excel'de bir reçete satırına (`K17`, taze hammadde) bağlı. Birden fazla taze hammaddesi olan üründe hangisi alınmalı belirsiz.
- **Soru:** Mal kabul miktarı = taze hammaddelerin toplamı mı, ilk satır mı?
- **Şu an sistem:** Sayfadaki değer aynen alınıyor; reçete değişirse otomatik güncellenmiyor.

### 13. `S.ALMA BF` sayfasındaki ikinci "Bütçe Birim Fiyatları" sütunu (I) nedir?
- **Neden:** Sayfada iki fiyat sütunu var: `F` ("Bütçe Birim Fiyatları") ve `I` (aynı başlık). 833 malzemenin 290'ında ikisi farklı. Sistem şu an yalnızca `F`'yi kullanıyor (ürün sayfalarındaki VLOOKUP da `F`'yi okuyor).
- **Sorular:** (a) `I` sütunu ne (eski bütçe, gerçekleşen, alternatif teklif)? (b) Sistemde ikinci fiyat olarak tutulmalı mı?
- **Şu an sistem:** `I` okunmuyor.

---

### 14. Üretim Adetleri sayfasındaki kodlar ürün kodlarıyla eşleşmiyor (23.10 eklendi)
- **Neden:** `Üretim Adetleri` sayfasında 71 kayıt `02.…` kodlu (örn. 02.045.007.002.00001 Dikenli H. Turşu No:2 1700 ml Berrak); ürün sayfaları `03.…` kodlu (aynı ürün 03.045.007.002.00183). Kod bazında hiçbiri eşleşmediği için "hedef adetle maliyet" hesaplanamıyor.
- **Sorular:** (a) 02 ve 03 önekleri ne (yarı mamul / mamul, farklı ERP kodlama)? (b) Ürün adına göre eşlemek doğru mu, yoksa bir kod dönüşüm tablosu var mı? (c) Üretim Adetleri sayfasındaki "Hedef üretim" ile ürün sayfasındaki "Vardiya üretim adedi" arasındaki ilişki ne?
- **Şu an sistem:** İki veri ayrı tutuluyor; Veri Girişi'nde ikisi ayrı kart; hedef adet etkisi boş.

## D. Ek özellik tercihleri (hangisi işinize yarar?)

Excel'de olmayan, servis katmanının üstüne kolayca eklenebilecekler. Sıralamanızı istiyoruz:

1. **Toplu "ne olur":** "USD 55 olursa 67 ürünün fiyatı ne olur", "kavanoz %10 zamlanırsa hangi ürünler etkilenir."
2. **Malzeme etki listesi (ters reçete):** bir malzemenin fiyatı değişince etkilenen ürünler ve tutarları — satın alma pazarlığı için.
3. **Hata/tutarsızlık paneli:** fiyatsız malzemeler, %100 olmayan paylar, fire yazılı-uygulanmamış satırlar, reçetesiz ürünler — hepsi tek ekranda (büyük kısmı zaten "Uyarılar" sayfasında var).
4. **Teklif çıktısı:** müşteriye giden PDF/Excel teklif formu, kayıtlı hesaba bağlı.
5. **Asgari kâr kırmızı çizgisi:** teklif turu belirlenen kârın altına inerse onay zorunluluğu.
6. **Ürün ailesi karşılaştırması:** aynı ürünün 370/720/1700 ml'lik hallerinin kg fiyatı ve kârı yan yana.
7. **Sezon kopyalama:** yeni sezona geçerken parametre ve reçeteleri kopyalayıp yalnızca değişenleri güncelleme.

---

## Görüşme notları için boş alan

| # | Cevap | Karar | Sistemde yapılacak |
|---|---|---|---|
| 1 | | | |
| 2 | Z = Ziraat'ten (kendi tarımından) gelen, enflasyon yok. S = satın alma; yalnız TL fiyatlılara enflasyon, dövizlilere kur. (23.10) | Hesap aynen kalır | Etiketler "Ziraat / Satın alma", Yardım'a açıklama (Faz 5b G2) |
| 3 | Stok süresini kendisi arayüzden günceller, sorun değil. (23.10) | Kapalı | — |
| 4 | Fire varsayılanları arayüzden değiştirilebilir olsun yeter. (23.10) | Kapalı (zaten öyle) | — |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | Çarpanları kullanıcı arayüzden güncelleyebilmeli; gider kalemleri Excel yüklemeden kalem bazında da girilebilmeli. (23.10) | Elle giriş sayfası + çarpanlar | Faz 5b G1: taban × çarpanlar, alt kalem tutar girişi, Veri Girişi sayfası |
| 10 | | | |
| 11 | | | |
| 12 | — | — | — |
| 13 | I sütunu sonradan yapılan güncellemeler; F eski değer, eskiyi görebilmek için sağa yazılıyor. (23.10) | Her revizyon fiyat geçmişine ayrı kayıt; hesap en günceli kullanır | Faz 5b G2: I okunur, "İlk bütçe / Revize" sütunları, süzgeç |
| Gerçekleşen | Gerçekleşen Excel aynı düzende, yalnız değerler farklı. (23.10) | Faz 6 planı geçerli | Dosya bekleniyor |
| D | | | |
