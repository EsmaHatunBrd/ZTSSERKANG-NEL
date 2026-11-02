# Faz 1: Hesap Motoru ve Excel Doğrulama - Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fiyat Çalışma Excel'indeki ürün maliyet hesabını (F1-F13) saf Python fonksiyonları olarak yazmak ve 69 ürün sayfasının tamamında Excel ile birebir aynı sonucu verdiğini testle kanıtlamak.

**Architecture:** Motor, veritabanı ve arayüzden bağımsız bir Python paketi (`fiyat_motoru`). Girdiler dataclass'larla verilir, çıktı tek bir `MaliyetSonucu` nesnesidir. Excel okuyucu modülü mevcut Excel'den hem girdileri hem beklenen sonuçları çeker; "altın referans" testleri bu ikisini karşılaştırır. Para değerleri `Decimal` ile tutulur.

**Tech Stack:** Python 3.11+, `openpyxl` (Excel okuma), `pytest`. Veritabanı ve web çerçevesi bu fazda **yok**.

**Spec:** `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` (bölüm 2 hesap kuralları, bölüm 3 bilinen Excel sorunları, bölüm 6 doğrulama stratejisi)

## Global Constraints

- Para tutarları `Decimal`; `float` yalnızca Excel'den okunan ham değerin `Decimal(str(x))` dönüşümünde geçer.
- Excel paritesi toleransı: mutlak fark `< 1e-6` TL (Excel float hesabından kaynaklanan sapma payı).
- Fiyatı bulunmayan malzeme Excel'deki gibi **0** hesaplanır ama `MaliyetSonucu.uyarilar` listesine yazılır (spec bölüm 3, madde 1). Faz 1'de hata fırlatılmaz; parite bozulmasın.
- Faz 1'de yalnızca **sol blok** (P sütunu) referans alınır. Sağ blok (Z-AO) kapsam dışı.
- Gider havuzu toplamları (örn. `49024334.97*1.35*1.3`) bu fazda hesaplanmış değer olarak girilir; çarpanların parametreleştirilmesi Faz 3.
- Kurumsal veri: Excel'den üretilen test fikstürleri yalnızca yerel diskte kalır, paylaşılan bir depoya konmaz (`.gitignore`).
- Dosya adlandırma (kurum kuralı): yeni **belge** dosyaları `MM-DD-YYYY-açıklama` biçiminde. Python modül ve test dosyaları Python'un import kuralı gereği bu biçime uymaz (`fiyat_motoru/fire.py` gibi).
- Git: klasörde depo yok. Kullanıcı onay verirse Task 1'de `git init` yapılır; vermezse commit adımları atlanır.
- Kod tanımlayıcıları Türkçe, Türkçe karakter kullanılmadan (`brut_miktar`, `fire_orani`).

---

## Dosya Yapısı

```
ZTSSERKANGÜNEL/
├── pyproject.toml                  # paket + pytest ayarı
├── .gitignore                      # fixtures/, .venv/, __pycache__
├── fiyat_motoru/
│   ├── __init__.py
│   ├── para.py                     # D() yardımcıları, sabitler (SIFIR, BIR)
│   ├── modeller.py                 # tüm girdi/çıktı dataclass'ları
│   ├── fire.py                     # F1 brut_miktar
│   ├── malzeme.py                  # F2 malzeme_tutari, F3 malzeme_toplami
│   ├── gider_dagitim.py            # F4, F8: havuzlar -> birim gider oranları
│   ├── uretim_gideri.py            # F5, F6, F7 + pazarlama/yönetim payı
│   ├── finansman.py                # F9, F10
│   ├── fiyat.py                    # F11, F12, F13
│   ├── hesapla.py                  # orkestrasyon: UrunGirdisi -> MaliyetSonucu
│   └── excel_okuyucu.py            # Fiyat Çalışma xlsx -> girdiler + beklenen değerler
├── scripts/
│   └── excel_parite_raporu.py      # 69 sayfa için fark raporu üretir
└── tests/
    ├── conftest.py
    ├── test_fire.py
    ├── test_malzeme.py
    ├── test_gider_dagitim.py
    ├── test_uretim_gideri.py
    ├── test_finansman.py
    ├── test_fiyat.py
    ├── test_hesapla.py
    ├── test_excel_okuyucu.py
    └── test_excel_paritesi.py      # altın referans: tüm sayfalar
```

Excel'in yolu testlerde `EXCEL_YOLU` ortam değişkeninden okunur; verilmezse `Fiyat Çalışma - 2026-2027 - Berrak.xlsx` (proje kökü) kullanılır. Dosya yoksa Excel testleri `skip` edilir.

---

### Task 1: Proje iskeleti ve `para.py`

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `fiyat_motoru/__init__.py`, `fiyat_motoru/para.py`, `tests/conftest.py`, `tests/test_para.py`

**Interfaces:**
- Produces: `para.D(x) -> Decimal` (int/float/str/Decimal/None kabul eder, None → Decimal(0)); `para.SIFIR`, `para.BIR`; `para.yakin(a, b, tol=Decimal("0.000001")) -> bool`.

- [ ] **Step 1: pyproject.toml ve .gitignore yaz**

```toml
# pyproject.toml
[project]
name = "fiyat-motoru"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["openpyxl>=3.1"]

[project.optional-dependencies]
test = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["fiyat_motoru*"]
```

```gitignore
.venv/
__pycache__/
*.pyc
fixtures/
*.xlsx
docs/parite-raporu-*.md
```

- [ ] **Step 2: Sanal ortam kur ve bağımlılıkları yükle**

Run (PowerShell, proje kökünde):
```
python -m venv .venv; .\.venv\Scripts\python -m pip install -e ".[test]"
```
Expected: `Successfully installed fiyat-motoru-0.1.0 openpyxl pytest ...`

- [ ] **Step 3: Başarısız testi yaz**

```python
# tests/test_para.py
from decimal import Decimal
from fiyat_motoru.para import D, SIFIR, BIR, yakin


def test_D_float_metin_uzerinden_cevirir():
    assert D(0.1) == Decimal("0.1")          # Decimal(0.1) olsaydı 0.1000000000000000055... olurdu


def test_D_none_sifir():
    assert D(None) == SIFIR


def test_D_decimal_aynen():
    assert D(Decimal("2.5")) == Decimal("2.5")


def test_yakin_tolerans():
    assert yakin(Decimal("1.0000001"), Decimal("1.0000002"))
    assert not yakin(Decimal("1.0"), Decimal("1.001"))
    assert BIR == Decimal(1)
```

- [ ] **Step 4: Testi çalıştır, başarısız olduğunu gör**

Run: `.\.venv\Scripts\python -m pytest tests/test_para.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'fiyat_motoru.para'`

- [ ] **Step 5: Uygulamayı yaz**

```python
# fiyat_motoru/__init__.py
"""Fiyat çalışması hesap motoru. Veritabanı ve arayüzden bağımsız saf fonksiyonlar."""
```

```python
# fiyat_motoru/para.py
"""Para ve oran değerleri için Decimal yardımcıları."""
from decimal import Decimal

SIFIR = Decimal(0)
BIR = Decimal(1)
TOLERANS = Decimal("0.000001")


def D(x) -> Decimal:
    """Her türlü sayıyı Decimal'e çevirir. float, str üzerinden geçer ki 0.1 -> 0.1 kalsın."""
    if x is None or x == "":
        return SIFIR
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise TypeError("bool para değeri olamaz")
    return Decimal(str(x))


def yakin(a: Decimal, b: Decimal, tol: Decimal = TOLERANS) -> bool:
    return abs(D(a) - D(b)) < tol
```

```python
# tests/conftest.py
import os
from pathlib import Path
import pytest

PROJE_KOKU = Path(__file__).resolve().parent.parent
VARSAYILAN_EXCEL = PROJE_KOKU / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"


@pytest.fixture(scope="session")
def excel_yolu() -> Path:
    yol = Path(os.environ.get("EXCEL_YOLU", VARSAYILAN_EXCEL))
    if not yol.exists():
        pytest.skip(f"Excel bulunamadı: {yol}")
    return yol
```

- [ ] **Step 6: Testi çalıştır, geçtiğini gör**

Run: `.\.venv\Scripts\python -m pytest tests/test_para.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit (git varsa)**

```bash
git init   # yalnızca kullanıcı onayladıysa, bir kez
git add pyproject.toml .gitignore fiyat_motoru/ tests/
git commit -m "feat: fiyat motoru iskeleti ve Decimal yardımcıları"
```

---

### Task 2: Veri modelleri (`modeller.py`)

**Files:**
- Create: `fiyat_motoru/modeller.py`, `tests/test_modeller.py`

**Interfaces:**
- Produces (sonraki tüm görevler bunları kullanır):

```python
@dataclass(frozen=True)
class Malzeme:
    kod: str
    ad: str
    tip: str | None            # '0008-Ambalaj Malzeme' gibi
    birim: str | None          # 'AD', 'KG'
    para_birimi: str | None    # 'TL', 'USD', 'EUR', 'GBP', 'CHF', None
    fiyat: Decimal             # bütçe birim fiyatı, yoksa SIFIR
    zs: str | None             # 'Z' veya 'S' (Excel N sütunu), bilinmiyorsa None

@dataclass(frozen=True)
class ReceteSatiri:
    malzeme_kodu: str
    ad: str
    miktar: Decimal            # net miktar (I sütunu)
    fire_orani: Decimal        # 0.02 gibi; yoksa SIFIR (J sütunu)
    birim: str | None

@dataclass(frozen=True)
class Parametreler:
    enflasyon: Decimal                       # F148, 0.25
    kurlar: dict[str, Decimal]               # {'USD': 50, 'EUR': 60, 'GBP': 68, 'CHF': 63.29..}
    faiz_oranlari: dict[str, Decimal]        # {'TL': 0.40, 'USD': 0.06, 'EUR': 0.06}
    stok_sureleri_ay: dict[str, Decimal]     # {'TL': 6, 'USD': 6, 'EUR': 6}
    satis_kar_orani: Decimal                 # P137'deki 1.2 -> 0.20
    teklif_kar_oranlari: tuple[Decimal, ...] # (0.20, 0.17, 0.14)
    vardiya_saati: Decimal                   # 7.5 (Excel 27000 sn sabitini kullanır = 7.5*3600)

@dataclass(frozen=True)
class UretimBilgisi:
    pazar: str                       # 'Yurtiçi' | 'Yurtdışı' (P2)
    vardiya_uretim_adedi: Decimal    # E138
    dolum_personel: Decimal          # E140
    etiketleme_adedi: Decimal        # E141 (0 ise etiket işçiliği 0)
    etiket_personel: Decimal         # E143
    hat: str                         # E144 'Niko', 'Herbort', ...
    taze_tursu_sinifi: str           # E145 'Taze/Taze', 'Taze/Turşu', 'Turşu/Turşu'
    ambalaj_hacmi: Decimal           # E146 370, 720, 2.5 ...
    suzme_kg: Decimal                # E136
    mal_kabul_miktar_kg: Decimal     # I104 (Excel'de =K17 gibi bir satıra bağlı; burada girdi)
    mal_kabul_fire: Decimal          # J104, genelde SIFIR
    pazarlama_yonetim_uygula: bool   # 14 sayfada P118/P119 elle 0 -> False

@dataclass(frozen=True)
class AmbalajSinifi:
    ad: str
    hacim: Decimal
    uretim_adedi: Decimal
    katsayi: Decimal

@dataclass(frozen=True)
class GiderHavuzlari:
    """Gider Dağıtım sayfasının ham girdileri (toplamlar hesaplanmış TL değer olarak)."""
    dolum_iscilik_toplam: Decimal;   dolum_iscilik_saniye: Decimal          # D4, F4
    mal_kabul_iscilik_toplam: Decimal                                        # A6
    mal_kabul_paylari: dict[str, tuple[Decimal, Decimal]]                   # sınıf -> (pay, kg)  C7:G9 / E7:E9
    etiket_iscilik_toplam: Decimal;  etiket_iscilik_saniye: Decimal         # D13, F13
    endirekt_iscilik_toplam: Decimal; endirekt_saniye: Decimal              # D18, F18
    mal_kabul_gug_toplam: Decimal                                            # A20
    mal_kabul_gug_paylari: dict[str, tuple[Decimal, Decimal]]               # C21:G23
    diger_gug_toplam: Decimal;       diger_gug_saniye: Decimal              # D27, F27
    elektrik_toplam: Decimal;   elektrik_hatlar: dict[str, tuple[Decimal, Decimal]]    # D38; hat -> (pay, saniye) A30:G37
    dogalgaz_toplam: Decimal;   dogalgaz_hatlar: dict[str, tuple[Decimal, Decimal]]    # D49; A41:G48
    amortisman_toplam: Decimal; amortisman_hatlar: dict[str, tuple[Decimal, Decimal]]  # D60; A52:G59
    yonetim_toplam: Decimal                                                  # D64
    pazarlama_toplam: Decimal                                                # D67
    ambalajlar: tuple[AmbalajSinifi, ...]                                    # A70:D91

@dataclass(frozen=True)
class GiderOranlari:
    """Havuzlardan türetilmiş birim oranlar (Gider Dağıtım'ın G/F sütunları)."""
    dolum_iscilik_sn: Decimal                      # G4
    etiket_iscilik_sn: Decimal                     # G13
    endirekt_iscilik_sn: Decimal                   # G18
    diger_gug_sn: Decimal                          # G27
    mal_kabul_iscilik_kg: dict[str, Decimal]       # F7:F9   (anahtar casefold)
    mal_kabul_gug_kg: dict[str, Decimal]           # F21:F23
    elektrik_sn: dict[str, Decimal]                # F30:F37 (anahtar casefold)
    dogalgaz_sn: dict[str, Decimal]                # F41:F48
    amortisman_sn: dict[str, Decimal]              # F52:F59
    pazarlama_adet: dict[Decimal, Decimal]         # hacim -> F70:F91
    yonetim_adet: dict[Decimal, Decimal]           # hacim -> G70:G91

@dataclass(frozen=True)
class UrunGirdisi:
    kod: str
    ad: str
    recete: tuple[ReceteSatiri, ...]
    uretim: UretimBilgisi

@dataclass
class MaliyetSatiri:
    kalem: str                 # 'Cam Kavanoz 370 ml Boğumlu' veya 'Dolum Doğrudan İşçilik'
    grup: str                  # 'malzeme' | 'direkt_iscilik' | 'gug' | 'diger' | 'finansman'
    miktar: Decimal
    brut_miktar: Decimal
    birim_fiyat: Decimal
    tutar: Decimal
    maliyet_yuzdesi: Decimal = SIFIR     # R sütunu
    fiyat_yuzdesi: Decimal = SIFIR       # S sütunu

@dataclass
class MaliyetSonucu:
    urun_kodu: str
    satirlar: list[MaliyetSatiri]
    malzeme_toplami: Decimal            # P100
    direkt_iscilik_toplami: Decimal     # P103
    gug_toplami: Decimal                # P107
    uretim_gideri_toplami: Decimal      # P114
    toplam_birim_maliyet: Decimal       # P116
    pazarlama_gideri: Decimal           # P118
    yonetim_gideri: Decimal             # P119
    diger_giderler_toplami: Decimal     # P120
    giydirilmis_maliyet: Decimal        # P122
    finansman: dict[str, Decimal]       # {'TL': P124, 'USD': P125, 'EUR': P126, ...}
    finansman_dahil_maliyet_tl: Decimal # P130
    doviz_maliyet: dict[str, Decimal]   # {'USD': P131, 'EUR': P132, 'GBP': P133}
    satis_fiyati_tl: Decimal            # P137
    satis_fiyati_doviz: dict[str, Decimal]  # {'USD': P138, 'EUR': P139, ...}
    suzme_kg_fiyati_tl: Decimal         # P143
    teklifler_usd: list[Decimal]        # [P145, P146, P147]
    uyarilar: list[str]
```

- [ ] **Step 1: Başarısız testi yaz**

```python
# tests/test_modeller.py
from decimal import Decimal
from fiyat_motoru.modeller import Malzeme, ReceteSatiri, Parametreler, MaliyetSatiri
from fiyat_motoru.para import SIFIR


def test_malzeme_dondurulmus():
    m = Malzeme(kod="20.10.051.000.0000", ad="Cam Kavanoz 370 ml", tip="0008-Ambalaj Malzeme",
                birim="AD", para_birimi="TL", fiyat=Decimal("5.9"), zs="S")
    try:
        m.fiyat = Decimal(1)
        assert False, "frozen olmalı"
    except AttributeError:
        pass


def test_recete_satiri_varsayilan_fire_yok():
    s = ReceteSatiri(malzeme_kodu="x", ad="y", miktar=Decimal(1), fire_orani=SIFIR, birim="AD")
    assert s.fire_orani == SIFIR


def test_maliyet_satiri_yuzde_varsayilan_sifir():
    s = MaliyetSatiri(kalem="a", grup="malzeme", miktar=Decimal(1), brut_miktar=Decimal(1),
                      birim_fiyat=Decimal(2), tutar=Decimal(2))
    assert s.maliyet_yuzdesi == SIFIR and s.fiyat_yuzdesi == SIFIR


def test_parametreler_teklif_tuple():
    p = Parametreler(enflasyon=Decimal("0.25"), kurlar={"USD": Decimal(50)},
                     faiz_oranlari={"TL": Decimal("0.4")}, stok_sureleri_ay={"TL": Decimal(6)},
                     satis_kar_orani=Decimal("0.2"),
                     teklif_kar_oranlari=(Decimal("0.2"), Decimal("0.17"), Decimal("0.14")),
                     vardiya_saati=Decimal("7.5"))
    assert len(p.teklif_kar_oranlari) == 3
```

- [ ] **Step 2: Çalıştır, başarısız**

Run: `.\.venv\Scripts\python -m pytest tests/test_modeller.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: `modeller.py` yaz** (Interfaces bölümündeki sınıfları aynen, `from dataclasses import dataclass, field`, `from decimal import Decimal`, `from .para import SIFIR` ile; `MaliyetSonucu.uyarilar` için `field(default_factory=list)`)

- [ ] **Step 4: Çalıştır, geçer**

Run: `.\.venv\Scripts\python -m pytest tests/test_modeller.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add fiyat_motoru/modeller.py tests/test_modeller.py
git commit -m "feat: hesap motoru veri modelleri"
```

---

### Task 3: F1 Fire → brüt miktar (`fire.py`)

**Files:**
- Create: `fiyat_motoru/fire.py`, `tests/test_fire.py`

**Interfaces:**
- Produces: `brut_miktar(miktar: Decimal, fire_orani: Decimal) -> Decimal` — Excel K8 `=I8/(1-J8)`.

- [ ] **Step 1: Başarısız test**

```python
# tests/test_fire.py
from decimal import Decimal
import pytest
from fiyat_motoru.fire import brut_miktar
from fiyat_motoru.para import yakin


def test_fire_bolme_ile_eklenir():
    # Excel 001!K8: 0.08333333/(1-0.02) = 0.08503401020408163
    assert yakin(brut_miktar(Decimal("0.08333333"), Decimal("0.02")), Decimal("0.08503401020408163"))


def test_fire_sifir_miktar_aynen():
    assert brut_miktar(Decimal("0.19531875"), Decimal(0)) == Decimal("0.19531875")


def test_fire_yuzde_yuz_hata():
    with pytest.raises(ValueError):
        brut_miktar(Decimal(1), Decimal(1))


def test_fire_negatif_hata():
    with pytest.raises(ValueError):
        brut_miktar(Decimal(1), Decimal("-0.1"))
```

- [ ] **Step 2: Çalıştır, başarısız** — Run: `.\.venv\Scripts\python -m pytest tests/test_fire.py -v` — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/fire.py
"""F1: Fire oranından brüt miktar. Excel: K = I / (1 - J). Fire çarpma ile değil bölme ile eklenir."""
from decimal import Decimal
from .para import BIR, SIFIR


def brut_miktar(miktar: Decimal, fire_orani: Decimal) -> Decimal:
    if fire_orani < SIFIR or fire_orani >= BIR:
        raise ValueError(f"fire oranı [0, 1) aralığında olmalı: {fire_orani}")
    if fire_orani == SIFIR:
        return miktar
    return miktar / (BIR - fire_orani)
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 4 passed

- [ ] **Step 5: Commit** — `git add fiyat_motoru/fire.py tests/test_fire.py && git commit -m "feat: F1 fire -> brüt miktar"`

---

### Task 4: F2, F3 Malzeme tutarı ve toplamı (`malzeme.py`)

**Files:**
- Create: `fiyat_motoru/malzeme.py`, `tests/test_malzeme.py`

**Interfaces:**
- Consumes: `fire.brut_miktar`, `modeller.Malzeme/ReceteSatiri/Parametreler/MaliyetSatiri`
- Produces:
  - `malzeme_tutari(satir: ReceteSatiri, malzeme: Malzeme | None, p: Parametreler) -> tuple[MaliyetSatiri, str | None]` — ikinci eleman uyarı metni veya None
  - `malzeme_toplami(satirlar: list[MaliyetSatiri]) -> Decimal`

Excel kuralı (001!P8):
```
N='S' ise:  USD/EUR/GBP/CHF -> fiyat * kur * brüt ;  TL -> fiyat*(1+enflasyon) * brüt ;  başka -> 0
N!='S' ise: brüt * fiyat
```

- [ ] **Step 1: Başarısız test**

```python
# tests/test_malzeme.py
from decimal import Decimal
from fiyat_motoru.malzeme import malzeme_tutari, malzeme_toplami
from fiyat_motoru.modeller import Malzeme, ReceteSatiri, Parametreler
from fiyat_motoru.para import yakin, SIFIR

P = Parametreler(enflasyon=Decimal("0.25"),
                 kurlar={"USD": Decimal(50), "EUR": Decimal(60), "GBP": Decimal(68), "CHF": Decimal(50) / Decimal("0.79")},
                 faiz_oranlari={"TL": Decimal("0.4")}, stok_sureleri_ay={"TL": Decimal(6)},
                 satis_kar_orani=Decimal("0.2"), teklif_kar_oranlari=(Decimal("0.2"),), vardiya_saati=Decimal("7.5"))


def satir(miktar, fire=SIFIR):
    return ReceteSatiri(malzeme_kodu="k", ad="a", miktar=Decimal(miktar), fire_orani=Decimal(fire), birim="AD")


def malz(fiyat, para, zs):
    return Malzeme(kod="k", ad="a", tip=None, birim="AD", para_birimi=para, fiyat=Decimal(fiyat), zs=zs)


def test_s_tl_enflasyon_uygulanir():
    # 001!P13: kavanoz 5.9 TL, fire 0.02 -> (5.9+5.9*0.25)*1.0204081632653061 = 7.525510204081633
    s, uyari = malzeme_tutari(satir(1, "0.02"), malz("5.9", "TL", "S"), P)
    assert yakin(s.tutar, Decimal("7.525510204081633")) and uyari is None


def test_s_eur_kur_enflasyon_yok():
    # 001!P10: etiket 0.049 EUR * 60 * 1.0204081632653061 = 3.0
    s, _ = malzeme_tutari(satir(1, "0.02"), malz("0.049", "EUR", "S"), P)
    assert yakin(s.tutar, Decimal("3"))


def test_s_usd():
    # 001!P9: shrink 1.95 USD * 50 * (0.00125/0.98) = 0.12436224489795919
    s, _ = malzeme_tutari(satir("0.00125", "0.02"), malz("1.95", "USD", "S"), P)
    assert yakin(s.tutar, Decimal("0.12436224489795919"))


def test_z_fiyat_aynen():
    # 001!P17: taze biberiye 65 TL, Z -> 0.19013459*65 = 12.35874835
    s, _ = malzeme_tutari(satir("0.19013459"), malz("65", "TL", "Z"), P)
    assert yakin(s.tutar, Decimal("12.35874835"))


def test_malzeme_bulunamadi_sifir_ve_uyari():
    s, uyari = malzeme_tutari(satir(1), None, P)
    assert s.tutar == SIFIR and "fiyat" in uyari.lower()


def test_s_bilinmeyen_para_sifir_ve_uyari():
    s, uyari = malzeme_tutari(satir(1), malz("10", "RUB", "S"), P)
    assert s.tutar == SIFIR and uyari is not None


def test_toplam():
    s1, _ = malzeme_tutari(satir(1, "0.02"), malz("5.9", "TL", "S"), P)
    s2, _ = malzeme_tutari(satir(1, "0.02"), malz("0.049", "EUR", "S"), P)
    assert yakin(malzeme_toplami([s1, s2]), Decimal("10.525510204081633"))
```

- [ ] **Step 2: Çalıştır, başarısız** — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/malzeme.py
"""F2/F3: Reçete satırının TL tutarı ve malzeme toplamı. Excel 001!P6:P99 ve P100."""
from decimal import Decimal
from .fire import brut_miktar
from .modeller import Malzeme, MaliyetSatiri, Parametreler, ReceteSatiri
from .para import BIR, SIFIR

DOVIZLER = ("USD", "EUR", "GBP", "CHF")


def malzeme_tutari(satir: ReceteSatiri, malzeme: Malzeme | None, p: Parametreler) -> tuple[MaliyetSatiri, str | None]:
    brut = brut_miktar(satir.miktar, satir.fire_orani)
    uyari = None
    if malzeme is None:
        fiyat, tutar = SIFIR, SIFIR
        uyari = f"{satir.malzeme_kodu} ({satir.ad}): fiyat listesinde yok, 0 TL alındı"
    elif malzeme.zs == "S":
        fiyat = malzeme.fiyat
        pb = malzeme.para_birimi
        if pb in DOVIZLER:
            tutar = fiyat * p.kurlar[pb] * brut
        elif pb == "TL":
            tutar = fiyat * (BIR + p.enflasyon) * brut
        else:
            tutar = SIFIR
            uyari = f"{satir.malzeme_kodu} ({satir.ad}): para birimi tanımsız ({pb}), 0 TL alındı"
    else:
        fiyat = malzeme.fiyat
        tutar = brut * fiyat
    if uyari is None and malzeme is not None and malzeme.fiyat == SIFIR:
        uyari = f"{satir.malzeme_kodu} ({satir.ad}): birim fiyatı 0"
    return MaliyetSatiri(kalem=satir.ad, grup="malzeme", miktar=satir.miktar, brut_miktar=brut,
                         birim_fiyat=fiyat, tutar=tutar), uyari


def malzeme_toplami(satirlar: list[MaliyetSatiri]) -> Decimal:
    return sum((s.tutar for s in satirlar), SIFIR)
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 7 passed

- [ ] **Step 5: Commit** — `git commit -m "feat: F2/F3 malzeme tutarı ve toplamı"`

---

### Task 5: F4, F8 Gider dağıtımı: havuzlar → birim oranlar (`gider_dagitim.py`)

**Files:**
- Create: `fiyat_motoru/gider_dagitim.py`, `tests/test_gider_dagitim.py`

**Interfaces:**
- Consumes: `modeller.GiderHavuzlari`, `AmbalajSinifi`, `GiderOranlari`
- Produces: `oranlari_hesapla(h: GiderHavuzlari) -> GiderOranlari`; `anahtar(s: str) -> str` (casefold + strip; Excel VLOOKUP büyük/küçük harf duyarsız: 'Turşu/turşu' = 'Turşu/Turşu')

Excel kuralları:
- `G4 = D4/F4` (₺/sn), `F7 = (A6*G7)/E7` (₺/kg), `F30 = (D38*G30)/E30` (₺/sn, hat bazlı)
- Ambalaj: `F70 = F92/E92 * E70/C70` ve `E70 = C70*D70` ⇒ `F70 = pazarlama_toplam / Σ(adet_i*katsayı_i) * katsayı_70`

- [ ] **Step 1: Başarısız test**

```python
# tests/test_gider_dagitim.py
from decimal import Decimal
from fiyat_motoru.gider_dagitim import oranlari_hesapla, anahtar
from fiyat_motoru.modeller import GiderHavuzlari, AmbalajSinifi
from fiyat_motoru.para import yakin

D_ = Decimal


def havuz():
    return GiderHavuzlari(
        dolum_iscilik_toplam=D_("86037707.86667047"), dolum_iscilik_saniye=D_(442154500),
        mal_kabul_iscilik_toplam=D_("32065211.4127488"),
        mal_kabul_paylari={"Taze/Taze": (D_("0.25"), D_(6000000)), "Taze/Turşu": (D_("0.65"), D_(7000000)), "Turşu/Turşu": (D_("0.1"), D_(3500000))},
        etiket_iscilik_toplam=D_("18533808.031511273"), etiket_iscilik_saniye=D_(132435000),
        endirekt_iscilik_toplam=D_("42088882.57323751"), endirekt_saniye=D_(32547902),
        mal_kabul_gug_toplam=D_(21000000),
        mal_kabul_gug_paylari={"Taze/Taze": (D_("0.25"), D_(6000000)), "Taze/Turşu": (D_("0.65"), D_(7000000)), "Turşu/Turşu": (D_("0.1"), D_(3500000))},
        diger_gug_toplam=D_("25281257.75"), diger_gug_saniye=D_(32547902),
        elektrik_toplam=D_(14112000), elektrik_hatlar={"Niko": (D_("0.376"), D_(8193712))},
        dogalgaz_toplam=D_(22464000), dogalgaz_hatlar={"Niko": (D_("0.46"), D_(8193712))},
        amortisman_toplam=D_(49056000), amortisman_hatlar={"Niko": (D_("0.43"), D_(8193712))},
        yonetim_toplam=D_("26274982.5"), pazarlama_toplam=D_(16848000),
        ambalajlar=(AmbalajSinifi("370 ml kavanoz", D_(370), D_(5690071), D_("0.5")),
                    AmbalajSinifi("720 ml kavanoz", D_(720), D_(11896020), D_("0.75"))),
    )


def test_saniye_bazli():
    o = oranlari_hesapla(havuz())
    assert yakin(o.dolum_iscilik_sn, D_("0.19458743011022273"))     # G4
    assert yakin(o.etiket_iscilik_sn, D_("0.13994644943943274"))    # G13
    assert yakin(o.endirekt_iscilik_sn, D_("1.2931365767672984"))   # G18
    assert yakin(o.diger_gug_sn, D_("0.7767400107693577"))          # G27


def test_kg_bazli_mal_kabul_anahtar_casefold():
    o = oranlari_hesapla(havuz())
    assert yakin(o.mal_kabul_iscilik_kg[anahtar("Turşu/turşu")], D_("0.9161488975071086"))  # F9
    assert yakin(o.mal_kabul_gug_kg[anahtar("TAZE/TAZE")], D_("0.875"))                    # F21


def test_hat_bazli():
    o = oranlari_hesapla(havuz())
    assert yakin(o.elektrik_sn[anahtar("Niko")], D_("0.6475834151847173"))     # F30
    assert yakin(o.dogalgaz_sn[anahtar("Niko")], D_("1.26114269088296"))       # F41
    assert yakin(o.amortisman_sn[anahtar("Niko")], D_("2.574422923334381"))    # F52


def test_ambalaj_dagitimi():
    # Gerçek Excel'de 22 ambalaj var; iki ambalajla formülün şekli test edilir:
    # paz/adet = 16848000 / (5690071*0.5 + 11896020*0.75) * katsayı
    o = oranlari_hesapla(havuz())
    payda = D_(5690071) * D_("0.5") + D_(11896020) * D_("0.75")
    assert yakin(o.pazarlama_adet[D_(370)], D_(16848000) / payda * D_("0.5"))
    assert yakin(o.yonetim_adet[D_(720)], D_("26274982.5") / payda * D_("0.75"))
```

- [ ] **Step 2: Çalıştır, başarısız** — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/gider_dagitim.py
"""F4/F8: Gider Dağıtım sayfası. Havuz toplamlarını saniye, kg ve adet başına birim gidere çevirir."""
from decimal import Decimal
from .modeller import GiderHavuzlari, GiderOranlari
from .para import SIFIR


def anahtar(s: str) -> str:
    """Excel VLOOKUP büyük/küçük harfe duyarsızdır; 'Turşu/turşu' ile 'Turşu/Turşu' aynı anahtardır."""
    return (s or "").strip().casefold()


def _bol(pay: Decimal, payda: Decimal) -> Decimal:
    return SIFIR if payda == SIFIR else pay / payda


def _paylastir(toplam: Decimal, paylar: dict[str, tuple[Decimal, Decimal]]) -> dict[str, Decimal]:
    # her satır: toplam * pay% / baz(kg veya saniye)
    return {anahtar(k): _bol(toplam * pay, baz) for k, (pay, baz) in paylar.items()}


def oranlari_hesapla(h: GiderHavuzlari) -> GiderOranlari:
    agirlikli_adet = sum((a.uretim_adedi * a.katsayi for a in h.ambalajlar), SIFIR)
    paz_birim = _bol(h.pazarlama_toplam, agirlikli_adet)
    yon_birim = _bol(h.yonetim_toplam, agirlikli_adet)
    return GiderOranlari(
        dolum_iscilik_sn=_bol(h.dolum_iscilik_toplam, h.dolum_iscilik_saniye),
        etiket_iscilik_sn=_bol(h.etiket_iscilik_toplam, h.etiket_iscilik_saniye),
        endirekt_iscilik_sn=_bol(h.endirekt_iscilik_toplam, h.endirekt_saniye),
        diger_gug_sn=_bol(h.diger_gug_toplam, h.diger_gug_saniye),
        mal_kabul_iscilik_kg=_paylastir(h.mal_kabul_iscilik_toplam, h.mal_kabul_paylari),
        mal_kabul_gug_kg=_paylastir(h.mal_kabul_gug_toplam, h.mal_kabul_gug_paylari),
        elektrik_sn=_paylastir(h.elektrik_toplam, h.elektrik_hatlar),
        dogalgaz_sn=_paylastir(h.dogalgaz_toplam, h.dogalgaz_hatlar),
        amortisman_sn=_paylastir(h.amortisman_toplam, h.amortisman_hatlar),
        pazarlama_adet={a.hacim: paz_birim * a.katsayi for a in h.ambalajlar},
        yonetim_adet={a.hacim: yon_birim * a.katsayi for a in h.ambalajlar},
    )
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 4 passed

- [ ] **Step 5: Commit** — `git commit -m "feat: F4/F8 gider dağıtım oranları"`

---

### Task 6: F5, F6, F7 Üretim giderleri ve pazarlama/yönetim payı (`uretim_gideri.py`)

**Files:**
- Create: `fiyat_motoru/uretim_gideri.py`, `tests/test_uretim_gideri.py`

**Interfaces:**
- Consumes: `GiderOranlari`, `UretimBilgisi`, `Parametreler`, `fire.brut_miktar`, `gider_dagitim.anahtar`
- Produces:
  - `direkt_iscilik(u, o, p) -> list[MaliyetSatiri]` (3 satır: mal kabul işçilik P104, dolum P105, etiketleme P106)
  - `genel_uretim(u, o, p) -> list[MaliyetSatiri]` (6 satır: endirekt P108, mal kabul GÜG P109, elektrik P110, doğalgaz P111, amortisman P112, diğer GÜG P113)
  - `diger_giderler(u, o) -> list[MaliyetSatiri]` (2 satır: pazarlama P118, yönetim P119)
  - `adet_basina_saniye(u, p) -> Decimal` = `vardiya_saati*3600 / vardiya_uretim_adedi` (Excel `27000/E138`)

Excel kuralları (001):
```
P104 = K104 * F(mal kabul işçilik, sınıf)   K104 = I104/(1-J104)
P105 = (27000/E138) * E140 * G4
P106 = IFERROR(27000/E141, 0) * E143 * G13       E141 = 0 ise 0
P108 = (27000/E138) * G18
P109 = I104 * F(mal kabul GÜG, sınıf)            fire uygulanmaz (K109 = I109)
P110 = (27000/E138) * F(elektrik, hat);  P111 doğalgaz;  P112 amortisman
P113 = (27000/E138) * G27
P118 = F(pazarlama, hacim);  P119 = G(yönetim, hacim);  uygula=False ise ikisi 0
```
Sınıf veya hat bulunamazsa oran 0 + uyarı (Excel'de elle 0 yazılmış sayfalarla parite için). Uyarılar `MaliyetSatiri` döndürmediği için fonksiyonlar `(satirlar, uyarilar)` çifti döndürür.

- [ ] **Step 1: Başarısız test**

```python
# tests/test_uretim_gideri.py
from decimal import Decimal
from fiyat_motoru.uretim_gideri import direkt_iscilik, genel_uretim, diger_giderler, adet_basina_saniye
from fiyat_motoru.modeller import GiderOranlari, UretimBilgisi, Parametreler
from fiyat_motoru.para import yakin, SIFIR

D_ = Decimal
P = Parametreler(enflasyon=D_("0.25"), kurlar={}, faiz_oranlari={}, stok_sureleri_ay={}, satis_kar_orani=D_("0.2"),
                 teklif_kar_oranlari=(), vardiya_saati=D_("7.5"))
O = GiderOranlari(dolum_iscilik_sn=D_("0.19458743011022273"), etiket_iscilik_sn=D_("0.13994644943943274"),
                  endirekt_iscilik_sn=D_("1.2931365767672984"), diger_gug_sn=D_("0.7767400107693577"),
                  mal_kabul_iscilik_kg={"turşu/turşu": D_("0.9161488975071086")},
                  mal_kabul_gug_kg={"turşu/turşu": D_("0.6")},
                  elektrik_sn={"niko": D_("0.6475834151847173")}, dogalgaz_sn={"niko": D_("1.26114269088296")},
                  amortisman_sn={"niko": D_("2.574422923334381")},
                  pazarlama_adet={D_(370): D_("0.5048087845717276")}, yonetim_adet={D_(370): D_("0.7872650748141269")})
U = UretimBilgisi(pazar="Yurtiçi", vardiya_uretim_adedi=D_(65000), dolum_personel=D_(13), etiketleme_adedi=D_(35000),
                  etiket_personel=D_(7), hat="Niko", taze_tursu_sinifi="Turşu/Turşu", ambalaj_hacmi=D_(370),
                  suzme_kg=D_("0.18"), mal_kabul_miktar_kg=D_("0.19013459"), mal_kabul_fire=SIFIR, pazarlama_yonetim_uygula=True)


def test_adet_basina_saniye():
    assert yakin(adet_basina_saniye(U, P), D_("0.4153846153846154"))  # 27000/65000


def test_direkt_iscilik_001():
    satirlar, uyarilar = direkt_iscilik(U, O, P)
    t = {s.kalem: s.tutar for s in satirlar}
    assert yakin(t["Mal Kabul ve Fermantasyon Giderleri"], D_("0.1741915950064661"))  # P104
    assert yakin(t["Dolum Doğrudan İşçilik Giderleri"], D_("1.0507721225952027"))     # P105
    assert yakin(t["Etiketleme İşçilik Giderleri"], D_("0.7557108269729369"))         # P106
    assert yakin(sum(s.tutar for s in satirlar), D_("1.9806745445746057")) and uyarilar == []


def test_etiketleme_adedi_sifir_ise_sifir():
    u = UretimBilgisi(**{**U.__dict__, "etiketleme_adedi": SIFIR})
    satirlar, _ = direkt_iscilik(u, O, P)
    assert {s.kalem: s.tutar for s in satirlar}["Etiketleme İşçilik Giderleri"] == SIFIR


def test_genel_uretim_001():
    satirlar, uyarilar = genel_uretim(U, O, P)
    t = {s.kalem: s.tutar for s in satirlar}
    assert yakin(t["Endirekt İşçilik Giderleri"], D_("0.5371490395802625"))                      # P108
    assert yakin(t["Mal Kabul ve Fermantasyon Genel Üretim Giderleri"], D_("0.11408075399999999"))  # P109
    assert yakin(t["Elektrik Giderleri"], D_("0.2689961878459595"))                               # P110
    assert yakin(t["Doğalgaz Giderleri"], D_("0.5238592715975372"))                               # P111
    assert yakin(t["Amortisman Giderleri"], D_("1.069375675846589"))                              # P112
    assert yakin(t["Diğer Genel Üretim Giderleri"], D_("0.3226458506272717"))                     # P113
    assert yakin(sum(s.tutar for s in satirlar), D_("2.83610677949762")) and uyarilar == []


def test_hat_bulunamazsa_sifir_ve_uyari():
    u = UretimBilgisi(**{**U.__dict__, "hat": "Yok"})
    satirlar, uyarilar = genel_uretim(u, O, P)
    assert {s.kalem: s.tutar for s in satirlar}["Elektrik Giderleri"] == SIFIR and any("hat" in w.lower() for w in uyarilar)


def test_diger_giderler_001():
    satirlar, _ = diger_giderler(U, O)
    t = {s.kalem: s.tutar for s in satirlar}
    assert yakin(t["Pazarlama Satış Giderleri"], D_("0.5048087845717276"))
    assert yakin(t["Genel Yönetim Giderleri"], D_("0.7872650748141269"))


def test_diger_giderler_kapali():
    u = UretimBilgisi(**{**U.__dict__, "pazarlama_yonetim_uygula": False})
    satirlar, _ = diger_giderler(u, O)
    assert all(s.tutar == SIFIR for s in satirlar)
```

- [ ] **Step 2: Çalıştır, başarısız** — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/uretim_gideri.py
"""F5/F6/F7: İşçilik, genel üretim ve pazarlama/yönetim giderleri. Excel 001!P103:P119."""
from decimal import Decimal
from .fire import brut_miktar
from .gider_dagitim import anahtar
from .modeller import GiderOranlari, MaliyetSatiri, Parametreler, UretimBilgisi
from .para import SIFIR

SANIYE_SAAT = Decimal(3600)


def adet_basina_saniye(u: UretimBilgisi, p: Parametreler) -> Decimal:
    """Excel: 27000/E138. 27000 = 7,5 saat * 3600."""
    if u.vardiya_uretim_adedi == SIFIR:
        return SIFIR
    return p.vardiya_saati * SANIYE_SAAT / u.vardiya_uretim_adedi


def _satir(kalem, grup, miktar, brut, fiyat) -> MaliyetSatiri:
    return MaliyetSatiri(kalem=kalem, grup=grup, miktar=miktar, brut_miktar=brut, birim_fiyat=fiyat, tutar=brut * fiyat)


def _oran(tablo: dict, ad: str, ne: str, uyarilar: list[str]) -> Decimal:
    k = anahtar(ad)
    if k not in tablo:
        uyarilar.append(f"{ne} bulunamadı: '{ad}', gider 0 alındı")
        return SIFIR
    return tablo[k]


def direkt_iscilik(u: UretimBilgisi, o: GiderOranlari, p: Parametreler) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    sn = adet_basina_saniye(u, p)
    mk_brut = brut_miktar(u.mal_kabul_miktar_kg, u.mal_kabul_fire)
    mk_oran = _oran(o.mal_kabul_iscilik_kg, u.taze_tursu_sinifi, "taze/turşu sınıfı", uyarilar)
    etiket_sn = SIFIR if u.etiketleme_adedi == SIFIR else p.vardiya_saati * SANIYE_SAAT / u.etiketleme_adedi
    return [
        _satir("Mal Kabul ve Fermantasyon Giderleri", "direkt_iscilik", u.mal_kabul_miktar_kg, mk_brut, mk_oran),
        _satir("Dolum Doğrudan İşçilik Giderleri", "direkt_iscilik", sn, sn * u.dolum_personel, o.dolum_iscilik_sn),
        _satir("Etiketleme İşçilik Giderleri", "direkt_iscilik", etiket_sn, etiket_sn * u.etiket_personel, o.etiket_iscilik_sn),
    ], uyarilar


def genel_uretim(u: UretimBilgisi, o: GiderOranlari, p: Parametreler) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    sn = adet_basina_saniye(u, p)
    mk = u.mal_kabul_miktar_kg          # Excel K109 = I109, fire yok
    return [
        _satir("Endirekt İşçilik Giderleri", "gug", sn, sn, o.endirekt_iscilik_sn),
        _satir("Mal Kabul ve Fermantasyon Genel Üretim Giderleri", "gug", mk, mk,
               _oran(o.mal_kabul_gug_kg, u.taze_tursu_sinifi, "taze/turşu sınıfı", uyarilar)),
        _satir("Elektrik Giderleri", "gug", sn, sn, _oran(o.elektrik_sn, u.hat, "üretim hattı", uyarilar)),
        _satir("Doğalgaz Giderleri", "gug", sn, sn, _oran(o.dogalgaz_sn, u.hat, "üretim hattı", uyarilar)),
        _satir("Amortisman Giderleri", "gug", sn, sn, _oran(o.amortisman_sn, u.hat, "üretim hattı", uyarilar)),
        _satir("Diğer Genel Üretim Giderleri", "gug", sn, sn, o.diger_gug_sn),
    ], uyarilar


def diger_giderler(u: UretimBilgisi, o: GiderOranlari) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    bir = Decimal(1)
    if not u.pazarlama_yonetim_uygula:
        paz = yon = SIFIR
    else:
        paz = o.pazarlama_adet.get(u.ambalaj_hacmi)
        yon = o.yonetim_adet.get(u.ambalaj_hacmi)
        if paz is None or yon is None:
            uyarilar.append(f"ambalaj hacmi {u.ambalaj_hacmi} dağıtım tablosunda yok, pazarlama/yönetim 0 alındı")
            paz, yon = SIFIR, SIFIR
    return [
        _satir("Pazarlama Satış Giderleri", "diger", bir, bir, paz),
        _satir("Genel Yönetim Giderleri", "diger", bir, bir, yon),
    ], uyarilar
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 7 passed

- [ ] **Step 5: Commit** — `git commit -m "feat: F5/F6/F7 üretim giderleri ve pazarlama/yönetim payı"`

---

### Task 7: F9, F10 Finansman ve döviz maliyeti (`finansman.py`)

**Files:**
- Create: `fiyat_motoru/finansman.py`, `tests/test_finansman.py`

**Interfaces:**
- Produces:
  - `finansman_gideri(maliyet, faiz_orani, stok_ay) -> Decimal` = `maliyet * faiz/12 * ay` (P124)
  - `tum_finansman(giydirilmis: Decimal, p: Parametreler) -> dict[str, Decimal]` = her para birimi için (TL, USD, EUR, ...)
  - `doviz_maliyet(giydirilmis: Decimal, finansman: dict, p: Parametreler) -> dict[str, Decimal]` = `(giydirilmis + finansman[pb]) / kur[pb]` (P131, P132, P133)

- [ ] **Step 1: Başarısız test**

```python
# tests/test_finansman.py
from decimal import Decimal
from fiyat_motoru.finansman import finansman_gideri, tum_finansman, doviz_maliyet
from fiyat_motoru.modeller import Parametreler
from fiyat_motoru.para import yakin

D_ = Decimal
P = Parametreler(enflasyon=D_("0.25"), kurlar={"USD": D_(50), "EUR": D_(60), "GBP": D_(68)},
                 faiz_oranlari={"TL": D_("0.4"), "USD": D_("0.06"), "EUR": D_("0.06"), "GBP": D_("0.06")},
                 stok_sureleri_ay={"TL": D_(6), "USD": D_(6), "EUR": D_(6), "GBP": D_(6)},
                 satis_kar_orani=D_("0.2"), teklif_kar_oranlari=(), vardiya_saati=D_("7.5"))
GIY = D_("31.775657799710626")   # 001!P122


def test_basit_faiz():
    assert yakin(finansman_gideri(GIY, D_("0.4"), D_(6)), D_("6.355131559942126"))   # P124
    assert yakin(finansman_gideri(GIY, D_("0.06"), D_(6)), D_("0.9532697339913188"))  # P125


def test_tum_finansman():
    f = tum_finansman(GIY, P)
    assert set(f) == {"TL", "USD", "EUR", "GBP"} and yakin(f["TL"], D_("6.355131559942126"))


def test_doviz_maliyet():
    f = tum_finansman(GIY, P)
    d = doviz_maliyet(GIY, f, P)
    assert yakin(d["USD"], D_("0.6545785506740388"))   # P131
    assert yakin(d["EUR"], D_("0.5454821255616991"))   # P132
    assert yakin(d["GBP"], D_("0.48130775784855795"))  # P133
    assert "TL" not in d
```

- [ ] **Step 2: Çalıştır, başarısız** — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/finansman.py
"""F9/F10: Finansman gideri (basit faiz) ve döviz bazında maliyet. Excel 001!P124:P134."""
from decimal import Decimal
from .modeller import Parametreler

ON_IKI = Decimal(12)


def finansman_gideri(maliyet: Decimal, faiz_orani: Decimal, stok_ay: Decimal) -> Decimal:
    """Yıllık faiz * ortalama stok süresi (ay) * birim maliyet."""
    return maliyet * (faiz_orani / ON_IKI * stok_ay)


def tum_finansman(giydirilmis: Decimal, p: Parametreler) -> dict[str, Decimal]:
    return {pb: finansman_gideri(giydirilmis, p.faiz_oranlari[pb], p.stok_sureleri_ay[pb]) for pb in p.faiz_oranlari}


def doviz_maliyet(giydirilmis: Decimal, finansman: dict[str, Decimal], p: Parametreler) -> dict[str, Decimal]:
    return {pb: (giydirilmis + finansman[pb]) / kur for pb, kur in p.kurlar.items() if pb in finansman}
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 3 passed

- [ ] **Step 5: Commit** — `git commit -m "feat: F9/F10 finansman ve döviz maliyeti"`

---

### Task 8: F11, F12, F13 Satış fiyatı, yüzdeler, süzme kg (`fiyat.py`)

**Files:**
- Create: `fiyat_motoru/fiyat.py`, `tests/test_fiyat.py`

**Interfaces:**
- Produces:
  - `satis_fiyati(maliyet, kar_orani) -> Decimal` = `maliyet * (1+kar)` (P137 = P130*1.2; P138 = P131*1.2)
  - `teklifler(doviz_maliyet_usd, kar_oranlari) -> list[Decimal]` = `[m*(1+k) for k]` (P145-147)
  - `suzme_kg_fiyati(satis_tl, suzme_kg) -> Decimal` = `satis_tl / suzme_kg`, suzme 0 ise SIFIR (P143)
  - `yuzdeleri_doldur(satirlar, pazar, maliyet_tl, satis_tl, kur_usd, maliyet_usd, satis_usd) -> None` — her satıra R ve S:
    - Yurtiçi: `R = tutar/maliyet_tl`, `S = tutar/satis_tl`
    - Yurtdışı: `R = tutar/kur_usd/maliyet_usd`, `S = tutar/kur_usd/satis_usd`

- [ ] **Step 1: Başarısız test**

```python
# tests/test_fiyat.py
from decimal import Decimal
from fiyat_motoru.fiyat import satis_fiyati, teklifler, suzme_kg_fiyati, yuzdeleri_doldur
from fiyat_motoru.modeller import MaliyetSatiri
from fiyat_motoru.para import yakin, SIFIR

D_ = Decimal


def test_satis_fiyati():
    assert yakin(satis_fiyati(D_("38.13078935965275"), D_("0.2")), D_("45.756947231583304"))  # P137


def test_teklifler_usd():
    t = teklifler(D_("0.6545785506740388"), (D_("0.2"), D_("0.17"), D_("0.14")))
    assert [str(round(x, 10)) for x in t] == ["0.7854942608", "0.7658569043", "0.7462195478"]  # P145-147


def test_suzme():
    assert yakin(suzme_kg_fiyati(D_("45.756947231583304"), D_("0.18")), D_("254.20526239768503"))  # P143
    assert suzme_kg_fiyati(D_(10), SIFIR) == SIFIR


def test_yuzdeler_yurtici():
    s = MaliyetSatiri(kalem="k", grup="malzeme", miktar=D_(1), brut_miktar=D_(1), birim_fiyat=D_(1),
                      tutar=D_("7.525510204081633"))   # 001!P13 kavanoz
    yuzdeleri_doldur([s], "Yurtiçi", D_("38.13078935965275"), D_("45.756947231583304"), D_(50), SIFIR, SIFIR)
    assert yakin(s.maliyet_yuzdesi, D_("0.19736046199045082")) and yakin(s.fiyat_yuzdesi, D_("0.164467051658709"))


def test_yuzdeler_yurtdisi():
    s = MaliyetSatiri(kalem="k", grup="malzeme", miktar=D_(1), brut_miktar=D_(1), birim_fiyat=D_(1), tutar=D_(50))
    yuzdeleri_doldur([s], "Yurtdışı", SIFIR, SIFIR, D_(50), D_(2), D_(4))
    assert s.maliyet_yuzdesi == D_("0.5") and s.fiyat_yuzdesi == D_("0.25")
```

- [ ] **Step 2: Çalıştır, başarısız** — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/fiyat.py
"""F11/F12/F13: Satış fiyatı, teklif turları, kalem yüzdeleri, süzme kg fiyatı. Excel 001!P137:P147, R/S sütunları."""
from decimal import Decimal
from .modeller import MaliyetSatiri
from .para import BIR, SIFIR


def satis_fiyati(maliyet: Decimal, kar_orani: Decimal) -> Decimal:
    return maliyet * (BIR + kar_orani)


def teklifler(doviz_maliyet: Decimal, kar_oranlari) -> list[Decimal]:
    return [doviz_maliyet * (BIR + k) for k in kar_oranlari]


def suzme_kg_fiyati(satis_tl: Decimal, suzme_kg: Decimal) -> Decimal:
    return SIFIR if suzme_kg == SIFIR else satis_tl / suzme_kg


def _bol(a: Decimal, b: Decimal) -> Decimal:
    return SIFIR if b == SIFIR else a / b


def yuzdeleri_doldur(satirlar: list[MaliyetSatiri], pazar: str, maliyet_tl: Decimal, satis_tl: Decimal,
                     kur_usd: Decimal, maliyet_usd: Decimal, satis_usd: Decimal) -> None:
    for s in satirlar:
        if pazar == "Yurtdışı":
            usd = _bol(s.tutar, kur_usd)
            s.maliyet_yuzdesi = _bol(usd, maliyet_usd)
            s.fiyat_yuzdesi = _bol(usd, satis_usd)
        else:
            s.maliyet_yuzdesi = _bol(s.tutar, maliyet_tl)
            s.fiyat_yuzdesi = _bol(s.tutar, satis_tl)
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 5 passed

- [ ] **Step 5: Commit** — `git commit -m "feat: F11/F12/F13 satış fiyatı, yüzdeler, süzme kg"`

---

### Task 9: Orkestrasyon (`hesapla.py`)

**Files:**
- Create: `fiyat_motoru/hesapla.py`, `tests/test_hesapla.py`

**Interfaces:**
- Consumes: Task 3-8'deki tüm fonksiyonlar
- Produces: `urun_maliyeti(girdi: UrunGirdisi, malzemeler: dict[str, Malzeme], oranlar: GiderOranlari, p: Parametreler) -> MaliyetSonucu`

Akış (Excel satır sırası): malzeme satırları → P100; direkt işçilik → P103; GÜG → P107; P114 = P103+P107; P116 = P100+P114; diğer → P120; P122 = P116+P120; finansman (tüm para birimleri); P130 = P122 + fin[TL]; döviz maliyet; P137 = P130*(1+kar); P138.. = döviz*(1+kar); P143; teklifler (USD); yüzdeler tüm satırlara + finansman TL satırı (R124 = P124/P130).

- [ ] **Step 1: Başarısız test** — 001 sayfasının küçültülmüş hali (3 malzeme satırı) ile uçtan uca: beklenen değerler elle hesaplanır.

```python
# tests/test_hesapla.py
from decimal import Decimal
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.modeller import Malzeme, ReceteSatiri, UrunGirdisi, UretimBilgisi, Parametreler, GiderOranlari
from fiyat_motoru.para import yakin, SIFIR
from tests.test_uretim_gideri import O, U, P as P_URETIM

D_ = Decimal
P = Parametreler(enflasyon=D_("0.25"), kurlar={"USD": D_(50), "EUR": D_(60)},
                 faiz_oranlari={"TL": D_("0.4"), "USD": D_("0.06"), "EUR": D_("0.06")},
                 stok_sureleri_ay={"TL": D_(6), "USD": D_(6), "EUR": D_(6)},
                 satis_kar_orani=D_("0.2"), teklif_kar_oranlari=(D_("0.2"), D_("0.17"), D_("0.14")), vardiya_saati=D_("7.5"))
MALZ = {
    "KAV": Malzeme("KAV", "Cam Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", D_("5.9"), "S"),
    "ETK": Malzeme("ETK", "Etiket", "0008-Ambalaj Malzeme", "AD", "EUR", D_("0.049"), "S"),
    "TAZ": Malzeme("TAZ", "Sarı Biberiye Taze", "0001-Hammadde", "KG", "TL", D_(65), "Z"),
}
GIRDI = UrunGirdisi(kod="TEST", ad="Test Ürün", uretim=U, recete=(
    ReceteSatiri("KAV", "Cam Kavanoz 370", D_(1), D_("0.02"), "AD"),
    ReceteSatiri("ETK", "Etiket", D_(1), D_("0.02"), "AD"),
    ReceteSatiri("TAZ", "Sarı Biberiye Taze", D_("0.19013459"), SIFIR, "KG"),
    ReceteSatiri("YOK", "Fiyatsız Ara Mamul", D_(1), SIFIR, "KG"),
))


def test_uctan_uca():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    # malzeme: 7.525510204081633 + 3 + 12.35874835 + 0
    assert yakin(r.malzeme_toplami, D_("22.884258554081633"))
    assert yakin(r.direkt_iscilik_toplami, D_("1.9806745445746057"))
    assert yakin(r.gug_toplami, D_("2.83610677949762"))
    assert yakin(r.uretim_gideri_toplami, D_("4.816781324072226"))
    assert yakin(r.toplam_birim_maliyet, r.malzeme_toplami + r.uretim_gideri_toplami)
    assert yakin(r.diger_giderler_toplami, D_("1.2920738593858545"))
    giy = r.toplam_birim_maliyet + r.diger_giderler_toplami
    assert yakin(r.giydirilmis_maliyet, giy)
    assert yakin(r.finansman["TL"], giy * D_("0.2"))
    assert yakin(r.finansman_dahil_maliyet_tl, giy * D_("1.2"))
    assert yakin(r.doviz_maliyet["USD"], (giy + giy * D_("0.03")) / 50)
    assert yakin(r.satis_fiyati_tl, r.finansman_dahil_maliyet_tl * D_("1.2"))
    assert yakin(r.satis_fiyati_doviz["USD"], r.doviz_maliyet["USD"] * D_("1.2"))
    assert yakin(r.suzme_kg_fiyati_tl, r.satis_fiyati_tl / D_("0.18"))
    assert len(r.teklifler_usd) == 3 and yakin(r.teklifler_usd[1], r.doviz_maliyet["USD"] * D_("1.17"))


def test_yuzdeler_toplami_bir():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    # R sütunu: tüm kalemler + finansman TL = 1 (Excel R130)
    assert yakin(sum(s.maliyet_yuzdesi for s in r.satirlar), D_(1))


def test_fiyatsiz_malzeme_uyarisi():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    assert any("YOK" in u for u in r.uyarilar)
    assert [s.grup for s in r.satirlar].count("finansman") == 1
```

- [ ] **Step 2: Çalıştır, başarısız** — Expected: `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/hesapla.py
"""Ürün maliyeti orkestrasyonu: UrunGirdisi -> MaliyetSonucu. Excel 001 sayfasının P sütunu sırasıyla."""
from decimal import Decimal
from .finansman import doviz_maliyet, tum_finansman
from .fiyat import satis_fiyati, suzme_kg_fiyati, teklifler, yuzdeleri_doldur
from .malzeme import malzeme_toplami, malzeme_tutari
from .modeller import GiderOranlari, Malzeme, MaliyetSatiri, MaliyetSonucu, Parametreler, UrunGirdisi
from .para import SIFIR
from .uretim_gideri import diger_giderler, direkt_iscilik, genel_uretim


def _toplam(satirlar: list[MaliyetSatiri]) -> Decimal:
    return sum((s.tutar for s in satirlar), SIFIR)


def urun_maliyeti(girdi: UrunGirdisi, malzemeler: dict[str, Malzeme], oranlar: GiderOranlari, p: Parametreler) -> MaliyetSonucu:
    uyarilar: list[str] = []
    malz_satirlari = []
    for rs in girdi.recete:
        s, u = malzeme_tutari(rs, malzemeler.get(rs.malzeme_kodu), p)
        malz_satirlari.append(s)
        if u:
            uyarilar.append(u)
    di, u1 = direkt_iscilik(girdi.uretim, oranlar, p)
    gug, u2 = genel_uretim(girdi.uretim, oranlar, p)
    diger, u3 = diger_giderler(girdi.uretim, oranlar)
    uyarilar += u1 + u2 + u3

    malzeme_top = malzeme_toplami(malz_satirlari)
    di_top, gug_top, diger_top = _toplam(di), _toplam(gug), _toplam(diger)
    uretim_top = di_top + gug_top
    birim = malzeme_top + uretim_top
    giydirilmis = birim + diger_top
    fin = tum_finansman(giydirilmis, p)
    maliyet_tl = giydirilmis + fin.get("TL", SIFIR)
    doviz = doviz_maliyet(giydirilmis, fin, p)
    satis_tl = satis_fiyati(maliyet_tl, p.satis_kar_orani)
    satis_doviz = {pb: satis_fiyati(m, p.satis_kar_orani) for pb, m in doviz.items()}
    usd = doviz.get("USD", SIFIR)

    fin_satiri = MaliyetSatiri(kalem="Finansman Giderleri (TL)", grup="finansman", miktar=Decimal(1), brut_miktar=Decimal(1),
                               birim_fiyat=fin.get("TL", SIFIR), tutar=fin.get("TL", SIFIR))
    satirlar = malz_satirlari + di + gug + diger + [fin_satiri]
    yuzdeleri_doldur(satirlar, girdi.uretim.pazar, maliyet_tl, satis_tl, p.kurlar.get("USD", SIFIR),
                     usd, satis_doviz.get("USD", SIFIR))

    return MaliyetSonucu(
        urun_kodu=girdi.kod, satirlar=satirlar,
        malzeme_toplami=malzeme_top, direkt_iscilik_toplami=di_top, gug_toplami=gug_top,
        uretim_gideri_toplami=uretim_top, toplam_birim_maliyet=birim,
        pazarlama_gideri=diger[0].tutar, yonetim_gideri=diger[1].tutar, diger_giderler_toplami=diger_top,
        giydirilmis_maliyet=giydirilmis, finansman=fin, finansman_dahil_maliyet_tl=maliyet_tl,
        doviz_maliyet=doviz, satis_fiyati_tl=satis_tl, satis_fiyati_doviz=satis_doviz,
        suzme_kg_fiyati_tl=suzme_kg_fiyati(satis_tl, girdi.uretim.suzme_kg),
        teklifler_usd=teklifler(usd, p.teklif_kar_oranlari), uyarilar=uyarilar,
    )
```

- [ ] **Step 4: Çalıştır, geçer** — Run: `.\.venv\Scripts\python -m pytest tests/ -v` — Expected: tümü passed

- [ ] **Step 5: Commit** — `git commit -m "feat: ürün maliyeti orkestrasyonu"`

---

### Task 10: Excel okuyucu (`excel_okuyucu.py`)

**Files:**
- Create: `fiyat_motoru/excel_okuyucu.py`, `tests/test_excel_okuyucu.py`

**Interfaces:**
- Produces:
  - `malzemeleri_oku(wb) -> dict[str, Malzeme]` — `S.ALMA BF` sayfası (A kod, B ad, C tip, D birim, E para, F fiyat, G Z/S). İlk 833 satır; kod boşsa atla. **Not:** Excel VLOOKUP'ta `N` sütunu `'S.ALMA BF'!A:I` 7. sütun = G (Departman). Yani `zs = G`.
  - `havuzlari_oku(wb) -> GiderHavuzlari` — `Gider Dağıtım` sabit hücreler (Task 5 testindeki yapıya göre; hücre adresleri aşağıda).
  - `urun_sayfalarini_listele(wb) -> list[str]` — adı `\d{3}( \(2\))?` kalıbına uyan sayfalar.
  - `urun_oku(ws_formul, ws_deger, parametre_cikar=True) -> tuple[UrunGirdisi, Parametreler, dict[str, Decimal]]` — üçüncü eleman **beklenen değerler** (`{"P100": ..., "P103": ..., ..., "P147": ..., "R100": ..., "S100": ...}`); satır konumları **etiket aramasıyla** bulunur (sayfa `053` 10 satır kaymış).
  - `excel_ac(yol) -> tuple[Workbook, Workbook]` — (formüllü, değerli) iki kopya.

Gider Dağıtım hücreleri: `D4,F4` dolum; `A6` mal kabul işçilik toplam, `C7:C9` sınıf, `G7:G9` pay, `E7:E9` kg; `D13,F13` etiket; `D18,F18` endirekt; `A20` mal kabul GÜG toplam, `C21:C23/G21:G23/E21:E23`; `D27,F27` diğer GÜG; `D38` elektrik toplam, `A30:A37` hat, `G30:G37` pay, `E30:E37` sn; `D49` doğalgaz, `A41:A48/G41:G48/E41:E48`; `D60` amortisman, `A52:A59/G52:G59/E52:E59`; `D64` yönetim toplam; `D67` pazarlama toplam; `A70:A91` ambalaj adı, `B` hacim, `C` adet, `D` katsayı.

Ürün sayfası etiketleri (D sütununda aranır; `startswith`):
| Etiket | Ne okunur |
|---|---|
| `HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI` | reçete bitişi; `P` = beklenen P100, `R`,`S` |
| reçete satırları: 6. satırdan bu etikete kadar `D` dolu olanlar | D kod, E ad, I miktar, J fire, L birim |
| `DİREKT İŞÇİLİK GİDERLERİ` | P103, R, S |
| `Mal Kabul ve Fermantasyon Giderleri` | I → `mal_kabul_miktar_kg`, J → `mal_kabul_fire`; P104 |
| `Dolum Doğrudan İşçilik Giderleri` / `Etiketleme İşçilik Giderleri` | P105 / P106 |
| `GENEL ÜRETİM GİDERLERİ` | P107 |
| `Endirekt İşçilik Giderleri` … `Diğer Genel Üretim Giderleri` | P108..P113 |
| `GİDER TOPLAMI`, `TOPLAM BİRİM MALİYET` | P114, P116 |
| `PAZARLAMA SATIŞ GİDERLERİ` / `GENEL YÖNETİM GİDERLERİ` | P118, P119; **formül hücresi sabit 0 ise** `pazarlama_yonetim_uygula=False` |
| `DİĞER GİDERLER TOPLAMI`, `DİĞER GİDERLER GİYDİRİLMİŞ BİRİM MALİYET` | P120, P122 |
| `FİNANSMAN GİDERLERİ` | aynı satır: I para, J faiz, K ay, P tutar; sonraki 4 satır (USD, EUR, GBP, ZAR) aynı şekilde |
| `FİNANSMAN GİDERİ DAHİL EDİLMİŞ MALİYET` | P130; +1 satır P131 (USD), +2 P132 (EUR), +3 P133 (GBP) |
| `Süzme Miktar (kg.)` | E → suzme_kg; **+1 satır** P → P137 (satış TL); +2 satır P → P138 (USD) |
| `Vardiya Üretim Adedi` | E138 |
| `Dolum İşçilik Pers.Sayısı` | E140 |
| `Etiketleme Adedi` | E141 |
| `Etiket İşçilik Pers.Sayısı` | E143; aynı satır P → P143 süzme kg fiyatı |
| `Üretim` (tam eşleşme) | E144 hat |
| `Taze / Turşu` | E145 sınıf; aynı satır L kâr1, P teklif1 |
| `Ambalaj` (tam eşleşme) | E146 hacim; L kâr2, P teklif2 |
| `Ürün Adı` | L kâr3, P teklif3 |
| `Enflasyon` | F148 |
| `Döviz Kurları` | F USD; +1 EUR; +2 GBP; +3 CHF |
| `P2` | pazar |
| `D6`, `E6` | ürün kodu ve adı (satır 6 sabit) |

Satış kâr oranı: `P137` formülü `=+P130*1.2` → `satis_kar_orani = Decimal("0.2")` sabit kabul edilir (formülden `*1.2` parse etmeye gerek yok; parite testi yakalar).

- [ ] **Step 1: Başarısız test**

```python
# tests/test_excel_okuyucu.py
from decimal import Decimal
import pytest
from fiyat_motoru.excel_okuyucu import excel_ac, malzemeleri_oku, havuzlari_oku, urun_sayfalarini_listele, urun_oku
from fiyat_motoru.para import yakin


@pytest.fixture(scope="module")
def wb(excel_yolu):
    return excel_ac(excel_yolu)


def test_malzemeler(wb):
    m = malzemeleri_oku(wb[1])
    assert len(m) >= 800
    kav = m["20.10.051.000.0000"]
    assert kav.fiyat == Decimal("5.9") and kav.para_birimi == "TL" and kav.zs == "S"
    assert m["10.002.005.00112"].zs == "Z"


def test_havuzlar(wb):
    h = havuzlari_oku(wb[1])
    assert yakin(h.dolum_iscilik_toplam, Decimal("86037707.86667047"))
    assert h.mal_kabul_paylari["Turşu/Turşu"] == (Decimal("0.1"), Decimal(3500000))
    assert len(h.ambalajlar) == 22 and h.ambalajlar[4].hacim == Decimal(370)


def test_sayfa_listesi(wb):
    s = urun_sayfalarini_listele(wb[1])
    assert "001" in s and "053" in s and "001 (2)" in s and "Teklif Kapak" not in s


def test_urun_001(wb):
    girdi, p, beklenen = urun_oku(wb[0]["001"], wb[1]["001"])
    assert girdi.kod == "03.004.001.002.00010"
    assert len(girdi.recete) >= 20
    assert girdi.uretim.vardiya_uretim_adedi == Decimal(65000) and girdi.uretim.hat == "Niko"
    assert girdi.uretim.taze_tursu_sinifi == "Turşu/Turşu" and girdi.uretim.ambalaj_hacmi == Decimal(370)
    assert yakin(girdi.uretim.mal_kabul_miktar_kg, Decimal("0.19013459"))
    assert p.kurlar["USD"] == Decimal(50) and p.enflasyon == Decimal("0.25")
    assert p.faiz_oranlari["TL"] == Decimal("0.4") and p.stok_sureleri_ay["TL"] == Decimal(6)
    assert p.teklif_kar_oranlari == (Decimal("0.2"), Decimal("0.17"), Decimal("0.14"))
    assert yakin(beklenen["P130"], Decimal("38.13078935965275"))
    assert yakin(beklenen["P147"], Decimal("0.7462195477684043"))


def test_urun_053_kaymis_satirlar(wb):
    girdi, p, beklenen = urun_oku(wb[0]["053"], wb[1]["053"])
    assert "P130" in beklenen and beklenen["P130"] is not None
```

- [ ] **Step 2: Çalıştır, başarısız** — Run: `.\.venv\Scripts\python -m pytest tests/test_excel_okuyucu.py -v` — Expected: `ModuleNotFoundError` (Excel yoksa `skipped`)

- [ ] **Step 3: Uygulama**

```python
# fiyat_motoru/excel_okuyucu.py
"""Fiyat Çalışma Excel'inden motor girdileri ve beklenen (altın) değerleri okur.
Ürün sayfalarında satır numaraları sabit değildir ('053' kaymış); konumlar D sütunundaki etiketlerle bulunur."""
import re
from decimal import Decimal
from pathlib import Path
import openpyxl
from .modeller import AmbalajSinifi, GiderHavuzlari, Malzeme, Parametreler, ReceteSatiri, UretimBilgisi, UrunGirdisi
from .para import D, SIFIR

URUN_SAYFA = re.compile(r"^\d{3}( \(2\))?$")


def excel_ac(yol: Path):
    return openpyxl.load_workbook(yol, data_only=False), openpyxl.load_workbook(yol, data_only=True)


def malzemeleri_oku(wb_deger) -> dict[str, Malzeme]:
    ws = wb_deger["S.ALMA BF"]
    out = {}
    for kod, ad, tip, birim, para, fiyat, zs, *_ in ws.iter_rows(min_row=2, values_only=True):
        if not kod:
            continue
        out[str(kod).strip()] = Malzeme(kod=str(kod).strip(), ad=(ad or "").strip(), tip=tip, birim=birim,
                                        para_birimi=para, fiyat=D(fiyat), zs=zs)
    return out


def _paylar(ws, satirlar, ad_sutunu, pay_sutunu, baz_sutunu):
    return {str(ws[f"{ad_sutunu}{r}"].value).strip(): (D(ws[f"{pay_sutunu}{r}"].value), D(ws[f"{baz_sutunu}{r}"].value))
            for r in satirlar if ws[f"{ad_sutunu}{r}"].value}


def havuzlari_oku(wb_deger) -> GiderHavuzlari:
    ws = wb_deger["Gider Dağıtım"]
    v = lambda a: D(ws[a].value)
    return GiderHavuzlari(
        dolum_iscilik_toplam=v("D4"), dolum_iscilik_saniye=v("F4"),
        mal_kabul_iscilik_toplam=v("A6"), mal_kabul_paylari=_paylar(ws, range(7, 10), "C", "G", "E"),
        etiket_iscilik_toplam=v("D13"), etiket_iscilik_saniye=v("F13"),
        endirekt_iscilik_toplam=v("D18"), endirekt_saniye=v("F18"),
        mal_kabul_gug_toplam=v("A20"), mal_kabul_gug_paylari=_paylar(ws, range(21, 24), "C", "G", "E"),
        diger_gug_toplam=v("D27"), diger_gug_saniye=v("F27"),
        elektrik_toplam=v("D38"), elektrik_hatlar=_paylar(ws, range(30, 38), "A", "G", "E"),
        dogalgaz_toplam=v("D49"), dogalgaz_hatlar=_paylar(ws, range(41, 49), "A", "G", "E"),
        amortisman_toplam=v("D60"), amortisman_hatlar=_paylar(ws, range(52, 60), "A", "G", "E"),
        yonetim_toplam=v("D64"), pazarlama_toplam=v("D67"),
        ambalajlar=tuple(AmbalajSinifi(ad=str(ws[f"A{r}"].value), hacim=D(ws[f"B{r}"].value),
                                       uretim_adedi=D(ws[f"C{r}"].value), katsayi=D(ws[f"D{r}"].value))
                         for r in range(70, 92) if ws[f"A{r}"].value),
    )


def urun_sayfalarini_listele(wb) -> list[str]:
    return [ws.title for ws in wb.worksheets if URUN_SAYFA.match(ws.title)]


def _etiket_satiri(ws, etiket: str, tam: bool = False, sutun: str = "D") -> int:
    for r in range(1, ws.max_row + 1):
        val = ws[f"{sutun}{r}"].value
        if isinstance(val, str):
            s = val.strip()
            if (s == etiket) if tam else s.startswith(etiket):
                return r
    raise KeyError(f"etiket bulunamadı: {etiket!r}")


def _sabit_sifir(ws_formul, adres: str) -> bool:
    v = ws_formul[adres].value
    return v in (0, None) or (isinstance(v, (int, float)) and v == 0)


def urun_oku(ws_f, ws_v) -> tuple[UrunGirdisi, Parametreler, dict[str, Decimal]]:
    E = lambda r: _etiket_satiri(ws_v, r)
    Et = lambda r: _etiket_satiri(ws_v, r, tam=True)
    val = lambda a: ws_v[a].value
    d = lambda a: D(val(a))

    r100 = E("HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    recete = tuple(
        ReceteSatiri(malzeme_kodu=str(val(f"D{r}")).strip(), ad=str(val(f"E{r}") or "").strip(),
                     miktar=d(f"I{r}"), fire_orani=d(f"J{r}"), birim=val(f"L{r}"))
        for r in range(6, r100) if val(f"D{r}")
    )
    r103, r104, r105, r106 = E("DİREKT İŞÇİLİK GİDERLERİ"), E("Mal Kabul ve Fermantasyon Giderleri"), \
        E("Dolum Doğrudan İşçilik Giderleri"), E("Etiketleme İşçilik Giderleri")
    r107 = E("GENEL ÜRETİM GİDERLERİ")
    r108 = E("Endirekt İşçilik Giderleri"); r109 = E("Mal Kabul ve Fermantasyon Genel Üretim Giderleri")
    r110, r111, r112, r113 = E("Elektrik Giderleri"), E("Doğalgaz Giderleri"), E("Amortisman Giderleri"), E("Diğer Genel Üretim Giderleri")
    r114, r116 = Et("GİDER TOPLAMI"), E("TOPLAM BİRİM MALİYET")
    r118, r119 = E("PAZARLAMA SATIŞ GİDERLERİ"), E("GENEL YÖNETİM GİDERLERİ")
    r120, r122 = E("DİĞER GİDERLER TOPLAMI"), E("DİĞER GİDERLER GİYDİRİLMİŞ BİRİM MALİYET")
    r124, r130 = E("FİNANSMAN GİDERLERİ"), E("FİNANSMAN GİDERİ DAHİL EDİLMİŞ MALİYET")
    r136, r138, r140, r141, r143 = E("Süzme Miktar"), E("Vardiya Üretim Adedi"), E("Dolum İşçilik Pers"), E("Etiketleme Adedi"), E("Etiket İşçilik Pers")
    r144, r145, r146, r147 = Et("Üretim"), E("Taze / Turşu"), Et("Ambalaj"), Et("Ürün Adı")
    r148, r150 = Et("Enflasyon"), E("Döviz Kurları")

    faiz, stok = {}, {}
    for i in range(5):                                   # TL, USD, EUR, GBP, ZAR
        pb = val(f"I{r124 + i}")
        if pb:
            faiz[str(pb)] = d(f"J{r124 + i}"); stok[str(pb)] = d(f"K{r124 + i}")
    kurlar = {str(val(f"E{r150 + i}")): d(f"F{r150 + i}") for i in range(4) if val(f"E{r150 + i}")}  # USD, EUR, GBP, CHF

    p = Parametreler(enflasyon=d(f"F{r148}"), kurlar=kurlar, faiz_oranlari=faiz, stok_sureleri_ay=stok,
                     satis_kar_orani=Decimal("0.2"),
                     teklif_kar_oranlari=(d(f"L{r145}"), d(f"L{r146}"), d(f"L{r147}")), vardiya_saati=Decimal("7.5"))
    uretim = UretimBilgisi(
        pazar=str(val("P2") or "Yurtiçi"), vardiya_uretim_adedi=d(f"E{r138}"), dolum_personel=d(f"E{r140}"),
        etiketleme_adedi=d(f"E{r141}"), etiket_personel=d(f"E{r143}"), hat=str(val(f"E{r144}") or ""),
        taze_tursu_sinifi=str(val(f"E{r145}") or ""), ambalaj_hacmi=d(f"E{r146}"), suzme_kg=d(f"E{r136}"),
        mal_kabul_miktar_kg=d(f"I{r104}"), mal_kabul_fire=d(f"J{r104}"),
        pazarlama_yonetim_uygula=not (_sabit_sifir(ws_f, f"P{r118}") and _sabit_sifir(ws_f, f"P{r119}")),
    )
    girdi = UrunGirdisi(kod=str(val("D6")).strip(), ad=str(val("E6") or "").strip(), recete=recete, uretim=uretim)

    bek = {}
    for ad, r in [("P100", r100), ("P103", r103), ("P104", r104), ("P105", r105), ("P106", r106), ("P107", r107),
                  ("P108", r108), ("P109", r109), ("P110", r110), ("P111", r111), ("P112", r112), ("P113", r113),
                  ("P114", r114), ("P116", r116), ("P118", r118), ("P119", r119), ("P120", r120), ("P122", r122),
                  ("P124", r124), ("P125", r124 + 1), ("P130", r130), ("P131", r130 + 1), ("P132", r130 + 2),
                  ("P137", r136 + 1), ("P138", r136 + 2), ("P143", r143), ("P145", r145), ("P146", r146), ("P147", r147)]:
        bek[ad] = D(val(f"P{r}"))
    for ad, r in [("100", r100), ("103", r103), ("107", r107), ("118", r118), ("119", r119), ("124", r124)]:
        bek["R" + ad], bek["S" + ad] = D(val(f"R{r}")), D(val(f"S{r}"))
    return girdi, p, bek
```

- [ ] **Step 4: Çalıştır, geçer** — Expected: 5 passed (Excel mevcutsa). Başarısız olursa hangi etiketin eşleşmediğini `KeyError` söyler; etiketi Excel'deki gerçek metne göre düzelt (Türkçe karakter ve boşluk farkları olabilir).

- [ ] **Step 5: Commit** — `git commit -m "feat: Excel okuyucu (girdiler + beklenen değerler)"`

---

### Task 11: Parite raporu scripti (`scripts/excel_parite_raporu.py`)

**Files:**
- Create: `scripts/excel_parite_raporu.py`

**Interfaces:**
- Consumes: `excel_okuyucu.*`, `gider_dagitim.oranlari_hesapla`, `hesapla.urun_maliyeti`
- Produces: `karsilastir(yol) -> list[dict]` (sayfa, alan, excel, motor, fark); çalıştırıldığında `docs/parite-raporu-<tarih>.md` yazar (`.gitignore`'da) ve özeti ekrana basar.

Ayrıca Gider Dağıtım oranlarını Excel'in G/F sütunlarıyla karşılaştırır (G4, G13, G18, G27, F7:F9, F21:F23, F30:F37, F41:F48, F52:F59, F70:F91, G70:G91).

- [ ] **Step 1: Script'i yaz**

```python
# scripts/excel_parite_raporu.py
"""Motor sonuçlarını Excel'deki değerlerle sayfa sayfa karşılaştırır, farkları raporlar.
Kullanım: .\.venv\Scripts\python scripts/excel_parite_raporu.py ["Fiyat Çalışma - 2026-2027 - Berrak.xlsx"]"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiyat_motoru.excel_okuyucu import excel_ac, havuzlari_oku, malzemeleri_oku, urun_oku, urun_sayfalarini_listele
from fiyat_motoru.gider_dagitim import anahtar, oranlari_hesapla
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.para import D, TOLERANS

ALAN_ESLEME = {   # beklenen anahtarı -> MaliyetSonucu'ndan değer alan fonksiyon
    "P100": lambda r: r.malzeme_toplami, "P103": lambda r: r.direkt_iscilik_toplami, "P107": lambda r: r.gug_toplami,
    "P104": lambda r: r.satirlar_by("Mal Kabul ve Fermantasyon Giderleri"),
    "P105": lambda r: r.satirlar_by("Dolum Doğrudan İşçilik Giderleri"),
    "P106": lambda r: r.satirlar_by("Etiketleme İşçilik Giderleri"),
    "P108": lambda r: r.satirlar_by("Endirekt İşçilik Giderleri"),
    "P109": lambda r: r.satirlar_by("Mal Kabul ve Fermantasyon Genel Üretim Giderleri"),
    "P110": lambda r: r.satirlar_by("Elektrik Giderleri"), "P111": lambda r: r.satirlar_by("Doğalgaz Giderleri"),
    "P112": lambda r: r.satirlar_by("Amortisman Giderleri"), "P113": lambda r: r.satirlar_by("Diğer Genel Üretim Giderleri"),
    "P114": lambda r: r.uretim_gideri_toplami, "P116": lambda r: r.toplam_birim_maliyet,
    "P118": lambda r: r.pazarlama_gideri, "P119": lambda r: r.yonetim_gideri, "P120": lambda r: r.diger_giderler_toplami,
    "P122": lambda r: r.giydirilmis_maliyet, "P124": lambda r: r.finansman["TL"], "P125": lambda r: r.finansman["USD"],
    "P130": lambda r: r.finansman_dahil_maliyet_tl, "P131": lambda r: r.doviz_maliyet["USD"], "P132": lambda r: r.doviz_maliyet["EUR"],
    "P137": lambda r: r.satis_fiyati_tl, "P138": lambda r: r.satis_fiyati_doviz["USD"], "P143": lambda r: r.suzme_kg_fiyati_tl,
    "P145": lambda r: r.teklifler_usd[0], "P146": lambda r: r.teklifler_usd[1], "P147": lambda r: r.teklifler_usd[2],
}


def _satir_tutari(r, kalem):
    return next(s.tutar for s in r.satirlar if s.kalem == kalem)


def gider_dagitim_farklari(wb_v, oranlar):
    ws = wb_v["Gider Dağıtım"]
    g = lambda a: D(ws[a].value)
    kontrol = [("G4", oranlar.dolum_iscilik_sn), ("G13", oranlar.etiket_iscilik_sn),
               ("G18", oranlar.endirekt_iscilik_sn), ("G27", oranlar.diger_gug_sn)]
    kontrol += [(f"F{r}", oranlar.mal_kabul_iscilik_kg[anahtar(ws[f"C{r}"].value)]) for r in range(7, 10)]
    kontrol += [(f"F{r}", oranlar.mal_kabul_gug_kg[anahtar(ws[f"C{r}"].value)]) for r in range(21, 24)]
    for blok, tablo in [(range(30, 38), oranlar.elektrik_sn), (range(41, 49), oranlar.dogalgaz_sn), (range(52, 60), oranlar.amortisman_sn)]:
        kontrol += [(f"F{r}", tablo[anahtar(ws[f"A{r}"].value)]) for r in blok]
    for r in range(70, 92):
        h = D(ws[f"B{r}"].value)
        kontrol += [(f"F{r}", oranlar.pazarlama_adet[h]), (f"G{r}", oranlar.yonetim_adet[h])]
    return [{"sayfa": "Gider Dağıtım", "alan": a, "excel": g(a), "motor": m, "fark": g(a) - m} for a, m in kontrol if abs(g(a) - m) >= TOLERANS]


def karsilastir(yol: Path) -> tuple[list[dict], dict[str, list[str]]]:
    wb_f, wb_v = excel_ac(yol)
    malzemeler = malzemeleri_oku(wb_v)
    oranlar = oranlari_hesapla(havuzlari_oku(wb_v))
    farklar = gider_dagitim_farklari(wb_v, oranlar)
    uyarilar = {}
    for ad in urun_sayfalarini_listele(wb_v):
        try:
            girdi, p, bek = urun_oku(wb_f[ad], wb_v[ad])
            r = urun_maliyeti(girdi, malzemeler, oranlar, p)
        except Exception as e:  # sayfa şablondan sapmış olabilir; raporda görünsün
            farklar.append({"sayfa": ad, "alan": "HATA", "excel": None, "motor": None, "fark": str(e)})
            continue
        r.satirlar_by = lambda kalem, _r=r: _satir_tutari(_r, kalem)
        uyarilar[ad] = r.uyarilar
        for alan, al in ALAN_ESLEME.items():
            try:
                motor = al(r)
            except (StopIteration, KeyError, IndexError):
                motor = None
            excel = bek.get(alan)
            if motor is None or abs(excel - motor) >= TOLERANS:
                farklar.append({"sayfa": ad, "alan": alan, "excel": excel, "motor": motor, "fark": None if motor is None else excel - motor})
        for yk in ("R100", "R103", "R107", "R118", "R119", "R124"):
            kalem_grubu = {"R100": "malzeme", "R103": "direkt_iscilik", "R107": "gug", "R124": "finansman"}.get(yk)
            if kalem_grubu:
                motor = sum((s.maliyet_yuzdesi for s in r.satirlar if s.grup == kalem_grubu), Decimal(0))
                if abs(bek[yk] - motor) >= TOLERANS:
                    farklar.append({"sayfa": ad, "alan": yk, "excel": bek[yk], "motor": motor, "fark": bek[yk] - motor})
    return farklar, uyarilar


def main():
    yol = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Fiyat Çalışma - 2026-2027 - Berrak.xlsx")
    farklar, uyarilar = karsilastir(yol)
    sayfalar = sorted({f["sayfa"] for f in farklar})
    rapor = Path("docs") / f"parite-raporu-{date.today():%m-%d-%Y}.md"
    with rapor.open("w", encoding="utf-8") as f:
        f.write(f"# Excel parite raporu - {date.today():%d.%m.%Y}\n\nKaynak: `{yol.name}`\n\n")
        f.write(f"Farklı sayfa sayısı: **{len(sayfalar)}**, toplam fark: **{len(farklar)}**\n\n")
        f.write("| Sayfa | Alan | Excel | Motor | Fark |\n|---|---|---|---|---|\n")
        for d in farklar:
            f.write(f"| {d['sayfa']} | {d['alan']} | {d['excel']} | {d['motor']} | {d['fark']} |\n")
        f.write("\n## Uyarılar (fiyatsız malzeme vb.)\n\n")
        for ad, u in uyarilar.items():
            if u:
                f.write(f"- **{ad}**: " + "; ".join(u) + "\n")
    print(f"farklı sayfa: {len(sayfalar)} / toplam fark: {len(farklar)} -> {rapor}")
    for s in sayfalar:
        print("  ", s, [d["alan"] for d in farklar if d["sayfa"] == s][:8])


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Çalıştır**

Run: `.\.venv\Scripts\python scripts/excel_parite_raporu.py`
Expected: `farklı sayfa: N / toplam fark: M -> docs/parite-raporu-MM-DD-YYYY.md`. İlk çalıştırmada fark çıkması normaldir.

- [ ] **Step 3: Farkları sınıflandır** — Raporu aç; her farklı sayfa için nedeni belirle:
  - Motor hatası (formül yanlış anlaşılmış) → ilgili Task'ın testini genişlet, düzelt.
  - Excel'in kendi sapması (spec bölüm 3: sabit 0 hücreler, `053` şablon sapması, kopya sayfalar, `001`'deki sağ-blok farkı sol bloğu etkilemez) → Task 12'deki `BILINEN_ISTISNALAR`'a sayfa + alan + açıklama olarak ekle.
  - Belirsiz → `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` bölüm 8'e soru olarak ekle.

- [ ] **Step 4: Commit** — `git add scripts/ && git commit -m "feat: Excel parite raporu"`

---

### Task 12: Altın referans testi (`test_excel_paritesi.py`)

**Files:**
- Create: `tests/test_excel_paritesi.py`

**Interfaces:**
- Consumes: `scripts.excel_parite_raporu.karsilastir`

- [ ] **Step 1: Testi yaz**

```python
# tests/test_excel_paritesi.py
"""Altın referans: motor, Excel'in 69 ürün sayfasında kuruşu kuruşuna aynı sonucu vermeli.
Bilinen Excel sapmaları (spec bölüm 3) BILINEN_ISTISNALAR'da açıklamasıyla listelenir."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.excel_parite_raporu import karsilastir

# (sayfa, alan): açıklama  — Task 11 Step 3'te doldurulur. Her kayıt bir gerekçe taşımak zorunda.
BILINEN_ISTISNALAR: dict[tuple[str, str], str] = {
    # ("053", "P118"): "sayfa şablondan sapmış, satırlar 10 kaymış, pazarlama VLOOKUP aralığı farklı",
}


@pytest.fixture(scope="module")
def farklar(excel_yolu):
    f, _ = karsilastir(excel_yolu)
    return f


def test_gider_dagitim_paritesi(farklar):
    assert [d for d in farklar if d["sayfa"] == "Gider Dağıtım"] == []


def test_urun_sayfalari_paritesi(farklar):
    beklenmeyen = [d for d in farklar if d["sayfa"] != "Gider Dağıtım" and (d["sayfa"], d["alan"]) not in BILINEN_ISTISNALAR]
    assert beklenmeyen == [], "\n".join(f"{d['sayfa']} {d['alan']}: excel={d['excel']} motor={d['motor']}" for d in beklenmeyen[:30])


def test_istisnalar_hala_gecerli(farklar):
    """Bir istisna artık fark üretmiyorsa listeden çıkarılmalı (ölü istisna birikmesin)."""
    mevcut = {(d["sayfa"], d["alan"]) for d in farklar}
    olu = [k for k in BILINEN_ISTISNALAR if k not in mevcut]
    assert olu == [], f"artık fark üretmeyen istisnalar: {olu}"
```

- [ ] **Step 2: Çalıştır** — Run: `.\.venv\Scripts\python -m pytest tests/test_excel_paritesi.py -v`
Expected: `test_gider_dagitim_paritesi` PASS; `test_urun_sayfalari_paritesi` Task 11 Step 3'te istisnalar doldurulduktan ve motor hataları düzeltildikten sonra PASS.

- [ ] **Step 3: Tüm testleri çalıştır** — Run: `.\.venv\Scripts\python -m pytest -v` — Expected: tümü passed, Excel yoksa parite testleri skipped.

- [ ] **Step 4: Sonuç özetini spec'e işle** — `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` bölüm 6'nın altına: kaç sayfa birebir uyuştu, istisna listesi ve her birinin gerekçesi, muhasebe direktörüne sorulacak yeni sorular.

- [ ] **Step 5: Commit** — `git add tests/test_excel_paritesi.py docs/ && git commit -m "test: Excel altın referans paritesi"`

---

## Self-review notları

- **Spec kapsamı:** F1 (T3), F2-F3 (T4), F4+F8 (T5), F5-F7 (T6), F9-F10 (T7), F11-F13 (T8), orkestrasyon (T9), Excel okuma (T10), 67 ürün paritesi ve bilinen sapmalar (T11-T12). Spec bölüm 2'deki "ek analizler" (geçen yıl, ambalaj trendi) Faz 5, bu planda yok. Fire kuralı önceliği (spec bölüm 4) Faz 2'nin konusu; Faz 1 reçetedeki fire değerini aynen kullanır.
- **Tip tutarlılığı:** `anahtar()` casefold tablo anahtarları T5'te üretilir, T6'da aynı fonksiyonla aranır. `GiderOranlari.pazarlama_adet` anahtarı `Decimal` hacim; T6 `u.ambalaj_hacmi` de `Decimal` → `Decimal(370) == Decimal("370.0")` eşittir, sözlük araması çalışır (hash eşit).
- **Bilinen risk:** T10'daki etiket metinleri Excel'deki gerçek metinle (boşluk, Türkçe karakter) birebir olmalı; ilk çalıştırmada `KeyError` çıkarsa etiket düzeltilir, mantık değişmez.
- **Yurtdışı yüzdeleri** test edildi ama Excel'de hiçbir sayfa Yurtdışı değil; parite yalnızca Yurtiçi'ni doğrular.
