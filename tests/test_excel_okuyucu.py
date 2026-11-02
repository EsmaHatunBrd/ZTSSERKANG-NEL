from decimal import Decimal
import pytest
from fiyat_motoru.excel_okuyucu import excel_ac, malzemeleri_oku, havuzlari_oku, urun_sayfalarini_listele, urun_oku
from fiyat_motoru.para import yakin


@pytest.fixture(scope="module")
def wb(excel_yolu):
    return excel_ac(excel_yolu)


def test_malzemeler(wb):
    m = malzemeleri_oku(wb[1])
    assert len(m) >= 800
    kav = m["20.10.051.000.0000"]
    assert kav.fiyat == Decimal("5.9") and kav.para_birimi == "TL" and kav.zs == "S"
    assert m["10.002.005.00112"].zs == "Z"


def test_havuzlar(wb):
    h = havuzlari_oku(wb[1])
    assert yakin(h.dolum_iscilik_toplam, Decimal("86037707.86667047"))
    assert h.mal_kabul_paylari["Turşu/Turşu"] == (Decimal("0.1"), Decimal(3500000))
    assert len(h.ambalajlar) == 22 and h.ambalajlar[4].hacim == Decimal(370)


def test_sayfa_listesi(wb):
    s = urun_sayfalarini_listele(wb[1])
    assert "001" in s and "053" in s and "001 (2)" in s and "Teklif Kapak" not in s


def test_urun_001(wb):
    girdi, p, beklenen = urun_oku(wb[0]["001"], wb[1]["001"])
    assert girdi.kod == "03.004.001.002.00010"
    assert len(girdi.recete) >= 20
    assert girdi.uretim.vardiya_uretim_adedi == Decimal(65000) and girdi.uretim.hat == "Niko"
    assert girdi.uretim.taze_tursu_sinifi == "Turşu/Turşu" and girdi.uretim.ambalaj_hacmi == Decimal(370)
    assert yakin(girdi.uretim.mal_kabul_miktar_kg, Decimal("0.19013459"))
    assert p.kurlar["USD"] == Decimal(50) and p.enflasyon == Decimal("0.25")
    assert p.faiz_oranlari["TL"] == Decimal("0.4") and p.stok_sureleri_ay["TL"] == Decimal(6)
    assert p.teklif_kar_oranlari == (Decimal("0.2"), Decimal("0.17"), Decimal("0.14"))
    assert yakin(beklenen["P130"], Decimal("38.13078935965275"))
    assert yakin(beklenen["P147"], Decimal("0.7462195477684043"))


def test_urun_053_kaymis_satirlar(wb):
    girdi, p, beklenen = urun_oku(wb[0]["053"], wb[1]["053"])
    assert "P130" in beklenen and beklenen["P130"] is not None


def test_urun_056_kodsuz(wb):
    girdi, _, _ = urun_oku(wb[0]["056"], wb[1]["056"])
    assert girdi.kod == "" and girdi.ad != ""


def test_urun_kendi_recetesinde_ara_mamul_isaretlenir(wb):
    girdi, _, _ = urun_oku(wb[0]["001"], wb[1]["001"])
    ara = [r for r in girdi.recete if r.dugum_tipi == "ara_mamul"]
    assert girdi.recete[0].malzeme_kodu == girdi.kod and girdi.recete[0].dugum_tipi == "ara_mamul"
    assert all(r.malzeme_kodu == girdi.kod for r in ara)


def _satirlar_by_row(wb, sayfa):
    """{excel satır no: ReceteSatiri} — okuyucunun D sütunu dolu satırlarıyla aynı süzme."""
    from fiyat_motoru.excel_okuyucu import _etiket_satiri
    girdi, _, _ = urun_oku(wb[0][sayfa], wb[1][sayfa], malzemeleri_oku(wb[1]))
    r100 = _etiket_satiri(wb[1][sayfa], "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    rows = [r for r in range(6, r100) if wb[1][sayfa][f"D{r}"].value]
    assert len(rows) == len(girdi.recete)
    return dict(zip(rows, girdi.recete))


def test_009_k8_elle_brut_miktar(wb):
    s = _satirlar_by_row(wb, "009")[8]
    assert s.brut_miktar_elle == Decimal("0.08333333") and s.birim_fiyat_elle is None


def test_k_sabit_ama_sayisal_esit_elle_degil(wb):
    """K sabit yazılmış ama I/(1-J) ile aynı değer (J boş): elle sayılmaz."""
    ws = wb[1]["001"]
    assert not isinstance(wb[0]["001"]["K6"].value, str) and ws["K6"].value == ws["I6"].value and not ws["J6"].value
    assert _satirlar_by_row(wb, "001")[6].brut_miktar_elle is None


def test_k_elle_sayisal_kural_birim():
    from fiyat_motoru.excel_okuyucu import k_sayisal_elle_mi, m_sayisal_elle_mi
    from fiyat_motoru.modeller import Malzeme
    assert not k_sayisal_elle_mi(1, 1, 0) and not k_sayisal_elle_mi(None, 0, None)
    assert not k_sayisal_elle_mi(Decimal("1.0204081632653061"), 1, Decimal("0.02"))      # =I/0.98, J=0.02
    assert k_sayisal_elle_mi(Decimal("1.0204081632653061"), 1, None)                    # =I/0.98, J boş
    assert k_sayisal_elle_mi(Decimal("0.5"), 1, 0)
    mz = Malzeme(kod="X", ad="", tip=None, birim=None, para_birimi="TL", fiyat=Decimal("5.9"), zs="S")
    assert not m_sayisal_elle_mi(Decimal("5.9"), mz) and m_sayisal_elle_mi(260, mz)
    assert not m_sayisal_elle_mi(0, None) and m_sayisal_elle_mi(10, None)


def test_011_k7_kalip_disi_formul_elle_sayilir(wb):
    assert wb[0]["011"]["K7"].value.replace(" ", "") == "=+I7/0.98"
    s = _satirlar_by_row(wb, "011")[7]
    assert s.brut_miktar_elle is not None and s.brut_miktar_elle > s.miktar


def test_001_k8_formul_elle_degil(wb):
    s = _satirlar_by_row(wb, "001")[8]
    assert s.brut_miktar_elle is None and s.birim_fiyat_elle is None


def test_012_m10_elle_birim_fiyat(wb):
    s = _satirlar_by_row(wb, "012")[10]
    assert s.birim_fiyat_elle == Decimal(260) and s.brut_miktar_elle is None


def test_k_elle_mi_kalip_toleransi():
    from fiyat_motoru.excel_okuyucu import k_elle_mi, m_elle_mi
    assert not k_elle_mi("=I8/(1-J8)", 8) and not k_elle_mi("=+I8 / (1-J8)", 8)
    assert k_elle_mi("=I8/0.98", 8) and k_elle_mi(1, 8) and k_elle_mi(None, 8) and k_elle_mi("=I9/(1-J9)", 8)
    assert m_elle_mi(260) and not m_elle_mi("=IFERROR(VLOOKUP(D7,'S.ALMA BF'!A:H,6,FALSE),0)")


def test_zar_rub_kurlari_ve_ek_parametreler(wb):
    from fiyat_motoru.excel_okuyucu import ek_parametreleri_oku
    _, p, _ = urun_oku(wb[0]["001"], wb[1]["001"])
    assert list(p.kurlar) == ["USD", "EUR", "GBP", "CHF", "RUB", "ZAR"] and p.kurlar["ZAR"] > 0 and p.kurlar["RUB"] > 0
    ek = ek_parametreleri_oku(wb[1]["001"])
    assert ek["maliyet_sapma"] == Decimal(0) and ek["satis_fiyati_notu"] and "SATIŞ FİYATI" in ek["satis_fiyati_notu"]
