"""F5/F6/F7: İşçilik, genel üretim ve pazarlama/yönetim giderleri. Excel 001!P103:P119."""
from decimal import Decimal
from .fire import brut_miktar
from .gider_dagitim import anahtar
from .modeller import GiderElle, GiderOranlari, MaliyetSatiri, Parametreler, UretimBilgisi
from .para import SIFIR

SANIYE_SAAT = Decimal(3600)
VARDIYA_UYARISI = "vardiya üretim adedi 0, saniye bazlı giderler 0 alındı"


def adet_basina_saniye(u: UretimBilgisi, p: Parametreler) -> Decimal:
    """Excel: 27000/E138. 27000 = 7,5 saat * 3600."""
    if u.vardiya_uretim_adedi == SIFIR:
        return SIFIR
    return p.vardiya_saati * SANIYE_SAAT / u.vardiya_uretim_adedi


def _satir(kod, kalem, grup, miktar, brut, fiyat, elle: dict[str, GiderElle] | None = None) -> MaliyetSatiri:
    """brut: miktardan brüt miktarı veren fonksiyon (Excel K formülü). Elle yazılmış hücre formülün yerine geçer ve
    Excel'deki gibi sonraki hücrelere akar: I -> K -> P, M -> P."""
    e = (elle or {}).get(kod) or GiderElle()
    m = e.miktar if e.miktar is not None else miktar
    k = e.brut_miktar if e.brut_miktar is not None else brut(m)
    f = e.birim_fiyat if e.birim_fiyat is not None else fiyat
    t = e.tutar if e.tutar is not None else k * f
    return MaliyetSatiri(kalem=kalem, grup=grup, miktar=m, brut_miktar=k, birim_fiyat=f, tutar=t, kod=kod, elle_alanlar=e.dolu_alanlar())


def _oran(tablo: dict, ad: str, ne: str, uyarilar: list[str]) -> Decimal:
    k = anahtar(ad)
    if k not in tablo:
        uyarilar.append(f"{ne} bulunamadı: '{ad}', gider 0 alındı")
        return SIFIR
    return tablo[k]


def direkt_iscilik(u: UretimBilgisi, o: GiderOranlari, p: Parametreler,
                   elle: dict[str, GiderElle] | None = None) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    sn = adet_basina_saniye(u, p)
    if u.vardiya_uretim_adedi == SIFIR:
        uyarilar.append(VARDIYA_UYARISI)
    mk_oran = _oran(o.mal_kabul_iscilik_kg, u.taze_tursu_sinifi, "taze/turşu sınıfı", uyarilar)
    etiket_sn = SIFIR if u.etiketleme_adedi == SIFIR else p.vardiya_saati * SANIYE_SAAT / u.etiketleme_adedi
    return [
        _satir("mal_kabul_iscilik", "Mal Kabul ve Fermantasyon Giderleri", "direkt_iscilik", u.mal_kabul_miktar_kg,
               lambda m: brut_miktar(m, u.mal_kabul_fire), mk_oran, elle),
        _satir("dolum_iscilik", "Dolum Doğrudan İşçilik Giderleri", "direkt_iscilik", sn, lambda m: m * u.dolum_personel,
               o.dolum_iscilik_sn, elle),
        _satir("etiket_iscilik", "Etiketleme İşçilik Giderleri", "direkt_iscilik", etiket_sn, lambda m: m * u.etiket_personel,
               o.etiket_iscilik_sn, elle),
    ], uyarilar


def _ayni(m: Decimal) -> Decimal:
    """Excel K = I (fire yok)."""
    return m


def genel_uretim(u: UretimBilgisi, o: GiderOranlari, p: Parametreler,
                 elle: dict[str, GiderElle] | None = None) -> tuple[list[MaliyetSatiri], list[str]]:
    uyarilar: list[str] = []
    sn = adet_basina_saniye(u, p)
    if u.vardiya_uretim_adedi == SIFIR:
        uyarilar.append(VARDIYA_UYARISI)
    mk = u.mal_kabul_miktar_kg          # Excel I109 = I104, K109 = I109
    return [
        _satir("endirekt_iscilik", "Endirekt İşçilik Giderleri", "gug", sn, _ayni, o.endirekt_iscilik_sn, elle),
        _satir("mal_kabul_gug", "Mal Kabul ve Fermantasyon Genel Üretim Giderleri", "gug", mk, _ayni,
               _oran(o.mal_kabul_gug_kg, u.taze_tursu_sinifi, "taze/turşu sınıfı", uyarilar), elle),
        _satir("elektrik", "Elektrik Giderleri", "gug", sn, _ayni, _oran(o.elektrik_sn, u.hat, "üretim hattı", uyarilar), elle),
        _satir("dogalgaz", "Doğalgaz Giderleri", "gug", sn, _ayni, _oran(o.dogalgaz_sn, u.hat, "üretim hattı", uyarilar), elle),
        _satir("amortisman", "Amortisman Giderleri", "gug", sn, _ayni, _oran(o.amortisman_sn, u.hat, "üretim hattı", uyarilar), elle),
        _satir("diger_gug", "Diğer Genel Üretim Giderleri", "gug", sn, _ayni, o.diger_gug_sn, elle),
    ], uyarilar


def diger_giderler(u: UretimBilgisi, o: GiderOranlari, elle: dict[str, GiderElle] | None = None) -> tuple[list[MaliyetSatiri], list[str]]:
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
        _satir("pazarlama", "Pazarlama Satış Giderleri", "diger", bir, lambda m: bir, paz, elle),   # Excel K118/K119 sabit 1
        _satir("yonetim", "Genel Yönetim Giderleri", "diger", bir, lambda m: bir, yon, elle),
    ], uyarilar
