# Faz 5 Kapanış Raporu — Karşılaştırma, Performans, Veri Aktar, Günlük/Arşiv

Tarih: 22.10.2026 · Plan: `docs/10-22-2026-faz5-karsilastirma-ve-performans-plani.md` · Durum: **kapandı** (final inceleme + 1 düzeltme dalgası; kritik yok)

## Kullanıcı gözüyle ne geldi
- **Dashboard hızlı:** ilk açılış ~1,6 sn (eskiden ~7 sn), sonrası anlık; herhangi bir kayıt yapılınca kendiliğinden tazelenir.
- **Zeytursan teması:** logo (Serkan Bey'in e-posta imzasından), kurumsal yeşiller, simgeli gruplu menü, özet kartları, zebra tablolar; kompakt ölçek (14 px).
- **Veri Aktar** (eski "Reçete Aktar"): altı sekme — Tüm çalışma kitabı (yeni senaryo / mevcut senaryoyu tamamla), Satın alma fiyat listesi, Üretim adetleri, Gider dağıtım, Satış geçmişi, Ürün reçetesi. Her biri: dosya → önizleme (yeni / değişen / aynı / hatalı) → neden → uygula; tam kitap ya da tek sayfalık Excel kabul edilir; yanlış dosya reddedilir.
- **Satış Geçmişi** sayfası: geçen yıl satışları (şablon indir, CSV/xlsx yükle, satır ekle/sil).
- **Karşılaştırma:** dashboard'da Geçen yıl (TL) · Enflasyon eşiği rozeti (altında/üstünde, fark %) · Hedef adetle maliyet; ürün ekranında Karşılaştırma kartı (geçen yıl, eşik, hedef adet) ve ürün ailesi rozeti (düzenlenebilir); yeni **Karşılaştırma** sayfası: aile seç → ambalaj büyüdükçe birim fiyat ve kg fiyatı tablosu + grafik.
- **Satış fiyatı tablosu** ürün ekranında Excel düzeninde (para birimi · kur · fiyat; süzme kg fiyatı; 3 teklif).
- **Teklif Kapak xlsx**: Teklifler sayfasından indir; Excel'in sütun düzeniyle, hedef adetli ikinci blok dahil.
- **Değişiklik Günlüğü**: tüm kaynaklardan tek akış (parametre, fiyat, fire, reçete sürümü, hesap, teklif, ürün kartı, hedef, havuz, kapasite, satış), süzgeçler, geri al, Excel'e aktar, son 7 gün özeti.
- **Arşiv**: sezon → senaryo (tür, tarih, kaynak dosya, kilit) → tarihli kayıtlı hesaplar; iki kaydı yan yana kıyas; **Kilitle/Kilidi aç** (neden zorunlu; kilitli senaryoda yazma uçları 409, ekranlarda sarı şerit ve pasif düğmeler; kilit senaryoya bağlı kayıtları korur, ürün/malzeme kartı gibi senaryodan bağımsız veriler değişebilir).
- **Yardım** sayfası: ana menüde değil, sağ üstteki "?" simgesinden (kullanıcı isteği: ulu orta olmasın).
- **Otomatik günlük yedek**: her açılışta `veri/yedek/AA-GG-YYYY-otomatik-fiyat.db`, son 14 gün.

## Teknik
- Backend: `onbellek.py` (nesil sayaçlı süreç içi önbellek, yazma isteklerinde temizlenir), `satis_servisi/okuyucu`, `aile.py` (aile türetme, ambalaj etiketi/ml), `karsilastirma_servisi` (geçen yıl ağırlıklı ortalama, enflasyon eşiği, hedef adet etkisi, aile trendi; tek sorgu), `aktarim_servisi` + `/aktarim/*`, `/disa-aktar/teklif-kapak.xlsx`, `Urun.aile` + `Senaryo.kaynak_dosya/kilitli` (ALTER ile), günlük/arşiv servisleri. Tam süit: 326 test (`-W error`) + Task D (19) + yedek (3) + final düzeltme testleri; son hedefli koşular yeşil.
- Frontend: tema token'ları, `Kabuk` gruplu menü, `SayfaBasligi`, `UstKartlar`, `Karsilastirma` + `AileGrafigi`, `KarsilastirmaKarti`, `AktarimFormu` + 3 sarmalayıcı, `SatisGecmisi`, `Gunluk`, `Arsiv`. Vitest 330+, tsc 0, build ok, Playwright 23/23 (dashboard beklemesi 15 sn).
- Canlı veri: kullanıcı isteğiyle 22.10 15:4x veritabanı boşaltıldı; tam yedek `veri/yedek/10-22-2026-bosaltma-oncesi-fiyat.db`.

## Kontrolörün kararları (yanlışsa düzeltin)
1. Geçen yıl fiyatı = adet ağırlıklı ortalama; döviz fiyatına enflasyon uygulanmaz (Excel kuralı); satış geçmişi gelene kadar sütunlar "—".
2. Ürün ailesi ürün adından türetilir (ı/İ/I → i katlama), elle düzeltilebilir; Excel'in Ambalaj hücresi birim tutarsız (ml/lt/kg) ve sınıf eşlemesi için aynen kalır; görünüm için addan `ambalaj_etiket`, sıralama için `ambalaj_ml`.
3. Dashboard önbelleği tek süreç varsayımıyla; `/hesapla` ve fiyat listesi önizlemesi önbelleği boşaltmaz; TTL 10 dk; `?yenile=1`.
4. Teklif Kapak'ta hedef üretim 0 veya hesap hatası olan üründe ikinci blok boş kalır, dosya düşmez; P sütunu (kaynağı belirsiz oran) boş.
5. Gider oranı/ambalaj gibi veri tipleri yalnız "Veri Aktar" ile; Malzeme Fiyatları'ndaki eski fiyat listesi yükleme düğmesi de kalır.
6. İkinci "Vardiya Saati" hücresi formüllerde ayrı kullanılmadığından tek alan.
7. Grafik: çift eksen yerine ortak x eksenli iki panel (dataviz tek eksen kuralı).
8. Dış yazı tipi isteği yok (Manrope yerel paket); grafik yeşili beyaz zeminde bir ton koyu (kontrast).

## Ertelenenler (final inceleme; teslimi engellemez)
- Aile düzenleme diyaloğu anahtarı düzenler (görünen ad değil); elle yazılan anahtar adı gibi görünür.
- Satış Geçmişi ve ürün/malzeme kartı yazımları senaryo kilidinden etkilenmez (kapsam notu eklendi).
- Günlük birleşik akış bellek içinde (≈10-50 bin satıra kadar). (Tarih sınırlarının UTC kayması 22.10 akşamı düzeltildi: yerel gün.)
- Veri Aktar: tüm-sıfır kuralı için önizleme testi yok; başarı sonrası önizleme kalıyor; boş hücre kart alanını eziyor; `_gecici` özel import.
- Önbellek: nesil sayacı global; çoklu işçi desteklenmez (belgelendi).
- Teklif Kapak: hat sıralaması Türkçe harfe duyarsız; çift kapasite kaydında son kazanır; sessiz except loglamıyor.
- Dashboard enflasyon süzgeci yalnız yüklü sayfayı süzer (etiketi öyle der). ("Reçete Aktar" metinleri 22.10 akşamı "Veri Aktar" yapıldı.)
- axe erişilebilirlik taraması yapılmadı (mevcut e2e: konsol hatası/taşma/odak kontrolleri).
- `GecmisCekmecesi` (sheet) ve `DialogClose` ref uyarıları (önceden mevcut).
- Muhasebe direktörüne açık sorular sürüyor (`docs/10-21-2026-muhasebe-direktoru-sorulari.md`).
