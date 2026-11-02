import sqlite3
from datetime import date

from backend.depo import yedek


def _db_olustur(yol):
    c = sqlite3.connect(str(yol))
    c.execute("create table t(x)")
    c.execute("insert into t values (1)")
    c.commit()
    c.close()


def test_gunluk_yedek_alinir_ve_ayni_gun_tekrarlanmaz(tmp_path):
    kaynak = tmp_path / "fiyat.db"
    _db_olustur(kaynak)
    url = f"sqlite:///{kaynak}"
    hedef = yedek.gunluk_yedek_al(url, bugun=date(2026, 10, 22))
    assert hedef is not None and hedef.name == "10-22-2026-otomatik-fiyat.db"
    assert sqlite3.connect(str(hedef)).execute("select count(*) from t").fetchone()[0] == 1
    assert yedek.gunluk_yedek_al(url, bugun=date(2026, 10, 22)) is None


def test_eski_otomatik_yedekler_budanir_elle_olanlar_kalir(tmp_path):
    kaynak = tmp_path / "fiyat.db"
    _db_olustur(kaynak)
    url = f"sqlite:///{kaynak}"
    klasor = tmp_path / "yedek"
    klasor.mkdir()
    (klasor / "10-22-2026-bosaltma-oncesi-fiyat.db").write_bytes(b"elle")
    for gun in range(1, 16):
        yedek.gunluk_yedek_al(url, bugun=date(2026, 9, gun), tut=14)
    yedek.gunluk_yedek_al(url, bugun=date(2026, 9, 16), tut=14)
    otomatik = sorted(p.name for p in klasor.glob("*-otomatik-fiyat.db"))
    assert len(otomatik) == 14 and otomatik[0] == "09-03-2026-otomatik-fiyat.db"
    assert (klasor / "10-22-2026-bosaltma-oncesi-fiyat.db").exists()
    assert any(y["ad"].endswith("bosaltma-oncesi-fiyat.db") and not y["otomatik"] for y in yedek.yedekleri_listele(url))


def test_bellek_ici_ve_yok_dosya_atlanir(tmp_path):
    assert yedek.gunluk_yedek_al("sqlite://") is None
    assert yedek.gunluk_yedek_al(f"sqlite:///{tmp_path / 'yok.db'}") is None


def test_silme_oncesi_yedekler_14_gunden_eskiyse_budanir(tmp_path):
    """B5: yalnız '…-silme-oncesi-<ad>.db' yedekleri 14 günden eskiyse silinir; elle alınanlar ve otomatikler kalır.
    Budama hem günlük yedekte hem yeni silme yedeği alınırken çalışır."""
    db = tmp_path / "fiyat.db"
    sqlite3.connect(db).close()
    klasor = tmp_path / "yedek"; klasor.mkdir()
    for ad in ("10-01-2026-silme-oncesi-Eski.db", "10-12-2026-silme-oncesi-Sinirda.db", "10-20-2026-silme-oncesi-Yeni.db",
               "10-01-2026-revize-oncesi-fiyat.db", "10-01-2026-bosaltma-oncesi-fiyat.db", "99-99-2026-silme-oncesi-Bozuk.db"):
        (klasor / ad).write_bytes(b"x")
    yedek.gunluk_yedek_al(f"sqlite:///{db}", bugun=date(2026, 10, 26))
    kalan = {p.name for p in klasor.iterdir()}
    assert "10-01-2026-silme-oncesi-Eski.db" not in kalan
    assert {"10-12-2026-silme-oncesi-Sinirda.db", "10-20-2026-silme-oncesi-Yeni.db", "10-01-2026-revize-oncesi-fiyat.db",
            "10-01-2026-bosaltma-oncesi-fiyat.db", "99-99-2026-silme-oncesi-Bozuk.db", "10-26-2026-otomatik-fiyat.db"} <= kalan
    yedek.silme_oncesi_yedek_al(f"sqlite:///{db}", "Yeni senaryo", bugun=date(2026, 11, 2))   # sınır 19.10: 20.10 kalır, 12.10 gider
    kalan = {p.name for p in klasor.iterdir()}
    assert "10-20-2026-silme-oncesi-Yeni.db" in kalan and "10-12-2026-silme-oncesi-Sinirda.db" not in kalan
    assert "11-02-2026-silme-oncesi-Yeni-senaryo.db" in kalan
