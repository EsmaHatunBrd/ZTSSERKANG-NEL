"""Formul zinciri orakeli: reçete satirlari Excel'in kendi K/M/N/O hucre degerleriyle beslenir; motorun
P100'den P147'ye hesap zinciri Excel'le birebir ayni olmali. Kalan farklar FORMUL_ISTISNALARI'nda hucre adresiyle aciklanir."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiyat_motoru.excel_okuyucu import (excel_ac, havuzlari_oku, malzemeleri_oku, urun_oku_excel_hucreleri,
                                        urun_sayfalarini_listele)
from fiyat_motoru.gider_dagitim import oranlari_hesapla
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.para import TOLERANS
from fiyat_motoru.parite import urun_farklari

FORMUL_ISTISNALARI: dict[tuple[str, str], str] = {}


def _f_istisna(sayfa: str, alanlar: tuple[str, ...], neden: str) -> None:
    for alan in alanlar:
        assert (sayfa, alan) not in FORMUL_ISTISNALARI, f"yinelenen istisna: {(sayfa, alan)}"
        FORMUL_ISTISNALARI[(sayfa, alan)] = neden


# Gider satırlarında formül yerine elle yazılmış hücreler (I/K/M/P) okuyucu tarafından UrunGirdisi.gider_elle olarak taşınır;
# fark üretmez. Kalan sapmalar Excel'in kendi formül hatalarıdır.
_f_istisna("053", ("P131",), "P141 formulu ($P$117+$P$120)/F160: satir kaymasinda mutlak referanslar kaydirilmamis")
_f_istisna("053", ("P138",), "P148=P141*1.2: P141 (mutlak referans kaymasi) zincirinin devami")
_f_istisna("053", ("P145", "P146", "P147"), "P155,P156,P157 formulleri $P$126 mutlak referansi kullaniyor (satir kaymasi)")


def _formul_farklari(yol):
    wb_f, wb_v = excel_ac(yol)
    malzemeler = malzemeleri_oku(wb_v)
    oranlar = oranlari_hesapla(havuzlari_oku(wb_v))
    farklar = []
    for ad in urun_sayfalarini_listele(wb_v):
        girdi, ozel, p, bek = urun_oku_excel_hucreleri(wb_f[ad], wb_v[ad])
        r = urun_maliyeti(girdi, {**malzemeler, **ozel}, oranlar, p)
        farklar += urun_farklari(ad, r, bek)
    return farklar


@pytest.fixture(scope="module")
def farklar(excel_yolu):
    return _formul_farklari(excel_yolu)


def test_formul_zinciri_paritesi(farklar):
    beklenmeyen = [d for d in farklar if (d["sayfa"], d["alan"]) not in FORMUL_ISTISNALARI]
    assert beklenmeyen == [], "\n".join(f"{d['sayfa']} {d['alan']}: excel={d['excel']} motor={d['motor']}" for d in beklenmeyen[:30])


def test_formul_istisnalari_hala_gecerli(farklar):
    mevcut = {(d["sayfa"], d["alan"]) for d in farklar}
    olu = [k for k in FORMUL_ISTISNALARI if k not in mevcut]
    assert olu == [], f"artik fark uretmeyen istisnalar: {olu}"


def test_formul_istisnalari_gerekceli():
    bos = [k for k, v in FORMUL_ISTISNALARI.items() if not v.strip()]
    assert bos == []
