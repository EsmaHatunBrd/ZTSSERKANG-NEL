# Faz 5b — Muhasebe cevapları: Z/S etiketi, elle veri girişi, S.ALMA BF revize fiyat

Tarih: 23.10.2026 · Durum: **onaylandı** (kullanıcı: "oki yap bakalım") · Sıra: Z/S → elle giriş → revize fiyat

## Muhasebe direktörünün cevapları (23.10 telefon)
- **Z/S:** Z = Ziraat'ten (kendi tarımından) gelen malzeme, enflasyon uygulanmaz. S = satın alma; yalnız TL fiyatlılara enflasyon, dövizlilere kur. → Hesap zaten böyle; yalnız etiket ve açıklama.
- **S.ALMA BF ikinci fiyat sütunu (I):** sonradan yapılan güncellemeler; soldaki (F) eski değer. Eskiyi görebilmek için sağa yazıyor. → Her revizyon fiyat geçmişine ayrı satır; hesap en güncel fiyatı kullanır.
- **Elle giriş:** Gider dağıtım kalemleri gibi şeyleri yalnız Excel'den değil arayüzden kalem bazında girebilmeli; tek bir giriş sayfası istiyor.
- Stok süresi (2 ay olan 3 ürün) ve fire varsayılanları: zaten arayüzden değiştirilebiliyor, iş yok.
- Gerçekleşen Excel aynı düzende, değerler farklı → Faz 6 planı geçerli (dosya bekleniyor).

## Görevler

### G1 — Gider Dağıtım elle giriş + çarpanlar + Veri Girişi sayfası (backend + arayüz)
Backend:
- `GiderHavuzu`'na `taban_tutar` (ParaTipi, null olabilir) ve `carpanlar` (JSON metin: `[{"ad": "...", "deger": "1.35"}, ...]`) kolonları; `EKSIK_KOLONLAR` ile ALTER. `toplam_tutar` = `taban_tutar × Π çarpan` (taban verilmişse sunucu hesaplar; verilmemişse eski davranış: toplam doğrudan girilir).
- `HavuzGiris`: `taban_tutar?`, `carpanlar?: [{ad, deger}]`, anahtarlar için `tutar?` alternatifi (`pay_orani` yerine alt kalem tutarı; sunucu pay = tutar / toplam). `pay_orani` ya da `tutar`dan biri zorunlu. Pay toplamı %100'den sapıyorsa mevcut `pay_kontrol` davranışı korunur.
- Değişiklik kaydı eski/yeni'ye taban ve çarpanları da yazar; günlükte görünür (gunluk_servisi `_havuz` satırı kontrol).
- Mevcut `dagitim_carpani.*` parametreleri kullanılmıyor; **dokunma**, belgele (kaldırma ayrı karar).
Arayüz:
- `HavuzDiyalogu`: üstte "Taban tutar × çarpanlar = Gider Toplamı" bloğu (çarpan ekle/sil, ad + değer; canlı sonuç); alt kalemlerde **tutar girişi** (TL) ve otomatik pay %; istenirse pay % de doğrudan yazılabilir (sekme: "Tutarla" / "Yüzdeyle"); alt kalem ekle/sil; baz miktar.
- `HavuzKarti`: çarpan varsa özet satırında `taban × 1,35 × 1,30 = toplam` gösterimi.
- Yeni sayfa **Veri Girişi** (`/veri-girisi`, menü VERİ grubu en üstte): tek sayfada kartlar: Gider havuzları (havuz seç → aynı diyalog), Malzeme fiyatı (kod ara → yeni fiyat + tarih + neden; mevcut `MalzemeFiyatlari` mutasyonunu yeniden kullan), Parametre (anahtar seç → değer + tarih + neden), Üretim hedefi/kapasite (ürün seç → mevcut düzenleme formu). Her kart kaydedince ilgili sorgular tazelenir. Kilitli senaryoda `KilitSeridi` + pasif.
- Yardım'a yeni satır (metnini final raporda ver; `Yardim.tsx`'i **G2 düzenler**, çakışma olmasın).
Testler: backend (taban×çarpan, tutar→pay, değişiklik kaydı), vitest (diyalog canlı hesap, Veri Girişi kartları), tsc, build; Playwright'a 1 senaryo (havuz tutarla kaydet).

### G2 — S.ALMA BF revize fiyat (I sütunu) + Z/S etiketleri (backend + arayüz)
Backend:
- `_satin_alma_oku` ve `import_servisi` (tam kitap) `I` sütununu `revize_fiyat` olarak okur (boş/eşit → yok). Uygula: `F` → `fiyat_ekle(..., gecerlilik_basi, neden="İlk bütçe (S.ALMA BF F)", kaynak="import")`; `I` farklıysa → ikinci kayıt aynı gün, `neden="Revize (S.ALMA BF I)"`, `kaynak="import-revize"`, **geçerli olan bu**. Aynı gün iki kayıt: `gecerli_fiyatlar` en son eklenen kazanmalı (id sırası) — doğrula, gerekiyorsa sıralamayı düzelt. Mevcut veritabanında tekrar yükleme: önizleme `fiyat_degisen`'e düşer, çift kayıt üretmez.
- Önizleme çıktısına `revize` sayısı ve listesi (`kod, ilk, revize`).
- Malzeme listesi API'sine `ilk_fiyat` (senaryodaki en eski kayıt) ve `revize` (bool: geçerli ≠ ilk) alanları; süzgeç `?revize=1`.
- Parite: `tests/backend` parite testi F ile çalışıyorsa, revize fiyatların Excel'den sapma yaratacağı bilinir; parite testini "ilk bütçe" tarihine göre (revize öncesi tarih) çalıştır ya da fixture'da I=F tut. Hangisini seçtiğini raporla.
Arayüz:
- `MalzemeFiyatlari`: "Z/S" sütunu → başlık **"Kaynak"**, değer `Z → "Ziraat"`, `S → "Satın alma"`, tooltip: "Ziraat: enflasyon uygulanmaz · Satın alma: TL fiyata enflasyon, dövize kur". Yeni sütunlar **"İlk bütçe"** ve **"Revize"** (geçerli fiyat; ilkinden farklıysa rozet "revize"), süzgeç "Yalnız revize edilenler". Geçmiş çekmecesi zaten var; revize kayıtları orada da görünür.
- `ReceteTablosu` Z/S sütunu → "Kaynak" (Ziraat / Satın alma).
- Veri Aktar → Satın alma sekmesi önizlemesinde "Revize edilen: N" satırı.
- `Yardim.tsx`: Z/S açıklaması + revize fiyat + G1'in Veri Girişi satırı.
- Uyarı metinleri: "Z bayraklı döviz" uyarısı → "Ziraat kaynaklı ama döviz fiyatlı: kur uygulanmaz, kontrol edin".
Testler: backend (I okuma, iki kayıt, geçerli = revize, tekrar yükleme çift yazmaz), vitest (sütunlar, süzgeç), tsc, build.

## Kurallar
- Kullanıcının 8000/5180 sunucularına dokunma; e2e 8010/5190; tip üretimi G1: 8020, G2: 8030.
- Şirket verisi fixture'a girmez. Decimal metin. Neden zorunlu. Değişiklik günlüğüne düşer.
- Dosya çakışması: `Yardim.tsx` yalnız G2; `yonlendirme.tsx`, `Kabuk.tsx` yalnız G1; `MalzemeFiyatlari.tsx` yalnız G2 (G1 Veri Girişi'nde fiyat kartı için ayrı bileşen yazar, mevcut hook'ları kullanır); `sema.d.ts` her iki ajan kendi uçlarından sonra yeniden üretir, son üreten tam üretir.
- Süreç: implementer → reviewer → düzeltme → kontrolör final; ledger `scratchpad/sdd-faz5b/progress.md`.

## Kapsam dışı
- Yeni havuz kodu ekleme (motor dağıtım kuralları sabit kodlara bağlı).
- `dagitim_carpani.*` parametrelerinin kaldırılması.
- Faz 6 (gerçekleşen kıyası) — dosya bekleniyor.
