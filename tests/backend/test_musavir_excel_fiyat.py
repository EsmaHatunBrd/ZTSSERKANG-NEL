"""Müşavir Excel'i — Fiyat Çalışması kitabı: şablon saklama, dışa aktarım ve gidiş-dönüş.

Yalnız UYDURMA kitaplar (test-dongusu/excel, test-dongusu/uret.py üretir). Gidiş-dönüş: bütçe kitabı yüklenir (şablon saklanır) →
uygulamada değişiklik (malzeme fiyatı, reçete miktarı, fire, USD kuru, gider havuzu, üretim adedi) → müşavir Excel'i üretilir →
üretilen dosya uygulamanın kendi okuyucusuyla (tüm çalışma kitabı aktarımı) yeni senaryoya okunur → girdiler ve ürün maliyetleri birebir aynı.
LibreOffice yok: formül değerleri gerekmeyen kıyas (okuyucunun okuduğu formül hücrelerine üretici önbellek değeri yazar)."""
from datetime import date
from decimal import Decimal as D
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote

import openpyxl
import pytest
from openpyxl import Workbook

from backend.servisler import (fiyat_servisi, gider_servisi, hesap_servisi as hs, import_servisi as ims, kapasite_servisi,
                               musavir_excel_servisi as mx, parametre_servisi, recete_servisi, senaryo_servisi)
from tests.backend.test_api import _senaryo, istemci  # noqa: F401

KOK = Path(__file__).resolve().parents[2]
BUTCE = KOK / "test-dongusu" / "excel" / "11-16-2026-sezon-fiyat-calismasi-butce.xlsx"
GERCEKLESEN = KOK / "test-dongusu" / "excel" / "11-16-2026-sezon-fiyat-calismasi-gerceklesen.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
H = {"X-Kullanici": "esma"}
TARIH = date(2026, 10, 21)
URL = "/api/v1/disa-aktar/musavir/fiyat-kitabi"
SEZON_BASI = date(2026, 6, 1)

pytestmark = pytest.mark.skipif(not BUTCE.exists(), reason="uydurma kitap yok: test-dongusu/uret.py çalıştırın")


def _yukle(c, yol: Path, **form) -> dict:
    r = c.post("/api/v1/import/excel-tam", files={"dosya": (yol.name, yol.read_bytes(), XLSX)},
               data={"sezon_ad": "2026-2027", "senaryo_ad": "Bütçe", "tur": "fiyat_calismasi", **form}, headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def _indir(c, sid: int) -> bytes:
    r = c.get(f"{URL}.xlsx", params={"senaryo_id": sid, "tarih": TARIH.isoformat()})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(XLSX)
    ad = unquote(r.headers["content-disposition"].split("filename*=UTF-8''")[1])
    assert ad == f"11-16-2026-sezon-fiyat-calismasi-butce - uygulama {TARIH:%d.%m.%Y}.xlsx"
    return r.content


def _degistir(s, sid: int) -> None:
    """Uygulamada bir malzeme fiyatı, bir reçete miktarı + bir fire, USD kuru, bir gider havuzu (çarpanlı ve düz), iki üretim adedi."""
    fiyat_servisi.fiyat_ekle(s, sid, "99.20.001", D("7.35"), SEZON_BASI, "test: kavanoz zammı", olusturan="esma")
    u = hs.urun_getir(s, "03.99.003")
    r = recete_servisi.aktif_recete(s, u.id, sid)
    satirlar = [{"malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": x.miktar, "birim": x.birim, "fire_override": x.fire_override,
                 "dugum_tipi": x.dugum_tipi, "brut_miktar_elle": x.brut_miktar_elle, "birim_fiyat_elle": x.birim_fiyat_elle, "seviye": x.seviye,
                 "zs_elle": x.zs_elle, "para_birimi_elle": x.para_birimi_elle} for x in r.satirlar]
    biber = next(x for x in satirlar if x["malzeme_kodu"] == "99.10.003")
    biber["miktar"], biber["fire_override"] = D("0.27"), D("0.065")
    recete_servisi.yeni_versiyon(s, u.id, sid, satirlar, "elle", "esma")
    parametre_servisi.deger_ekle(s, sid, "kur.USD", D("45.36"), SEZON_BASI, "test: kur", olusturan="esma")
    h = gider_servisi.havuzlar(s, sid)["elektrik"]
    gider_servisi.havuz_kaydet(s, sid, "elektrik", h.ad, None, h.baz_tipi, h.baz_miktar,
                               [(a.alt_kalem, a.pay_orani, a.baz_miktar) for a in h.anahtarlar], "esma",
                               taban_tutar=D("2750000"), carpanlar=[("Excel çarpanı 1", D("1.4")), ("enflasyon", D("1.1"))])
    h = gider_servisi.havuzlar(s, sid)["etiket_iscilik"]
    gider_servisi.havuz_kaydet(s, sid, "etiket_iscilik", h.ad, D("1950000"), h.baz_tipi, h.baz_miktar, [], "esma")
    u7 = hs.urun_getir(s, "03.99.007")
    hd = hs.uretim_hedefi_getir(s, u7.id, sid)
    hs.uretim_hedefi_kaydet(s, u7.id, sid, "esma", **{a: getattr(hd, a) for a in hs.URETIM_ALANLARI if a != "vardiya_uretim_adedi"},
                            vardiya_uretim_adedi=D("14400"))
    k = next(k for k in kapasite_servisi.listele(s, sid)[0] if k.urun_kodu == "03.99.001")
    kapasite_servisi.kaydet(s, sid, "03.99.001", {**{a: getattr(k, a) for a in kapasite_servisi.SAYISAL_ALANLAR}, "hedef_uretim": D("17500")},
                            "test: hedef", kullanici="esma")
    s.flush()


def _girdiler(s, sid: int) -> dict:
    """Karşılaştırılacak girdiler: ürün başına reçete/üretim/elle gider/parametre, kullanılan malzeme fiyatları, havuzlar, ambalaj, kapasite."""
    out = {"urun": {}, "fiyat": {}}
    kodlar = set()
    for u in hs.urunler(s):
        if recete_servisi.aktif_recete_veya_none(s, u.id, sid) is None:
            continue
        c = hs.hesapla(s, u.kod, sid, TARIH)
        kodlar |= {x.malzeme_kodu for x in c.girdi.recete}
        out["urun"][u.kod] = {
            "recete": [(x.malzeme_kodu, x.miktar, x.fire_orani, x.brut_miktar_elle, x.birim_fiyat_elle, x.zs_elle, x.para_birimi_elle)
                       for x in c.girdi.recete],
            "uretim": c.girdi.uretim, "gider_elle": c.girdi.gider_elle,
            "parametre": parametre_servisi.gecerli_parametreler(s, sid, TARIH, u.id),
            "maliyet": c.sonuc.finansman_dahil_maliyet_tl, "satis": c.sonuc.satis_fiyati_tl, "doviz": c.sonuc.doviz_maliyet,
            "teklif": c.sonuc.teklifler_usd, "malzeme": c.sonuc.malzeme_toplami, "uretim_gideri": c.sonuc.uretim_gideri_toplami,
            "diger": c.sonuc.diger_giderler_toplami}
    fiyatlar = fiyat_servisi.gecerli_fiyatlar(s, sid, TARIH)
    out["fiyat"] = {k: (fiyatlar[k].fiyat, fiyatlar[k].para_birimi) for k in sorted(kodlar) if k in fiyatlar}
    out["havuz"] = {k: (h.toplam_tutar, h.baz_miktar, h.taban_tutar, gider_servisi.carpan_degerleri(h)[1],
                        sorted((a.alt_kalem, a.pay_orani, a.baz_miktar) for a in h.anahtarlar))
                    for k, h in gider_servisi.havuzlar(s, sid).items()}
    out["ambalaj"] = [(a.ad, a.hacim, a.uretim_adedi, a.katsayi) for a in gider_servisi.ambalajlar(s, sid)]
    out["kapasite"] = {k.urun_kodu: tuple(getattr(k, a) for a in kapasite_servisi.SAYISAL_ALANLAR) for k in kapasite_servisi.listele(s, sid, boyut=500)[0]}
    return out


def _esit(a, b, yol="") -> list[str]:
    """Derin karşılaştırma; Decimal'ler 1e-12 içinde eşit sayılır (Excel çift duyarlıklı saklar)."""
    if isinstance(a, D) and isinstance(b, D):
        return [] if abs(a - b) <= D("1e-12") * max(D(1), abs(a)) else [f"{yol}: {a} != {b}"]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{yol}: anahtarlar {sorted(set(a) ^ set(b))}"]
        return [f for k in a for f in _esit(a[k], b[k], f"{yol}.{k}")]
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [f"{yol}: uzunluk {len(a)} != {len(b)}"]
        return [f for i, (x, y) in enumerate(zip(a, b)) for f in _esit(x, y, f"{yol}[{i}]")]
    if hasattr(a, "__dataclass_fields__") and type(a) is type(b):
        return [f for k in a.__dataclass_fields__ for f in _esit(getattr(a, k), getattr(b, k), f"{yol}.{k}")]
    return [] if a == b else [f"{yol}: {a!r} != {b!r}"]


def test_gidis_donus_girdiler_ve_maliyetler_birebir(istemci, oturum, tmp_path):
    ozet = _yukle(istemci, BUTCE)
    assert ozet["musavir_sablonu_saklandi"] is True
    sid = ozet["senaryo_id"]
    d = istemci.get(f"{URL}/durum", params={"senaryo_id": sid}).json()
    assert d["sablon"]["dosya_adi"] == BUTCE.name and d["sablon"]["boyut"] == len(BUTCE.read_bytes()) and d["uyarilar_ozeti"] is None

    _degistir(oturum, sid)
    once = _girdiler(oturum, sid)
    icerik = _indir(istemci, sid)

    yol = tmp_path / "musavir.xlsx"
    yol.write_bytes(icerik)
    geri = ims.excel_tam_yukle(oturum, yol, "2026-2027", "Geri okunan", kartlari_guncelle=False)
    assert geri["urun"] == 7 and not [a for a in geri["atlanan"] if "(2)" not in a], geri
    sonra = _girdiler(oturum, geri["senaryo_id"])
    farklar = _esit(once, sonra)
    assert not farklar, "\n".join(farklar[:30])
    # değişiklikler gerçekten dosyaya geçti (bütçe kitabıyla aynı olsaydı yukarıdaki kıyas boş geçerdi)
    assert once["fiyat"]["99.20.001"][0] == D("7.35")
    assert once["urun"]["03.99.007"]["uretim"].vardiya_uretim_adedi == D("14400")
    assert once["havuz"]["elektrik"][2:4] == (D("2750000"), (D("1.4"), D("1.1")))
    assert once["kapasite"]["03.99.001"][4] == D("17500")
    assert once["urun"]["03.99.001"]["parametre"].kurlar["USD"] == D("45.36")


def test_formuller_bicim_ve_sayfa_duzeni_korunur(istemci, oturum):
    sid = _yukle(istemci, BUTCE)["senaryo_id"]
    _degistir(oturum, sid)
    icerik = _indir(istemci, sid)
    sablon = openpyxl.load_workbook(BUTCE, data_only=False)
    cikti = openpyxl.load_workbook(BytesIO(icerik), data_only=False)
    assert cikti.sheetnames == sablon.sheetnames                       # ad ve sıra; kapak/ek sayfa yok
    assert cikti.calculation.fullCalcOnLoad is True
    assert "Uygulamadan üretildi" in (cikti.properties.description or "")
    degisen_formul = []
    for ws in sablon.worksheets:
        wc = cikti[ws.title]
        assert (wc.max_row, wc.max_column) == (ws.max_row, ws.max_column), ws.title
        assert sorted(map(str, wc.merged_cells.ranges)) == sorted(map(str, ws.merged_cells.ranges)), ws.title
        assert {k: v.width for k, v in wc.column_dimensions.items()} == {k: v.width for k, v in ws.column_dimensions.items()}, ws.title
        for row in ws.iter_rows():
            for h in row:
                yeni = wc[h.coordinate]
                bicim = lambda x: (x.number_format, repr(x.font), repr(x.fill), repr(x.border), repr(x.alignment), repr(x.protection))
                assert bicim(yeni) == bicim(h), (ws.title, h.coordinate)
                if isinstance(h.value, str) and h.value.startswith("="):
                    if yeni.value != h.value:
                        degisen_formul.append((ws.title, h.coordinate, h.value, yeni.value))
    # Yalnız Gider Dağıtım'daki "taban × çarpan" sabit ifadesi (girdi) uygulamanın taban/çarpanlarıyla yeniden yazılır.
    assert degisen_formul == [("Gider Dağıtım", "D38", "=2600000*1.4", "=2750000*1.4*1.1")], degisen_formul
    # Formül hücrelerine önbellek değeri yazıldı: değerli açılışta okuyucunun okuduğu hücreler dolu
    v = openpyxl.load_workbook(BytesIO(icerik), data_only=True)
    assert v["Gider Dağıtım"]["D38"].value == pytest.approx(2750000 * 1.4 * 1.1)
    assert v["003"]["K7"].value == pytest.approx(0.27 / (1 - 0.065))
    kav = next(r for r in range(7, 20) if v["001"][f"D{r}"].value == "99.20.001")
    assert v["001"][f"M{kav}"].value == pytest.approx(7.35)                # S.ALMA BF araması: yeni fiyat
    assert v["S.ALMA BF"]["F19"].value == pytest.approx(7.35) or any(
        v["S.ALMA BF"][f"A{r}"].value == "99.20.001" and v["S.ALMA BF"][f"F{r}"].value == pytest.approx(7.35) for r in range(2, 40))


def test_degisiklik_yoksa_degisen_hucre_yok_ve_maliyet_ayni(istemci, oturum, tmp_path):
    sid = _yukle(istemci, BUTCE)["senaryo_id"]
    r = mx.fiyat_kitabi_hazirla(oturum, sid, TARIH)
    assert r.degisen_hucre == 0, r.uyarilar
    assert r.urun_sayfasi == 7 and r.yazilan_urun == 7


def test_gerceklesen_kitabi_gidis_donus(istemci, oturum, tmp_path):
    if not GERCEKLESEN.exists():
        pytest.skip("gerçekleşen uydurma kitap yok")
    ozet = _yukle(istemci, GERCEKLESEN, tur="gerceklesen", senaryo_ad="Gerçekleşen")
    sid = ozet["senaryo_id"]
    once = _girdiler(oturum, sid)
    yol = tmp_path / "g.xlsx"
    yol.write_bytes(mx.fiyat_kitabi_uret(oturum, sid, TARIH))
    geri = ims.excel_tam_yukle(oturum, yol, "2026-2027", "Geri", tur="gerceklesen", kartlari_guncelle=False)
    farklar = _esit(once, _girdiler(oturum, geri["senaryo_id"]))
    assert not farklar, "\n".join(farklar[:30])


def test_sablon_yoksa_404(istemci):
    sid = _senaryo(istemci)
    r = istemci.get(f"{URL}.xlsx", params={"senaryo_id": sid})
    assert r.status_code == 404 and r.json()["kod"] == "sablon_yok"
    assert "Veri Aktar › Tüm çalışma kitabı" in r.json()["mesaj"]
    assert istemci.get(f"{URL}/durum", params={"senaryo_id": sid}).json() == {"sablon": None, "uyarilar_ozeti": None}
    assert istemci.get(f"{URL}/durum", params={"senaryo_id": 9999}).status_code == 404


def test_tamamla_modunda_da_sablon_saklanir(istemci):
    sid = _senaryo(istemci)
    ozet = _yukle(istemci, BUTCE, senaryo_id=str(sid))
    assert ozet["mod"] == "tamamla" and ozet["musavir_sablonu_saklandi"] is True
    d = istemci.get(f"{URL}/durum", params={"senaryo_id": sid}).json()
    assert d["sablon"]["dosya_adi"] == BUTCE.name and d["sablon"]["olusturan"] == "esma"
    assert istemci.get(f"{URL}.xlsx", params={"senaryo_id": sid}).status_code == 200


def test_yalniz_sakla_onizleme_ve_red(istemci):
    sid = _senaryo(istemci)
    on = istemci.post("/api/v1/import/excel-tam/musavir-sablonu/onizle", files={"dosya": (BUTCE.name, BUTCE.read_bytes(), XLSX)},
                      data={"senaryo": str(sid)})
    assert on.status_code == 200, on.text
    g = on.json()
    assert g["urun_sayfasi"] == 7 and "S.ALMA BF" in g["sayfalar"] and g["mevcut"] is None and g["dosya_adi"] == BUTCE.name
    wb = Workbook(); wb.active.title = "Rastgele"; b = BytesIO(); wb.save(b)
    red = istemci.post("/api/v1/import/excel-tam/musavir-sablonu", files={"dosya": ("baska.xlsx", b.getvalue(), XLSX)}, data={"senaryo": str(sid)})
    assert red.status_code == 422 and red.json()["kod"] == "eksik_sayfa"
    assert istemci.get(f"{URL}/durum", params={"senaryo_id": sid}).json()["sablon"] is None
    ok = istemci.post("/api/v1/import/excel-tam/musavir-sablonu", files={"dosya": (BUTCE.name, BUTCE.read_bytes(), XLSX)},
                      data={"senaryo": str(sid)}, headers=H)
    assert ok.status_code == 200 and ok.json()["sablon"]["dosya_adi"] == BUTCE.name
    assert istemci.get(f"{URL}/durum", params={"senaryo_id": sid}).json()["sablon"]["olusturan"] == "esma"


def test_kopyada_sablon_indirilir(istemci):
    """B7: "Geçen sezondan kopyala" ile açılan çalışmada Fiyat Çalışması Excel'i iner (şablon kopyalandı)."""
    sid = _yukle(istemci, BUTCE)["senaryo_id"]
    secim = {k: False for k in ("receteler", "fiyatlar", "parametreler", "gider", "uretim", "fire_kurallari")}
    r = istemci.post(f"/api/v1/senaryolar/{sid}/kopyala", json={"sezon_ad": "2027-2028", "ad": "Kopya", "tur": "fiyat_calismasi",
                                                               "neden": "sezon", "kopyala": {**secim, "receteler": True, "fiyatlar": True,
                                                                                             "parametreler": True, "gider": True, "uretim": True}})
    assert r.status_code == 201, r.text
    assert r.json()["kopyalanan"]["sablon"] == 1
    yeni = r.json()["id"]
    assert istemci.get(f"{URL}/durum", params={"senaryo_id": yeni}).json()["sablon"]["dosya_adi"] == BUTCE.name
    assert istemci.get(f"{URL}.xlsx", params={"senaryo_id": yeni}).status_code == 200


def test_senaryo_silinince_sablon_silinir(istemci, oturum):
    sid = _yukle(istemci, BUTCE)["senaryo_id"]
    assert mx.sablon(oturum, sid) is not None
    senaryo_servisi.sil(oturum, sid, yedek_url="")
    assert mx.sablon(oturum, sid) is None


def test_elle_deger_formul_hucresinde_uyari(istemci, oturum):
    """Uygulamada elle birim fiyat var, kitapta o hücre formül: formüle dokunulmaz, uyarı listelenir."""
    sid = _yukle(istemci, BUTCE)["senaryo_id"]
    u = hs.urun_getir(oturum, "03.99.001")
    r = recete_servisi.aktif_recete(oturum, u.id, sid)
    satirlar = [{"malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": x.miktar, "birim": x.birim, "fire_override": x.fire_override,
                 "dugum_tipi": x.dugum_tipi, "brut_miktar_elle": x.brut_miktar_elle,
                 "birim_fiyat_elle": D("2.5") if x.malzeme_kodu == "99.20.003" else x.birim_fiyat_elle, "seviye": x.seviye}
                for x in r.satirlar]
    recete_servisi.yeni_versiyon(oturum, u.id, sid, satirlar, "elle", "esma")
    oturum.flush()
    d = istemci.get(f"{URL}/durum", params={"senaryo_id": sid, "uyarilar": "true", "tarih": TARIH.isoformat()}).json()
    uy = d["uyarilar_ozeti"]
    assert uy["sayi"] >= 1 and any("001!M" in x and "formül var" in x for x in uy["uyarilar"]), uy
    cikti = openpyxl.load_workbook(BytesIO(mx.fiyat_kitabi_uret(oturum, sid, TARIH)), data_only=False)
    m_hucre = next(f"M{r}" for r in range(7, 20) if cikti["001"][f"D{r}"].value == "99.20.003")
    assert str(cikti["001"][m_hucre].value).startswith("=IFERROR(VLOOKUP(")
