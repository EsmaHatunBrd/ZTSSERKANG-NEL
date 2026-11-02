"""Günlük otomatik yedek: SQLite dosyasını tutarlı biçimde (backup API, WAL dahil) tarihli kopyalar.

Tek süreç varsayımı. Açılışta çağrılır; o güne ait yedek varsa bir şey yapmaz. Son `tut` gün saklanır.
Bellek içi (`sqlite://`) ya da SQLite olmayan URL'lerde işlem yapılmaz.
"""
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

YEDEK_DESENI = re.compile(r"^(\d{2}-\d{2}-\d{4})-otomatik-(.+\.db)$")
SILME_DESENI = re.compile(r"^(\d{2}-\d{2}-\d{4})-silme-oncesi-.+\.db$")
SILME_TUT_GUN = 14


def yedek_yolu(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    return Path(url.removeprefix("sqlite:///"))


def gunluk_yedek_al(url: str, bugun: date | None = None, tut: int = 14) -> Path | None:
    """Yedek alındıysa yolunu, atlandıysa None döner. Hata durumunda uygulamayı düşürmez (çağıran loglar)."""
    kaynak = yedek_yolu(url)
    if kaynak is None or not kaynak.exists():
        return None
    bugun = bugun or date.today()
    klasor = kaynak.parent / "yedek"
    klasor.mkdir(parents=True, exist_ok=True)
    hedef = klasor / f"{bugun.strftime('%m-%d-%Y')}-otomatik-{kaynak.name}"
    if hedef.exists():
        return None
    src = sqlite3.connect(str(kaynak))
    try:
        dst = sqlite3.connect(str(hedef))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    _eskileri_sil(klasor, kaynak.name, tut)
    silme_yedeklerini_buda(klasor, bugun)
    return hedef


def _eskileri_sil(klasor: Path, dosya_adi: str, tut: int) -> None:
    """Yalnız bu modülün ürettiği (…-otomatik-<ad>) yedekleri budar; elle alınan yedeklere dokunmaz."""
    adaylar = []
    for p in klasor.iterdir():
        m = YEDEK_DESENI.match(p.name)
        if m and m.group(2) == dosya_adi:
            ay, gun, yil = m.group(1).split("-")
            adaylar.append((f"{yil}-{ay}-{gun}", p))
    for _, p in sorted(adaylar)[:-tut] if len(adaylar) > tut else []:
        p.unlink(missing_ok=True)


def silme_yedeklerini_buda(klasor: Path, bugun: date | None = None, gun: int = SILME_TUT_GUN) -> list[Path]:
    """Yalnız senaryo silme öncesi yedeklerini (…-silme-oncesi-<ad>.db) budar: dosya adındaki tarih `gun` günden eskiyse silinir.
    Elle alınanlar (revize-oncesi, bosaltma-oncesi …) ve otomatik günlük yedekler bu kurala girmez. Dönüş: silinen dosyalar."""
    if not klasor.exists():
        return []
    sinir = (bugun or date.today()) - timedelta(days=gun)
    silinen = []
    for p in klasor.iterdir():
        m = SILME_DESENI.match(p.name)
        if not m:
            continue
        ay, gn, yil = (int(x) for x in m.group(1).split("-"))
        try:
            tarih = date(yil, ay, gn)
        except ValueError:
            continue
        if tarih < sinir:
            p.unlink(missing_ok=True)
            silinen.append(p)
    return silinen


def yedekleri_listele(url: str) -> list[dict]:
    kaynak = yedek_yolu(url)
    if kaynak is None:
        return []
    klasor = kaynak.parent / "yedek"
    if not klasor.exists():
        return []
    out = []
    for p in sorted(klasor.glob("*.db")):
        out.append({"ad": p.name, "boyut": p.stat().st_size, "otomatik": bool(YEDEK_DESENI.match(p.name))})
    return out


def _dosya_adi_guvenli(ad: str) -> str:
    """Senaryo adını dosya adına uygun kısaltır: harf/rakam/-/_ dışındakiler '-' olur, en çok 60 karakter."""
    ad = re.sub(r"[^\w\-]+", "-", (ad or "").strip(), flags=re.UNICODE).strip("-")
    return (ad or "senaryo")[:60]


def silme_oncesi_yedek_al(url: str, ad: str, bugun: date | None = None) -> Path | None:
    """Yıkıcı işlem öncesi tutarlı kopya: `yedek/<MM-DD-YYYY>-silme-oncesi-<ad>.db`. Aynı gün aynı ad tekrar silinirse -2, -3 eklenir.
    Bellek içi/dosyasız URL'de None döner (çağıran atlar). Otomatik yedek budamasından etkilenmez (desen farklı)."""
    kaynak = yedek_yolu(url)
    if kaynak is None or not kaynak.exists():
        return None
    bugun = bugun or date.today()
    klasor = kaynak.parent / "yedek"
    klasor.mkdir(parents=True, exist_ok=True)
    govde = f"{bugun.strftime('%m-%d-%Y')}-silme-oncesi-{_dosya_adi_guvenli(ad)}"
    hedef = klasor / f"{govde}.db"
    n = 2
    while hedef.exists():
        hedef = klasor / f"{govde}-{n}.db"; n += 1
    silme_yedeklerini_buda(klasor, bugun)
    src = sqlite3.connect(str(kaynak))
    try:
        dst = sqlite3.connect(str(hedef))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return hedef
