# Faz 2 (Backend) ve Faz 4 (Frontend) Tasarımı

Tarih: 21.10.2026
Durum: **TASLAK - onay bekliyor**
Dayanak: `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` (spec), `fiyat_motoru/` (Faz 1 motoru)

> Spec'teki Faz 3 (versiyonlama) ayrı bir faz olmaktan çıkarıldı: kayıt geçmişi veri modelinin temelidir, sonradan eklenemez. Bu belgede Faz 2 = backend (veri + servis + API + versiyonlama + import), Faz 4 = frontend.

---

## 1. Katmanlar ve kurallar

```
frontend/  (React)  ──HTTP/JSON──>  backend/api  ──>  backend/servisler  ──>  fiyat_motoru (saf hesap)
                                                                        └──>  backend/depo (SQLAlchemy) ──> SQLite
```

| Katman | Sorumluluk | Bilmediği şey |
|---|---|---|
| `api/` | HTTP: istek doğrulama (Pydantic), yanıt, hata kodu | Veritabanı, motor |
| `servisler/` | İş kuralları: hangi fiyat geçerli, fire önceliği, snapshot, teklif turu | HTTP |
| `depo/` | SQLAlchemy modelleri ve sorgular | İş kuralı |
| `fiyat_motoru/` | Hesap (Faz 1) | Hepsi |

Kurallar: router içinde SQL yok; servis içinde `Request`/`Response` yok; motor içinde import dışı hiçbir şey yok. Her servis fonksiyonu tek bir `Session` alır (dependency injection), transaction'ı router açar/kapatır.

---

## 2. Veri modeli (SQLAlchemy)

Tutarlar `Numeric(18, 6)` (SQLite'ta `Decimal` olarak okunur/yazılır), oranlar `Numeric(9, 6)`, tarihler ISO. Her tabloda `id`, `olusturma_zamani`, `olusturan`.

### Versiyonlama ilkesi (append-only)
Fiyat, parametre ve fire gibi **zamanla değişen değerler asla güncellenmez veya silinmez.** Her değişiklik yeni satırdır: `(anahtar, kapsam, deger, gecerlilik_basi, neden, olusturan)`. "Geçerli değer" = `gecerlilik_basi <= hesap_tarihi` olan en yeni satır. "Geri al" = eski değeri yeni satır olarak eklemek. Böylece "fiyat değişti ama eski kaydı kaybetmeyeyim" isteği doğal olarak karşılanır ve her maliyet hesabı hangi değerlerle yapıldığını gösterebilir.

### Tablolar

**Dönem ve senaryo**
- `sezon` — `ad` ("2026-2027"), `baslangic`, `bitis`
- `senaryo` — `sezon_id`, `tur` (`fiyat_calismasi` | `gerceklesen`), `ad`, `aciklama`. Enflasyon yalnızca `fiyat_calismasi` türünde uygulanır.

**Parametreler**
- `parametre` — `anahtar` (`enflasyon`, `kur.USD`, `kur.EUR`, `faiz.TL`, `stok_ay.TL`, `satis_kar`, `teklif_kar.1`, `vardiya_saati`, `dagitim_carpani.dolum_iscilik` …), `aciklama`, `birim`
- `parametre_degeri` — `parametre_id`, `senaryo_id`, `kapsam_tipi` (`genel` | `urun`), `kapsam_id` (ürün override için), `deger`, `gecerlilik_basi`, `neden`, `olusturan`  ← append-only

**Malzeme ve fiyat**
- `malzeme` — `kod` (benzersiz), `ad`, `tip`, `birim`, `para_birimi`, `zs`, `aktif`
- `malzeme_fiyati` — `malzeme_id`, `senaryo_id`, `fiyat`, `para_birimi`, `gecerlilik_basi`, `kaynak` (`import` | `elle`), `neden`, `olusturan`  ← append-only

**Gider dağıtımı**
- `gider_havuzu` — `senaryo_id`, `kod` (`dolum_iscilik`, `mal_kabul_iscilik`, `elektrik` …), `ad`, `toplam_tutar`, `baz_tipi` (`saniye` | `kg` | `adet`), `baz_miktar`
- `dagitim_anahtari` — `gider_havuzu_id`, `alt_kalem` (hat adı veya taze/turşu sınıfı), `pay_orani`, `baz_miktar`
- `ambalaj_sinifi` — `senaryo_id`, `ad`, `hacim`, `uretim_adedi`, `katsayi`

**Ürün ve reçete**
- `urun` — `kod` (benzersiz), `ad`, `ambalaj_hacmi`, `hat`, `taze_tursu_sinifi`, `suzme_kg`, `pazar` (`Yurtiçi` | `Yurtdışı`), `aktif`
- `uretim_hedefi` — `urun_id`, `senaryo_id`, `vardiya_uretim_adedi`, `dolum_personel`, `etiketleme_adedi`, `etiket_personel`, `mal_kabul_miktar_kg`, `pazarlama_yonetim_uygula`
- `recete` — `urun_id`, `senaryo_id`, `versiyon`, `kaynak` (`import` | `elle`), `aktif`
- `recete_satiri` — `recete_id`, `sira`, `malzeme_id`, `miktar`, `birim`, `fire_override` (null = kural uygulanır), `dugum_tipi` (`yaprak` | `ara_mamul`), `brut_miktar_elle` (null = brüt miktar fire kuralından hesaplanır; dolu ise o değer brüt miktardır ve fire kuralı o satırda uygulanmaz), `birim_fiyat_elle` (null = birim fiyat fiyat listesinden; dolu ise liste atlanır). İki alan da nullable, `ParaTipi`; Excel'deki elle yazılmış `K`/`M` hücreleri içe aktarmada bu alanlara veri olarak taşınır. Elle brüt miktarlı satırda `fire` override'ı reddedilir (422, "önce elle değeri kaldırın"); `kurallara-birak` varsayılan olarak elle değerleri korur; gövdede `elle_degerleri_kaldir: true` gönderilirse seçili satırlarda `brut_miktar_elle` de boşaltılır.
- **Firesiz paralel sonuç:** motor her hesapta aynı girdiyle fire uygulanmamış (net miktar `I`) ikinci bir sonuç üretir (`MaliyetSonucu.firesiz`); satır bazında `tutar_firesiz`, `miktar_kaynagi` (`fire` \| `elle` \| `-`), `fiyat_kaynagi` (`liste` \| `elle` \| `-`). Kayıtlı hesabın `sonuc_snapshot`ına otomatik girer
- `fire_kurali` — `senaryo_id`, `kapsam_tipi` (`tip` | `grup` | `malzeme`), `kapsam_deger`, `oran`, `oncelik`, `gecerlilik_basi`  ← append-only
- `malzeme_grubu` — kullanıcının fire için oluşturduğu gruplar: `ad`; `malzeme_grubu_uyesi` — `grup_id`, `malzeme_id`

**Hesap ve teklif**
- `maliyet_hesabi` — `urun_id`, `senaryo_id`, `hesap_tarihi`, `girdi_snapshot` (JSON: motorun aldığı `UrunGirdisi`+`Parametreler`+`GiderOranlari`), `sonuc_snapshot` (JSON: `MaliyetSonucu`), `uyarilar` (JSON), `olusturan`. Snapshot sayesinde eski hesap, parametreler değişse de aynen görüntülenir.
- `teklif` — `maliyet_hesabi_id`, `tur_no`, `kar_orani`, `fiyat_tl`, `fiyat_usd`, `fiyat_eur`, `musteri`, `durum` (`taslak` | `gonderildi` | `kabul` | `red`), `not`
- `satis_gecmisi` — `urun_id`, `musteri`, `tarih`, `fiyat`, `para_birimi`, `adet` (kaynağı henüz belirsiz; tablo hazır, import Faz 5)

**İzleme**
- `degisiklik_kaydi` — `tablo`, `kayit_id`, `islem`, `eski` (JSON), `yeni` (JSON), `kullanici`, `zaman`. Append-only tablolar için gerekmez; `urun`, `uretim_hedefi`, `gider_havuzu` gibi güncellenen tablolar için servis katmanı yazar.

### Fire önceliği (servis kuralı)
1. `recete_satiri.fire_override` doluysa o
2. malzeme `malzeme_grubu` üyesiyse ve grup için `fire_kurali(kapsam=grup)` varsa o
3. `fire_kurali(kapsam=malzeme)`
4. `fire_kurali(kapsam=tip)` — varsayılanlar spec bölüm 3'teki tablodan tohumlanır (ambalaj %2, folyo %4, taze hammadde %5, yardımcı %0)
5. hiçbiri yoksa 0

---

## 3. Servisler

| Servis | Fonksiyonlar | Not |
|---|---|---|
| `parametre_servisi` | `gecerli_parametreler(senaryo, tarih, urun=None) -> Parametreler`, `deger_ekle(...)`, `gecmis(anahtar, senaryo)` | Ürün override'ı geneli ezer |
| `fiyat_servisi` | `gecerli_fiyatlar(senaryo, tarih) -> dict[kod, Malzeme]`, `fiyat_ekle(...)`, `gecmis(malzeme)`, `fiyatsizlar(senaryo)` | Motorun `Malzeme` nesnesini üretir |
| `gider_servisi` | `havuzlari_getir(senaryo) -> GiderHavuzlari`, `oranlar(senaryo) -> GiderOranlari`, `pay_toplami_kontrol(havuz)` | Toplam %100 değilse uyarı döner |
| `recete_servisi` | `aktif_recete(urun, senaryo)`, `fire_uygula(satirlar) -> tuple[ReceteSatiri]`, `yeni_versiyon(...)` | Fire önceliği burada |
| `hesap_servisi` | `hesapla(urun, senaryo, tarih, override: dict | None) -> MaliyetSonucu`, `kaydet(...) -> maliyet_hesabi`, `toplu_hesapla(senaryo)` | `override` ekran üzerinden geçici "ne olur" denemesi; kaydetmeden döner |
| `teklif_servisi` | `tur_ekle(hesap, kar, musteri)`, `turlar(hesap)` | Tur sayısı sınırsız |
| `import_servisi` | `fiyat_listesi_onizle(dosya)`, `fiyat_listesi_uygula(onizleme_id)`, `recete_onizle(dosya, urun)`, `recete_uygula(...)`, `gider_dagitim_onizle/uygula`, `excel_tam_yukle(dosya, senaryo)` | Faz 1 `excel_okuyucu` yeniden kullanılır; önizleme olmadan yazma yok |
| `karsilastirma_servisi` | `ambalaj_kg_trendi(urun_ailesi)`, `gecen_yil(urun)`, `enflasyon_esigi(urun)`, `senaryo_farki(urun, s1, s2)` | Faz 5; imzalar şimdiden sabit |

---

## 4. API sözleşmesi (FastAPI, `/api/v1`)

Tüm yanıtlar JSON; tutarlar string olarak (`"38.130789"`) gider ki JS float'a düşmesin. Hatalar: `{ "hata": "kod", "mesaj": "Türkçe açıklama", "alanlar": {...} }`. Listeler `?sayfa=&boyut=&sirala=&filtre=` alır ve `{ "kayitlar": [...], "toplam": N }` döner (`sayfa >= 1`, `1 <= boyut <= 500`).

**Adlandırma kuralı (dondurulmuştur):** sorgu parametresi `senaryo` (tamsayı kimlik) olarak adlanır; JSON gövdeleri ve yanıtlar `senaryo_id` kullanır. Bilinmeyen `senaryo` her uçta aynı biçimde 404 döner. Ek hata kodları: benzersizlik/ilişki ihlali `409 {"hata": "cakisma"}`, beklenmeyen hata `500 {"hata": "sunucu"}` (gövdede yığın izi yoktur). Kullanıcı `X-Kullanici` başlığıyla gelir (yüzde-kodlu olabilir); zaman damgaları UTC ISO (`+00:00`).

Tüm yanıtlar `response_model` ile şemalanmıştır; frontend tipleri `/openapi.json`'dan üretilir.

**Hesaplama tarihi (`tarih`) kapsamı:** `tarih` yalnızca *tarihe bağlı* verileri seçer: malzeme fiyatları, parametre değerleri ve fire kuralları o tarihte geçerli olan kayıttır. Reçete (aktif versiyon), gider havuzları, ambalaj sınıfları, üretim hedefleri ve ürün/malzeme kartları ise her zaman *güncel* halidir. Kayıtlı hesap (`maliyet_hesabi`) girdiyi, kullanılan malzeme kartlarını, reçete kimliği/versiyonunu ve varsa `override`'ı snapshot'ta saklar.

| Yöntem | Yol | Amaç |
|---|---|---|
| GET | `/senaryolar` | sezon ve senaryo listesi |
| POST | `/senaryolar` | yeni senaryo (`sezon_id`, `tur`, `ad`) |
| GET | `/parametreler?senaryo=` | geçerli değerler (+ `urun=` ile override dahil) |
| POST | `/parametreler/{anahtar}/degerler` | yeni değer (`deger`, `gecerlilik_basi`, `neden`, `kapsam`) |
| GET | `/parametreler/{anahtar}/gecmis?senaryo=` | değişiklik geçmişi |
| GET | `/parametreler/tanimlar` | parametre tanımları `[{anahtar, aciklama, birim}]` |
| GET | `/malzemeler?senaryo=&fiyatsiz=true` | malzeme + geçerli fiyat (`gecerlilik_basi`, `kaynak`: geçerli fiyat kaydından, kayıt yoksa null); `fiyatsiz=true` reçetede geçen ama kartı olmayan kodları da `{"kod", "ad": null, "kart_yok": true}` olarak ekler (ara mamul satırları hariç) |
| PATCH | `/malzemeler/{kod}/pasif` | malzemeyi pasifleştir (`degisiklik_kaydi` yazar) |
| POST | `/malzemeler/{kod}/fiyatlar` | yeni fiyat kaydı |
| GET | `/malzemeler/{kod}/fiyatlar` | fiyat geçmişi |
| GET/PUT | `/gider-havuzlari?senaryo=` | havuzlar ve anahtarlar; PUT pay toplamı kontrolü döner; PUT gövdesinde `neden` zorunlu, `degisiklik_kaydi.yeni` içinde `"_neden"` olarak saklanır |
| GET/PUT | `/ambalaj-siniflari?senaryo=` | ambalaj katsayıları; PUT gövdesi `{ siniflar: [..], neden }` (çıplak liste de kabul edilir, `neden` "(belirtilmedi)"); neden `yeni."_neden"` içinde saklanır |
| GET | `/urunler?senaryo=` | ürün listesi + son hesap özeti (dashboard); satırlarda ürün `id` |
| GET/PUT | `/urunler/{kod}` | ürün kartı, üretim hedefi |
| PATCH | `/urunler/{kod}/pasif` | ürünü pasifleştir |
| PATCH | `/urunler/{kod}/kod` | gövde `{ yeni_kod }`; kimlik değişmez, kayıtlı hesaplar korunur (geçici `SAYFA-*` kodlarını ERP koduna çevirmek için) |
| GET | `/urunler?senaryo=&gecici=` | `gecici=true` yalnız geçici kodlu (`gecici_kod`) ürünler |
| GET | `/uyarilar?senaryo=` | tüm ürünlerin hesap uyarıları `[{urun_kodu, uyari}]` |
| GET | `/urunler/{kod}/recete?senaryo=` | aktif reçete, uygulanan fire ve kaynağı |
| POST | `/urunler/{kod}/recete` | yeni reçete versiyonu (elle düzenleme) |
| POST | `/urunler/{kod}/recete/kurallara-birak?senaryo=` | gövde `{ siralar: [..] \| null, elle_degerleri_kaldir?: false }`; aktif reçeteyi yeni versiyon olarak kopyalar, seçili satırlarda (null: hepsi) `fire_override` boşalır ve fire kurallardan gelir → 201 |
| GET | `/urunler/{kod}/recete/versiyonlar?senaryo=` | `[{id, versiyon, kaynak, aktif, olusturma_zamani}]` |
| GET | `/receteler/{id}` | bir reçete versiyonunun satırları |
| POST | `/urunler/{kod}/hesapla` | `satirlar[]` her satırda `sira` (reçete sırası, 1 tabanlı) ve `doviz` (malzeme para birimi) taşır; maliyet satırlarında ve eski snapshot'larda null. Gövde: `{ senaryo_id, tarih?, override? }` → `MaliyetSonucu` (kaydetmez). `override` tiplidir: `{ parametreler: {anahtar: deger}, fire: {sira: oran}, uretim: {...} }`; bilinmeyen alan 422, `sira` 1..satır sayısı, `teklif_kar.N` için `N >= 1`, gerçekleşen senaryoda `enflasyon` override edilemez |
| POST | `/urunler/{kod}/hesaplar` | hesabı kaydet (snapshot) → `maliyet_hesabi_id` |
| GET | `/urunler/{kod}/hesaplar?senaryo=` | kayıtlı hesaplar, yeniden eskiye `[{id, hesap_tarihi, olusturan, maliyet_tl, satis_tl, son_tur_no, son_kar_orani, son_musteri, son_durum}]` (`son_*`: hesabın en yüksek tur_no'lu teklifi, yoksa null) |
| GET | `/hesaplar/{id}` | kayıtlı hesap: snapshot'lar + `gorunum` (canlı `/hesapla` yanıtıyla aynı biçim; arayüzde tek çizici) |
| GET | `/degisiklikler?tablo=&kayit_id=` | `degisiklik_kaydi` listesi |
| POST | `/hesaplar/{id}/teklifler` | yeni tur (`kar_orani`, `musteri`) |
| GET | `/hesaplar/{id}/teklifler` | tüm turlar |
| GET | `/teklifler?senaryo=&durum=&musteri=&sayfa=&boyut=` | senaryodaki tüm teklif turları, en yeni önce, `{kayitlar: [{teklif_id, hesap_id, urun_kodu, urun_ad, hesap_tarihi, tur_no, kar_orani, fiyat_tl, fiyat_usd, fiyat_eur, musteri, durum, olusturan, olusturma_zamani}], toplam}`; `durum` tam eşleşme, `musteri` büyük/küçük harf duyarsız içerir |
| GET | `/fire-kurallari?senaryo=` / POST | kurallar ve gruplar |
| GET/POST | `/malzeme-gruplari` | fire grupları (üyeleriyle) ve yeni grup |
| POST | `/import/fiyat-listesi` (multipart; `senaryo`, `gecerlilik_basi`) | önizleme: yeni/değişen/aynı fiyatlar, `gecerlilik_basi` tarihindeki geçerli fiyata göre |
| POST | `/import/fiyat-listesi/uygula` (multipart; `senaryo`, `gecerlilik_basi`, `neden`) | yalnız önizlemedeki "değişen" satırları yazar → `{ yazilan, kodlar }` |
| POST | `/import/recete` / `.../uygula` | ürün reçetesi önizle ve yaz |
| POST | `/import/excel-tam` | mevcut Fiyat Çalışma Excel'ini bütünüyle yükle (ilk kurulum ve gerçekleşen dosyası); form alanı `kartlari_guncelle` (varsayılan true); dosya en çok 25 MB; yanıtta `kart_farklari` ve `yeniden_adlandirilan` |
| GET | `/karsilastirma/...` | Faz 5 |
| GET | `/disa-aktar/urunler.xlsx?senaryo=` | dashboard'u Excel'e |

`satirlar[].miktar_kaynagi` / `fiyat_kaynagi` gider satırlarında `"-"`; `brut_miktar_elle` / `birim_fiyat_elle` reçete satırındaki girilmiş değerdir (yoksa `null`). `toplamlar_firesiz` / `fiyatlar_firesiz` `toplamlar` / `fiyatlar` ile aynı anahtarları taşır; firesiz alanı olmayan eski kayıtlı hesapların `gorunum`unda `null` döner. `POST /urunler/{kod}/recete` gövdesinde her satır `brut_miktar_elle` ve `birim_fiyat_elle` (`>= 0`, isteğe bağlı) alabilir; `GET .../recete` ve `GET /receteler/{id}` bunları döner. Dashboard (`GET /urunler`) satırlarına `maliyet_tl_firesiz`, `maliyet_usd_firesiz` eklenir; `disa-aktar/urunler.xlsx` "Maliyet TL (firesiz)" sütununu içerir.

`POST /urunler/{kod}/hesapla` yanıtı (özet):
```json
{
  "urun_kodu": "...", "senaryo": "...", "hesap_tarihi": "2026-10-21",
  "satirlar": [{ "kalem": "...", "grup": "malzeme", "miktar": "1", "brut_miktar": "1.020408",
                 "birim_fiyat": "5.9", "tutar": "7.525510", "maliyet_yuzdesi": "0.197360", "fiyat_yuzdesi": "0.164467",
                 "fire_orani": "0.02", "fire_kaynagi": "tip:ambalaj",
                 "tutar_firesiz": "7.375000", "miktar_kaynagi": "fire", "fiyat_kaynagi": "liste",
                 "brut_miktar_elle": null, "birim_fiyat_elle": null }],
  "toplamlar": { "malzeme": "...", "direkt_iscilik": "...", "gug": "...", "diger": "...", "giydirilmis": "...",
                 "finansman_tl": "...", "maliyet_tl": "38.130789", "maliyet_usd": "0.654579", "maliyet_eur": "..." },
  "fiyatlar": { "satis_tl": "45.756947", "satis_usd": "...", "suzme_kg_tl": "254.205262",
                "teklifler_usd": ["0.785494", "0.765857", "0.746220"] },
  "toplamlar_firesiz": { "malzeme": "...", "...": "toplamlar ile aynı anahtarlar", "maliyet_tl": "36.9..." },
  "fiyatlar_firesiz": { "satis_tl": "...", "...": "fiyatlar ile aynı anahtarlar" },
  "kullanilan_parametreler": { "enflasyon": "0.25", "kur.USD": "50", "faiz.TL": "0.40", "stok_ay.TL": "6" },
  "uyarilar": ["... fiyat listesinde yok, 0 TL alındı"]
}
```

---

## 5. Frontend (Faz 4)

**Yığın:** React 18 + Vite + TypeScript; TanStack Query (sunucu durumu, önbellek), TanStack Table (büyük tablolar), react-hook-form + zod (formlar), Tailwind + shadcn/ui (bileşenler, açık/koyu tema), Recharts (dashboard grafikleri). Para ve tarih biçimi `Intl.NumberFormat('tr-TR')`; tutarlar string olarak gelir, gösterimde `decimal.js` ile toplanır, float toplama yok.

**Sayfalar**

| Sayfa | İçerik | Ana API |
|---|---|---|
| Dashboard (Teklif Kapak) | Ürün tablosu: reçete maliyeti, GÜG, faaliyet, finans, gider %, TL/USD/EUR, üretim adedi; filtre, sıralama, toplam satırı, Excel'e aktar; senaryo seçici; üstte fiyatsız malzeme ve pay toplamı uyarı kartları | `GET /urunler`, `/disa-aktar` |
| Ürün Maliyeti | Sol: tek reçete tablosu; sütunlar "Tutar (firesiz) | Tutar (fireli)" yan yana. Her satırın başında iki seçim: "Miktar: fire oranı / elle brüt" (elle brüt seçilirse brüt miktar kutusu açılır, `brut_miktar_elle`) ve "Fiyat: liste / elle" (elle seçilirse birim fiyat kutusu açılır, `birim_fiyat_elle`); fire kaynağı rozeti `fire`/`elle` ve fiyat rozeti `liste`/`elle` gösterir. Altta iki toplam (firesiz, fireli) ve iki satış fiyatı (`fiyatlar_firesiz.satis_tl`, `fiyatlar.satis_tl`). Orta: gider kalemleri, finansman (faiz/stok süresi inline override), toplamlar. Sağ: kalem yüzdeleri (maliyet % ve satış fiyatı %) çubuk grafik, teklif turları. "Ne olur" modu: override anında hesaplanır, "Kaydet" ile snapshot | `POST /hesapla`, `/hesaplar`, `/teklifler` |
| Reçete Aktar | Excel yükle → önizleme tablosu (eşleşen/yeni/eksik malzeme) → onay | `/import/recete` |
| Malzeme Fiyatları | Satır içi fiyat düzenleme (neden zorunlu), geçmiş çekmecesi, "fiyatsız" filtresi, toplu import | `/malzemeler`, `/import/fiyat-listesi` |
| Parametreler | Gruplu form (kur, enflasyon, faiz, stok, kâr, çarpanlar); her alanın yanında geçmiş simgesi; değişiklikte neden sor | `/parametreler` |
| Gider Dağıtım | Havuz kartları, anahtar tabloları, pay toplamı göstergesi (%100 değilse kırmızı), ambalaj katsayıları | `/gider-havuzlari`, `/ambalaj-siniflari` |
| Teklif | Tur listesi, yeni tur (kâr oranı, müşteri), teklif özeti yazdırma | `/teklifler` |
| Karşılaştırma (Faz 5) | geçen yıl, enflasyon eşiği, ambalaj/kg trendi, varsayım vs gerçekleşen | `/karsilastirma` |

**Ortak davranış:** her yazma işlemi öncesi özet onayı; silme yok (pasifleştirme var); hata mesajları Türkçe, alan altında; boş/yükleniyor/hata durumları her tabloda; klavye ile tablo gezinme; 1280px masaüstü öncelikli, 768px'e kadar bozulmaz.

---

## 6. Kapsam dışı (bu fazlarda yok)
Kimlik doğrulama ve yetki (kullanıcı sayısı netleşince), SMM entegrasyonu, satış geçmişi importu (kaynak belirsiz), PostgreSQL (SQLAlchemy ile geçiş tek satır).

## 7. Onay istenen kararlar
1. Faz 3'ün Faz 2'ye katılması (versiyonlama baştan).
2. Tutarların API'de string taşınması.
3. UI kiti: shadcn/ui + Tailwind (alternatif: MUI / Ant Design; shadcn daha hafif ve özelleştirilebilir).
4. Senaryo = sezon + tür modeli; gerçekleşen dosyası aynı import ile `tur=gerceklesen` olarak yüklenir.

---

## Faz 2 sonucu

**Uçtan uca test:** `tests/backend/test_uctan_uca_excel.py` — gerçek çalışma kitabı `import_servisi.excel_tam_yukle` ile veritabanına alınır, her ürün `hesap_servisi.hesapla` ile (DB → servisler → motor) hesaplanır ve Faz 1'in doğrudan Excel'den okuduğu beklenen değerlerle (P100, P114, P120, P124, P130, P131, P137, P145-P147) karşılaştırılır. Sonuç: 67 ürün sayfası karşılaştırıldı (32 sayfa tamamen birebir, kalanı `BILINEN_ISTISNALAR` kapsamında), 0 fark (ürün kodu olmayan 056-067 sayfaları `SAYFA-<ad>` koduyla; "(2)" kopya sayfaları atlanır). İkinci test sayfa bazında uyarı sayısını Faz 1 motoruyla karşılaştırır: `dugum_tipi` (57 ara mamul satırı) içe aktarmadan motora kadar taşındığı için sayılar eşittir.

**Son düzeltme dalgası (G1-G12):** tiplenmiş `override` ve sınır doğrulamaları; `dugum_tipi` uçtan uca; içe aktarılan reçetelerde her satır `fire_override` taşır (Excel paritesi) ve `kurallara-birak` ile satır bazında kurallara bırakılır; her `senaryo` parametresi tek bağımlılıkla (`SenaryoDep`) doğrulanır, `409`/`500` gövdeleri tekdüzedir; kayıtlı hesabın snapshot'ı malzeme kartlarını, reçete versiyonunu ve `override`'ı içerir; kart pasifleştirme, ambalaj değişiklik kaydı, `kartlari_guncelle` ve `kart_farklari`; 25 MB yükleme sınırı ve bozuk çalışma kitabında 422; fiyat listesi önizleme/uygulama aynı tarih ve aynı fonksiyonla; `SAYFA-*` ürünleri `PATCH /urunler/{kod}/kod` ile ERP koduna çevrilir; CORS (`CORS_ORIGINS`), UTC zaman damgaları; yeni okuma uçları (§4). Tüm süit `-W error` ile yeşil.

**API'yi çalıştırma:** `.\.venv\Scripts\python -m uvicorn backend.uygulama:app --reload` (önek `/api/v1`, belgeler `/docs`).

**Bilinen eksikler:** `GET /urunler` (dashboard) dosya veritabanında ~6,8 sn sürer (67 ürün canlı hesaplanır; önbellek Faz 5); sunucu tarafı malzeme araması yok; Karşılaştırma uçları Faz 5.


## Faz 4 sonucu

**Neler çalışıyor:** Vite + React + TypeScript arayüzü, 8 menü girişi (Dashboard, Ürün Maliyeti -> `/urunler` ürün seçici, Reçete Aktar, Malzeme Fiyatları, Parametreler, Gider Dağıtım, Teklifler, Uyarılar) ve `/urunler/:kod`, salt okunur `/hesaplar/:id`, 404 ("Sayfa bulunamadı") ve hata (`errorElement`) rotaları; sayfalar rota bazında yüklenir (giriş paketi 1.156 kB -> 225 kB, recharts ayrı parça); iki tutarlı (firesiz/fireli) reçete tablosu ve toplamlar, "ne olur" paneli, hesap kaydı ve teklif turları, açık/koyu tema, senaryo seçici. Üretilen API tipleri `npm run api:tipler` ile alınır.

**Testler:** Vitest 20 dosya / 169 test yeşil (`npm test -- --run`). Playwright uçtan uca 19 test yeşil (`npm run e2e`, ~1 dk): gerçek FastAPI (e2e portu **8010**, `veri/e2e.db`, `frontend/e2e/kurulum.py`, gerçek Excel içe aktarımı) + gerçek Vite sunucusu (e2e portu **5190**, `/api` vekili `API_PORT=8010`). Geliştirme sunucuları (8000/5180) açıkken de koşar. Duman akışı: Dashboard "Ürün sayısı" = 67 -> ilk ürün -> iki tutar sütunu ve iki toplam -> fire % değişince fireli toplam değişir -> "Hesabı kaydet" -> teklif turu (kâr %20) -> Teklifler sayfasında görünür. Erişilebilirlik: 8 rota x 2 görünüm (1280x800, 768x1024) konsol hatasız, koyu tema `body` zemini koyu, klavye odak halkası görünür.

**Tasarım temizliği:** Klavye odağı halkası belirgin değildi (bağlantılarda tarayıcı varsayılanı 1px); `src/index.css` içinde global `:focus-visible` (2px, `--ring`) eklendi ve `--ring` iki temada daha koyu/doygun yapıldı.

**Bilinen eksikler:** Senaryo geneli `GET /teklifler` ve `HesapSatiri` sıra/döviz alanları artık mevcut (eski eksikler kapandı). Kalanlar: base-ui `Input` ile react-hook-form uyumu sınırlı (form alanlarında ortak düz `bilesenler/Girdi.tsx` kullanılır); toast sağlayıcısı bağlanmadı (durum iletileri satır içi); arama/hat süzgeci yalnızca yüklü sayfayı kapsar (sunucu tarafı arama yok); Karşılaştırma ekranı Faz 5.

**Faz 4 sonucu - düzeltme turu 1:** Odak halkası testi artık yalnızca `outline` değerine bakar (stil `none` değil, kalınlık >= 2px). 768x1024 görünümünde her rota için yatay taşma (`scrollWidth - innerWidth <= 1`) denetlenir; taşma yok. Konsol hatası süzgeci yalnızca `/urunler/*` 404'üne indirildi. **Axe/kontrast denetimi yapılmadı**; koyu tema yalnızca `body` zemin parlaklığıyla doğrulandı. Not: 768px taşma denetimi `/urunler` ürün seçicisini ölçer; gerçek ürün ekranının (`/urunler/:kod`) 768px düzeni otomatik denetlenmedi. Arayüz `VITE_API_URL` okumaz; API adresi `vite.config.ts` proxy hedefindedir (`API_PORT` ortam değişkeni, varsayılan 8000).

**Faz 4 sonucu - son düzeltme dalgası (22.10.2026):** Final incelemenin F1-F8 / I1-I8 / M1-M7 kalemleri uygulandı ve yeniden incelendi ("onay, küçük notlarla"); notlar da kapatıldı: döviz etiketleri her para biriminde (GBP/CHF dahil) kendi birimiyle; kayıtlı hesap görünümünde reçete tablosu salt okunur (`saltOkunur`); kullanıcı adı diyaloğu "sistem" adı için de zorunlu; test kütüphanesi bekleme süresi 5 sn (tam süit yükünde kararsızlık giderildi); 768px'te üst başlık sarar, kullanıcı adı kısaltılır (yatay taşma yok).

**Faz 4 sonucu - son düzeltme turu:** Ürün Maliyeti menüsü ürün seçiciye (`/urunler`) bağlandı; 404 ve hata sayfaları eklendi. Döviz etiketleri malzeme dövizini gösterir (GBP/CHF dahil). Fiyat listesi önizlemesi 4 ondalıkla gösterilir ve tarih değişince temizlenir. Değiştirici yazmalar onay ister (elle reçete: mevcut/yeni satır sayısı; tam kitap: aynı adda senaryo; havuz: pay toplamı %100 değilse; teklif durumu kabul/red). Tek hata biçimleyici (`hataMetni`: mesaj + alan ayrıntıları), 4xx yeniden denenmez, ilk açılışta ad diyaloğu ve adsız yazma engeli, kaydedilmemiş reçete taslağında "Hesabı kaydet" kapalı, reçete sürümü dışarıdan değişince ne-olur fire'ları temizlenir. Kayıtlı hesap salt okunur görünümü (`/hesaplar/:id`). **Uçtan uca (Playwright) bu turda çalıştırılmadı;** e2e belirtimleri kullanıcı adı ön kaydı ve `/urunler` rotası için güncellendi.
