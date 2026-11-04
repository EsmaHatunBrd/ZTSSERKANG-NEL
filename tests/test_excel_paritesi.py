# tests/test_excel_paritesi.py
"""Altın referans: motor, Excel'in 69 ürün sayfasında kuruşu kuruşuna aynı sonucu vermeli.
Bilinen Excel formül hataları BILINEN_ISTISNALAR'da açıklamasıyla listelenir."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiyat_motoru.parite import karsilastir

# Excel'de formül yerine elle yazılmış hücreler (reçete K/M/N/O, gider I/K/M/P) okuyucu tarafından veri olarak taşınır
# (brut_miktar_elle, birim_fiyat_elle, zs_elle, para_birimi_elle, UrunGirdisi.gider_elle), bu yüzden fark üretmez.
# Kalan sapmalar Excel'in kendi formül hatalarıdır; motor bunları kopyalamaz.
BILINEN_ISTISNALAR: dict[tuple[str, str], str] = {
    ('053', 'P131'): 'P141 formülü ($P$117+$P$120)/F160 kaydırılmamış mutlak referans içeriyor',
    ('053', 'P138'): 'P148=P141*1.2, P141 sorununun devamı',
    ('053', 'P145'): 'P155 formülü $P$126 mutlak referansı kullanıyor',
    ('053', 'P146'): 'P156 formülü $P$126 mutlak referansı kullanıyor',
    ('053', 'P147'): 'P157 formülü $P$126 mutlak referansı kullanıyor',
}


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
