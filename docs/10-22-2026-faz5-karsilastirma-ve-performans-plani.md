# Faz 5 — Karşılaştırma ve Performans Uygulama Planı

Tarih: 22.10.2026 · Durum: **onaylandı (22.10.2026 "ok"), uygulanıyor**
Spec: `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` (§2 ek analizler, §4 `satis_gecmisi`, §8 açık soru 5) · Tasarım: `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` (`karsilastirma_servisi` imzaları, `/karsilastirma`)
Önceki: Faz 4c (`docs/10-22-2026-faz4c-kapanis-raporu.md`).

## 1. Hedef
Kullanıcının ilk notlarındaki "karşılaştırma" istekleri + dashboard hızı:
1. **Dashboard hızlı açılsın** (bugün ~7 sn; 67 ürün her açılışta canlı hesaplanıyor).
2. **Geçen yıl kaça sattım** → bu yılki fiyatla yan yana; **enflasyona göre altında/üstünde** rozeti.
3. **Ambalaj büyüdükçe birim/kg fiyat trendi** (aynı ürün ailesi: 370 ml → 720 ml → 2,5 kg…).
4. **Üretim adedi etkisi**: Excel Teklif Kapak'ın ikinci "Birim Maliyet" bloğu (bütçe adedi yerine Üretim Adetleri'ndeki hedef adetle maliyet; oran sütunu).
5. **Teklif Kapak dışa aktarımı**: Excel'in Teklif Kapak düzeninde xlsx (muhasebeye verilecek dosya).

## 2. Varsayımlar (muhasebe cevabı gelince düzeltilir)
- **Geçen yıl verisinin kaynağı belli değil** (soru 5). Plan: `satis_gecmisi` tablosu (zaten var) CSV/xlsx ile yüklenir; şablon indirilebilir: `urun_kodu, musteri, tarih, fiyat, para_birimi, adet`. ERP bağlantısı yok. Satır elle de girilebilir.
- "Geçen yıl fiyatı" = önceki sezon (sezon başlangıcından 12 ay geri) satışlarının **adet ağırlıklı ortalaması**, para birimi bazında; müşteri süzgeci isteğe bağlı.
- **Enflasyon eşiği** = yeni satış fiyatı ÷ (geçen yıl fiyatı × (1 + enflasyon)). TL için senaryo enflasyonu; döviz için eşik 1 (döviz fiyatına enflasyon uygulanmaz, Excel kuralı). < 1 → "enflasyonun altında" (kırmızı), ≥ 1 → "üstünde" (yeşil); fark %.
- **Ürün ailesi** = ürün adından hacim ifadesi (`370 ml`, `720 ml`, `2,5 kg`, `5lt`, `1700 ml`…) ve ambalaj sözcükleri (`Pet`, `Torba`, `Cam`) temizlenince kalan kök; `urun.aile` alanı (nullable) ile elle düzeltilebilir.
- Kg fiyatı = mevcut `suzme_kg_fiyati` (satış fiyatı ÷ süzme kg).

## 3. Görevler
| # | Görev | Kapsam | Model |
|---|---|---|---|
| T1 | **Dashboard önbelleği**: `backend/servisler/onbellek.py` — senaryo+tarih anahtarlı bellek içi sonuç; her yazma isteğinde (POST/PUT/DELETE, import) middleware ile boşaltılır; TTL 10 dk; `GET /urunler?yenile=1` zorla; yanıt başlığında `X-Onbellek: isabet/hesap`. Hedef ikinci açılış < 0,5 sn. e2e bekleme sabiti 45 sn → 15 sn'ye geri. | `backend/uygulama.py`, `backend/api/urunler.py` (yalnız `listele`), yeni servis, testler | sonnet |
| T2 | **Satış geçmişi**: `GET/POST /satis-gecmisi` (liste, sayfalı; toplu yükleme CSV/xlsx; satır ekle); `GET /satis-gecmisi/sablon` (boş şablon). Yeni sayfa **Satış Geçmişi** (yükle, tablo, satır ekle). | backend `satis_servisi.py`, `api/satis.py`; frontend `sayfalar/SatisGecmisi.tsx` | sonnet |
| T3 | **Karşılaştırma servisi + uçlar**: `karsilastirma_servisi.gecen_yil(urun)`, `enflasyon_esigi(urun)`, `ambalaj_kg_trendi(aile)`, `uretim_adedi_etkisi(urun)` (hedef adetle yeniden hesap: motor aynı, `vardiya_uretim_adedi` yerine Üretim Adetleri `hedef_uretim`); `GET /karsilastirma/urun/{kod}`, `GET /karsilastirma/aile/{aile}`, `GET /karsilastirma/aileler`. `urun.aile` kolonu (ALTER ile), import'ta addan türetme. | backend servis/API/model, testler (motor değişmez) | sonnet |
| T4 | **Ekranlar**: Dashboard'a sütunlar "Geçen yıl", "Enf. eşiği" (rozet + %), "Hedef adetle maliyet" (gizlenebilir sütun grubu); ürün ekranına "Karşılaştırma" kartı (geçen yıl, eşik, aile trendi mini grafik); yeni sayfa **Karşılaştırma**: aile seçimi → ambalaj hacmine göre kg fiyatı ve birim fiyat çizgi/çubuk grafiği (Recharts, dataviz kuralları), tablo. | frontend | sonnet |
| T5 | **Teklif Kapak xlsx**: `GET /disa-aktar/teklif-kapak?senaryo=` — Excel'in sütun düzeni (Grup, S.No, kod, ad, reçete maliyeti, GÜG, faaliyet, finans, toplam, gider %, birim maliyet TL/USD/EUR, üretim adedi; ikinci blok hedef adetle); Teklifler sayfasına "Teklif Kapak indir" düğmesi. | backend `disa_aktar.py` (openpyxl), frontend düğme | sonnet |
| T6 | Final inceleme (opus) + kapanış raporu | — | opus |

## 4. Doğrulama
- T1: aynı senaryo için ikinci `GET /urunler` süresi < 0,5 sn (test ölçer); herhangi bir PUT sonrası ilk istek yeniden hesaplar; `yenile=1` zorlar.
- T2: şablon → yükle → liste; hatalı satır (bilinmeyen ürün kodu, negatif fiyat) satır numarasıyla 422.
- T3: elle kurulmuş geçmişle ağırlıklı ortalama; eşik < / ≥ 1; aile türetme örnekleri ("X Turşu 370 ml Berrak", "X Turşu 2,5 kg Torba Berrak" → aynı aile); hedef adet etkisi = motorun aynı girdiyle hesabı (1e-9).
- T4: MSW ile sütunlar/rozetler; Karşılaştırma grafiği veri → nokta sayısı; e2e: Karşılaştırma sayfası açılır, aile seçince grafik gelir.
- T5: üretilen xlsx'in başlıkları Excel Teklif Kapak satır 2-3 ile aynı; ilk ürün satırı canlı hesapla birebir.

## 5. Kararlar / riskler
1. Önbellek bellek içi (tek süreç, SQLite varsayımıyla uyumlu); çoklu işçi (`--workers`) kullanılmaz.
2. Geçen yıl verisi gelene kadar karşılaştırma sütunları "—" gösterir; rozet çıkmaz.
3. Aile türetme sezgisel; yanlış eşleşme `urun.aile` ile düzeltilir, uyarı listesine "aile tek üyeli" girer.
4. Teklif Kapak'taki ikinci blokta Excel'in oran sütunu (örn. 0,95) = hedef adet ÷ bütçe adet; kaynağı kesinleşmediği için başlıkta "Üretim Adetleri hedef" diye yazılır.
