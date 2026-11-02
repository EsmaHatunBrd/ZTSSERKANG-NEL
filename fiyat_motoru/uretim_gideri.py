"""F5/F6/F7: İşçilik, genel üretim ve pazarlama/yönetim giderleri. Excel 001!P103:P119."""
from decimal import Decimal
from .fire import brut_miktar
from .gider_dagitim import anahtar
from .modeller import GiderOranlari, MaliyetSatiri, Parametreler, UretimBilgisi
from .para import SIFIR

SANIYE_SAAT = Decimal(3600)
VARDIYA_UYARISI = "vardiya üretim adedi 0, saniye bazlı giderler 0 alındı"


def adet_basina_saniye(u: UretimBilgisi, p: Parametreler) -> Decimal:
    """Excel: 27000/E138. 27000 = 7,5 saat * 3600."""
    if u.vardiya_uretim_adedi == SIFIR:
        return SIFIR
    return p.vardiya_saati * SANIYE_SAAT / u.vardiya_uretim_adedi


def _satir(kod, kalem, grup, miktar, brut, fiyat) -> MaliyetSatiri:
    return MaliyetSatiri(kalem=kalem, grup=grup, miktar=miktar, brut_miktar=brut, birim_fiyat=fiyat, tutar=brut * fiyat, kod=kod)


def _oran(tablo: dict, ad: str, ne: str, uyarilar: list[str]) -> Decimal:
    k = anahtar(ad)
    if k not in tablo:
        uyarilar.append(f"{ne} bulunamadı: '{ad}', gider 0 alındı")
        return SIFIR
    return tablo[k]


def direkt_iscilik(u: UretimBilgisi, o: GiderOranlari, p: Parametreler) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    sn = adet_basina_saniye(u, p)
    if u.vardiya_uretim_adedi == SIFIR:
        uyarilar.append(VARDIYA_UYARISI)
    mk_brut = brut_miktar(u.mal_kabul_miktar_kg, u.mal_kabul_fire)
    mk_oran = _oran(o.mal_kabul_iscilik_kg, u.taze_tursu_sinifi, "taze/turşu sınıfı", uyarilar)
    etiket_sn = SIFIR if u.etiketleme_adedi == SIFIR else p.vardiya_saati * SANIYE_SAAT / u.etiketleme_adedi
    return [
        _satir("mal_kabul_iscilik", "Mal Kabul ve Fermantasyon Giderleri", "direkt_iscilik", u.mal_kabul_miktar_kg, mk_brut, mk_oran),
        _satir("dolum_iscilik", "Dolum Doğrudan İşçilik Giderleri", "direkt_iscilik", sn, sn * u.dolum_personel, o.dolum_iscilik_sn),
        _satir("etiket_iscilik", "Etiketleme İşçilik Giderleri", "direkt_iscilik", etiket_sn, etiket_sn * u.etiket_personel, o.etiket_iscilik_sn),
    ], uyarilar


def genel_uretim(u: UretimBilgisi, o: GiderOranlari, p: Parametreler) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    sn = adet_basina_saniye(u, p)
    if u.vardiya_uretim_adedi == SIFIR:
        uyarilar.append(VARDIYA_UYARISI)
    mk = u.mal_kabul_miktar_kg          # Excel K109 = I109, fire yok
    return [
        _satir("endirekt_iscilik", "Endirekt İşçilik Giderleri", "gug", sn, sn, o.endirekt_iscilik_sn),
        _satir("mal_kabul_gug", "Mal Kabul ve Fermantasyon Genel Üretim Giderleri", "gug", mk, mk,
               _oran(o.mal_kabul_gug_kg, u.taze_tursu_sinifi, "taze/turşu sınıfı", uyarilar)),
        _satir("elektrik", "Elektrik Giderleri", "gug", sn, sn, _oran(o.elektrik_sn, u.hat, "üretim hattı", uyarilar)),
        _satir("dogalgaz", "Doğalgaz Giderleri", "gug", sn, sn, _oran(o.dogalgaz_sn, u.hat, "üretim hattı", uyarilar)),
        _satir("amortisman", "Amortisman Giderleri", "gug", sn, sn, _oran(o.amortisman_sn, u.hat, "üretim hattı", uyarilar)),
        _satir("diger_gug", "Diğer Genel Üretim Giderleri", "gug", sn, sn, o.diger_gug_sn),
    ], uyarilar


def diger_giderler(u: UretimBilgisi, o: GiderOranlari) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    bir = Decimal(1)
    if not u.pazarlama_yonetim_uygula:
        paz = yon = SIFIR
    else:
        paz = o.pazarlama_adet.get(u.ambalaj_hacmi)
        yon = o.yonetim_adet.get(u.ambalaj_hacmi)
        if paz is None or yon is None:
            uyarilar.append(f"ambalaj hacmi {u.ambalaj_hacmi} dağıtım tablosunda yok, pazarlama/yönetim 0 alındı")
            paz, yon = SIFIR, SIFIR
    return [
        _satir("pazarlama", "Pazarlama Satış Giderleri", "diger", bir, bir, paz),
        _satir("yonetim", "Genel Yönetim Giderleri", "diger", bir, bir, yon),
    ], uyarilar
