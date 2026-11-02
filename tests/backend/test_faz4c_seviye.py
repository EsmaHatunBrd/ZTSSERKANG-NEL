"""Faz 4c B4: reçete satırı `seviye` (kolon tamamlama, API, hesap görünümü, Excel A sütunu okuması). Şirket verisi yok: yalnız sayım/dağılım."""
from collections import Counter
from datetime import date
from decimal import Decimal as D_
import warnings
import pytest
from sqlalchemy import create_engine, inspect, text
from backend.depo import modeller as m
from backend.depo.veritabani import Base, eksik_kolonlari_tamamla
from backend.servisler import hesap_servisi as hs, import_servisi as ims, recete_servisi as rs
from tests.backend.test_faz4c_kaydet import API, _kaydet, _recete_json, istemci, sid  # noqa: F401  (fikstürler)
from tests.backend.test_hesap_servisi import ortam  # noqa: F401


def test_kolon_tamamla_eski_dosyaya_ekler_ve_idempotent(tmp_path):
    yol = tmp_path / "eski.db"
    e = create_engine(f"sqlite:///{yol}")
    Base.metadata.create_all(e)
    with e.begin() as c:   # eski şema: seviye kolonu yok
        c.execute(text("ALTER TABLE recete_satiri DROP COLUMN seviye"))
    assert "seviye" not in {k["name"] for k in inspect(e).get_columns("recete_satiri")}
    eksik_kolonlari_tamamla(e)
    assert "seviye" in {k["name"] for k in inspect(e).get_columns("recete_satiri")}
    eksik_kolonlari_tamamla(e)   # ikinci çağrı hata vermez
    assert [k["name"] for k in inspect(e).get_columns("recete_satiri")].count("seviye") == 1
    e.dispose()


def test_yeni_versiyon_seviye_saklar_ve_kurallara_birak_korur(oturum, ortam):
    sen, u = ortam
    sat = [{"malzeme_kodu": "KAV", "miktar": D_(1), "seviye": 0}, {"malzeme_kodu": "ETK", "miktar": D_(1), "seviye": 2}, {"malzeme_kodu": "TAZ", "miktar": D_(1)}]
    r = rs.yeni_versiyon(oturum, u.id, sen.id, sat, "elle")
    assert [x.seviye for x in r.satirlar] == [0, 2, None]
    r2 = rs.kurallara_birak(oturum, u.id, sen.id, None)
    assert [x.seviye for x in r2.satirlar] == [0, 2, None]


def test_api_seviye_get_ve_hesap_gorunumu(istemci, oturum, sid):
    satirlar = [{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "seviye": 1}]
    assert istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", json=satirlar).status_code == 201
    g = istemci.get(f"{API}/urunler/TEST/recete?senaryo={sid}").json()
    assert g["satirlar"][0]["seviye"] == 1
    assert istemci.get(f"{API}/receteler/{g['id']}").json()["satirlar"][0]["seviye"] == 1
    h = istemci.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    mal = [x for x in h["satirlar"] if x["grup"] == "malzeme"]
    assert [x["seviye"] for x in mal] == [1] and all(x["seviye"] is None for x in h["satirlar"] if x["grup"] != "malzeme")
    kayit = istemci.post(f"{API}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    gorunum = istemci.get(f"{API}/hesaplar/{kayit['id']}").json()["gorunum"]
    assert [x["seviye"] for x in gorunum["satirlar"] if x["grup"] == "malzeme"] == [1]


def test_eski_snapshot_seviyesiz_none(istemci, oturum, sid):
    kayit = istemci.post(f"{API}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    h = oturum.get(m.MaliyetHesabi, kayit["id"])
    gs = dict(h.girdi_snapshot); gs["recete"] = {k: v for k, v in gs["recete"].items() if k != "seviyeler"}
    h.girdi_snapshot = gs; oturum.commit()
    gorunum = istemci.get(f"{API}/hesaplar/{kayit['id']}").json()["gorunum"]
    assert all(x["seviye"] is None for x in gorunum["satirlar"])


def test_toplu_kaydet_seviye_yazar(istemci, oturum, sid):
    r = _kaydet(istemci, sid, recete=[{**_recete_json()[0], "seviye": 3}], hesabi_kaydet=False)
    assert r.status_code == 200
    u = oturum.query(m.Urun).filter_by(kod="TEST").one()
    assert rs.aktif_recete(oturum, u.id, sid).satirlar[0].seviye == 3


def test_excel_seviyeleri_okur(excel_yolu):
    from fiyat_motoru import excel_okuyucu as eo
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb_f, wb_v = eo.excel_ac(excel_yolu)
    ilk = next(a for a in eo.urun_sayfalarini_listele(wb_v) if "(2)" not in a)
    girdi, _, _ = eo.urun_oku(wb_f[ilk], wb_v[ilk])
    sev = ims.recete_seviyeleri_oku(wb_v[ilk])
    assert len(sev) == len(girdi.recete) and len(sev) > 0
    assert sev == [0, 0, 2, 3, 2, 0, 1, 2, 2, 0, 1, 1, 1, 1, 0, 3, 3, 3, 1, 3, 3, 3, 3]
    assert Counter(sev) == Counter({3: 8, 1: 6, 0: 5, 2: 4})


def test_import_seviyeleri_yazar(excel_yolu):
    from backend.depo.veritabani import motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Seviye testi")
    toplam = s.query(m.ReceteSatiri).count()
    dolu = s.query(m.ReceteSatiri).filter(m.ReceteSatiri.seviye.isnot(None)).count()
    sayim = Counter(x for (x,) in s.query(m.ReceteSatiri.seviye).all())
    assert dolu > toplam * 0.5 and all(sayim[k] > 0 for k in (0, 1, 2, 3))
    assert all(k is None or k >= 0 for k in sayim)
    s.close()


def test_tamamla_modu_yalniz_recete_eklerken_seviye_yazar(excel_yolu):
    from backend.depo.veritabani import motor_olustur, oturum_fabrikasi
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    o = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "A")
    bos = m.Senaryo(sezon_id=s.query(m.Sezon).one().id, tur="fiyat_calismasi", ad="Boş"); s.add(bos); s.flush()
    ims.excel_tam_yukle(s, excel_yolu, "x", "y", senaryo_id=bos.id)
    sayim = lambda sid: Counter(x for (x,) in s.query(m.ReceteSatiri.seviye).join(m.Recete, m.Recete.id == m.ReceteSatiri.recete_id).filter(m.Recete.senaryo_id == sid))
    assert sayim(bos.id) == sayim(o["senaryo_id"]) and sayim(bos.id)[3] > 0
    s.close()


def test_alt_satiri_olan_fiyatsiz_satir_uyari_vermez(istemci, oturum, sid):
    """Uyarı sadeleştirme: fiyat listesinde olmayan ARA (altında daha derin satır var) uyarmaz; altı olmayan YOK uyarır.
    Aynı seviyedeki ya da son satır 'alt satırlı' sayılmaz; seviyesiz satır da sayılmaz."""
    satirlar = [
        {"malzeme_kodu": "ARA", "ad": "Ara ürün", "miktar": "1", "birim": "KG", "seviye": 0},
        {"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD", "seviye": 1},
        {"malzeme_kodu": "YOK", "ad": "Eksik turşu", "miktar": "1", "birim": "KG", "seviye": 1},
        {"malzeme_kodu": "SEVIYESIZ", "ad": "Seviyesiz", "miktar": "1", "birim": "KG"},
    ]
    assert istemci.post(f"{API}/urunler/TEST/recete?senaryo={sid}", json=satirlar).status_code == 201
    h = istemci.post(f"{API}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).json()
    fiyat_yok = [u for u in h["uyarilar"] if "fiyat listesinde yok" in u]
    assert any(u.startswith("YOK ") for u in fiyat_yok) and any(u.startswith("SEVIYESIZ ") for u in fiyat_yok)
    assert not any(u.startswith("ARA ") for u in fiyat_yok)
