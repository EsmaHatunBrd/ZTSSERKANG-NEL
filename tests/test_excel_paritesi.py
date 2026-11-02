# tests/test_excel_paritesi.py
"""Altın referans: motor, Excel'in 69 ürün sayfasında kuruşu kuruşuna aynı sonucu vermeli.
Bilinen Excel sapmaları (spec bölüm 3) BILINEN_ISTISNALAR'da açıklamasıyla listelenir."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiyat_motoru.parite import karsilastir

MALZEME_ZINCIRI = ("P100", "P116", "P122", "P124", "P125", "P130", "P131", "P132", "P133", "P137", "P138", "P143",
                   "P145", "P146", "P147", "R100", "R103", "R107")   # malzeme toplamından sonraki hesap zinciri
GIDER_KALEMLERI = ("P103", "P104", "P105", "P106", "P107", "P108", "P109", "P110", "P111", "P112", "P113", "P114")
TAM_ZINCIR = GIDER_KALEMLERI + MALZEME_ZINCIRI
# R/S yüzde sütunları: payda (P122/P130/P137) sapması olan sayfalarda aynı nedenin türevi olarak sapar.
ORAN_SUTUNLARI = ("R118", "R119", "S100", "S103", "S107", "S118", "S119")

# Reçete satırlarında elle müdahale: K (brüt miktar) ve M (birim fiyat) artık veri olarak taşınır (brut_miktar_elle /
# birim_fiyat_elle), bu yüzden fark üretmez. Kalan tek reçete sapması N (Z/S) sütunundaki elle yazılmış değerlerdir.
RECETE_SAPMASI: dict[str, str] = {
    '040': 'N sabit: N10',
    '043': 'N sabit: N14',
    '044': 'N sabit: N14',
}

# Maliyet satırlarındaki elle yazılmış hücreler (formül yerine sabit; hücre adresleriyle).
GIDER_SAPMASI: dict[str, str] = {
    '001 (2)': 'formül yerine elle 0: P104,P105,P106,P108,P109,P110,P111,P112,P113',
    '012': 'elle 0: I104,I105,I108,I111,I112,I113',
    '013': 'elle 0: I104,I105,I108,I111,I112,I113',
    '022': 'formül yerine elle yazılmış: P105=20, P113=10',
    '040': 'elle yazılmış: I104=1; M104,M105,M106,M108,M109,M110,M111,M112=0',
    '041': 'elle 0: I112',
    '042': 'elle yazılmış: I105,I108,I109,I111,I112=0; I113=1',
    '048': 'elle yazılmış: M104,M108-M112=0; I105,I108-I112=0; K105,K106=0; I113=1',
    '055': 'formül yerine elle 0: P105,P108,P110,P111,P118,P119',
}

BILINEN_ISTISNALAR: dict[tuple[str, str], str] = {}


def _recete(sayfa: str) -> str:
    return "reçete satırı N (Z/S) elle müdahalesi, " + RECETE_SAPMASI[sayfa]


def _istisna(sayfa: str, alanlar: tuple[str, ...], neden: str, haric: tuple[str, ...] = (), ek: tuple[str, ...] = ()) -> None:
    for alan in tuple(a for a in alanlar if a not in haric) + ek:
        assert (sayfa, alan) not in BILINEN_ISTISNALAR, f"yinelenen istisna: {(sayfa, alan)}"
        BILINEN_ISTISNALAR[(sayfa, alan)] = neden


def _oran_istisna(sayfa: str, haric: tuple[str, ...] = ()) -> None:
    """R/S yüzde sapması: sayfanın P zincirindeki sapmanın (reçete ve/veya gider elle müdahalesi) türevidir."""
    nedenler = []
    if sayfa in RECETE_SAPMASI:
        nedenler.append(_recete(sayfa))
    if sayfa in GIDER_SAPMASI:
        nedenler.append(GIDER_SAPMASI[sayfa])
    _istisna(sayfa, ORAN_SUTUNLARI, "R/S yüzdeleri P116/P122/P137 sapmasının türevi: " + "; ".join(nedenler), haric=haric)


_istisna('001 (2)', GIDER_KALEMLERI, GIDER_SAPMASI['001 (2)'])
_istisna('001 (2)', MALZEME_ZINCIRI, GIDER_SAPMASI['001 (2)'], haric=('P100',))
_istisna('012', GIDER_KALEMLERI, GIDER_SAPMASI['012'], haric=('P104', 'P106', 'P109', 'P110'))
_istisna('012', MALZEME_ZINCIRI, GIDER_SAPMASI['012'], haric=('P100',))
_istisna('013', GIDER_KALEMLERI, GIDER_SAPMASI['013'], haric=('P104', 'P106', 'P109', 'P110'))
_istisna('013', MALZEME_ZINCIRI, GIDER_SAPMASI['013'], haric=('P100',))
_istisna('022', MALZEME_ZINCIRI, GIDER_SAPMASI['022'], haric=('P100',), ek=('P103', 'P105', 'P107', 'P113', 'P114'))
_istisna('040', GIDER_KALEMLERI, GIDER_SAPMASI['040'], haric=('P105', 'P113'))
_istisna('040', ('P100',), _recete('040'))
_istisna('040', MALZEME_ZINCIRI, _recete('040') + "; " + GIDER_SAPMASI['040'], haric=('P100',))
_istisna('041', ('P107', 'P112', 'P114'), GIDER_SAPMASI['041'])
_istisna('041', MALZEME_ZINCIRI, GIDER_SAPMASI['041'], haric=('P100',))
_istisna('042', TAM_ZINCIR, GIDER_SAPMASI['042'], haric=('P104', 'P106', 'P110', 'P100'))
_istisna('043', MALZEME_ZINCIRI, _recete('043'))
_istisna('044', MALZEME_ZINCIRI, _recete('044'))
_istisna('048', ('P107', 'P113', 'P114'), GIDER_SAPMASI['048'])
_istisna('048', MALZEME_ZINCIRI, GIDER_SAPMASI['048'], haric=('P100', 'R103'))
_istisna('053', ('P131',), 'P141 formülü ($P$117+$P$120)/F160 kaydırılmamış mutlak referans içeriyor')
_istisna('053', ('P138',), 'P148=P141*1.2, P141 sorununun devamı')
_istisna('053', ('P145',), 'P155 formülü $P$126 mutlak referansı kullanıyor')
_istisna('053', ('P146',), 'P156 formülü $P$126 mutlak referansı kullanıyor')
_istisna('053', ('P147',), 'P157 formülü $P$126 mutlak referansı kullanıyor')
_istisna('055', TAM_ZINCIR, GIDER_SAPMASI['055'], haric=('P104', 'P106', 'P109', 'P112', 'P113', 'P100'))

for _s in ('001 (2)', '012', '013', '022', '040', '041', '042', '043', '044'):
    _oran_istisna(_s)
_oran_istisna('048', haric=('S103',))
_oran_istisna('055', haric=('R118', 'R119', 'S118', 'S119'))



@pytest.fixture(scope="module")
def farklar(excel_yolu):
    f, _ = karsilastir(excel_yolu)
    return f


def test_gider_dagitim_paritesi(farklar):
    assert [d for d in farklar if d["sayfa"] == "Gider Dağıtım"] == []


def test_urun_sayfalari_paritesi(farklar):
    beklenmeyen = [d for d in farklar if d["sayfa"] != "Gider Dağıtım" and (d["sayfa"], d["alan"]) not in BILINEN_ISTISNALAR]
    assert beklenmeyen == [], "\n".join(f"{d['sayfa']} {d['alan']}: excel={d['excel']} motor={d['motor']}" for d in beklenmeyen[:30])


def test_istisnalar_hala_gecerli(farklar):
    """Bir istisna artık fark üretmiyorsa listeden çıkarılmalı (ölü istisna birikmesin)."""
    mevcut = {(d["sayfa"], d["alan"]) for d in farklar}
    olu = [k for k in BILINEN_ISTISNALAR if k not in mevcut]
    assert olu == [], f"artık fark üretmeyen istisnalar: {olu}"
