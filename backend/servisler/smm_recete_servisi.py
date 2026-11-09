"""Maliyet muhasebesi: kalıcı üretim reçeteleri (Canias ürün ağacı dökümü, 'TBLRESULT'). Dönemden bağımsızdır; Canias'ta değişince
yeniden yüklenir. Dönem, reçete kaynağı 'ana' ise aşama hesabında bu reçeteleri kullanır (bkz. smm_asama_servisi).

Döküm sütunları: Alternatif Numarası, Malzeme Kodu, Malzeme Açıklaması, Satır No, Ürün Ağacı Kalem Tipi, Tüketim Malzeme Kodu,
Tüketim Malzeme Adı, Tüketim Miktarı, Tüketim Birimi, Fire Oranı (%), Fireli Miktar. Tüketim malzemesi boş satırlar ürün başlığıdır.
Aşama koddan: 02 -> 40 (üretim hattı), 03 -> 50 (etiketleme), diğerleri (01 salamura, 11-19 taze/kalibre/fermente) -> 20."""
import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi
from .smm_servisi import MAKS_BAYT, SIFIR, _d, _metin, _tr, donem_getir

BASLIKLAR = ("Alternatif Numarası", "Malzeme Kodu", "Malzeme Açıklaması", "Satır No", "Ürün Ağacı Kalem Tipi", "Tüketim Malzeme Kodu",
             "Tüketim Malzeme Adı", "Tüketim Miktarı", "Tüketim Birimi", "Fire Oranı")
VARSAYILAN_ALTERNATIF = "00"
YUZ = Decimal(100)


def asama_bul(kod: str) -> int:
    return {"02": 40, "03": 50}.get(kod[:2], 20)


@dataclass
class HesapSatiri:
    """Aşama hesabının beklediği reçete satırı biçimi (SmmReceteSatiri ile aynı alanlar)."""
    asama: int
    ana_kod: str
    ana_ad: str | None
    malzeme_kod: str
    malzeme_ad: str | None
    miktar: Decimal
    birim: str | None
    fire_orani: Decimal
    ana_miktar: Decimal = Decimal(1)
    ana_birim: str | None = None
    ozel: dict | None = None


# ---------------------------------------------------------------- dosya
def dosya_oku(icerik: bytes) -> list[dict]:
    if len(icerik) > MAKS_BAYT:
        raise DogrulamaHatasi("dosya 60 MB'den büyük")
    try:
        wb = load_workbook(io.BytesIO(icerik), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError):
        raise DogrulamaHatasi("dosya geçerli bir .xlsx değil")
    try:
        ws = wb.worksheets[0]
        satirlar = ws.iter_rows(values_only=True)
        baslik = [(_metin(x) or "") for x in next(satirlar, ())]
        sira = {}
        for b in BASLIKLAR:
            if b not in baslik:
                raise DogrulamaHatasi("Canias ürün ağacı dökümü bekleniyor; sütun eksik", {"eksik": b, "beklenen": list(BASLIKLAR)})
            sira[b] = baslik.index(b)
        out = []
        for r in satirlar:
            def h(b):
                i = sira[b]
                return r[i] if i < len(r) else None
            kod, mal = _metin(h("Malzeme Kodu")), _metin(h("Tüketim Malzeme Kodu"))
            if not kod or not mal:
                continue   # ürün başlık satırı
            tip = h("Ürün Ağacı Kalem Tipi")
            out.append({"ana_kod": kod, "ana_ad": _metin(h("Malzeme Açıklaması")), "alternatif": _metin(h("Alternatif Numarası")) or VARSAYILAN_ALTERNATIF,
                        "satir_no": int(_d(h("Satır No"))), "kalem_tipi": int(tip) if isinstance(tip, (int, float)) else None,
                        "asama": asama_bul(kod), "malzeme_kod": mal, "malzeme_ad": _metin(h("Tüketim Malzeme Adı")),
                        "miktar": _d(h("Tüketim Miktarı")), "birim": _metin(h("Tüketim Birimi")), "fire_orani": _d(h("Fire Oranı")) / YUZ})
        if not out:
            raise DogrulamaHatasi("dosyada reçete satırı yok")
        return out
    finally:
        wb.close()


def _ozet(satirlar: list[dict]) -> dict:
    urunler = defaultdict(set)
    asama = defaultdict(set)
    for x in satirlar:
        urunler[x["ana_kod"]].add(x["alternatif"])
        asama[x["asama"]].add(x["ana_kod"])
    return {"satir_sayisi": len(satirlar), "urun_sayisi": len(urunler),
            "asama": {str(a): len(k) for a, k in sorted(asama.items())},
            "alternatifli_urun": sum(1 for a in urunler.values() if len(a) > 1)}


def _imza(satirlar) -> dict[tuple[str, str], tuple]:
    """(ürün, alternatif) -> satırların karşılaştırılabilir özeti."""
    g = defaultdict(list)
    for x in satirlar:
        get = (lambda k: x[k]) if isinstance(x, dict) else (lambda k: getattr(x, k))
        g[(get("ana_kod"), get("alternatif"))].append((get("malzeme_kod"), str(_d(get("miktar")).normalize()), str(_d(get("fire_orani")).normalize())))
    return {k: tuple(sorted(v)) for k, v in g.items()}


def _urun_imza(imza: dict[tuple[str, str], tuple]) -> dict[str, frozenset]:
    """(ürün, alternatif) imzalarını ürün başına tek imzada toplar."""
    out = defaultdict(set)
    for (kod, alt), v in imza.items():
        out[kod].add((alt, v))
    return {k: frozenset(v) for k, v in out.items()}


def _elle_kodlar(s: Session) -> set[str]:
    return set(s.scalars(select(m.SmmReceteElle.ana_kod)))


def onizle(s: Session, icerik: bytes) -> dict:
    yeni = dosya_oku(icerik)
    return _onizle(s, yeni)


def _onizle(s: Session, yeni: list[dict]) -> dict:
    elle = _elle_kodlar(s)
    eski = [r for r in s.scalars(select(m.SmmAnaRecete)) if r.ana_kod not in elle]
    a, b = _imza(eski), _imza([x for x in yeni if x["ana_kod"] not in elle])
    ua, ub = _urun_imza(a), _urun_imza(b)
    eski_urun, yeni_urun = set(ua), set(ub)
    degisen = {k for k in eski_urun & yeni_urun if ua[k] != ub[k]}
    # elle değiştirilmiş ürünler korunur; Canias'taki yeni hâli bugünkünden farklıysa ayrıca gösterilir
    mevcut_elle = _imza([r for r in s.scalars(select(m.SmmAnaRecete).where(m.SmmAnaRecete.ana_kod.in_(elle)))]) if elle else {}
    yeni_elle = _imza([x for x in yeni if x["ana_kod"] in elle])
    adlar = {x["ana_kod"]: x["ana_ad"] for x in yeni}
    adlar.update({r.ana_kod: r.ana_ad for r in s.scalars(select(m.SmmAnaRecete).where(m.SmmAnaRecete.ana_kod.in_(elle)))} if elle else {})
    me, ye = _urun_imza(mevcut_elle), _urun_imza(yeni_elle)
    korunan = [{"ana_kod": kod, "ana_ad": adlar.get(kod), "caniasta_var": kod in ye, "canias_farkli": kod in ye and me.get(kod) != ye[kod]}
               for kod in sorted(elle)]
    return {**_ozet(yeni), "mevcut_urun": len(eski_urun) + len(elle), "eklenecek_urun": len(yeni_urun - eski_urun),
            "kalkacak_urun": len(eski_urun - yeni_urun), "degisecek_urun": len(degisen), "korunan": korunan,
            "ornek": [{"ana_kod": x["ana_kod"], "ana_ad": x["ana_ad"], "alternatif": x["alternatif"], "malzeme_kod": x["malzeme_kod"],
                       "malzeme_ad": x["malzeme_ad"], "miktar": str(x["miktar"]), "birim": x["birim"], "fire_orani": str(x["fire_orani"])}
                      for x in yeni[:8]]}


def yukle(s: Session, icerik: bytes, dosya_adi: str, kullanici: str = "sistem") -> dict:
    """Kalıcı reçeteleri dosyadakilerle değiştirir. Elle değiştirilmiş ürünler korunur; alternatif seçimleri korunur.
    Dosyanın değiştirilmemiş kopyası ayrıca saklanır ('Canias'a döndür' için)."""
    yeni = dosya_oku(icerik)
    sonuc = _onizle(s, yeni)
    elle = _elle_kodlar(s)
    s.execute(delete(m.SmmCaniasRecete))
    s.add_all(m.SmmCaniasRecete(olusturan=kullanici, **x) for x in yeni)
    s.execute(delete(m.SmmAnaRecete).where(m.SmmAnaRecete.ana_kod.not_in(elle)) if elle else delete(m.SmmAnaRecete))
    s.add_all(m.SmmAnaRecete(olusturan=kullanici, **x) for x in yeni if x["ana_kod"] not in elle)
    y = m.SmmReceteYukleme(kaynak_dosya=(dosya_adi or "")[-200:] or None, satir_sayisi=sonuc["satir_sayisi"], urun_sayisi=sonuc["urun_sayisi"],
                           olusturan=kullanici)
    s.add(y)
    s.flush()
    s.add(m.DegisiklikKaydi(tablo="smm_recete", kayit_id=y.id, islem="toplu_yukle", eski={"urun": sonuc["mevcut_urun"]}, kullanici=kullanici,
                            yeni={"dosya": y.kaynak_dosya, "urun": sonuc["urun_sayisi"], "satir": sonuc["satir_sayisi"],
                                  "eklenen": sonuc["eklenecek_urun"], "kalkan": sonuc["kalkacak_urun"], "degisen": sonuc["degisecek_urun"],
                                  "korunan_elle": len(sonuc["korunan"])}))
    s.flush()
    return decimal_str(sonuc)


# ---------------------------------------------------------------- okuma
def _secimler(s: Session) -> dict[str, str]:
    return dict(s.execute(select(m.SmmAlternatifSecimi.ana_kod, m.SmmAlternatifSecimi.alternatif)).all())


def hesap_gruplari(s: Session) -> dict[int, dict[str, list[HesapSatiri]]]:
    """Aşama hesabı için: aşama -> ürün -> seçili alternatifin satırları (seçim yoksa '00', o da yoksa ilk alternatif)."""
    secim = _secimler(s)
    tum = defaultdict(lambda: defaultdict(list))
    for r in s.scalars(select(m.SmmAnaRecete).order_by(m.SmmAnaRecete.ana_kod, m.SmmAnaRecete.alternatif, m.SmmAnaRecete.satir_no)):
        tum[r.ana_kod][r.alternatif].append(r)
    gruplar: dict[int, dict[str, list[HesapSatiri]]] = {20: {}, 40: {}, 50: {}}
    for kod, altlar in tum.items():
        alt = secim.get(kod)
        if alt not in altlar:
            alt = VARSAYILAN_ALTERNATIF if VARSAYILAN_ALTERNATIF in altlar else sorted(altlar)[0]
        satirlar = altlar[alt]
        gruplar.setdefault(satirlar[0].asama, {})[kod] = [
            HesapSatiri(asama=r.asama, ana_kod=r.ana_kod, ana_ad=r.ana_ad, malzeme_kod=r.malzeme_kod, malzeme_ad=r.malzeme_ad, miktar=r.miktar,
                        birim=r.birim, fire_orani=r.fire_orani) for r in satirlar]
    return gruplar


def son_yukleme(s: Session) -> dict | None:
    y = s.scalar(select(m.SmmReceteYukleme).order_by(m.SmmReceteYukleme.id.desc()))
    if y is None:
        return None
    return {"kaynak_dosya": y.kaynak_dosya, "satir_sayisi": y.satir_sayisi, "urun_sayisi": y.urun_sayisi, "olusturan": y.olusturan,
            "zaman": y.olusturma_zamani.isoformat() if y.olusturma_zamani else None}


def liste(s: Session, arama: str | None = None, asama: int | None = None) -> dict:
    secim = _secimler(s)
    urunler: dict[str, dict] = {}
    for kod, ad, alt, asm, n in s.execute(select(m.SmmAnaRecete.ana_kod, m.SmmAnaRecete.ana_ad, m.SmmAnaRecete.alternatif, m.SmmAnaRecete.asama,
                                                 func.count()).group_by(m.SmmAnaRecete.ana_kod, m.SmmAnaRecete.alternatif)):
        u = urunler.setdefault(kod, {"ana_kod": kod, "ana_ad": ad, "asama": asm, "alternatifler": [], "satir_sayisi": 0})
        u["alternatifler"].append(alt)
        if alt == secim.get(kod, VARSAYILAN_ALTERNATIF):
            u["satir_sayisi"] = n
    q = _tr((arama or "").strip())
    kayitlar = []
    sayac = defaultdict(int)
    elle = _elle_kodlar(s)
    for u in sorted(urunler.values(), key=lambda x: x["ana_kod"]):
        u["alternatifler"].sort()
        u["elle"] = u["ana_kod"] in elle
        u["secili_alternatif"] = secim.get(u["ana_kod"]) if secim.get(u["ana_kod"]) in u["alternatifler"] else (
            VARSAYILAN_ALTERNATIF if VARSAYILAN_ALTERNATIF in u["alternatifler"] else u["alternatifler"][0])
        sayac[u["asama"]] += 1
        if asama and u["asama"] != asama:
            continue
        if q and q not in _tr(u["ana_kod"]) and q not in _tr(u["ana_ad"]):
            continue
        kayitlar.append(u)
    return {"son_yukleme": son_yukleme(s), "asama_sayilari": {str(a): n for a, n in sorted(sayac.items())},
            "alternatifli_urun": sum(1 for u in urunler.values() if len(u["alternatifler"]) > 1), "elle_urun": len(elle & set(urunler)),
            "kayitlar": kayitlar}


def urun(s: Session, kod: str) -> dict:
    satirlar = list(s.scalars(select(m.SmmAnaRecete).where(m.SmmAnaRecete.ana_kod == kod)
                              .order_by(m.SmmAnaRecete.alternatif, m.SmmAnaRecete.satir_no)))
    if not satirlar:
        raise BulunamadiHatasi("reçete bulunamadı", {"kod": kod})
    altlar = defaultdict(list)
    for r in satirlar:
        altlar[r.alternatif].append({"id": r.id, "satir_no": r.satir_no, "kalem_tipi": r.kalem_tipi, "malzeme_kod": r.malzeme_kod,
                                     "malzeme_ad": r.malzeme_ad, "miktar": r.miktar, "birim": r.birim, "fire_orani": r.fire_orani})
    secili = _secimler(s).get(kod)
    if secili not in altlar:
        secili = VARSAYILAN_ALTERNATIF if VARSAYILAN_ALTERNATIF in altlar else sorted(altlar)[0]
    elle = s.scalar(select(m.SmmReceteElle).where(m.SmmReceteElle.ana_kod == kod))
    canias_var = s.scalar(select(m.SmmCaniasRecete.id).where(m.SmmCaniasRecete.ana_kod == kod).limit(1)) is not None
    return decimal_str({"ana_kod": kod, "ana_ad": satirlar[0].ana_ad, "asama": satirlar[0].asama, "kod_asamasi": asama_bul(kod),
                        "secili_alternatif": secili,
                        "elle": elle is not None, "elle_degistiren": elle.son_degistiren if elle else None, "canias_var": canias_var,
                        "alternatifler": [{"alternatif": a, "satirlar": x} for a, x in sorted(altlar.items())]})


# ---------------------------------------------------------------- elle düzenleme
ALTERNATIF_DESENI = re.compile(r"^\d{2}$")


def _isaretle(s: Session, kod: str, kullanici: str) -> None:
    x = s.scalar(select(m.SmmReceteElle).where(m.SmmReceteElle.ana_kod == kod))
    if x is None:
        s.add(m.SmmReceteElle(ana_kod=kod, son_degistiren=kullanici, olusturan=kullanici))
    else:
        x.son_degistiren = kullanici


def _gunluk(s: Session, kod: str, islem: str, eski: dict | None, yeni: dict | None, kullanici: str) -> None:
    s.add(m.DegisiklikKaydi(tablo="smm_recete", kayit_id=0, islem=islem, eski={"kod": kod, **(eski or {})} if eski is not None else None,
                            yeni={"kod": kod, **(yeni or {})} if yeni is not None else None, kullanici=kullanici))


def _satir_dogrula(ana_kod: str, malzeme_kod: str | None, miktar: Decimal | None, birim: str | None, fire_orani: Decimal | None) -> None:
    hatalar = {}
    if malzeme_kod is not None and (not malzeme_kod.strip() or malzeme_kod.strip() == ana_kod):
        hatalar["malzeme_kod"] = "malzeme kodu boş ya da ürünün kendisi olamaz"
    if miktar is not None and miktar <= 0:
        hatalar["miktar"] = "miktar sıfırdan büyük olmalı"
    if birim is not None and not birim.strip():
        hatalar["birim"] = "birim boş olamaz"
    if fire_orani is not None and not (0 <= fire_orani <= 10):
        hatalar["fire_orani"] = "fire oranı %0 ile %1000 arasında olmalı"
    if hatalar:
        raise DogrulamaHatasi("reçete satırı geçersiz", hatalar)


def _urun_satirlari(s: Session, kod: str) -> list[m.SmmAnaRecete]:
    return list(s.scalars(select(m.SmmAnaRecete).where(m.SmmAnaRecete.ana_kod == kod)))


def satir_ekle(s: Session, kod: str, alternatif: str, malzeme_kod: str, malzeme_ad: str | None, miktar: Decimal, birim: str,
               fire_orani: Decimal, kullanici: str = "sistem", ana_ad: str | None = None, yeni_urun: bool = False) -> dict:
    kod = kod.strip()
    var = _urun_satirlari(s, kod)
    if yeni_urun and var:
        raise CatismaHatasi("bu kodla reçete zaten var", {"kod": kod})
    if not yeni_urun and not var:
        raise BulunamadiHatasi("reçete bulunamadı", {"kod": kod})
    if not ALTERNATIF_DESENI.match(alternatif or ""):
        raise DogrulamaHatasi("alternatif iki haneli olmalı (00, 01…)", {"alternatif": alternatif})
    _satir_dogrula(kod, malzeme_kod, miktar, birim, fire_orani)
    no = max((r.satir_no for r in var if r.alternatif == alternatif), default=0) + 1
    r = m.SmmAnaRecete(ana_kod=kod, ana_ad=(var[0].ana_ad if var else ana_ad), alternatif=alternatif, satir_no=no, kalem_tipi=None,
                       asama=var[0].asama if var else asama_bul(kod), malzeme_kod=malzeme_kod.strip(), malzeme_ad=malzeme_ad,
                       miktar=miktar, birim=birim.strip(), fire_orani=fire_orani, olusturan=kullanici)
    s.add(r)
    _isaretle(s, kod, kullanici)
    _gunluk(s, kod, "ekle" if yeni_urun else "satir_ekle", None,
            {"alternatif": alternatif, "malzeme": r.malzeme_kod, "miktar": str(miktar), "birim": r.birim, "fire": str(fire_orani)}, kullanici)
    s.flush()
    return urun(s, kod)


def satir_guncelle(s: Session, satir_id: int, alanlar: dict, kullanici: str = "sistem") -> dict:
    r = s.get(m.SmmAnaRecete, satir_id)
    if r is None:
        raise BulunamadiHatasi("reçete satırı bulunamadı", {"id": satir_id})
    alanlar = {k: v for k, v in alanlar.items() if k in ("malzeme_kod", "malzeme_ad", "miktar", "birim", "fire_orani") and v is not None}
    _satir_dogrula(r.ana_kod, alanlar.get("malzeme_kod"), alanlar.get("miktar"), alanlar.get("birim"), alanlar.get("fire_orani"))
    eski = {k: str(getattr(r, k)) for k in alanlar}
    for k, v in alanlar.items():
        setattr(r, k, v.strip() if isinstance(v, str) else v)
    yeni = {k: str(getattr(r, k)) for k in alanlar}
    if eski != yeni:
        _isaretle(s, r.ana_kod, kullanici)
        _gunluk(s, r.ana_kod, "satir_guncelle", {"malzeme": r.malzeme_kod, **eski}, yeni, kullanici)
    s.flush()
    return urun(s, r.ana_kod)


def satir_sil(s: Session, satir_id: int, kullanici: str = "sistem") -> dict:
    r = s.get(m.SmmAnaRecete, satir_id)
    if r is None:
        raise BulunamadiHatasi("reçete satırı bulunamadı", {"id": satir_id})
    kod = r.ana_kod
    if len(_urun_satirlari(s, kod)) <= 1:
        raise DogrulamaHatasi("ürünün son reçete satırı silinemez")
    _gunluk(s, kod, "satir_sil", {"alternatif": r.alternatif, "malzeme": r.malzeme_kod, "miktar": str(r.miktar)}, None, kullanici)
    s.delete(r)
    _isaretle(s, kod, kullanici)
    s.flush()
    return urun(s, kod)


def alternatif_kopyala(s: Session, kod: str, kaynak: str, yeni: str, kullanici: str = "sistem") -> dict:
    satirlar = _urun_satirlari(s, kod)
    if not satirlar:
        raise BulunamadiHatasi("reçete bulunamadı", {"kod": kod})
    if not ALTERNATIF_DESENI.match(yeni or ""):
        raise DogrulamaHatasi("alternatif iki haneli olmalı (00, 01…)", {"alternatif": yeni})
    if any(r.alternatif == yeni for r in satirlar):
        raise CatismaHatasi("bu alternatif zaten var", {"alternatif": yeni})
    kaynaklar = [r for r in satirlar if r.alternatif == kaynak]
    if not kaynaklar:
        raise BulunamadiHatasi("kopyalanacak alternatif bulunamadı", {"alternatif": kaynak})
    for r in kaynaklar:
        s.add(m.SmmAnaRecete(ana_kod=r.ana_kod, ana_ad=r.ana_ad, alternatif=yeni, satir_no=r.satir_no, kalem_tipi=r.kalem_tipi, asama=r.asama,
                             malzeme_kod=r.malzeme_kod, malzeme_ad=r.malzeme_ad, miktar=r.miktar, birim=r.birim, fire_orani=r.fire_orani,
                             olusturan=kullanici))
    _isaretle(s, kod, kullanici)
    _gunluk(s, kod, "alternatif_kopyala", None, {"kaynak": kaynak, "yeni": yeni, "satir": len(kaynaklar)}, kullanici)
    s.flush()
    return urun(s, kod)


def asama_degistir(s: Session, kod: str, asama: int, kullanici: str = "sistem") -> dict:
    """Ürünün aşamasını (20 / 40 / 50) elle değiştirir; tüm alternatiflerine uygulanır. Varsayılan koddan gelir (bkz. asama_bul)."""
    if asama not in (20, 40, 50):
        raise DogrulamaHatasi("aşama 20, 40 ya da 50 olmalı", {"asama": asama})
    satirlar = _urun_satirlari(s, kod)
    if not satirlar:
        raise BulunamadiHatasi("reçete bulunamadı", {"kod": kod})
    eski = satirlar[0].asama
    if eski != asama:
        for r in satirlar:
            r.asama = asama
        _isaretle(s, kod, kullanici)
        _gunluk(s, kod, "asama", {"asama": eski}, {"asama": asama}, kullanici)
        s.flush()
    return urun(s, kod)


def caniasa_don(s: Session, kod: str, kullanici: str = "sistem") -> dict:
    """Elle değiştirilmiş ürünün reçetesini son yüklenen Canias dökümündeki hâline döndürür."""
    kaynak = list(s.scalars(select(m.SmmCaniasRecete).where(m.SmmCaniasRecete.ana_kod == kod)))
    if not kaynak:
        raise DogrulamaHatasi("bu ürün son Canias dökümünde yok; döndürülemez", {"kod": kod})
    s.execute(delete(m.SmmAnaRecete).where(m.SmmAnaRecete.ana_kod == kod))
    for r in kaynak:
        s.add(m.SmmAnaRecete(ana_kod=r.ana_kod, ana_ad=r.ana_ad, alternatif=r.alternatif, satir_no=r.satir_no, kalem_tipi=r.kalem_tipi,
                             asama=r.asama, malzeme_kod=r.malzeme_kod, malzeme_ad=r.malzeme_ad, miktar=r.miktar, birim=r.birim,
                             fire_orani=r.fire_orani, olusturan=kullanici))
    s.execute(delete(m.SmmReceteElle).where(m.SmmReceteElle.ana_kod == kod))
    _gunluk(s, kod, "canias_don", None, {"satir": len(kaynak)}, kullanici)
    s.flush()
    return urun(s, kod)


def malzeme_ara(s: Session, q: str, limit: int = 20) -> list[dict]:
    """Reçeteye eklenecek malzeme: reçetelerde geçen malzemeler ve son dönemin stok kartları (kod ya da ad)."""
    t = _tr((q or "").strip())
    if len(t) < 2:
        return []
    bulunan: dict[str, dict] = {}
    for kod, ad, birim in s.execute(select(m.SmmAnaRecete.malzeme_kod, m.SmmAnaRecete.malzeme_ad, m.SmmAnaRecete.birim).distinct()):
        if t in _tr(kod) or t in _tr(ad):
            bulunan.setdefault(kod, {"kod": kod, "ad": ad, "birim": birim})
    son = s.scalar(select(m.SmmDonem).order_by(m.SmmDonem.yil.desc(), m.SmmDonem.ay.desc()))
    if son is not None:
        for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == son.id)):
            if t in _tr(k.kod) or t in _tr(k.ad):
                bulunan.setdefault(k.kod, {"kod": k.kod, "ad": k.ad, "birim": k.birim})
    return sorted(bulunan.values(), key=lambda x: (not _tr(x["kod"]).startswith(t), x["kod"]))[:limit]


def alternatif_sec(s: Session, kod: str, alternatif: str, kullanici: str = "sistem") -> dict:
    var = set(s.scalars(select(m.SmmAnaRecete.alternatif).where(m.SmmAnaRecete.ana_kod == kod).distinct()))
    if not var:
        raise BulunamadiHatasi("reçete bulunamadı", {"kod": kod})
    if alternatif not in var:
        raise DogrulamaHatasi("bu üründe böyle bir alternatif yok", {"alternatif": alternatif, "var": sorted(var)})
    x = s.scalar(select(m.SmmAlternatifSecimi).where(m.SmmAlternatifSecimi.ana_kod == kod))
    eski = x.alternatif if x else VARSAYILAN_ALTERNATIF
    if x is None:
        s.add(m.SmmAlternatifSecimi(ana_kod=kod, alternatif=alternatif, olusturan=kullanici))
    else:
        x.alternatif = alternatif
    if eski != alternatif:
        s.add(m.DegisiklikKaydi(tablo="smm_recete", kayit_id=0, islem="alternatif", eski={"kod": kod, "alternatif": eski},
                                yeni={"kod": kod, "alternatif": alternatif}, kullanici=kullanici))
    s.flush()
    return urun(s, kod)


def kiyas(s: Session, donem_id: int) -> dict:
    """Kalıcı reçeteler (seçili alternatif) ile dönemin Excel'den gelen 20/40/50 reçetelerinin karşılaştırması."""
    d = donem_getir(s, donem_id)
    ana = hesap_gruplari(s)
    excel = defaultdict(lambda: defaultdict(list))
    for r in s.scalars(select(m.SmmReceteSatiri).where(m.SmmReceteSatiri.donem_id == d.id)):
        excel[r.asama][r.ana_kod].append(r)

    def topla(xs) -> dict[str, tuple[Decimal, Decimal]]:
        t: dict[str, list] = {}
        for x in xs:
            c = _d(x.miktar) / (_d(x.ana_miktar) or 1)
            e = t.setdefault(x.malzeme_kod, [SIFIR, _d(x.fire_orani)])
            e[0] += c
        return {k: (v[0], v[1]) for k, v in t.items()}

    sayac = defaultdict(lambda: defaultdict(int))
    farklar = []
    for asama in (20, 40, 50):
        kodlar = set(ana.get(asama, {})) | set(excel.get(asama, {}))
        for kod in sorted(kodlar):
            a, e = ana.get(asama, {}).get(kod), excel.get(asama, {}).get(kod)
            if a is None or e is None:
                durum = "yalniz_excel" if a is None else "yalniz_canias"
                ayrinti = None
            else:
                ta, te = topla(a), topla(e)
                if set(ta) != set(te):
                    durum = "malzeme"
                    ayrinti = {"yalniz_canias": sorted(set(ta) - set(te))[:5], "yalniz_excel": sorted(set(te) - set(ta))[:5]}
                elif any(abs(ta[k][0] - te[k][0]) > Decimal("0.000001") for k in ta):
                    durum, ayrinti = "miktar", {"malzemeler": [k for k in ta if abs(ta[k][0] - te[k][0]) > Decimal("0.000001")][:5]}
                elif any(abs(ta[k][1] - te[k][1]) > Decimal("0.0001") for k in ta):
                    durum, ayrinti = "fire", {"malzemeler": [k for k in ta if abs(ta[k][1] - te[k][1]) > Decimal("0.0001")][:5]}
                else:
                    durum, ayrinti = "ayni", None
            sayac[asama][durum] += 1
            if durum != "ayni":
                ad = (a or e)[0].ana_ad
                farklar.append({"asama": asama, "ana_kod": kod, "ana_ad": ad, "durum": durum, "ayrinti": ayrinti})
    return {"donem": d.id, "sayilar": {str(a): dict(v) for a, v in sayac.items()}, "farklar": farklar}
