# Faz 6 — Bütçe vs Gerçekleşen: Kapanış Raporu

Tarih: 27.10.2026 · Plan: `docs/10-22-2026-faz6-gerceklesen-kiyas-plani.md` · Onay: "faz6yı yap"

## Yapılanlar
1. **Deneme gerçekleşen Excel'i** — `10-27-2026-gerceklesen-deneme-2026-2027.xlsx`. Asıl kitabın kopyası; yalnız elle girilen 1302 hücre
   olası gerçek değerlerle değişti (malzeme fiyatları, fiili kur USD 52,85 / EUR 61,40, enflasyon 0, vardiya adetleri, bazı reçete
   miktar/fireleri, gider havuzu tabanları). Excel'in kendisi yeniden hesapladı. Üretim: `scripts/10-27-2026-gerceklesen-deneme-uret.py`
   (değişiklik listesi) + `scripts/10-27-2026-excel-hucre-yaz.ps1` (Excel COM). Asıl dosya değişmedi.
2. **Backend** — `servisler/kiyas_servisi.py`, `api/kiyas.py`, `api/kiyas_semalari.py` (şema adları `Bg…`):
   - `GET /kiyas?a=&b=&esik=` ürün başına A | B | fark | fark % (reçete, GÜG, faaliyet, finans, maliyet TL/USD, satış TL/USD), önbellekli.
   - `GET /kiyas/urun/{kod}` reçete eşlemesi (malzeme kodu + sıra), gider kalemleri, üretim bilgileri, parametreler, sapma ayrıştırması.
   - `GET /kiyas/karsi?senaryo=` aynı sezonun karşı senaryosu; `GET /disa-aktar/butce-gerceklesen.xlsx`.
   - Sapma ayrıştırması zincirleme ikame: malzeme fiyatları → reçete → üretim bilgileri → gider oranları → kurlar → enflasyon → diğer.
     Toplamı toplam farka tam eşittir (etkileşim, sıradaki bloğa düşer).
3. **Arayüz** — menü "Bütçe vs Gerçekleşen": A/B seçici (varsayılan: seçili senaryo + aynı sezonun karşılığı), eşik (±%5, URL'de),
   "Yalnız sapanlar", Excel'e aktar, özet kutucukları, sapma dağılımı grafiği, tablo; satıra tıklayınca ürün ekranı (sapmanın kaynağı,
   toplamlar, reçete ve giderler yan yana, değişen hücre vurgulu). Genel Bakış'ta karşı senaryo varsa tek satır özet şeridi.
4. **3 yıllık deneme veritabanı** — `veri/10-27-2026-deneme.db` (`scripts/10-27-2026-deneme-verisi-uret.py`): 2024-25, 2025-26, 2026-27;
   her sezonda bütçe + gerçekleşen, geçmiş sezonlar kilitli; 2887 uydurma satış kaydı (Deneme Market / Toptan / İhracat).
   Port 8001'de açılır. Canlı veritabanına yazılmaz.
5. **Ek düzeltme** — üst çubuktaki senaryo seçici uzun çalışma adında 768 px'te taşıyordu; genişlik 40vw ile sınırlandı.

## Doğrulama
- Gerçekleşen paritesi: deneme kitabı "Gerçekleşen" türüyle yüklenince 67 ürünün hesabı Excel hücreleriyle birebir (bütçedeki bilinen
  Excel istisnaları dışında).
- Testler: pytest 447, vitest 404, e2e 27 (yeni: `e2e/butce-gerceklesen.spec.ts` — Excel'i arayüzden yükler, listeyi/detayı/şeridi açar).
- Deneme sonuçları: sapan ürün (±%5) 15 / 19 / 26; ortalama maliyet sapması +%2,5 / +%2,8 / +%3,4.

## Plandan farklar
- Dashboard'a ayrı "sapma %" sütunu yerine tek satır özet şeridi + bağlantı kondu (tablo zaten geniş).
- Eşik parametre tablosuna değil URL'ye yazılır (kişisel görünüm ayarı; hesabı değiştirmez).

## Bekleyen
- Muhasebeden gerçek gerçekleşen Excel: gelince aynı yoldan (Veri Aktar → Tüm çalışma kitabı → tür Gerçekleşen) yüklenir; parite testi
  `GERCEKLESEN_YOLU` ortam değişkeniyle gerçek dosyaya çevrilebilir.
