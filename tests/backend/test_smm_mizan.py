"""SMM mizan satırlarına elle giriş: listeleme, ekleme, güncelleme, silme; 'elle' işareti, yeniden yükleme uyarısı, kilit, günlük."""
from decimal import Decimal as D_
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_veri import _ekim, _rapor, _yukle

A = "/api/v1"
H = {"X-Kullanici": "esma"}
MIZAN_BASLIK = ["Hesap Kodu", "Hesap Adı", "B", "A", "BB", "BA", "Bakiye"]


def _mizan(c, did, tur):
    r = c.get(f"{A}/smm/donemler/{did}/mizan/{tur}")
    assert r.status_code == 200, r.text
    return r.json()


def _kaynak(c, did, kaynak):
    v = c.get(f"{A}/smm/donemler/{did}/veri").json()
    return next(x for x in v["kaynaklar"] if x["kaynak"] == kaynak), v


def _ozet_720(c, did):
    o = c.get(f"{A}/smm/donemler/{did}/ozet").json()
    blok = next(b for b in o["tablo"] if b["hesap"] == "72x")
    return D_(next(x for x in blok["satirlar"] if x["ad"].startswith("720"))["tutar"]), D_(o["smm"]), o


def test_gider_mizani_elle_satir_ekle_guncelle_ozet_yeniden_hesaplanir(istemci):  # noqa: F811
    did = _ekim(istemci)
    m0 = _mizan(istemci, did, "gider")
    assert m0["kayitlar"] == [] and D_(m0["toplam"]) == 0 and m0["elle"] == 0 and m0["elle_uyari"] is None
    _, smm0, _ = _ozet_720(istemci, did)
    r = istemci.post(f"{A}/smm/donemler/{did}/mizan/gider", json={"hesap": "720", "bakiye": "2000", "neden": "mizan düzeltmesi"}, headers=H)
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["kayitlar"] == [{"hesap": "720", "ad": "Direkt İşçilik Giderleri", "bakiye": "2000", "elle": True}]
    assert D_(v["toplam"]) == 2000 and v["elle"] == 1
    # kontrol listesi: gider mizanı artık var, elle satır uyarısı döner, 720 ayarlara yansır
    k, durum = _kaynak(istemci, did, "gider_mizan")
    assert k["yuklendi"] is True and k["dolu"] == 1 and k["elle"] == 1 and k["elle_uyari"] == "1 elle satır var, yükleme bunları siler"
    assert "Gider mizanı (720 / 730)" not in durum["eksik"] and D_(durum["ayarlar"]["gider_720"]) == 2000
    assert _kaynak(istemci, did, "alim")[0]["elle"] == 0
    # özet istek anında yeniden hesaplanır
    t720, smm1, _ = _ozet_720(istemci, did)
    assert t720 == 2000 and smm1 == smm0 + 2000
    r = istemci.patch(f"{A}/smm/donemler/{did}/mizan/gider/720", json={"bakiye": "2500.50", "neden": "mizan düzeltmesi"}, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["degisti"] == ["bakiye"] and r.json()["kayitlar"][0]["bakiye"] == "2500.50"
    t720, smm2, _ = _ozet_720(istemci, did)
    assert t720 == D_("2500.50") and smm2 == smm0 + D_("2500.50")
    # aşama hesabının okuduğu dönem alanı da eşitlenir (ayarlar aynı tutarı gösterir)
    assert D_(_kaynak(istemci, did, "gider_mizan")[1]["ayarlar"]["gider_720"]) == D_("2500.50")
    # değişmeyen değer kayıt açmaz
    r = istemci.patch(f"{A}/smm/donemler/{did}/mizan/gider/720", json={"bakiye": "2500.5", "neden": "aynı"}, headers=H)
    assert r.status_code == 200 and r.json()["degisti"] == []
    # günlükte neden ile bulunur
    assert istemci.get(f"{A}/gunluk", params={"q": "mizan düzeltmesi"}).json()["toplam"] >= 2
    # sil: satır gider, 720 sıfırlanır
    r = istemci.delete(f"{A}/smm/donemler/{did}/mizan/gider/720", params={"neden": "yanlış girildi"}, headers=H)
    assert r.status_code == 200 and r.json()["kayitlar"] == [] and r.json()["elle"] == 0
    t720, smm3, _ = _ozet_720(istemci, did)
    assert t720 == 0 and smm3 == smm0
    assert D_(_kaynak(istemci, did, "gider_mizan")[1]["ayarlar"]["gider_720"]) == 0


def test_dogrulamalar(istemci):  # noqa: F811
    did = _ekim(istemci)
    u = f"{A}/smm/donemler/{did}/mizan"
    assert istemci.post(f"{u}/gider", json={"hesap": "730", "bakiye": "10", "neden": "ilk"}, headers=H).status_code == 201
    assert istemci.post(f"{u}/gider", json={"hesap": "730", "bakiye": "10", "neden": "tekrar"}, headers=H).status_code == 409
    assert istemci.post(f"{u}/gider", json={"hesap": "150", "bakiye": "10", "neden": "x"}, headers=H).status_code == 422     # gider değil
    assert istemci.post(f"{u}/gider", json={"hesap": "720.01", "bakiye": "10", "neden": "x"}, headers=H).status_code == 422  # ana hesap değil
    assert istemci.post(f"{u}/gider", json={"hesap": "720", "bakiye": "10"}, headers=H).status_code == 422                   # neden yok
    assert istemci.post(f"{u}/gider", json={"hesap": "720", "bakiye": "10", "neden": "  "}, headers=H).status_code == 422
    assert istemci.post(f"{u}/gider", json={"hesap": "720", "bakiye": "-1", "neden": "x"}, headers=H).status_code == 422    # 720 eksi olamaz
    assert istemci.post(f"{u}/gider", json={"hesap": "720", "bakiye": "abc", "neden": "x"}, headers=H).status_code == 422
    assert istemci.post(f"{u}/gider", json={"hesap": "721", "bakiye": "-10", "neden": "yansıtma alacak bakiyesi"}, headers=H).status_code == 201
    assert istemci.post(f"{u}/stok", json={"hesap": "720", "bakiye": "10", "neden": "x"}, headers=H).status_code == 422      # stok değil
    assert istemci.patch(f"{u}/gider/799", json={"bakiye": "1", "neden": "x"}, headers=H).status_code == 404
    assert istemci.patch(f"{u}/gider/730", json={"bakiye": "1"}, headers=H).status_code == 422
    assert istemci.patch(f"{u}/gider/730", json={"bakiye": "1", "bilinmeyen": 1, "neden": "x"}, headers=H).status_code == 422
    assert istemci.delete(f"{u}/gider/730", headers=H).status_code == 422                                                     # neden yok
    assert istemci.delete(f"{u}/gider/799", params={"neden": "x"}, headers=H).status_code == 404
    assert istemci.get(f"{u}/baska").status_code == 422
    assert istemci.get(f"{A}/smm/donemler/99999/mizan/gider").status_code == 404
    assert [x["hesap"] for x in _mizan(istemci, did, "gider")["kayitlar"]] == ["721", "730"]


def test_stok_mizani_elle_ve_mizan_kiyasi(istemci):  # noqa: F811
    did = _ekim(istemci)
    u = f"{A}/smm/donemler/{did}/mizan/stok"
    r = istemci.post(u, json={"hesap": "150.01.001", "ad": "Hammadde", "bakiye": "500", "neden": "mizandan"}, headers=H)
    assert r.status_code == 201, r.text
    assert istemci.post(u, json={"hesap": "151", "bakiye": "120.25", "neden": "mizandan"}, headers=H).status_code == 201
    v = _mizan(istemci, did, "stok")
    assert [(x["hesap"], x["ad"], x["bakiye"], x["elle"]) for x in v["kayitlar"]] == [
        ("150.01.001", "Hammadde", "500", True), ("151", None, "120.25", True)]
    assert D_(v["toplam"]) == D_("620.25") and v["elle"] == 2
    kiyas = {x["hesap"]: x for x in istemci.get(f"{A}/smm/donemler/{did}/ozet").json()["mizan_kiyas"]}
    assert D_(kiyas["150"]["mizan"]) == 500 and D_(kiyas["151"]["mizan"]) == D_("120.25")
    # ad ve bakiye birlikte
    r = istemci.patch(f"{u}/151", json={"ad": "Yarı mamuller", "bakiye": "130", "neden": "düzeltme"}, headers=H)
    assert r.status_code == 200 and r.json()["degisti"] == ["ad", "bakiye"]
    r = istemci.delete(f"{u}/150.01.001", params={"neden": "yanlış hesap"}, headers=H)
    assert r.status_code == 200 and [x["hesap"] for x in r.json()["kayitlar"]] == ["151"] and r.json()["elle"] == 1
    kiyas = {x["hesap"]: x for x in istemci.get(f"{A}/smm/donemler/{did}/ozet").json()["mizan_kiyas"]}
    assert D_(kiyas["151"]["mizan"]) == 130 and D_(kiyas.get("150", {"mizan": "0"})["mizan"]) == 0
    k, _ = _kaynak(istemci, did, "stok_mizan")
    assert k["yuklendi"] is True and k["elle"] == 1 and k["elle_uyari"] == "1 elle satır var, yükleme bunları siler"


def test_excel_yeniden_yuklenince_elle_satirlar_silinir(istemci):  # noqa: F811
    did = _ekim(istemci)
    dosya = _rapor(MIZAN_BASLIK, [["720", "İşçilik", 0, 0, 0, 0, 2000], ["730", "GÜG", 0, 0, 0, 0, 3000]])
    assert _yukle(istemci, did, "gider_mizan", dosya).status_code == 200
    v = _mizan(istemci, did, "gider")
    assert [(x["hesap"], x["bakiye"], x["elle"]) for x in v["kayitlar"]] == [("720", "2000", False), ("730", "3000", False)]
    u = f"{A}/smm/donemler/{did}/mizan/gider"
    assert istemci.patch(f"{u}/730", json={"bakiye": "3500", "ad": "GÜG (düzeltilmiş)", "neden": "eksik fatura"}, headers=H).status_code == 200
    assert istemci.post(u, json={"hesap": "731", "bakiye": "-3500", "neden": "yansıtma"}, headers=H).status_code == 201
    v = _mizan(istemci, did, "gider")
    assert {x["hesap"]: x["elle"] for x in v["kayitlar"]} == {"720": False, "730": True, "731": True}
    assert next(x for x in v["kayitlar"] if x["hesap"] == "730")["ad"] == "GÜG (düzeltilmiş)"
    k, _ = _kaynak(istemci, did, "gider_mizan")
    assert k["elle"] == 2 and k["elle_uyari"] == "2 elle satır var, yükleme bunları siler"
    # yükleme mevcut davranışı korur: mizan baştan yazılır, elle satırlar ve işaretleri gider
    r = _yukle(istemci, did, "gider_mizan", dosya)
    assert r.status_code == 200
    k = next(x for x in r.json()["kaynaklar"] if x["kaynak"] == "gider_mizan")
    assert k["elle"] == 0 and k["elle_uyari"] is None and k["dolu"] == 2
    v = _mizan(istemci, did, "gider")
    assert [(x["hesap"], x["bakiye"], x["elle"]) for x in v["kayitlar"]] == [("720", "2000", False), ("730", "3000", False)]
    assert v["kayitlar"][1]["ad"] == "Genel Üretim Giderleri"
    # Gider tutarları kartından (ayarlar) girilen 720 de elle işaretlenir
    assert istemci.put(f"{A}/smm/donemler/{did}/ayarlar", json={"gider_720": "2100"}).status_code == 200
    assert {x["hesap"]: x["elle"] for x in _mizan(istemci, did, "gider")["kayitlar"]} == {"720": True, "730": False}


def test_kilitli_donemde_mizan_degismez(istemci):  # noqa: F811
    did = _ekim(istemci)
    u = f"{A}/smm/donemler/{did}/mizan/gider"
    assert istemci.post(u, json={"hesap": "720", "bakiye": "10", "neden": "ilk"}, headers=H).status_code == 201
    assert istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True}).status_code == 200
    r = istemci.post(u, json={"hesap": "730", "bakiye": "10", "neden": "x"}, headers=H)
    assert r.status_code == 409 and r.json()["kod"] == "donem_kilitli"
    assert istemci.patch(f"{u}/720", json={"bakiye": "11", "neden": "x"}, headers=H).status_code == 409
    assert istemci.delete(f"{u}/720", params={"neden": "x"}, headers=H).status_code == 409
    assert _mizan(istemci, did, "gider")["kayitlar"][0]["bakiye"] == "10"   # okuma serbest, değer aynı
    assert istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": False}).status_code == 200
    assert istemci.patch(f"{u}/720", json={"bakiye": "11", "neden": "x"}, headers=H).status_code == 200
