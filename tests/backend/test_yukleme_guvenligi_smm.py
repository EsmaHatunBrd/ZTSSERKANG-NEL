"""Excel yükleme güvenliği — Maliyet Muhasebesi (SMM) yüklemeleri.

Aylık kaynaklar (alım-satış, iade, üretim, sayım, şahit, gider / stok mizanı), SMM dönem Excel'i ve Canias ürün ağacı dökümü için:
esnek başlık ve sayfa adı, başka kaynağın / şablonun dosyasının reddi, boş dosyada veri değişmemesi (önceki sessiz sıfırlama hatasının
regresyonu), yarıdan az satırda onay, bozuk sayının sorunlu sayılması, önizleme sayıları, son yüklemeyi geri alma.
Çalışma kitapları bellekte üretilen uydurma küçük dosyalardır (gerçek şirket dosyası okunmaz)."""
from decimal import Decimal as D_
from io import BytesIO

import pytest
from openpyxl import Workbook

from backend.depo import modeller as m
from backend.servisler.excel_ortak import sablon_kimligi_yaz
from tests.backend.test_api import istemci  # noqa: F401  (fixture)
from tests.backend.test_smm_asama import _excel
from tests.backend.test_smm_recete import BASLIK as CANIAS_BASLIK, _canias
from tests.backend.test_smm_veri import ALIM_BASLIK, _ekim, _rapor, _yukle

A = "/api/v1"
H = {"X-Kullanici": "esma"}


def _kitap(sayfa: str, baslik: list, satirlar: list[list], ust: str | None = "RAPOR (serbest satır)", kimlik: str | None = None,
           ek_sayfalar: tuple[str, ...] = ()) -> bytes:
    """Şablon düzeni: 1. satır serbest, 2. satır başlık, sonra veri. `kimlik`: gizli şablon kimliği sayfası."""
    wb = Workbook()
    ws = wb.active
    ws.title = sayfa
    ws.append([ust])
    ws.append(baslik)
    for r in satirlar:
        ws.append(r)
    for ad in ek_sayfalar:
        wb.create_sheet(ad).append(["bilgi"])
    if kimlik:
        sablon_kimligi_yaz(wb, kimlik)
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def _bos(n: int) -> list:
    return [None] * n


# Şablonlardaki (sablonlar/uret.py) başlıkların büyük/küçük harf, Türkçe harf, boşluk ve eş anlamlı varyasyonları.
def _alim(satirlar, sayfa="hm-ym alış satış", **k):
    baslik = ["fiş no", "MALZEME (SINIF) KODU", "malzeme açıklaması", "Tarih", "Depo", "birimi", "GİRİŞ  MİKTARI", "", "", "",
              "tutar (tl)", "Çıkış Miktarı"] + [""] * 7 + ["hareket türü"]
    return _kitap(sayfa, baslik, [[None, kod, ad, None, None, br, g, None, None, None, t, c] + _bos(7) + [tur]
                                  for kod, ad, br, g, t, c, tur in satirlar], **k)


def _iade(satirlar, sayfa="İadeler", **k):
    baslik = ["malzeme kodu", "Açıklama", "", "", "BİRİM", "", "", "iade miktari", "İADE TUTARI"]
    return _kitap(sayfa, baslik, [[kod, "Ad", None, None, "KG", None, None, mk, tt] for kod, mk, tt in satirlar], **k)


def _uretim(satirlar, sayfa="üretim", **k):
    return _kitap(sayfa, ["Malzeme Kodu", "Malzeme Açıklaması", "Birim"] + [""] * 11 + ["ÜRETIM MIKTARI"],
                  [[kod, "Ad", "AD"] + _bos(11) + [mk] for kod, mk in satirlar], **k)


def _sayim(satirlar, sayfa="dss", **k):
    return _kitap(sayfa, ["stok karti kodu", "Stok Kartı Adı", "SAYIM MİKTARI"], [[kod, "Ad", mk] for kod, mk in satirlar], **k)


def _sahit(satirlar, sayfa="şahit", **k):
    return _kitap(sayfa, ["Stok Kodu", "Stok Adı", "Birim"] + [""] * 6 + ["toplam miktar"], [[kod, "Ad", "AD"] + _bos(6) + [mk] for kod, mk in satirlar],
                  **k)


def _mizan(satirlar, sayfa="Gider Mizanı", **k):
    return _kitap(sayfa, ["HESAP KODU", "hesap adı", "Borç", "Alacak", "", "", "BAKİYE"], [[h, "Ad", None, None, None, None, b] for h, b in satirlar], **k)


DOSYALAR = {
    "alim": lambda: _alim([("HM-1", "Biber", "KG", 50, 700, None, "Alış"), ("HM-1", "Biber", "KG", None, None, 5, "SATIŞ"),
                           ("AMB-1", "Kavanoz", "AD", 100, 600, None, "Alış")]),
    "iade": lambda: _iade([("HM-1", 4, 56), ("AMB-1", 2, 12)]),
    "uretim": lambda: _uretim([("01-1", 200), ("02-1", 90)]),
    "sayim": lambda: _sayim([("HM-1", 30), ("AMB-1", 20)]),
    "sahit": lambda: _sahit([("01-1", 1), ("03-1", 2)]),
    "gider_mizan": lambda: _mizan([("710", 10), ("720", 2000), ("720.01", 5), ("730", 3000)]),
    "stok_mizan": lambda: _mizan([("150.01.001", 400), ("151.04.002", 150)], sayfa="stok mizani"),
}
KALEM_KAYNAKLARI = ("alim", "iade", "uretim", "sayim", "sahit")


def _stok(c, did):
    r = c.get(f"{A}/smm/donemler/{did}/stok", params={"yalniz_hareketli": False})
    assert r.status_code == 200, r.text
    return {x["kod"]: x for x in r.json()["kayitlar"]}


def _durum(c, did):
    return c.get(f"{A}/smm/donemler/{did}/veri").json()


def _mizan_satirlari(c, did, tur):
    return c.get(f"{A}/smm/donemler/{did}/mizan/{tur}").json()["kayitlar"]


def _yukle_onay(c, did, kaynak, icerik, onay=False):
    return c.post(f"{A}/smm/donemler/{did}/veri/{kaynak}", files={"dosya": (f"{kaynak}.xlsx", icerik)}, data={"onay": str(onay).lower()}, headers=H)


def _onizle(c, did, kaynak, icerik):
    return c.post(f"{A}/smm/donemler/{did}/veri/{kaynak}/onizle", files={"dosya": (f"{kaynak}.xlsx", icerik)})


# ---------------------------------------------------------------- esnek başlık ve sayfa adı
def test_her_kaynak_baslik_ve_sayfa_adi_varyasyonlariyla_okunur(istemci):  # noqa: F811
    did = _ekim(istemci)
    for kaynak in DOSYALAR:
        r = _yukle(istemci, did, kaynak, DOSYALAR[kaynak]())
        assert r.status_code == 200, f"{kaynak}: {r.text}"
        y = r.json()["yukleme"]
        assert y["sorunlu"] == [] and y["kaynak"] == kaynak, (kaynak, y)
    st = _stok(istemci, did)
    hm, amb = st["HM-1"], st["AMB-1"]
    assert (D_(hm["alim_miktar"]), D_(hm["alim_tutar"]), D_(hm["satis_miktar"])) == (50, 700, 5)   # 'SATIŞ' büyük harfle de satış
    assert (D_(amb["alim_miktar"]), D_(amb["alim_tutar"])) == (100, 600)
    assert (D_(hm["iade_miktar"]), D_(hm["iade_tutar"]), D_(amb["iade_miktar"])) == (4, 56, 2)
    assert D_(st["01-1"]["uretim_miktar"]) == 200 and D_(st["02-1"]["uretim_miktar"]) == 90
    assert D_(hm["sayim_miktar"]) == 30 and D_(amb["sayim_miktar"]) == 20
    assert D_(st["01-1"]["sahit_miktar"]) == 1 and D_(st["03-1"]["sahit_miktar"]) == 2
    assert [x["hesap"] for x in _mizan_satirlari(istemci, did, "gider")] == ["710", "720", "730"]   # alt hesap (720.01) okunmaz
    assert [x["hesap"] for x in _mizan_satirlari(istemci, did, "stok")] == ["150.01.001", "151.04.002"]
    v = _durum(istemci, did)
    assert v["eksik"] == [] and D_(v["ayarlar"]["gider_720"]) == 2000


def test_es_anlamli_baslik_ve_sayfa_adi_canias_bicimi(istemci):  # noqa: F811
    """Sayfa adı farklı (tek veri sayfası), başlıklar eş anlamlı ve noktalama/boşluk farklı; şablonun Örnek / Açıklama sayfaları okunmaz."""
    did = _ekim(istemci)
    dosya = _kitap("Rapor 1", ["Stok Kodu", "Malzeme Adı", "Ölçü Birimi", "Alış Miktarı", "ALIŞ TUTARI", "Hareket Tipi"],
                   [["HM-1", "Biber", "KG", 10, 140, "Alış"]], ek_sayfalar=("Örnek", "Açıklama"))
    o = _onizle(istemci, did, "alim", dosya)
    assert o.status_code == 200, o.text
    assert o.json()["okunan"] == 1 and any("'Rapor 1' sayfası okundu" in u for u in o.json()["uyarilar"])
    assert _yukle(istemci, did, "alim", dosya).status_code == 200
    assert D_(_stok(istemci, did)["HM-1"]["alim_tutar"]) == 140


def test_smm_excel_duzeni_baslik_metni_farkli_konumdan_okunur_uyariyla(istemci):  # noqa: F811
    """Bugünkü SMM Excel'inin sayfa düzeni: kod bilinen yerinde, değer sütununun başlığı farklı ('TOPLAM'). Konumdan okunur, önizlemede uyarı."""
    did = _ekim(istemci)
    dosya = _rapor(["MalzemeKodu", "Ad"] + [""] * 12 + ["TOPLAM"], [["01-1", "Biber salamura"] + [0] * 12 + [200]])
    o = _onizle(istemci, did, "uretim", dosya).json()
    assert o["okunan"] == 1 and o["yeni"] == 1 and any("SMM Excel düzenine göre O sütunundan" in u for u in o["uyarilar"])


def test_tek_sayfalik_ornek_dosya_okunur(istemci):  # noqa: F811
    """Şablonun yalnız 'Örnek' sayfası tek başına kaydedilmişse o sayfa okunur."""
    did = _ekim(istemci)
    r = _yukle(istemci, did, "sayim", _sayim([("HM-1", 7)], sayfa="Örnek"))
    assert r.status_code == 200, r.text
    assert D_(_stok(istemci, did)["HM-1"]["sayim_miktar"]) == 7


# ---------------------------------------------------------------- yanlış dosya
def test_baska_kaynagin_dosyasi_reddedilir(istemci):  # noqa: F811
    did = _ekim(istemci)
    once = _stok(istemci, did)
    for kaynak, dosya, gelen in (("iade", DOSYALAR["uretim"](), "uretim"), ("alim", DOSYALAR["iade"](), "iade"),
                                 ("sayim", DOSYALAR["sahit"](), "sahit"), ("sahit", DOSYALAR["sayim"](), "sayim"),
                                 ("uretim", DOSYALAR["alim"](), "alim")):
        r = _yukle(istemci, did, kaynak, dosya)
        assert r.status_code == 422, (kaynak, r.text)
        assert r.json()["kod"] == "yanlis_kaynak" and r.json()["alanlar"]["gelen_kaynak"] == gelen, (kaynak, r.json())
        assert "dosyası gibi görünüyor" in r.json()["mesaj"] or "sayfası var" in r.json()["mesaj"]
    # tek sayfası başka kaynağın adını taşıyan dosya (başlık bu kaynağa uymuyor)
    r = _yukle(istemci, did, "sayim", _rapor(["MalzemeKodu", "Ad"] + [""] * 12 + ["TOPLAM"], [["01-1", "x"] + [0] * 12 + [1]], "ÜRETİM"))
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_kaynak" and "'ÜRETİM' sayfası var" in r.json()["mesaj"]
    # şablon kimliği başka ekranın
    r = _yukle(istemci, did, "sayim", _sayim([("HM-1", 1)], kimlik="smm_uretim"))
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon" and "SMM üretim şablonu" in r.json()["mesaj"]
    assert _yukle(istemci, did, "sayim", _sayim([("HM-1", 1)], kimlik="smm_sayim")).status_code == 200   # kendi şablonu
    # zorunlu sütun eksik: mesajda sütun adı
    r = _yukle(istemci, did, "iade", _kitap("İADELER", ["Malzeme (Sınıf) Kodu", "Açıklama", "İade Miktarı"], [["HM-1", "x", 1]]))
    assert r.status_code == 422 and r.json()["kod"] == "eksik_sutun" and "İade Tutarı" in r.json()["mesaj"]
    # gider mizanı ekranına stok mizanı (içerikten): 720 / 730 yok
    r = _yukle(istemci, did, "gider_mizan", DOSYALAR["stok_mizan"]())
    assert r.status_code == 422
    # sayfa bulunamadı: çok sayfalı, hiçbiri uymuyor
    wb = Workbook()
    wb.active.title = "A"
    wb.create_sheet("B")
    b = BytesIO()
    wb.save(b)
    r = _yukle(istemci, did, "sayim", b.getvalue())
    assert r.status_code == 422 and r.json()["kod"] == "sayfa_yok" and "Dosyadaki sayfalar: A, B" in r.json()["mesaj"]
    assert _yukle(istemci, did, "sayim", b"bozuk").status_code == 422
    sonra = _stok(istemci, did)
    assert {k: v["sayim_miktar"] for k, v in sonra.items() if k != "HM-1"} == {k: v["sayim_miktar"] for k, v in once.items() if k != "HM-1"}


# ---------------------------------------------------------------- sessiz silme yok
@pytest.mark.parametrize("kaynak", list(DOSYALAR))
def test_bos_dosya_reddedilir_mevcut_veri_degismez(istemci, kaynak):  # noqa: F811
    """Regresyon: eskiden 5 kalem kaynağı boş ya da yanlış dosyada kaynağın verisini sessizce sıfırlıyordu."""
    did = _ekim(istemci)
    assert _yukle(istemci, did, kaynak, DOSYALAR[kaynak]()).status_code == 200
    once_stok, once_durum = _stok(istemci, did), _durum(istemci, did)
    once_mizan = (_mizan_satirlari(istemci, did, "gider"), _mizan_satirlari(istemci, did, "stok"))
    bas = {"alim": ALIM_BASLIK, "iade": ["Malzeme (Sınıf) Kodu", "", "", "", "", "", "", "İade Miktarı", "İade Tutarı"],
           "uretim": ["MalzemeKodu", "", "", "", "", "", "", "", "", "", "", "", "", "", "Üretim Miktarı"],
           "sayim": ["StokKartıKodu", "", "Sayım Miktarı"], "sahit": ["StokKodu"] + [""] * 8 + ["Toplam Miktar"],
           "gider_mizan": ["Hesap Kodu", "", "", "", "", "", "Bakiye"], "stok_mizan": ["Hesap Kodu", "", "", "", "", "", "Bakiye"]}[kaynak]
    for bos in (_kitap("Sayfa1", bas, []), _kitap("Sayfa1", bas, [[None] * len(bas), ["Toplam"] + [None] * (len(bas) - 1)])):
        r = _yukle(istemci, did, kaynak, bos)
        assert r.status_code == 422 and r.json()["kod"] == "bos_dosya", (kaynak, r.text)
        assert "mevcut veri değiştirilmedi" in r.json()["mesaj"]
    o = _onizle(istemci, did, kaynak, _kitap("Sayfa1", bas, []))
    assert o.status_code == 200 and o.json()["okunan"] == 0 and "okunabilen satır yok" in o.json()["uyarilar"][0]
    assert _stok(istemci, did) == once_stok
    assert _durum(istemci, did)["kaynaklar"] == once_durum["kaynaklar"]
    assert (_mizan_satirlari(istemci, did, "gider"), _mizan_satirlari(istemci, did, "stok")) == once_mizan


def test_yaridan_az_satir_onay_ister(istemci, oturum):  # noqa: F811
    did = _ekim(istemci)
    dort = _sayim([("HM-1", 1), ("AMB-1", 2), ("K-3", 3), ("K-4", 4)])
    assert _yukle(istemci, did, "sayim", dort).status_code == 200
    bir = _sayim([("HM-1", 9)])
    o = _onizle(istemci, did, "sayim", bir).json()
    assert (o["mevcut"], o["dosyadaki"], o["silinecek"]) == (4, 1, 3) and "onay istenecek" in o["uyarilar"][0]
    r = _yukle_onay(istemci, did, "sayim", bir)
    assert r.status_code == 409 and r.json()["kod"] == "satir_kaybi_onayi"
    assert r.json()["alanlar"] == {"mevcut": 4, "yeni": 1, "silinecek": 3}
    assert D_(_stok(istemci, did)["AMB-1"]["sayim_miktar"]) == 2   # yazılmadı
    r = _yukle_onay(istemci, did, "sayim", bir, onay=True)
    assert r.status_code == 200, r.text
    st = _stok(istemci, did)
    assert D_(st["HM-1"]["sayim_miktar"]) == 9 and D_(st["AMB-1"]["sayim_miktar"]) == 0
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="smm_donem", islem="veri_yukle").order_by(m.DegisiklikKaydi.id.desc()).first()
    assert k.yeni["onayli_kayip"] == 3
    # yarı ve fazlası onaysız geçer
    assert _yukle_onay(istemci, did, "sayim", _sayim([("HM-1", 1)])).status_code == 200


def test_bozuk_sayi_sorunlu_metin_sayi_cevrilir(istemci):  # noqa: F811
    did = _ekim(istemci)
    dosya = _alim([("HM-1", "Biber", "KG", "1.234,5", "17.280,00 TL", None, "Alış"), ("AMB-1", "Kavanoz", "AD", 10, "abc", None, "Alış"),
                   ("ETK-1", "Etiket", "AD", "2.000", 40, None, "Alış"), (None, "TOPLAM", None, 99, 99, None, None)])
    o = _onizle(istemci, did, "alim", dosya)
    assert o.status_code == 200, o.text
    o = o.json()
    assert o["okunan"] == 4 and o["atlanan"] == 3 and o["yeni"] == 1
    neden = {(x["kod"], x["alan"]): x for x in o["sorunlu"]}
    assert neden[("AMB-1", "Tutar (TL)")]["deger"] == "abc" and neden[("AMB-1", "Tutar (TL)")]["satir"] == 4
    assert "belirsiz" in neden[("ETK-1", "Giriş Miktarı")]["neden"]   # '2.000' binlik mi ondalık mı belli değil
    assert neden[(None, "Malzeme(Sınıf)Kodu")]["neden"].startswith("kod boş")
    r = _yukle(istemci, did, "alim", dosya)
    assert r.status_code == 200 and len(r.json()["yukleme"]["sorunlu"]) == 3
    st = _stok(istemci, did)
    assert D_(st["HM-1"]["alim_miktar"]) == D_("1234.5") and D_(st["HM-1"]["alim_tutar"]) == D_("17280")
    assert D_(st["AMB-1"]["alim_tutar"]) == 0 and D_(st["AMB-1"]["alim_miktar"]) == 0   # sorunlu satır yazılmadı (0 da yazılmadı: kalem önceden yoktu)
    assert "ETK-1" not in st or D_(st["ETK-1"]["alim_miktar"]) == 0


def test_onizleme_sayilari_ve_yazmaz(istemci):  # noqa: F811
    did = _ekim(istemci)
    assert _yukle(istemci, did, "sayim", _sayim([("HM-1", 30), ("AMB-1", 20), ("K-3", 5)])).status_code == 200
    once = _stok(istemci, did)
    o = _onizle(istemci, did, "sayim", _sayim([("HM-1", 30), ("AMB-1", 25), ("YENI-9", 1)]))
    assert o.status_code == 200, o.text
    o = o.json()
    assert (o["okunan"], o["yeni"], o["degisen"], o["ayni"], o["silinecek"], o["atlanan"]) == (3, 1, 1, 1, 1, 0)
    assert o["yeni_kalem"] == 1 and any("yeni kart açılacak" in u for u in o["uyarilar"]) and any("sıfırlanır" in u for u in o["uyarilar"])
    assert o["donem"]["id"] == did and o["ad"] == "Sayım (dönem sonu stok)"
    assert _stok(istemci, did) == once   # önizleme yazmaz
    # mizan önizlemesi: elle satır uyarısı
    istemci.post(f"{A}/smm/donemler/{did}/mizan/gider", json={"hesap": "720", "bakiye": "5", "neden": "elle"}, headers=H)
    o = _onizle(istemci, did, "gider_mizan", DOSYALAR["gider_mizan"]()).json()
    assert (o["yeni"], o["degisen"], o["elle_silinecek"]) == (2, 1, 1) and any("elle" in u for u in o["uyarilar"])


# ---------------------------------------------------------------- geri al
def test_geri_al_birebir_eski_durum_ve_asama_sonuclari(istemci, oturum):  # noqa: F811
    r = istemci.post(f"{A}/smm/donemler/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())})
    did = r.json()["id"]
    u = f"{A}/smm/donemler/{did}/veri/uretim"
    assert istemci.get(f"{u}/son-yukleme").json() == {"son": None}
    assert istemci.post(f"{u}/son-yuklemeyi-geri-al").status_code == 404
    once_stok = _stok(istemci, did)
    once_asama = {a: istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": a}).json() for a in (20, 40, 50)}
    once_ozet = istemci.get(f"{A}/smm/donemler/{did}/ozet").json()
    once_durum = _durum(istemci, did)
    # üretim miktarları değişir (01-1 500 -> 250, 02-1 100 -> 100, 03-1 yok, yeni kalem 03-7): aşama birim maliyetleri değişir
    r = _yukle_onay(istemci, did, "uretim", _uretim([("01-1", 250), ("02-1", 100), ("03-1", 100), ("03-7", 5)]))
    assert r.status_code == 200, r.text
    assert istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": 20}).json() != once_asama[20]
    son = istemci.get(f"{u}/son-yukleme").json()["son"]
    assert son["olusturan"] == "esma" and son["zaman"]
    assert son["kaynak_dosya"] == "uretim.xlsx" and "Üretim miktarları: 4 kalem" in son["ozet"]
    r = istemci.post(f"{u}/son-yuklemeyi-geri-al", headers=H)
    assert r.status_code == 200, r.text
    assert "önceki hâline döndü" in r.json()["mesaj"]
    assert _stok(istemci, did) == once_stok   # 03-7 kartı da silindi
    for a in (20, 40, 50):
        assert istemci.get(f"{A}/smm/donemler/{did}/uretim", params={"asama": a}).json() == once_asama[a]
    assert istemci.get(f"{A}/smm/donemler/{did}/ozet").json() == once_ozet
    assert _durum(istemci, did)["kaynaklar"] == once_durum["kaynaklar"]   # 'son yükleme' bilgisi de eskisi
    assert istemci.post(f"{u}/son-yuklemeyi-geri-al").status_code == 404   # ikinci geri al
    assert istemci.get(f"{u}/son-yukleme").json() == {"son": None}
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="smm_donem", islem="yukleme_geri_al").one()   # günlüğe yazıldı
    assert k.kullanici == "esma" and k.yeni["kaynak"] == "Üretim miktarları"


def test_geri_al_tek_adim_ve_mizan_elle_satirlari_geri_gelir(istemci):  # noqa: F811
    did = _ekim(istemci)
    g = f"{A}/smm/donemler/{did}/veri/gider_mizan"
    assert _yukle(istemci, did, "gider_mizan", _mizan([("720", 1000), ("730", 1500)])).status_code == 200
    istemci.patch(f"{A}/smm/donemler/{did}/mizan/gider/730", json={"bakiye": "1600", "neden": "düzeltme"}, headers=H)
    istemci.post(f"{A}/smm/donemler/{did}/mizan/gider", json={"hesap": "731", "bakiye": "-1600", "neden": "yansıtma"}, headers=H)
    once = _mizan_satirlari(istemci, did, "gider")
    once_ayar = _durum(istemci, did)["ayarlar"]
    assert _yukle(istemci, did, "gider_mizan", DOSYALAR["gider_mizan"]()).status_code == 200
    assert _mizan_satirlari(istemci, did, "gider") != once
    assert istemci.post(f"{g}/son-yuklemeyi-geri-al").status_code == 200
    assert _mizan_satirlari(istemci, did, "gider") == once   # elle satırlar ve 'elle' işaretleri geri geldi
    assert _durum(istemci, did)["ayarlar"] == once_ayar
    assert istemci.post(f"{g}/son-yuklemeyi-geri-al").status_code == 404   # tek adım: ilk yüklemeye dönülmez


def test_kapanmis_donemde_geri_al_409(istemci):  # noqa: F811
    did = _ekim(istemci)
    assert _yukle(istemci, did, "sayim", DOSYALAR["sayim"]()).status_code == 200
    assert istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": True, "zorla": True}).status_code == 200
    r = istemci.post(f"{A}/smm/donemler/{did}/veri/sayim/son-yuklemeyi-geri-al")
    assert r.status_code == 409 and r.json()["kod"] == "donem_kilitli"
    assert _onizle(istemci, did, "sayim", DOSYALAR["sayim"]()).status_code == 409
    assert istemci.get(f"{A}/smm/donemler/{did}/veri/sayim/son-yukleme").json()["son"] is not None   # okuma serbest
    assert istemci.put(f"{A}/smm/donemler/{did}/kilit", json={"kilitli": False}).status_code == 200
    assert istemci.post(f"{A}/smm/donemler/{did}/veri/sayim/son-yuklemeyi-geri-al").status_code == 200


# ---------------------------------------------------------------- SMM dönem Excel'i
def _excel_sayfa_adlari_kucuk() -> bytes:
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(_excel()))
    adlar = [ws.title for ws in wb.worksheets]
    for i, ws in enumerate(wb.worksheets):   # openpyxl aynı adı (büyük/küçük duyarsız) yeniden vermez: önce geçici ad
        ws.title = f"gecici{i}"
    for ad, ws in zip(adlar, wb.worksheets):
        ws.title = ad.replace(" ", "") if ad.endswith(" KOD") else ad.replace("İ", "i").replace("I", "ı").lower()
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def test_donem_exceli_esnek_sayfa_onizleme_onay_ve_geri_al(istemci, oturum):  # noqa: F811
    d = f"{A}/smm/donemler"
    o = istemci.post(f"{d}/yukle/onizle", files={"dosya": ("09-2026 SMM.xlsx", _excel_sayfa_adlari_kucuk())})
    assert o.status_code == 200, o.text
    o = o.json()
    assert (o["yil"], o["ay"], o["donem_ad"], o["mevcut_donem_id"], o["yeni"], o["kalem"]) == (2026, 9, "Eylül 2026", None, o["kalem"], o["kalem"])
    assert o["recete_satiri"] == 6 and o["iscilik"] == 2 and "hm-ym alış satış" in o["sayfalar"]
    assert istemci.get(f"{d}").json()["kayitlar"] == []   # önizleme yazmaz
    r = istemci.post(f"{d}/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel_sayfa_adlari_kucuk())})
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    once_stok, once_asama = _stok(istemci, did), istemci.get(f"{d}/{did}/uretim", params={"asama": 50}).json()
    # aylık kaynak yüklemesi; dönem Excel'i üzerine yazılınca bu yedek eskir
    assert _yukle(istemci, did, "sayim", _sayim([("HM-1", 1)])).status_code == 200
    # az kalemli Excel üzerine yazılırken önce dönem onayı, sonra satır kaybı onayı
    kucuk = _kucuk_excel()
    o = istemci.post(f"{d}/yukle/onizle", files={"dosya": ("09-2026 SMM.xlsx", kucuk)}).json()
    assert o["mevcut_donem_id"] == did and o["silinecek"] >= 1 and any("onay istenecek" in u for u in o["uyarilar"])
    r = istemci.post(f"{d}/yukle", files={"dosya": ("09-2026 SMM.xlsx", kucuk)})
    assert r.status_code == 409 and r.json()["kod"] is None   # dönem zaten yüklü
    r = istemci.post(f"{d}/yukle", files={"dosya": ("09-2026 SMM.xlsx", kucuk)}, data={"uzerine_yaz": "true"})
    assert r.status_code == 409 and r.json()["kod"] == "satir_kaybi_onayi"
    assert _stok(istemci, did)["HM-1"]["sayim_miktar"] == "1"   # değişmedi
    r = istemci.post(f"{d}/yukle", files={"dosya": ("09-2026 SMM.xlsx", kucuk)}, data={"uzerine_yaz": "true", "onay": "true"}, headers=H)
    assert r.status_code == 200, r.text
    assert set(_stok(istemci, did)) == {"HM-1"}
    assert istemci.get(f"{A}/smm/donemler/{did}/veri/sayim/son-yukleme").json()["son"] is None   # aylık yedek eskidi
    # geri al: dönem üzerine yazmadan önceki hâline (aylık sayım yüklemesi dahil)
    son = istemci.get(f"{d}/{did}/son-yukleme").json()["son"]
    assert "üzerine yazıldı" in son["ozet"]
    r = istemci.post(f"{d}/{did}/son-yuklemeyi-geri-al", headers=H)
    assert r.status_code == 200, r.text
    st = _stok(istemci, did)
    assert set(st) == set(once_stok) and st["HM-1"]["sayim_miktar"] == "1"
    assert {k: v for k, v in st["AMB-1"].items()} == once_stok["AMB-1"]
    assert istemci.get(f"{d}/{did}/uretim", params={"asama": 50}).json() == once_asama
    assert istemci.post(f"{d}/{did}/son-yuklemeyi-geri-al").status_code == 404   # tek adım
    # yeni dönem açan yükleme geri alınınca dönem silinir
    r = istemci.post(f"{d}/yukle", files={"dosya": ("10-2026 SMM.xlsx", _excel())})
    yeni_id = r.json()["id"]
    assert istemci.get(f"{d}/{yeni_id}/son-yukleme").json()["son"]["ozet"].endswith("(yeni dönem)")
    r = istemci.post(f"{d}/{yeni_id}/son-yuklemeyi-geri-al")
    assert r.status_code == 200 and "silindi" in r.json()["mesaj"]
    assert [x["id"] for x in istemci.get(d).json()["kayitlar"]] == [did]
    assert oturum.query(m.SmmKalem).filter_by(donem_id=yeni_id).count() == 0


def _kucuk_excel() -> bytes:
    """Yalnız HM-1 olan dönem Excel'i (test_smm_asama düzeninde)."""
    wb = Workbook()
    wb.remove(wb.active)
    for ad, satirlar in (("DBS", [["HM-1", "Biber", 100, 1000]]), ("HM-YM ALIŞ SATIŞ", [[None, "HM-1", "Biber", 9, 9, "KG", 100, 1400, 0, 0, 1400]]),
                         ("DSS", [["HM-1", "Biber", 40]]), ("TABLO", [])):
        ws = wb.create_sheet(ad)
        ws.append([None] * 9 + [0] if ad == "TABLO" else [])
        ws.append(["başlık"])
        for r in satirlar:
            ws.append(r)
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def test_donem_exceli_yanlis_dosya_ve_kilit(istemci):  # noqa: F811
    d = f"{A}/smm/donemler"
    r = istemci.post(f"{d}/yukle", files={"dosya": ("09-2026.xlsx", _sayim([("HM-1", 1)], kimlik="smm_sayim"))})
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon" and "Veri Girişi" in r.json()["mesaj"]
    r = istemci.post(f"{d}/yukle/onizle", files={"dosya": ("09-2026.xlsx", _sayim([("HM-1", 1)]))})
    assert r.status_code == 422 and r.json()["kod"] == "eksik_sayfa" and "DBS" in r.json()["mesaj"]
    did = istemci.post(f"{d}/yukle", files={"dosya": ("09-2026 SMM.xlsx", _excel())}).json()["id"]
    istemci.put(f"{d}/{did}/kilit", json={"kilitli": True, "zorla": True})
    r = istemci.post(f"{d}/{did}/son-yuklemeyi-geri-al")
    assert r.status_code == 409 and r.json()["kod"] == "donem_kilitli"
    o = istemci.post(f"{d}/yukle/onizle", files={"dosya": ("09-2026 SMM.xlsx", _excel())}).json()
    assert o["kilitli"] is True and any("kilitli" in u for u in o["uyarilar"])


def test_donem_exceli_metin_sayi_sorunlu_listelenir(istemci):  # noqa: F811
    from openpyxl import load_workbook
    wb = load_workbook(BytesIO(_excel()))
    wb["DSS"].append(["AMB-1", "Kavanoz", "1.234,5"])
    b = BytesIO()
    wb.save(b)
    o = istemci.post(f"{A}/smm/donemler/yukle/onizle", files={"dosya": ("09-2026 SMM.xlsx", b.getvalue())}).json()
    assert o["sorunlu"] == [{"satir": 4, "kod": "AMB-1", "alan": "DSS · sayım miktarı", "deger": "1.234,5",
                             "neden": "sayı sütununda metin; SMM Excel'i gibi 0 okundu. Hücreyi sayı yapıp yeniden yükleyin."}]


# ---------------------------------------------------------------- Canias ürün ağacı
def _canias_varyant() -> bytes:
    """Başlıklar küçük harf / Türkçe harfsiz / eş anlamlı, sayfa adı farklı, sütun sırası farklı, alternatif sayı (0)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sonuç"
    ws.append(["fire orani", "TÜKETİM MİKTARI", "tuketim malzeme kodu", "malzeme kodu", "alternatif no", "Tüketim Birimi"])
    ws.append([10, 0.5, "HM-1", "01-1", 0, "KG"])
    ws.append([0, "0,2", "01-1", "02-1", 0, "KG"])
    ws.append([0, "abc", "AMB-1", "02-1", 0, "AD"])
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


def test_canias_esnek_baslik_sorunlu_onay_ve_geri_al(istemci):  # noqa: F811
    r = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("Reçete.xlsx", _canias_varyant())})
    assert r.status_code == 200, r.text
    o = r.json()
    assert (o["okunan"], o["atlanan"], o["yeni"], o["urun_sayisi"]) == (3, 1, 2, 2)
    assert o["sorunlu"][0]["kod"] == "02-1 / AMB-1" and o["sorunlu"][0]["alan"] == "Tüketim Miktarı"
    # ilk yükleme (4 ürün)
    assert istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", _canias())}).status_code == 200
    once = {k: istemci.get(f"{A}/smm/receteler/{k}").json() for k in ("01-1", "02-1", "03-1", "03-2")}
    once_liste = istemci.get(f"{A}/smm/receteler").json()
    # 2 ürünlük dosya: 4'ün yarısı -> onaysız geçer; 1 ürünlük -> 409
    tek = BytesIO()
    wb = Workbook()
    wb.active.title = "TBLRESULT"
    wb.active.append(CANIAS_BASLIK)
    wb.active.append(["00", "01-1", "Biber salamura", 1, 2, "HM-1", "Biber", 0.6, "KG", 5, 0.63])
    wb.save(tek)
    r = istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", tek.getvalue())})
    assert r.status_code == 409 and r.json()["kod"] == "satir_kaybi_onayi" and r.json()["alanlar"]["mevcut"] == 4
    r = istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", tek.getvalue())}, data={"onay": "true"})
    assert r.status_code == 200 and r.json()["silinecek"] == 3
    assert istemci.get(f"{A}/smm/receteler/03-1").status_code == 404
    son = istemci.get(f"{A}/smm/receteler/son-yukleme").json()["son"]
    assert "1 ürün" in son["ozet"]
    r = istemci.post(f"{A}/smm/receteler/son-yuklemeyi-geri-al")
    assert r.status_code == 200, r.text
    assert {k: istemci.get(f"{A}/smm/receteler/{k}").json() for k in once} == once
    assert istemci.get(f"{A}/smm/receteler").json() == once_liste   # 'son yükleme' bilgisi de eskisi
    assert istemci.post(f"{A}/smm/receteler/son-yuklemeyi-geri-al").status_code == 404
    # boş döküm: 422, reçeteler değişmez
    bos = BytesIO()
    wb = Workbook()
    wb.active.title = "TBLRESULT"
    wb.active.append(CANIAS_BASLIK)
    wb.save(bos)
    r = istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("Reçete.xlsx", bos.getvalue())})
    assert r.status_code == 422 and r.json()["kod"] == "bos_dosya"
    assert istemci.get(f"{A}/smm/receteler").json() == once_liste
    # başka şablon
    r = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("x.xlsx", _sayim([("HM-1", 1)], kimlik="smm_sayim"))})
    assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon"


# ---------------------------------------------------------------- şablonlar (sablonlar/uret.py ile bellekte üretilir)
def _uret():
    import importlib.util
    from pathlib import Path
    yol = Path(__file__).resolve().parents[2] / "sablonlar" / "uret.py"
    spec = importlib.util.spec_from_file_location("sablon_uret_smm_testi", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bayt(wb) -> bytes:
    b = BytesIO()
    wb.save(b)
    return b.getvalue()


SABLON_KAYNAK = {"10": ("alim", 3), "11": ("iade", 2), "12": ("uretim", 3), "13": ("sayim", 5), "14": ("sahit", 2), "15": ("gider_mizan", 5),
                 "16": ("stok_mizan", 5)}


def test_smm_sablonlari_okunur_bos_sablon_reddedilir_baska_ekrana_yuklenemez(istemci, oturum):  # noqa: F811
    """Şablon 10-16: dolu kitap (Örnek / Açıklama / gizli kimlik sayfalarıyla) ve yalnız Örnek sayfası okunur, satır sayısı örnekle aynı;
    boş şablon 422 `bos_dosya`; başka kaynağın satırına yüklenen şablon 422 `yanlis_sablon`."""
    u = _uret()
    did = _ekim(istemci)
    for t in u.SABLONLAR:
        if t.no not in SABLON_KAYNAK:
            continue
        kaynak, beklenen = SABLON_KAYNAK[t.no]
        r = _yukle(istemci, did, kaynak, _bayt(u.kitap(t)))
        assert r.status_code == 422 and r.json()["kod"] == "bos_dosya", (t.no, r.text)
        wb = u.kitap(t)
        for ad in list(wb.sheetnames):
            if ad != "Örnek":
                del wb[ad]
        for dosya in (_bayt(wb), _bayt(u.kitap(t, dolu=True))):
            r = _yukle_onay(istemci, did, kaynak, dosya, onay=True)
            assert r.status_code == 200, (t.no, r.text)
            assert r.json()["yukleme"]["sorunlu"] == [], (t.no, r.json()["yukleme"])
            oturum.expire_all()
            assert oturum.get(m.SmmDonem, did).veri_kaynaklari[kaynak]["satir"] == beklenen, t.no
        baska = next(k for k, _ in SABLON_KAYNAK.values() if k != kaynak)
        r = _yukle(istemci, did, baska, _bayt(u.kitap(t, dolu=True)))
        assert r.status_code == 422 and r.json()["kod"] == "yanlis_sablon", (t.no, baska, r.text)
    canias = next(t for t in u.SABLONLAR if t.no == "09")
    o = istemci.post(f"{A}/smm/receteler/onizle", files={"dosya": ("dokum.xlsx", _bayt(u.kitap(canias, dolu=True)))}).json()
    assert (o["urun_sayisi"], o["satir_sayisi"], o["sorunlu"]) == (3, 10, [])
    r = istemci.post(f"{A}/smm/receteler/yukle", files={"dosya": ("dokum.xlsx", _bayt(u.kitap(canias)))})
    assert r.status_code == 422 and r.json()["kod"] == "bos_dosya"
