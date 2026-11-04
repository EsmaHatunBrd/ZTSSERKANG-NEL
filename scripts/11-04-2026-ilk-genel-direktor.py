"""İlk Genel Direktör hesabını açar (giriş ekranından önce bir kez). Geçici şifre üretilir ve yalnız ekrana yazılır; ilk girişte
kullanıcı kendi şifresini belirler. Veritabanında zaten aktif bir Genel Direktör varsa hiçbir şey yapmaz.
Kullanıcı ve oturum tabloları yoksa oluşturulur (diğer tablolara dokunulmaz).

Kullanım: .venv/Scripts/python scripts/11-04-2026-ilk-genel-direktor.py [--db veri/fiyat.db] [--kullanici direktor] [--ad "Genel Direktör"]
"""
import argparse
import secrets
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from sqlalchemy import select  # noqa: E402
from backend.depo import modeller as m  # noqa: E402
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi  # noqa: E402
from backend.servisler import kimlik_servisi as ks  # noqa: E402


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--db", default=str(KOK / "veri" / "fiyat.db"))
    a.add_argument("--kullanici", default="direktor")
    a.add_argument("--ad", default="Genel Direktör")
    g = a.parse_args()
    db = Path(g.db).resolve()
    if not db.exists():
        raise SystemExit(f"veritabanı yok: {db}")
    engine = motor_olustur(f"sqlite:///{db.as_posix()}")
    Base.metadata.create_all(engine, tables=[m.Kullanici.__table__, m.GirisOturumu.__table__])
    with oturum_fabrikasi(engine)() as s:
        var = s.scalar(select(m.Kullanici).where(m.Kullanici.rol == ks.YONETICI_ROL, m.Kullanici.aktif == True))  # noqa: E712
        if var is not None:
            print(f"zaten aktif bir Genel Direktör var: {var.kullanici_adi}; hiçbir şey yapılmadı.")
            return
        sifre = secrets.token_urlsafe(9)
        ks.kullanici_olustur(s, g.kullanici, g.ad, ks.YONETICI_ROL, sifre, olusturan="kurulum")
        s.commit()
    print(f"Genel Direktör hesabı açıldı.\n  kullanıcı adı: {g.kullanici}\n  geçici şifre : {sifre}\n"
          "İlk girişte kendi şifrenizi belirlemeniz istenecek. Bu şifre başka yerde saklanmaz.")


if __name__ == "__main__":
    main()
