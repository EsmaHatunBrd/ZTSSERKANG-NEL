# Faz 2: Backend (Veri, Servisler, API, Import) - Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faz 1 motorunun üstüne; append-only versiyonlu veri modeli, iş kurallarını taşıyan servisler, FastAPI ile JSON API ve mevcut Fiyat Çalışma Excel'ini bütünüyle içe aktaran bir import kurmak; Excel'den yüklenen verinin servis katmanından geçince Excel ile aynı maliyeti verdiğini testle kanıtlamak.

**Architecture:** `backend/api` (FastAPI router, yalnız HTTP) → `backend/servisler` (iş kuralı) → `backend/depo` (SQLAlchemy 2, SQLite) ve `fiyat_motoru` (Faz 1, değişmez). Tutarlar veritabanında TEXT olarak saklanan `Decimal` (float'a hiç düşmez). Fiyat, parametre ve fire kuralı tabloları append-only; "geçerli değer" = `gecerlilik_basi <= tarih` olan en yeni kayıt. Her kaydedilen hesap, girdi ve sonucun JSON snapshot'ını taşır.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy ≥ 2.0, Pydantic ≥ 2, SQLite (WAL), openpyxl, pytest + httpx (TestClient).

**Spec:** `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` (bölüm 1-4, 6) ve `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` (bölüm 2-4).

## Global Constraints

- Para ve oran alanları `Decimal`; veritabanında `ParaTipi` (TEXT) ile saklanır, `Numeric`/`Float` kullanılmaz.
- Append-only tablolar (`parametre_degeri`, `malzeme_fiyati`, `fire_kurali`) için `UPDATE`/`DELETE` yazan servis fonksiyonu olmaz; geri alma = yeni kayıt.
- `fiyat_motoru/` değiştirilmez. Motorun dataclass'ları (`Malzeme`, `ReceteSatiri`, `Parametreler`, `UretimBilgisi`, `GiderHavuzlari`, `AmbalajSinifi`, `UrunGirdisi`, `MaliyetSonucu`) servislerin dönüş/giriş tipleridir.
- `senaryo.tur == "gerceklesen"` ise enflasyon 0 uygulanır (spec: enflasyon yalnızca fiyat çalışmasında).
- Router'da SQL/ORM sorgusu yok; serviste `Request`/`Response` yok. Her servis fonksiyonunun ilk parametresi `Session`.
- API: tüm `Decimal` alanlar JSON'da **string**; hata gövdesi `{"hata": str, "mesaj": str, "alanlar": dict}`; liste uçları `?sayfa=1&boyut=50` ve `{"kayitlar": [...], "toplam": N}`.
- Kimlik doğrulama yok; `olusturan` alanı `X-Kullanici` başlığından, yoksa `"sistem"`.
- Kurumsal veri (Excel) test fikstürü olarak yalnızca yerel diskte; `veri/` ve `*.db` `.gitignore`'da.
- Dosya adlandırma: Python modülleri import kuralına uyar; yeni **belge** dosyaları `MM-DD-YYYY-açıklama`.
- Git yok (kullanıcı istemedi); commit adımları atlanır.
- Kod tanımlayıcıları Türkçe, Türkçe karakter kullanılmadan.
- Migrasyon aracı (Alembic) bu fazda yok; şema `Base.metadata.create_all` ile kurulur. Faz 3'te eklenecek.

---

## Dosya Yapısı

```
backend/
├── __init__.py
├── ayarlar.py                 # VERITABANI_URL, EXCEL varsayılan yolu
├── uygulama.py                # FastAPI app fabrikası, router kayıtları, hata işleyici
├── depo/
│   ├── __init__.py
│   ├── veritabani.py          # engine, SessionLocal, Base, ParaTipi, oturum_ver()
│   └── modeller.py            # tüm ORM tabloları
├── servisler/
│   ├── __init__.py
│   ├── hatalar.py             # BulunamadiHatasi, DogrulamaHatasi
│   ├── donusum.py             # motor dataclass <-> dict (snapshot), Decimal<->str
│   ├── parametre_servisi.py
│   ├── fiyat_servisi.py
│   ├── gider_servisi.py
│   ├── recete_servisi.py
│   ├── hesap_servisi.py
│   ├── teklif_servisi.py
│   └── import_servisi.py
├── api/
│   ├── __init__.py
│   ├── bagimliliklar.py       # oturum ve kullanıcı dependency'leri
│   ├── semalar.py             # Pydantic giriş/çıkış modelleri
│   ├── senaryolar.py
│   ├── parametreler.py
│   ├── malzemeler.py
│   ├── gider.py
│   ├── urunler.py             # ürün, reçete, hesapla, hesaplar
│   ├── teklifler.py
│   ├── fire.py
│   ├── import_.py
│   └── disa_aktar.py
└── tohum.py                   # parametre tanımları + fire varsayılanları
tests/backend/
├── __init__.py
├── conftest.py                # bellek içi SQLite oturumu, TestClient, tohumlu senaryo
├── test_depo.py
├── test_parametre_servisi.py
├── test_fiyat_servisi.py
├── test_gider_servisi.py
├── test_recete_servisi.py
├── test_hesap_servisi.py
├── test_teklif_servisi.py
├── test_import_servisi.py
├── test_api.py
└── test_uctan_uca_excel.py    # Excel → import → servis hesabı == Excel değeri
```

---

### Task 1: Backend iskeleti, veritabanı ve `ParaTipi`

**Files:**
- Modify: `pyproject.toml` (bağımlılıklar), `.gitignore` (+ `veri/`, `*.db`)
- Create: `backend/__init__.py`, `backend/ayarlar.py`, `backend/depo/__init__.py`, `backend/depo/veritabani.py`, `tests/backend/__init__.py`, `tests/backend/conftest.py`, `tests/backend/test_depo.py`

**Interfaces:**
- Produces: `veritabani.Base`, `veritabani.ParaTipi`, `veritabani.motor_olustur(url) -> Engine`, `veritabani.oturum_fabrikasi(engine) -> sessionmaker`, `veritabani.oturum_ver()` (FastAPI dependency, Task 10), `ayarlar.Ayarlar` (`veritabani_url`, `excel_yolu`).

- [ ] **Step 1: Bağımlılıkları ekle**

`pyproject.toml` içindeki `dependencies` ve `test` satırlarını şöyle değiştir:
```toml
dependencies = ["openpyxl>=3.1", "fastapi>=0.115", "uvicorn>=0.30", "sqlalchemy>=2.0", "pydantic>=2.7", "python-multipart>=0.0.9"]

[project.optional-dependencies]
test = ["pytest>=8", "httpx>=0.27"]
```
ve `[tool.setuptools.packages.find]` satırını `include = ["fiyat_motoru*", "backend*"]` yap. `.gitignore`'a `veri/` ve `*.db` ekle. Kur: `.\.venv\Scripts\python -m pip install -e ".[test]"`.

- [ ] **Step 2: Başarısız test**

```python
# tests/backend/test_depo.py
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column
from backend.depo.veritabani import Base, ParaTipi, motor_olustur, oturum_fabrikasi


class _Deneme(Base):
    __tablename__ = "_deneme"
    id: Mapped[int] = mapped_column(primary_key=True)
    tutar: Mapped[Decimal] = mapped_column(ParaTipi)


def test_para_tipi_decimal_kaybetmez():
    engine = motor_olustur("sqlite://")
    Base.metadata.create_all(engine)
    with oturum_fabrikasi(engine)() as s:
        s.add(_Deneme(tutar=Decimal("0.1")))
        s.add(_Deneme(tutar=Decimal("38.130789359652750000001")))
        s.commit()
        degerler = [d.tutar for d in s.scalars(select(_Deneme).order_by(_Deneme.id))]
    assert degerler == [Decimal("0.1"), Decimal("38.130789359652750000001")]
    assert all(isinstance(d, Decimal) for d in degerler)


def test_para_tipi_none():
    engine = motor_olustur("sqlite://")
    Base.metadata.create_all(engine)
    with oturum_fabrikasi(engine)() as s:
        s.add(_Deneme(tutar=None)); s.commit()
        assert s.scalars(select(_Deneme)).first().tutar is None
```

- [ ] **Step 3: Çalıştır, başarısız** — `.\.venv\Scripts\python -m pytest tests/backend/test_depo.py -v` → `ModuleNotFoundError: backend`

- [ ] **Step 4: Uygulama**

```python
# backend/__init__.py
"""Fiyat çalışması backend: depo (SQLAlchemy), servisler (iş kuralı), api (FastAPI)."""
```
```python
# backend/ayarlar.py
"""Ortam değişkenlerinden ayarlar. Varsayılanlar tek kullanıcılı yerel kurulum içindir."""
import os
from dataclasses import dataclass
from pathlib import Path

PROJE_KOKU = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Ayarlar:
    veritabani_url: str = os.environ.get("VERITABANI_URL", f"sqlite:///{PROJE_KOKU / 'veri' / 'fiyat.db'}")
    excel_yolu: Path = Path(os.environ.get("EXCEL_YOLU", PROJE_KOKU / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"))


AYARLAR = Ayarlar()
```
```python
# backend/depo/__init__.py
```
```python
# backend/depo/veritabani.py
"""Engine, oturum ve Decimal'i kayıpsız saklayan ParaTipi."""
from decimal import Decimal
from pathlib import Path
from sqlalchemy import String, TypeDecorator, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from ..ayarlar import AYARLAR


class Base(DeclarativeBase):
    pass


class ParaTipi(TypeDecorator):
    """Decimal'i TEXT olarak saklar; SQLite'ın float'a düşürmesini engeller."""
    impl = String(48)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(Decimal(value))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


def motor_olustur(url: str = AYARLAR.veritabani_url) -> Engine:
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    bellek_ici = url == "sqlite://"
    engine = create_engine(url, connect_args={"check_same_thread": False},
                           poolclass=StaticPool if bellek_ici else None)

    @event.listens_for(engine, "connect")
    def _pragmalar(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if not bellek_ici:
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()
    return engine


def oturum_fabrikasi(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


_ENGINE: Engine | None = None
_SESSION: sessionmaker | None = None


def oturum_ver():
    """FastAPI dependency: istek başına bir oturum; router commit/rollback'i burada."""
    global _ENGINE, _SESSION
    if _SESSION is None:
        _ENGINE = motor_olustur()
        Base.metadata.create_all(_ENGINE)
        _SESSION = oturum_fabrikasi(_ENGINE)
    s = _SESSION()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
```
```python
# tests/backend/__init__.py
```
```python
# tests/backend/conftest.py
import pytest
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi


@pytest.fixture
def oturum():
    engine = motor_olustur("sqlite://")
    Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    yield s
    s.close()
```

- [ ] **Step 5: Çalıştır, geçer** — 2 passed. Tüm süit: `.\.venv\Scripts\python -m pytest -q` — Faz 1 testleri etkilenmemeli.

---

### Task 2: ORM modelleri (`backend/depo/modeller.py`)

**Files:**
- Create: `backend/depo/modeller.py`; Modify: `tests/backend/test_depo.py` (ek test)

**Interfaces:**
- Produces (tablolar; tasarım bölüm 2 ile birebir). Ortak: `id` PK int, `olusturma_zamani` datetime default now, `olusturan` str default "sistem".

```python
Sezon(ad, baslangic: date, bitis: date)
Senaryo(sezon_id, tur: "fiyat_calismasi"|"gerceklesen", ad, aciklama)
Parametre(anahtar unique, aciklama, birim)
ParametreDegeri(parametre_id, senaryo_id, kapsam_tipi: "genel"|"urun", kapsam_id: int|None, deger: Decimal, gecerlilik_basi: date, neden)
Malzeme(kod unique, ad, tip, birim, para_birimi, zs, aktif=True)
MalzemeFiyati(malzeme_id, senaryo_id, fiyat: Decimal, para_birimi, gecerlilik_basi: date, kaynak, neden)
GiderHavuzu(senaryo_id, kod, ad, toplam_tutar: Decimal, baz_tipi: "saniye"|"kg"|"adet", baz_miktar: Decimal|None)   # unique (senaryo_id, kod)
DagitimAnahtari(gider_havuzu_id, alt_kalem, pay_orani: Decimal, baz_miktar: Decimal)
AmbalajSinifi(senaryo_id, ad, hacim: Decimal, uretim_adedi: Decimal, katsayi: Decimal)
Urun(kod unique, ad, ambalaj_hacmi: Decimal, hat, taze_tursu_sinifi, suzme_kg: Decimal, pazar="Yurtiçi", aktif=True)
UretimHedefi(urun_id, senaryo_id, vardiya_uretim_adedi, dolum_personel, etiketleme_adedi, etiket_personel, mal_kabul_miktar_kg, mal_kabul_fire, pazarlama_yonetim_uygula: bool)  # unique (urun_id, senaryo_id)
Recete(urun_id, senaryo_id, versiyon: int, kaynak, aktif: bool)  # unique (urun_id, senaryo_id, versiyon)
ReceteSatiri(recete_id, sira: int, malzeme_kodu: str, ad, miktar: Decimal, birim, fire_override: Decimal|None, dugum_tipi="yaprak")
FireKurali(senaryo_id, kapsam_tipi: "tip"|"grup"|"malzeme", kapsam_deger: str, oran: Decimal, oncelik: int, gecerlilik_basi: date, neden)
MalzemeGrubu(ad unique); MalzemeGrubuUyesi(grup_id, malzeme_kodu)
MaliyetHesabi(urun_id, senaryo_id, hesap_tarihi: date, girdi_snapshot: JSON, sonuc_snapshot: JSON, uyarilar: JSON)
Teklif(maliyet_hesabi_id, tur_no: int, kar_orani: Decimal, fiyat_tl, fiyat_usd, fiyat_eur, musteri, durum="taslak", notu)
SatisGecmisi(urun_id, musteri, tarih: date, fiyat: Decimal, para_birimi, adet: Decimal)
DegisiklikKaydi(tablo, kayit_id, islem, eski: JSON, yeni: JSON, kullanici, zaman)
```
`ReceteSatiri.malzeme_kodu` bilerek string: reçetede fiyat listesinde olmayan ara mamul kodları da bulunur (motor bunları 0 + uyarı yapar).

- [ ] **Step 1: Test ekle** (`tests/backend/test_depo.py` sonuna)

```python
from datetime import date
from backend.depo import modeller as m


def test_tablolar_olusur_ve_iliskiler(oturum):
    sezon = m.Sezon(ad="2026-2027", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31))
    oturum.add(sezon); oturum.flush()
    sen = m.Senaryo(sezon_id=sezon.id, tur="fiyat_calismasi", ad="Berrak 2026-2027")
    oturum.add(sen); oturum.flush()
    par = m.Parametre(anahtar="kur.USD", aciklama="USD kuru", birim="TL")
    oturum.add(par); oturum.flush()
    oturum.add(m.ParametreDegeri(parametre_id=par.id, senaryo_id=sen.id, kapsam_tipi="genel",
                                 deger=Decimal("50"), gecerlilik_basi=date(2026, 6, 1), neden="bütçe"))
    urun = m.Urun(kod="U1", ad="Ürün", ambalaj_hacmi=Decimal(370), hat="Niko", taze_tursu_sinifi="Turşu/Turşu", suzme_kg=Decimal("0.18"))
    oturum.add(urun); oturum.flush()
    rec = m.Recete(urun_id=urun.id, senaryo_id=sen.id, versiyon=1, kaynak="elle", aktif=True)
    oturum.add(rec); oturum.flush()
    oturum.add(m.ReceteSatiri(recete_id=rec.id, sira=1, malzeme_kodu="KAV", ad="Kavanoz", miktar=Decimal(1), birim="AD", fire_override=Decimal("0.02")))
    oturum.commit()
    assert rec.satirlar[0].fire_override == Decimal("0.02")
    assert sen.sezon.ad == "2026-2027"
    assert {t for t in m.Base.metadata.tables} >= {"sezon", "senaryo", "parametre", "parametre_degeri", "malzeme", "malzeme_fiyati",
        "gider_havuzu", "dagitim_anahtari", "ambalaj_sinifi", "urun", "uretim_hedefi", "recete", "recete_satiri", "fire_kurali",
        "malzeme_grubu", "malzeme_grubu_uyesi", "maliyet_hesabi", "teklif", "satis_gecmisi", "degisiklik_kaydi"}
```

- [ ] **Step 2: Çalıştır, başarısız** — `ImportError: cannot import name 'modeller'`

- [ ] **Step 3: Uygulama** — `backend/depo/modeller.py`: her tablo için `class X(Base, Ortak)` ile Interfaces'teki alanlar. İskelet:

```python
# backend/depo/modeller.py
"""ORM tabloları. Para/oran alanları ParaTipi; fiyat, parametre değeri ve fire kuralı append-only."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .veritabani import Base, ParaTipi


class Ortak:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    olusturma_zamani: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    olusturan: Mapped[str] = mapped_column(String(64), default="sistem")


class Sezon(Base, Ortak):
    __tablename__ = "sezon"
    ad: Mapped[str] = mapped_column(String(32), unique=True)
    baslangic: Mapped[date] = mapped_column(Date)
    bitis: Mapped[date] = mapped_column(Date)


class Senaryo(Base, Ortak):
    __tablename__ = "senaryo"
    sezon_id: Mapped[int] = mapped_column(ForeignKey("sezon.id"))
    tur: Mapped[str] = mapped_column(String(20))            # fiyat_calismasi | gerceklesen
    ad: Mapped[str] = mapped_column(String(100))
    aciklama: Mapped[str | None] = mapped_column(String(500))
    sezon: Mapped[Sezon] = relationship()


class Parametre(Base, Ortak):
    __tablename__ = "parametre"
    anahtar: Mapped[str] = mapped_column(String(64), unique=True)
    aciklama: Mapped[str | None] = mapped_column(String(200))
    birim: Mapped[str | None] = mapped_column(String(16))


class ParametreDegeri(Base, Ortak):
    __tablename__ = "parametre_degeri"
    parametre_id: Mapped[int] = mapped_column(ForeignKey("parametre.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    kapsam_tipi: Mapped[str] = mapped_column(String(8), default="genel")   # genel | urun
    kapsam_id: Mapped[int | None] = mapped_column(Integer)
    deger: Mapped[Decimal] = mapped_column(ParaTipi)
    gecerlilik_basi: Mapped[date] = mapped_column(Date)
    neden: Mapped[str | None] = mapped_column(String(300))
    parametre: Mapped[Parametre] = relationship()


class Malzeme(Base, Ortak):
    __tablename__ = "malzeme"
    kod: Mapped[str] = mapped_column(String(32), unique=True)
    ad: Mapped[str] = mapped_column(String(200))
    tip: Mapped[str | None] = mapped_column(String(64))
    birim: Mapped[str | None] = mapped_column(String(8))
    para_birimi: Mapped[str | None] = mapped_column(String(4))
    zs: Mapped[str | None] = mapped_column(String(1))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)


class MalzemeFiyati(Base, Ortak):
    __tablename__ = "malzeme_fiyati"
    malzeme_id: Mapped[int] = mapped_column(ForeignKey("malzeme.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    fiyat: Mapped[Decimal] = mapped_column(ParaTipi)
    para_birimi: Mapped[str | None] = mapped_column(String(4))
    gecerlilik_basi: Mapped[date] = mapped_column(Date)
    kaynak: Mapped[str] = mapped_column(String(16), default="elle")
    neden: Mapped[str | None] = mapped_column(String(300))
    malzeme: Mapped[Malzeme] = relationship()
```
Kalan tablolar (`GiderHavuzu` + `anahtarlar: relationship(DagitimAnahtari, cascade="all, delete-orphan")`, `DagitimAnahtari`, `AmbalajSinifi`, `Urun`, `UretimHedefi` (`UniqueConstraint("urun_id","senaryo_id")`), `Recete` (`UniqueConstraint("urun_id","senaryo_id","versiyon")`, `satirlar: relationship(ReceteSatiri, order_by="ReceteSatiri.sira", cascade="all, delete-orphan")`), `ReceteSatiri`, `FireKurali`, `MalzemeGrubu` (`uyeler` relationship), `MalzemeGrubuUyesi`, `MaliyetHesabi` (`girdi_snapshot`, `sonuc_snapshot`, `uyarilar`: `mapped_column(JSON)`), `Teklif`, `SatisGecmisi`, `DegisiklikKaydi`) aynı kalıpla, Interfaces'teki alan ve tiplerle yazılır. `Teklif.notu` sütun adı `notu` (Python'da `not` ayrılmış kelime).

- [ ] **Step 4: Çalıştır, geçer** — 3 passed.

---

### Task 3: Hata tipleri, dönüşüm ve parametre servisi

**Files:**
- Create: `backend/servisler/__init__.py`, `backend/servisler/hatalar.py`, `backend/servisler/donusum.py`, `backend/servisler/parametre_servisi.py`, `tests/backend/test_parametre_servisi.py`

**Interfaces:**
- `hatalar.BulunamadiHatasi(Exception)`, `hatalar.DogrulamaHatasi(Exception)` — ikisi de `mesaj: str`, `alanlar: dict` taşır.
- `donusum.decimal_str(obj)`: dict/list/dataclass içindeki `Decimal` → str, `date` → ISO (JSON snapshot için); `donusum.dataclass_to_dict(dc)`.
- `parametre_servisi.gecerli_parametreler(s, senaryo_id, tarih, urun_id=None) -> Parametreler`; `parametre_servisi.deger_ekle(s, senaryo_id, anahtar, deger, gecerlilik_basi, neden, kapsam_tipi="genel", kapsam_id=None, olusturan="sistem") -> ParametreDegeri`; `parametre_servisi.gecmis(s, senaryo_id, anahtar) -> list[ParametreDegeri]`; `parametre_servisi.gecerli_degerler(s, senaryo_id, tarih, urun_id=None) -> dict[str, Decimal]`.

Anahtar sözleşmesi: `enflasyon`, `kur.<PB>`, `faiz.<PB>`, `stok_ay.<PB>`, `satis_kar`, `teklif_kar.<n>`, `vardiya_saati`. Eksik `enflasyon`/`satis_kar`/`vardiya_saati` → `DogrulamaHatasi`.

Geçerli değer kuralı: `gecerlilik_basi <= tarih`, sıralama `gecerlilik_basi DESC, id DESC`, anahtar başına ilk; `kapsam_tipi="urun"` ve `kapsam_id=urun_id` olan kayıt, `genel` olanı ezer.

- [ ] **Step 1: Test**

```python
# tests/backend/test_parametre_servisi.py
from datetime import date
from decimal import Decimal
import pytest
from backend.depo import modeller as m
from backend.servisler import parametre_servisi as ps
from backend.servisler.hatalar import DogrulamaHatasi


@pytest.fixture
def senaryo(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    for a in ["enflasyon", "kur.USD", "kur.EUR", "faiz.TL", "stok_ay.TL", "faiz.USD", "stok_ay.USD", "satis_kar", "teklif_kar.1", "teklif_kar.2", "vardiya_saati"]:
        oturum.add(m.Parametre(anahtar=a))
    oturum.flush()
    return sen


def _tohum(oturum, sen):
    t = date(2026, 6, 1)
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"),
                 ("faiz.USD", "0.06"), ("stok_ay.USD", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"), ("teklif_kar.2", "0.17"), ("vardiya_saati", "7.5")]:
        ps.deger_ekle(oturum, sen.id, a, Decimal(v), t, "tohum")


def test_gecerli_parametreler_motor_tipi(oturum, senaryo):
    _tohum(oturum, senaryo)
    p = ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 10, 21))
    assert p.enflasyon == Decimal("0.25") and p.kurlar == {"USD": Decimal(50), "EUR": Decimal(60)}
    assert p.faiz_oranlari["TL"] == Decimal("0.4") and p.stok_sureleri_ay["USD"] == Decimal(6)
    assert p.teklif_kar_oranlari == (Decimal("0.2"), Decimal("0.17")) and p.vardiya_saati == Decimal("7.5")


def test_yeni_deger_eskiyi_silmez_gecmiste_kalir(oturum, senaryo):
    _tohum(oturum, senaryo)
    ps.deger_ekle(oturum, senaryo.id, "kur.USD", Decimal(55), date(2026, 9, 1), "kur güncellendi")
    assert ps.gecerli_degerler(oturum, senaryo.id, date(2026, 8, 1))["kur.USD"] == Decimal(50)
    assert ps.gecerli_degerler(oturum, senaryo.id, date(2026, 10, 1))["kur.USD"] == Decimal(55)
    g = ps.gecmis(oturum, senaryo.id, "kur.USD")
    assert [x.deger for x in g] == [Decimal(55), Decimal(50)] and g[0].neden == "kur güncellendi"


def test_ayni_gun_iki_kayit_sonuncusu_gecerli(oturum, senaryo):
    _tohum(oturum, senaryo)
    ps.deger_ekle(oturum, senaryo.id, "stok_ay.TL", Decimal(2), date(2026, 6, 1), "düzeltme")
    assert ps.gecerli_degerler(oturum, senaryo.id, date(2026, 6, 1))["stok_ay.TL"] == Decimal(2)


def test_urun_override_geneli_ezer(oturum, senaryo):
    _tohum(oturum, senaryo)
    ps.deger_ekle(oturum, senaryo.id, "stok_ay.TL", Decimal(2), date(2026, 6, 1), "bu ürün hızlı döner", kapsam_tipi="urun", kapsam_id=7)
    assert ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 7, 1), urun_id=7).stok_sureleri_ay["TL"] == Decimal(2)
    assert ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 7, 1), urun_id=8).stok_sureleri_ay["TL"] == Decimal(6)


def test_eksik_zorunlu_parametre_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        ps.gecerli_parametreler(oturum, senaryo.id, date(2026, 7, 1))


def test_bilinmeyen_anahtar_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        ps.deger_ekle(oturum, senaryo.id, "yok.boyle", Decimal(1), date(2026, 6, 1), "")
```

- [ ] **Step 2: Çalıştır, başarısız** — `ModuleNotFoundError: backend.servisler`

- [ ] **Step 3: Uygulama**

```python
# backend/servisler/__init__.py
```
```python
# backend/servisler/hatalar.py
class ServisHatasi(Exception):
    def __init__(self, mesaj: str, alanlar: dict | None = None):
        super().__init__(mesaj); self.mesaj = mesaj; self.alanlar = alanlar or {}


class BulunamadiHatasi(ServisHatasi): ...
class DogrulamaHatasi(ServisHatasi): ...
```
```python
# backend/servisler/donusum.py
"""Motor dataclass'ları ile JSON snapshot arasında dönüşüm. Decimal -> str, date -> ISO."""
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal


def decimal_str(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: decimal_str(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {str(k): decimal_str(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [decimal_str(v) for v in obj]
    return obj


dataclass_to_dict = decimal_str
```
```python
# backend/servisler/parametre_servisi.py
"""Append-only parametre değerleri. Geçerli değer = gecerlilik_basi <= tarih olan en yeni kayıt; ürün override geneli ezer."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import Parametreler
from ..depo import modeller as m
from .hatalar import DogrulamaHatasi

ZORUNLU = ("enflasyon", "satis_kar", "vardiya_saati")


def _parametre(s: Session, anahtar: str) -> m.Parametre:
    p = s.scalar(select(m.Parametre).where(m.Parametre.anahtar == anahtar))
    if p is None:
        raise DogrulamaHatasi(f"bilinmeyen parametre: {anahtar}", {"anahtar": anahtar})
    return p


def deger_ekle(s: Session, senaryo_id: int, anahtar: str, deger: Decimal, gecerlilik_basi: date, neden: str,
               kapsam_tipi: str = "genel", kapsam_id: int | None = None, olusturan: str = "sistem") -> m.ParametreDegeri:
    if kapsam_tipi not in ("genel", "urun") or (kapsam_tipi == "urun" and kapsam_id is None):
        raise DogrulamaHatasi("kapsam geçersiz", {"kapsam_tipi": kapsam_tipi})
    kayit = m.ParametreDegeri(parametre_id=_parametre(s, anahtar).id, senaryo_id=senaryo_id, kapsam_tipi=kapsam_tipi,
                              kapsam_id=kapsam_id, deger=Decimal(deger), gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(kayit); s.flush()
    return kayit


def gecmis(s: Session, senaryo_id: int, anahtar: str) -> list[m.ParametreDegeri]:
    q = (select(m.ParametreDegeri).join(m.Parametre).where(m.Parametre.anahtar == anahtar, m.ParametreDegeri.senaryo_id == senaryo_id)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    return list(s.scalars(q))


def gecerli_degerler(s: Session, senaryo_id: int, tarih: date, urun_id: int | None = None) -> dict[str, Decimal]:
    q = (select(m.ParametreDegeri, m.Parametre.anahtar).join(m.Parametre)
         .where(m.ParametreDegeri.senaryo_id == senaryo_id, m.ParametreDegeri.gecerlilik_basi <= tarih)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    genel: dict[str, Decimal] = {}
    urun: dict[str, Decimal] = {}
    for kayit, anahtar in s.execute(q):
        if kayit.kapsam_tipi == "urun":
            if urun_id is not None and kayit.kapsam_id == urun_id:
                urun.setdefault(anahtar, kayit.deger)
        else:
            genel.setdefault(anahtar, kayit.deger)
    return {**genel, **urun}


def _grup(d: dict[str, Decimal], onek: str) -> dict[str, Decimal]:
    return {k[len(onek):]: v for k, v in d.items() if k.startswith(onek)}


def gecerli_parametreler(s: Session, senaryo_id: int, tarih: date, urun_id: int | None = None) -> Parametreler:
    d = gecerli_degerler(s, senaryo_id, tarih, urun_id)
    eksik = [z for z in ZORUNLU if z not in d]
    if eksik:
        raise DogrulamaHatasi("zorunlu parametre eksik", {"eksik": eksik})
    teklif = _grup(d, "teklif_kar.")
    return Parametreler(
        enflasyon=d["enflasyon"], kurlar=_grup(d, "kur."), faiz_oranlari=_grup(d, "faiz."), stok_sureleri_ay=_grup(d, "stok_ay."),
        satis_kar_orani=d["satis_kar"], teklif_kar_oranlari=tuple(teklif[k] for k in sorted(teklif, key=int)),
        vardiya_saati=d["vardiya_saati"])
```

- [ ] **Step 4: Çalıştır, geçer** — 6 passed.

---

### Task 4: Fiyat servisi (`fiyat_servisi.py`)

**Files:** Create `backend/servisler/fiyat_servisi.py`, `tests/backend/test_fiyat_servisi.py`

**Interfaces:**
- `malzeme_ekle_veya_guncelle(s, kod, ad, tip, birim, para_birimi, zs) -> Malzeme` (ad/tip/birim/para/zs güncellenir; `DegisiklikKaydi` yazılır)
- `fiyat_ekle(s, senaryo_id, kod, fiyat, gecerlilik_basi, neden, kaynak="elle", para_birimi=None, olusturan="sistem") -> MalzemeFiyati` (para_birimi None ise malzemenin)
- `gecerli_fiyatlar(s, senaryo_id, tarih) -> dict[str, Malzeme(motor)]` — fiyatı olmayan malzeme de döner (`fiyat=SIFIR`), motor 0 + uyarı üretir
- `gecmis(s, senaryo_id, kod) -> list[MalzemeFiyati]`
- `fiyatsizlar(s, senaryo_id, tarih) -> list[str]` (kod listesi; yalnız `aktif=True`)

- [ ] **Step 1: Test**

```python
# tests/backend/test_fiyat_servisi.py
from datetime import date
from decimal import Decimal
import pytest
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs
from fiyat_motoru.para import SIFIR


@pytest.fixture
def senaryo(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    return sen


def test_fiyat_gecmisi_ve_gecerli(oturum, senaryo):
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", "S")
    fs.fiyat_ekle(oturum, senaryo.id, "KAV", Decimal("5.9"), date(2026, 6, 1), "bütçe", kaynak="import")
    fs.fiyat_ekle(oturum, senaryo.id, "KAV", Decimal("6.4"), date(2026, 9, 1), "zam")
    assert fs.gecerli_fiyatlar(oturum, senaryo.id, date(2026, 8, 1))["KAV"].fiyat == Decimal("5.9")
    g = fs.gecerli_fiyatlar(oturum, senaryo.id, date(2026, 10, 1))["KAV"]
    assert g.fiyat == Decimal("6.4") and g.zs == "S" and g.para_birimi == "TL" and g.ad == "Kavanoz 370"
    assert [x.fiyat for x in fs.gecmis(oturum, senaryo.id, "KAV")] == [Decimal("6.4"), Decimal("5.9")]


def test_fiyatsiz_malzeme_listede_sifir_ve_raporda(oturum, senaryo):
    fs.malzeme_ekle_veya_guncelle(oturum, "ARA", "Ara mamul", "0001-Hammadde", "KG", None, None)
    f = fs.gecerli_fiyatlar(oturum, senaryo.id, date(2026, 8, 1))
    assert f["ARA"].fiyat == SIFIR and fs.fiyatsizlar(oturum, senaryo.id, date(2026, 8, 1)) == ["ARA"]


def test_malzeme_guncelleme_degisiklik_kaydi(oturum, senaryo):
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Kavanoz", None, "AD", "TL", "S")
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Kavanoz 370 Boğumlu", None, "AD", "TL", "S")
    kayit = oturum.query(m.DegisiklikKaydi).filter_by(tablo="malzeme").one()
    assert kayit.eski["ad"] == "Kavanoz" and kayit.yeni["ad"] == "Kavanoz 370 Boğumlu"
```

- [ ] **Step 2: Çalıştır, başarısız** — `ModuleNotFoundError`

- [ ] **Step 3: Uygulama**

```python
# backend/servisler/fiyat_servisi.py
"""Malzeme kartı ve append-only bütçe birim fiyatı. Motorun Malzeme dataclass'ını üretir."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import Malzeme as MotorMalzeme
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi

IZLENEN = ("ad", "tip", "birim", "para_birimi", "zs", "aktif")


def _malzeme(s: Session, kod: str) -> m.Malzeme:
    mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
    if mz is None:
        raise BulunamadiHatasi(f"malzeme yok: {kod}", {"kod": kod})
    return mz


def malzeme_ekle_veya_guncelle(s: Session, kod: str, ad: str, tip: str | None, birim: str | None,
                               para_birimi: str | None, zs: str | None, kullanici: str = "sistem") -> m.Malzeme:
    mz = s.scalar(select(m.Malzeme).where(m.Malzeme.kod == kod))
    yeni = {"ad": ad, "tip": tip, "birim": birim, "para_birimi": para_birimi, "zs": zs, "aktif": True}
    if mz is None:
        mz = m.Malzeme(kod=kod, **yeni, olusturan=kullanici); s.add(mz); s.flush()
        return mz
    eski = {a: getattr(mz, a) for a in IZLENEN}
    if eski != yeni:
        for a, v in yeni.items():
            setattr(mz, a, v)
        s.add(m.DegisiklikKaydi(tablo="malzeme", kayit_id=mz.id, islem="guncelle", eski=eski, yeni=yeni, kullanici=kullanici, zaman=datetime.now()))
        s.flush()
    return mz


def fiyat_ekle(s: Session, senaryo_id: int, kod: str, fiyat: Decimal, gecerlilik_basi: date, neden: str,
               kaynak: str = "elle", para_birimi: str | None = None, olusturan: str = "sistem") -> m.MalzemeFiyati:
    mz = _malzeme(s, kod)
    k = m.MalzemeFiyati(malzeme_id=mz.id, senaryo_id=senaryo_id, fiyat=Decimal(fiyat), para_birimi=para_birimi or mz.para_birimi,
                        gecerlilik_basi=gecerlilik_basi, kaynak=kaynak, neden=neden, olusturan=olusturan)
    s.add(k); s.flush()
    return k


def gecmis(s: Session, senaryo_id: int, kod: str) -> list[m.MalzemeFiyati]:
    mz = _malzeme(s, kod)
    q = (select(m.MalzemeFiyati).where(m.MalzemeFiyati.malzeme_id == mz.id, m.MalzemeFiyati.senaryo_id == senaryo_id)
         .order_by(m.MalzemeFiyati.gecerlilik_basi.desc(), m.MalzemeFiyati.id.desc()))
    return list(s.scalars(q))


def _gecerli_kayitlar(s: Session, senaryo_id: int, tarih: date) -> dict[int, m.MalzemeFiyati]:
    q = (select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == senaryo_id, m.MalzemeFiyati.gecerlilik_basi <= tarih)
         .order_by(m.MalzemeFiyati.gecerlilik_basi.desc(), m.MalzemeFiyati.id.desc()))
    son: dict[int, m.MalzemeFiyati] = {}
    for k in s.scalars(q):
        son.setdefault(k.malzeme_id, k)
    return son


def gecerli_fiyatlar(s: Session, senaryo_id: int, tarih: date) -> dict[str, MotorMalzeme]:
    son = _gecerli_kayitlar(s, senaryo_id, tarih)
    out = {}
    for mz in s.scalars(select(m.Malzeme)):
        f = son.get(mz.id)
        out[mz.kod] = MotorMalzeme(kod=mz.kod, ad=mz.ad, tip=mz.tip, birim=mz.birim,
                                   para_birimi=(f.para_birimi if f else mz.para_birimi), fiyat=(f.fiyat if f else SIFIR), zs=mz.zs)
    return out


def fiyatsizlar(s: Session, senaryo_id: int, tarih: date) -> list[str]:
    son = _gecerli_kayitlar(s, senaryo_id, tarih)
    return sorted(mz.kod for mz in s.scalars(select(m.Malzeme).where(m.Malzeme.aktif == True))
                  if mz.id not in son or son[mz.id].fiyat == SIFIR)
```

- [ ] **Step 4: Çalıştır, geçer** — 3 passed.

---

### Task 5: Gider servisi (`gider_servisi.py`)

**Files:** Create `backend/servisler/gider_servisi.py`, `tests/backend/test_gider_servisi.py`

**Interfaces:**
- `havuz_kaydet(s, senaryo_id, kod, ad, toplam_tutar, baz_tipi, baz_miktar, anahtarlar: list[tuple[str, Decimal, Decimal]], kullanici) -> GiderHavuzu` — var olanı günceller (anahtarları yeniden yazar), `DegisiklikKaydi` tutar
- `ambalaj_kaydet(s, senaryo_id, siniflar: list[tuple[str, Decimal, Decimal, Decimal]]) -> list[AmbalajSinifi]` — tam değiştirme
- `havuzlari_getir(s, senaryo_id) -> GiderHavuzlari` (motor dataclass'ı); eksik havuz → `DogrulamaHatasi`
- `oranlar(s, senaryo_id) -> GiderOranlari` = `oranlari_hesapla(havuzlari_getir(...))`
- `pay_toplami_kontrol(s, senaryo_id) -> list[dict]` → `[{"havuz": kod, "toplam": Decimal}]` yalnız |toplam−1| ≥ 0.0005 olanlar

Havuz kodları (sabit): `dolum_iscilik` (saniye), `mal_kabul_iscilik` (kg, anahtarlar: sınıf→pay,kg), `etiket_iscilik` (saniye), `endirekt_iscilik` (saniye), `mal_kabul_gug` (kg), `diger_gug` (saniye), `elektrik`/`dogalgaz`/`amortisman` (saniye, anahtarlar: hat→pay,saniye), `yonetim` (adet), `pazarlama` (adet).

- [ ] **Step 1: Test**

```python
# tests/backend/test_gider_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import gider_servisi as gs
from backend.servisler.hatalar import DogrulamaHatasi
from fiyat_motoru.para import yakin


@pytest.fixture
def senaryo(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    return sen


def tohumla(oturum, sid):
    sinif = [("Taze/Taze", D_("0.25"), D_(6000000)), ("Taze/Turşu", D_("0.65"), D_(7000000)), ("Turşu/Turşu", D_("0.1"), D_(3500000))]
    hat = [("Niko", D_("0.376"), D_(8193712))]
    gs.havuz_kaydet(oturum, sid, "dolum_iscilik", "Dolum", D_("86037707.86667047"), "saniye", D_(442154500), [])
    gs.havuz_kaydet(oturum, sid, "mal_kabul_iscilik", "Mal kabul", D_("32065211.4127488"), "kg", None, sinif)
    gs.havuz_kaydet(oturum, sid, "etiket_iscilik", "Etiket", D_("18533808.031511273"), "saniye", D_(132435000), [])
    gs.havuz_kaydet(oturum, sid, "endirekt_iscilik", "Endirekt", D_("42088882.57323751"), "saniye", D_(32547902), [])
    gs.havuz_kaydet(oturum, sid, "mal_kabul_gug", "Mal kabul GÜG", D_(21000000), "kg", None, sinif)
    gs.havuz_kaydet(oturum, sid, "diger_gug", "Diğer GÜG", D_("25281257.75"), "saniye", D_(32547902), [])
    gs.havuz_kaydet(oturum, sid, "elektrik", "Elektrik", D_(14112000), "saniye", None, hat)
    gs.havuz_kaydet(oturum, sid, "dogalgaz", "Doğalgaz", D_(22464000), "saniye", None, [("Niko", D_("0.46"), D_(8193712))])
    gs.havuz_kaydet(oturum, sid, "amortisman", "Amortisman", D_(49056000), "saniye", None, [("Niko", D_("0.43"), D_(8193712))])
    gs.havuz_kaydet(oturum, sid, "yonetim", "Yönetim", D_("26274982.5"), "adet", None, [])
    gs.havuz_kaydet(oturum, sid, "pazarlama", "Pazarlama", D_(16848000), "adet", None, [])
    gs.ambalaj_kaydet(oturum, sid, [("370 ml kavanoz", D_(370), D_(5690071), D_("0.5")), ("720 ml kavanoz", D_(720), D_(11896020), D_("0.75"))])


def test_oranlar_excel_ile_ayni(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    o = gs.oranlar(oturum, senaryo.id)
    assert yakin(o.dolum_iscilik_sn, D_("0.19458743011022273"))
    assert yakin(o.mal_kabul_iscilik_kg["turşu/turşu"], D_("0.9161488975071086"))
    assert yakin(o.elektrik_sn["niko"], D_("0.6475834151847173"))
    payda = D_(5690071) * D_("0.5") + D_(11896020) * D_("0.75")
    assert yakin(o.pazarlama_adet[D_(370)], D_(16848000) / payda * D_("0.5"))


def test_eksik_havuz_hata(oturum, senaryo):
    with pytest.raises(DogrulamaHatasi):
        gs.havuzlari_getir(oturum, senaryo.id)


def test_pay_toplami_kontrol(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(14112000), "saniye", None,
                    [("Niko", D_("0.376"), D_(8193712)), ("Herbort", D_("0.191"), D_(4720549))])
    bozuk = gs.pay_toplami_kontrol(oturum, senaryo.id)
    assert {b["havuz"] for b in bozuk} >= {"elektrik", "dogalgaz", "amortisman"}
    assert next(b for b in bozuk if b["havuz"] == "elektrik")["toplam"] == D_("0.567")


def test_havuz_guncelleme_anahtarlari_yeniler(oturum, senaryo):
    tohumla(oturum, senaryo.id)
    gs.havuz_kaydet(oturum, senaryo.id, "elektrik", "Elektrik", D_(1), "saniye", None, [("Torba", D_(1), D_(10))])
    h = oturum.query(m.GiderHavuzu).filter_by(senaryo_id=senaryo.id, kod="elektrik").one()
    assert [a.alt_kalem for a in h.anahtarlar] == ["Torba"] and oturum.query(m.DegisiklikKaydi).filter_by(tablo="gider_havuzu").count() == 1
```

- [ ] **Step 2: Çalıştır, başarısız**

- [ ] **Step 3: Uygulama**

```python
# backend/servisler/gider_servisi.py
"""Gider havuzları ve dağıtım anahtarları -> motorun GiderHavuzlari/GiderOranlari."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.gider_dagitim import oranlari_hesapla
from fiyat_motoru.modeller import AmbalajSinifi, GiderHavuzlari, GiderOranlari
from ..depo import modeller as m
from .hatalar import DogrulamaHatasi

HAVUZ_KODLARI = ("dolum_iscilik", "mal_kabul_iscilik", "etiket_iscilik", "endirekt_iscilik", "mal_kabul_gug", "diger_gug",
                 "elektrik", "dogalgaz", "amortisman", "yonetim", "pazarlama")
PAYLI = ("mal_kabul_iscilik", "mal_kabul_gug", "elektrik", "dogalgaz", "amortisman")


def havuz_kaydet(s: Session, senaryo_id: int, kod: str, ad: str, toplam_tutar: Decimal, baz_tipi: str, baz_miktar: Decimal | None,
                 anahtarlar: list[tuple[str, Decimal, Decimal]], kullanici: str = "sistem") -> m.GiderHavuzu:
    if kod not in HAVUZ_KODLARI:
        raise DogrulamaHatasi(f"bilinmeyen havuz: {kod}", {"kod": kod})
    h = s.scalar(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == senaryo_id, m.GiderHavuzu.kod == kod))
    yeni = {"ad": ad, "toplam_tutar": str(toplam_tutar), "baz_tipi": baz_tipi, "baz_miktar": None if baz_miktar is None else str(baz_miktar),
            "anahtarlar": [[a, str(p), str(b)] for a, p, b in anahtarlar]}
    if h is None:
        h = m.GiderHavuzu(senaryo_id=senaryo_id, kod=kod, ad=ad, toplam_tutar=toplam_tutar, baz_tipi=baz_tipi, baz_miktar=baz_miktar, olusturan=kullanici)
        s.add(h)
    else:
        eski = {"ad": h.ad, "toplam_tutar": str(h.toplam_tutar), "baz_tipi": h.baz_tipi, "baz_miktar": None if h.baz_miktar is None else str(h.baz_miktar),
                "anahtarlar": [[a.alt_kalem, str(a.pay_orani), str(a.baz_miktar)] for a in h.anahtarlar]}
        h.ad, h.toplam_tutar, h.baz_tipi, h.baz_miktar = ad, toplam_tutar, baz_tipi, baz_miktar
        s.add(m.DegisiklikKaydi(tablo="gider_havuzu", kayit_id=h.id, islem="guncelle", eski=eski, yeni=yeni, kullanici=kullanici, zaman=datetime.now()))
    h.anahtarlar = [m.DagitimAnahtari(alt_kalem=a, pay_orani=p, baz_miktar=b) for a, p, b in anahtarlar]
    s.flush()
    return h


def ambalaj_kaydet(s: Session, senaryo_id: int, siniflar: list[tuple[str, Decimal, Decimal, Decimal]]) -> list[m.AmbalajSinifi]:
    for eski in s.scalars(select(m.AmbalajSinifi).where(m.AmbalajSinifi.senaryo_id == senaryo_id)):
        s.delete(eski)
    kayitlar = [m.AmbalajSinifi(senaryo_id=senaryo_id, ad=ad, hacim=h, uretim_adedi=u, katsayi=k) for ad, h, u, k in siniflar]
    s.add_all(kayitlar); s.flush()
    return kayitlar


def _havuzlar(s: Session, senaryo_id: int) -> dict[str, m.GiderHavuzu]:
    return {h.kod: h for h in s.scalars(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == senaryo_id))}


def _paylar(h: m.GiderHavuzu) -> dict[str, tuple[Decimal, Decimal]]:
    return {a.alt_kalem: (a.pay_orani, a.baz_miktar) for a in h.anahtarlar}


def havuzlari_getir(s: Session, senaryo_id: int) -> GiderHavuzlari:
    h = _havuzlar(s, senaryo_id)
    eksik = [k for k in HAVUZ_KODLARI if k not in h]
    if eksik:
        raise DogrulamaHatasi("gider havuzu eksik", {"eksik": eksik})
    amb = s.scalars(select(m.AmbalajSinifi).where(m.AmbalajSinifi.senaryo_id == senaryo_id).order_by(m.AmbalajSinifi.id))
    return GiderHavuzlari(
        dolum_iscilik_toplam=h["dolum_iscilik"].toplam_tutar, dolum_iscilik_saniye=h["dolum_iscilik"].baz_miktar,
        mal_kabul_iscilik_toplam=h["mal_kabul_iscilik"].toplam_tutar, mal_kabul_paylari=_paylar(h["mal_kabul_iscilik"]),
        etiket_iscilik_toplam=h["etiket_iscilik"].toplam_tutar, etiket_iscilik_saniye=h["etiket_iscilik"].baz_miktar,
        endirekt_iscilik_toplam=h["endirekt_iscilik"].toplam_tutar, endirekt_saniye=h["endirekt_iscilik"].baz_miktar,
        mal_kabul_gug_toplam=h["mal_kabul_gug"].toplam_tutar, mal_kabul_gug_paylari=_paylar(h["mal_kabul_gug"]),
        diger_gug_toplam=h["diger_gug"].toplam_tutar, diger_gug_saniye=h["diger_gug"].baz_miktar,
        elektrik_toplam=h["elektrik"].toplam_tutar, elektrik_hatlar=_paylar(h["elektrik"]),
        dogalgaz_toplam=h["dogalgaz"].toplam_tutar, dogalgaz_hatlar=_paylar(h["dogalgaz"]),
        amortisman_toplam=h["amortisman"].toplam_tutar, amortisman_hatlar=_paylar(h["amortisman"]),
        yonetim_toplam=h["yonetim"].toplam_tutar, pazarlama_toplam=h["pazarlama"].toplam_tutar,
        ambalajlar=tuple(AmbalajSinifi(ad=a.ad, hacim=a.hacim, uretim_adedi=a.uretim_adedi, katsayi=a.katsayi) for a in amb),
    )


def oranlar(s: Session, senaryo_id: int) -> GiderOranlari:
    return oranlari_hesapla(havuzlari_getir(s, senaryo_id))


def pay_toplami_kontrol(s: Session, senaryo_id: int) -> list[dict]:
    out = []
    for kod, h in _havuzlar(s, senaryo_id).items():
        if kod in PAYLI:
            toplam = sum((a.pay_orani for a in h.anahtarlar), Decimal(0))
            if abs(toplam - 1) >= Decimal("0.0005"):
                out.append({"havuz": kod, "toplam": toplam})
    return out
```

- [ ] **Step 4: Çalıştır, geçer** — 4 passed.

---

### Task 6: Reçete servisi ve fire önceliği (`recete_servisi.py`)

**Files:** Create `backend/servisler/recete_servisi.py`, `tests/backend/test_recete_servisi.py`

**Interfaces:**
- `yeni_versiyon(s, urun_id, senaryo_id, satirlar: list[dict], kaynak, kullanici) -> Recete` — `satirlar` elemanı: `{"malzeme_kodu","ad","miktar","birim","fire_override"(opsiyonel),"dugum_tipi"(opsiyonel)}`; önceki aktif reçete `aktif=False`, yeni `versiyon = max+1`
- `aktif_recete(s, urun_id, senaryo_id) -> Recete` (yoksa `BulunamadiHatasi`)
- `fire_kurali_ekle(s, senaryo_id, kapsam_tipi, kapsam_deger, oran, gecerlilik_basi, neden, oncelik=None) -> FireKurali` (öncelik varsayılanı: malzeme=10, grup=20, tip=30; küçük önce)
- `grup_olustur(s, ad, malzeme_kodlari) -> MalzemeGrubu`
- `fire_uygulanmis(s, recete, senaryo_id, tarih, malzeme_tipleri: dict[str, str|None]) -> tuple[list[ReceteSatiri(motor)], list[str]]` — ikinci eleman satır sırasına göre fire kaynağı: `"satir"`, `"grup:<ad>"`, `"malzeme"`, `"tip:<tip>"`, `"yok"`

Öncelik: satır override > grup > malzeme > tip > 0. Aynı kapsam için geçerli kural = `gecerlilik_basi <= tarih` en yeni.

- [ ] **Step 1: Test**

```python
# tests/backend/test_recete_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import recete_servisi as rs
from fiyat_motoru.para import SIFIR


@pytest.fixture
def ortam(oturum):
    sz = m.Sezon(ad="S", baslangic=date(2026, 6, 1), bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    u = m.Urun(kod="U1", ad="Ürün", ambalaj_hacmi=D_(370), hat="Niko", taze_tursu_sinifi="Turşu/Turşu", suzme_kg=D_("0.18")); oturum.add(u); oturum.flush()
    return sen, u


SATIRLAR = [
    {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": D_(1), "birim": "AD"},
    {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.05")},
    {"malzeme_kodu": "TAZ", "ad": "Taze", "miktar": D_("0.19"), "birim": "KG"},
    {"malzeme_kodu": "ARA", "ad": "Ara mamul", "miktar": D_(1), "birim": "KG", "dugum_tipi": "ara_mamul"},
]
TIPLER = {"KAV": "0008-Ambalaj Malzeme", "ETK": "0008-Ambalaj Malzeme", "TAZ": "0001-Hammadde", "ARA": None}


def test_versiyonlama(oturum, ortam):
    sen, u = ortam
    r1 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    r2 = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR[:2], "elle", "esma")
    assert (r1.versiyon, r1.aktif, r2.versiyon, r2.aktif) == (1, False, 2, True)
    assert rs.aktif_recete(oturum, u.id, sen.id).id == r2.id and len(r2.satirlar) == 2


def test_fire_onceligi(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR, "import", "sistem")
    t = date(2026, 6, 1)
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.02"), t, "varsayılan")
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0001-Hammadde", D_("0.05"), t, "varsayılan")
    rs.fire_kurali_ekle(oturum, sen.id, "malzeme", "TAZ", D_("0.03"), t, "bu taze az fire verir")
    rs.grup_olustur(oturum, "Hassas kavanozlar", ["KAV"])
    rs.fire_kurali_ekle(oturum, sen.id, "grup", "Hassas kavanozlar", D_("0.04"), t, "kırılgan")
    satirlar, kaynaklar = rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 10, 1), TIPLER)
    assert [s.fire_orani for s in satirlar] == [D_("0.04"), D_("0.05"), D_("0.03"), SIFIR]
    assert kaynaklar == ["grup:Hassas kavanozlar", "satir", "malzeme", "yok"]


def test_fire_kurali_gecmisi(oturum, ortam):
    sen, u = ortam
    r = rs.yeni_versiyon(oturum, u.id, sen.id, SATIRLAR[:1], "import", "sistem")
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.02"), date(2026, 6, 1), "v1")
    rs.fire_kurali_ekle(oturum, sen.id, "tip", "0008-Ambalaj Malzeme", D_("0.03"), date(2026, 9, 1), "v2")
    assert rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 8, 1), TIPLER)[0][0].fire_orani == D_("0.02")
    assert rs.fire_uygulanmis(oturum, r, sen.id, date(2026, 10, 1), TIPLER)[0][0].fire_orani == D_("0.03")
```

- [ ] **Step 2: Çalıştır, başarısız**

- [ ] **Step 3: Uygulama**

```python
# backend/servisler/recete_servisi.py
"""Reçete versiyonları ve fire önceliği: satır override > grup > malzeme > tip > 0."""
from datetime import date
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import ReceteSatiri as MotorSatir
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

ONCELIK = {"malzeme": 10, "grup": 20, "tip": 30}


def yeni_versiyon(s: Session, urun_id: int, senaryo_id: int, satirlar: list[dict], kaynak: str, kullanici: str = "sistem") -> m.Recete:
    if not satirlar:
        raise DogrulamaHatasi("reçete boş olamaz")
    for eski in s.scalars(select(m.Recete).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True)):
        eski.aktif = False
    son = s.scalar(select(func.max(m.Recete.versiyon)).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id)) or 0
    r = m.Recete(urun_id=urun_id, senaryo_id=senaryo_id, versiyon=son + 1, kaynak=kaynak, aktif=True, olusturan=kullanici)
    r.satirlar = [m.ReceteSatiri(sira=i + 1, malzeme_kodu=d["malzeme_kodu"], ad=d.get("ad", ""), miktar=Decimal(d["miktar"]), birim=d.get("birim"),
                                 fire_override=None if d.get("fire_override") is None else Decimal(d["fire_override"]),
                                 dugum_tipi=d.get("dugum_tipi", "yaprak")) for i, d in enumerate(satirlar)]
    s.add(r); s.flush()
    return r


def aktif_recete(s: Session, urun_id: int, senaryo_id: int) -> m.Recete:
    r = s.scalar(select(m.Recete).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True))
    if r is None:
        raise BulunamadiHatasi("aktif reçete yok", {"urun_id": urun_id, "senaryo_id": senaryo_id})
    return r


def fire_kurali_ekle(s: Session, senaryo_id: int, kapsam_tipi: str, kapsam_deger: str, oran: Decimal, gecerlilik_basi: date, neden: str,
                     oncelik: int | None = None, olusturan: str = "sistem") -> m.FireKurali:
    if kapsam_tipi not in ONCELIK:
        raise DogrulamaHatasi("kapsam_tipi tip|grup|malzeme olmalı", {"kapsam_tipi": kapsam_tipi})
    k = m.FireKurali(senaryo_id=senaryo_id, kapsam_tipi=kapsam_tipi, kapsam_deger=kapsam_deger, oran=Decimal(oran),
                     oncelik=ONCELIK[kapsam_tipi] if oncelik is None else oncelik, gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(k); s.flush()
    return k


def grup_olustur(s: Session, ad: str, malzeme_kodlari: list[str]) -> m.MalzemeGrubu:
    g = m.MalzemeGrubu(ad=ad)
    g.uyeler = [m.MalzemeGrubuUyesi(malzeme_kodu=k) for k in malzeme_kodlari]
    s.add(g); s.flush()
    return g


def _gecerli_kurallar(s: Session, senaryo_id: int, tarih: date) -> dict[tuple[str, str], m.FireKurali]:
    q = (select(m.FireKurali).where(m.FireKurali.senaryo_id == senaryo_id, m.FireKurali.gecerlilik_basi <= tarih)
         .order_by(m.FireKurali.gecerlilik_basi.desc(), m.FireKurali.id.desc()))
    out: dict[tuple[str, str], m.FireKurali] = {}
    for k in s.scalars(q):
        out.setdefault((k.kapsam_tipi, k.kapsam_deger), k)
    return out


def _gruplar(s: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for g in s.scalars(select(m.MalzemeGrubu)):
        for u in g.uyeler:
            out.setdefault(u.malzeme_kodu, []).append(g.ad)
    return out


def fire_uygulanmis(s: Session, recete: m.Recete, senaryo_id: int, tarih: date,
                    malzeme_tipleri: dict[str, str | None]) -> tuple[list[MotorSatir], list[str]]:
    kurallar = _gecerli_kurallar(s, senaryo_id, tarih)
    gruplar = _gruplar(s)
    satirlar, kaynaklar = [], []
    for rs_ in recete.satirlar:
        if rs_.fire_override is not None:
            oran, kaynak = rs_.fire_override, "satir"
        else:
            adaylar: list[tuple[int, Decimal, str]] = []
            for g in gruplar.get(rs_.malzeme_kodu, []):
                if ("grup", g) in kurallar:
                    adaylar.append((kurallar[("grup", g)].oncelik, kurallar[("grup", g)].oran, f"grup:{g}"))
            if ("malzeme", rs_.malzeme_kodu) in kurallar:
                k = kurallar[("malzeme", rs_.malzeme_kodu)]; adaylar.append((k.oncelik, k.oran, "malzeme"))
            tip = malzeme_tipleri.get(rs_.malzeme_kodu)
            if tip and ("tip", tip) in kurallar:
                k = kurallar[("tip", tip)]; adaylar.append((k.oncelik, k.oran, f"tip:{tip}"))
            if adaylar:
                _, oran, kaynak = min(adaylar, key=lambda a: a[0])
            else:
                oran, kaynak = SIFIR, "yok"
        satirlar.append(MotorSatir(malzeme_kodu=rs_.malzeme_kodu, ad=rs_.ad, miktar=rs_.miktar, fire_orani=oran, birim=rs_.birim))
        kaynaklar.append(kaynak)
    return satirlar, kaynaklar
```

- [ ] **Step 4: Çalıştır, geçer** — 3 passed.

---

### Task 7: Hesap servisi (`hesap_servisi.py`)

**Files:** Create `backend/servisler/hesap_servisi.py`, `tests/backend/test_hesap_servisi.py`

**Interfaces:**
- `@dataclass HesapCiktisi: girdi: UrunGirdisi; parametreler: Parametreler; oranlar: GiderOranlari; sonuc: MaliyetSonucu; fire_kaynaklari: list[str]; kullanilan_parametreler: dict[str, Decimal]`
- `hesapla(s, urun_kodu, senaryo_id, tarih=None, override=None) -> HesapCiktisi` — `override = {"parametreler": {anahtar: Decimal}, "fire": {sira: Decimal}, "uretim": {alan: deger}}`; `tarih` None → bugün; `senaryo.tur == "gerceklesen"` → `enflasyon = 0`
- `kaydet(s, cikti, urun_kodu, senaryo_id, tarih, kullanici) -> MaliyetHesabi` (snapshot'lar `donusum.decimal_str` ile)
- `getir(s, hesap_id) -> MaliyetHesabi`
- `toplu_hesapla(s, senaryo_id, tarih=None) -> list[tuple[str, HesapCiktisi | Exception]]` (aktif ürünler; bir ürünün hatası diğerini durdurmaz)
- `urun_kaydet(s, kod, ad, ambalaj_hacmi, hat, taze_tursu_sinifi, suzme_kg, pazar="Yurtiçi") -> Urun` (var olanı günceller + `DegisiklikKaydi`); `uretim_hedefi_kaydet(s, urun_id, senaryo_id, **alanlar) -> UretimHedefi` (upsert + `DegisiklikKaydi`)

- [ ] **Step 1: Test** — Task 3-6 servisleriyle `001` ürününün küçültülmüş hali kurulur (tests/test_hesapla.py'deki üç malzeme), sonuç Faz 1 testinin değerleriyle aynı olmalı.

```python
# tests/backend/test_hesap_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs, gider_servisi as gs, hesap_servisi as hs, parametre_servisi as ps, recete_servisi as rs
from backend.servisler.hatalar import BulunamadiHatasi
from fiyat_motoru.para import yakin
from tests.backend.test_gider_servisi import tohumla as gider_tohumla

T = date(2026, 6, 1)


@pytest.fixture
def ortam(oturum):
    sz = m.Sezon(ad="S", baslangic=T, bitis=date(2027, 5, 31)); oturum.add(sz); oturum.flush()
    sen = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="A"); oturum.add(sen); oturum.flush()
    for a in ["enflasyon", "kur.USD", "kur.EUR", "faiz.TL", "stok_ay.TL", "faiz.USD", "stok_ay.USD", "faiz.EUR", "stok_ay.EUR",
              "satis_kar", "teklif_kar.1", "teklif_kar.2", "teklif_kar.3", "vardiya_saati"]:
        oturum.add(m.Parametre(anahtar=a))
    oturum.flush()
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"), ("faiz.USD", "0.06"),
                 ("stok_ay.USD", "6"), ("faiz.EUR", "0.06"), ("stok_ay.EUR", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"),
                 ("teklif_kar.2", "0.17"), ("teklif_kar.3", "0.14"), ("vardiya_saati", "7.5")]:
        ps.deger_ekle(oturum, sen.id, a, D_(v), T, "tohum")
    gider_tohumla(oturum, sen.id)
    fs.malzeme_ekle_veya_guncelle(oturum, "KAV", "Cam Kavanoz 370", "0008-Ambalaj Malzeme", "AD", "TL", "S"); fs.fiyat_ekle(oturum, sen.id, "KAV", D_("5.9"), T, "")
    fs.malzeme_ekle_veya_guncelle(oturum, "ETK", "Etiket", "0008-Ambalaj Malzeme", "AD", "EUR", "S"); fs.fiyat_ekle(oturum, sen.id, "ETK", D_("0.049"), T, "")
    fs.malzeme_ekle_veya_guncelle(oturum, "TAZ", "Sarı Biberiye Taze", "0001-Hammadde", "KG", "TL", "Z"); fs.fiyat_ekle(oturum, sen.id, "TAZ", D_(65), T, "")
    u = hs.urun_kaydet(oturum, "TEST", "Test Ürün", D_(370), "Niko", "Turşu/Turşu", D_("0.18"))
    hs.uretim_hedefi_kaydet(oturum, u.id, sen.id, vardiya_uretim_adedi=D_(65000), dolum_personel=D_(13), etiketleme_adedi=D_(35000),
                            etiket_personel=D_(7), mal_kabul_miktar_kg=D_("0.19013459"), mal_kabul_fire=D_(0), pazarlama_yonetim_uygula=True)
    rs.yeni_versiyon(oturum, u.id, sen.id, [
        {"malzeme_kodu": "KAV", "ad": "Cam Kavanoz 370", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02")},
        {"malzeme_kodu": "ETK", "ad": "Etiket", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02")},
        {"malzeme_kodu": "TAZ", "ad": "Sarı Biberiye Taze", "miktar": D_("0.19013459"), "birim": "KG"},
        {"malzeme_kodu": "YOK", "ad": "Fiyatsız Ara Mamul", "miktar": D_(1), "birim": "KG"},
    ], "import")
    return sen, u


def test_hesapla_faz1_ile_ayni(oturum, ortam):
    sen, _ = ortam
    c = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    assert yakin(c.sonuc.malzeme_toplami, D_("22.884258554081633"))
    assert yakin(c.sonuc.direkt_iscilik_toplami, D_("1.9806745445746057"))
    assert yakin(c.sonuc.gug_toplami, D_("2.83610677949762"))
    assert c.fire_kaynaklari == ["satir", "satir", "yok", "yok"]
    assert any("YOK" in u for u in c.sonuc.uyarilar) and c.kullanilan_parametreler["kur.USD"] == D_(50)


def test_override_kaydetmeden(oturum, ortam):
    sen, _ = ortam
    normal = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    dene = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21), override={"parametreler": {"stok_ay.TL": D_(2)}, "fire": {3: D_("0.05")}})
    assert dene.sonuc.finansman["TL"] < normal.sonuc.finansman["TL"]
    assert dene.girdi.recete[2].fire_orani == D_("0.05") and dene.fire_kaynaklari[2] == "satir"
    assert oturum.query(m.ParametreDegeri).filter_by(kapsam_tipi="urun").count() == 0


def test_gerceklesen_enflasyon_sifir(oturum, ortam):
    sen, u = ortam
    g = m.Senaryo(sezon_id=sen.sezon_id, tur="gerceklesen", ad="G"); oturum.add(g); oturum.flush()
    for k in oturum.query(m.ParametreDegeri).filter_by(senaryo_id=sen.id):
        ps.deger_ekle(oturum, g.id, k.parametre.anahtar, k.deger, k.gecerlilik_basi, "kopya")
    gider_tohumla(oturum, g.id)
    for kod, f in [("KAV", "5.9"), ("ETK", "0.049"), ("TAZ", "65")]:
        fs.fiyat_ekle(oturum, g.id, kod, D_(f), T, "")
    hs.uretim_hedefi_kaydet(oturum, u.id, g.id, vardiya_uretim_adedi=D_(65000), dolum_personel=D_(13), etiketleme_adedi=D_(35000),
                            etiket_personel=D_(7), mal_kabul_miktar_kg=D_("0.19013459"), mal_kabul_fire=D_(0), pazarlama_yonetim_uygula=True)
    rs.yeni_versiyon(oturum, u.id, g.id, [{"malzeme_kodu": "KAV", "ad": "K", "miktar": D_(1), "birim": "AD", "fire_override": D_("0.02")}], "import")
    c = hs.hesapla(oturum, "TEST", g.id, date(2026, 10, 21))
    assert c.parametreler.enflasyon == D_(0) and yakin(c.sonuc.malzeme_toplami, D_("5.9") / D_("0.98"))


def test_kaydet_ve_getir_snapshot(oturum, ortam):
    sen, _ = ortam
    c = hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21))
    h = hs.kaydet(oturum, c, "TEST", sen.id, date(2026, 10, 21), "esma")
    ps.deger_ekle(oturum, sen.id, "kur.USD", D_(99), date(2026, 10, 22), "sonradan")
    g = hs.getir(oturum, h.id)
    assert g.sonuc_snapshot["finansman_dahil_maliyet_tl"] == str(c.sonuc.finansman_dahil_maliyet_tl)
    assert g.girdi_snapshot["parametreler"]["kurlar"]["USD"] == "50" and g.olusturan == "esma"


def test_toplu_hesapla_hata_izole(oturum, ortam):
    sen, _ = ortam
    hs.urun_kaydet(oturum, "RECETESIZ", "Reçetesiz", D_(370), "Niko", "Turşu/Turşu", D_("0.1"))
    out = dict(hs.toplu_hesapla(oturum, sen.id, date(2026, 10, 21)))
    assert isinstance(out["TEST"], hs.HesapCiktisi) and isinstance(out["RECETESIZ"], BulunamadiHatasi)
```

- [ ] **Step 2: Çalıştır, başarısız**

- [ ] **Step 3: Uygulama**

```python
# backend/servisler/hesap_servisi.py
"""Ürün maliyeti: servislerden girdileri toplar, motoru çağırır, isteğe bağlı snapshot kaydeder."""
from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.modeller import GiderOranlari, MaliyetSonucu, Parametreler, UretimBilgisi, UrunGirdisi
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import fiyat_servisi, gider_servisi, parametre_servisi, recete_servisi
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

URETIM_ALANLARI = ("vardiya_uretim_adedi", "dolum_personel", "etiketleme_adedi", "etiket_personel", "mal_kabul_miktar_kg", "mal_kabul_fire", "pazarlama_yonetim_uygula")


@dataclass
class HesapCiktisi:
    girdi: UrunGirdisi
    parametreler: Parametreler
    oranlar: GiderOranlari
    sonuc: MaliyetSonucu
    fire_kaynaklari: list[str]
    kullanilan_parametreler: dict[str, Decimal]


def _urun(s: Session, kod: str) -> m.Urun:
    u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
    if u is None:
        raise BulunamadiHatasi(f"ürün yok: {kod}", {"kod": kod})
    return u


def _senaryo(s: Session, senaryo_id: int) -> m.Senaryo:
    sen = s.get(m.Senaryo, senaryo_id)
    if sen is None:
        raise BulunamadiHatasi("senaryo yok", {"senaryo_id": senaryo_id})
    return sen


def urun_kaydet(s: Session, kod: str, ad: str, ambalaj_hacmi: Decimal, hat: str, taze_tursu_sinifi: str, suzme_kg: Decimal,
                pazar: str = "Yurtiçi", kullanici: str = "sistem") -> m.Urun:
    yeni = {"ad": ad, "ambalaj_hacmi": ambalaj_hacmi, "hat": hat, "taze_tursu_sinifi": taze_tursu_sinifi, "suzme_kg": suzme_kg, "pazar": pazar}
    u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
    if u is None:
        u = m.Urun(kod=kod, **yeni, olusturan=kullanici); s.add(u); s.flush()
        return u
    eski = {k: getattr(u, k) for k in yeni}
    if eski != yeni:
        for k, v in yeni.items():
            setattr(u, k, v)
        s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=u.id, islem="guncelle", eski=decimal_str(eski), yeni=decimal_str(yeni), kullanici=kullanici, zaman=datetime.now()))
        s.flush()
    return u


def uretim_hedefi_kaydet(s: Session, urun_id: int, senaryo_id: int, kullanici: str = "sistem", **alanlar) -> m.UretimHedefi:
    eksik = [a for a in URETIM_ALANLARI if a not in alanlar]
    if eksik:
        raise DogrulamaHatasi("üretim hedefi alanı eksik", {"eksik": eksik})
    h = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == urun_id, m.UretimHedefi.senaryo_id == senaryo_id))
    if h is None:
        h = m.UretimHedefi(urun_id=urun_id, senaryo_id=senaryo_id, olusturan=kullanici, **{a: alanlar[a] for a in URETIM_ALANLARI}); s.add(h); s.flush()
        return h
    eski = {a: getattr(h, a) for a in URETIM_ALANLARI}
    yeni = {a: alanlar[a] for a in URETIM_ALANLARI}
    if eski != yeni:
        for a, v in yeni.items():
            setattr(h, a, v)
        s.add(m.DegisiklikKaydi(tablo="uretim_hedefi", kayit_id=h.id, islem="guncelle", eski=decimal_str(eski), yeni=decimal_str(yeni), kullanici=kullanici, zaman=datetime.now()))
        s.flush()
    return h


def _parametre_override(p: Parametreler, degerler: dict[str, Decimal]) -> Parametreler:
    kurlar, faiz, stok = dict(p.kurlar), dict(p.faiz_oranlari), dict(p.stok_sureleri_ay)
    teklif = list(p.teklif_kar_oranlari)
    enf, kar, vs = p.enflasyon, p.satis_kar_orani, p.vardiya_saati
    for k, v in degerler.items():
        v = Decimal(v)
        if k == "enflasyon": enf = v
        elif k == "satis_kar": kar = v
        elif k == "vardiya_saati": vs = v
        elif k.startswith("kur."): kurlar[k[4:]] = v
        elif k.startswith("faiz."): faiz[k[5:]] = v
        elif k.startswith("stok_ay."): stok[k[8:]] = v
        elif k.startswith("teklif_kar."):
            i = int(k[11:]) - 1
            while len(teklif) <= i: teklif.append(SIFIR)
            teklif[i] = v
        else:
            raise DogrulamaHatasi(f"bilinmeyen override parametresi: {k}")
    return Parametreler(enflasyon=enf, kurlar=kurlar, faiz_oranlari=faiz, stok_sureleri_ay=stok, satis_kar_orani=kar,
                        teklif_kar_oranlari=tuple(teklif), vardiya_saati=vs)


def hesapla(s: Session, urun_kodu: str, senaryo_id: int, tarih: date | None = None, override: dict | None = None) -> HesapCiktisi:
    tarih = tarih or date.today()
    override = override or {}
    u, sen = _urun(s, urun_kodu), _senaryo(s, senaryo_id)
    hedef = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == u.id, m.UretimHedefi.senaryo_id == senaryo_id))
    if hedef is None:
        raise BulunamadiHatasi("üretim hedefi yok", {"urun": urun_kodu, "senaryo_id": senaryo_id})

    kullanilan = parametre_servisi.gecerli_degerler(s, senaryo_id, tarih, u.id)
    p = parametre_servisi.gecerli_parametreler(s, senaryo_id, tarih, u.id)
    if sen.tur == "gerceklesen":
        p = replace(p, enflasyon=SIFIR); kullanilan["enflasyon"] = SIFIR
    if override.get("parametreler"):
        p = _parametre_override(p, override["parametreler"]); kullanilan.update({k: Decimal(v) for k, v in override["parametreler"].items()})

    malzemeler = fiyat_servisi.gecerli_fiyatlar(s, senaryo_id, tarih)
    oranlar = gider_servisi.oranlar(s, senaryo_id)
    recete = recete_servisi.aktif_recete(s, u.id, senaryo_id)
    satirlar, kaynaklar = recete_servisi.fire_uygulanmis(s, recete, senaryo_id, tarih, {k: mz.tip for k, mz in malzemeler.items()})
    for sira, oran in (override.get("fire") or {}).items():
        i = int(sira) - 1
        satirlar[i] = replace(satirlar[i], fire_orani=Decimal(oran)); kaynaklar[i] = "satir"

    ub = {a: getattr(hedef, a) for a in URETIM_ALANLARI}
    ub.update(override.get("uretim") or {})
    uretim = UretimBilgisi(pazar=u.pazar, hat=u.hat, taze_tursu_sinifi=u.taze_tursu_sinifi, ambalaj_hacmi=u.ambalaj_hacmi, suzme_kg=u.suzme_kg,
                           vardiya_uretim_adedi=Decimal(ub["vardiya_uretim_adedi"]), dolum_personel=Decimal(ub["dolum_personel"]),
                           etiketleme_adedi=Decimal(ub["etiketleme_adedi"]), etiket_personel=Decimal(ub["etiket_personel"]),
                           mal_kabul_miktar_kg=Decimal(ub["mal_kabul_miktar_kg"]), mal_kabul_fire=Decimal(ub["mal_kabul_fire"]),
                           pazarlama_yonetim_uygula=bool(ub["pazarlama_yonetim_uygula"]))
    girdi = UrunGirdisi(kod=u.kod, ad=u.ad, recete=tuple(satirlar), uretim=uretim)
    sonuc = urun_maliyeti(girdi, malzemeler, oranlar, p)
    return HesapCiktisi(girdi=girdi, parametreler=p, oranlar=oranlar, sonuc=sonuc, fire_kaynaklari=kaynaklar, kullanilan_parametreler=kullanilan)


def kaydet(s: Session, cikti: HesapCiktisi, urun_kodu: str, senaryo_id: int, tarih: date, kullanici: str = "sistem") -> m.MaliyetHesabi:
    u = _urun(s, urun_kodu)
    h = m.MaliyetHesabi(urun_id=u.id, senaryo_id=senaryo_id, hesap_tarihi=tarih,
                        girdi_snapshot={"girdi": decimal_str(cikti.girdi), "parametreler": decimal_str(cikti.parametreler),
                                        "oranlar": decimal_str(cikti.oranlar), "fire_kaynaklari": cikti.fire_kaynaklari,
                                        "kullanilan_parametreler": decimal_str(cikti.kullanilan_parametreler)},
                        sonuc_snapshot=decimal_str(cikti.sonuc), uyarilar=list(cikti.sonuc.uyarilar), olusturan=kullanici)
    s.add(h); s.flush()
    return h


def getir(s: Session, hesap_id: int) -> m.MaliyetHesabi:
    h = s.get(m.MaliyetHesabi, hesap_id)
    if h is None:
        raise BulunamadiHatasi("hesap yok", {"hesap_id": hesap_id})
    return h


def toplu_hesapla(s: Session, senaryo_id: int, tarih: date | None = None) -> list[tuple[str, HesapCiktisi | Exception]]:
    out = []
    for u in s.scalars(select(m.Urun).where(m.Urun.aktif == True).order_by(m.Urun.kod)):
        try:
            out.append((u.kod, hesapla(s, u.kod, senaryo_id, tarih)))
        except Exception as e:  # bir ürünün hatası toplu hesabı durdurmaz; dashboard satırında gösterilir
            out.append((u.kod, e))
    return out
```

- [ ] **Step 4: Çalıştır, geçer** — 5 passed.

---

### Task 8: Teklif servisi (`teklif_servisi.py`)

**Files:** Create `backend/servisler/teklif_servisi.py`, `tests/backend/test_teklif_servisi.py`

**Interfaces:**
- `tur_ekle(s, hesap_id, kar_orani, musteri=None, notu=None, kullanici="sistem") -> Teklif` — `tur_no = son+1`; fiyatlar snapshot'tan: `fiyat_tl = maliyet_tl*(1+kar)`, `fiyat_usd = doviz_maliyet.USD*(1+kar)`, `fiyat_eur = doviz_maliyet.EUR*(1+kar)` (yoksa None)
- `turlar(s, hesap_id) -> list[Teklif]` (tur_no sırası)
- `durum_guncelle(s, teklif_id, durum) -> Teklif` (`taslak|gonderildi|kabul|red`, aksi `DogrulamaHatasi`)

- [ ] **Step 1: Test**

```python
# tests/backend/test_teklif_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.servisler import hesap_servisi as hs, teklif_servisi as ts
from backend.servisler.hatalar import DogrulamaHatasi
from fiyat_motoru.para import yakin
from tests.backend.test_hesap_servisi import ortam  # noqa: F401  (fixture)


def test_uc_tur_ve_fazlasi(oturum, ortam):
    sen, _ = ortam
    h = hs.kaydet(oturum, hs.hesapla(oturum, "TEST", sen.id, date(2026, 10, 21)), "TEST", sen.id, date(2026, 10, 21))
    usd = D_(h.sonuc_snapshot["doviz_maliyet"]["USD"]); tl = D_(h.sonuc_snapshot["finansman_dahil_maliyet_tl"])
    t1 = ts.tur_ekle(oturum, h.id, D_("0.2"), musteri="M")
    t2 = ts.tur_ekle(oturum, h.id, D_("0.17"))
    t3 = ts.tur_ekle(oturum, h.id, D_("0.14"))
    t4 = ts.tur_ekle(oturum, h.id, D_("0.12"), notu="4. tur istisna")
    assert [t.tur_no for t in ts.turlar(oturum, h.id)] == [1, 2, 3, 4]
    assert yakin(t1.fiyat_usd, usd * D_("1.2")) and yakin(t3.fiyat_tl, tl * D_("1.14")) and t4.notu == "4. tur istisna"
    assert ts.durum_guncelle(oturum, t2.id, "gonderildi").durum == "gonderildi"
    with pytest.raises(DogrulamaHatasi):
        ts.durum_guncelle(oturum, t2.id, "belirsiz")
```

- [ ] **Step 2: Çalıştır, başarısız**

- [ ] **Step 3: Uygulama**

```python
# backend/servisler/teklif_servisi.py
"""Teklif turları: kayıtlı hesabın snapshot'ı üzerinden kâr oranıyla fiyat. Tur sayısı sınırsız."""
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

DURUMLAR = ("taslak", "gonderildi", "kabul", "red")


def tur_ekle(s: Session, hesap_id: int, kar_orani: Decimal, musteri: str | None = None, notu: str | None = None, kullanici: str = "sistem") -> m.Teklif:
    h = s.get(m.MaliyetHesabi, hesap_id)
    if h is None:
        raise BulunamamadiHatasi("hesap yok", {"hesap_id": hesap_id}) if False else BulunamadiHatasi("hesap yok", {"hesap_id": hesap_id})
    kar = Decimal(kar_orani); carpan = 1 + kar
    sn = h.sonuc_snapshot
    doviz = sn.get("doviz_maliyet", {})
    son = s.scalar(select(func.max(m.Teklif.tur_no)).where(m.Teklif.maliyet_hesabi_id == hesap_id)) or 0
    t = m.Teklif(maliyet_hesabi_id=hesap_id, tur_no=son + 1, kar_orani=kar,
                 fiyat_tl=Decimal(sn["finansman_dahil_maliyet_tl"]) * carpan,
                 fiyat_usd=Decimal(doviz["USD"]) * carpan if "USD" in doviz else None,
                 fiyat_eur=Decimal(doviz["EUR"]) * carpan if "EUR" in doviz else None,
                 musteri=musteri, durum="taslak", notu=notu, olusturan=kullanici)
    s.add(t); s.flush()
    return t


def turlar(s: Session, hesap_id: int) -> list[m.Teklif]:
    return list(s.scalars(select(m.Teklif).where(m.Teklif.maliyet_hesabi_id == hesap_id).order_by(m.Teklif.tur_no)))


def durum_guncelle(s: Session, teklif_id: int, durum: str) -> m.Teklif:
    if durum not in DURUMLAR:
        raise DogrulamaHatasi("durum geçersiz", {"durum": durum, "izinli": list(DURUMLAR)})
    t = s.get(m.Teklif, teklif_id)
    if t is None:
        raise BulunamadiHatasi("teklif yok", {"teklif_id": teklif_id})
    t.durum = durum; s.flush()
    return t
```
(Uygulayıcı not: `tur_ekle` içindeki `if h is None:` satırı sadece `raise BulunamadiHatasi("hesap yok", {"hesap_id": hesap_id})` olmalı; yukarıdaki satır yazım hatasıdır, düz hali yazılır.)

- [ ] **Step 4: Çalıştır, geçer** — 1 passed.

---

### Task 9: Import servisi (`import_servisi.py`) ve tohum (`tohum.py`)

**Files:** Create `backend/servisler/import_servisi.py`, `backend/tohum.py`, `tests/backend/test_import_servisi.py`

**Interfaces:**
- `tohum.parametreleri_tohumla(s)` — Task 3'teki anahtar listesi (`enflasyon`, `kur.USD/EUR/GBP/CHF`, `faiz.TL/USD/EUR/GBP/ZAR`, `stok_ay.*` aynı, `satis_kar`, `teklif_kar.1..3`, `vardiya_saati`, `dagitim_carpani.*` için 11 havuz) `Parametre` olarak; varsa atlar.
- `tohum.fire_varsayilanlarini_tohumla(s, senaryo_id, tarih)` — tip kuralları: `0008-Ambalaj Malzeme` 0.02, `0017-Yardımcı Malzeme` 0, `0001-Hammadde` 0 (taze hammaddenin %5'i reçete satırındaki değerle gelir; tip varsayılanı 0'dır — spec bölüm 3 tablosu: 101/124 taze satırı %0).
- `import_servisi.excel_tam_yukle(s, excel_yolu, sezon_ad, senaryo_ad, tur="fiyat_calismasi", kullanici="sistem") -> dict` — döner: `{"senaryo_id", "malzeme": n, "fiyat": n, "havuz": n, "ambalaj": n, "urun": n, "recete": n, "parametre": n, "atlanan": [sayfa adları], "uyarilar": [...]}`. Adımlar:
  1. `Sezon` (varsa kullan) + `Senaryo` oluştur; `tohum.parametreleri_tohumla`.
  2. `excel_okuyucu.malzemeleri_oku` → `fiyat_servisi.malzeme_ekle_veya_guncelle` + fiyatı > 0 olanlara `fiyat_ekle(kaynak="import", gecerlilik_basi=sezon.baslangic)`.
  3. `havuzlari_oku` → `gider_servisi.havuz_kaydet` ×11 + `ambalaj_kaydet`.
  4. İlk ürün sayfasının (`urun_sayfalarini_listele()[0]`) `Parametreler`'i → `parametre_servisi.deger_ekle` (enflasyon, kur.*, faiz.*, stok_ay.*, satis_kar=0.2, teklif_kar.n, vardiya_saati).
  5. Her ürün sayfası: `urun_oku` → `hesap_servisi.urun_kaydet`, `uretim_hedefi_kaydet`, `recete_servisi.yeni_versiyon(kaynak="import")` — reçete satırının `fire_override` = sayfadaki fire (0 dahil; Excel paritesi için satır değeri aynen taşınır). Kopya sayfalar (`"(2)"` içeren) ve `urun_oku` hata veren sayfalar `atlanan`'a yazılır, yükleme sürer. Aynı ürün kodu iki sayfada ise ikinci yeni reçete versiyonu olur ve `uyarilar`a düşer.
  6. `tohum.fire_varsayilanlarini_tohumla`.
- `import_servisi.fiyat_listesi_onizle(s, senaryo_id, dosya_yolu) -> dict` — `{"yeni": [...], "degisen": [{"kod","eski","yeni"}], "ayni": n, "hatali": [...]}`; `fiyat_listesi_uygula(s, senaryo_id, dosya_yolu, gecerlilik_basi, neden, kullanici)` → yazılan sayı.

- [ ] **Step 1: Test** (gerçek Excel'i kullanır; yoksa skip)

```python
# tests/backend/test_import_servisi.py
from datetime import date
from decimal import Decimal as D_
import pytest
from backend.depo import modeller as m
from backend.servisler import fiyat_servisi as fs, hesap_servisi as hs, import_servisi as ims, recete_servisi as rs
from backend.tohum import fire_varsayilanlarini_tohumla, parametreleri_tohumla


@pytest.fixture(scope="module")
def yuklu(excel_yolu):
    from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak fiyat çalışması")
    s.commit()
    yield s, ozet
    s.close()


def test_ozet(yuklu):
    s, o = yuklu
    assert o["malzeme"] >= 800 and o["fiyat"] >= 500 and o["havuz"] == 11 and o["ambalaj"] == 22
    assert o["urun"] >= 60 and o["recete"] >= 60 and all("(2)" in a for a in o["atlanan"] if "(2)" in a)


def test_parametreler_ve_fire(yuklu):
    s, o = yuklu
    from backend.servisler import parametre_servisi as ps
    p = ps.gecerli_parametreler(s, o["senaryo_id"], date(2026, 10, 21))
    assert p.kurlar["USD"] == D_(50) and p.enflasyon == D_("0.25") and p.teklif_kar_oranlari == (D_("0.2"), D_("0.17"), D_("0.14"))
    assert s.query(m.FireKurali).filter_by(kapsam_tipi="tip", kapsam_deger="0008-Ambalaj Malzeme").one().oran == D_("0.02")


def test_recete_fire_satirdan(yuklu):
    s, o = yuklu
    u = s.query(m.Urun).filter_by(kod="03.004.001.002.00010").one()
    r = rs.aktif_recete(s, u.id, o["senaryo_id"])
    assert r.kaynak == "import" and any(x.fire_override == D_("0.02") for x in r.satirlar)


def test_tohum_tekrar_calisinca_coğalmaz(oturum):
    parametreleri_tohumla(oturum); n = oturum.query(m.Parametre).count()
    parametreleri_tohumla(oturum); assert oturum.query(m.Parametre).count() == n
```

- [ ] **Step 2: Çalıştır, başarısız**

- [ ] **Step 3: Uygulama**

```python
# backend/tohum.py
"""Parametre tanımları ve fire varsayılanları. Çalıştır: python -m backend.tohum"""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from .depo import modeller as m
from .servisler import recete_servisi

PARAMETRELER = [("enflasyon", "Enflasyon öngörüsü (yalnız fiyat çalışması)", "oran"), ("satis_kar", "Satış fiyatı kâr oranı", "oran"), ("vardiya_saati", "Vardiya süresi", "saat")]
PARAMETRELER += [(f"kur.{pb}", f"{pb} kuru", "TL") for pb in ("USD", "EUR", "GBP", "CHF")]
PARAMETRELER += [(f"faiz.{pb}", f"{pb} yıllık faiz", "oran") for pb in ("TL", "USD", "EUR", "GBP", "ZAR")]
PARAMETRELER += [(f"stok_ay.{pb}", f"{pb} ortalama stok süresi", "ay") for pb in ("TL", "USD", "EUR", "GBP", "ZAR")]
PARAMETRELER += [(f"teklif_kar.{i}", f"{i}. teklif kâr oranı", "oran") for i in (1, 2, 3)]
PARAMETRELER += [(f"dagitim_carpani.{k}", f"{k} havuzu bütçe çarpanı", "çarpan") for k in
                 ("dolum_iscilik", "mal_kabul_iscilik", "etiket_iscilik", "endirekt_iscilik", "mal_kabul_gug", "diger_gug", "elektrik", "dogalgaz", "amortisman", "yonetim", "pazarlama")]
FIRE_TIP_VARSAYILAN = {"0008-Ambalaj Malzeme": Decimal("0.02"), "0017-Yardımcı Malzeme": Decimal(0), "0001-Hammadde": Decimal(0),
                       "0018-Sarf Malzemesi": Decimal(0), "0004-Ticari Malzeme": Decimal(0)}


def parametreleri_tohumla(s: Session) -> int:
    mevcut = set(s.scalars(select(m.Parametre.anahtar)))
    yeni = [m.Parametre(anahtar=a, aciklama=ac, birim=b) for a, ac, b in PARAMETRELER if a not in mevcut]
    s.add_all(yeni); s.flush()
    return len(yeni)


def fire_varsayilanlarini_tohumla(s: Session, senaryo_id: int, tarih: date) -> int:
    n = 0
    for tip, oran in FIRE_TIP_VARSAYILAN.items():
        var = s.scalar(select(m.FireKurali).where(m.FireKurali.senaryo_id == senaryo_id, m.FireKurali.kapsam_tipi == "tip", m.FireKurali.kapsam_deger == tip))
        if var is None:
            recete_servisi.fire_kurali_ekle(s, senaryo_id, "tip", tip, oran, tarih, "Excel analizinden varsayılan"); n += 1
    return n


if __name__ == "__main__":
    from .depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    e = motor_olustur(); Base.metadata.create_all(e)
    with oturum_fabrikasi(e)() as s:
        print("yeni parametre:", parametreleri_tohumla(s)); s.commit()
```

```python
# backend/servisler/import_servisi.py
"""Excel içe aktarma. Faz 1 excel_okuyucu'yu kullanır; önizleme olmadan fiyat yazmaz."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .. import tohum
from . import fiyat_servisi, gider_servisi, hesap_servisi, parametre_servisi, recete_servisi

HAVUZ_ESLEME = [  # (kod, ad, GiderHavuzlari alanı toplam, baz_tipi, baz alanı veya None, pay alanı veya None)
    ("dolum_iscilik", "Dolum doğrudan işçilik", "dolum_iscilik_toplam", "saniye", "dolum_iscilik_saniye", None),
    ("mal_kabul_iscilik", "Mal kabul doğrudan işçilik", "mal_kabul_iscilik_toplam", "kg", None, "mal_kabul_paylari"),
    ("etiket_iscilik", "Etiketleme doğrudan işçilik", "etiket_iscilik_toplam", "saniye", "etiket_iscilik_saniye", None),
    ("endirekt_iscilik", "Endirekt işçilik", "endirekt_iscilik_toplam", "saniye", "endirekt_saniye", None),
    ("mal_kabul_gug", "Mal kabul genel üretim gideri", "mal_kabul_gug_toplam", "kg", None, "mal_kabul_gug_paylari"),
    ("diger_gug", "Diğer genel üretim giderleri", "diger_gug_toplam", "saniye", "diger_gug_saniye", None),
    ("elektrik", "Elektrik", "elektrik_toplam", "saniye", None, "elektrik_hatlar"),
    ("dogalgaz", "Doğalgaz", "dogalgaz_toplam", "saniye", None, "dogalgaz_hatlar"),
    ("amortisman", "Amortisman", "amortisman_toplam", "saniye", None, "amortisman_hatlar"),
    ("yonetim", "Genel yönetim giderleri", "yonetim_toplam", "adet", None, None),
    ("pazarlama", "Pazarlama satış giderleri", "pazarlama_toplam", "adet", None, None),
]


def _sezon(s: Session, ad: str) -> m.Sezon:
    sz = s.scalar(select(m.Sezon).where(m.Sezon.ad == ad))
    if sz is None:
        y1 = int(ad.split("-")[0]); sz = m.Sezon(ad=ad, baslangic=date(y1, 6, 1), bitis=date(y1 + 1, 5, 31)); s.add(sz); s.flush()
    return sz


def _parametreleri_yaz(s, senaryo_id, p, tarih, neden):
    n = 0
    def ekle(a, v):
        nonlocal n; parametre_servisi.deger_ekle(s, senaryo_id, a, v, tarih, neden, olusturan="import"); n += 1
    ekle("enflasyon", p.enflasyon); ekle("satis_kar", p.satis_kar_orani); ekle("vardiya_saati", p.vardiya_saati)
    for pb, v in p.kurlar.items(): ekle(f"kur.{pb}", v)
    for pb, v in p.faiz_oranlari.items(): ekle(f"faiz.{pb}", v)
    for pb, v in p.stok_sureleri_ay.items(): ekle(f"stok_ay.{pb}", v)
    for i, v in enumerate(p.teklif_kar_oranlari, 1): ekle(f"teklif_kar.{i}", v)
    return n


def excel_tam_yukle(s: Session, excel_yolu: Path, sezon_ad: str, senaryo_ad: str, tur: str = "fiyat_calismasi", kullanici: str = "sistem") -> dict:
    wb_f, wb_v = eo.excel_ac(Path(excel_yolu))
    sz = _sezon(s, sezon_ad)
    sen = m.Senaryo(sezon_id=sz.id, tur=tur, ad=senaryo_ad, olusturan=kullanici); s.add(sen); s.flush()
    tohum.parametreleri_tohumla(s)
    ozet = {"senaryo_id": sen.id, "malzeme": 0, "fiyat": 0, "havuz": 0, "ambalaj": 0, "urun": 0, "recete": 0, "parametre": 0, "atlanan": [], "uyarilar": []}

    for kod, mz in eo.malzemeleri_oku(wb_v).items():
        fiyat_servisi.malzeme_ekle_veya_guncelle(s, kod, mz.ad, mz.tip, mz.birim, mz.para_birimi, mz.zs, kullanici); ozet["malzeme"] += 1
        if mz.fiyat and mz.fiyat != SIFIR:
            fiyat_servisi.fiyat_ekle(s, sen.id, kod, mz.fiyat, sz.baslangic, "Excel bütçe fiyatı", kaynak="import", olusturan=kullanici); ozet["fiyat"] += 1

    h = eo.havuzlari_oku(wb_v)
    for kod, ad, toplam_alani, baz_tipi, baz_alani, pay_alani in HAVUZ_ESLEME:
        paylar = [(k, p, b) for k, (p, b) in getattr(h, pay_alani).items()] if pay_alani else []
        gider_servisi.havuz_kaydet(s, sen.id, kod, ad, getattr(h, toplam_alani), baz_tipi, getattr(h, baz_alani) if baz_alani else None, paylar, kullanici)
        ozet["havuz"] += 1
    gider_servisi.ambalaj_kaydet(s, sen.id, [(a.ad, a.hacim, a.uretim_adedi, a.katsayi) for a in h.ambalajlar]); ozet["ambalaj"] = len(h.ambalajlar)

    sayfalar = eo.urun_sayfalarini_listele(wb_v)
    ilk = next(a for a in sayfalar if "(2)" not in a)
    _, p, _ = eo.urun_oku(wb_f[ilk], wb_v[ilk])
    ozet["parametre"] = _parametreleri_yaz(s, sen.id, p, sz.baslangic, f"Excel {ilk} sayfası")

    gorulen: set[str] = set()
    for ad in sayfalar:
        if "(2)" in ad:
            ozet["atlanan"].append(ad); continue
        try:
            girdi, _, _ = eo.urun_oku(wb_f[ad], wb_v[ad])
        except Exception as e:
            ozet["atlanan"].append(f"{ad}: {e}"); continue
        if girdi.kod in gorulen:
            ozet["uyarilar"].append(f"{ad}: ürün kodu {girdi.kod} daha önce yüklendi, yeni reçete versiyonu açıldı")
        gorulen.add(girdi.kod)
        u = hesap_servisi.urun_kaydet(s, girdi.kod, girdi.ad, girdi.uretim.ambalaj_hacmi, girdi.uretim.hat, girdi.uretim.taze_tursu_sinifi,
                                      girdi.uretim.suzme_kg, girdi.uretim.pazar, kullanici)
        ub = girdi.uretim
        hesap_servisi.uretim_hedefi_kaydet(s, u.id, sen.id, kullanici, vardiya_uretim_adedi=ub.vardiya_uretim_adedi, dolum_personel=ub.dolum_personel,
                                           etiketleme_adedi=ub.etiketleme_adedi, etiket_personel=ub.etiket_personel, mal_kabul_miktar_kg=ub.mal_kabul_miktar_kg,
                                           mal_kabul_fire=ub.mal_kabul_fire, pazarlama_yonetim_uygula=ub.pazarlama_yonetim_uygula)
        recete_servisi.yeni_versiyon(s, u.id, sen.id, [{"malzeme_kodu": r.malzeme_kodu, "ad": r.ad, "miktar": r.miktar, "birim": r.birim,
                                                        "fire_override": r.fire_orani} for r in girdi.recete], "import", kullanici)
        ozet["urun"] += 1; ozet["recete"] += 1

    tohum.fire_varsayilanlarini_tohumla(s, sen.id, sz.baslangic)
    s.flush()
    return ozet


def _fiyat_satirlari(dosya_yolu: Path):
    ws = openpyxl.load_workbook(dosya_yolu, data_only=True, read_only=True).worksheets[0]
    for satir in ws.iter_rows(min_row=2, values_only=True):
        if satir and satir[0]:
            yield str(satir[0]).strip(), satir[5] if len(satir) > 5 else None


def fiyat_listesi_onizle(s: Session, senaryo_id: int, dosya_yolu: Path, tarih: date | None = None) -> dict:
    mevcut = fiyat_servisi.gecerli_fiyatlar(s, senaryo_id, tarih or date.today())
    out = {"yeni": [], "degisen": [], "ayni": 0, "hatali": []}
    for kod, fiyat in _fiyat_satirlari(dosya_yolu):
        try:
            f = Decimal(str(fiyat)) if fiyat not in (None, "") else None
        except Exception:
            out["hatali"].append(kod); continue
        if f is None:
            continue
        if kod not in mevcut:
            out["yeni"].append({"kod": kod, "yeni": str(f)})
        elif mevcut[kod].fiyat != f:
            out["degisen"].append({"kod": kod, "eski": str(mevcut[kod].fiyat), "yeni": str(f)})
        else:
            out["ayni"] += 1
    return out


def fiyat_listesi_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date, neden: str, kullanici: str = "sistem") -> int:
    on = fiyat_listesi_onizle(s, senaryo_id, dosya_yolu, gecerlilik_basi)
    n = 0
    for d in on["degisen"]:
        fiyat_servisi.fiyat_ekle(s, senaryo_id, d["kod"], Decimal(d["yeni"]), gecerlilik_basi, neden, kaynak="import", olusturan=kullanici); n += 1
    return n
```
Not: `fiyat_listesi_onizle` yalnızca var olan malzemelerin fiyatını günceller; "yeni" malzemeler önizlemede listelenir ama kartı olmadığı için uygulanmaz (malzeme kartı açma Faz 4 arayüzünden veya `excel_tam_yukle` ile).

- [ ] **Step 4: Çalıştır, geçer** — 4 passed (Excel yoksa 3 skipped).

---

### Task 10: FastAPI uygulaması, şemalar ve router'lar

**Files:** Create `backend/uygulama.py`, `backend/api/__init__.py`, `backend/api/bagimliliklar.py`, `backend/api/semalar.py`, `backend/api/senaryolar.py`, `backend/api/parametreler.py`, `backend/api/malzemeler.py`, `backend/api/gider.py`, `backend/api/urunler.py`, `backend/api/teklifler.py`, `backend/api/fire.py`, `backend/api/import_.py`, `backend/api/disa_aktar.py`, `tests/backend/test_api.py`

**Interfaces:** Tasarım bölüm 4'teki uçlar, `/api/v1` öneki. `uygulama.uygulama_olustur(oturum_bagimliligi=None) -> FastAPI`. Hata eşleme: `BulunamadiHatasi` → 404, `DogrulamaHatasi` → 422, `RequestValidationError` → 422; gövde `{"hata","mesaj","alanlar"}`. Kullanıcı: `X-Kullanici` başlığı, yoksa `"sistem"`.

Pydantic (`semalar.py`): tüm `Decimal` alanlar `Decimal` tipinde; `model_config = ConfigDict(json_encoders={Decimal: str})` yerine Pydantic 2'nin varsayılanı (Decimal → JSON string) kullanılır. Örnek şemalar:
```python
class SenaryoGiris(BaseModel): sezon_ad: str; tur: Literal["fiyat_calismasi", "gerceklesen"]; ad: str; aciklama: str | None = None
class SenaryoCikis(BaseModel): id: int; sezon_ad: str; tur: str; ad: str
class ParametreDegerGiris(BaseModel): deger: Decimal; gecerlilik_basi: date; neden: str = Field(min_length=1); kapsam_tipi: Literal["genel","urun"]="genel"; kapsam_id: int | None=None
class FiyatGiris(BaseModel): fiyat: Decimal; gecerlilik_basi: date; neden: str = Field(min_length=1); para_birimi: str | None=None
class HavuzGiris(BaseModel): ad: str; toplam_tutar: Decimal; baz_tipi: Literal["saniye","kg","adet"]; baz_miktar: Decimal | None=None; anahtarlar: list[AnahtarGiris]=[]
class AnahtarGiris(BaseModel): alt_kalem: str; pay_orani: Decimal; baz_miktar: Decimal
class AmbalajGiris(BaseModel): ad: str; hacim: Decimal; uretim_adedi: Decimal; katsayi: Decimal
class UrunGiris(BaseModel): ad: str; ambalaj_hacmi: Decimal; hat: str; taze_tursu_sinifi: str; suzme_kg: Decimal; pazar: Literal["Yurtiçi","Yurtdışı"]="Yurtiçi"
class UretimHedefiGiris(BaseModel): vardiya_uretim_adedi: Decimal; dolum_personel: Decimal; etiketleme_adedi: Decimal; etiket_personel: Decimal; mal_kabul_miktar_kg: Decimal; mal_kabul_fire: Decimal=Decimal(0); pazarlama_yonetim_uygula: bool=True
class ReceteSatirGiris(BaseModel): malzeme_kodu: str; ad: str=""; miktar: Decimal; birim: str | None=None; fire_override: Decimal | None=None; dugum_tipi: Literal["yaprak","ara_mamul"]="yaprak"
class HesaplaGiris(BaseModel): senaryo_id: int; tarih: date | None=None; override: dict | None=None
class TeklifGiris(BaseModel): kar_orani: Decimal; musteri: str | None=None; notu: str | None=None
class FireKuraliGiris(BaseModel): kapsam_tipi: Literal["tip","grup","malzeme"]; kapsam_deger: str; oran: Decimal; gecerlilik_basi: date; neden: str
class GrupGiris(BaseModel): ad: str; malzeme_kodlari: list[str]
```
`POST /urunler/{kod}/hesapla` yanıtı tasarım bölüm 4'teki şekil: `satirlar` (her satıra `fire_orani`, `fire_kaynagi` eklenir), `toplamlar`, `fiyatlar`, `kullanilan_parametreler`, `uyarilar`; `donusum.decimal_str` ile üretilir.

`GET /urunler?senaryo=` dashboard satırı: `{kod, ad, ambalaj_hacmi, hat, recete_maliyeti(P100), gug(P114), faaliyet(P120), finans(P124), gider_yuzdesi((P114+P120+P124)/P130), maliyet_tl(P130), maliyet_usd, maliyet_eur, satis_tl, uretim_adedi, uyari_sayisi, hata}` — `hesap_servisi.toplu_hesapla` ile canlı hesaplanır (snapshot değil).

`GET /disa-aktar/urunler.xlsx?senaryo=`: openpyxl ile dashboard tablosu; `StreamingResponse`, `Content-Disposition: attachment; filename="urunler.xlsx"`.

`POST /import/excel-tam` (multipart `dosya`, form `sezon_ad`, `senaryo_ad`, `tur`): dosyayı geçici klasöre yazar, `excel_tam_yukle` çağırır, özeti döner. `POST /import/fiyat-listesi` → önizleme; `POST /import/fiyat-listesi/uygula` (`gecerlilik_basi`, `neden`) → yazılan sayı. Önizleme id'si yerine dosya iki istekte de gönderilir (durumsuz; basit).

- [ ] **Step 1: Test** — TestClient, bellek içi DB; `uygulama_olustur(oturum_bagimliligi=...)` ile test oturumu enjekte edilir.

```python
# tests/backend/test_api.py
from datetime import date
from decimal import Decimal as D_
import pytest
from fastapi.testclient import TestClient
from backend.uygulama import uygulama_olustur
from backend.depo.veritabani import oturum_ver
from backend.tohum import parametreleri_tohumla
from tests.backend.test_gider_servisi import tohumla as gider_tohumla


@pytest.fixture
def istemci(oturum):
    app = uygulama_olustur()
    app.dependency_overrides[oturum_ver] = lambda: oturum
    parametreleri_tohumla(oturum)
    return TestClient(app)


def _senaryo(c):
    r = c.post("/api/v1/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "A"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _kur(c, sid, oturum):
    for a, v in [("enflasyon", "0.25"), ("kur.USD", "50"), ("kur.EUR", "60"), ("faiz.TL", "0.4"), ("stok_ay.TL", "6"), ("faiz.USD", "0.06"),
                 ("stok_ay.USD", "6"), ("faiz.EUR", "0.06"), ("stok_ay.EUR", "6"), ("satis_kar", "0.2"), ("teklif_kar.1", "0.2"), ("vardiya_saati", "7.5")]:
        assert c.post(f"/api/v1/parametreler/{a}/degerler?senaryo={sid}", json={"deger": v, "gecerlilik_basi": "2026-06-01", "neden": "tohum"}).status_code == 201
    gider_tohumla(oturum, sid)
    c.post("/api/v1/malzemeler", json={"kod": "KAV", "ad": "Kavanoz", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "TL", "zs": "S"})
    assert c.post("/api/v1/malzemeler/KAV/fiyatlar?senaryo=%d" % sid, json={"fiyat": "5.9", "gecerlilik_basi": "2026-06-01", "neden": "bütçe"}).status_code == 201
    assert c.put("/api/v1/urunler/TEST", json={"ad": "Test", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"/api/v1/urunler/TEST/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000",
                 "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}).status_code == 200
    assert c.post(f"/api/v1/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "fire_override": "0.02"}]).status_code == 201


def test_hesapla_akisi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.post("/api/v1/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["satirlar"][0]["fire_kaynagi"] == "satir" and isinstance(g["toplamlar"]["maliyet_tl"], str)
    assert D_(g["satirlar"][0]["tutar"]) == D_("5.9") * D_("1.25") / D_("0.98")
    r2 = istemci.post("/api/v1/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}, headers={"X-Kullanici": "esma"})
    assert r2.status_code == 201 and r2.json()["olusturan"] == "esma"
    hid = r2.json()["id"]
    assert istemci.post(f"/api/v1/hesaplar/{hid}/teklifler", json={"kar_orani": "0.2"}).status_code == 201
    assert len(istemci.get(f"/api/v1/hesaplar/{hid}/teklifler").json()["kayitlar"]) == 1


def test_dashboard_ve_disa_aktar(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.get(f"/api/v1/urunler?senaryo={sid}")
    assert r.status_code == 200 and r.json()["toplam"] == 1 and r.json()["kayitlar"][0]["hata"] is None
    x = istemci.get(f"/api/v1/disa-aktar/urunler.xlsx?senaryo={sid}")
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_hata_govdesi(istemci):
    r = istemci.get("/api/v1/hesaplar/999")
    assert r.status_code == 404 and set(r.json()) == {"hata", "mesaj", "alanlar"}
    r = istemci.post("/api/v1/parametreler/yok.boyle/degerler?senaryo=1", json={"deger": "1", "gecerlilik_basi": "2026-06-01", "neden": "x"})
    assert r.status_code == 422


def test_parametre_gecmisi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    istemci.post(f"/api/v1/parametreler/kur.USD/degerler?senaryo={sid}", json={"deger": "55", "gecerlilik_basi": "2026-09-01", "neden": "zam"})
    g = istemci.get(f"/api/v1/parametreler/kur.USD/gecmis?senaryo={sid}").json()["kayitlar"]
    assert [x["deger"] for x in g] == ["55", "50"]
    assert istemci.get(f"/api/v1/parametreler?senaryo={sid}&tarih=2026-08-01").json()["kur.USD"] == "50"
```

- [ ] **Step 2: Çalıştır, başarısız**

- [ ] **Step 3: Uygulama** — Dosya başına iskelet:

```python
# backend/api/bagimliliklar.py
from fastapi import Header
from ..depo.veritabani import oturum_ver  # yeniden dışa aktarım; testler bunu override eder

def kullanici_ver(x_kullanici: str | None = Header(default=None)) -> str:
    return x_kullanici or "sistem"
```
```python
# backend/uygulama.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from .servisler.hatalar import BulunamadiHatasi, DogrulamaHatasi
from .api import senaryolar, parametreler, malzemeler, gider, urunler, teklifler, fire, import_, disa_aktar


def uygulama_olustur() -> FastAPI:
    app = FastAPI(title="Fiyat Çalışması API", version="0.2.0")
    for r in (senaryolar, parametreler, malzemeler, gider, urunler, teklifler, fire, import_, disa_aktar):
        app.include_router(r.router, prefix="/api/v1")

    @app.exception_handler(BulunamadiHatasi)
    async def _404(_: Request, e: BulunamadiHatasi):
        return JSONResponse(404, {"hata": "bulunamadi", "mesaj": e.mesaj, "alanlar": e.alanlar})

    @app.exception_handler(DogrulamaHatasi)
    async def _422(_: Request, e: DogrulamaHatasi):
        return JSONResponse(422, {"hata": "dogrulama", "mesaj": e.mesaj, "alanlar": e.alanlar})

    @app.exception_handler(RequestValidationError)
    async def _422b(_: Request, e: RequestValidationError):
        return JSONResponse(422, {"hata": "dogrulama", "mesaj": "istek gövdesi geçersiz", "alanlar": {".".join(str(p) for p in x["loc"]): x["msg"] for x in e.errors()}})
    return app


app = uygulama_olustur()   # uvicorn backend.uygulama:app
```
Router örneği (`parametreler.py`); diğerleri aynı kalıpla servis çağırır, `decimal_str` ile döner:
```python
# backend/api/parametreler.py
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..servisler import parametre_servisi as ps
from ..servisler.donusum import decimal_str
from .bagimliliklar import kullanici_ver, oturum_ver
from .semalar import ParametreDegerGiris

router = APIRouter(tags=["parametreler"])


@router.get("/parametreler")
def gecerli(senaryo: int, tarih: date | None = None, urun_id: int | None = None, s: Session = Depends(oturum_ver)):
    return decimal_str(ps.gecerli_degerler(s, senaryo, tarih or date.today(), urun_id))


@router.post("/parametreler/{anahtar}/degerler", status_code=201)
def ekle(anahtar: str, g: ParametreDegerGiris, senaryo: int = Query(...), s: Session = Depends(oturum_ver), k: str = Depends(kullanici_ver)):
    d = ps.deger_ekle(s, senaryo, anahtar, g.deger, g.gecerlilik_basi, g.neden, g.kapsam_tipi, g.kapsam_id, k)
    return {"id": d.id, "deger": str(d.deger), "gecerlilik_basi": d.gecerlilik_basi.isoformat()}


@router.get("/parametreler/{anahtar}/gecmis")
def gecmis(anahtar: str, senaryo: int, s: Session = Depends(oturum_ver)):
    k = [{"id": x.id, "deger": str(x.deger), "gecerlilik_basi": x.gecerlilik_basi.isoformat(), "neden": x.neden, "kapsam_tipi": x.kapsam_tipi,
          "kapsam_id": x.kapsam_id, "olusturan": x.olusturan, "olusturma_zamani": x.olusturma_zamani.isoformat()} for x in ps.gecmis(s, senaryo, anahtar)]
    return {"kayitlar": k, "toplam": len(k)}
```
`urunler.py` hesapla yanıtı:
```python
def _hesap_yaniti(c, urun_kodu, senaryo_id, tarih):
    r = c.sonuc
    satirlar = [dict(decimal_str(s_), fire_orani=str(c.girdi.recete[i].fire_orani) if i < len(c.girdi.recete) else None,
                     fire_kaynagi=c.fire_kaynaklari[i] if i < len(c.fire_kaynaklari) else None) for i, s_ in enumerate(r.satirlar)]
    return {"urun_kodu": urun_kodu, "senaryo_id": senaryo_id, "hesap_tarihi": tarih.isoformat(), "satirlar": satirlar,
            "toplamlar": decimal_str({"malzeme": r.malzeme_toplami, "direkt_iscilik": r.direkt_iscilik_toplami, "gug": r.gug_toplami, "uretim_gideri": r.uretim_gideri_toplami,
                                      "diger": r.diger_giderler_toplami, "giydirilmis": r.giydirilmis_maliyet, "finansman_tl": r.finansman.get("TL"),
                                      "maliyet_tl": r.finansman_dahil_maliyet_tl, "maliyet_usd": r.doviz_maliyet.get("USD"), "maliyet_eur": r.doviz_maliyet.get("EUR")}),
            "fiyatlar": decimal_str({"satis_tl": r.satis_fiyati_tl, "satis_usd": r.satis_fiyati_doviz.get("USD"), "satis_eur": r.satis_fiyati_doviz.get("EUR"),
                                     "suzme_kg_tl": r.suzme_kg_fiyati_tl, "teklifler_usd": r.teklifler_usd}),
            "kullanilan_parametreler": decimal_str(c.kullanilan_parametreler), "uyarilar": r.uyarilar}
```
Uçlar: `GET /urunler`, `GET/PUT /urunler/{kod}`, `PUT /urunler/{kod}/uretim-hedefi?senaryo=`, `GET/POST /urunler/{kod}/recete?senaryo=`, `POST /urunler/{kod}/hesapla`, `POST /urunler/{kod}/hesaplar` (201, `{"id","olusturan","hesap_tarihi"}`), `GET /hesaplar/{id}` (snapshot'lar + uyarılar); `teklifler.py`: `POST/GET /hesaplar/{id}/teklifler`, `PATCH /teklifler/{id}/durum`; `malzemeler.py`: `GET /malzemeler?senaryo=&fiyatsiz=&sayfa=&boyut=`, `POST /malzemeler` (kart), `POST/GET /malzemeler/{kod}/fiyatlar?senaryo=`; `gider.py`: `GET /gider-havuzlari?senaryo=` (havuzlar + `pay_kontrol`), `PUT /gider-havuzlari/{kod}?senaryo=`, `GET/PUT /ambalaj-siniflari?senaryo=`; `fire.py`: `GET/POST /fire-kurallari?senaryo=`, `POST /malzeme-gruplari`; `senaryolar.py`: `GET/POST /senaryolar` (POST 201; sezon adı yoksa `_sezon` mantığı import servisinden alınır: `import_servisi._sezon`); `import_.py`: `POST /import/excel-tam`, `POST /import/fiyat-listesi`, `POST /import/fiyat-listesi/uygula`; `disa_aktar.py`: `GET /disa-aktar/urunler.xlsx?senaryo=`.

- [ ] **Step 4: Çalıştır, geçer** — 4 passed. Sunucuyu elle kontrol: `.\.venv\Scripts\python -m uvicorn backend.uygulama:app --reload` → `http://127.0.0.1:8000/docs` açılır.

---

### Task 11: Uçtan uca Excel testi (`test_uctan_uca_excel.py`)

**Files:** Create `tests/backend/test_uctan_uca_excel.py`

**Interfaces:** Consumes `import_servisi.excel_tam_yukle`, `hesap_servisi.hesapla`, `fiyat_motoru.excel_okuyucu.urun_oku`, `tests/test_excel_paritesi.BILINEN_ISTISNALAR`.

Kanıt: Excel → veritabanı → servis katmanı → motor zinciri, Faz 1'in doğrudan Excel'den hesapladığı sonucun aynısını verir (P100, P114, P120, P124, P130, P131, P137, P145-147), bilinen istisnalar hariç.

- [ ] **Step 1: Test**

```python
# tests/backend/test_uctan_uca_excel.py
"""Excel → import → servis hesabı, Faz 1 parite değerleriyle (ve dolayısıyla Excel'le) aynı olmalı."""
from datetime import date
from decimal import Decimal
import pytest
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
from backend.servisler import hesap_servisi as hs, import_servisi as ims
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import TOLERANS
from tests.test_excel_paritesi import BILINEN_ISTISNALAR

ALANLAR = {"P100": lambda r: r.malzeme_toplami, "P114": lambda r: r.uretim_gideri_toplami, "P120": lambda r: r.diger_giderler_toplami,
           "P124": lambda r: r.finansman["TL"], "P130": lambda r: r.finansman_dahil_maliyet_tl, "P131": lambda r: r.doviz_maliyet["USD"],
           "P137": lambda r: r.satis_fiyati_tl, "P145": lambda r: r.teklifler_usd[0], "P146": lambda r: r.teklifler_usd[1], "P147": lambda r: r.teklifler_usd[2]}


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak"); s.commit()
    wb_f, wb_v = eo.excel_ac(excel_yolu)
    yield s, ozet, wb_f, wb_v
    s.close()


def test_tum_urunler_excel_ile_ayni(ortam):
    s, ozet, wb_f, wb_v = ortam
    farklar = []
    for ad in eo.urun_sayfalarini_listele(wb_v):
        if "(2)" in ad or any(ad in a for a in ozet["atlanan"]):
            continue
        girdi, _, bek = eo.urun_oku(wb_f[ad], wb_v[ad])
        c = hs.hesapla(s, girdi.kod, ozet["senaryo_id"], date(2026, 10, 21))
        for alan, al in ALANLAR.items():
            if (ad, alan) in BILINEN_ISTISNALAR:
                continue
            if abs(bek[alan] - al(c.sonuc)) >= TOLERANS:
                farklar.append((ad, alan, bek[alan], al(c.sonuc)))
    assert farklar == [], "\n".join(f"{a} {b}: excel={c} servis={d}" for a, b, c, d in farklar[:30])
```

Not: Aynı ürün kodu birden çok sayfada varsa son yüklenen reçete aktiftir; o ürünün ilk sayfası fark verebilir. Bu durumda test `BILINEN_ISTISNALAR`'a değil, bu dosyadaki ayrı bir `COKLU_SAYFA = {...}` kümesine (sayfa adı + gerekçe) alınır ve `continue` ile atlanır; gerekçe yazılmadan atlanamaz.

- [ ] **Step 2: Çalıştır** — `.\.venv\Scripts\python -m pytest tests/backend/test_uctan_uca_excel.py -v`. Fark çıkarsa kaynağını bul: servis katmanında veri kaybı (örn. `zs`, `para_birimi`, fire, `pazarlama_yonetim_uygula`, parametre eşleme) mi, yoksa Faz 1 istisnası mı. Servis hatası ise ilgili servis testini genişletip düzelt.

- [ ] **Step 3: Tüm süit** — `.\.venv\Scripts\python -m pytest -q` → tamamı geçer, uyarı yok.

- [ ] **Step 4: Belgeye işle** — `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` sonuna "Faz 2 sonucu" başlığı: uçtan uca test sonucu, API'nin çalıştırılma komutu, bilinen eksikler.

---

## Self-review notları

- **Spec kapsamı:** Tasarım bölüm 2 tabloları → T2; bölüm 3 servisleri → T3-T9 (`karsilastirma_servisi` Faz 5, planda yok — bilinçli); bölüm 4 uçları → T10 (`/karsilastirma` hariç); import → T9; versiyonlama ilkesi → T3/T4/T6 testleriyle kanıtlı; "gerçekleşen → enflasyon 0" → T7 testi; uçtan uca kanıt → T11.
- **Tip tutarlılığı:** `gider_servisi.havuz_kaydet` anahtar tuple sırası `(alt_kalem, pay, baz)` T5 testi, T9 `HAVUZ_ESLEME` ve `_paylar` ile aynı; `recete_servisi.yeni_versiyon` satır dict anahtarları T6/T7/T9/T10'da aynı; `hesap_servisi.uretim_hedefi_kaydet(**alanlar)` alan adları `URETIM_ALANLARI` ile T7/T9/T10'da aynı; `HesapCiktisi` alanları T7/T10/T11'de aynı.
- **Bilinen risk:** T10 `GET /urunler` 67 ürünü her istekte canlı hesaplar; yerel SQLite'ta milisaniyeler, kabul. T9 `fiyat_listesi_onizle` sütun konumu `S.ALMA BF` düzenine bağlı (A kod, F fiyat); farklı dosya düzeni Faz 4'te eşleme ekranıyla gelir.
- **Git yok:** commit adımları yazılmadı.
