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


_f_istisna('001 (2)', ('P103', 'P107', 'P104', 'P105', 'P106', 'P108', 'P109', 'P110', 'P111', 'P112', 'P113', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'elle yazilmis sabit 0 hucreler: P104,P105,P106,P108,P109,P110,P111,P112,P113 (formul yok)')
_f_istisna('012', ('P103', 'P107', 'P105', 'P108', 'P111', 'P112', 'P113', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'elle 0 yazilmis I104,I105,I108,I111,I112,I113')
_f_istisna('013', ('P103', 'P107', 'P105', 'P108', 'P111', 'P112', 'P113', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'elle 0 yazilmis I104,I105,I108,I111,I112,I113')
_f_istisna('022', ('P103', 'P107', 'P105', 'P113', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'formul yerine elle yazilmis P105=20 ve P113=10')
_f_istisna('040', ('P103', 'P107', 'P104', 'P106', 'P108', 'P109', 'P110', 'P111', 'P112', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'elle yazilmis I104=1 ve M104,M105,M106,M108,M109,M110,M111,M112=0')
_f_istisna('041', ('P107', 'P112', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'elle 0 yazilmis I112')
_f_istisna('042', ('P103', 'P107', 'P105', 'P108', 'P109', 'P111', 'P112', 'P113', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'elle yazilmis I105,I108,I109,I111,I112=0 ve I113=1')
_f_istisna('048', ('P107', 'P113', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R107'), 'elle yazilmis M104,M108-M112=0; I105,I108-I112=0; K105,K106=0; I113=1')
_f_istisna("053", ("P131",), "P141 formulu ($P$117+$P$120)/F160: satir kaymasinda mutlak referanslar kaydirilmamis")
_f_istisna("053", ("P138",), "P148=P141*1.2: P141 (mutlak referans kaymasi) zincirinin devami")
_f_istisna("053", ("P145", "P146", "P147"), "P155,P156,P157 formulleri $P$126 mutlak referansi kullaniyor (satir kaymasi)")
_f_istisna('055', ('P103', 'P107', 'P105', 'P108', 'P110', 'P111', 'P114', 'P116', 'P122', 'P124', 'P125', 'P130', 'P131', 'P132', 'P133', 'P137', 'P138', 'P143', 'P145', 'P146', 'P147', 'R100', 'R103', 'R107'), 'formul yerine elle 0 yazilmis P105,P108,P110,P111,P118,P119')


# R/S yüzde sütunları: payda (P116/P122/P137) sapan sayfalarda aynı nedenin türevi olarak sapar.
for _sayfa in ('001 (2)', '012', '013', '022', '040', '041', '042', '048', '055'):
    _alanlar = {'055': ('S100', 'S103', 'S107'), '048': ('R118', 'R119', 'S100', 'S107', 'S118', 'S119')}.get(
        _sayfa, ('R118', 'R119', 'S100', 'S103', 'S107', 'S118', 'S119'))
    _f_istisna(_sayfa, _alanlar, "R/S yuzdeleri payda sapmasinin turevi: " + FORMUL_ISTISNALARI[(_sayfa, 'P116')])


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
