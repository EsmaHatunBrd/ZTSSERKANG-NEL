# Fiyat Çalışması Otomasyonu - Excel Analizi ve Mimari Plan

Tarih: 21.10.2026
Durum: **TASLAK - onay bekliyor** (henüz kod yazılmadı)
İncelenen dosyalar: `Fiyat Çalışma - 2026-2027 - Berrak.xlsx` (derin analiz), `09-2026 SMM v1.xlsx` (yalnızca yapısal analiz)

> Dosyalar yalnızca okundu, hiçbir değişiklik yapılmadı.

---

## 1. Sistem ne yapıyor? (Excel'in iş mantığı)

Tek cümle: **Bir ürünün reçetesinden ve gider havuzlarından birim maliyeti çıkarır, üstüne finansman ve kâr ekleyip teklif fiyatına çevirir.**

```
 PARAMETRELER (kur, enflasyon, faiz, stok süresi, fire)
        |
 S.ALMA BF (833 malzeme birim fiyatı) ----+
 Reçete (ürün başına ~28 satır) ----------+--> HAMMADDE+YARDIMCI MALZEME MALİYETİ
                                          |
 Gider Dağıtım (havuzlar, anahtarlar) ----+--> ÜRETİM GİDERLERİ (işçilik + GÜG)
 Üretim Adetleri (vardiya hedefi) --------+        + PAZARLAMA + YÖNETİM
                                                   |
                                          TOPLAM BİRİM MALİYET
                                                   |  x faiz/12 x stok ayı
                                          FİNANSMAN DAHİL MALİYET (TL, USD, EUR...)
                                                   |  x (1 + kâr)
                                          TEKLİF 1 / 2 / 3  -->  Teklif Kapak (özet)
```

### Sayfaların rolleri

| Sayfa | Rol | Not |
|---|---|---|
| `Gider Dağıtım` | Gider havuzlarını birim maliyete (₺/saniye, ₺/kg, ₺/adet) çevirir | Parametre sayfası |
| `S.ALMA BF` | 833 malzemenin bütçe birim fiyatı, para birimi, Z/S bayrağı | Fiyat listesi |
| `Üretim Adetleri` | Ürün başına vardiyalık kapasite, hedef, işçi sayısı | Girdi sayfası |
| `001` ... `067` | **Ürün başına maliyet hesabı** (aynı şablon) | Asıl motor, 69 sayfa |
| `Teklif Kapak` | 67 ürünün özeti (maliyet, gider, TL/USD/EUR, adet) | Dashboard olacak |
| `Ambalaj Özeti`, `Sayfa2` | Ambalaj ve kapak adetleri özeti (pivot) | Raporlama |
| SMM dosyası | Muhasebenin aylık Satılan Mamul Maliyeti tablosu (150/151/152/157, 710/720/730 hesapları) | **Kapsam dışı**, ileride ayrı ele alınacak |

**Gerçekleşen veri:** Kullanıcı ayrı bir "gerçekleşen" Excel'i tutuyor. Bu dosya mevcut fiyat çalışması Excel'inin **kopyası** (aynı sayfa yapısı ve başlıklar), farkı gerçekleşen fiyat ve miktarları içermesi ve enflasyon öngörüsü uygulanmaması. Dosya Faz 6'da alınacak.

---

## 2. Hesap kuralları (çıkarılan fonksiyonlar)

Referanslar `001` sayfasındaki hücrelerdir. Çıkan değerler sayfada doğrulandı.

| # | Fonksiyon | Excel karşılığı | Kural |
|---|---|---|---|
| F1 | `brutMiktar(miktar, fire)` | K8 `=I8/(1-J8)` | Fire **bölme** ile eklenir (miktar x 1,02 değil, miktar / 0,98) |
| F2 | `malzemeBirimMaliyeti(malzeme, ctx)` | P8 | Z/S='S' ve TL: `fiyat x (1+enflasyon)`; USD/EUR/GBP/CHF: `fiyat x kur` (enflasyon yok); Z/S='Z': fiyat olduğu gibi |
| F3 | `malzemeToplam(reçete)` | P100 `=SUM(P6:P99)` | Satır tutarlarının toplamı |
| F4 | `iscilikSaniyeBasina(havuz)` | G4, G13, G18 | Gider toplamı / çalışılan saniye |
| F5 | `iscilikMaliyeti(ürün)` | P105 | `(27000 sn / vardiya adedi) x personel sayısı x ₺/sn`; 27000 = 7,5 saat x 3600 |
| F6 | `malKabulMaliyeti(ürün)` | P104, P109 | Kg başına ₺ (Taze/Taze, Taze/Turşu, Turşu/Turşu) x taze miktar |
| F7 | `hatBazliGider(ürün, havuz)` | P110-P112 | Elektrik, doğalgaz, amortisman: ürünün üretim hattına (Niko, Herbort, Torba...) göre ₺/sn x saniye |
| F8 | `ambalajGiderDagitimi(ambalaj)` | Gider Dağıtım F70:G91 | Yönetim ve pazarlama giderleri **ambalaj hacim katsayısıyla** (0,5 / 0,75 / 1 / 1,25) ağırlıklandırılıp dağıtılır |
| F9 | `finansmanGideri(maliyet, faiz, stokAy)` | M124, P124 | `maliyet x faiz/12 x stok ayı` (basit faiz). TL: %40, döviz: %6, varsayılan 6 ay |
| F10 | `dovizMaliyeti(maliyet, finans, kur)` | P131 `=(P122+P125)/F150` | (Maliyet + döviz finansmanı) / kur |
| F11 | `satisFiyati(maliyet, kar)` | P137 `=P130*1.2`, P145-147 | Teklif turlarında `maliyet x (1+kâr)`; kâr %20 / %17 / %14 |
| F12 | `kalemYuzdeleri(maliyet, fiyat)` | R ve S sütunları | Her kalemin toplam maliyet içindeki ve satış fiyatı içindeki payı |
| F13 | `suzmeKgFiyati(fiyat, suzmeKg)` | P143 `=P137/E136` | Süzme kg başına fiyat |

Ek analizler (Excel'de yok, istenen): ambalaj büyüdükçe birim/kg fiyat trendi, geçen yıl satış fiyatı karşılaştırması, çıkan fiyat / (geçen yıl x enflasyon) oranı.

---

## 3. Excel'de bulduğum sorunlar (muhasebe direktörüyle netleşmeli)

Doğrulananlar:

1. **299 / 833 malzemenin fiyatı boş veya 0.** Formüller `IFERROR(...,0)` kullandığı için bu malzemeler **sessizce 0 TL** hesaplanıyor. Reçetedeki ara mamul satırları da bilerek 0 ama ayırt edilemiyor.
2. **Kâr %20 formülün içine gömülü** (`P137 = P130*1.2`). Teklif turlarındaki oranlar (%20/17/14) ayrı hücrelerde ve USD maliyet üzerinden hesaplanıyor.
3. **Dağıtım çarpanları formüllerin içinde sabit:** örn. `=49024334.97*1.35*1.3`, `=(10875000+3571433)*1.4*1.25`. Bunlar dönemden döneme değişen bütçe çarpanları, parametre olmalı.
4. **Elektrik pay toplamı %100,1, doğalgaz %99,5** (G38, G49). Dağıtım küçük de olsa tutmuyor.
5. **`Maliyet Sapma` (F149) hiçbir formülde kullanılmıyor.** 68 sayfada 0 değerinde duruyor.
6. **Brüt miktar (K sütunu):** 1909 reçete satırının yalnızca 360'ında formül var, 1549'u elle yazılmış değer. Sonradan fire eklenirse bu satırlar güncellenmiyor. *(Faz 2b: elle K ve M değerleri artık veri olarak taşınır; reçete satırında `brut_miktar_elle` / `birim_fiyat_elle` alanları vardır, okuyucu bunları Excel'den aktarır ve motor fire/liste yerine bunları kullanır. Aynı hesapta fire uygulanmamış "firesiz" paralel sonuç da üretilir.)*
7. **Sağ blok (Z-AO) sol bloğun kopyası ama bağımsız değil:** `AL131` ve teklif formülleri sol bloğa (`$P$`) bakıyor. `001` sayfasında sağ bloğun `AG` sütunu sabit değer olduğu için fire uygulanmıyor (P100 = 25,667, AL100 = 25,416). sağ blokta (AA138) 14 sayfada 1.000.000; sol blokta (E138) 2 sayfada.
8. **Şablondan sapan sayfa var:** bir sayfada satırlar 10 kaydırılmış (kur hücreleri F160, F161...). `001 (2)` ve `035 (2)` kopya sayfa. 14 üründe pazarlama/yönetim payı elle 0.
9. **Ambalaj sınıfı sayı ile aranıyor** (`E146 = 370`). `3` ve `5` değerleri (teneke) hacim 3 ml ile karışabilir.
10. **Üretim Adetleri'nde aynı ürün iki kez** var (02.044.002.002.00333).
11. **SMM dosyasında `#REF!` hataları** (ŞAHİT sayfası bağlantıları) ve elle yazılmış aylık değerler var. (Kapsam dışı, bilgi amaçlı.)

### Fire oranları (Excel'den çıkarılan gerçek dağılım)

Fiyatı olan reçete satırları tarandı. Varsayılanlar bu tabloya göre belirlenecek, tahmine göre değil.

| Malzeme türü | Satır | Fire dağılımı | Varsayılan |
|---|---|---|---|
| Etiket | 60 | 53 x %2, 7 x %0 | **%2** |
| Kapak | 55 | 49 x %2, 6 x %0 | %2 |
| Kavanoz | 51 | 46 x %2, 5 x %0 | %2 |
| Shrink naylon | 58 | 52 x %2, 6 x %0 | %2 |
| Levha | 44 | 39 x %2, 5 x %0 | %2 |
| Karton, koli, şişe, teneke, palet, sticker | ~20 | çoğunlukla %2 | %2 |
| Folyo (torba) | 8 | 8 x %4 | **%4** |
| Hammadde (taze) | 124 | 22 x %5, 1 x %2, 101 x %0 | %5 yalnızca taze; turşu/ara mamul %0 |
| Yardımcı malzeme | 542 | hepsi %0 | %0 |

Not: Görüşme notlarındaki "etiket %1" Excel'de yok; etiket varsayılanı %2. %0 olan istisnalar satır bazında override ile korunur.

Doğrulanmayanlar (sorulacak): Z ve S bayrağının tam anlamı, sağ bloğun amacı, `I104 = K17` bağlantısının (mal kabul miktarı) her üründe doğru satırı gösterip göstermediği.

---

## 4. Veri modeli

```
Sezon/Senaryo ──< ParametreDeğeri >── Parametre (kur, enflasyon, faiz, stok ayı, kâr, çarpanlar)
     |                (anahtar, kapsam, değer, geçerlilik_başı, kim, neden)  <-- append-only
     |
     +──< MalzemeFiyatı >── Malzeme (kod, ad, tip, birim, para, Z/S)
     |
     +──< GiderHavuzu >──< DağıtımAnahtarı (alt kalem, pay %, baz: sn / kg / adet)
     |        |
     |        +── AmbalajKatsayısı (hacim sınıfı → katsayı)
     |
Ürün (kod, ad, ambalaj, hat, taze/turşu, süzme kg, ihracat/yurtiçi)
     +──< ÜretimHedefi (sezon, hedef vardiyalık üretim, net/toplam süre kapasitesi, dolum ve etiket personel sayısı, etiketleme adedi)
     +──< ReçeteSatırı (malzeme, miktar, birim, fire_override, düğüm_tipi: yaprak | ara_mamul)
     +──< FireKuralı (kapsam: tip / grup / malzeme, oran, öncelik)
     |
MaliyetHesabı (snapshot: ürün + parametre seti + senaryo türü + tarih)
     +──< MaliyetSatırı (kalem, tutar, maliyet %, fiyat %)
     +──< Teklif (tur no, kâr, fiyat TL/USD/EUR, müşteri, durum)   <-- tur sayısı sınırsız
SatışGeçmişi (ürün, müşteri, tarih, fiyat, adet)    <-- "geçen yıl kaça sattım" (kaynak henüz belirsiz)
```

Senaryo türü (`fiyat_çalışması` / `gerçekleşen`) aynı motoru ve aynı tabloları kullanır. Gerçekleşen Excel'i bu Excel'in kopyası olduğu için **ayrı bir "Gerçekleşen" varlığına gerek yok**: aynı import, `senaryo = gerçekleşen` ve enflasyon = 0 ile yüklenir.

### Çözülen gereksinimler

| İstek | Çözüm |
|---|---|
| Fiyat değişsin ama eski kayıt kaybolmasın | Parametre ve fiyat tabloları **append-only**; her değişiklik yeni satır (kim, ne zaman, neden) |
| Faiz / stok süresi / finansman varsayılan gelsin, değiştirilebilsin | Varsayılan = sezon parametresi; ürün bazında override; değişiklik geçmişte kalır |
| Fire varsayılan veya kullanıcı seçsin, gruplansın | `FireKuralı` öncelik sırası: reçete satırı > kullanıcı grubu > malzeme > tip. Tip varsayılanları Excel'den: ambalaj (etiket, kapak, kavanoz, shrink, levha, karton...) %2, folyo %4, taze hammadde %5, yardımcı malzeme %0. Reçete içe aktarılırken satırdaki fire değeri aynen korunur |
| Teklif turu sayısı değişebilir | `Teklif` tablosunda tur numarası, sabit 3 değil |
| Reçete Excel'den aktarılsın | Import sayfası: ERP çıktısı → önizleme → eşleştirme → onay |
| Enflasyon sadece yeni ürün fiyat çalışmasında | Senaryo türü: `fiyat_çalışması` (enflasyon uygular) / `gerçekleşen` (uygulamaz) |

---

## 5. Mimari

Hesap motoru **saf fonksiyonlar** olarak ayrı katmanda yazılır (veritabanı ve arayüzden bağımsız). Bu sayede Excel ile birebir karşılaştırılabilir ve test edilebilir.

```
[Arayüz]  Dashboard | Ürün Maliyeti | Reçete Aktar | Fiyatlar | Parametreler | Dağıtım | Teklif | Karşılaştırma
    |  REST
[API]     /urunler  /receteler  /malzeme-fiyatlari  /parametreler  /gider-havuzlari
          /hesapla (POST)  /maliyet-hesaplari  /teklifler  /karsilastirma  /import/*
    |
[Servis]  HesapServisi  ImportServisi  VersiyonServisi  KarsilastirmaServisi
    |
[Motor]   F1-F13 saf fonksiyonlar + doğrulama (fiyatı olmayan malzeme = 0 TL + uyarı (Faz 1 paritesi); arayüz uyarıyı göstermeli)
    |
[Veri]    SQL veritabanı (para tutarları Decimal / kuruş)
```

### Teknoloji önerisi (onay istiyorum)

Henüz seçilmedi. Önerim: **Python (FastAPI) + SQLite (sonra PostgreSQL) + React/Vite arayüz.**
Gerekçe: `Decimal` ile kuruş hassasiyeti, Excel/CSV okuma kolaylığı, tek kişilik geliştirme için sade kurulum.
Alternatif: TypeScript ile uçtan uca (Node + React); tek dil avantajı var, Excel okuma biraz daha zahmetli.

### Ekranlar

1. **Dashboard (Teklif Kapak):** 67 ürün, maliyet/gider yüzdeleri, TL/USD/EUR, üretim adedi, filtre ve Excel dışa aktarma.
2. **Ürün Maliyeti:** reçete tablosu, fire düzenleme, gider kalemleri, finansman, fiyatlar, **kalem yüzdeleri**, teklif turları.
3. **Reçete Aktar:** Excel yükle, önizle, eşleştir, onayla.
4. **Malzeme Fiyatları:** satır içi düzenleme, değişiklik geçmişi, fiyatsız malzeme uyarı listesi.
5. **Parametreler:** varsayılanlar, düzenleme, geçmiş ("bu değer ne zaman, kim tarafından değişti").
6. **Gider Dağıtım:** havuzlar, anahtarlar, pay toplamı kontrolü (%100 değilse uyarı).
7. **Karşılaştırma:** geçen yıl fiyatı, enflasyon eşiği, ambalaj boyutuna göre kg fiyatı, varsayım ve gerçekleşen.

---

## 6. Doğrulama stratejisi (en önemli güvence)

Excel'deki mevcut sonuçlar **altın referans** olarak testlere konur. Örnek (`001`, Biberiye Turşu 370 ml):

| Çıktı | Excel değeri |
|---|---|
| Hammadde + yardımcı malzeme (P100) | 25,6668 |
| Gider toplamı (P114) | 4,8168 |
| Pazarlama + yönetim (P120) | 1,2921 |
| Finansman (P124) | 6,3551 |
| Finansman dahil maliyet (P130) | 38,1308 TL |
| USD maliyet (P131) | 0,65458 |
| Teklif 1 / 2 / 3 (USD) | 0,78549 / 0,76586 / 0,74622 |

Hedef: 67 ürünün tamamında yeni sistem Excel ile **kuruşu kuruşuna** aynı çıkmalı (bilinen Excel hataları listesi hariç). Fark çıkarsa hangisinin doğru olduğuna muhasebe direktörü karar verir.

### Faz 1 parite sonucu (10-21-2026)

`scripts/excel_parite_raporu.py` motoru 69 ürün sayfasına ve Gider Dağıtım oranlarına karşı çalıştırır; `tests/test_excel_paritesi.py` bunu altın referans olarak doğrular.

- **Gider Dağıtım oranları (G/F sütunları): tamamı birebir uyuştu.** `001` dahil 32/69 ürün sayfası her alanda birebir uyuştu. **Faz 2b güncellemesi:** elle K/M değerleri veri olarak taşınınca (`brut_miktar_elle`, `birim_fiyat_elle`) birebir uyuşan sayfa sayısı **57/69** oldu; `BILINEN_ISTISNALAR` 933 kayıttan 331 kayda indi. Kalan 12 sayfa: maliyet satırı elle 0/sabit (B: `001 (2)`, `012`, `013`, `022`, `040`, `041`, `042`, `048`, `055`), `N` (Z/S) elle yazılmış (`040`, `043`, `044`) ve `053` mutlak referans kayması (C). Aşağıdaki A maddesi tarihsel olarak Faz 1 durumunu anlatır; K/M kaynaklı fark kalmadı.
- Kalan 37 sayfanın tamamında fark, motor hatasından değil Excel'deki elle müdahalelerden geliyor; her (sayfa, alan) çifti `BILINEN_ISTISNALAR` içinde gerekçesiyle listelidir (727 kayıt). Bu sayfalarda Excel'in kendi satır değerleri motora verildiğinde (reçete satırı P değerleri), kalan farklar yalnızca aşağıdaki B ve C nedenlerinden oluşur; yani formül zinciri (P100'den P147'ye) doğrudur.
- **A. Reçete satırlarında elle müdahale (34 sayfa):** `K` (brüt miktar) hücresi `I/(1-J)` yerine elle yazılmış (örn. fire J sütununda var ama K'ya yansıtılmamış) veya formülün içine sabit bölen/çarpan gömülmüş (`=I/0.98`, `=I/(1-J)*0.8`); `M` (birim fiyat) hücresi fiyat listesi araması yerine elle yazılmış (listede fiyatı 0 olan veya hiç olmayan malzemelerde); `043` ve `044`'te `N` (Z/S) hücresine küçük harfle `s` yazılmış. Motor reçetedeki `J` fire oranını uyguladığı için bu satırlarda ayrışır.
- **B. Maliyet satırlarında elle 0/sabit (9 sayfa):** `001 (2)` (kopya sayfa, P104-P113 elle 0), `012`, `013`, `042`, `048` (satır miktarı I elle 0/1), `040` (M elle 0), `041` (I112 elle 0), `022` (P105=20, P113=10 elle yazılmış), `055` (P105/P108/P110/P111/P118/P119 elle 0).
- **C. `053` satır kayması:** P131, P138, P145-P147 formülleri kaydırılmamış mutlak referans (`$P$117`, `$P$120`, `$P$126`) kullanıyor; USD maliyet ve teklifler yanlış hücrelere bakıyor. P130 ve P132-P133 uyuşuyor.

**Firesiz (sağ blok) parite sonucu (Faz 2b) - EMEKLİ 22.10.2026.** Sağ blok (Z–AO) deneme/önemsiz bulunduğu için (kullanıcı kararı 22.10.2026) bu karşılaştırma, `tests/test_excel_firesiz_paritesi.py` ve `firesiz_farklari`/`karsilastir_firesiz` kaldırıldı. Sistemin kendi firesiz tanımı (aynı girdiler, tüm fireler 0, mal kabul dahil) değişmedi. Aşağıdaki tespit tarihsel kayıt olarak durur: Motorun `firesiz` paralel sonucu sağ bloğun (`AA:AL`) `AL100, AL114, AL116, AL120, AL122, AL124, AL130, AL131, AL137` hücreleriyle karşılaştırılır (`tests/test_excel_firesiz_paritesi.py`, `fiyat_motoru.parite.firesiz_farklari`). Sağ blok sol bloğun bağımsız kopyası olduğu için (`Z` kodları, `AE/AG` miktarları, `AI` fiyatları, `AA136:AA146` üretim girdileri, `AB148:AB153` enflasyon/kurlar) birebir beklenmez: **AL100 69 sayfanın 8'inde, AL130 4'ünde birebir** (AL130: `008`, `009`, `010`, `054`); 66 sayfadaki 515 fark `FIRESIZ_ISTISNALARI`nda hücre adresleriyle gerekçelendirilmiştir. Sistematik nedenler: `AL131 = ($P$122+$P$125)/AB150` sol bloğun (fireli) hücrelerine bağlı; `AA138≠E138`/`AA140≠E140`/`AA141≠E141` gibi üretim girdisi farkları; `Z≠D` malzeme kodu, `AG≠I` elle brüt miktar ve `AI≠M` birim fiyat farkları; `013` sağ bloğunda `#REF!`.

**Muhasebe direktörüne yeni sorular**

1. Reçetede `K` hücresini elle yazan ya da formüle sabit bölen gömen satırlar (A) bilinçli bir fire/pay kuralı mı, yoksa güncellenmemiş eski değer mi? Bilinçliyse motor reçeteye "brüt miktar" ve "bileşen oranı" alanı eklemeli.
2. Fiyat listesinde olmayan veya fiyatı 0 olan malzemeler için reçetede elle yazılan `M` fiyatı geçerli fiyat mıdır? Öyleyse fiyat listesine işlenmeli.
3. B grubundaki elle 0 yazılan maliyet satırları (örn. `001 (2)`, `055`) gerçekten sıfır maliyet mi, yoksa unutulmuş formüller mi?
4. `022` sayfasındaki sabit P105=20 ve P113=10 hangi varsayıma dayanıyor?
5. `053` sayfası düzeltilecek mi? Düzeltilmezse USD maliyeti ve teklifleri hatalı kalır.

---

## 7. Fazlar

| Faz | İçerik | Çıktı |
|---|---|---|
| 0 | Açık soruların cevabı, teknoloji kararı | Onaylı kapsam |
| 1 | Hesap motoru (F1-F13) + Excel doğrulama testleri | Çalışan motor, 67 üründe parite |
| 2 | Veri modeli + import (fiyat listesi, reçete, gider dağıtım, üretim adetleri) | Veri sistemde |
| 3 | Parametre ve fiyat versiyonlama, değişiklik geçmişi | Geçmiş kaybolmuyor |
| 4 | Arayüz: ürün maliyeti + dashboard | Kullanılabilir ilk sürüm |
| 5 | Teklif turları + analizler (geçen yıl, enflasyon, ambalaj, kg fiyatı) | Tam fiyat çalışması |
| 6 | Gerçekleşen Excel'inin aynı import ile `senaryo = gerçekleşen` olarak yüklenmesi | Varsayım / gerçekleşen karşılaştırma ekranı |
| 7 (ileride) | Muhasebe SMM tablosu entegrasyonu | Şu an kapsam dışı, ayrıca planlanacak |

Agent dağılımı: **orkestratör** istekleri çevirir, **backend** Faz 1-3 ve import, **arayüz** Faz 4-5. Faz 1'den önce motorun doğruluğu muhasebe direktörüyle teyit edilmeli.

---

## 8. Açık sorular

1. **Z/S bayrağı** tam olarak ne demek (Zeytursan içi / satın alma?) ve enflasyon neden yalnızca 'S' + TL fiyatlara uygulanıyor?
2. **Fiyatı boş 299 malzeme:** hangileri gerçekten kullanılmıyor, hangileri eksik veri?
3. **Kâr oranı:** Excel'de P137'deki %20 mi geçerli, teklif turlarındaki %20/17/14 mü? İkisi ayrı mı kullanılıyor?
4. **Gider dağıtımındaki çarpanlar** (1,35 x 1,3 gibi) ne anlama geliyor? Her sezon değişen enflasyon/zam katsayıları mı?
5. **"Geçen sene kaça sattım" verisinin kaynağı:** Fiyat Çalışma dosyasında yok. ERP'den mi gelecek, ayrı Excel mi? Bu veri olmadan geçen yıl ve enflasyon karşılaştırması yapılamaz.
6. **Kullanıcılar:** tek kişi mi, ekip mi? Yetkilendirme (kim fiyat değiştirebilir) gerekir mi?
7. **Z bayraklı döviz fiyatlı 2 malzeme** (043/044'te N14 elle 's' yapılmış): kur uygulanmalı mı?
8. **Yurtdışı yüzde ve finansman kuralı** (ihracat sayfası yok).
9. **056-067 sayfalarının ERP ürün kodu yok** (ARGE?).
10. **3 sayfada stok süresi 2 ay:** ürün bazlı mı, hata mı?

Kapanan sorular:
- Elle yazılan K/M değerleri elle kalır; fire yazılan satırda fire uygulanır; yeni üründe satır bazında seçim (kullanıcı kararı 21.10.2026).
- Firesiz hesap = sistemin kendi tanımı (aynı girdiler, tüm fireler 0, mal kabul dahil); Excel sağ bloğu (Z-AO) deneme, önemsiz - kullanıcı 22.10.2026. Tek tabloda firesiz ve fireli toplam gösterilecek (kullanıcı kararı 21.10.2026).
- Etiket fire oranı: Excel'e göre %2 (görüşme notundaki %1 kullanılmayacak).
- Gerçekleşen veri: SMM dosyası değil; kullanıcının bu Excel'in kopyası olarak tuttuğu ayrı dosya. Faz 6'da alınacak.
- SMM tablosu: şu an kapsam dışı, ileride dahil edilecek.
