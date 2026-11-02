from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column
from backend.depo.veritabani import Base, ParaTipi, motor_olustur, oturum_fabrikasi


class _Deneme(Base):
    __tablename__ = "_deneme"
    id: Mapped[int] = mapped_column(primary_key=True)
    tutar: Mapped[Decimal | None] = mapped_column(ParaTipi)


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
