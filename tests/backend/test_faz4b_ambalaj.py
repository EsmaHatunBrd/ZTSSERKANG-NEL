"""Faz 4b B3: GET /ambalaj-ozeti (ambalaj türü ve kapak bazında ürün sayısı + üretim adedi)."""
from decimal import Decimal as D_
from backend.servisler import ambalaj_servisi as asv
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401

A = "/api/v1"
HEDEF = {"dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}


def _urun(c, sid, kod, adet, satirlar):
    assert c.put(f"{A}/urunler/{kod}", json={"ad": kod, "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"{A}/urunler/{kod}/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": adet, **HEDEF}).status_code == 200
    assert c.post(f"{A}/urunler/{kod}/recete?senaryo={sid}", json=[{"malzeme_kodu": f"M{i}", "ad": ad, "miktar": "1", "birim": "AD"} for i, ad in enumerate(satirlar)]).status_code == 201


def test_tur_esleme():
    t = asv.ambalaj_turu
    assert t("Cam Kavanoz 370 ml Boğumlu") == "Cam Kavanoz" and t("CAM KAVANOZ 720ml") == "Cam Kavanoz"
    assert t("Cam Şişe 1000 ml") == "Cam Şişe" and t("Teneke Kutu A10 (3/1)") == "Teneke Kutu"
    assert t("Folyo (Torba)") == "Torba/Folyo" and t("Torba 2,5 kg") == "Torba/Folyo"
    assert t("Pet Kavanoz 5000 ml") == "Pet Kavanoz" and t("Pet Şişe 1 lt") == "Pet Kavanoz"
    assert t("Kapak 63 mm Beyaz") is None and t("Etiket") is None and t("Karpet") is None


def test_ozet(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    _urun(istemci, sid, "U1", "1000", ["Cam Kavanoz 370 ml", "Kapak 63 mm Beyaz", "Etiket Ön"])
    _urun(istemci, sid, "U2", "500", ["Cam Kavanoz 720 ml", "Kapak 63 mm Beyaz"])
    _urun(istemci, sid, "U3", "200", ["Folyo (Torba)"])
    _urun(istemci, sid, "U4", "50", ["Cam Şişe 250 ml", "Kapak 38 mm Siyah"])
    r = istemci.get(f"{A}/ambalaj-ozeti?senaryo={sid}")
    assert r.status_code == 200, r.text
    g = r.json()
    tur = {x["tur"]: x for x in g["turler"]}   # _kur ürünü TEST de (Kavanoz, 65000) Cam Kavanoz sayılır
    assert tur["Cam Kavanoz"]["urun_sayisi"] == 3 and D_(tur["Cam Kavanoz"]["uretim_adedi"]) == 66500
    assert tur["Torba/Folyo"]["urun_sayisi"] == 1 and D_(tur["Torba/Folyo"]["uretim_adedi"]) == 200
    assert tur["Cam Şişe"]["urun_sayisi"] == 1 and D_(tur["Cam Şişe"]["uretim_adedi"]) == 50
    assert [x["tur"] for x in g["turler"]] == ["Cam Kavanoz", "Cam Şişe", "Torba/Folyo"]   # sabit tür sırası
    kap = {x["ad"]: x for x in g["kapaklar"]}
    assert kap["Kapak 63 mm Beyaz"]["urun_sayisi"] == 2 and D_(kap["Kapak 63 mm Beyaz"]["uretim_adedi"]) == 1500
    assert kap["Kapak 38 mm Siyah"]["urun_sayisi"] == 1 and len(kap) == 2


def test_bos_ve_bilinmeyen_senaryo(istemci, oturum):
    sid = _senaryo(istemci)
    assert istemci.get(f"{A}/ambalaj-ozeti?senaryo={sid}").json() == {"turler": [], "kapaklar": []}
    assert istemci.get(f"{A}/ambalaj-ozeti?senaryo=999").status_code == 404


def test_receteli_olmayan_urun_atlanir(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)   # TEST ürünü: kavanoz reçeteli ("Kavanoz" adı, tür eşlemesi var)
    istemci.put(f"{A}/urunler/BOS", json={"ad": "Boş", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"})
    g = istemci.get(f"{A}/ambalaj-ozeti?senaryo={sid}").json()
    assert g["turler"] == [{"tur": "Cam Kavanoz", "urun_sayisi": 1, "uretim_adedi": "65000"}]
