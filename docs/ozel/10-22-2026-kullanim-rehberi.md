# Fiyat Çalışması — Kullanım Rehberi (Muhasebe)

Adres: `http://<sunucu>:5180` · Üstte **Senaryo** seçilir (sezon · ad · tür); tüm sayfalar seçili senaryoyu gösterir.

## Excel'deki yerin burada karşılığı
| Excel'de | Burada |
|---|---|
| Teklif Kapak sayfası | **Dashboard** (ürün listesi, maliyet/satış, uyarılar; "Teklif Kapak indir" Teklifler sayfasında) |
| Ürün sayfaları (001…067) | **Ürün Maliyeti** → ürün seç: reçete, gider kalemleri, toplamlar, finansman, üretim bilgileri, kurlar, satış fiyatı tablosu, teklifler |
| S.ALMA BF | **Malzeme Fiyatları** (geçmişli); yükleme **Veri Aktar → Satın alma fiyat listesi** |
| Gider Dağıtım | **Gider Dağıtım** (havuzlar, paylar, ambalaj sınıfları); yükleme **Veri Aktar → Gider dağıtım** |
| Üretim Adetleri | **Üretim Adetleri**; yükleme **Veri Aktar → Üretim adetleri** |
| Enflasyon, kurlar, faiz, stok süresi, kâr oranları | **Parametreler** (tarihli geçmiş) — ürün ekranındaki kutulardan da değişir |
| Ambalaj Özeti | Dashboard'da "Ambalaj özeti" kartı |
| (yok) | **Satış Geçmişi**, **Karşılaştırma**, **Değişiklik Günlüğü**, **Arşiv** |

## Yeni sezon / yeni çalışma
1. **Veri Aktar → Tüm çalışma kitabı → Yeni senaryo oluştur**: Excel dosyasını seçin, sezon adı (örn. 2026-2027), senaryo adı, tür (Fiyat çalışması / Gerçekleşen) → İçe aktar (≈1 dk).
2. Aynı senaryoya sonradan eksik tablo eklemek için **Mevcut senaryoyu tamamla**.
3. Tek bir sayfayı güncellemek için ilgili sekme (satın alma / üretim adetleri / gider dağıtım): dosya → **Önizle** (yeni / değişen / aynı / hatalı) → neden yazın → **Uygula**. Tam kitap da tek sayfalık Excel de olur.

## Ürün ekranında çalışma (Excel alışkanlığı)
- Hücreye yazın (miktar, fire %, brüt, birim fiyat, gider oranı, kur, faiz, üretim bilgileri): **hesap anında yenilenir**, henüz kaydedilmez.
- Üst şeritte **"N değişiklik · Kaydet · Vazgeç"**. **Kaydet** → değişiklik listesi ve etki (Bu ürün / Senaryo geneli) → **Neden** yazmak zorunlu → **Onayla ve kaydet**. Neden boşsa onay düğmesi pasiftir.
- Senaryo geneli parametreler (kur, enflasyon) tüm ürünleri etkiler; diyalogda "yalnız bu ürün için yaz" seçilebilir.
- Kaydedilen her hesap numaralı ve tarihlidir; teklif turları kayıtlı hesaba bağlanır (Teklif turları kartı).
- Sağ üst **Uyarılar**: fiyatsız malzeme, fire kuralı vb.

## Diğer sayfalar
- **Karşılaştırma**: ürün ailesi seç → ambalaj büyüdükçe birim fiyat ve kg fiyatı; dashboard'da geçen yıl / enflasyon eşiği (Satış Geçmişi yüklüyse) ve hedef adetle maliyet.
- **Satış Geçmişi**: "Şablonu indir" → doldur → yükle (ürün kodu, müşteri, tarih, fiyat, para birimi, adet).
- **Değişiklik Günlüğü**: kim, ne zaman, neyi, neden; süzgeç; geri al; Excel'e aktar.
- **Arşiv**: sezon → senaryo → tarihli kayıtlı hesaplar; iki kaydı kıyasla; **Kilitle** (kapanan sezon değiştirilemez).
- **Teklifler**: senaryo geneli teklif listesi, durum; **Teklif Kapak indir** (Excel düzeni).

## Yedek
- Her açılışta günlük otomatik yedek: `veri/yedek/AA-GG-YYYY-otomatik-fiyat.db` (son 14 gün). Geri dönmek için servisi durdurup yedeği `veri/fiyat.db` olarak kopyalayın.
