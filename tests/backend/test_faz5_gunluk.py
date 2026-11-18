"""Faz 5 Görev D: Değişiklik Günlüğü, Arşiv (sezon -> senaryo -> kayıtlı hesaplar, kıyas), senaryo kilidi, reçete sürümü etkinleştirme."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D_
from io import BytesIO
import pytest
from openpyxl import load_workbook
from sqlalchemy import event
from backend.depo import modeller as m
from backend.depo.veritabani import eksik_kolonlari_tamamla, motor_olustur
from backend.servisler import import_servisi as ims
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401

A = "/api/v1"
KAP = {"net_kapasite": "100", "net_sure": "10", "toplam_kapasite": "200", "toplam_sure": "20", "hedef_uretim": "150", "ortalama_isci": "12"}


def _hazirla(c, oturum, sid):
    """Her kaynaktan en az bir günlük satırı üretir (kullanıcı: esma)."""
    h = {"X-Kullanici": "esma"}
    assert c.post(f"{A}/parametreler/kur.USD/degerler?senaryo={sid}", json={"deger": "55", "gecerlilik_basi": "2026-07-01", "neden": "kur güncellemesi"}, headers=h).status_code == 201
    assert c.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"fiyat": "6.5", "gecerlilik_basi": "2026-07-01", "neden": "zam"}, headers=h).status_code == 201
    for oran in ("0.02", "0.03"):
        assert c.post(f"{A}/fire-kurallari?senaryo={sid}", json={"kapsam_tipi": "malzeme", "kapsam_deger": "KAV", "oran": oran, "gecerlilik_basi": "2026-07-01", "neden": f"fire {oran}"}, headers=h).status_code == 201
    assert c.post(f"{A}/metin-parametreler?senaryo={sid}", json={"anahtar": "satis_fiyati_notu", "deger": "not 1", "gecerlilik_basi": "2026-07-01", "neden": "ilk not"}, headers=h).status_code == 201
    assert c.put(f"{A}/urunler/TEST", json={"ad": "Test 2", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}, headers=h).status_code == 200
    assert c.put(f"{A}/urunler/TEST/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "70000", "dolum_personel": "13", "etiketleme_adedi": "35000",
                 "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}, headers=h).status_code == 200
    assert c.put(f"{A}/uretim-kapasitesi/TEST?senaryo={sid}", json={**KAP, "neden": "ilk kapasite", "urun_ad": "Test 2"}, headers=h).status_code == 200
    assert c.put(f"{A}/gider-havuzlari/pazarlama?senaryo={sid}", json={"ad": "Pazarlama", "neden": "bütçe revizyonu", "toplam_tutar": "17000000", "baz_tipi": "adet"}, headers=h).status_code == 200
    assert c.put(f"{A}/ambalaj-siniflari?senaryo={sid}", json={"siniflar": [{"ad": "370 ml", "hacim": "370", "uretim_adedi": "100", "katsayi": "0.5"}], "neden": "yeniden"}, headers=h).status_code == 200
    assert c.post(f"{A}/satis-gecmisi", json={"urun_kodu": "TEST", "musteri": "Örnek Müşteri A", "tarih": "2026-05-01", "fiyat": "10", "para_birimi": "TL", "adet": "5", "neden": "elle giriş"}, headers=h).status_code == 201
    assert c.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "2", "birim": "AD"}], headers=h).status_code == 201
    r = c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}, headers=h)
    assert r.status_code == 201, r.text
    assert c.post(f"{A}/hesaplar/{r.json()['id']}/teklifler", json={"kar_orani": "0.2", "musteri": "Örnek Müşteri A"}, headers=h).status_code == 201
    return r.json()["id"]


@pytest.fixture
def veri(istemci, oturum):
    sid = _senaryo(istemci)
    _kur(istemci, sid, oturum)
    hid = _hazirla(istemci, oturum, sid)
    return istemci, oturum, sid, hid


def _gunluk(c, **p):
    r = c.get(f"{A}/gunluk", params=p)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ günlük
def test_her_kaynaktan_satir_ve_zaman_sirasi(veri):
    c, _, sid, _ = veri
    g = _gunluk(c, senaryo=sid, boyut=500)
    assert {x["tur"] for x in g["kayitlar"]} >= {"parametre", "fiyat", "fire", "metin", "recete", "hesap", "teklif", "urun", "hedef", "havuz", "ambalaj", "kapasite", "satis"}
    assert g["toplam"] == len(g["kayitlar"]) and g["sayfa"] == 1
    kaynaklar = {x["id"].split(":")[0] for x in g["kayitlar"]}
    assert kaynaklar >= {"degisiklik", "parametre", "fiyat", "fire", "metin", "recete", "hesap", "teklif"}
    zamanlar = [x["zaman"] for x in g["kayitlar"]]
    assert zamanlar == sorted(zamanlar, reverse=True)
    assert all(x["kullanici"] for x in g["kayitlar"])


def test_satir_alanlari_ve_urun_kodu(veri):
    c, _, sid, hid = veri
    g = _gunluk(c, senaryo=sid, boyut=500)["kayitlar"]
    hesap = next(x for x in g if x["id"] == f"hesap:{hid}")
    assert hesap["urun_kodu"] == "TEST" and hesap["senaryo_id"] == sid and hesap["kullanici"] == "esma" and hesap["tur"] == "hesap"
    par = next(x for x in g if x["tur"] == "parametre" and x["baslik"] == "Parametre: USD kuru")
    assert (par["neden"], par["kullanici"]) == ("kur güncellemesi", "esma") and D_(par["eski"]) == D_("50") and D_(par["yeni"]) == D_("55")
    urun = next(x for x in g if x["tur"] == "urun")
    assert urun["urun_kodu"] == "TEST" and "Ad: Test 2" in urun["yeni"]
    kap = next(x for x in g if x["tur"] == "kapasite")
    assert kap["urun_kodu"] == "TEST" and kap["neden"] == "ilk kapasite"
    satis = next(x for x in g if x["tur"] == "satis")
    assert satis["urun_kodu"] == "TEST"
    assert any(x["tur"] == "teklif" and x["urun_kodu"] == "TEST" for x in g)


def test_suzgecler(veri):
    c, oturum, sid, _ = veri
    assert {x["tur"] for x in _gunluk(c, senaryo=sid, tur="fire", boyut=500)["kayitlar"]} == {"fire"}
    iki = _gunluk(c, senaryo=sid, tur=["fire", "metin"], boyut=500)["kayitlar"]
    assert {x["tur"] for x in iki} == {"fire", "metin"}
    assert _gunluk(c, senaryo=sid, kullanici="esma", tur="fiyat", boyut=500)["toplam"] == 1   # yalnız esma'nın zam kaydı
    assert _gunluk(c, senaryo=sid, kullanici="yok-kisi")["toplam"] == 0
    assert all(x["urun_kodu"] == "TEST" for x in _gunluk(c, senaryo=sid, urun_kodu="tes", boyut=500)["kayitlar"])
    assert _gunluk(c, senaryo=sid, urun_kodu="yokkod")["toplam"] == 0
    q = _gunluk(c, senaryo=sid, q="kur güncellemesi")["kayitlar"]
    assert len(q) == 1 and q[0]["tur"] == "parametre"
    bugun = date.today().isoformat()
    assert _gunluk(c, senaryo=sid, bas=bugun, son=bugun)["toplam"] > 0
    dun = (date.today() - timedelta(days=1)).isoformat()
    assert _gunluk(c, senaryo=sid, son=dun)["toplam"] == 0
    yarin = (date.today() + timedelta(days=1)).isoformat()
    assert _gunluk(c, senaryo=sid, bas=yarin)["toplam"] == 0
    assert c.get(f"{A}/gunluk", params={"tur": "olmayan"}).status_code == 422
    assert c.get(f"{A}/gunluk", params={"bas": yarin, "son": dun}).status_code == 422
    assert c.get(f"{A}/gunluk", params={"senaryo": 9999}).status_code == 404


def test_senaryo_suzgeci_baska_senaryoyu_icermez(veri):
    c, oturum, sid, _ = veri
    s2 = c.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "B"}).json()["id"]
    assert c.post(f"{A}/parametreler/kur.USD/degerler?senaryo={s2}", json={"deger": "60", "gecerlilik_basi": "2026-07-01", "neden": "b senaryosu"}).status_code == 201
    b = _gunluk(c, senaryo=s2, boyut=500)["kayitlar"]
    assert b and all(x["senaryo_id"] in (s2, None) for x in b)
    assert not any(x["neden"] == "kur güncellemesi" for x in b)
    assert any(x["neden"] == "b senaryosu" for x in _gunluk(c, boyut=500)["kayitlar"])   # senaryosuz çağrı hepsini döndürür


def test_sayfalama(veri):
    c, _, sid, _ = veri
    tum = _gunluk(c, senaryo=sid, boyut=500)
    ilk = _gunluk(c, senaryo=sid, boyut=5, sayfa=1)
    ikinci = _gunluk(c, senaryo=sid, boyut=5, sayfa=2)
    assert ilk["toplam"] == ikinci["toplam"] == tum["toplam"] and len(ilk["kayitlar"]) == 5
    assert [x["id"] for x in ilk["kayitlar"] + ikinci["kayitlar"]] == [x["id"] for x in tum["kayitlar"][:10]]
    assert _gunluk(c, senaryo=sid, boyut=5, sayfa=999)["kayitlar"] == []


def test_geri_alinabilir_kurali(veri):
    c, _, sid, _ = veri
    g = _gunluk(c, senaryo=sid, boyut=500)["kayitlar"]
    for x in g:
        if x["geri_alinabilir"]:
            assert x["tur"] in ("parametre", "fiyat", "fire", "recete") and x["geri_al"]["yol"].startswith("/api/v1/") and x["geri_al"]["govde"]
        else:
            assert x["geri_al"] is None
    par = next(x for x in g if x["baslik"] == "Parametre: USD kuru")
    assert par["geri_alinabilir"] and par["geri_al"]["yol"] == f"/api/v1/parametreler/kur.USD/degerler?senaryo={sid}"
    assert D_(par["geri_al"]["govde"]["deger"]) == D_("50") and par["geri_al"]["govde"]["gecerlilik_basi"] == date.today().isoformat()
    # ilk kayıtların (eski değeri yok) geri alması yok; yalnız en son kayıt geri alınabilir
    kur_satirlari = [x for x in g if x["baslik"] == "Parametre: USD kuru"]
    assert sum(x["geri_alinabilir"] for x in kur_satirlari) == 1 and len(kur_satirlari) == 2
    fire = [x for x in g if x["tur"] == "fire"]
    assert sorted(x["geri_alinabilir"] for x in fire) == [False, True]
    assert all(x["geri_alinabilir"] is False for x in g if x["tur"] in ("metin", "hesap", "teklif", "urun", "hedef", "havuz", "ambalaj", "kapasite", "satis"))


def test_geri_al_govdesi_mevcut_uclarla_calisir(veri):
    c, _, sid, _ = veri
    g = _gunluk(c, senaryo=sid, boyut=500)["kayitlar"]
    for tur in ("parametre", "fiyat", "fire"):
        x = next(x for x in g if x["tur"] == tur and x["geri_alinabilir"])
        r = c.post(x["geri_al"]["yol"], json=x["geri_al"]["govde"], headers={"X-Kullanici": "esma"})
        assert r.status_code == 201, (tur, r.text)
    # geri alma yeni kayıt olarak eklendi: parametre geçerli değeri eski değere döndü
    assert D_(c.get(f"{A}/parametreler?senaryo={sid}&tarih={date.today().isoformat()}").json()["kur.USD"]) == D_("50")
    assert len(c.get(f"{A}/parametreler/kur.USD/gecmis?senaryo={sid}").json()["kayitlar"]) == 3


def test_recete_etkinlestir_ve_geri_al(veri):
    c, oturum, sid, _ = veri
    vs = {v["versiyon"]: v for v in c.get(f"{A}/urunler/TEST/recete/versiyonlar?senaryo={sid}").json()["kayitlar"]}
    assert vs[2]["aktif"] and not vs[1]["aktif"]
    g = _gunluk(c, senaryo=sid, tur="recete", boyut=500)["kayitlar"]
    v2 = next(x for x in g if x["baslik"].startswith("Reçete sürümü v2"))
    assert v2["geri_alinabilir"] and v2["geri_al"]["yol"] == f"/api/v1/urunler/TEST/recete/1/etkinlestir?senaryo={sid}" and v2["eski"] == "v1" and v2["yeni"] == "v2"
    assert "1 satır" in v2["baslik"]
    assert not next(x for x in g if x["baslik"].startswith("Reçete sürümü v1"))["geri_alinabilir"]
    r = c.post(v2["geri_al"]["yol"], json=v2["geri_al"]["govde"], headers={"X-Kullanici": "esma"})
    assert r.status_code == 200 and r.json() == {"id": vs[1]["id"], "versiyon": 1, "aktif": True}
    vs2 = {v["versiyon"]: v for v in c.get(f"{A}/urunler/TEST/recete/versiyonlar?senaryo={sid}").json()["kayitlar"]}
    assert vs2[1]["aktif"] and not vs2[2]["aktif"] and len(vs2) == 2   # yeni sürüm açılmadı
    k = oturum.query(m.DegisiklikKaydi).filter_by(tablo="recete", islem="etkinlestir").one()
    assert k.kullanici == "esma" and k.eski == {"aktif_versiyon": 2} and k.yeni["aktif_versiyon"] == 1 and k.yeni["_neden"]
    assert any(x["tur"] == "recete" and x["baslik"] == "Reçete sürümü etkinleştirildi" for x in _gunluk(c, senaryo=sid, boyut=500)["kayitlar"])
    assert c.post(f"{A}/urunler/TEST/recete/9/etkinlestir?senaryo={sid}", json={"neden": "x"}).status_code == 404
    assert c.post(f"{A}/urunler/TEST/recete/1/etkinlestir?senaryo={sid}", json={}).status_code == 422


def test_sorgu_sayisi_veri_miktarindan_bagimsiz(veri):
    c, oturum, sid, _ = veri
    sayac = []
    motor = oturum.get_bind()
    dinle = lambda conn, cur, stmt, *a: sayac.append(stmt)
    event.listen(motor, "before_cursor_execute", dinle)
    try:
        sayac.clear(); _gunluk(c, senaryo=sid, boyut=500); az = len(sayac)
        for i in range(15):
            c.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"fiyat": str(7 + i), "gecerlilik_basi": "2026-07-01", "neden": f"n{i}"})
            c.post(f"{A}/parametreler/kur.EUR/degerler?senaryo={sid}", json={"deger": str(61 + i), "gecerlilik_basi": "2026-07-01", "neden": f"p{i}"})
            c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"})
        sayac.clear(); g = _gunluk(c, senaryo=sid, boyut=500); cok = len(sayac)
    finally:
        event.remove(motor, "before_cursor_execute", dinle)
    assert g["toplam"] > 60 and cok == az, (az, cok)


def test_ozet(veri):
    c, _, sid, _ = veri
    o = c.get(f"{A}/gunluk/ozet", params={"senaryo": sid, "gun": 7}).json()
    tum = _gunluk(c, senaryo=sid)
    assert o["gun"] == 7 and o["toplam"] == tum["toplam"] > 0
    assert sum(x["adet"] for x in o["kullanici_bazinda"]) == o["toplam"] == sum(x["adet"] for x in o["tur_bazinda"])
    kul = {x["kullanici"]: x["adet"] for x in o["kullanici_bazinda"]}
    assert kul["esma"] > 0 and "sistem" in kul
    assert o["kullanici_bazinda"][0]["adet"] >= o["kullanici_bazinda"][-1]["adet"]
    assert c.get(f"{A}/gunluk/ozet", params={"gun": 0}).status_code == 422
    assert c.get(f"{A}/gunluk/ozet", params={"senaryo": 9999}).status_code == 404


def test_xlsx(veri):
    c, _, sid, _ = veri
    r = c.get(f"{A}/disa-aktar/gunluk.xlsx", params={"senaryo": sid, "tur": "fire"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    ws = load_workbook(BytesIO(r.content)).active
    satirlar = list(ws.iter_rows(values_only=True))
    assert satirlar[0][:4] == ("Zaman", "Kullanıcı", "Tür", "Başlık") and len(satirlar) == 3
    assert {x[2] for x in satirlar[1:]} == {"Fire kuralı"}
    assert c.get(f"{A}/disa-aktar/gunluk.xlsx", params={"tur": "olmayan"}).status_code == 422


# ------------------------------------------------------------------ arşiv
def test_arsiv_agaci_ve_kayitlar(veri):
    c, oturum, sid, hid = veri
    s2 = c.post(f"{A}/senaryolar", json={"sezon_ad": "2025-2026", "tur": "gerceklesen", "ad": "Eski"}).json()["id"]
    agac = c.get(f"{A}/arsiv").json()["sezonlar"]
    assert [z["ad"] for z in agac] == ["2026-2027", "2025-2026"] or {z["ad"] for z in agac} == {"2026-2027", "2025-2026"}
    sen = next(x for z in agac for x in z["senaryolar"] if x["id"] == sid)
    assert (sen["urun_sayisi"], sen["hesap_sayisi"], sen["teklif_sayisi"], sen["kilitli"], sen["kaynak_dosya"]) == (1, 1, 1, False, None)
    assert sen["tur"] == "fiyat_calismasi" and sen["olusturma_zamani"]
    bos = next(x for z in agac for x in z["senaryolar"] if x["id"] == s2)
    assert (bos["urun_sayisi"], bos["hesap_sayisi"], bos["teklif_sayisi"]) == (0, 0, 0) and bos["tur"] == "gerceklesen"
    # ikinci hesap: farklı tarih; liste tarih sırasıyla (en yeni önce)
    h2 = c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-11-05"}).json()["id"]
    k = c.get(f"{A}/arsiv/senaryo/{sid}/kayitlar").json()
    assert k["toplam"] == 2 and [x["id"] for x in k["kayitlar"]] == [h2, hid]
    ilk = k["kayitlar"][0]
    assert ilk["urun_kodu"] == "TEST" and ilk["urun_ad"] == "Test 2" and ilk["hesap_tarihi"] == "2026-11-05" and ilk["teklif_sayisi"] == 0
    assert D_(ilk["maliyet_tl"]) > 0 and D_(ilk["satis_tl"]) > 0 and ilk["olusturan"] and ilk["olusturma_zamani"]
    assert k["kayitlar"][1]["teklif_sayisi"] == 1
    assert c.get(f"{A}/arsiv/senaryo/{sid}/kayitlar", params={"boyut": 1, "sayfa": 2}).json()["kayitlar"][0]["id"] == hid
    assert c.get(f"{A}/arsiv/senaryo/{sid}/kayitlar", params={"urun_kodu": "yok"}).json()["toplam"] == 0
    assert c.get(f"{A}/arsiv/senaryo/9999/kayitlar").status_code == 404


def test_hesap_nedeni_arsivde(veri):
    c, _, sid, _ = veri
    r = c.post(f"{A}/urunler/TEST/kaydet", json={"senaryo_id": sid, "tarih": "2026-10-22", "neden": "kur revizyonu", "hesabi_kaydet": True})
    assert r.status_code == 200, r.text
    ilk = c.get(f"{A}/arsiv/senaryo/{sid}/kayitlar").json()["kayitlar"][0]
    assert ilk["id"] == r.json()["hesap_id"] and ilk["neden"] == "kur revizyonu"
    assert any(x["tur"] == "hesap" and x["neden"] == "kur revizyonu" for x in _gunluk(c, senaryo=sid, boyut=500)["kayitlar"])


def test_kaynak_dosya_import_ve_aktarim(istemci, oturum, excel_yolu):
    s = oturum
    o = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak", kaynak_dosya="berrak.xlsx")
    s.flush()
    assert s.get(m.Senaryo, o["senaryo_id"]).kaynak_dosya == "berrak.xlsx"
    r = istemci.post(f"{A}/import/excel-tam", data={"sezon_ad": "2027-2028", "senaryo_ad": "Yeni"}, files={"dosya": ("C:\\klasor\\kitap-1.xlsx", excel_yolu.read_bytes())})
    assert r.status_code == 200, r.text
    agac = istemci.get(f"{A}/arsiv").json()["sezonlar"]
    sen = next(x for z in agac for x in z["senaryolar"] if x["id"] == r.json()["senaryo_id"])
    assert sen["kaynak_dosya"] == "kitap-1.xlsx"   # yol bileşenleri atılır


def test_kiyas_decimal_farklar(veri):
    c, oturum, sid, hid = veri
    oturum.add(m.Malzeme(kod="KAP", ad="Kapak")); oturum.commit()   # ekrandan eklenen satırın malzeme kartı olmalı (D3b)
    assert c.post(f"{A}/urunler/TEST/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "3", "birim": "AD"},
                                                                  {"malzeme_kodu": "KAP", "ad": "Kapak", "miktar": "1", "birim": "AD", "birim_fiyat_elle": "1.5"}]).status_code == 201
    h2 = c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-22"}).json()["id"]
    r = c.get(f"{A}/arsiv/kiyas", params={"hesap_a": hid, "hesap_b": h2})
    assert r.status_code == 200, r.text
    k = r.json()
    assert k["a"]["id"] == hid and k["b"]["id"] == h2 and k["uyari"] is None and k["a"]["urun_kodu"] == "TEST"
    hesaplar = {x["id"]: oturum.get(m.MaliyetHesabi, x["id"]) for x in (k["a"], k["b"])}
    for t in k["toplamlar"]:
        a, b = hesaplar[hid].sonuc_snapshot[t["alan"]], hesaplar[h2].sonuc_snapshot[t["alan"]]
        assert t["a"] == a and t["b"] == b and D_(t["fark"]) == D_(b) - D_(a)
    assert {t["alan"] for t in k["toplamlar"]} >= {"malzeme_toplami", "finansman_dahil_maliyet_tl"}
    assert {t["alan"] for t in k["fiyatlar"]} == {"satis_fiyati_tl", "suzme_kg_fiyati_tl"}
    mal = {x["malzeme_kodu"]: x for x in k["satirlar"]}
    assert mal["KAV"]["durum"] == "ortak" and D_(mal["KAV"]["fark"]) == D_(mal["KAV"]["b_tutar"]) - D_(mal["KAV"]["a_tutar"]) > 0
    assert mal["KAP"]["durum"] == "sadece_b" and mal["KAP"]["a_tutar"] is None and D_(mal["KAP"]["fark"]) == D_(mal["KAP"]["b_tutar"])
    assert all(isinstance(x["fark"], str) for x in k["satirlar"])


def test_kiyas_farkli_urun_uyarisi_ve_hatalar(veri):
    c, _, sid, hid = veri
    assert c.put(f"{A}/urunler/DIGER", json={"ad": "Diğer", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu", "suzme_kg": "0.18"}).status_code == 200
    assert c.put(f"{A}/urunler/DIGER/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "65000", "dolum_personel": "13", "etiketleme_adedi": "35000",
                 "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"}).status_code == 200
    assert c.post(f"{A}/urunler/DIGER/recete?senaryo={sid}", json=[{"malzeme_kodu": "KAV", "ad": "Kavanoz", "miktar": "1", "birim": "AD"}]).status_code == 201
    h2 = c.post(f"{A}/urunler/DIGER/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-22"}).json()["id"]
    k = c.get(f"{A}/arsiv/kiyas", params={"hesap_a": hid, "hesap_b": h2}).json()
    assert k["uyari"] and "TEST" in k["uyari"] and "DIGER" in k["uyari"]
    assert c.get(f"{A}/arsiv/kiyas", params={"hesap_a": hid, "hesap_b": 9999}).status_code == 404
    assert c.get(f"{A}/arsiv/kiyas", params={"hesap_a": hid}).status_code == 422


# ------------------------------------------------------------------ kilit
def test_kilit_akisi(veri):
    c, oturum, sid, hid = veri
    put = lambda: c.put(f"{A}/uretim-kapasitesi/TEST?senaryo={sid}", json={**KAP, "hedef_uretim": "999", "neden": "deneme"}, headers={"X-Kullanici": "esma"})
    assert c.get(f"{A}/senaryolar").json()["kayitlar"][0]["kilitli"] is False
    assert c.post(f"{A}/senaryolar/{sid}/kilitle", json={}).status_code == 422                       # neden zorunlu
    assert c.post(f"{A}/senaryolar/{sid}/kilitle", json={"neden": "  "}).status_code == 422
    r = c.post(f"{A}/senaryolar/{sid}/kilitle", json={"neden": "Teklif gönderildi"}, headers={"X-Kullanici": "esma"})
    assert r.status_code == 200 and r.json()["kilitli"] is True and r.json()["id"] == sid
    assert c.get(f"{A}/senaryolar").json()["kayitlar"][0]["kilitli"] is True
    # yazma uçları 409; hesapla ve okuma serbest
    for yanit in (put(),
                  c.post(f"{A}/parametreler/kur.USD/degerler?senaryo={sid}", json={"deger": "1", "gecerlilik_basi": "2026-07-01", "neden": "x"}),
                  c.post(f"{A}/malzemeler/KAV/fiyatlar?senaryo={sid}", json={"fiyat": "1", "gecerlilik_basi": "2026-07-01", "neden": "x"}),
                  c.post(f"{A}/urunler/TEST/recete/1/etkinlestir?senaryo={sid}", json={"neden": "x"}),
                  c.post(f"{A}/urunler/TEST/hesaplar", json={"senaryo_id": sid, "tarih": "2026-10-21"}),
                  c.post(f"{A}/urunler/TEST/kaydet", json={"senaryo_id": sid, "tarih": "2026-10-21", "neden": "x", "hesabi_kaydet": True}),
                  c.post(f"{A}/hesaplar/{hid}/teklifler", json={"kar_orani": "0.3"}),
                  c.put(f"{A}/gider-havuzlari/pazarlama?senaryo={sid}", json={"ad": "P", "neden": "x", "toplam_tutar": "1", "baz_tipi": "adet"})):
        assert yanit.status_code == 409 and yanit.json()["mesaj"] == "A çalışması kilitli; değişiklik için önce kilidi açın.", yanit.text
    teklif_id = c.get(f"{A}/hesaplar/{hid}/teklifler").json()["kayitlar"][0]["id"]
    assert c.patch(f"{A}/teklifler/{teklif_id}/durum", json={"durum": "gonderildi"}).status_code == 409
    assert c.post(f"{A}/urunler/TEST/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"}).status_code == 200
    assert c.get(f"{A}/parametreler?senaryo={sid}").status_code == 200
    # günlükte kilitli senaryoda geri alınamaz
    assert not any(x["geri_alinabilir"] for x in _gunluk(c, senaryo=sid, boyut=500)["kayitlar"])
    assert c.post(f"{A}/senaryolar/{sid}/kilitle", json={"neden": "tekrar"}).status_code == 422          # zaten kilitli
    # başka senaryo etkilenmez
    s2 = c.post(f"{A}/senaryolar", json={"sezon_ad": "2026-2027", "tur": "fiyat_calismasi", "ad": "B"}).json()["id"]
    assert c.post(f"{A}/parametreler/kur.USD/degerler?senaryo={s2}", json={"deger": "1", "gecerlilik_basi": "2026-07-01", "neden": "x"}).status_code == 201
    # kilit aç
    assert c.post(f"{A}/senaryolar/{sid}/kilit-ac", json={}).status_code == 422
    r = c.post(f"{A}/senaryolar/{sid}/kilit-ac", json={"neden": "Revizyon gerekti"}, headers={"X-Kullanici": "ayse"})
    assert r.status_code == 200 and r.json()["kilitli"] is False
    assert put().status_code == 200
    assert c.post(f"{A}/senaryolar/{sid}/kilit-ac", json={"neden": "x"}).status_code == 422             # zaten açık
    assert c.post(f"{A}/senaryolar/9999/kilitle", json={"neden": "x"}).status_code == 404
    kayitlar = oturum.query(m.DegisiklikKaydi).filter_by(tablo="senaryo", kayit_id=sid).order_by(m.DegisiklikKaydi.id).all()
    assert [(k.islem, k.kullanici, k.eski, k.yeni) for k in kayitlar] == [
        ("kilitle", "esma", {"kilitli": False}, {"kilitli": True, "_neden": "Teklif gönderildi"}),
        ("kilit_ac", "ayse", {"kilitli": True}, {"kilitli": False, "_neden": "Revizyon gerekti"})]
    g = _gunluk(c, senaryo=sid, q="Revizyon gerekti")["kayitlar"]
    assert len(g) == 1 and g[0]["baslik"] == "Senaryo kilidi açıldı" and g[0]["kullanici"] == "ayse" and g[0]["neden"] == "Revizyon gerekti"


def test_kilitli_senaryoda_aktarim_ve_import_409(veri, excel_yolu):
    c, _, sid, _ = veri
    assert c.post(f"{A}/senaryolar/{sid}/kilitle", json={"neden": "kapandı"}).status_code == 200
    dosya = {"dosya": ("k.xlsx", excel_yolu.read_bytes())}
    for yol, veri_ in ((f"{A}/aktarim/uretim-adetleri/uygula", {"senaryo": sid, "neden": "x"}),
                       (f"{A}/aktarim/gider-dagitim/uygula", {"senaryo": sid, "neden": "x"}),
                       (f"{A}/aktarim/satin-alma/uygula", {"senaryo": sid, "neden": "x", "gecerlilik_basi": "2026-07-01"}),
                       (f"{A}/import/fiyat-listesi/uygula", {"senaryo": sid, "neden": "x", "gecerlilik_basi": "2026-07-01"}),
                       (f"{A}/import/excel-tam", {"senaryo_id": sid})):
        r = c.post(yol, data=veri_, files=dosya)
        assert r.status_code == 409 and r.json()["mesaj"] == "A çalışması kilitli; değişiklik için önce kilidi açın.", (yol, r.text)
    assert c.post(f"{A}/import/fiyat-listesi", data={"senaryo": sid}, files=dosya).status_code != 409   # önizleme salt okunur


def test_eski_veritabanina_kolonlar_eklenir():
    engine = motor_olustur("sqlite://")
    with engine.begin() as bag:
        bag.exec_driver_sql("CREATE TABLE senaryo (id INTEGER PRIMARY KEY, sezon_id INTEGER, tur VARCHAR(20), ad VARCHAR(100), aciklama VARCHAR(500), olusturan VARCHAR(64))")
        bag.exec_driver_sql("INSERT INTO senaryo (sezon_id, tur, ad) VALUES (1, 'fiyat_calismasi', 'eski')")
    assert {"senaryo.kilitli", "senaryo.kaynak_dosya"} <= set(eksik_kolonlari_tamamla(engine))
    assert eksik_kolonlari_tamamla(engine) == []
    with engine.connect() as bag:
        assert bag.exec_driver_sql("SELECT kilitli, kaynak_dosya FROM senaryo").one() == (0, None)


def test_gunluk_tarih_suzgeci_yerel_gun_sinirini_kullanir():
    """bas/son yerel takvim günüdür: yerel gece yarısından 1 dk önceki kayıt önceki güne, tam gece yarısındaki kayıt o güne düşer
    (saklanan damgalar naif UTC; eski davranış UTC gece yarısı aldığı için TR'de 00:00-03:00 kayıtları kayıyordu)."""
    from datetime import date, datetime, time, timedelta, timezone
    from backend.servisler.gunluk_servisi import Suzgec, _suz
    d = date(2026, 10, 22)
    yerel_gece = datetime.combine(d, time.min).astimezone()
    utc_naif = lambda z: z.astimezone(timezone.utc).replace(tzinfo=None)
    satir = lambda z, pk: {"id": f"x:{pk}", "_z": utc_naif(z), "_pk": pk, "kullanici": "esma", "tur": "fiyat", "baslik": "", "urun_kodu": None}
    kayitlar = [satir(yerel_gece - timedelta(minutes=1), 1), satir(yerel_gece, 2), satir(yerel_gece + timedelta(hours=23, minutes=59), 3),
                satir(yerel_gece + timedelta(days=1), 4)]
    assert sorted(r["_pk"] for r in _suz(kayitlar, Suzgec(bas=d, son=d))) == [2, 3]   # süzgeç en yeniden eskiye sıralar
    assert [r["_pk"] for r in _suz(kayitlar, Suzgec(son=d - timedelta(days=1)))] == [1]
    assert [r["_pk"] for r in _suz(kayitlar, Suzgec(bas=d + timedelta(days=1)))] == [4]


def test_havuz_carpanlari_gunlukte_okunur(veri):
    """G3: taban × çarpan girilen havuzun günlük satırında çarpanlar JSON yerine 'taban × 1,35 (SGK) × 1,30 (zam) = toplam' biçiminde görünür."""
    c, _, sid, _ = veri
    r = c.put(f"{A}/gider-havuzlari/pazarlama?senaryo={sid}", headers={"X-Kullanici": "esma"},
              json={"ad": "Pazarlama", "neden": "SGK ve zam", "taban_tutar": "1000.10", "baz_tipi": "adet",
                    "carpanlar": [{"ad": "SGK", "deger": "1.35"}, {"ad": "zam", "deger": "1.30"}]})
    assert r.status_code == 200, r.text
    satir = max((x for x in _gunluk(c, senaryo=sid, tur="havuz")["kayitlar"]), key=lambda x: x["zaman"])
    assert satir["yeni"] is not None and "×" in satir["yeni"] and "SGK" in satir["yeni"] and "zam" in satir["yeni"]
    assert "1.000,10 × 1,35 (SGK) × 1,30 (zam) = 1.755,18" in satir["yeni"]
    assert '"deger"' not in satir["yeni"] and "[{" not in satir["yeni"]
    assert satir["eski"] is not None and "17.000.000,00" in satir["eski"] and "×" not in satir["eski"]
    assert satir["neden"] == "SGK ve zam"
    # 3 çarpan ve uzun ad: metin 60 karakteri aşar, toplam yine görünür (kesilmez)
    r = c.put(f"{A}/gider-havuzlari/pazarlama?senaryo={sid}", headers={"X-Kullanici": "esma"},
              json={"ad": "Pazarlama", "neden": "ikramiye", "taban_tutar": "17000000", "baz_tipi": "adet",
                    "carpanlar": [{"ad": "SGK işveren payı", "deger": "1.35"}, {"ad": "zam", "deger": "1.30"}, {"ad": "ikramiye", "deger": "1.10"}]})
    assert r.status_code == 200, r.text
    satir = max((x for x in _gunluk(c, senaryo=sid, tur="havuz")["kayitlar"]), key=lambda x: x["zaman"])
    assert satir["yeni"].endswith("= 32.818.500,00 TL"), satir["yeni"]
    assert "17.000.000,00 × 1,35 (SGK işveren payı) × 1,30 (zam) × 1,10 (ikramiye)" in satir["yeni"]


# ------------------------------------------------------------------ D5: günlükte okunur metin (ham Python/JSON yok)
def test_fark_metni_okunur_turkce():
    from backend.servisler.gunluk_servisi import fark_metni
    adlar = {2: "Test Bütçe 2026-2027"}
    _, y, n = fark_metni(None, {"recete": 12, "kaynak_senaryo_id": 2, "_neden": "sezon"}, tablo="senaryo", senaryo_adlari=adlar)
    assert y == "Kopyalanan reçete: 12; Kaynak çalışma: Test Bütçe 2026-2027" and n == "sezon"
    _, y, _ = fark_metni(None, {"adet": "10", "birim_maliyet": "30.81388087306671547542783930", "enflasyon": None, "senaryo_id": 2,
                                "_neden": "sayım"}, tablo="stok_devri")
    assert y == "Adet: 10; Birim maliyet: 30,8139 TL"   # boş alan ve kimlik yazılmaz, birim fiyat 4 hane
    _, y, _ = fark_metni(None, {"eklenen": 5, "atlanan_kayitli": 0}, tablo="satis_gecmisi")
    assert y == "Eklenen satır: 5"
    _, y, _ = fark_metni(None, {"yazilan": 3, "bolenler": {"yurtici": "0.63", "yurtdisi": "0.85"}}, tablo="liste_fiyati")
    assert y == "Yazılan satır: 3; Bölenler: Yurtiçi 0,63, Yurtdışı 0,85"
    e, y, _ = fark_metni({"liste_fiyati": "6.4"}, {"urun_kodu": "T", "yil": 2025, "liste_fiyati": "7.36"}, tablo="liste_fiyati")
    assert (e, y) == ("Liste fiyatı: 6,40 TL", "Liste fiyatı: 7,36 TL")
    _, y, _ = fark_metni(None, {"anahtarlar": [["Kavanoz Hattı", "0.55", "18000000"], ["Teneke Hattı", "0.25", "1"], ["Sos Hattı", "0.2", "1"]]},
                         tablo="gider_havuzu")
    assert y == "Dağıtım anahtarları: Kavanoz Hattı %55, Teneke Hattı %25, Sos Hattı %20"
    e, y, n = fark_metni({"tur_no": 2, "kar_orani": "0.2", "fiyat_tl": "35.4359630040267227", "hesap_id": 5, "senaryo_id": 2, "durum": "taslak"},
                         {"_neden": "yanlış tur"}, tablo="teklif")
    assert e == "Tur: 2; Kâr oranı: %20; Fiyat: 35,436 TL; Durum: Taslak" and y is None and n == "yanlış tur"
    for metin in (e, y or ""):
        assert "{" not in metin and "[" not in metin and "None" not in metin and "_id" not in metin


def test_gunluk_ucu_okunur_metin(veri):
    c, _, sid, _ = veri
    for x in _gunluk(c, senaryo=sid, boyut=500)["kayitlar"]:
        for alan in ("eski", "yeni"):
            metin = x[alan] or ""
            assert not any(p in metin for p in ("{", "[[", "None", "senaryo_id", "_neden", "'")), (x["baslik"], metin)
    g = _gunluk(c, senaryo=sid, tur="hesap")["kayitlar"][0]
    assert g["yeni"].startswith("Maliyet: ") and g["yeni"].endswith(" TL") and "," in g["yeni"]
    t = _gunluk(c, senaryo=sid, tur="teklif")["kayitlar"][0]
    assert "Kâr oranı: %20" in t["yeni"] and "(Taslak)" in t["baslik"]
    f = next(x for x in _gunluk(c, senaryo=sid, tur="fiyat")["kayitlar"] if x["eski"])
    assert f["yeni"].endswith(" TL") and "," in f["yeni"]


# ------------------------------------------------------------------ D7: elle ekleme/silme uçlarında zorunlu neden
def test_satis_elle_ekle_sil_neden_zorunlu_ve_gunlukte(veri):
    c, _, sid, _ = veri
    govde = {"urun_kodu": "TEST", "musteri": "Örnek Müşteri B", "tarih": "2026-06-01", "fiyat": "12.5", "para_birimi": "TL", "adet": "3"}
    for g in (govde, {**govde, "neden": "  "}):
        r = c.post(f"{A}/satis-gecmisi", json=g)
        assert r.status_code == 422 and r.json()["mesaj"] == "Neden girin.", r.text
    kid = c.post(f"{A}/satis-gecmisi", json={**govde, "neden": "faturadan elle"}).json()["id"]
    for yol in (f"{A}/satis-gecmisi/{kid}", f"{A}/satis-gecmisi/{kid}?neden="):
        r = c.delete(yol)
        assert r.status_code == 422 and r.json()["mesaj"] == "Neden girin."
    assert c.delete(f"{A}/satis-gecmisi/{kid}?neden=m%C3%BCkerrer").status_code == 204
    satirlar = _gunluk(c, tur="satis", boyut=50)["kayitlar"]
    sil = next(x for x in satirlar if x["baslik"] == "Satış geçmişi silindi")
    assert sil["neden"] == "mükerrer" and sil["urun_kodu"] == "TEST" and "Fiyat: 12,50" in sil["eski"] and sil["yeni"] is None
    ekle = next(x for x in satirlar if x["neden"] == "faturadan elle")
    assert "Tarih: 01.06.2026" in ekle["yeni"] and "Müşteri: Örnek Müşteri B" in ekle["yeni"]


def test_teklif_sil_neden_zorunlu_ve_gunlukte(veri):
    c, _, sid, hid = veri
    tid = c.post(f"{A}/hesaplar/{hid}/teklifler", json={"kar_orani": "0.25"}).json()["id"]
    r = c.delete(f"{A}/teklifler/{tid}")
    assert r.status_code == 422 and r.json()["mesaj"] == "Neden girin."
    assert c.delete(f"{A}/teklifler/{tid}?neden=hatal%C4%B1%20tur").status_code == 204
    sil = next(x for x in _gunluk(c, senaryo=sid, tur="teklif")["kayitlar"] if x["baslik"] == "Teklif turu silindi")
    assert sil["neden"] == "hatalı tur" and "Kâr oranı: %25" in sil["eski"] and "hesap" not in sil["eski"].lower()


# ------------------------------------------------------------------ D6: hata mesajları kendi başına anlaşılır
def test_hata_mesajlari_okunur(veri):
    c, oturum, sid, _ = veri
    from backend.servisler import hesap_servisi as hs, kimlik_servisi as ks, liste_kurallari as lk
    from backend.servisler.hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi
    r = c.delete(f"{A}/senaryolar/{sid}")
    assert r.status_code == 409 and r.json()["mesaj"] == "Bu çalışmada 1 kayıtlı hesap var; kayıtlı hesabı olan çalışma silinemez."
    assert r.json()["alanlar"]["hesap_sayisi"] == 1   # alanlar makine için korunur
    assert c.put(f"{A}/urunler/YENI", json={"ad": "Yeni", "ambalaj_hacmi": "370", "hat": "Niko", "taze_tursu_sinifi": "Turşu/Turşu",
                                             "suzme_kg": "0.18"}).status_code == 200
    r = c.post(f"{A}/urunler/YENI/hesapla", json={"senaryo_id": sid, "tarih": "2026-10-21"})
    assert r.status_code == 404 and r.json()["kod"] == "hedef_yok"
    assert r.json()["mesaj"] == "YENI ürününün bu çalışmada üretim bilgisi yok; Üretim bilgileri bölümünden girin."
    with pytest.raises(DogrulamaHatasi) as e:
        lk.bolen_dogrula("1.5")
    assert e.value.mesaj == "Bölen 0'dan büyük ve en fazla 1 olmalı (ör. 0,63); girilen değer 1,5."
    ks.kullanici_olustur(oturum, "muhasebe1", "Muhasebe", "muhasebe", "gecici-sifre-123")
    with pytest.raises(CatismaHatasi) as e:
        ks.kullanici_olustur(oturum, "muhasebe1", "Muhasebe", "muhasebe", "gecici-sifre-123")
    assert e.value.mesaj == "muhasebe1 kullanıcı adı zaten var; başka bir ad seçin."
    with pytest.raises(DogrulamaHatasi, match="^Kullanıcı adı 3-64 karakter olmalı; "):
        ks.kullanici_olustur(oturum, "A", "Muhasebe", "muhasebe", "gecici-sifre-123")
    with pytest.raises(BulunamadiHatasi) as e:
        hs.urun_getir(oturum, "YOK-1")
    assert e.value.mesaj == "YOK-1 kodlu ürün bulunamadı."
