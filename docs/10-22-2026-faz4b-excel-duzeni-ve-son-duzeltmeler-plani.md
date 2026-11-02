# Faz 4b: Ürün Maliyeti Ekranını Excel Düzenine Yaklaştırma + Son Düzeltmeler

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

Tarih: 22.10.2026 — Kullanıcı onayı: "ok" (Excel'de olup ekranda olmayan bilgiler listesine karşılık).

**Goal:** Muhasebenin Excel alışkanlığını korumak: ürün sayfasında gördüğü her bilgi (üretim girdileri, kurlar/enflasyon, para birimi bazlı finansman, gider satırlarının miktar/oran/satış yüzdesi, reçete ağaç seviyesi ve Z/S, GBP/ZAR maliyetleri, teklif kâr oranları, Üretim Adetleri sayfası) arayüzde de görünsün ve düzenlenebilsin. Ayrıca Faz 4 final incelemesinin 8 "kullanıma almadan önce" kalemi ve önemli iyileştirmeleri (önceki yarım kalan dalga) bu planın içinde.

**Spec:** `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` §2 (formüller, hücre adresleri), `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` §4-§5, Faz 4 final inceleme bulguları (E görevleri).

## Global Constraints
- Önce backend (B), sonra tip üretimi, sonra frontend (U ve E). Backend değişiklikleri geriye uyumlu (alan/uç ekleme; isim ve şekil değişmez). `fiyat_motoru/` mantığı değişmez (yalnız B2'deki yeni okuyucu fonksiyonu eklenir).
- Tipler `/openapi.json`'dan üretilir; `tipler.ts` yalnız takma ad.
- Para `Decimal`/`ParaHucresi`; döviz tutarları kendi para birimiyle etiketlenir (TL yazılmaz).
- Her yazma işlemi: neden zorunlu (API'de varsa), bugün tarihi, özet; geçmiş append-only.
- Türkçe arayüz; tanımlayıcılar Türkçe karakter kullanmadan; git yok; kurumsal veri fikstürlerde yok.
- Testler: değişen her bileşen için MSW testi; sonunda `npm test -- --run`, `tsc`, `npm run build`, backend `pytest -q -W error`; en sonda Playwright e2e (kontrolör koşar).

---

## B. Backend eklemeleri (tek görev)

### B1. Hesap yanıtını Excel bloklarıyla zenginleştir
`backend/api/urunler.py` (`_gorunum`, `_toplamlar`, `_fiyatlar`) ve `backend/api/semalar.py`:
- `HesapToplamlari` + `maliyet_gbp`, `maliyet_zar` (motor `doviz_maliyet`; yoksa null) + `finansman: dict[str, str]` (TL/USD/EUR/GBP/ZAR faiz tutarları; motor `finansman` sözlüğü).
- `HesapFiyatlari` + `satis_gbp`, `satis_zar` (motor `satis_fiyati_doviz`) + `teklif_kar_oranlari: list[str]` + `satis_kar_orani: str`.
- `HesapSatiri` + `birim` (malzeme satırı: reçete satırının birimi; gider satırı: `uretim_gideri.py`'deki kalem→birim eşlemesi SN/KG/ADET, `kod` ile) + `zs` (malzeme kartı) + `dugum_tipi` (reçete satırı: `yaprak`/`ara_mamul`; gider satırı null).
- `HesapYaniti` + `uretim: UretimBilgisiCikis` (pazar, hat, taze_tursu_sinifi, ambalaj_hacmi, suzme_kg, vardiya_uretim_adedi, vardiya_saati, dolum_personel, etiketleme_adedi, etiket_personel, mal_kabul_miktar_kg, mal_kabul_fire, pazarlama_yonetim_uygula) + `parametreler: ParametreOzetiCikis` (enflasyon, maliyet_sapma|null, kurlar{}, faiz{}, stok_ay{}, satis_kar, teklif_kar[]) + `notlar: list[str]`.
- Snapshot `gorunum` aynı alanları `girdi_snapshot["girdi"]["uretim"]` ve `["parametreler"]`'den üretir (eski snapshot → null).
- `tohum.PARAMETRELER`'e `maliyet_sapma` (oran, varsayılan 0) ve metin parametre `satis_fiyati_notu` (Excel `G137` notu; `ParametreDegeri.deger` ParaTipi olduğu için metin parametreler için ayrı küçük tablo `metin_parametre(senaryo_id, anahtar, deger, gecerlilik_basi, neden)` append-only; `GET/POST /metin-parametreler`). `notlar` buradan dolar.

### B2. Üretim Adetleri (Excel `Üretim Adetleri` sayfası)
- `fiyat_motoru/excel_okuyucu.py` + `uretim_adetlerini_oku(wb_v) -> list[dict]` (ürün kodu, ürün adı, net süredeki vardiyalık kapasite, net süre %, toplam süredeki kapasite, toplam süre %, hedef vardiyalık üretim, ortalama işçi). Yalnız ekleme; motor mantığı değişmez; test: 70 civarı satır, bilinen bir satırın değerleri.
- Tablo `uretim_kapasitesi` (senaryo_id, urun_kodu, urun_ad, 6 sayısal alan ParaTipi, olusturma/olusturan); import yazar (`ozet["kapasite"]`); `GET /uretim-kapasitesi?senaryo=&sayfa=&boyut=` → `{kayitlar, toplam}`; `PUT /uretim-kapasitesi/{urun_kodu}?senaryo=` gövde alanlar + `neden` (DegisiklikKaydi).

### B3. Ambalaj özeti (Excel `Ambalaj Özeti`/`Sayfa2`)
`GET /ambalaj-ozeti?senaryo=` → `{turler: [{tur, urun_sayisi, uretim_adedi}], kapaklar: [{ad, urun_sayisi, uretim_adedi}]}`; serviste `AMBALAJ_TURU` eşleme tablosu (malzeme adında "kavanoz"→Cam Kavanoz, "şişe"→Cam Şişe, "teneke"→Teneke Kutu, "torba"/"folyo"→Torba/Folyo, "pet"→Pet); kapak = adı "Kapak" ile başlayan reçete malzemesi; üretim adedi = üretim hedefinin vardiya adedi × 1 (Excel `F` sütunu sezon adedi — import'ta yoksa null).

### B4. Testler + tip üretimi
`tests/backend/*` genişlet (yeni alanlar, eski snapshot null, kapasite CRUD, ambalaj özeti, metin parametre); `pytest -q -W error` yeşil; uvicorn (8010) ile `npm run api:tipler`; `tipler.ts` takma adları; `tsc` 0 (sayfa hataları varsa rapor).

---

## U. Ürün Maliyeti ekranı — Excel düzeni (tek görev, E ile aynı ajan)

### U1. Üretim bilgileri bloğu (Excel `D136-E146`)
`src/sayfalar/urun/UretimBilgileri.tsx`: Süzme miktar (kg), Vardiya üretim adedi, Vardiya saati, Dolum personel, Etiketleme adedi, Etiket personel, Üretim hattı (liste: gider havuzu hat anahtarları), Taze/Turşu sınıfı (liste), Ambalaj (ml), Pazar (Yurtiçi/Yurtdışı), Mal kabul kg + fire %. Her alan "ne olur" (geçici, `override.uretim`) **ve** "Kalıcı kaydet" (`PUT /urunler/{kod}` + `PUT uretim-hedefi`, neden zorunlu, özet). Hesap tarihi ve senaryo başlıkta.

### U2. Kurlar ve enflasyon bloğu (Excel `D148-F155`)
`KurlarBlogu.tsx`: Enflasyon, Maliyet sapma, USD/EUR/GBP/CHF/RUB/ZAR kurları (`parametreler`); satır içi "ne olur"; "Parametrelerde kalıcı değiştir" bağlantısı.

### U3. Finansman tablosu (Excel `I123-P134`)
`FinansmanTablosu.tsx`: satır = para birimi (TL/USD/EUR/GBP/ZAR): faiz oranı, stok süresi (ay), faiz (oran), faiz tutarı; altında Finansman dahil maliyet TL/USD/EUR/GBP/ZAR ve kur. Faiz ve stok süresi "ne olur" düzenlenebilir (`override.parametreler`).

### U4. Gider kalemleri (Excel `I102-P119`)
`GiderKalemleri.tsx`: sütunlar Kalem, Miktar, Fire %, Brüt, Birim, Birim fiyat, Döviz, Tutar, Maliyet %, Satış %; üç grup başlığı ve ara toplamları (Direkt işçilik, Genel üretim giderleri, Diğer giderler + "dolum yapılan toplam adede göre dağıtılmıştır" notu); Gider toplamı; Toplam birim maliyet.

### U5. Reçete tablosu
Sütun sırası Excel gibi: Satır, Kod, Cinsi, Miktar, Fire %, Brüt, Birim, Birim fiyat, Z/S, Döviz, Tutar (firesiz), Tutar (fireli), Maliyet %, Satış %. `ara_mamul` satırı rozetli; ondan sonraki yaprak satırlar bir kademe girintili (ağaç hissi); ürünün kendi satırı "Ürün" rozeti.

### U6. Toplamlar kartı
Excel sırası: Hammadde-yardımcı malzeme toplamı, Direkt işçilik, GÜG, Gider toplamı, Toplam birim maliyet, Diğer giderler, Giydirilmiş maliyet, Finansman (TL), Finansman dahil maliyet TL/USD/EUR/GBP/ZAR, Satış fiyatı (%kâr) TL/USD/EUR/GBP/ZAR, Süzme kg fiyatı, Teklif 1/2/3 (kâr % etiketiyle, USD); altında `notlar`. Fireli | Firesiz sütunları korunur.

### U7. Ekran düzeni
Excel sırası: başlık → reçete → gider kalemleri → (toplamlar | finansman tablosu) → (üretim bilgileri | kurlar) → teklif paneli → yüzde grafiği. 1280px iki sütun, 768px tek sütun. "Excel görünümü" adı verilmez; sadece düzen.

### U8. Üretim Adetleri sayfası ve ambalaj özeti
`src/sayfalar/UretimAdetleri.tsx` (menü "Üretim Adetleri", route `/uretim-adetleri`): tablo + satır içi düzenleme (neden); Dashboard'a "Ambalaj özeti" kartı/sekmesi.

### U9. Testler
Her blok için MSW testi (render + bir "ne olur" düzenlemesi → `/hesapla` override gövdesi; bir kalıcı kayıt → PUT gövdesi); fikstürler yeni alanlarla; e2e `duman.spec.ts` yeni başlıklara göre güncellenir.

---

## E. Faz 4 final inceleme düzeltmeleri — **BU PLANDAN DÜŞÜRÜLDÜ** (22.10.2026: paralel oturum ztsserkang-nel-b7 tarafından tamamlandı; 169 Vitest, tsc 0, build ok; rapor sdd-faz4/final-fix-report.md). Aşağıdaki liste yalnızca kayıt amaçlıdır.
E1 Menü "Ürün Maliyeti" → `/urunler` ürün seçici (arama + liste) + catch-all route + errorElement (Türkçe). E2 Döviz birim fiyatlar kendi para birimiyle (`ParaBirimi` GBP/CHF/ZAR/RUB). E3 Fiyat listesi önizleme: 4 hane, para birimi, tarih değişince önizleme sıfırlanır. E4 Reçete tamamen değiştirilirken onay ("mevcut N satır → yeni M satır") + "mevcut reçeteyi yükle"; tam kitap importunda aynı sezon+ad varsa uyarı; senaryo seçicide `#id · tür`. E5 Tek `hataMetni(e)` (`alanlar` dahil) `api/istemci.ts`'te; fire % istemci doğrulaması 0–<100. E6 QueryClient `retry`: 4xx'te yok, diğer 2. E7 "Hesabı kaydet": taslak varken açıklamalı engel. E8 İlk açılışta kullanıcı adı diyaloğu (boşsa yazma işlemleri kapalı). I1 Fire sütunu "Fire % (ne olur)" + kayıt notu; reçete taslağına `fire_override` yazma seçeneği; "Kurallara bırak" düğmesi (`kurallara-birak` ucu). I2 `/hesaplar/:id` salt okunur görünüm (`gorunum` ile aynı bileşenler). I3 Malzeme arama kod+ad, `boyut 500`, kapsam etiketi. I4 NavLink `?senaryo=` korur. I5 Reçete sürümü dışarıdan değişince `override.fire` temizlenir (kendi kaydımız hariç). I6 Teklif durum select: bekleme durumu, kabul/red onayı. I7 Tekrarlar tek yere: `bilesenler/Girdi.tsx`, `yardimcilar/teklif.ts`, `KaynakRozeti` "import", `yardimcilar/sayi.ts` (katı ayrıştırıcı), tek reçete hook'u. I8 Route bazlı `React.lazy` + `Suspense`; recharts ayrı chunk; MSW handler'ları `Sema[...]` ile tipli. M1 pay toplamı yüzde; M2 senaryo değişince sayfa/filtre sıfırla; M3 boş DB → Reçete Aktar bağlantısı; M4 elle form fire % (oran değil); M5 havuz %100 değilse onay; M6 yazdırma "yalnız bu sayfa" notu; M7 "Faz 4 sonucu" güncelle (test sayıları, uçlar).

## Sıra ve dağıtım
B (backend, 1 ajan, sonnet) → inceleme → U (frontend, 1 ajan, sonnet; yalnız src/sayfalar/urun/**, UrunMaliyeti.tsx, yeni UretimAdetleri.tsx, Dashboard ambalaj kartı) → inceleme → tam süit + e2e (kontrolör, 8010) → kısa final inceleme → kapanış. E görevleri diğer oturumda bitti.
