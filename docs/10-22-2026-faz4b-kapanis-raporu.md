# Faz 4b Kapanış Raporu — Ürün Ekranı Excel Düzeni

Tarih: 22.10.2026
Plan: `docs/10-22-2026-faz4b-excel-duzeni-ve-son-duzeltmeler-plani.md`
Tetikleyen: kullanıcının "Excel'de olan ama arayüzde olmayan bilgiler var" itirazı (16 maddelik eksik listesi).

## Sonuç
- Backend: 209 test (`-W error`); 4 yeni uç (`/metin-parametreler`, `/uretim-kapasitesi` GET/PUT, `/ambalaj-ozeti`); hesap yanıtına üretim bilgileri, parametre özeti (kurlar/enflasyon/maliyet sapma), para birimi bazlı finansman, GBP/ZAR maliyet ve satış, teklif kâr oranları, satır birim/Z-S/düğüm tipi, notlar; Üretim Adetleri okuyucu (71 satır); açılışta parametre tanımı tohumu.
- Frontend: 22 dosya / 188 test, tsc 0, build ok; Playwright e2e 19/19 (Faz 4b sonrası, gerçek Excel, diğer oturum tarafından koşuldu).
- Ürün Maliyeti ekranı Excel sayfası sırasında: başlık → reçete (Satır, Kod, Cinsi, Miktar, Fire %, Brüt, Birim, Birim fiyat, Z/S, Döviz, Tutar firesiz/fireli, Maliyet %, Satış %; ara mamul rozeti ve girinti) → gider kalemleri (miktar/fire/brüt/birim/birim fiyat/döviz/tutar/%; üç grup + ara toplamlar + dağıtım notu) → toplamlar | finansman tablosu (para birimi × faiz / stok süresi / dönem faizi / faiz tutarı TL; finansman dahil maliyet per para birimi + kur) → üretim bilgileri (süzme kg, vardiya adedi/saati, personel, hat, sınıf, ambalaj, pazar, mal kabul; "ne olur" + kalıcı kaydet özetle) | kurlar ve enflasyon → ne olur paneli → teklif turları → yüzde grafiği.
- Yeni sayfa: Üretim Adetleri (satır içi düzenleme, neden zorunlu). Dashboard: Ambalaj özeti kartı.
- Ekranda ham parametre anahtarı (`faiz.TL`, `stok_ay.ZAR`) kalmadı; okunur etiketler ve yüzde gösterimi.

## Kontrolörün kararları (yanlışsa düzeltin)
1. E görevleri (Faz 4 final inceleme düzeltmeleri) bu plandan düşürüldü: paralel oturum (ztsserkang-nel-b7) tamamladı.
2. Yeni yanıt alanları opsiyonel/nullable (eski snapshot → null); eski istemciler kırılmaz.
3. Ambalaj özeti üretim adedi = vardiya adedi toplamı (Excel'in sezon adedi sütunu import'ta yok); etikette belirtilecek.
4. Finansman faiz tutarları TL cinsinden gösterilir (motor: giydirilmiş TL × faiz/12 × ay — `fiyat_motoru/finansman.py`); USD/EUR/GBP/ZAR satırlarında "Faiz tutarı (TL)".
5. Hat/sınıf/ambalaj/pazar/süzme kg için "ne olur" yok (backend override şeması kabul etmiyor); yalnız kalıcı kayıt. Vardiya saati "ne olur" parametre override'ıyla.
6. `PUT /urunler/{kod}` ve üretim hedefi kaydında API'de `neden` yok → özet diyaloğu; Üretim Adetleri'nde neden zorunlu.
7. "Üretim Adetleri" sayfasındaki "-" ve "#DIV/0!" hücreleri 0 okunur; tekrar eden ürün kodunda ilk satır alınır, uyarı listelenir.
8. `satis_fiyati_notu` tohumlanmadı (kurumsal metin kodda tutulmaz); `/metin-parametreler` ile girilir.
9. Kullanıcı bilgisi (22.10): Excel'deki sağ blok (Z-AO) deneme/önemsiz → firesiz tanımı sağ bloğa dayanmaz; sağ-blok parite testinin silinmesi **kullanıcı onayı bekliyor**.

## Ertelenenler (bir sonraki dalga için)
- "Hücreye yaz, tek Kaydet" modeli (kullanıcı önerisi bekliyor): tüm düzenlenebilir hücreler anında hesaplasın, tek Kaydet hepsini geçmişe yazsın; gider ₺/sn oranları ürün ekranından düzenlenebilsin.
- `HesapGoruntule` (kayıtlı hesap salt okunur görünümü) yeni blokları göstermiyor (diğer oturumun dosyası).
- Üretim bilgileri kalıcı kayıtta iki ardışık PUT; ikincisi hata verirse taslak sıfırlanmış olur.
- Ambalaj servisi ürün başına sorgu (70 üründe sorun değil); kapasite okuyucu başlık doğrulaması var, sütun konumu sabit.
- Dashboard ilk açılış ~7 sn (67 ürün canlı hesap) → önbellek/ön hesaplama Faz 5'in ilk işi.

## Çalıştırma
Backend'i bir kez yeniden başlatın (yeni parametre tanımları açılışta tohumlanır):
```
.\.venv\Scripts\python -m uvicorn backend.uygulama:app --reload
```
Frontend: `cd frontend && npm run dev` → http://localhost:5180

## Dosyalar
Backend: `backend/api/{semalar,urunler,kapasite,parametreler}.py`, `backend/servisler/{hesap,import,kapasite,ambalaj,parametre}_servisi.py`, `backend/depo/{modeller,veritabani}.py`, `backend/tohum.py`, `fiyat_motoru/excel_okuyucu.py` (+`uretim_adetlerini_oku`), testler `tests/backend/test_faz4b_*.py`, `tests/test_excel_uretim_adetleri.py`.
Frontend: `src/sayfalar/urun/{UretimBilgileri,KurlarBlogu,FinansmanTablosu,GiderKalemleri,ReceteTablosu,ToplamlarKarti,NeOlurPaneli,parametreEtiketleri,kaliciKayit}.*`, `src/sayfalar/{UrunMaliyeti,UretimAdetleri}.tsx` (+testler), `src/sayfalar/dashboard/AmbalajOzeti.tsx`, `src/api/sorgular/{kapasite,ambalaj,anahtarlar}.ts`, `src/api/{sema.d.ts,tipler.ts}`, `src/test/msw/isleyiciler-urun-excel.ts`, `src/test/fikstur/urunExcel.ts`, `src/yonlendirme.tsx`, `src/bilesenler/Kabuk.tsx`.
