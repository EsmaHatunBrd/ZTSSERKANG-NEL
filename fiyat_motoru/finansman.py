"""F9/F10: Finansman gideri (basit faiz) ve döviz bazında maliyet. Excel 001!P124:P134."""
from decimal import Decimal
from .modeller import Parametreler

ON_IKI = Decimal(12)


def finansman_gideri(maliyet: Decimal, faiz_orani: Decimal, stok_ay: Decimal) -> Decimal:
    """Yıllık faiz * ortalama stok süresi (ay) * birim maliyet."""
    return maliyet * (faiz_orani / ON_IKI * stok_ay)


def tum_finansman(giydirilmis: Decimal, p: Parametreler) -> dict[str, Decimal]:
    return {pb: finansman_gideri(giydirilmis, p.faiz_oranlari[pb], p.stok_sureleri_ay[pb]) for pb in p.faiz_oranlari if pb in p.stok_sureleri_ay}


def doviz_maliyet(giydirilmis: Decimal, finansman: dict[str, Decimal], p: Parametreler) -> dict[str, Decimal]:
    return {pb: (giydirilmis + finansman[pb]) / kur for pb, kur in p.kurlar.items() if pb in finansman and kur > 0}
