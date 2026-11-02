"""Faz 4b B2: Excel `Üretim Adetleri` sayfası okuyucusu (başlık satır 2, veri satır 4'ten)."""
from decimal import Decimal
from collections import Counter
from fiyat_motoru import excel_okuyucu as eo



def _satirlar(excel_yolu):
    _, wb_v = eo.excel_ac(excel_yolu)
    return eo.uretim_adetlerini_oku(wb_v)


def test_satir_sayisi_ve_alanlar(excel_yolu):
    s = _satirlar(excel_yolu)
    assert 65 <= len(s) <= 80
    assert set(s[0]) == {"urun_kodu", "urun_ad", "net_kapasite", "net_sure", "toplam_kapasite", "toplam_sure", "hedef_uretim", "ortalama_isci"}
    assert all(isinstance(x["hedef_uretim"], Decimal) and x["urun_kodu"] for x in s)


def test_ilk_satir_sayfadaki_degerlerle_ayni(excel_yolu):   # sayfa satır 4, doğrudan hücrelerden
    import openpyxl
    ham = next(openpyxl.load_workbook(excel_yolu, data_only=True, read_only=True)["Üretim Adetleri"].iter_rows(min_row=4, max_col=8, values_only=True))
    k = _satirlar(excel_yolu)[0]
    assert k["urun_kodu"] == str(ham[0]).strip()
    assert (k["net_kapasite"], k["net_sure"], k["toplam_kapasite"], k["toplam_sure"], k["hedef_uretim"], k["ortalama_isci"]) == tuple(Decimal(str(x)) for x in ham[2:8])


def test_tekrar_eden_kod_okuyucuda_korunur(excel_yolu):
    sayac = Counter(x["urun_kodu"] for x in _satirlar(excel_yolu))
    assert any(v == 2 for v in sayac.values())


def test_baslik_dogrulamasi(tmp_path):
    import openpyxl
    import pytest
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Üretim Adetleri"
    ws.append([]); ws.append(["ÜRÜN KODU", "ÜRÜN ADI", "A", "B", "C", "D", "HEDEF VARDİYALIK ÜRETİM", "ORTALAMA İŞÇİ SAYISI"]); ws.append([])
    ws.append(["X1", "Deneme", 1, 1, 1, 1, 5, 2])
    assert eo.uretim_adetlerini_oku(wb)[0]["hedef_uretim"] == Decimal(5)
    ws["G2"] = "BASKA"
    with pytest.raises(ValueError, match="beklenen başlıklarda değil"):
        eo.uretim_adetlerini_oku(wb)


def test_sayi_olmayan_hucreler_sifir(excel_yolu):   # sayfada '-' ve '#DIV/0!' hücreleri var
    s = _satirlar(excel_yolu)
    assert all(isinstance(x[a], Decimal) for x in s for a in ("net_kapasite", "net_sure", "toplam_kapasite", "toplam_sure", "hedef_uretim", "ortalama_isci"))
    assert any(x["net_kapasite"] == 0 and x["net_sure"] == 0 for x in s)
