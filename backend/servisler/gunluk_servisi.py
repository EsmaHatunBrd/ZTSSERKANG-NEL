"""Değişiklik Günlüğü: tüm denetim kaynaklarını tek, zamana göre tersten akışta birleştirir.

Kaynaklar: DegisiklikKaydi, ParametreDegeri, MalzemeFiyati, FireKurali, MetinParametre, Recete sürümleri, MaliyetHesabi, Teklif.
Yöntem: her kaynak tek (birkaç) sorguyla çekilir, ad/kod eşlemeleri toplu sorgudur (satır başına sorgu yok),
süzgeç + sıralama + sayfalama bellek içinde yapılır. Birkaç on bin satıra kadar yeterlidir; daha büyük veri için
kaynak başına SQL süzgeci/keyset sayfalama gerekir (bilinen sınır).
Salt okunur: hiçbir şey yazmaz."""
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO
from typing import Any
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import zaman_iso
from .hatalar import BulunamadiHatasi, DogrulamaHatasi, liste_metni

TURLER = ("parametre", "fiyat", "fire", "metin", "recete", "hesap", "teklif", "urun", "hedef", "havuz", "ambalaj", "kapasite", "satis", "diger")

_TABLO_TUR = {"urun": "urun", "uretim_hedefi": "hedef", "gider_havuzu": "havuz", "ambalaj_sinifi": "ambalaj", "uretim_kapasitesi": "kapasite",
              "satis_gecmisi": "satis", "recete": "recete", "teklif": "teklif"}
_TABLO_ETIKET = {"urun": "Ürün kartı", "uretim_hedefi": "Üretim hedefi", "gider_havuzu": "Gider havuzu", "ambalaj_sinifi": "Ambalaj sınıfları",
                 "uretim_kapasitesi": "Üretim kapasitesi", "satis_gecmisi": "Satış geçmişi", "malzeme": "Malzeme kartı", "recete": "Reçete",
                 "senaryo": "Senaryo", "teklif": "Teklif turu", "liste_fiyati": "Liste fiyatı", "smm_donem": "SMM dönemi",
                 "smm_recete": "SMM reçeteleri", "stok_devri": "Stokta kalan", "smm_kalem": "SMM stok kalemi",
                 "smm_mizan": "SMM mizan satırı", "kullanici": "Kullanıcı",
                 "duzenleme_kilidi": "Düzenleme"}   # "Düzenleme" + "kilidi açıldı" = "Düzenleme kilidi açıldı"
_ISLEM_ETIKET = {"guncelle": "güncellendi", "olustur": "oluşturuldu", "ekle": "eklendi", "sil": "silindi", "pasiflestir": "pasifleştirildi",
                 "aile_degistir": "ailesi değişti", "kod_degistir": "kodu değişti", "toplu_yukle": "toplu yüklendi", "etkinlestir": "sürümü etkinleştirildi",
                 "kilitle": "kilitlendi", "kilit_ac": "kilidi açıldı", "kopyala": "kopyalanarak oluşturuldu",
                 "ornek_uret": "örnek verisi üretildi", "ornek_sil": "örnek verisi silindi",
                 "dagitim": "dağıtım havuzları değişti", "alternatif": "reçete alternatifi değişti",
                 "recete_kaynagi": "reçete kaynağı değişti", "satir_ekle": "reçete satırı eklendi",
                 "satir_guncelle": "reçete satırı değişti", "satir_sil": "reçete satırı silindi",
                 "alternatif_kopyala": "reçete alternatifi kopyalandı", "canias_don": "Canias reçetesine döndürüldü",
                 "asama": "aşaması değişti", "asama_elle": "aşama değeri elle girildi", "sure_ekle": "üretim süresi eklendi",
                 "sure_guncelle": "üretim süresi değişti", "sure_sil": "üretim süresi silindi",
                 "veri_yukle": "veri yüklendi", "kalem_guncelle": "stok kalemi düzeltildi", "ayar_guncelle": "finansman / gider tutarı değişti",
                 "sifre_degistir": "kendi şifresini değiştirdi", "sifre_sifirla": "şifresi sıfırlandı"}


@dataclass
class Suzgec:
    senaryo: int | None = None
    bas: date | None = None
    son: date | None = None
    kullanici: str | None = None
    tur: list[str] = field(default_factory=list)
    urun_kodu: str | None = None
    q: str | None = None


def _kisa(v: Any, sinir: int = 160) -> str:
    metin = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return metin if len(metin) <= sinir else metin[: sinir - 1] + "…"


def _tr_bicim(d: Decimal, basamak: int) -> str:
    """Decimal -> '1.234.567,89' (binlik nokta, ondalık virgül)."""
    return f"{d:,.{basamak}f}".replace(",", "\0").replace(".", ",").replace("\0", ".")


def _tutar_tr(v: Any) -> str:
    """Tutar: 2 ondalık ROUND_HALF_UP ('1755.1755' -> '1.755,18'). Sayı değilse olduğu gibi."""
    try:
        return _tr_bicim(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), 2)
    except (InvalidOperation, ValueError, TypeError):
        return str(v)


def _carpan_tr(v: Any) -> str:
    """Çarpan: en az 2 ondalık, fazlası varsa korunur ('1.3' -> '1,30', '1.355' -> '1,355')."""
    try:
        d = Decimal(str(v)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return str(v)
    us = d.as_tuple().exponent
    return _tr_bicim(d, max(2, -us) if isinstance(us, int) else 2)


def _carpan_metni(c: Any) -> str:
    if not isinstance(c, dict):
        return str(c)
    deger = _carpan_tr(c.get("deger", "?"))
    return f"{deger} ({c['ad']})" if c.get("ad") else deger


def _havuz_gosterim(d: Any) -> Any:
    """Gider havuzu kaydı: taban/çarpanlar JSON'u yerine 'Toplam tutar: 1.000,10 × 1,35 (SGK) × 1,30 (zam) = 1.755,18 TL' okunur metni
    (değer `_Hazir` ile işaretlenir, ayrıca biçimlenmez). Toplam yoksa kayıt olduğu gibi kalır."""
    if not isinstance(d, dict) or d.get("toplam_tutar") is None:
        return d
    d = dict(d)
    taban, carpanlar, toplam = d.pop("taban_tutar", None), d.pop("carpanlar", None), d["toplam_tutar"]
    if taban is not None and carpanlar:
        d["toplam_tutar"] = _Hazir(" × ".join([_tutar_tr(taban), *map(_carpan_metni, carpanlar)]) + f" = {_tutar_tr(toplam)} TL")
    else:
        d["toplam_tutar"] = _Hazir(f"{_tutar_tr(toplam)} TL")
    return d


HAVUZ_ALAN_SINIRI = 240   # taban × çarpanlar = toplam metni 60 karakteri kolayca aşar; kesilirse toplam kaybolur


# ---------------------------------------------------------------- günlük metinlerinin okunur gösterimi
# Kayıtlar ham veriyi (anahtar/değer) saklamayı sürdürür; GÖSTERİM burada biçimlenir, eski kayıtlar da düzgün görünür.
# Değer türleri: tl (2 hane + TL), fiyat (en çok 4 hane), fiyat_tl (en çok 4 hane + TL), oran (yüzde), sayi (en çok 4 hane),
# metin, tarih (GG.AA.YYYY), evet (Evet/Hayır), surum (v3), senaryo (kimlik -> çalışma adı), gizli (gösterilmez);
# tanımsız anahtar "oto": etiket anahtardan türetilir, sayı/tarih görünen değer Türkçe biçimlenir.
class _Hazir(str):
    """Önceden biçimlenmiş metin: yeniden biçimlenmez."""


_ALANLAR: dict[str, tuple[str, str]] = {
    # genel
    "ad": ("Ad", "metin"), "aciklama": ("Açıklama", "metin"), "kod": ("Kod", "metin"), "aktif": ("Aktif", "evet"), "kilitli": ("Kilitli", "evet"),
    "tur": ("Tür", "metin"), "durum": ("Durum", "metin"), "dosya": ("Dosya", "metin"), "kaynak_dosya": ("Dosya", "metin"),
    "sayfa": ("Sayfa", "metin"), "tarih": ("Tarih", "tarih"), "yil": ("Yıl", "metin"), "neden": ("Neden", "metin"),
    # çalışma (senaryo)
    "sezon_ad": ("Sezon", "metin"), "kaynak_senaryo_ad": ("Kaynak çalışma", "metin"), "silinen_satir": ("Silinen satır", "sayi"),
    "yedek": ("Yedek dosyası", "metin"),
    # ürün kartı / üretim
    "urun_kodu": ("Ürün", "metin"), "urun_ad": ("Ürün adı", "metin"), "hat": ("Hat", "metin"), "taze_tursu_sinifi": ("Taze/turşu sınıfı", "metin"),
    "ambalaj_hacmi": ("Ambalaj hacmi", "sayi"), "suzme_kg": ("Süzme (kg)", "sayi"), "pazar": ("Pazar", "metin"), "marka": ("Marka", "metin"),
    "aile": ("Aile", "metin"), "aile_ad": ("Aile adı", "metin"), "doldurulan": ("Doldurulan", "sayi"),
    "vardiya_uretim_adedi": ("Vardiya üretim adedi", "sayi"), "dolum_personel": ("Dolum personeli", "sayi"),
    "etiketleme_adedi": ("Etiketleme adedi", "sayi"), "etiket_personel": ("Etiket personeli", "sayi"),
    "mal_kabul_miktar_kg": ("Mal kabul miktarı (kg)", "sayi"), "mal_kabul_fire": ("Mal kabul firesi", "oran"),
    "pazarlama_yonetim_uygula": ("Pazarlama ve yönetim gideri", "evet"), "gider_elle": ("Elle gider değerleri", "metin"),
    "net_kapasite": ("Net kapasite", "sayi"), "net_sure": ("Net süre", "sayi"), "toplam_kapasite": ("Toplam kapasite", "sayi"),
    "toplam_sure": ("Toplam süre", "sayi"), "hedef_uretim": ("Hedef üretim", "sayi"), "ortalama_isci": ("Ortalama işçi", "sayi"),
    # malzeme
    "tip": ("Tip", "metin"), "birim": ("Birim", "metin"), "para_birimi": ("Para birimi", "metin"), "zs": ("Z/S", "metin"),
    # satış / liste / teklif / stok
    "musteri": ("Müşteri", "metin"), "fiyat": ("Fiyat", "fiyat"), "adet": ("Adet", "sayi"), "liste_fiyati": ("Liste fiyatı", "fiyat_tl"),
    "birim_maliyet": ("Birim maliyet", "fiyat_tl"), "bolen": ("Bölen", "sayi"), "bolenler": ("Bölenler", "metin"), "ornek": ("Örnek veri", "evet"),
    "enflasyon": ("Enflasyon", "oran"), "uretim_adedi": ("Üretim adedi", "sayi"), "kar_orani": ("Kâr oranı", "oran"),
    "fiyat_tl": ("Fiyat", "fiyat_tl"), "tur_no": ("Tur", "metin"), "yazilan": ("Yazılan satır", "sayi"), "eklenen": ("Eklenen", "sayi"),
    "atlanan_kayitli": ("Atlanan (zaten kayıtlı)", "sayi"), "silinen": ("Silinen", "sayi"),
    # gider havuzu / ambalaj
    "toplam_tutar": ("Toplam tutar", "tl"), "taban_tutar": ("Taban tutar", "tl"), "baz_tipi": ("Dağıtım bazı", "metin"),
    "baz_miktar": ("Baz miktar", "sayi"), "anahtarlar": ("Dağıtım anahtarları", "metin"), "siniflar": ("Ambalaj sınıfları", "metin"),
    # reçete
    "aktif_versiyon": ("Etkin sürüm", "surum"), "versiyon": ("Sürüm", "surum"), "satir": ("Satır", "sayi"),
    # SMM
    "donem": ("Dönem", "metin"), "devir": ("Devralınan dönem", "metin"), "devir_kalem": ("Devralınan kalem", "sayi"),
    "devir_tutar": ("Devir tutarı", "tl"), "kalem": ("Kalem", "sayi"), "recete_satiri": ("Reçete satırı", "sayi"),
    "uzerine_yazildi": ("Üzerine yazıldı", "evet"), "sorunlu": ("Sorunlu satır", "sayi"), "onayli_kayip": ("Onaylı satır kaybı", "sayi"),
    "kaynak": ("Kaynak", "metin"), "elle_silinen": ("Silinen elle satır", "sayi"), "onceki": ("Önceki dönem", "metin"),
    "guncellenen": ("Güncellenen", "sayi"), "elle_kalem": ("Elle kalem", "sayi"), "elle_ez": ("Elle değerlerin üzerine yazıldı", "evet"),
    "dbs_miktar": ("Dönem başı miktar", "sayi"), "dbs_tutar": ("Dönem başı tutar", "tl"), "alim_miktar": ("Alım miktarı", "sayi"),
    "alim_tutar": ("Alım tutarı", "tl"), "iade_miktar": ("İade miktarı", "sayi"), "iade_tutar": ("İade tutarı", "tl"),
    "uretim_miktar": ("Üretim miktarı", "sayi"), "sayim_miktar": ("Sayım miktarı", "sayi"), "sahit_miktar": ("Şahit miktarı", "sayi"),
    "hesap": ("Hesap", "metin"), "bakiye": ("Bakiye", "tl"), "asama": ("Aşama", "metin"), "alternatif": ("Alternatif", "metin"),
    "mamul_kod": ("Mamul kodu", "metin"), "yari_mamul_kod": ("Yarı mamul kodu", "metin"),
    # kullanıcı / yükleme
    "kullanici_adi": ("Kullanıcı adı", "metin"), "rol": ("Rol", "metin"), "alan": ("Alan", "metin"), "kapsam": ("Kapsam", "metin"),
    "ozet": ("Özet", "metin"),
    # gizli: kimlikler ve ham ayrıntılar (çalışma adı satırın kendi bağlamında görünür)
    "senaryo_id": ("", "gizli"), "hesap_id": ("", "gizli"), "kaynak_senaryo_id": ("Kaynak çalışma", "senaryo"), "donem_id": ("", "gizli"),
    "yukleme_id": ("", "gizli"), "kayit_id": ("", "gizli"), "id": ("", "gizli"), "urun_id": ("", "gizli"), "ayrinti": ("", "gizli"),
    "kalemler": ("", "gizli"),
}
# Tabloya özgü etiketler (aynı anahtar başka tabloda başka anlama gelir)
_TABLO_ALANLARI: dict[str, dict[str, tuple[str, str]]] = {
    "senaryo": {"recete": ("Kopyalanan reçete", "sayi"), "fiyat": ("Kopyalanan fiyat", "sayi"), "parametre": ("Kopyalanan parametre", "sayi"),
                "metin": ("Kopyalanan metin", "sayi"), "havuz": ("Kopyalanan gider havuzu", "sayi"), "ambalaj": ("Kopyalanan ambalaj sınıfı", "sayi"),
                "hedef": ("Kopyalanan üretim hedefi", "sayi"), "kapasite": ("Kopyalanan kapasite", "sayi"),
                "fire": ("Kopyalanan fire kuralı", "sayi"), "sablon": ("Kopyalanan Excel şablonu", "sayi")},
    "satis_gecmisi": {"eklenen": ("Eklenen satır", "sayi")},
}
_SIFIRSA_GIZLE = {"atlanan_kayitli", "sorunlu", "elle_silinen", "onayli_kayip", "elle_kalem", "silinen_satir"}
_DEGER_ADLARI = {
    "pazar": {"yurtici": "Yurtiçi", "yurtdisi": "Yurtdışı"},
    "tur": {"fiyat_calismasi": "Fiyat çalışması", "gerceklesen": "Gerçekleşen", "butce": "Bütçe"},
    "durum": {"taslak": "Taslak", "gonderildi": "Gönderildi", "kabul": "Kabul", "red": "Red"},
    "baz_tipi": {"saniye": "Saniye", "kg": "Kg", "adet": "Adet"},
}
_SAYI_RE = re.compile(r"^-?\d+(\.\d+)?([eE][-+]?\d+)?$")
_TARIH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ondalik(v: Any) -> Decimal | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, Decimal)):
        return Decimal(v)
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, str) and _SAYI_RE.match(v.strip()):
        try:
            return Decimal(v.strip())
        except InvalidOperation:
            return None
    return None


def sayi_tr(v: Any, en_cok: int = 4, en_az: int = 0) -> str:
    """Sayı -> Türkçe biçim, en çok `en_cok` hane (ROUND_HALF_UP), sondaki sıfırlar atılır; kesirliyse en az 2 hane.
    '35.4359630040267227' -> '35,436'; '6.4' -> '6,40'; '18000000' -> '18.000.000'. Sayı değilse olduğu gibi."""
    d = _ondalik(v)
    if d is None or not d.is_finite():
        return str(v)
    d = d.quantize(Decimal(1).scaleb(-en_cok), rounding=ROUND_HALF_UP).normalize()
    us = -d.as_tuple().exponent if d.as_tuple().exponent < 0 else 0
    return _tr_bicim(d, max(en_az, us, 2 if us else 0))


def oran_tr(v: Any) -> str:
    """Oran -> yüzde: '0.2' -> '%20', '0.025' -> '%2,5', '0.55' -> '%55'."""
    d = _ondalik(v)
    if d is None or not d.is_finite():
        return str(v)
    d = (d * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).normalize()
    us = -d.as_tuple().exponent if d.as_tuple().exponent < 0 else 0
    return "%" + _tr_bicim(d, us)


def _tarih_tr(v: str) -> str:
    y, a, g = v.split("-")
    return f"{g}.{a}.{y}"


def _anahtar_listesi(v: Any) -> str | None:
    """Dağıtım anahtarları [[alt kalem, pay oranı, baz miktar], ...] -> 'Kavanoz Hattı %55, Teneke Hattı %25'."""
    if not isinstance(v, list) or not all(isinstance(x, (list, tuple)) and len(x) >= 2 for x in v):
        return None
    return ", ".join(f"{x[0]} {oran_tr(x[1])}" for x in v)


def _sinif_listesi(v: Any) -> str | None:
    """Ambalaj sınıfları [[ad, hacim, üretim adedi, katsayı], ...] -> '370 ml (hacim 370, adet 100, katsayı 0,50)'."""
    if not isinstance(v, list) or not all(isinstance(x, (list, tuple)) and len(x) == 4 for x in v):
        return None
    return ", ".join(f"{x[0]} (hacim {sayi_tr(x[1])}, adet {sayi_tr(x[2])}, katsayı {sayi_tr(x[3], en_az=2)})" for x in v)


def _alan(tablo: str | None, anahtar: str) -> tuple[str, str]:
    if tablo and anahtar in _TABLO_ALANLARI.get(tablo, {}):
        return _TABLO_ALANLARI[tablo][anahtar]
    if anahtar in _ALANLAR:
        return _ALANLAR[anahtar]
    return anahtar.replace("_", " ").strip().capitalize(), "oto"


def _bos_mu(v: Any) -> bool:
    return v is None or (isinstance(v, (str, list, tuple, dict)) and len(v) == 0)


def deger_metni(v: Any, tur: str = "metin", anahtar: str | None = None, senaryo_adlari: dict[int, str] | None = None) -> str:
    """Tek bir değerin okunur metni (sözlük/liste dökümü yok)."""
    if isinstance(v, _Hazir):
        return str(v)
    if anahtar == "anahtarlar" and (m_ := _anahtar_listesi(v)) is not None:
        return m_
    if anahtar == "siniflar" and (m_ := _sinif_listesi(v)) is not None:
        return m_
    if anahtar in _DEGER_ADLARI and isinstance(v, str):
        return _DEGER_ADLARI[anahtar].get(v, v)
    if isinstance(v, bool) or tur == "evet":
        return "Evet" if v else "Hayır"
    if tur == "senaryo":
        return (senaryo_adlari or {}).get(v) or "(silinmiş çalışma)"
    if isinstance(v, dict):
        if anahtar == "bolenler":
            return ", ".join(f"{_DEGER_ADLARI['pazar'].get(k, k)} {sayi_tr(x)}" for k, x in v.items())
        return ", ".join(f"{_alan(None, str(k))[0]} {deger_metni(x, _alan(None, str(k))[1], str(k))}" for k, x in v.items()
                         if not _bos_mu(x) and _alan(None, str(k))[1] != "gizli")
    if isinstance(v, (list, tuple)):
        return ", ".join(" / ".join(deger_metni(y) for y in x) if isinstance(x, (list, tuple)) else deger_metni(x) for x in v)
    if tur == "surum" and _ondalik(v) is not None:
        return f"v{v}"
    if tur == "tarih" or (isinstance(v, str) and _TARIH_RE.match(v)):
        return _tarih_tr(v) if isinstance(v, str) and _TARIH_RE.match(v) else str(v)
    if tur == "metin" or _ondalik(v) is None:
        return str(v)
    if tur == "tl":
        return f"{_tutar_tr(v)} TL"
    if tur == "fiyat_tl":
        return f"{sayi_tr(v, 4, 2)} TL"
    if tur == "fiyat":
        return sayi_tr(v, 4, 2)
    if tur == "oran":
        return oran_tr(v)
    return sayi_tr(v)


def _alanlar_metni(d: dict, anahtarlar: list[str], tablo: str | None, sinir: int, senaryo_adlari: dict[int, str] | None) -> str | None:
    parcalar = []
    for k in anahtarlar:
        v = d.get(k)
        etiket, tur = _alan(tablo, k)
        if tur == "gizli" or _bos_mu(v) or (k in _SIFIRSA_GIZLE and _ondalik(v) == 0):
            continue
        if k == "kaynak_senaryo_id" and d.get("kaynak_senaryo_ad"):
            continue   # ad zaten yazılı
        parcalar.append(f"{etiket}: {_kisa(deger_metni(v, tur, k, senaryo_adlari), sinir)}")
    return "; ".join(parcalar) or None


def _gorunur(k: str) -> bool:
    return not k.startswith("_")


def fark_metni(eski: Any, yeni: Any, alan_siniri: int = 120, tablo: str | None = None,
               senaryo_adlari: dict[int, str] | None = None) -> tuple[str | None, str | None, str | None]:
    """DegisiklikKaydi.eski/yeni -> (eski_metin, yeni_metin, neden), okunur Türkçe: alan adları etiketli ('Birim maliyet: 30,8139 TL'),
    boş alanlar ve kimlikler yazılmaz, tutarlar Türkçe biçimli, liste/sözlük dökümü yok. Sözlüklerde yalnız değişen alanlar gösterilir
    (alan başına `alan_siniri` karakter). `_` ile başlayan iç alanlar gösterilmez; `_neden` (yoksa `neden`) ayrılır."""
    neden = None
    if isinstance(yeni, dict):
        neden = yeni.get("_neden") or (yeni.get("neden") if isinstance(yeni.get("neden"), str) else None)
        yeni = {k: v for k, v in yeni.items() if _gorunur(k) and k != "neden"}
        if set(yeni) == {"siniflar"}:
            yeni = yeni["siniflar"]
    if isinstance(eski, dict):
        eski = {k: v for k, v in eski.items() if _gorunur(k)}
    if isinstance(eski, dict) and isinstance(yeni, dict) and yeni:
        # önce iki tarafta da olan ve değişen alanlar (yalnız yenide olan ürün kodu/yıl gibi bağlam alanları gürültü yapmaz)
        degisen = ([k for k in yeni if k in eski and eski[k] != yeni[k]] or [k for k in yeni if eski.get(k) != yeni[k]] or list(yeni))
        return (_alanlar_metni(eski, degisen, tablo, alan_siniri, senaryo_adlari),
                _alanlar_metni(yeni, degisen, tablo, alan_siniri, senaryo_adlari), neden)

    def gos(v: Any) -> str | None:   # silmede `yeni` yalnız nedeni taşır: boş sözlük -> None, eski tam gösterilir
        if isinstance(v, dict):
            return _alanlar_metni(v, list(v), tablo, alan_siniri, senaryo_adlari)
        if _bos_mu(v):
            return None
        if tablo == "ambalaj_sinifi" and (m_ := _sinif_listesi(v)) is not None:
            return _kisa(m_, 4 * alan_siniri)
        return _kisa(deger_metni(v), 4 * alan_siniri)
    return gos(eski), gos(yeni), neden


def _gun_basi(d: date) -> datetime:
    """Kullanıcının (sunucunun) yerel takvim gününün başlangıcı, saklanan damgalarla aynı eksende (naif UTC).
    Önceden UTC gece yarısı alınıyordu; Türkiye'de 00:00-03:00 arası kayıtlar bir önceki güne düşüyordu."""
    return datetime.combine(d, time.min).astimezone().astimezone(timezone.utc).replace(tzinfo=None)


def _naif_utc(z: datetime | None) -> datetime:
    if z is None:
        return datetime.min
    return z.astimezone(timezone.utc).replace(tzinfo=None) if z.tzinfo else z


def _satir(kaynak: str, pk: int, zaman: datetime | None, kullanici: str | None, tur: str, baslik: str, **ek) -> dict:
    return {"id": f"{kaynak}:{pk}", "zaman": zaman_iso(zaman), "_z": _naif_utc(zaman), "_pk": pk, "kullanici": kullanici or "sistem", "tur": tur, "baslik": baslik,
            "urun_kodu": ek.get("urun_kodu"), "senaryo_id": ek.get("senaryo_id"), "eski": ek.get("eski"), "yeni": ek.get("yeni"), "neden": ek.get("neden"),
            "geri_alinabilir": False, "geri_al": None}


def _onceki_ile_eski(kayitlar: list, grup, deger) -> dict[int, Any]:
    """Aynı (grup) içinde id sırasına göre bir önceki kaydın değeri; ilk kayıt için yok (None, ve `ilk` işaretli)."""
    onceki: dict[tuple, Any] = {}
    out: dict[int, Any] = {}
    for k in sorted(kayitlar, key=lambda x: x.id):
        g = grup(k)
        out[k.id] = onceki.get(g)
        onceki[g] = k
    return out


def _bugun() -> str:
    return date.today().isoformat()


def _degisiklik_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun]) -> list[dict]:
    kayitlar = list(s.scalars(select(m.DegisiklikKaydi)))
    if not kayitlar:
        return []
    hedef = {h.id: (h.urun_id, h.senaryo_id) for h in s.execute(select(m.UretimHedefi.id, m.UretimHedefi.urun_id, m.UretimHedefi.senaryo_id)).all()}
    havuz = dict(s.execute(select(m.GiderHavuzu.id, m.GiderHavuzu.senaryo_id)).all())
    kap = {k.id: (k.urun_kodu, k.senaryo_id) for k in s.execute(select(m.UretimKapasitesi.id, m.UretimKapasitesi.urun_kodu, m.UretimKapasitesi.senaryo_id)).all()}
    satis = dict(s.execute(select(m.SatisGecmisi.id, m.SatisGecmisi.urun_id)).all())
    recete = {r.id: (r.urun_id, r.senaryo_id) for r in s.execute(select(m.Recete.id, m.Recete.urun_id, m.Recete.senaryo_id)).all()}
    malzeme = dict(s.execute(select(m.Malzeme.id, m.Malzeme.kod)).all())
    senaryo_adlari = dict(s.execute(select(m.Senaryo.id, m.Senaryo.ad)).all())
    out = []
    for k in kayitlar:
        urun_kodu, sen_id = None, None
        t = k.tablo
        if t == "urun":
            urun_kodu = urunler[k.kayit_id].kod if k.kayit_id in urunler else None
        elif t == "uretim_hedefi" and k.kayit_id in hedef:
            uid, sen_id = hedef[k.kayit_id]
            urun_kodu = urunler[uid].kod if uid in urunler else None
        elif t == "gider_havuzu":
            sen_id = havuz.get(k.kayit_id)
        elif t == "ambalaj_sinifi":
            sen_id = k.kayit_id
        elif t == "uretim_kapasitesi":
            urun_kodu, sen_id = kap.get(k.kayit_id, (None, None))
            if urun_kodu is None and isinstance(k.yeni, dict):
                urun_kodu = k.yeni.get("urun_kodu")
        elif t == "satis_gecmisi":
            if k.kayit_id in satis and satis[k.kayit_id] in urunler:
                urun_kodu = urunler[satis[k.kayit_id]].kod
            else:   # silinmiş kayıt: ürün kodu içerikte saklıdır (silmede `yeni` yalnız nedeni taşır)
                veri = k.yeni if isinstance(k.yeni, dict) and "urun_kodu" in k.yeni else k.eski
                urun_kodu = veri.get("urun_kodu") if isinstance(veri, dict) else None
        elif t == "recete" and k.kayit_id in recete:
            uid, sen_id = recete[k.kayit_id]
            urun_kodu = urunler[uid].kod if uid in urunler else None
        elif t == "malzeme":
            urun_kodu = None
        elif t == "senaryo":
            sen_id = k.kayit_id
        elif t == "liste_fiyati":
            veri = k.yeni if isinstance(k.yeni, dict) and "urun_kodu" in k.yeni else k.eski
            urun_kodu = veri.get("urun_kodu") if isinstance(veri, dict) else None
        elif t == "stok_devri":   # ürün ve çalışma içerikte saklıdır (silinen kayıtta da)
            veri = k.yeni if isinstance(k.yeni, dict) and "urun_kodu" in k.yeni else k.eski
            if isinstance(veri, dict):
                urun_kodu, sen_id = veri.get("urun_kodu"), veri.get("senaryo_id")
        elif t == "duzenleme_kilidi":   # arayüz düzenleme kilidinin açılması: çalışma içerikte saklıdır (yoksa her çalışmada görünür)
            sen_id = k.yeni.get("senaryo_id") if isinstance(k.yeni, dict) else None
        elif t == "teklif" and isinstance(k.eski, dict):   # silinmiş tur: ürün ve senaryo içerikte saklıdır
            urun_kodu, sen_id = k.eski.get("urun_kodu"), k.eski.get("senaryo_id")
        if senaryo is not None and sen_id is not None and sen_id != senaryo:
            continue   # senaryoya bağlı kayıt başka senaryoya aitse çıkar; senaryosuz (ürün/malzeme/satış) kayıtlar her senaryoda görünür
        if t == "gider_havuzu":
            eski, yeni, neden = fark_metni(_havuz_gosterim(k.eski), _havuz_gosterim(k.yeni), HAVUZ_ALAN_SINIRI, t, senaryo_adlari)
        else:
            eski, yeni, neden = fark_metni(k.eski, k.yeni, tablo=t, senaryo_adlari=senaryo_adlari)
        baslik = f"{_TABLO_ETIKET.get(t, t)} {_ISLEM_ETIKET.get(k.islem, k.islem)}"
        if t == "malzeme" and malzeme.get(k.kayit_id):
            baslik += f" ({malzeme[k.kayit_id]})"
        out.append(_satir("degisiklik", k.id, k.zaman, k.kullanici, _TABLO_TUR.get(t, "diger"), baslik, urun_kodu=urun_kodu, senaryo_id=sen_id,
                          eski=eski, yeni=yeni, neden=neden))
    return out


def _parametre_satirlari(s: Session, senaryo: int | None, kilitli: dict[int, bool], gerceklesen: set[int],
                         urunler: dict[int, m.Urun] | None = None) -> list[dict]:
    from .parametre_servisi import _okunur_ad, yuzde_mi
    tanimlar = {p.anahtar: p for p in s.execute(select(m.Parametre)).scalars()}
    birimler = {a: p.birim for a, p in tanimlar.items()}
    q = select(m.ParametreDegeri, m.Parametre.anahtar).join(m.Parametre, m.Parametre.id == m.ParametreDegeri.parametre_id)
    if senaryo is not None:
        q = q.where(m.ParametreDegeri.senaryo_id == senaryo)
    sat = list(s.execute(q).all())
    son_id = {}
    for d, _ in sat:
        g = (d.senaryo_id, d.parametre_id, d.kapsam_tipi, d.kapsam_id)
        son_id[g] = max(son_id.get(g, 0), d.id)
    onceki = _onceki_ile_eski([d for d, _ in sat], lambda d: (d.senaryo_id, d.parametre_id, d.kapsam_tipi, d.kapsam_id), None)
    out = []
    for d, anahtar in sat:
        e = onceki[d.id]
        u = (urunler or {}).get(d.kapsam_id) if d.kapsam_tipi != "genel" else None
        kapsam = "" if d.kapsam_tipi == "genel" else (f" (ürün {u.kod})" if u else " (ürüne özel)")
        bic = oran_tr if yuzde_mi(anahtar, birimler.get(anahtar)) else sayi_tr
        r = _satir("parametre", d.id, d.olusturma_zamani, d.olusturan, "parametre", f"Parametre: {_okunur_ad(tanimlar[anahtar]) if anahtar in tanimlar else anahtar}{kapsam}", senaryo_id=d.senaryo_id,
                   urun_kodu=u.kod if u else None, eski=None if e is None else bic(e.deger), yeni=bic(d.deger), neden=d.neden)
        r["anahtar"] = anahtar
        g = (d.senaryo_id, d.parametre_id, d.kapsam_tipi, d.kapsam_id)
        if e is not None and son_id[g] == d.id and not kilitli.get(d.senaryo_id) and not (anahtar == "enflasyon" and d.senaryo_id in gerceklesen):
            r["geri_alinabilir"] = True
            r["geri_al"] = {"yol": f"/api/v1/parametreler/{anahtar}/degerler?senaryo={d.senaryo_id}",
                            "govde": {"deger": str(e.deger), "gecerlilik_basi": _bugun(), "neden": f"Geri alındı (günlük #{d.id})",
                                      "kapsam_tipi": d.kapsam_tipi, "kapsam_id": d.kapsam_id}}
        out.append(r)
    return out


def _fiyat_metni(f: m.MalzemeFiyati) -> str:
    return f"{sayi_tr(f.fiyat, 4, 2)} {f.para_birimi or 'TL'}"


def _fiyat_satirlari(s: Session, senaryo: int | None, kilitli: dict[int, bool]) -> list[dict]:
    q = select(m.MalzemeFiyati, m.Malzeme.kod).join(m.Malzeme, m.Malzeme.id == m.MalzemeFiyati.malzeme_id)
    if senaryo is not None:
        q = q.where(m.MalzemeFiyati.senaryo_id == senaryo)
    sat = list(s.execute(q).all())
    grup = lambda f: (f.senaryo_id, f.malzeme_id)
    onceki = _onceki_ile_eski([f for f, _ in sat], grup, None)
    son_id: dict[tuple, int] = {}
    for f, _ in sat:
        son_id[grup(f)] = max(son_id.get(grup(f), 0), f.id)
    out = []
    for f, kod in sat:
        e = onceki[f.id]
        r = _satir("fiyat", f.id, f.olusturma_zamani, f.olusturan, "fiyat", f"Malzeme fiyatı: {kod}", senaryo_id=f.senaryo_id,
                   eski=None if e is None else _fiyat_metni(e), yeni=_fiyat_metni(f), neden=f.neden)
        r["kod"] = kod
        if e is not None and son_id[grup(f)] == f.id and not kilitli.get(f.senaryo_id):
            r["geri_alinabilir"] = True
            r["geri_al"] = {"yol": f"/api/v1/malzemeler/{kod}/fiyatlar?senaryo={f.senaryo_id}",
                            "govde": {"fiyat": str(e.fiyat), "gecerlilik_basi": _bugun(), "neden": f"Geri alındı (günlük #{f.id})", "para_birimi": e.para_birimi}}
        out.append(r)
    return out


def _fire_satirlari(s: Session, senaryo: int | None, kilitli: dict[int, bool]) -> list[dict]:
    q = select(m.FireKurali)
    if senaryo is not None:
        q = q.where(m.FireKurali.senaryo_id == senaryo)
    sat = list(s.scalars(q))
    grup = lambda f: (f.senaryo_id, f.kapsam_tipi, f.kapsam_deger)
    onceki = _onceki_ile_eski(sat, grup, None)
    son_id: dict[tuple, int] = {}
    for f in sat:
        son_id[grup(f)] = max(son_id.get(grup(f), 0), f.id)
    out = []
    for f in sat:
        e = onceki[f.id]
        r = _satir("fire", f.id, f.olusturma_zamani, f.olusturan, "fire", f"Fire kuralı: {f.kapsam_tipi} {f.kapsam_deger}", senaryo_id=f.senaryo_id,
                   eski=None if e is None else oran_tr(e.oran), yeni=oran_tr(f.oran), neden=f.neden)
        if e is not None and son_id[grup(f)] == f.id and not kilitli.get(f.senaryo_id):
            r["geri_alinabilir"] = True
            r["geri_al"] = {"yol": f"/api/v1/fire-kurallari?senaryo={f.senaryo_id}",
                            "govde": {"kapsam_tipi": f.kapsam_tipi, "kapsam_deger": f.kapsam_deger, "oran": str(e.oran), "gecerlilik_basi": _bugun(),
                                      "neden": f"Geri alındı (günlük #{f.id})"}}
        out.append(r)
    return out


def _metin_satirlari(s: Session, senaryo: int | None) -> list[dict]:
    q = select(m.MetinParametre)
    if senaryo is not None:
        q = q.where(m.MetinParametre.senaryo_id == senaryo)
    sat = list(s.scalars(q))
    onceki = _onceki_ile_eski(sat, lambda k: (k.senaryo_id, k.anahtar), None)
    return [_satir("metin", k.id, k.olusturma_zamani, k.olusturan, "metin", f"Metin parametresi: {k.anahtar}", senaryo_id=k.senaryo_id,
                   eski=None if onceki[k.id] is None else _kisa(onceki[k.id].deger), yeni=_kisa(k.deger), neden=k.neden) for k in sat]


def _recete_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun], kilitli: dict[int, bool]) -> list[dict]:
    q = select(m.Recete)
    if senaryo is not None:
        q = q.where(m.Recete.senaryo_id == senaryo)
    sat = list(s.scalars(q))
    adet = dict(s.execute(select(m.ReceteSatiri.recete_id, func.count()).group_by(m.ReceteSatiri.recete_id)).all())
    grup = lambda r: (r.urun_id, r.senaryo_id)
    onceki = _onceki_ile_eski(sat, grup, None)   # id sırası = sürüm sırası
    out = []
    for r in sat:
        urun_kodu = urunler[r.urun_id].kod if r.urun_id in urunler else None
        e = onceki[r.id]
        satir = _satir("recete", r.id, r.olusturma_zamani, r.olusturan, "recete",
                       f"Reçete sürümü v{r.versiyon} ({r.kaynak or 'bilinmiyor'}, {adet.get(r.id, 0)} satır){'' if r.aktif else ' - pasif'}",
                       urun_kodu=urun_kodu, senaryo_id=r.senaryo_id, eski=None if e is None else f"v{e.versiyon}", yeni=f"v{r.versiyon}",
                       neden=r.neden)
        if r.aktif and e is not None and urun_kodu and not kilitli.get(r.senaryo_id):
            satir["geri_alinabilir"] = True
            satir["geri_al"] = {"yol": f"/api/v1/urunler/{urun_kodu}/recete/{e.versiyon}/etkinlestir?senaryo={r.senaryo_id}",
                                "govde": {"neden": f"Geri alındı: v{r.versiyon} yerine v{e.versiyon} (günlük #{r.id})"}}
        out.append(satir)
    return out


def _hesap_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun]) -> list[dict]:
    q = select(m.MaliyetHesabi)
    if senaryo is not None:
        q = q.where(m.MaliyetHesabi.senaryo_id == senaryo)
    out = []
    for h in s.scalars(q):
        sn = h.sonuc_snapshot or {}
        u = urunler.get(h.urun_id)
        yeni = f"Maliyet: {_tutar_tr(sn['finansman_dahil_maliyet_tl'])} TL" if sn.get("finansman_dahil_maliyet_tl") is not None else None
        out.append(_satir("hesap", h.id, h.olusturma_zamani, h.olusturan, "hesap", f"Hesap kaydedildi ({h.hesap_tarihi.strftime('%d.%m.%Y')})",
                          urun_kodu=u.kod if u else None, senaryo_id=h.senaryo_id, yeni=yeni, neden=(h.girdi_snapshot or {}).get("neden")))
    return out


def _teklif_satirlari(s: Session, senaryo: int | None, urunler: dict[int, m.Urun]) -> list[dict]:
    q = select(m.Teklif, m.MaliyetHesabi.urun_id, m.MaliyetHesabi.senaryo_id).join(m.MaliyetHesabi, m.MaliyetHesabi.id == m.Teklif.maliyet_hesabi_id)
    if senaryo is not None:
        q = q.where(m.MaliyetHesabi.senaryo_id == senaryo)
    out = []
    for t, urun_id, sen_id in s.execute(q).all():
        u = urunler.get(urun_id)
        musteri = f" - {t.musteri}" if t.musteri else ""
        durum = _DEGER_ADLARI["durum"].get(t.durum, t.durum)
        out.append(_satir("teklif", t.id, t.olusturma_zamani, t.olusturan, "teklif", f"Teklif turu {t.tur_no} ({durum}){musteri}",
                          urun_kodu=u.kod if u else None, senaryo_id=sen_id,
                          yeni=f"Fiyat: {sayi_tr(t.fiyat_tl, 4, 2)} TL; Kâr oranı: {oran_tr(t.kar_orani)}", neden=t.notu))
    return out


def _tum_satirlar(s: Session, senaryo: int | None) -> list[dict]:
    urunler = {u.id: u for u in s.scalars(select(m.Urun))}
    sen_durum = {x.id: (x.kilitli, x.tur) for x in s.execute(select(m.Senaryo.id, m.Senaryo.kilitli, m.Senaryo.tur)).all()}
    kilitli = {i: bool(k) for i, (k, _) in sen_durum.items()}
    gerceklesen = {i for i, (_, t) in sen_durum.items() if t == "gerceklesen"}
    return (_degisiklik_satirlari(s, senaryo, urunler) + _parametre_satirlari(s, senaryo, kilitli, gerceklesen, urunler) + _fiyat_satirlari(s, senaryo, kilitli)
            + _fire_satirlari(s, senaryo, kilitli) + _metin_satirlari(s, senaryo) + _recete_satirlari(s, senaryo, urunler, kilitli)
            + _hesap_satirlari(s, senaryo, urunler) + _teklif_satirlari(s, senaryo, urunler))


def _suz(satirlar: list[dict], f: Suzgec) -> list[dict]:
    bas = _gun_basi(f.bas) if f.bas else None
    son = _gun_basi(f.son + timedelta(days=1)) if f.son else None
    turler = set(f.tur)
    kul = (f.kullanici or "").strip().casefold()
    kod = (f.urun_kodu or "").strip().casefold()
    q = (f.q or "").strip().casefold()
    out = []
    for r in satirlar:
        if bas and r["_z"] < bas or son and r["_z"] >= son:
            continue
        if turler and r["tur"] not in turler:
            continue
        if kul and (r["kullanici"] or "").casefold() != kul:
            continue
        if kod and kod not in (r["urun_kodu"] or "").casefold():
            continue
        if q and q not in " ".join(str(r.get(a) or "") for a in ("baslik", "kullanici", "urun_kodu", "eski", "yeni", "neden", "anahtar", "kod")).casefold():
            continue
        out.append(r)
    out.sort(key=lambda r: (r["_z"], r["_pk"]), reverse=True)   # aynı saniyedeki kayıtlar: kimlik sırası (yeni önce)
    return out


def _temiz(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in ("_z", "_pk", "anahtar", "kod")}


def _dogrula(f: Suzgec) -> None:
    kotu = [t for t in f.tur if t not in TURLER]
    if kotu:
        raise DogrulamaHatasi(f"Bilinmeyen kayıt türü: {liste_metni(kotu)}.", {"tur": kotu, "izinli": list(TURLER)})
    if f.bas and f.son and f.bas > f.son:
        raise DogrulamaHatasi("Başlangıç tarihi bitiş tarihinden sonra olamaz.", {"bas": f.bas.isoformat(), "son": f.son.isoformat()})


def senaryo_denetle(s: Session, senaryo: int | None) -> None:
    if senaryo is not None and s.get(m.Senaryo, senaryo) is None:
        raise BulunamadiHatasi("Çalışma bulunamadı.", {"senaryo_id": senaryo})


def liste(s: Session, f: Suzgec, sayfa: int = 1, boyut: int = 50) -> tuple[list[dict], int]:
    _dogrula(f)
    senaryo_denetle(s, f.senaryo)
    uygun = _suz(_tum_satirlar(s, f.senaryo), f)
    bas = (sayfa - 1) * boyut
    return [_temiz(r) for r in uygun[bas:bas + boyut]], len(uygun)


def ozet(s: Session, senaryo: int | None, gun: int = 7) -> dict:
    senaryo_denetle(s, senaryo)
    f = Suzgec(senaryo=senaryo, bas=date.today() - timedelta(days=gun - 1))
    uygun = _suz(_tum_satirlar(s, senaryo), f)
    kul = Counter(r["kullanici"] for r in uygun)
    tur = Counter(r["tur"] for r in uygun)
    return {"gun": gun, "toplam": len(uygun),
            "kullanici_bazinda": [{"kullanici": k, "adet": n} for k, n in sorted(kul.items(), key=lambda x: (-x[1], x[0]))],
            "tur_bazinda": [{"tur": k, "adet": n} for k, n in sorted(tur.items(), key=lambda x: (-x[1], x[0]))]}


XLSX_BASLIK = ["Zaman", "Kullanıcı", "Tür", "Başlık", "Ürün kodu", "Çalışma", "Eski", "Yeni", "Neden"]
TUR_ETIKET = {"parametre": "Parametre", "fiyat": "Malzeme fiyatı", "fire": "Fire kuralı", "metin": "Metin parametresi", "recete": "Reçete",
              "hesap": "Hesap", "teklif": "Teklif", "urun": "Ürün kartı", "hedef": "Üretim hedefi", "havuz": "Gider havuzu",
              "ambalaj": "Ambalaj sınıfları", "kapasite": "Üretim kapasitesi", "satis": "Satış geçmişi", "diger": "Diğer"}


def _zaman_tr(z: str | None) -> str | None:
    """ISO zaman -> yerel 'GG.AA.YYYY SS:DD'."""
    if not z:
        return None
    try:
        d = datetime.fromisoformat(z)
    except ValueError:
        return z
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone().strftime("%d.%m.%Y %H:%M")


def xlsx(s: Session, f: Suzgec) -> BytesIO:
    _dogrula(f)
    senaryo_denetle(s, f.senaryo)
    wb = Workbook()
    ws = wb.active
    ws.title = "Değişiklik Günlüğü"
    ws.append(XLSX_BASLIK)
    adlar = dict(s.execute(select(m.Senaryo.id, m.Senaryo.ad)).all())
    for r in _suz(_tum_satirlar(s, f.senaryo), f):   # Eski/Yeni/Neden: günlük ekranıyla aynı okunur metin
        ws.append([_zaman_tr(r["zaman"]), r["kullanici"], TUR_ETIKET.get(r["tur"], r["tur"]), r["baslik"], r["urun_kodu"],
                   adlar.get(r["senaryo_id"]), r["eski"], r["yeni"], r["neden"]])
    for sutun, genislik in zip("ABCDEFGHI", (18, 14, 18, 44, 16, 24, 40, 40, 36)):
        ws.column_dimensions[sutun].width = genislik
    ws.freeze_panes = "A2"
    tampon = BytesIO()
    wb.save(tampon)
    tampon.seek(0)
    return tampon


# ---------------------------------------------------------------- reçete sürümü etkinleştirme (geri al ucu)
def recete_etkinlestir(s: Session, urun_kodu: str, senaryo_id: int, versiyon: int, neden: str, kullanici: str = "sistem") -> m.Recete:
    """Seçilen eski sürümü aktif yapar (satırlar silinmez, sürüm numarası artmaz); DegisiklikKaydi yazar."""
    if not (neden or "").strip():
        raise DogrulamaHatasi("Neden girin.")
    u = s.scalar(select(m.Urun).where(m.Urun.kod == urun_kodu))
    if u is None:
        raise BulunamadiHatasi(f"{urun_kodu} kodlu ürün bulunamadı.", {"kod": urun_kodu})
    r = s.scalar(select(m.Recete).where(m.Recete.urun_id == u.id, m.Recete.senaryo_id == senaryo_id, m.Recete.versiyon == versiyon))
    if r is None:
        raise BulunamadiHatasi(f"Reçetenin v{versiyon} sürümü bulunamadı.", {"versiyon": versiyon})
    if not r.aktif:
        eski = s.scalar(select(m.Recete).where(m.Recete.urun_id == u.id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True))
        for x in s.scalars(select(m.Recete).where(m.Recete.urun_id == u.id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True)):
            x.aktif = False
        r.aktif = True
        s.add(m.DegisiklikKaydi(tablo="recete", kayit_id=r.id, islem="etkinlestir", kullanici=kullanici,
                                eski={"aktif_versiyon": eski.versiyon if eski else None}, yeni={"aktif_versiyon": versiyon, "_neden": neden}))
        s.flush()
    return r
