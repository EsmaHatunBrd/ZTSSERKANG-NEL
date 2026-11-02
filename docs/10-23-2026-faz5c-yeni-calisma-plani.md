# Faz 5c — Yeni çalışma: boş sezon, geçen sezondan kopyalama, senaryo yönetimi, yeni ürün

Tarih: 23.10.2026 · Durum: **onaylandı** (kullanıcı: "OK") · İstek: "Yeni bomboş bir çalışma kitabı yok" — yeni çalışma yalnız Excel yükleyerek açılabiliyor.

## Hedef
Kullanıcı Excel olmadan: (1) boş bir sezon/senaryo açabilsin, (2) geçen sezondan seçerek kopyalayıp yalnız değişenleri güncelleyebilsin, (3) senaryoyu adlandırıp/silebilsin, (4) yeni ürün kartı açıp reçetesini ekranda kurabilsin.

## Mevcut durum (tespit)
- `POST /senaryolar` var (boş senaryo), arayüzde düğmesi yok. Kopyalama, düzenleme, silme yok.
- Ürün kartları (`Urun`) senaryodan bağımsız; `toplu_hesapla` tüm aktif ürünleri her senaryoda hesaplar → boş senaryoda 67 ürün "reçete yok" hatasıyla listelenir. Senaryoya bağlı tablolar: ParametreDegeri, MalzemeFiyati, GiderHavuzu(+anahtarlar), AmbalajSinifi, UretimHedefi, Recete, FireKurali, MaliyetHesabi, MetinParametre, UretimKapasitesi.

## API sözleşmesi (Y1 uygular, Y2 buna göre arayüz yazar)
- `POST /senaryolar/{id}/kopyala` → 201. Gövde: `{sezon_ad, ad, tur, aciklama?, neden, kopyala: {receteler: bool, fiyatlar: bool, parametreler: bool, gider: bool, uretim: bool, fire_kurallari: bool}}`. Yanıt: `SenaryoCikis` + `kopyalanan: {recete, fiyat, parametre, metin, havuz, ambalaj, hedef, kapasite, fire}` (sayılar). Tek işlem (hepsi ya da hiçbiri). Kopyalananlar:
  - receteler: kaynaktaki her ürünün **aktif** reçetesi → yeni senaryoda versiyon 1, `kaynak="kopya"`, satırlar aynen (elle değerler dahil).
  - fiyatlar: kaynakta **bugün geçerli** malzeme fiyatı (malzeme başına tek kayıt) → `gecerlilik_basi` kaynak kaydınki, `neden="Kopya: <kaynak senaryo adı>"`, `kaynak="kopya"`.
  - parametreler: bugün geçerli `ParametreDegeri` (genel ve ürün kapsamlı) + `MetinParametre`; aynı neden/kaynak kuralı. Yeni senaryo zaten `parametreleri_tohumla` ile tanımları alır; değerler kopyalanır.
  - gider: `GiderHavuzu` (taban, çarpanlar, anahtarlar dahil) + `AmbalajSinifi`.
  - uretim: `UretimHedefi` + `UretimKapasitesi`.
  - fire_kurallari: bugün geçerli `FireKurali`.
  - Kopyalanmaz: `MaliyetHesabi`, teklifler, satış geçmişi (senaryodan bağımsız), `kilitli` (yeni senaryo açık), `kaynak_dosya` (boş).
  - Günlük: yeni senaryoya tek `DegisiklikKaydi` (tablo "senaryo", islem "kopyala", yeni = sayılar + kaynak id, `_neden`).
- `PATCH /senaryolar/{id}` gövde `{sezon_ad?, ad?, aciklama?, neden}` → `SenaryoCikis`; kilitliyse 409; değişiklik kaydı.
- `DELETE /senaryolar/{id}` → 204 yalnız **kayıtlı hesabı yoksa ve kilitli değilse**; aksi 409 (`hata: "catisma"`, mesajda neden). Siler: senaryoya bağlı tüm satırlar (yukarıdaki tablolar) + senaryo. Son senaryo da silinebilir (boş uygulama durumu zaten var). Günlük: senaryo silme senaryoya bağlı olduğundan günlükte kalmaz; silmeden önce `veri/yedek/<tarih>-silme-oncesi-<ad>.db` otomatik yedek (`yedek.py` kullan).
- **Senaryo üyeliği:** `GET /urunler?senaryo=` ve dashboard/`uyarilar`/`toplu_hesapla`/Teklif Kapak xlsx/`karsilastirma` yalnız **o senaryoda aktif reçetesi olan** ürünleri alır. `?tum=1` ile eski davranış (tüm aktif ürünler; hatalılar "reçete yok"). `SenaryoCikis`'e `urun_sayisi` (üye ürün) eklenir. Üye olmayan ürün için `GET /urunler/{kod}?senaryo=`: ürün döner, `senaryoda: false`, `uretim_hedefi: null`; `GET /urunler/{kod}/recete?senaryo=` boş reçete (`id: null, versiyon: 0, satirlar: []`) döner, 404 değil; `POST .../recete` ilk versiyonu açar (mevcut). Parite ve mevcut testler etkilenmez (import tüm ürünlere reçete yazar) — koşup doğrula.
- `POST /urunler` (yeni kart): mevcut `PUT /urunler/{kod}` upsert yeterli; kod tekilliği 409. `gecici_kod` kullanıcı "ERP kodu yok" derse `SAYFA-<ad>` yerine `GECICI-<zaman>` üretmesin; kullanıcı kodu kendisi yazar (zorunlu).

## Görevler
### Y1 — Backend (servis + API + testler)
`backend/servisler/senaryo_servisi.py` (yeni: `kopyala`, `guncelle`, `sil`, `uye_urun_kodlari`), `backend/api/senaryolar.py` uçları, `semalar.py` (`SenaryoKopyaGiris`, `SenaryoGuncelleGiris`, `SenaryoKopyaCikis`, `SenaryoCikis.urun_sayisi`, `UrunCikis.senaryoda`), üyelik süzgeci (`hesap_servisi.toplu_hesapla(s, senaryo_id, tarih, tum=False)` ve çağıranlar: `api/urunler.py`, `disa_aktar`, `karsilastirma_servisi`, `gunluk/arsiv` etkilenmez). `recete_servisi.aktif_recete` reçetesiz üründe `None` dönebilsin ve `GET recete` boş yapı versin. Testler: `tests/backend/test_faz5c_senaryo.py` (kopya sayıları ve içerik, seçimli kopya, tek işlem geri alma, PATCH, DELETE 204/409, üyelik süzgeci, `?tum=1`, boş reçete GET, parite dosyaları yeşil). Tam süit `-W error`. Tip üretimi için 8020'de geçici backend bırakma; Y2 kendi üretir.

### Y2 — Arayüz
- `SenaryoSecici` yanında **"Yeni çalışma"** düğmesi → diyalog, 3 sekme: Boş (sezon adı, senaryo adı, tür, açıklama), Geçen sezondan kopyala (kaynak senaryo seç; onay kutuları: Ürünler ve reçeteler, Malzeme fiyatları, Parametreler, Gider dağıtımı ve ambalaj sınıfları, Üretim bilgileri ve kapasite, Fire kuralları — hepsi varsayılan işaretli; neden zorunlu; sonuç özeti "Kopyalandı: 67 reçete, 661 fiyat …"), Excel'den (Veri Aktar → Tüm çalışma kitabına bağlantı). Oluşturunca yeni senaryo seçilir (`?senaryo=`).
- Senaryo menüsünde **Düzenle** (ad/sezon/açıklama + neden) ve **Sil** (yalnız kayıtlı hesabı yoksa; onay diyaloğu "geri alınamaz, yedek alınır"; 409 mesajı gösterilir).
- Dashboard boş senaryo durumu: "Bu çalışmada henüz ürün yok" + üç düğme: Geçen sezondan kopyala (diyaloğu kopya sekmesiyle açar), Yeni ürün (Veri Girişi), Excel yükle.
- Veri Girişi'ne **Yeni ürün** kartı: kod (zorunlu, tekil), ad, ambalaj hacmi, hat (mevcut hat listesinden), taze/turşu sınıfı, süzme kg, pazar, "ERP kodu yok" onay kutusu (gecici_kod) → `PUT /urunler/{kod}` → "Reçeteyi kur" bağlantısıyla ürün ekranına.
- Ürün ekranı reçetesiz üründe açılır: boş reçete tablosu + "Satır ekle" (mevcut elle satır ekleme akışı), hesap yerine "Reçete girilince hesaplanır" notu; `senaryoda: false` ise üst şerit "Bu ürün bu çalışmada yok — reçete kaydedince dahil olur".
- Üye olmayan ürünleri görmek için Ürün Maliyeti listesinde "Çalışma dışı ürünleri göster" anahtarı (`?tum=1`).
- Yardım: "Yeni sezon" bölümü güncellenir (Excel'siz yollar). Kabuk/menü değişmez.
- Testler: vitest (diyalog 3 sekme, kopya isteği gövdesi, düzenle/sil, dashboard boş durum, yeni ürün kartı, reçetesiz ürün ekranı), tsc, build; Playwright: 1 senaryo (boş çalışma aç → yeni ürün → reçete satırı ekle → hesap gelir; 8010/5190).
- Tipler: Y1 bitince 8030'da geçici backend ile `sema.d.ts` yeniden üret; Y1 bitene kadar msw ile sözleşmeye göre geliştir.

## Kurallar
- 8000/5180 kullanıcının; Y1 8020, Y2 8030; e2e 8010/5190. Şirket verisi fixture'a girmez. Decimal metin. Neden zorunlu, günlüğe düşer.
- Dosya sahipliği: backend tamamen Y1; frontend tamamen Y2; `sema.d.ts` Y2 (Y1 bitince).
- Süreç: implementer → reviewer → düzeltme → kontrolör birleşik doğrulama (backend tam süit, vitest, tsc, build, Playwright). Ledger `scratchpad/sdd-faz5c/progress.md`.

## Kapsam dışı
- Ürün kartlarının senaryoya özel kopyası (kartlar global kalır; üyelik reçeteyle).
- Toplu ürün silme; senaryolar arası reçete karşılaştırması (Arşiv kıyası kayıtlı hesaplar üzerinden zaten var).
