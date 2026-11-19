# Fiyat Çalışması ve Maliyet Muhasebesi

Zeytursan'ın Excel'de yürüttüğü **fiyat çalışmasını** (ürün maliyeti, satış ve liste fiyatı, teklifler, analizler) ve aylık **maliyet muhasebesini (SMM)** web uygulamasına taşıyan şirket içi uygulama.

Tek bir Windows bilgisayarda çalışır. Kullanıcılar tarayıcıdan bağlanır; ayrı bir veritabanı sunucusu gerekmez (veritabanı tek bir SQLite dosyasıdır).

> **Şirket içi, gizli depo.** Gerçek şirket verisi (veritabanı, Excel kitapları, gerçek veriden ekran görüntüleri) bu depoya girmez; bkz. [Veri güvenliği](#veri-güvenliği).

## Neler yapar

**Fiyat Çalışması**
- Ürün maliyeti: reçete, fire, gider dağıtımı, finansman, birim maliyet; Excel'deki ürün sayfasıyla aynı sonuç (parite testleriyle korunur)
- Satış fiyatı, Berrak liste fiyatı (yurtiçi / yurtdışı bölen, yuvarlama), teklif turları ve Teklif Kapak
- Analizler: Ya olursa, Zam etkisi, Kur riski, Kârlılık haritası, Marjı koruyan fiyat, Fiyat eğilimi, Önemli malzemeler (80/20)
- Yönetim Özeti (tek sayfa), Bütçe ve Gerçekleşen kıyası, stokta kalan ile ortalama maliyet
- Excel'den toplu yükleme ve önizleme, Excel/PDF rapor, Değişiklik Günlüğü ve geri alma, çalışma kilidi

**Maliyet Muhasebesi (SMM)**
- Aylık dönem: alım, iade, üretim, sayım, şahit numune, gider ve stok mizanı yükleme
- Stok ve envanter, üretim maliyeti (20 → 40 → 50 aşamaları), sarf farkı, SMM özeti ve muhasebe fişi, dönem kapanışı ve devir

**Kullanıcılar ve roller:** Genel Direktör, Muhasebe, Satın alma (yalnız malzeme ve fiyat), İzleyici (yalnız okur). Her değişiklik bir "Neden" ister ve günlüğe yazılır.

## Kurulum

### A. Tek bilgisayar (pilot): hazır paket

İnternet ve yönetici yetkisi gerekmez; Node.js gerekmez.

1. Bu deponun **[Releases](../../releases)** bölümünden son `…-FiyatCalismasi-Pilot.zip` dosyasını indirin.
2. Zip'i yolunda **Türkçe karakter olmayan** bir klasöre açın, örn. `C:\FiyatCalismasi`.
3. `11-18-2026-1-kur.bat` dosyasına çift tıklayın. Python 3.12 yoksa kendisi kurar, bağımlılıkları paketten yükler, ilk Genel Direktör hesabını açar (geçici şifre ekranda) ve masaüstüne kısayol koyar.
4. Ayrıntılar paketteki `11-18-2026-OKU-BENI.pdf` dosyasında.

| Dosya | Ne yapar |
|---|---|
| `11-18-2026-1-kur.bat` | İlk kurulum (tekrar çalıştırmak zararsızdır) |
| `11-18-2026-2-uygulamayi-ac.bat` | Uygulamayı açar (masaüstü kısayolu da bunu çalıştırır) |
| `11-18-2026-3-yedek-al.bat` | Veritabanının tarihli yedeğini `veri\yedek` altına alır |
| `11-18-2026-4-durdur.bat` | Uygulamayı kapatır |

Paket yeniden üretmek için (geliştirme bilgisayarında):

```powershell
cd frontend; npx vite build; cd ..
.venv\Scripts\python scripts\11-18-2026-pilot-paketi-hazirla.py --zip
```

### B. Ağdaki sunucu (çok kullanıcılı)

BT sorumlusu için ayrıntılı rehber: [docs/11-12-2026-kurulum-ve-isletim-rehberi.md](docs/11-12-2026-kurulum-ve-isletim-rehberi.md). Kurulum, başlatma, otomatik başlatma, yedekleme, geri yükleme ve güncelleme betikleri `kurulum\` klasöründedir.

```powershell
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-kur.ps1
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1
```

Gereksinimler: Windows 10/11 ya da Server 2016+, Python 3.11+ (geliştirme 3.12), arayüzü derlemek için Node.js 22.12+ (ya da 20.19+). Ayarlar `kurulum\ayarlar.env` dosyasındadır (şablon: `kurulum\ayarlar.ornek.env`); sunucuda `GIRIS_ZORUNLU=1` kalmalıdır.

> Excel yükleme şablonları (`sablonlar\11-16-2026-NN-*.xlsx`) git dışındadır ama uygulamanın "Şablonu indir" düğmeleri bunları kullanır. Depodan kurulumda `sablonlar\uret.py` ile üretin ya da hazır paketten kopyalayın.

## Geliştirme

```powershell
# Backend (FastAPI + SQLAlchemy), http://127.0.0.1:8000
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e .[test]
.venv\Scripts\python -m uvicorn backend.uygulama:app --reload --port 8000

# Arayüz (React + Vite + TypeScript)
cd frontend
npm ci
npm run dev        # geliştirme sunucusu
npx vite build     # frontend\dist (backend bu klasörü aynı adresten sunar)
```

API değiştiğinde arayüzün tip dosyasını (`frontend/src/api/sema.d.ts`) yeniden üretin:

```bash
GIRIS_ZORUNLU=0 ONBELLEK_ISITMA=0 .venv/Scripts/python -c "import json; from backend.uygulama import app; open('frontend/node_modules/.openapi-gecici.json','w',encoding='utf-8').write(json.dumps(app.openapi(), ensure_ascii=False))" \
  && cd frontend && npx openapi-typescript node_modules/.openapi-gecici.json -o src/api/sema.d.ts
```

### Testler

```powershell
.venv\Scripts\python -m pytest tests          # backend ve hesap motoru (~730 test, ~20 dk)
cd frontend; npx tsc -b --noEmit; npm run lint; npx vitest run   # arayüz (~670 test)
```

Uçtan uca deneme için uydurma verili sezon senaryosu: [docs/test-dongusu/11-16-2026-sezon-senaryosu.md](docs/test-dongusu/11-16-2026-sezon-senaryosu.md). Test verisi `test-dongusu\uret.py` ile üretilir. Senaryonun API kuru koşusu 206 kontrolü doğrular (`test-dongusu\kuru_kosu_sezon.py`). Son ekran denemesinin sonuçları: [docs/test-dongusu/11-18-2026-sezon-deneme-sonuclari.md](docs/test-dongusu/11-18-2026-sezon-deneme-sonuclari.md).

### Kurallar

- Para tutarları hiçbir zaman `float` ile tutulmaz; `Decimal` kullanılır. Gösterim `1.234.567,89 TL`, tarih `GG.AA.YYYY`.
- Hesap mantığında yapılan her değişiklikte Excel ile sonuç eşliği (parite) korunur.
- Emin olunmayan muhasebe ya da vergi kuralı tahmin edilmez; "doğrulanmalı" diye işaretlenir.
- Yeni dosya adları `MM-DD-YYYY-aciklayici-ad` biçimindedir.

## Klasör yapısı

| Klasör | İçerik |
|---|---|
| `fiyat_motoru/` | Hesap motoru (Excel formüllerinin karşılığı) |
| `backend/` | FastAPI uygulaması: `api/` (uçlar), `servisler/` (iş kuralları), `depo/` (model, veritabanı, yedek) |
| `frontend/` | React arayüzü; derlenmiş hâli `frontend/dist` |
| `kurulum/` | PowerShell kurulum, başlatma, yedek ve güncelleme betikleri; `pilot/` çift tıklanan dosyalar |
| `sablonlar/` | Excel yükleme şablonları ve rehberi |
| `scripts/` | Yardımcı betikler (ilk Genel Direktör hesabı, pilot paketi, parite raporu) |
| `tests/` | pytest testleri |
| `test-dongusu/` | Uydurma test verisi, uçtan uca kuru koşu ve deneme betikleri |
| `docs/` | Planlar, kapanış raporları, kurulum rehberi, test senaryoları |

## Veri güvenliği

Aşağıdakiler `.gitignore` ile depo dışında tutulur ve **asla commit'lenmez**:

- `veri/`: canlı veritabanı (`fiyat.db`), yedekler ve günlükler
- Bütün `.db`, `.xlsx`, `.xls` dosyaları (şirket Excel kitapları, şablonlar)
- `docs/ozel/`, `docs/aktarim/`, `docs/briefler/`: gerçek veriden ekran görüntüleri ve raporlar
- `kurulum/ayarlar.env`: bilgisayara özel ayarlar

Gerçek veriyle çalışan bir kurulum taşınacaksa `veri\fiyat.db` uygulama kapalıyken elle kopyalanır; depo ya da paket üzerinden taşınmaz.
