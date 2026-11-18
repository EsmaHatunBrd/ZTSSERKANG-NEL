"""Faz 4b-ek: 'Mevcut senaryoyu tamamla' içe aktarma modu (şirket verisi yok: yalnız sayımlar)."""
from datetime import date
from decimal import Decimal as D_
import pytest
from sqlalchemy import delete
from backend.depo import modeller as m
from backend.servisler import import_servisi as ims, parametre_servisi as ps
from backend.servisler.hatalar import BulunamadiHatasi
from tests.backend.test_api import istemci  # noqa: F401


@pytest.fixture
def yuklu(excel_yolu):
    from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak fiyat çalışması")
    s.commit()
    yield s, ozet
    s.close()


def _say(s):
    return {t.__tablename__: s.query(t).count() for t in (m.Urun, m.Recete, m.ReceteSatiri, m.Malzeme, m.MalzemeFiyati, m.Senaryo, m.Sezon,
                                                           m.GiderHavuzu, m.UretimHedefi)}


def test_yeni_mod_ozeti_zar_rub_sapma_not(yuklu):
    s, o = yuklu
    assert o["mod"] == "yeni" and o["satis_notu"] == 1
    p = ps.gecerli_parametreler(s, o["senaryo_id"], date(2026, 10, 21))
    assert p.kurlar["ZAR"] > 0 and p.kurlar["RUB"] > 0
    assert [k.anahtar for k in ps.metin_gecerli(s, o["senaryo_id"], date(2026, 10, 21))] == ["satis_fiyati_notu"]


def test_tamamla_eksikleri_doldurur(yuklu, excel_yolu):
    s, o = yuklu
    sid = o["senaryo_id"]
    n_kap = s.query(m.UretimKapasitesi).count()
    assert n_kap == 71
    s.execute(delete(m.UretimKapasitesi))
    zar = s.query(m.Parametre).filter_by(anahtar="kur.ZAR").one()
    s.execute(delete(m.ParametreDegeri).where(m.ParametreDegeri.parametre_id == zar.id))
    s.execute(delete(m.MetinParametre))
    s.flush()
    onceki = _say(s)
    t = ims.excel_tam_yukle(s, excel_yolu, "x", "y", senaryo_id=sid)
    assert t["mod"] == "tamamla" and t["senaryo_id"] == sid
    assert t["kapasite"] == 71 and s.query(m.UretimKapasitesi).count() == 71
    assert t["satis_notu"] == 1 and len(ps.metin_gecerli(s, sid, date(2026, 10, 21))) == 1
    assert ps.gecerli_parametreler(s, sid, date(2026, 10, 21)).kurlar["ZAR"] > 0
    assert t["parametre"] == 1 and t["recete"] == 0 and t["urun"] == 0 and t["malzeme"] == 0 and t["fiyat"] == 0
    assert _say(s) == onceki
    assert s.query(m.Senaryo).count() == 1 and s.query(m.Sezon).count() == 1


def test_tamamla_ikinci_kez_hicbir_sey_eklemez(yuklu, excel_yolu):
    s, o = yuklu
    onceki = _say(s); par = s.query(m.ParametreDegeri).count(); kap = s.query(m.UretimKapasitesi).count()
    t = ims.excel_tam_yukle(s, excel_yolu, "x", "y", senaryo_id=o["senaryo_id"])
    assert (t["parametre"], t["kapasite"], t["satis_notu"], t["urun"], t["recete"], t["fiyat"], t["malzeme"], t["havuz"], t["ambalaj"]) == (0,) * 9
    assert _say(s) == onceki and s.query(m.ParametreDegeri).count() == par and s.query(m.UretimKapasitesi).count() == kap


def test_tamamla_bos_senaryoya_urun_recete_fiyat_ekler(yuklu, excel_yolu):
    s, o = yuklu
    sz = s.query(m.Sezon).one()
    bos = m.Senaryo(sezon_id=sz.id, tur="fiyat_calismasi", ad="Boş"); s.add(bos); s.flush()
    t = ims.excel_tam_yukle(s, excel_yolu, "x", "y", senaryo_id=bos.id)
    assert t["mod"] == "tamamla" and t["recete"] == 67 and t["urun"] == 67 and t["fiyat"] >= 500 and t["havuz"] == 11 and t["ambalaj"] == 22
    assert t["malzeme"] == 0 and s.query(m.Urun).count() == 67   # kartlar zaten vardı: yeni kart açılmaz
    assert s.query(m.Recete).filter_by(senaryo_id=bos.id).count() == 67
    assert s.query(m.Senaryo).count() == 2


def test_tamamla_olmayan_senaryo(yuklu, excel_yolu):
    s, _ = yuklu
    with pytest.raises(BulunamadiHatasi):
        ims.excel_tam_yukle(s, excel_yolu, "x", "y", senaryo_id=9999)


def test_api_tamamla_formu(excel_yolu, oturum):
    from fastapi.testclient import TestClient
    from backend.depo.veritabani import oturum_ver
    from backend.tohum import parametreleri_tohumla
    from backend.uygulama import uygulama_olustur
    app = uygulama_olustur(); app.dependency_overrides[oturum_ver] = lambda: oturum
    parametreleri_tohumla(oturum)
    c = TestClient(app); A = "/api/v1"
    with open(excel_yolu, "rb") as f:
        r = c.post(f"{A}/import/excel-tam", data={"sezon_ad": "2026-2027", "senaryo_ad": "X"}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code == 200 and r.json()["mod"] == "yeni" and r.json()["satis_notu"] == 1, r.text
    sid = r.json()["senaryo_id"]
    oturum.execute(delete(m.UretimKapasitesi)); oturum.flush()
    with open(excel_yolu, "rb") as f:   # sezon_ad/senaryo_ad/tur verilmeden ve yok sayılarak
        r = c.post(f"{A}/import/excel-tam", data={"senaryo_id": str(sid), "tur": "gerceklesen", "sezon_ad": "1999-2000"}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["mod"] == "tamamla" and o["senaryo_id"] == sid and o["kapasite"] == 71 and o["parametre"] == 0 and o["satis_notu"] == 0
    assert c.get(f"{A}/senaryolar").json()["toplam"] == 1
    assert c.get(f"{A}/uretim-kapasitesi?senaryo={sid}").json()["toplam"] == 71


def test_api_tamamla_veya_yeni_zorunlu_alan(istemci, tmp_path):
    from tests.backend.test_api import _xlsx_alakasiz
    yol = _xlsx_alakasiz(tmp_path)
    with open(yol, "rb") as f:
        r = istemci.post("/api/v1/import/excel-tam", data={}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code == 422 and "var olan bir çalışmayı seçin" in r.json()["mesaj"]
    with open(yol, "rb") as f:
        r = istemci.post("/api/v1/import/excel-tam", data={"senaryo_id": "999"}, files={"dosya": ("a.xlsx", f)})
    assert r.status_code in (404, 422)   # alakasız kitap/olmayan senaryo: hata, yeni kayıt yok


def test_hesap_yanitinda_zar_rub_kurlari_ve_not(istemci, oturum):
    from tests.backend.test_api import _kur, _senaryo
    from tests.backend.test_faz4b_hesap import _doviz_param, _hesap
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _doviz_param(istemci, sid, "kur.ZAR", "2.94"); _doviz_param(istemci, sid, "kur.RUB", "0.57")
    istemci.post(f"/api/v1/metin-parametreler?senaryo={sid}", json={"anahtar": "satis_fiyati_notu", "deger": "SATIŞ FİYATI (%20)", "gecerlilik_basi": "2026-06-01", "neden": "t"})
    g = _hesap(istemci, sid)
    assert D_(g["parametreler"]["kurlar"]["ZAR"]) == D_("2.94") and D_(g["parametreler"]["kurlar"]["RUB"]) == D_("0.57")
    assert g["notlar"] == ["SATIŞ FİYATI (%20)"]
