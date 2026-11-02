# Faz 4c Kapanış Raporu — "Hücreye yaz, tek Kaydet"

Tarih: 22.10.2026 · Plan: `docs/10-22-2026-faz4c-hucreye-yaz-tek-kaydet-plani.md` · Durum: **kapandı** (final inceleme + 1 düzeltme dalgası, yeniden inceleme temiz)

## Ne değişti (kullanıcı gözüyle)
- Ürün Maliyeti ekranında her sayı hücresi Excel gibi yazılır yazılmaz hesaba girer (300 ms sonra sunucu hesabı): reçete miktar / fire % / brüt (elle) / birim fiyat (elle), gider kalemi birim fiyatları (₺/sn, ₺/kg), üretim bilgileri (hat, sınıf, ambalaj, süzme kg, pazar, vardiya, personel, mal kabul), kurlar, enflasyon, maliyet sapma, faiz ve stok süresi.
- Üst şerit: **N değişiklik · Kaydet · Vazgeç**. "Ne olur", "Kalıcı kaydet", "Reçeteyi kaydet", "Hesabı kaydet" düğmeleri kalktı.
- **Kaydet** diyaloğu: değişiklik listesi (eski → yeni), etki rozeti ("Bu ürün" / "Senaryo geneli — tüm ürünleri etkiler" / "Yalnız bu hesapta"), senaryo geneli parametreler için "yalnız bu ürün için yaz" seçeneği, tek zorunlu neden, "Hesabı da kaydet". Tek istekle hepsi ya da hiçbiri yazılır; geçmiş tabloları (parametre, reçete sürümü, havuz, değişiklik kaydı) dolar; hesap numarası gösterilir.
- Reçete artık Excel'deki seviye sütunuyla ağaç gibi girintili (└ işareti); ürün satırı kalın.
- Sayfadan ayrılırken kaydedilmemiş değişiklik uyarısı.

## Teknik
- Backend: `OverrideGiris` + `satirlar / urun / gider_oranlari`; `POST /urunler/{kod}/kaydet` (`TopluKaydetGiris`, opsiyonel `override` yalnız kaydedilen hesaba uygulanır; `hesabi_kaydet=false` + override → 422); `ReceteSatiri.seviye` (açılışta idempotent `ALTER TABLE`), import A sütunundan okur; `urun_kaydet`/`uretim_hedefi_kaydet` `neden` taşır. Testler: 218 → 259 (`-W error`); final düzeltme: ürün-kapsamlı parametre varken senaryo geneli kayıt ürün kopyasını da yazar ve uyarı verir; kalıcı yazım + hatalı override → 422 ve geri alma testi; commit başarısız → 500 testi.
- Frontend: tek taslak (`urun/Taslak.ts`: `taslakYamasi` tek yazma kapısı, `taslaktanOverride`, `taslaktanKaydetGovdesi`, `degisiklikListesi`), `DegisiklikSeridi`, `KaydetDiyalogu`, hücreler taslağa bağlı, `HesapGoruntule` seviye + override listesi. Testler: 193 → 252; tsc 0; build ok; Playwright 21/21 (duman: fiyat değiştir → Kaydet → yenile → kalıcı; kur-kaydet: senaryo geneli → Parametreler geçmişi; girinti).
- Canlı veri: backend 8000 yeni derlemeyle çalışıyor; 67 aktif reçetenin seviyeleri Excel'den tek seferlik dolduruldu; Üretim Adetleri (71) ve ZAR/RUB/sapma/satış notu "mevcut senaryoyu tamamla" ile yüklendi.

## Kontrolörün kararları (yanlışsa düzeltin)
1. Gider oranı kalıcı yazımı yalnız saniye bazlı dört havuz (dolum, etiket, endirekt işçilik, diğer GÜG): `toplam_tutar = oran × baz_miktar`, baz sabit. Sınıf/hat bazlı oranlar (mal kabul işçilik/GÜG, elektrik) ve doğalgaz/amortisman yalnız bu hesapta (ne-olur) kalır; kalıcı yazım Gider Dağıtım sayfasından.
2. Kur/enflasyon/maliyet sapma varsayılan **senaryo geneli** (diyalogda uyarı; "yalnız bu ürün" seçilebilir); faiz/stok/vardiya saati **ürün** kapsamlı.
3. Hat/sınıf değişince eski hat/sınıfa bağlı gider oranı taslakları sessizce düşer.
4. Reçete seviyesi: Excel A sütunu 0–5 saklanır; metin ('A') None; eski kayıtlar için girinti `dugum_tipi` sezgisine düşer.
5. Dashboard ilk yükleme yavaşlığı (67 ürün canlı hesap) Faz 5 işi; e2e'de tek bekleme sabiti.
6. `kaliciKayit.ts`, `NeOlurPaneli.tsx` silindi; sağ blok (Z–AO) parite testi ve okuyucu kodu silindi (ayrı görev, aynı gün).

## Ertelenenler (final inceleme; hiçbiri teslimi engellemez)
- Kaydet diyaloğundaki "N ürünü etkiler" sayısı pasif ürünleri de sayabilir; sayı dashboard listesinden (`boyut=1`) alınır, diyalog açılınca yüklenir.
- Ürün-kapsamlı kopya, değer zaten aynıysa da yazılır (fazladan geçmiş satırı + uyarı).
- Parametre değerleri seçili hesap tarihinden itibaren geçerli yazılır; diyalog bu tarihi göstermiyor.
- POST asılı kalırsa Kaydet diyaloğu kilitli (zaman aşımı yok); ürün/senaryo değişince uçuştaki POST'un başarı geri çağrısı yeni taslağı silebilir.
- Hat/sınıf değişince eski ankete bağlı gider oranı taslakları sessizce düşer; `mal_kabul_` önek sezgisi.
- e2e: `E2E_URUN_KODU`/`senaryo=1` sabit; dashboard beklemesi 45 sn (Faz 5 T1 önbellek ile 15 sn'ye iner).
- Gerçekleşen senaryoda enflasyon hücresi "Eski değer —" gösterir.
- Teknik: `override_sozlugu` boş `{}` gürültüsü snapshot'ta; seviye okuma `isdigit`; `gider_oranlari` yazım hatası sessiz; decimal.js 20 basamak hassasiyet.
