# Faz 4c — "Hücreye yaz, tek Kaydet" Uygulama Planı

Tarih: 22.10.2026 · Durum: **onaylandı (22.10.2026 "onaylıyom"), uygulanıyor**
Önceki: `10-22-2026-faz4b-excel-duzeni-ve-son-duzeltmeler-plani.md`, kapanış `10-22-2026-faz4b-kapanis-raporu.md`
Karar (22.10, kullanıcı "ok"): Ürün ekranındaki her düzenlenebilir hücre anında yeniden hesaplasın; tek **Kaydet** tümünü geçmişe yazsın; gider ₺/sn oranları ürün ekranından düzenlenebilsin.

## 1. Hedef (Excel alışkanlığı)
Excel'de kullanıcı hücreye yazar, sayfa anında yeniden hesaplanır, dosyayı kaydeder. Sistemde karşılığı:
- **Yaz → anında hesap:** her hücre taslağa yazılır, sunucu hesabı 300 ms gecikmeyle yenilenir (mevcut `useHesapla`; motor ~100 ms).
- **Tek Kaydet:** üst şeritte "N değişiklik · Kaydet · Vazgeç". Kaydet diyaloğu değişiklik listesini (eski → yeni, etki alanı) gösterir, tek *neden* ister, tek istekle **atomik** yazar (hepsi ya da hiçbiri) ve hesabı snapshot olarak saklar.
- **Geçmiş korunur:** parametre/fiyat/havuz tabloları append-only; reçete yeni sürüm; ürün kartı/hedef `DegisiklikKaydi`.

## 2. Bugünkü durum (neden yetersiz)
| Alan | Anında hesap | Kalıcı yazım |
|---|---|---|
| Reçete elle brüt / elle fiyat | **yok** (önce "Reçeteyi kaydet") | Reçeteyi kaydet (yeni sürüm) |
| Reçete fire %, parametreler, hedef alanları | var (override) | **yok** ürün ekranından; hedef için ayrı "Kalıcı kaydet" |
| Ürün kartı (hat, sınıf, ambalaj, süzme kg, pazar) | **yok** | Kalıcı kaydet (2 ardışık PUT, atomik değil) |
| Kur / enflasyon / faiz / stok | var (override) | yalnız Parametreler sayfasından |
| Gider ₺/sn oranları | **yok** | yalnız Gider Dağıtım sayfasından |
| Hesap snapshot | — | "Hesabı kaydet" (ayrı düğme) |

Üç ayrı kayıt düğmesi + bir "ne olur" paneli → kullanıcı için karışık.

## 3. Tasarım

### 3.1 Backend
**A1. Override genişler** (`OverrideGiris`, motor değişmez):
- `satirlar: dict[int, {miktar?, brut_miktar_elle?, birim_fiyat_elle?}]` → reçete satırı geçici olarak değiştirilir (elle değer anında hesaba girer; elle brüt + fire override çakışması mevcut 422 kuralıyla).
- `urun: {hat?, taze_tursu_sinifi?, ambalaj_hacmi?, suzme_kg?, pazar?}` → `UretimBilgisi` geçici.
- `gider_oranlari: dict[str, Decimal]` anahtarlar: `dolum_iscilik_sn, etiket_iscilik_sn, endirekt_iscilik_sn, diger_gug_sn, mal_kabul_iscilik_kg.<sınıf>, mal_kabul_gug_kg.<sınıf>, elektrik_sn.<hat>` → `GiderOranlari` üzerinde `replace`.
- `kullanilan_parametreler` ve `girdi_snapshot.override` yeni alanları da taşır.

**A2. Yeni uç `POST /urunler/{kod}/kaydet`** (tek oturum, tek commit = atomik):
```
{ senaryo_id, tarih, neden,
  urun?: UrunGiris alanları (değişenler),
  uretim_hedefi?: UretimHedefiGiris,
  recete?: ReceteSatirGiris[] (tam liste; değişmediyse gönderilmez),
  parametreler?: [{anahtar, deger, kapsam: "urun"|"genel"}],
  gider_havuzlari?: [{kod, toplam_tutar}],
  hesabi_kaydet: true }
```
Sıra: ürün kartı → hedef → reçete sürümü → parametre değerleri (`gecerlilik_basi` = hesap tarihi, `neden`) → havuz (`neden`) → hesap snapshot. Yanıt: `{hesap, yazilan: {urun, hedef, recete, parametre, havuz}, uyarilar}`. Tekil uçlar kalır (geriye uyum, diğer sayfalar).

**A3. Gider oranı → havuz eşlemesi.** Oran = `toplam_tutar / baz_miktar`. Ürün ekranından oran yazıldığında kalıcı yazım havuzun **toplam tutarını** `oran × baz` olarak günceller (baz sabit). Senaryo geneli etki → diyalogda açık uyarı.

**A4. Parametre kapsamı varsayılanı.** `faiz.*`, `stok_ay.*`, `vardiya_saati` → **ürün** kapsamı (DB zaten destekliyor: `kapsam_tipi="urun"`). `kur.*`, `enflasyon`, `maliyet_sapma` → **genel** (Excel'de tek yerde) + diyalogda "senaryo geneli, N ürünü etkiler" uyarısı; kullanıcı diyalogda "yalnız bu ürün" seçebilir.

### 3.2 Frontend
**B1. Tek taslak modeli** `Taslak = {urun, hedef, satirlar, parametreler, giderOranlari}`; her hücre → taslak → `hesaplaGovdesi` (override) → sunucu hesabı. "Ne olur" paneli ve "Kalıcı kaydet"/"Reçeteyi kaydet"/"Hesabı kaydet" düğmeleri kalkar; üst şerit: `N değişiklik · Kaydet · Vazgeç`. Değişen hücre vurgusu (mevcut `vurgu`), hücre tooltip'inde eski değer.
**B2. Kaydet diyaloğu:** değişiklik tablosu (alan · eski → yeni · etki: "bu ürün" / "senaryo geneli — N ürün"), tek *neden* (zorunlu), "Hesabı da kaydet" (varsayılan açık). Gönder → `POST /urunler/{kod}/kaydet`; başarı → sorgular yenilenir, taslak sıfır, hesap numarası gösterilir.
**B3. Düzenlenebilir hücreler:** Reçete: Miktar, Fire %, Brüt (elle), Birim fiyat (elle), "kurala bırak" ikonu. Gider kalemleri: Birim fiyat (₺/sn, ₺/kg) hücresi — tooltip "Senaryo geneli oran". Üretim bilgileri / Kurlar / Finansman: mevcut kutular taslağa bağlanır.
**B4. Sayfadan ayrılma uyarısı** (kaydedilmemiş değişiklik). `HesapGoruntule`: override rozetleri yeni alanları gösterir (küçük).

### 3.3 Doğrulama
- Backend: `override.satirlar` ile hesap = aynı değerler reçeteye yazılıp hesaplanan sonuçla birebir (1e-9); `gider_oranlari` override = havuz tutarı güncellenmiş hesapla birebir; kaydet ucu atomiklik testi (parametre hatası → reçete sürümü/ürün kartı yazılmaz); 209 mevcut test + parite değişmeden.
- Frontend: MSW ile hücre → hesapla gövdesi; diyalog listesi/etki uyarısı; e2e: kur değiştir → Kaydet → Parametreler sayfasında geçmişte görünsün; reçete elle fiyat → Kaydet → yeni sürüm.

## 4. Görev bölümü (subagent-driven, her görev TDD + inceleme)
| # | Görev | Kapsam |
|---|---|---|
| T1 | Override genişletme (satirlar, urun, gider_oranlari) | `semalar.py`, `hesap_servisi.py`, testler |
| T2 | `POST /urunler/{kod}/kaydet` atomik uç | `urunler.py`, `hesap_servisi.kaydet_toplu`, testler |
| T3 | Tipler yenileme + tek taslak modeli + üst şerit | `sema.d.ts`, `yardimci.ts`, `UrunMaliyeti.tsx` |
| T4 | Kaydet diyaloğu + kapsam uyarısı | `urun/KaydetDiyalogu.tsx` |
| T5 | Hücreler (reçete, gider, üretim, kurlar, finansman) + ayrılma uyarısı + reçete ağaç girintisi (Excel A sütunu seviye) + e2e | `urun/*.tsx`, `e2e/` |
| T6 | Final inceleme + kapanış raporu | — |

## 5. Kararlar / riskler (yanlışsa düzeltin)
1. Kur/enflasyon ürün ekranından **senaryo geneli** yazılır (Excel'deki gibi tek kaynak), diyalogda uyarıyla; ürün-özel seçeneği var.
2. Gider oranı düzenlenince havuz **toplam tutarı** değişir, baz (sn/kg/adet) sabit kalır.
3. Reçete satırı ekleme/silme bu fazda yok (mevcut Reçete Aktar ve POST recete ile); yalnız hücre düzenleme.
4. Mevcut tekil uçlar ve diğer sayfaların düzenleme akışları değişmez.
5. Eski "Ne olur" paneli kalkar; "kaydetmeden dene" ihtiyacı Vazgeç ile karşılanır.
