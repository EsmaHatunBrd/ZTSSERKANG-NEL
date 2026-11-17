"""Müşavir Excel'i (SMM): yeminli mali müşavire giden aylık SMM Excel'inin AYNISI, rakamları uygulamadan.

Yöntem: SMM dönem Excel okuyucusunun (smm_servisi.excel_oku) TERSİ. Muhasebenin yüklediği kendi SMM Excel'i şablon olarak saklanır
(excel_sablon_deposu, tür "smm_donem", kapsam = dönem kimliği). Dışa aktarırken şablon formüllü açılır ve okuyucunun okuduğu GİRDİ
hücrelerine dönemin güncel verisi yazılır; formül, biçim, sayfa adı ve sırası değişmez, kapak / ek sayfa eklenmez.

Sayfa -> sütun (0 tabanlı) -> uygulamadaki kaynak:
    ENVANTER (3. satırdan)          A kod, B ad, C birim, D tür, E mizan kodu                    <- SmmKalem (envanterde olanlar)
    DBS                              A kod, B ad, C miktar, D tutar                               <- dbs_miktar / dbs_tutar
    HM-YM ALIŞ SATIŞ                 B kod, C ad, F birim, G giriş, K tutar, T "Alış"            <- alim_miktar / alim_tutar
                                     (satış ayrı satır) L çıkış, T "Satış"                        <- satis_miktar
    İADELER                          A kod, B ad, E birim, H miktar, I tutar                      <- iade_miktar / iade_tutar
    ÜRETİM                           A kod, B ad, O yıl içi toplam (O formülse dönemin ay sütunu) <- uretim_miktar
    DSS                              A kod, B ad, C sayım, E tutar (formül değilse)               <- sayim_miktar, DSS değerlemesi
    ŞAHİT                            A kod, B ad, J toplam miktar                                 <- sahit_miktar
    STOK MİZAN                       A hesap, B ad, G bakiye; J2 fiş tarihi                       <- excel_ozet.stok_mizan
    GİDER MİZAN (başlıktan sonra)    A hesap, B ad, G bakiye (3 haneli ana hesaplar)              <- excel_ozet.gider_mizan
    TABLO                            J1 finansman; B kod, C ad ve Excel'in kendi değerleri (D, H, O, U, V, W) formül değilse
    20 / 40 / 50 KOD                 1. satır dağıtım havuzları; A-H reçete satırı, fire sütunu; I/K/M elle çarpan/fiyat
                                     (standart formül ya da elle değer); ürün ilk satırında 40 AA / 50 T elle süre,
                                     U / W birim maliyet (formül değilse)                         <- dönemin hesapta kullandığı reçete
    51                               B mamul, C yarı mamul, D ad, J, L, M, P, Q, R, S süreler    <- SmmIscilik

Satır yerleşimi (her sayfada aynı): kayıt şablonda aynı anahtarla (kod; reçetede ana kod + malzeme) bir satırdaysa o satıra yazılır
(satır formülleri aynı koda denk gelir); yeni kayıtlar boşalan satırlara, sonra veri bloğunun altındaki boş satırlara yazılır. Satır
eklenmez / kaydırılmaz. Yer yetmezse kayıt şablonun son satırının altına yazılır, o satırın formülleri ve biçimi kopyalanır ve
`uyarilar`a "satır yetmedi" düşülür (toplam formüllerinin aralığı kontrol edilmeli).

Temizlik: veri bloğunda okuyucunun okuduğu sütunlar temizlenir; Canias'tan yapıştırılan rapor sayfalarında (DBS, alış-satış, iadeler,
üretim, DSS, şahit, mizanlar) veri satırlarındaki diğer sabit hücreler de (fiş no, tarih, birim fiyat, borç/alacak) temizlenir ki eski
dönemden iz kalmasın. FORMÜL hücresine hiçbir koşulda yazılmaz; yazılması gereken hücre formülse `uyarilar`a düşer."""
from __future__ import annotations

import calendar
import io
from collections import Counter, defaultdict
from copy import copy
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.formula.translate import Translator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..depo import modeller as m
from . import excel_sablon_deposu as esd
from .hatalar import BulunamadiHatasi, DogrulamaHatasi
from .smm_asama_servisi import ELLE_ALANLARI, VARSAYILAN_ANAHTARLAR, _Baglam, dagitim_anahtarlari
from .smm_servisi import (AY_ADLARI, ASAMA_SAYFALARI, BIRIM_SUTUNU, HAVUZ_HUCRELERI, MAKS_BAYT, OZEL_SUTUNLAR, SIFIR, URUN_ELLE_SUTUNLARI,
                          ZORUNLU_SAYFALAR, _d, _metin, _normal, _sablon_degil, _sayfa_bulucu, donem_adi, donem_getir, stok_hesabi)

TUR = "smm_donem"
UYGULAMA = "Fiyat Çalışması uygulaması"


# ---------------------------------------------------------------- şablon
def sablon_bul(s: Session, d: m.SmmDonem) -> tuple[m.ExcelSablonu | None, m.SmmDonem | None]:
    """Dönemin kendi şablonu; yoksa en yakın ÖNCEKİ dönemin şablonu (geriye doğru). (şablon, şablonun dönemi)."""
    y = esd.son(s, TUR, str(d.id))
    if y is not None:
        return y, d
    for o in s.scalars(select(m.SmmDonem).where((m.SmmDonem.yil * 12 + m.SmmDonem.ay) < d.yil * 12 + d.ay)
                       .order_by(m.SmmDonem.yil.desc(), m.SmmDonem.ay.desc())):
        y = esd.son(s, TUR, str(o.id))
        if y is not None:
            return y, o
    return None, None


def durum(s: Session, donem_id: int) -> dict:
    """Arayüz için: kullanılacak şablon (yoksa null), hangi dönemin şablonu, dönem kapatılmadıysa taslak."""
    d = donem_getir(s, donem_id)
    y, o = sablon_bul(s, d)
    return {"sablon": esd.ozet(y), "kaynak_donem": donem_adi(o) if o is not None else None,
            "kaynak_donem_id": o.id if o is not None else None, "kendi": o is not None and o.id == d.id, "taslak": not d.kilitli}


def _sablon_denetle(icerik: bytes) -> list[str]:
    """SMM dönem Excel'i mi (zorunlu sayfalar var, aylık kaynak şablonu değil)? Sayfa adlarını döner; değilse 422."""
    if len(icerik) > MAKS_BAYT:
        raise DogrulamaHatasi("dosya 60 MB'den büyük")
    try:
        wb = load_workbook(io.BytesIO(icerik), read_only=True)
    except Exception:   # bozuk / .xlsx olmayan dosya: hangi istisna olursa olsun anlaşılır red
        raise DogrulamaHatasi("dosya geçerli bir .xlsx değil (Excel'de .xlsx olarak kaydedip yeniden deneyin)", kod="gecersiz_dosya")
    try:
        _sablon_degil(wb)
        bul = _sayfa_bulucu(wb)
        eksik = [a for a in ZORUNLU_SAYFALAR if bul(a) is None]
        if eksik:
            raise DogrulamaHatasi(f"Bu dosya SMM dönem Excel'i değil: beklenen sayfalar yok ({', '.join(eksik)}). Dosyadaki sayfalar: "
                                  f"{', '.join(wb.sheetnames)}.", {"eksik_sayfalar": eksik, "sayfalar": list(wb.sheetnames)},
                                  kod="smm_excel_degil")
        return list(wb.sheetnames)
    finally:
        wb.close()


def sablon_onizle(s: Session, donem_id: int, icerik: bytes, dosya_adi: str) -> dict:
    """"Müşavir şablonu olarak yalnız sakla" önizlemesi (yazmaz): sayfa adları; dönemin mevcut şablonu varsa onun yerine geçeceği."""
    d = donem_getir(s, donem_id)
    sayfalar = _sablon_denetle(icerik)
    mevcut = esd.son(s, TUR, str(d.id))
    return {"dosya_adi": dosya_adi, "sayfalar": sayfalar, "donem": donem_adi(d), "mevcut": esd.ozet(mevcut)}


def sablon_sakla(s: Session, donem_id: int, icerik: bytes, dosya_adi: str, kullanici: str = "sistem") -> dict:
    """Dönem verisine dokunmadan yalnız şablonu kaydeder (SMM Excel'i değilse 422)."""
    d = donem_getir(s, donem_id)
    _sablon_denetle(icerik)
    y = esd.kaydet(s, TUR, str(d.id), dosya_adi, icerik, kullanici)
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="musavir_sablonu", eski=None, kullanici=kullanici,
                            yeni={"donem": donem_adi(d), "dosya": y.dosya_adi, "boyut": y.boyut}))
    s.flush()
    return durum(s, donem_id)


# ---------------------------------------------------------------- hücre yardımcıları
_SABIT = (str, int, float, bool, Decimal, datetime, date, type(None))


def _formul(c) -> bool:
    v = c.value
    return c.data_type == "f" or (isinstance(v, str) and v.startswith("=")) or not isinstance(v, _SABIT)


def _sayi(v):
    """Decimal -> Excel sayısı (tam sayıysa int)."""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() and abs(v) < Decimal(10) ** 15 else float(v)
    return v


@dataclass
class _Rapor:
    uyarilar: list[str] = field(default_factory=list)
    formul_atlanan: Counter = field(default_factory=Counter)   # (sayfa, sütun harfi) -> adet
    yazilan: Counter = field(default_factory=Counter)           # sayfa -> satır
    tasan: Counter = field(default_factory=Counter)             # sayfa -> şablonun altına yazılan satır
    temizlenen: Counter = field(default_factory=Counter)        # sayfa -> temizlenen satır

    def uyar(self, metin: str) -> None:
        if metin not in self.uyarilar:
            self.uyarilar.append(metin)


def _yaz(ws, r: int, i: int, v, rp: _Rapor, sessiz: bool = False) -> bool:
    """Hücreye sabit değer yazar; formül ya da birleştirilmiş hücreyse yazmaz (False)."""
    c = ws.cell(row=r, column=i + 1)
    if isinstance(c, MergedCell) or _formul(c):
        if not sessiz:
            rp.formul_atlanan[(ws.title, c.column_letter)] += 1
        return False
    c.value = _sayi(v)
    return True


def _temizle(ws, r: int, sutunlar, tum: bool) -> None:
    hucreler = ws[r] if tum else [ws.cell(row=r, column=i + 1) for i in sutunlar]
    for c in hucreler:
        if not isinstance(c, MergedCell) and not _formul(c) and c.value is not None:
            c.value = None


def _formulleri_kopyala(ws, kaynak: int, hedef: int, haric: set[int] = frozenset()) -> None:
    """Taşan satıra şablonun son veri satırının formüllerini (satıra göre kaydırarak) ve biçimini kopyalar."""
    for c in ws[kaynak]:
        if isinstance(c, MergedCell):
            continue
        h = ws.cell(row=hedef, column=c.column)
        if c.has_style:
            h._style = copy(c._style)
        if c.column - 1 in haric or not _formul(c) or not isinstance(c.value, str):
            continue
        try:
            h.value = Translator(c.value, origin=c.coordinate).translate_formula(h.coordinate)
        except Exception:   # çevrilemeyen formül (dış bağlantı vb.): kopyalanmaz
            pass
    if ws.row_dimensions[kaynak].height is not None:
        ws.row_dimensions[hedef].height = ws.row_dimensions[kaynak].height


@dataclass
class _Kayit:
    anahtar: object
    degerler: dict[int, object]
    veri: object = None


def _blok_yaz(ws, degerler: list[tuple], bas: int, anahtar, kayitlar: list[_Kayit], sutunlar: list[int], rapor_sayfasi: bool,
              rp: _Rapor, sessiz: set[int] = frozenset(), kopyalanmaz: set[int] = frozenset()) -> dict[int, _Kayit]:
    """Veri bloğunu yeniden yazar (bkz. modül açıklaması). `degerler`: şablonun önbellek değerleri (data_only) satır listesi;
    `anahtar(satır)`: satırın anahtarı ya da None. Dönüş: satır no -> kayıt."""
    son = bas - 1
    sablon: dict[object, list[int]] = defaultdict(list)
    for r in range(bas, len(degerler) + 1):
        a = anahtar(degerler[r - 1])
        if a is not None:
            son = r
            sablon[a].append(r)
    yerlesim: dict[int, _Kayit] = {}
    bekleyen = []
    for k in kayitlar:
        satirlar = sablon.get(k.anahtar)
        if satirlar:
            yerlesim[satirlar.pop(0)] = k
        else:
            bekleyen.append(k)
    for r in range(bas, son + 1):   # eski veri: okuyucunun sütunları (rapor sayfasında satırdaki tüm sabit hücreler)
        _temizle(ws, r, sutunlar, rapor_sayfasi)
        rp.temizlenen[ws.title] += 1 if r not in yerlesim and anahtar(degerler[r - 1]) is not None else 0
    hedef_formul = lambda r: any(_formul(ws.cell(row=r, column=i + 1)) for i in sutunlar if i not in sessiz)   # noqa: E731
    bos = [r for r in range(bas, max(ws.max_row, son) + 1) if r not in yerlesim and not hedef_formul(r)
           and (r <= son or all(ws.cell(row=r, column=i + 1).value is None for i in sutunlar))]
    sonraki = max(ws.max_row, son) + 1
    for k in bekleyen:
        if bos:
            r = bos.pop(0)
        else:
            r = sonraki
            sonraki += 1
            if son >= bas:
                _formulleri_kopyala(ws, son, r, kopyalanmaz)
            rp.tasan[ws.title] += 1
        yerlesim[r] = k
    for r, k in yerlesim.items():
        for i, v in k.degerler.items():
            _yaz(ws, r, i, v, rp, sessiz=i in sessiz)
        rp.yazilan[ws.title] += 1
    return yerlesim


def _degerler(wbv, ad: str) -> list[tuple]:
    return [tuple(r) for r in wbv[ad].iter_rows(values_only=True)]


def _hucre(r: tuple, i: int):
    return r[i] if len(r) > i else None


def _kod_anahtari(i: int):
    return lambda r: _metin(_hucre(r, i))


# ---------------------------------------------------------------- üretim
def smm_donem_excel_uret(s: Session, donem_id: int, simdi: datetime | None = None) -> tuple[bytes, str, list[str]]:
    """Dönemin müşavir Excel'i: (dosya baytları, dosya adı, uyarılar). Şablon yoksa 404 `sablon_yok`."""
    d = donem_getir(s, donem_id)
    y, kaynak = sablon_bul(s, d)
    if y is None:
        raise BulunamadiHatasi("Şablon yok: Dönemler › SMM Excel'inden yükle ile bir ayın Excel'ini yükleyin", {"donem_id": d.id},
                               kod="sablon_yok")
    simdi = simdi or datetime.now()
    rp = _Rapor()
    if kaynak.id != d.id:
        rp.uyar(f"Şablon: {kaynak and donem_adi(kaynak)} dosyası ({y.dosya_adi}); bu dönemin kendi Excel'i yüklenmedi.")
    wb = load_workbook(io.BytesIO(y.icerik), keep_vba=False)                       # formüllü: yazılacak kitap
    wbv = load_workbook(io.BytesIO(y.icerik), read_only=True, data_only=True)     # önbellek değerleri: şablon satırlarının anahtarları
    try:
        _yaz_hepsi(s, d, kaynak, wb, wbv, rp)
    finally:
        wbv.close()
    wb.calculation.fullCalcOnLoad = True   # Excel açınca bütün formülleri yeniden hesaplasın (openpyxl formül sonuçlarını yazmaz)
    taslak = "" if d.kilitli else " — TASLAK — dönem kapatılmadı"
    p = wb.properties
    p.subject = f"SMM {donem_adi(d)}"
    p.description = (f"Uygulamadan üretildi: {donem_adi(d)}, {simdi.strftime('%d.%m.%Y %H:%M')}{taslak}. "
                     f"Şablon: {y.dosya_adi}. Excel açıldığında toplamlar yeniden hesaplanır.")[:1000]
    p.keywords = "uygulamadan üretildi" + ("" if d.kilitli else ", TASLAK")
    p.lastModifiedBy = UYGULAMA
    p.modified = simdi
    b = io.BytesIO()
    wb.save(b)
    for (sayfa, sutun), n in sorted(rp.formul_atlanan.items()):
        rp.uyar(f"{sayfa}!{sutun}: {n} hücre formül; üzerine yazılmadı (Excel kendi hesabını kullanır).")
    for sayfa, n in rp.tasan.items():
        rp.uyar(f"{sayfa}: şablondaki satırlar yetmedi; {n} satır son satırın altına yazıldı (formül ve biçimi kopyalandı). "
                f"Toplam formüllerinin aralığını kontrol edin.")
    ad = f"{d.ay:02d}-{d.yil} SMM - uygulama {simdi.strftime('%d.%m.%Y')}.xlsx"
    return b.getvalue(), ad, rp.uyarilar


def _yaz_hepsi(s: Session, d: m.SmmDonem, kaynak: m.SmmDonem, wb, wbv, rp: _Rapor) -> None:
    bul = _sayfa_bulucu(wb)
    b = _Baglam(s, d)
    kalemler = sorted(b.kalem.values(), key=lambda k: k.kod)
    from .smm_ozet_servisi import _dss
    dss = _dss(b)

    def k_(i_kod: int, k: m.SmmKalem, sut: dict) -> _Kayit:
        return _Kayit(k.kod, {i_kod: k.kod, **sut}, k)

    # ENVANTER: kart bilgisi; P (aşama birim fiyatı) formülü korunur, yeni kartta aynı aşamaya bakan bir satırdan kopyalanır
    if (ad := bul("ENVANTER")):
        ws, deg = wb[ad], _degerler(wbv, ad)
        kay = [_Kayit(k.kod, {0: k.kod, 1: k.ad, 2: k.birim, 3: k.tur, 4: k.mizan_kodu}, k) for k in kalemler if k.envanterde]
        yer = _blok_yaz(ws, deg, 3, _kod_anahtari(0), kay, [0, 1, 2, 3, 4], False, rp, kopyalanmaz={15})
        _envanter_asamasi(ws, deg, yer, rp)
    elif any(k.envanterde for k in kalemler):
        rp.uyar("Şablonda ENVANTER sayfası yok; kart bilgisi (tür, mizan kodu) yazılamadı.")
    sayfalar = [
        ("DBS", 0, [0, 1, 2, 3], [k_(0, k, {1: k.ad, 2: k.dbs_miktar, 3: k.dbs_tutar}) for k in kalemler if k.dbs_miktar or k.dbs_tutar]),
        ("İADELER", 0, [0, 1, 4, 7, 8], [k_(0, k, {1: k.ad, 4: k.birim, 7: k.iade_miktar, 8: k.iade_tutar}) for k in kalemler
                                          if k.iade_miktar or k.iade_tutar]),
        ("DSS", 0, [0, 1, 2, 4], [k_(0, k, {1: k.ad, 2: k.sayim_miktar, 4: dss[k.kod]["tutar"]}) for k in kalemler if k.sayim_miktar]),
        ("ŞAHİT", 0, [0, 1, 9], [k_(0, k, {1: k.ad, 9: k.sahit_miktar}) for k in kalemler if k.sahit_miktar]),
    ]
    for sayfa, i_kod, sutunlar, kay in sayfalar:
        ad = bul(sayfa)
        if ad is None:
            if kay:
                rp.uyar(f"Şablonda {sayfa} sayfası yok; {len(kay)} kalemin verisi yazılamadı.")
            continue
        _blok_yaz(wb[ad], _degerler(wbv, ad), 3, _kod_anahtari(i_kod), kay, sutunlar, True, rp, sessiz={4} if sayfa == "DSS" else set())
    _alim_satis(wb, wbv, bul, kalemler, rp)
    _uretim(wb, wbv, bul, d, kalemler, rp)
    _tablo(wb, wbv, bul, d, b, kalemler, rp)
    _mizanlar(wb, wbv, bul, d, rp)
    _sureler(wb, wbv, bul, s, d, rp)
    _asamalar(wb, wbv, bul, d, b, rp)
    if kaynak.id != d.id:
        _baslik_donemi(wb, kaynak, d)


def _envanter_asamasi(ws, deg: list[tuple], yer: dict[int, _Kayit], rp: _Rapor) -> None:
    """ENVANTER!P hangi aşama sayfasına bakıyor (okuyucu uretim_asamasi'ni buradan çıkarır). Yeni karta, kartın aşamasına bakan bir
    şablon satırının P formülü kopyalanır; şablon satırındaki aşama uygulamadakinden farklıysa (formüle dokunulmaz) uyarı."""
    def asama(r: int) -> int | None:
        v = ws.cell(row=r, column=16).value
        p = v if isinstance(v, str) else ""
        return next((a for a, (ad, _) in ASAMA_SAYFALARI.items() if f"'{ad}'" in p), None)
    ornek: dict[int, int] = {}
    for r in range(3, len(deg) + 1):
        a = asama(r)
        if a is not None and a not in ornek:
            ornek[a] = r
    farkli = []
    for r, k in yer.items():
        istenen, mevcut = k.veri.uretim_asamasi, asama(r)
        if istenen == mevcut:
            continue
        c = ws.cell(row=r, column=16)
        if istenen is not None and mevcut is None and not _formul(c) and istenen in ornek:
            kc = ws.cell(row=ornek[istenen], column=16)
            c.value = Translator(kc.value, origin=kc.coordinate).translate_formula(c.coordinate)
        else:
            farkli.append(k.anahtar)
    if farkli:
        rp.uyar(f"ENVANTER!P: {len(farkli)} kartta Excel'in baktığı aşama sayfası uygulamadakinden farklı (formüle dokunulmadı). "
                f"Örnek: {', '.join(farkli[:5])}.")


def _alim_satis(wb, wbv, bul, kalemler: list[m.SmmKalem], rp: _Rapor) -> None:
    ad = bul("HM-YM ALIŞ SATIŞ")
    kay = []
    for k in kalemler:
        if k.alim_miktar or k.alim_tutar:
            kay.append(_Kayit((k.kod, False), {1: k.kod, 2: k.ad, 5: k.birim, 6: k.alim_miktar, 10: k.alim_tutar, 19: "Alış"}, k))
        if k.satis_miktar:
            kay.append(_Kayit((k.kod, True), {1: k.kod, 2: k.ad, 5: k.birim, 11: k.satis_miktar, 19: "Satış"}, k))
    if ad is None:
        return
    _blok_yaz(wb[ad], _degerler(wbv, ad), 3, lambda r: (_metin(_hucre(r, 1)), _metin(_hucre(r, 19)) == "Satış") if _metin(_hucre(r, 1)) else None,
              kay, [1, 2, 5, 6, 10, 11, 19], True, rp)


def _uretim(wb, wbv, bul, d: m.SmmDonem, kalemler: list[m.SmmKalem], rp: _Rapor) -> None:
    """ÜRETİM!O yıl içi toplam. O formülse (aylar toplamı) toplam dönemin ay sütununa (C=Ocak … N=Aralık) yazılır."""
    ad = bul("ÜRETİM")
    kay = [_Kayit(k.kod, {0: k.kod, 1: k.ad, 14: k.uretim_miktar}, k) for k in kalemler if k.uretim_miktar]
    if ad is None:
        if kay:
            rp.uyar(f"Şablonda ÜRETİM sayfası yok; {len(kay)} kalemin üretim miktarı yazılamadı.")
        return
    ws = wb[ad]
    yer = _blok_yaz(ws, _degerler(wbv, ad), 3, _kod_anahtari(0), kay, [0, 1, 14], True, rp, sessiz={14})
    ay_sutunu = 1 + d.ay   # 0 tabanlı: C (2) = Ocak
    aya = 0
    for r, k in yer.items():
        if _formul(ws.cell(row=r, column=15)):
            _yaz(ws, r, ay_sutunu, k.veri.uretim_miktar, rp)
            aya += 1
    if aya:
        rp.uyar(f"ÜRETİM!O formül (ayların toplamı): {aya} kalemin üretimi {AY_ADLARI[d.ay]} sütununa yazıldı; uygulamada aylık dağılım "
                f"tutulmadığı için diğer aylar boş.")


def _tablo(wb, wbv, bul, d: m.SmmDonem, b: _Baglam, kalemler: list[m.SmmKalem], rp: _Rapor) -> None:
    """TABLO: J1 finansman (okuyucu okur); satırlar B kod, C ad ve Excel'in kendi değerleri (formül değilse; karşılaştırma için)."""
    ad = bul("TABLO")
    if ad is None:
        return
    ws = wb[ad]
    if not _yaz(ws, 1, 9, d.finansman or SIFIR, rp, sessiz=True) and (d.finansman or SIFIR):
        rp.uyar("TABLO!J1 (finansman) formül; uygulamadaki finansman yazılamadı.")
    kay = []
    for k in kalemler:
        h = b.stok[k.kod]
        kay.append(_Kayit(k.kod, {1: k.kod, 2: k.ad, 3: k.dbs_miktar, 7: k.alim_tutar, 14: h["ortalama_fiyat"], 20: h["dss_tutar"],
                                  21: h["sarf_miktar"], 22: h["sarf_tutar"]}, k))
    deg = _degerler(wbv, ad)
    if any(_formul(ws.cell(row=r, column=2)) for r in range(3, ws.max_row + 1)):
        rp.uyar("TABLO!B kodları formülle geliyor; TABLO satırlarına dokunulmadı.")
        return
    _blok_yaz(ws, deg, 3, _kod_anahtari(1), kay, [1, 2, 3, 7, 14, 20, 21, 22], False, rp, sessiz={2, 3, 7, 14, 20, 21, 22})


def _mizanlar(wb, wbv, bul, d: m.SmmDonem, rp: _Rapor) -> None:
    from .smm_mizan_servisi import satirlar
    ad = bul("GİDER MİZAN")
    gider = [_Kayit(x["hesap"], {0: x["hesap"], 1: x["ad"], 6: x["bakiye"]}) for x in satirlar(d, "gider", isaretsiz=True)]
    if ad is not None:
        deg = _degerler(wbv, ad)
        # okuyucu 1. satırdan okur; veri bloğu hesap koduyla başlayan ilk satırdan (yoksa başlıktan sonra) başlar
        bas = next((n for n, r in enumerate(deg, start=1) if (_metin(_hucre(r, 0)) or "")[:1].isdigit()), 2)
        _blok_yaz(wb[ad], deg, bas, _kod_anahtari(0), gider, [0, 1, 6], True, rp)
    elif gider:
        rp.uyar("Şablonda GİDER MİZAN sayfası yok; gider mizanı yazılamadı.")
    ad = bul("STOK MİZAN")
    stok = [_Kayit(x["hesap"], {0: x["hesap"], 1: x["ad"], 6: x["bakiye"]}) for x in satirlar(d, "stok", isaretsiz=True)]
    if ad is not None:
        ws = wb[ad]
        _blok_yaz(ws, _degerler(wbv, ad), 3, _kod_anahtari(0), stok, [0, 1, 6], True, rp)
        tarih = (d.excel_ozet or {}).get("mizan_tarihi") or date(d.yil, d.ay, calendar.monthrange(d.yil, d.ay)[1]).strftime("%d.%m.%Y")
        _yaz(ws, 2, 9, tarih, rp)   # J2: fiş tarihi
    elif stok:
        rp.uyar("Şablonda STOK MİZAN sayfası yok; stok mizanı yazılamadı.")


_SURE_SUTUNLARI = {9: "vardiya_uretim", 11: "dolum_isci", 12: "etiket_isci", 15: "dolum_sn", 16: "dolum_adam_sn", 17: "etiket_sn",
                   18: "etiket_adam_sn"}


def _sureler(wb, wbv, bul, s: Session, d: m.SmmDonem, rp: _Rapor) -> None:
    ad = bul("51")
    kay = [_Kayit((x.mamul_kod, x.yari_mamul_kod), {1: x.mamul_kod, 2: x.yari_mamul_kod, 3: x.ad, **{i: getattr(x, a) for i, a in _SURE_SUTUNLARI.items()}}, x)
           for x in s.scalars(select(m.SmmIscilik).where(m.SmmIscilik.donem_id == d.id).order_by(m.SmmIscilik.id))]
    if ad is None:
        if kay:
            rp.uyar("Şablonda 51 sayfası yok; üretim süreleri yazılamadı.")
        return
    _blok_yaz(wb[ad], _degerler(wbv, ad), 3,
              lambda r: (_metin(_hucre(r, 1)), _metin(_hucre(r, 2))) if (_metin(_hucre(r, 1)) or _metin(_hucre(r, 2))) else None,
              kay, [1, 2, 3, *_SURE_SUTUNLARI], False, rp)


def _asamalar(wb, wbv, bul, d: m.SmmDonem, b: _Baglam, rp: _Rapor) -> None:
    """20 / 40 / 50 KOD: dağıtım havuzları (1. satır), dönemin hesapta kullandığı reçete satırları, elle çarpan / fiyat ve ürün süreleri."""
    if (d.recete_kaynagi or "excel") == "ana":
        rp.uyar("Aşama sayfalarına (20/40/50 KOD) dönemin kullandığı kalıcı Canias reçeteleri (seçili alternatif) yazıldı.")
    anahtar = dagitim_anahtarlari(d)
    farkli = [k for k, v in anahtar.items() if v != VARSAYILAN_ANAHTARLAR[k]]
    if farkli:
        rp.uyar(f"Dağıtım anahtarı uygulamada değiştirilmiş ({', '.join(farkli)}); Excel formülleri kendi anahtarıyla dağıtır.")
    havuz = d.dagitim or {}
    elle_tum = d.asama_elle or {}
    for asama, (sayfa, fire_i) in ASAMA_SAYFALARI.items():
        gruplar = b.gruplar.get(asama, {})
        elle = elle_tum.get(str(asama), {})
        ekran_elle = sorted(kod for kod, e in elle.items() if set(e) & set(ELLE_ALANLARI))
        if ekran_elle:
            rp.uyar(f"{sayfa}: {len(ekran_elle)} üründe ekrandan girilmiş elle değer (malzeme / işçilik / GÜG / fire / birim maliyet) "
                    f"Excel'de karşılığı olmadığı için yazılmadı. Örnek: {', '.join(ekran_elle[:5])}.")
        ad = bul(sayfa)
        if ad is None:
            if gruplar:
                rp.uyar(f"Şablonda {sayfa} sayfası yok; {len(gruplar)} ürünün reçetesi yazılamadı.")
            continue
        ws, deg = wb[ad], _degerler(wbv, ad)
        for anahtar_, i in HAVUZ_HUCRELERI[asama].items():
            if anahtar_ in havuz and not _yaz(ws, 1, i, _d(havuz.get(anahtar_)), rp, sessiz=True):
                rp.uyar(f"{ad} 1. satır ({ws.cell(row=1, column=i + 1).coordinate}) formül; dağıtım havuzu {anahtar_} yazılamadı.")
        formuller = [tuple(c.value for c in row) for row in ws.iter_rows(min_row=3)]
        std, std_kaynak = _standartlar(deg[2:], formuller, asama)
        kay = []
        for ana, satirlar in gruplar.items():
            for x in satirlar:
                ozel = x.ozel or {}
                mal = f"{x.malzeme_kod} " if "kod_bosluklu" in ozel else x.malzeme_kod
                kay.append(_Kayit((ana, x.malzeme_kod), {0: ana, 1: x.ana_ad, 2: x.ana_miktar, 3: x.ana_birim, 4: mal, 5: x.malzeme_ad,
                                                         6: x.miktar, 7: x.birim, fire_i: x.fire_orani}, x))
        anahtar_fn = lambda r: (_metin(_hucre(r, 0)), _metin(_hucre(r, 4))) if _metin(_hucre(r, 0)) and _metin(_hucre(r, 4)) else None  # noqa: E731
        yer = _blok_yaz(ws, deg, 3, anahtar_fn, kay, [0, 1, 2, 3, 4, 5, 6, 7, fire_i], False, rp)
        _asama_ozel(ws, yer, std, std_kaynak, asama, elle, b, rp)


def _standartlar(degerler: list[tuple], formuller: list[tuple], asama: int) -> tuple[dict[int, str], dict[int, int]]:
    """Sütun -> sayfanın standart formülü (normalleştirilmiş) ve onu taşıyan bir şablon satırı. I/K/M reçete satırlarında, AA/T ürün
    ilk satırlarında en sık görülen formül (okuyucu da elle / standart dışı ayrımını böyle yapar)."""
    sayac: dict[int, Counter] = defaultdict(Counter)
    ornek: dict[tuple[int, str], int] = {}
    onceki = None
    urun_sut = set(URUN_ELLE_SUTUNLARI.get(asama, {}).values())
    for n, f in enumerate(formuller):
        r = degerler[n] if n < len(degerler) else ()
        satir_no = n + 3
        ana = _metin(_hucre(r, 0))
        sutunlar = list(OZEL_SUTUNLAR.values()) if _metin(_hucre(r, 4)) else []
        if ana and ana != onceki:
            sutunlar += list(urun_sut)
        onceki = ana
        for i in sutunlar:
            nf = _normal(_hucre(f, i), satir_no)
            if nf:
                sayac[i][nf] += 1
                ornek.setdefault((i, nf), satir_no)
    std = {i: c.most_common(1)[0][0] for i, c in sayac.items() if c}
    return std, {i: ornek[(i, nf)] for i, nf in std.items()}


def _asama_ozel(ws, yer: dict[int, _Kayit], std: dict[int, str], std_kaynak: dict[int, int], asama: int, elle: dict, b: _Baglam,
                rp: _Rapor) -> None:
    """Reçete satırında I (çarpan), K (HM fiyatı), M (YM fiyatı): uygulamada elle değer varsa o değer; yoksa sayfanın standart formülü
    (şablonda o satırda eski elle değer kaldıysa standart formül geri yazılır). Ürün ilk satırında 40 AA / 50 T elle süre ve U / W birim
    maliyet (formül değilse). Formül hücresine yazılmaz; uygulamanın istediğiyle uyuşmayan formül uyarıya düşer."""
    sayfa = ws.title
    uyusmaz = Counter()

    def standart_yaz(r: int, i: int) -> bool:
        if i not in std:
            return False
        kc = ws.cell(row=std_kaynak[i], column=i + 1)
        c = ws.cell(row=r, column=i + 1)
        if isinstance(c, MergedCell):
            return False
        c.value = Translator(kc.value, origin=kc.coordinate).translate_formula(c.coordinate)
        return True

    def hucre_ayarla(r: int, i: int, istenen) -> None:
        """istenen: None = standart formül; Decimal = elle değer; ('bolen', N) = standart / N."""
        c = ws.cell(row=r, column=i + 1)
        if isinstance(c, MergedCell):
            return
        if i not in std:
            # sütunda formül yok: okuyucu bu sütunda elle / standart ayrımı yapmaz (değer okunmaz); uygulamada elle değer varsa söylenir
            if istenen is not None:
                uyusmaz[c.column_letter] += 1
            return
        if _formul(c):
            nf = _normal(c.value, r) if isinstance(c.value, str) else None
            if istenen is None and nf == std[i]:
                return
            if isinstance(istenen, tuple) and nf and nf.endswith(f"/{istenen[1]}"):
                return
            uyusmaz[c.column_letter] += 1   # formüle dokunulmaz
            return
        if istenen is None:
            standart_yaz(r, i)   # boş ya da eski elle değer: standart formül
            return
        if isinstance(istenen, tuple):
            kc = ws.cell(row=std_kaynak[i], column=i + 1)
            f = Translator(kc.value, origin=kc.coordinate).translate_formula(c.coordinate)
            c.value = f"=({f[1:]})/{istenen[1]}"
            return
        c.value = _sayi(_d(istenen))

    for r in sorted(yer):
        x = yer[r].veri
        ozel = x.ozel or {}
        for alan, i in OZEL_SUTUNLAR.items():
            if alan in ozel:
                hucre_ayarla(r, i, _d(ozel[alan]))
            elif alan == "hm" and "hm_bolen" in ozel:
                hucre_ayarla(r, i, ("bolen", ozel["hm_bolen"]))
            elif alan == "carpan" and ws.cell(row=r, column=i + 1).value is None:
                continue   # boş çarpan okuyucu için standart (miktar / ana miktar)
            else:
                hucre_ayarla(r, i, None)
    # ürün ilk satırları (sayfadaki son sıraya göre): elle süre ve birim maliyet
    ilk: dict[str, int] = {}
    onceki = None
    for r in range(3, ws.max_row + 1):
        ana = _metin(ws.cell(row=r, column=1).value)
        if ana and ana != onceki and r in yer:
            ilk.setdefault(ana, r)
        onceki = ana
    for ana, r in ilk.items():
        e = elle.get(ana, {})
        for alan, i in URUN_ELLE_SUTUNLARI.get(asama, {}).items():
            hucre_ayarla(r, i, _d(e[alan]) if alan in e else None)
        _yaz(ws, r, BIRIM_SUTUNU[asama], b.birim(asama, ana), rp, sessiz=True)
    bitisik_degil = sorted({yer[r].anahtar[0] for r in yer} - set(ilk)) + sorted(
        a for a in ilk if sum(1 for r in yer if yer[r].anahtar[0] == a) != _ardisik(ws, ilk[a], a))
    if bitisik_degil:
        rp.uyar(f"{sayfa}: {len(bitisik_degil)} ürünün reçete satırları bitişik değil (yeni satırlar boş satırlara yazıldı); Excel'in grup "
                f"formüllerini kontrol edin. Örnek: {', '.join(bitisik_degil[:5])}.")
    for sut, n in sorted(uyusmaz.items()):
        rp.uyar(f"{sayfa}!{sut}: {n} satırda uygulamadaki elle / standart değer formülle uyuşmuyor; formüle dokunulmadı.")


def _ardisik(ws, r: int, ana: str) -> int:
    n = 0
    while _metin(ws.cell(row=r + n, column=1).value) == ana:
        n += 1
    return n


def _baslik_donemi(wb, kaynak: m.SmmDonem, d: m.SmmDonem) -> None:
    """Şablon başka ayın dosyasıysa üst iki satırdaki sabit başlık metinlerinde '<ay> <yıl>' yeni dönemle değiştirilir
    (ör. 'ENVANTER · Ekim 2026' -> 'ENVANTER · Kasım 2026'). Sayı / tarih hücrelerine ve formüllere dokunulmaz."""
    eski, yeni = donem_adi(kaynak), donem_adi(d)
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=1, max_row=2):
            for c in row:
                if isinstance(c, MergedCell) or _formul(c) or not isinstance(c.value, str):
                    continue
                if eski in c.value:
                    c.value = c.value.replace(eski, yeni)
                elif eski.upper() in c.value:
                    c.value = c.value.replace(eski.upper(), yeni.upper())
