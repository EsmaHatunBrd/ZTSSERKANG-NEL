"""Engine, oturum ve Decimal'i kayıpsız saklayan ParaTipi."""
from decimal import Decimal
from pathlib import Path
from sqlalchemy import String, TypeDecorator, create_engine, event, text
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
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30},
                           poolclass=StaticPool if bellek_ici else None)

    @event.listens_for(engine, "connect")
    def _pragmalar(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if not bellek_ici:
            cur.execute("PRAGMA journal_mode=WAL")
        cur.close()
    return engine


# create_all mevcut tabloya kolon eklemez: sonradan eklenen kolonlar burada (tablo, kolon, SQL türü) olarak bildirilir.
EKSIK_KOLONLAR = (("recete_satiri", "seviye", "INTEGER"), ("urun", "aile", "VARCHAR(120)"),
                 ("senaryo", "kilitli", "BOOLEAN DEFAULT 0"), ("senaryo", "kaynak_dosya", "VARCHAR(200)"),
                 ("gider_havuzu", "taban_tutar", "VARCHAR(48)"), ("gider_havuzu", "carpanlar", "JSON"),
                 ("urun", "aile_ad", "VARCHAR(120)"))


def eksik_kolonlari_tamamla(engine: Engine) -> list[str]:
    """Mevcut (eski şemalı) veritabanı dosyasına eksik kolonları ekler; idempotent. Eklenenleri 'tablo.kolon' olarak döner."""
    eklenen = []
    with engine.begin() as c:
        for tablo, kolon, tur in EKSIK_KOLONLAR:
            mevcut = {satir[1] for satir in c.execute(text(f"PRAGMA table_info({tablo})"))}
            if mevcut and kolon not in mevcut:
                c.execute(text(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tur}"))
                eklenen.append(f"{tablo}.{kolon}")
    return eklenen


def oturum_fabrikasi(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


_ENGINE: Engine | None = None
_SESSION: sessionmaker | None = None


def oturum_ver():
    """FastAPI dependency: istek başına bir oturum; router commit/rollback'i burada."""
    global _ENGINE, _SESSION
    if _SESSION is None:
        try:   # günlük otomatik yedek (şema değişmeden ÖNCE, tutarlı kopya); hata uygulamayı düşürmez
            from .yedek import gunluk_yedek_al
            gunluk_yedek_al(AYARLAR.veritabani_url)
        except Exception as e:   # noqa: BLE001 — yedek alınamaması açılışı engellememeli
            import logging
            logging.getLogger("fiyat").warning("otomatik yedek alınamadı: %s", e)
        _ENGINE = motor_olustur()
        Base.metadata.create_all(_ENGINE)
        eksik_kolonlari_tamamla(_ENGINE)
        _SESSION = oturum_fabrikasi(_ENGINE)
        from ..tohum import parametreleri_tohumla   # döngüsel içe aktarmayı önlemek için burada; idempotent
        from ..servisler.aile import aileleri_doldur
        with _SESSION() as ilk:
            parametreleri_tohumla(ilk); aileleri_doldur(ilk); ilk.commit()
    s = _SESSION()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
