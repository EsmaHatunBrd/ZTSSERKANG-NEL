# Faz 5b Kapanış Raporu — Muhasebe cevapları: Z/S, elle veri girişi, S.ALMA BF revize fiyat

Tarih: 23.10.2026 · Plan: `docs/10-23-2026-faz5b-muhasebe-cevaplari-plani.md` · Durum: **kapandı**
(G1 ve G2 ayrı reviewer turlarından geçti; birleşik doğrulama: backend 396/396 `-W error`, vitest 350/350, tsc 0, build ok, Playwright 24/24)

## Kullanıcı gözüyle ne geldi
- **Veri Girişi** (menü: VERİ → en üst): tek sayfadan gider havuzu, malzeme fiyatı, parametre ve üretim hedefi/kapasite girişi. Excel yüklemeden kalem bazında çalışma. Her kayıt neden ister ve Değişiklik Günlüğü'ne düşer; kilitli senaryoda pasif.
- **Gider havuzu düzenleme** (Gider Dağıtım ve Veri Girişi'nden): Gider Toplamı "taban tutar × çarpanlar" olarak girilebilir (çarpan ekle/sil, adlandırılabilir, canlı sonuç); alt kalemler Excel'deki gibi **TL tutarıyla** yazılır, Gider % kendiliğinden hesaplanır ("Yüzdeyle" moduna geçilebilir); alt kalem ekle/sil. Kartta çarpan satırı `taban × 1,35 × 1,30 = toplam`.
- **Gider Dağıtım kartı** Excel düzeninde: Alt kalem · Gider Toplamı · Çalışılan Saniye (kg/adet bazında "Kg"/"Adet") · B.M. / SN · Gider %, toplam satırı; tam genişlik, sütunlar %24/22/20/18/16.
- **Revize fiyat:** S.ALMA BF'deki ikinci fiyat sütunu (I) artık okunuyor. Yüklemede F "İlk bütçe", I farklıysa "Revize" olarak aynı güne ikinci fiyat kaydı; **hesap revizeyi kullanır**. Malzeme Fiyatları'nda "İlk bütçe" ve "Revize" sütunları, "Yalnız revize edilenler" süzgeci; Veri Aktar → Satın alma önizlemesinde "Revize edilen: N" ve liste. Gerçek dosyada I≠F olan malzeme: 127.
- **Kaynak (Z/S):** "Z/S" sütunu "Kaynak" oldu: Ziraat (kendi tarımından; enflasyon uygulanmaz) / Satın alma (TL fiyata enflasyon, dövize kur). Reçete tablosunda da aynı. Ziraat + döviz uyarısı yeniden yazıldı. Yardım'a açıklamalar eklendi.
- **Değişiklik Günlüğü** tarih süzgeci yerel günü kullanır (22.10 akşamı düzeltme).

## Muhasebe direktörünün cevapları (23.10 telefon) ve sonuçları
| Konu | Cevap | Sistemde |
|---|---|---|
| Z/S | Z = Ziraat, enflasyon yok; S = satın alma, yalnız TL'ye enflasyon | Hesap aynı; etiket + açıklama |
| S.ALMA BF I sütunu | Sonradan yapılan güncellemeler; F eski | Revize fiyat geçmişi, hesap güncel fiyatla |
| Gider dağıtım çarpanları | Arayüzden güncellenebilmeli; kalemler Excel'siz girilebilmeli | Taban × çarpanlar, tutar girişi, Veri Girişi |
| Stok süresi 2 ay (3 ürün) | Kendisi günceller | Zaten düzenlenebilir, iş yok |
| Fire varsayılanları | Düzenlenebilir olsun | Zaten öyle |
| Gerçekleşen Excel | Aynı düzen, farklı değerler | Faz 6 planı geçerli; dosya bekleniyor |

## Teknik
- Backend: `GiderHavuzu.taban_tutar/carpanlar` (ALTER ile), `gider_servisi.toplam_hesapla/_pay_cozumle`, `HavuzGiris` (toplam **veya** taban; anahtar `pay_orani` **veya** `tutar`), toplu kaydet taban/çarpanı temizlerse `uyarilar`; `import_servisi`/`aktarim_servisi` I sütunu (`revize_fiyatlarini_oku`, `revize_ile_fiyat_ekle`, `excel_tam_yukle(revize_uygula=True)`), `fiyat_servisi.ilk_kayitlar_kodla`, `GET /malzemeler?revize=1` + `ilk_fiyat/revize`; uyarı metni `fiyat_motoru/malzeme.py`. Testler: `test_faz5b_gider_giris.py` (14), `test_faz5b_revize_fiyat.py` (15), `test_faz5_gunluk.py` (+1 yerel gün).
- Frontend: `HavuzDiyalogu` (yeniden), `HavuzKarti` (Excel düzeni + çarpan satırı), `VeriGirisi` + `kapasiteDuzenleme.ts` (UretimAdetleri ile ortak), `MalzemeFiyatlari` (Kaynak, İlk bütçe, Revize, süzgeç), `KaynakRozeti`, `ReceteTablosu`, `SatinAlmaAktar`, `Yardim`, `Kabuk`/`yonlendirme` (Veri Girişi), e2e `gider-tutar.spec.ts`, `DASHBOARD_BEKLEME_MS` 30 sn.
- Parite: `test_uctan_uca_excel.py` `revize_uygula=False` ile ilk bütçe üzerinden koşar; Excel ürün sayfaları F'ye baktığı için revize uygulanınca sistem bilinçli olarak Excel'den sapar.

## Kontrolörün kararları (yanlışsa düzeltin)
1. Hesap revize (güncel) fiyatı kullanır; Excel ile birebir kontrol "ilk bütçe" üzerinden.
2. Revize varken F yalnız senaryoda o değerde kayıt yoksa yazılır (tekrar yükleme sahte "İlk bütçe" üretmez). Kullanıcı nedeni korunur: "<neden> · İlk bütçe (S.ALMA BF F)" / "<neden> · Revize (S.ALMA BF I)".
3. Malzeme listesinde `revize` = geçerli ≠ ilk kayıt (elle zam da sayılır).
4. Çarpanlar havuz kaydında; `dagitim_carpani.*` parametrelerine dokunulmadı (kaldırma ayrı karar). Toplam doğrudan yazılınca (ürün ekranı toplu kaydet, Excel gider yeniden yükleme) taban × çarpan temizlenir; toplu kaydet uyarır.
5. API: taban + toplam birlikte ya da tabansız çarpan → 422; `pay_orani` ve `tutar` birlikte gelirse `pay_orani` kazanır; tutar→pay ham Decimal bölüm.
6. Diyalogda tutar modu varsayılan; dokunulmayan alt kalem özgün payını korur.
7. Yeni havuz kodu ekleme kapsam dışı (motor dağıtım kuralları sabit kodlara bağlı).
8. İki duman testinin ilk koşudaki kırmızısı yük kaynaklı zaman aşımıydı (soğuk dashboard boş makinede ~2 sn, aynı anda e2e kurulumu + Vite + tarayıcı + paralel işler altında 15 sn aşıldı); tek başına ve tam süit 24/24 geçti; bekleme 30 sn yapıldı.

## Ek (23.10 öğleden sonra, kullanıcı: "üretim adedi giremiyorum")
- Veri Girişi'ne **Üretim bilgileri (ürün)** kartı eklendi: senaryodaki ürünü seç → vardiya üretim adedi, dolum/etiket personel, etiketleme adedi, mal kabul kg ve fire %, pazarlama/yönetim uygulansın; neden zorunlu; `PUT /urunler/{kod}/uretim-hedefi` artık `neden` alır (`UretimHedefiNedenliGiris`), günlüğe düşer. Dashboard'daki "Üretim Adedi" bu alandan gelir.
- Eski kart **Hat kapasitesi (Üretim Adetleri)** olarak yeniden adlandırıldı (Excel'in Üretim Adetleri sayfası kayıtları).
- Testler: backend `test_faz5b_uretim_neden.py` (2), vitest VeriGirisi 8/8; tam süit 351 (HavuzDiyalogu'nun bir testi tam süit yükünde bir kez kırıldı, tek başına 3/3; kırılgan, izlenecek).
- **Veri uyumsuzluğu (muhasebeye soru):** Excel'in Üretim Adetleri sayfasındaki 71 kayıt `02.*` kodlu, ürün sayfaları `03.*` kodlu; hiçbiri eşleşmiyor. Bu yüzden dashboard'daki "Hedef adetle maliyet" sütunu boş. Adlar büyük ölçüde aynı ("Dikenli H. Turşu No:2 1700 ml Berrak" iki tarafta da var). Karar gerekiyor: ada göre eşleme mi, kod dönüşüm tablosu mu, yoksa Üretim Adetleri sayfası başka amaçla mı?

## Canlı veri notu
- 8000'deki backend yeni kodla çalışıyor; şema ALTER ile tamamlandı.
- **23.10 öğleden sonra (kullanıcı: "ne kaldıysa devam et"):** S.ALMA BF, Veri Aktar satın alma ucuyla yeniden yüklendi: 127 revize fiyat `import-revize` kaynağıyla 2026-06-01 tarihine ikinci kayıt olarak girdi (706 aynı, 0 yeni); hesap artık revize fiyatı kullanır, etkilenen ürünlerde maliyet Excel'den bilinçli olarak sapar. Öncesi yedek: `veri/yedek/10-23-2026-revize-oncesi-fiyat.db`. Günlükte 127 kayıt, neden: "S.ALMA BF revize sütunu (I) yüklendi; muhasebe direktörü 23.10: sağdaki sütun güncel fiyat".

## Ek 2 (23.10 akşam, "ne kaldıysa devam et"): ertelenenlerin kapatılması
- Tam kitap yükleme özetinde "Revize fiyat (S.ALMA BF I)" kartı; `FiyatListesiYukle` diyaloğunda revize listesi (kod · ilk → revize).
- Günlükte havuz satırı okunur: `toplam_tutar: 1.000,10 × 1,35 (SGK) × 1,30 (zam) = 1.755,18` (ham kayıt değişmedi).
- Aile diyaloğu görünen adı düzenler: kullanıcı ad yazar, sunucu anahtarı türetir (`aile_anahtari`), `Urun.aile_ad` (ALTER ile) saklanır; PATCH yanıtı `{kod, aile, aile_ad}`. Not: anahtar artık küçük harf; daha önce elle atanmış büyük harfli anahtarlar yeniden kaydedilene kadar eski haliyle kalır.
- Rulings 15-17 ledger'da. Doğrulama: backend tam süit **401/401** (`-W error`, 21 dk), vitest 353/353, tsc 0, build ok; Playwright sonucu ledger'da. 8000 yeni kodla yeniden başlatıldı (`urun.aile_ad` ALTER ile eklendi).

## Ek 3 (23.10 akşam, kullanıcı: "yavaşlık problemini çöz")
Ölçüm (8000, canlı veri): tüm uçlar 5-280 ms; tek yavaş nokta **dashboard soğuk hesabı** (67 ürün): boş makinede 1,6-2 sn, paralel yük altında 5-9 sn. Her yazma önbelleği boşalttığı için kullanıcı her kayıttan sonra dashboard'u soğuk buluyordu. Vite dev sayfası 270 ms'de yükleniyor; arayüz darboğaz değil.
Yapılanlar:
- **Arka plan ısıtıcı** (`backend/servisler/isitici.py`): yazma sonrası middleware önbelleği boşaltır ve 0,8 sn gecikmeyle sunucunun kendi `GET /urunler` ve `/uyarilar` uçlarına istek atarak her açık senaryoyu yeniden hesaplar; peş peşe yazmalar tek ısıtmaya birleşir; hata isteği düşürmez; `ONBELLEK_ISITMA=0` ile kapatılır; test istemcisinde (testserver) devre dışı. Ölçüm: yazmadan 4 sn sonra dashboard `X-Onbellek: isabet`, 5 ms.
- **Üretim derlemesi aynı sunucudan** (`uygulama._arayuzu_bagla`): `frontend/dist` varsa http://<sunucu>:8000/ arayüzü sunar (SPA yolları index.html'e düşer, `/api/*` JSON 404, dizin kaçışı engelli). Vite dev sunucusuna gerek kalmaz; `npm run build` sonrası tek adres. dist yoksa hiçbir şey bağlanmaz.
- Testler: `tests/backend/test_isitici_ve_arayuz.py` (6).
- **Soğuk hesap hızlandırıldı** (`hesap_servisi.HesapBaglami`): `toplu_hesapla` senaryo geneli yükleri (malzeme fiyat haritası, malzeme tipleri, gider oranları, parametre satırları, satış notları) 67 ürün için bir kez çeker; `parametre_servisi.parametre_satirlari/degerleri_coz` ayrıştırıldı. Ölçüm (e2e.db, 67 ürün): **1,5 sn → 0,15-0,2 sn**. Sonuçlar tek tek `hesapla` ile birebir (test `test_hesap_baglami.py`: eşitlik, ürün kapsamlı parametre karışmaz, yükler bir kez).
- Not: makinedeki yavaşlığın bir kısmı aynı anda koşan test süitleri ve ajanlardı (CPU); bundan sonra tam süitler sırayla koşulur.

## Ertelenenler (teslimi engellemez)
- Taban "0" için istemci tarafı ayrı mesaj yok (sunucu 422); radiogroup ok tuşu gezinmesi yok.
- Excel gider yeniden yüklemesi taban/çarpanı okumaz (toplam yazar, çarpan temizlenir).
- Ürün ekranı yalnız ürünün kendi `aile_ad`ını gösterir; aynı gruptaki başka üyeye yazılmış ad Karşılaştırma'da görünür.
- Günlükte `None` alanlar "null" yazar (eskiden de öyle).
- Önceki fazlardan: kilit senaryodan bağımsız yazımları kapsamaz; axe taraması yok.
- `HavuzDiyalogu.test.tsx` yalnız paralel vitest yükünde bir kez kırıldı; beklentiler waitFor/findByText(5 sn) yapıldı, tek başına 8/8 yeşil.
