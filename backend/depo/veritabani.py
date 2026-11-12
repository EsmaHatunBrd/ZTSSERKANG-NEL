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
                 ("urun", "aile_ad", "VARCHAR(120)"), ("uretim_hedefi", "gider_elle", "JSON"),
                 ("recete_satiri", "zs_elle", "VARCHAR(1)"), ("recete_satiri", "para_birimi_elle", "VARCHAR(8)"),
                 ("smm_donem", "dagitim", "JSON"), ("smm_donem", "dagitim_excel", "JSON"), ("smm_donem", "gider_mizan", "JSON"),
                 ("smm_donem", "excel_asama", "JSON"), ("smm_kalem", "envanterde", "BOOLEAN DEFAULT 1"),
                 ("smm_iscilik", "mamul_kod", "VARCHAR(40)"), ("smm_iscilik", "yari_mamul_kod", "VARCHAR(40)"),
                 ("smm_donem", "asama_elle", "JSON"), ("smm_recete_satiri", "ozel", "JSON"), ("smm_kalem", "uretim_asamasi", "INTEGER"),
                 ("smm_kalem", "satis_miktar", "VARCHAR(48)"), ("smm_kalem", "sahit_miktar", "VARCHAR(48)"), ("smm_donem", "excel_ozet", "JSON"),
                 ("smm_donem", "recete_kaynagi", "VARCHAR(10) DEFAULT 'excel'"), ("smm_donem", "devir_donem_id", "INTEGER"),
                 ("smm_donem", "veri_kaynaklari", "JSON"), ("smm_donem", "kilitli", "BOOLEAN DEFAULT 0"), ("smm_donem", "kilitleyen", "VARCHAR(64)"),
                 ("urun", "marka", "VARCHAR(64)"))


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


def _benzersiz_kolonlar(c, tablo: str) -> list[set[str]]:
    """Tablonun UNIQUE indekslerinin kolon kümeleri (UniqueConstraint SQLite'ta sqlite_autoindex olarak görünür)."""
    out = []
    for satir in c.execute(text(f"PRAGMA index_list({tablo})")):
        if satir[2]:   # unique
            out.append({k[2] for k in c.execute(text(f"PRAGMA index_info('{satir[1]}')"))})
    return out


def liste_fiyati_gocu(engine: Engine) -> bool:
    """liste_fiyati tablosunu (urun_id, yil) benzersizliğinden (urun_id, yil, pazar) benzersizliğine taşır. SQLite kısıt değiştiremediği
    için tablo yeniden kurulur: eski tablo adı değişir, ORM şemasıyla yeni tablo oluşur, satırlar pazar='yurtici' (bolen boş) ile kopyalanır,
    eski tablo düşer. İdempotent: tablo yoksa ya da zaten yeni şemadaysa hiçbir şey yapmaz. Dönüş: göç yapıldı mı."""
    from .modeller import ListeFiyati   # modeller bu modülü içe aktarır: döngü olmasın diye burada
    with engine.begin() as c:
        kolonlar = [satir[1] for satir in c.execute(text("PRAGMA table_info(liste_fiyati)"))]
        if not kolonlar:
            return False
        benzersiz = _benzersiz_kolonlar(c, "liste_fiyati")
        if "pazar" in kolonlar and {"urun_id", "yil", "pazar"} in benzersiz and {"urun_id", "yil"} not in benzersiz:
            return False
        c.execute(text("DROP TABLE IF EXISTS liste_fiyati_eski"))
        c.execute(text("ALTER TABLE liste_fiyati RENAME TO liste_fiyati_eski"))
        ListeFiyati.__table__.create(c)
        yeni = [col.name for col in ListeFiyati.__table__.columns]
       
        ortak = [k for k in yeni if k in kolonlar and k not in ("pazar", "bolen")]
        bos_ise = {"olusturma_zamani": "CURRENT_TIMESTAMP", "olusturan": "'sistem'", "ornek": "0"}   # NOT NULL kolonlarda boş eski değer
        secim = [f"COALESCE({k}, {bos_ise[k]})" if k in bos_ise else k for k in ortak]
        pazar = "COALESCE(pazar, 'yurtici')" if "pazar" in kolonlar else "'yurtici'"
        bolen = "bolen" if "bolen" in kolonlar else "NULL"
        c.execute(text(f"INSERT INTO liste_fiyati ({', '.join(ortak)}, pazar, bolen) SELECT {', '.join(secim)}, {pazar}, {bolen} FROM liste_fiyati_eski"))
        c.execute(text("DROP TABLE liste_fiyati_eski"))
    return True


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
        liste_fiyati_gocu(_ENGINE)
        eksik_kolonlari_tamamla(_ENGINE)
        _SESSION = oturum_fabrikasi(_ENGINE)
        from ..tohum import parametreleri_tohumla, markalari_doldur   # döngüsel içe aktarmayı önlemek için burada; idempotent
        from ..servisler.aile import aileleri_doldur
        with _SESSION() as ilk:
            parametreleri_tohumla(ilk); aileleri_doldur(ilk); markalari_doldur(ilk); ilk.commit()
    s = _SESSION()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
