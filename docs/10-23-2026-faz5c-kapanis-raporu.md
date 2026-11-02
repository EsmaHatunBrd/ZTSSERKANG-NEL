# Faz 5c Kapanış Raporu — Yeni çalışma (boş sezon, kopyalama, senaryo yönetimi, yeni ürün) + performans

Tarih: 23.10.2026 · Plan: `docs/10-23-2026-faz5c-yeni-calisma-plani.md` · Durum: **kapandı** (Y1 ve Y2 ayrı reviewer turları + kontrolör birleşik doğrulama)

## Kullanıcı gözüyle ne geldi
- **Yeni çalışma** düğmesi (senaryo seçicinin yanında) → üç yol: **Boş** (sezon adı YYYY-YYYY, senaryo adı, tür, açıklama), **Geçen sezondan kopyala** (kaynak senaryo + altı seçim: ürünler ve reçeteler, malzeme fiyatları, parametreler, gider dağıtımı ve ambalaj sınıfları, üretim bilgileri ve kapasite, fire kuralları; neden zorunlu; sonuç "Kopyalandı: 67 reçete, 661 fiyat …"), **Excel'den** (Veri Aktar'a bağlantı). Oluşturunca yeni çalışma seçilir.
- Senaryo menüsü (⋯): **Düzenle** (ad / sezon / açıklama + neden) ve **Sil** (yalnız kayıtlı hesabı yoksa ve kilitli değilse; önce otomatik yedek `veri/yedek/<tarih>-silme-oncesi-<ad>.db`; aksi halde nedenli 409 mesajı).
- **Boş çalışmada dashboard**: "Bu çalışmada henüz ürün yok" + Geçen sezondan kopyala / Yeni ürün / Excel yükle.
- **Veri Girişi → Yeni ürün** kartı: kod (zorunlu, tekil; var olan kart ezilmez), ad, ambalaj hacmi, hat, taze/turşu sınıfı, süzme kg, pazar → "Reçeteyi kur" bağlantısı.
- **Reçetesiz ürün ekranı** açılır: boş reçete + satır ekleme; üretim bilgisi yoksa ekranda kart; parametre değeri yoksa Parametreler bağlantılı not; reçete kaydedilince hesap gelir ve ürün çalışmaya dahil olur. Ürün Maliyeti listesinde "Çalışma dışı ürünleri göster" anahtarı.
- **Senaryoya dahil ürün kuralı:** bir ürün o çalışmada ancak aktif reçetesi varsa dashboard, uyarılar, Teklif Kapak ve karşılaştırmada görünür (`?tum=1` eski görünüm). Boş çalışma gerçekten boş açılır.
- **Performans** (ayrıntı Faz 5b raporu Ek 3): dashboard soğuk hesabı 1,6-5 sn → **0,26 sn**; her kayıttan sonra arka plan ısıtıcı → dashboard 6 ms; arayüz http://<sunucu>:8000/ adresinden tek sunucuyla.

## Teknik
- Backend: `servisler/senaryo_servisi.py` (`kopyala`, `guncelle`, `sil`, `uye_urun_kodlari`), `api/senaryolar.py` (`POST /senaryolar/{id}/kopyala` 201, `PATCH`, `DELETE` 204/409 `catisma`), `SenaryoCikis.urun_sayisi/aciklama`, `UrunCikis.senaryoda`, boş reçete `GET recete` 200 `{versiyon: 0}`, `toplu_hesapla(tum=False)` + `?tum=1` altı uçta, `CatismaHatasi`, `yedek.silme_oncesi_yedek_al`. Performans: `servisler/isitici.py`, `uygulama._arayuzu_bagla`, `hesap_servisi.HesapBaglami`, `parametre_servisi.parametre_satirlari/degerleri_coz`.
- Frontend: `YeniCalismaDiyalogu`, `SenaryoDuzenleDiyalogu`, `SenaryoSecici` (düğme + klavyeli menü), `Dashboard` boş durum, `Urunler` (tum anahtarı, Durum sütunu), `VeriGirisi` → `girdi/{ortak,YeniUrunKarti,UretimBilgileriKarti}`, `UrunMaliyeti` reçetesiz akış, `ElleReceteFormu` gömülü, `yardimcilar/{senaryo,urunKarti}.ts`, Yardım "Yeni sezon".
- Testler: backend `test_faz5c_senaryo.py` (14), `test_isitici_ve_arayuz.py` (6), `test_hesap_baglami.py` (3); vitest `YeniCalismaDiyalogu.test.tsx`, `Urunler.test.tsx` + güncellemeler; Playwright `yeni-calisma.spec.ts`.
- Birleşik doğrulama (kontrolör, sırayla): vitest **380/380**, tsc 0, build ok; backend tam süit **424/424** (`-W error`, 12 dk); Playwright sonucu ledger'da (`sdd-faz5c/progress.md`). 8000 son backend koduyla çalışıyor, `frontend/dist` 16:22 derlemesi (http://localhost:8000/).

## Kontrolörün kararları (yanlışsa düzeltin)
1. Üyelik = aktif reçete; kopya "bugün geçerli" kayıtları tek kayıt olarak taşır (ileri tarihli kayıtlar taşınmaz); hesaplar, teklifler, kilit kopyalanmaz.
2. Kopya seçimleri açıkça gönderilir (varsayılan yok); kilitli kaynaktan kopya serbest.
3. Silme: kayıtlı hesabı olan senaryo silinemez (arşiv korunur); silinen senaryonun günlük satırları yedekte kalır, genel günlükte tek "Senaryo silindi" kaydı.
4. Yeni üründe "ERP kodu yok" kutusu yok: kullanıcı kodu kendisi yazar (`UrunGiris` gecici_kod almıyor; SAYFA-* yalnız Excel'den).
5. Isıtıcı kendi HTTP uçlarını çağırır; `HesapBaglami` yalnız toplu hesapta, paylaşılan nesneler salt okunur.
6. Reçetesiz `hesapla` 422 "reçete yok"; arayüz reçetesiz üründe hesap çağırmaz.

## Ertelenenler (teslimi engellemez)
- Y2 önerisi: hesap hatalarında kararlı kod (`hedef_yok`, `parametre_eksik`) — arayüz şu an mesaj metniyle tanıyor.
- Boş çalışmada parametre değerleri (kur, enflasyon, satış kârı, vardiya saati) girilmeden hesap gelmez; kopya yolu bunu atlatır. İstenirse "Boş" sekmesine "parametreleri geçen sezondan al" kısayolu.
- Yeni çalışma diyaloğunda sekme değişince Boş sekmesine yazılanlar sıfırlanır.
- Silme öncesi yedekler budanmaz (yalnız `-otomatik-` budanır).
- Aile görünen adı tasarım gereği küçük harf türetilir ("biberiye turşu"); baş harfleri büyük istenirse `aile_ad_turet` tek satırlık değişiklik (kozmetik).
- `ui/button.tsx` ref iletmiyor (eski uyarı).
