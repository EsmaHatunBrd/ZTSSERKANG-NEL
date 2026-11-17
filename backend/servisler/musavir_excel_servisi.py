"""Müşavir Excel'i — Fiyat Çalışması kitabı: muhasebenin kendi yüklediği kitap (şablon) aynen alınır, okuyucunun
(fiyat_motoru.excel_okuyucu + import_servisi) okuduğu her GİRDİ hücresine senaryonun güncel değeri yazılır.

Kurallar (okuyucunun tersi):
- Sabit hücre: uygulamadaki değer farklıysa yazılır (aynıysa dokunulmaz; biçim korunur).
- Formül hücresi: üzerine YAZILMAZ. Formülün sonucu bilinebiliyorsa (reçete K = I/(1-J), M = S.ALMA BF araması, başka hücreye düz
  başvuru) önbellek değeri olarak o yazılır; uygulamadaki değer formülün vereceğinden farklıysa `uyarilar`a düşer.
  Gider Dağıtım toplamlarındaki "=taban*çarpan" sabit ifadesi girdi sayılır ve uygulamanın taban/çarpanlarıyla yeniden yazılır.
- Uygulamada olup kitapta olmayan ürün/malzeme/satır için yeni sayfa ya da satır açılmaz (uyarı); kitapta olup uygulamada olmayana dokunulmaz.
- Kapak/ek sayfa eklenmez; yalnız dosya özelliklerine "uygulamadan üretildi" notu yazılır. Excel açılınca tüm formüller yeniden hesaplanır
  (fullCalcOnLoad); okuyucunun okuduğu formül hücrelerine önbellek değeri yazıldığı için dosya uygulamaya geri yüklenince aynı girdiler okunur.

Kullanım:
    fiyat_kitabi_uret(s, senaryo_id, tarih) -> bytes
    fiyat_kitabi_hazirla(s, senaryo_id, tarih) -> MusavirSonucu (icerik, uyarilar, degisen_hucre, dosya_adi)
"""
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape, unescape

import openpyxl
from openpyxl.cell.cell import MergedCell
from sqlalchemy import select
from sqlalchemy.orm import Session

from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.fire import brut_miktar
from fiyat_motoru.modeller import GIDER_ELLE_ALANLARI, GIDER_KALEMLERI
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import excel_sablon_deposu as depo
from . import fiyat_servisi, gider_servisi, hesap_servisi, kapasite_servisi, parametre_servisi
from .hatalar import BulunamadiHatasi, DogrulamaHatasi, ServisHatasi

TUR = "fiyat_kitabi"
SABLON_YOK = "sablon_yok"
SABLON_YOK_MESAJI = "Bu çalışma için şablon yok: Veri Aktar › Tüm çalışma kitabı ile kitabınızı yükleyin"
AZAMI_UYARI = 300
_YOK = object()

SAYFA_SALMA = ("S.ALMA BF", ("SALMA BF", "Satın Alma"))
SAYFA_GIDER = ("Gider Dağıtım", ("Gider Dagitim", "Gider Dağıtımı"))
SAYFA_URETIM = (eo.URETIM_ADETLERI_SAYFA, ("Uretim Adetleri",))
# Gider Dağıtım pay blokları: (havuz kodu, satır aralığı, ad sütunu) — excel_okuyucu.havuzlari_oku ile aynı.
PAY_BLOKLARI = (("mal_kabul_iscilik", range(7, 10), "C"), ("mal_kabul_gug", range(21, 24), "C"), ("elektrik", range(30, 38), "A"),
                ("dogalgaz", range(41, 49), "A"), ("amortisman", range(52, 60), "A"))
SANIYE_HUCRELERI = {"dolum_iscilik": "F4", "etiket_iscilik": "F13", "endirekt_iscilik": "F18", "diger_gug": "F27"}
URETIM_SUTUNLARI = dict(zip(kapasite_servisi.SAYISAL_ALANLAR, "CDEFGH"))
# Okuyucunun sabit kabul ettiği parametreler (Excel'de hücresi yok): uygulamada farklıysa kitaba yazılamaz.
OKUYUCU_SABITLERI = {"satis_kar": Decimal("0.2"), "vardiya_saati": Decimal("7.5")}


# ---------------------------------------------------------------- şablon
def sablon(s: Session, senaryo_id: int) -> m.ExcelSablonu | None:
    return depo.son(s, TUR, str(senaryo_id))


def sablon_ozeti(s: Session, senaryo_id: int) -> dict | None:
    return depo.ozet(sablon(s, senaryo_id))


def sablon_sakla(s: Session, senaryo_id: int, dosya_adi: str | None, icerik: bytes, kullanici: str = "sistem") -> dict:
    y = depo.kaydet(s, TUR, str(senaryo_id), dosya_adi or "fiyat-calismasi.xlsx", icerik, kullanici)
    return depo.ozet(y)


def sablon_sil(s: Session, senaryo_id: int) -> None:
    depo.sil(s, TUR, str(senaryo_id))


def sablon_onizle(dosya_yolu: Path) -> dict:
    """Yalnız saklamadan önce: kitap mı (tam_kitap_ac'ın denetimi: S.ALMA BF, Gider Dağıtım, en az bir ürün sayfası)?
    Dönüş: {"sayfalar": [...], "urun_sayfasi": n}. Kitap değilse 422 (eksik_sayfa / yanlis_sablon / desteklenmeyen_dosya)."""
    from .import_servisi import tam_kitap_ac
    try:
        _, wb_v = tam_kitap_ac(Path(dosya_yolu))
    except DogrulamaHatasi:
        raise
    except Exception as e:   # noqa: BLE001 — bozuk dosya: anlaşılır red
        raise DogrulamaHatasi(f"Dosya Fiyat Çalışması kitabı olarak okunamadı: {e}", kod="desteklenmeyen_dosya")
    urun = [a for a in eo.urun_sayfalarini_listele(wb_v) if "(2)" not in a]
    return {"sayfalar": list(wb_v.sheetnames), "urun_sayfasi": len(urun)}


# ---------------------------------------------------------------- yardımcılar
def _dec(v) -> Decimal | None:
    if v is None or v == "" or isinstance(v, bool):
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v).strip()) if isinstance(v, str) else Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _ayni(mevcut, yeni) -> bool:
    """Okuyucunun gözünde aynı mı: sayılarda boş = 0 ve 1e-12 göreli tolerans; metinde kırpılmış eşitlik."""
    if isinstance(yeni, (Decimal, int, float)) and not isinstance(yeni, bool):
        a = SIFIR if mevcut in (None, "") else _dec(mevcut)
        if a is None:
            return False
        b = Decimal(str(yeni)) if not isinstance(yeni, Decimal) else yeni
        return abs(a - b) <= Decimal("1e-12") * max(Decimal(1), abs(b))
    a = "" if mevcut is None else str(mevcut).strip()
    b = "" if yeni is None else str(yeni).strip()
    return a == b


def _hucre_degeri(v):
    """Decimal -> Excel sayısı (tam sayıysa int, değilse float; Excel zaten çift duyarlıklı saklar)."""
    if isinstance(v, Decimal):
        if v == v.to_integral_value() and abs(v) < Decimal("1e15"):
            return int(v)
        return float(v)
    return v


def _sayi_metni(d: Decimal) -> str:
    """Formül içine sayı: üssüz, gereksiz sıfırsız ('6000000', '1.35')."""
    t = format(Decimal(d).normalize(), "f")
    return t


def _goster(v) -> str:
    if isinstance(v, Decimal):
        return _sayi_metni(v).replace(".", ",")
    if isinstance(v, float):
        return _sayi_metni(Decimal(str(v))).replace(".", ",")
    return "boş" if v in (None, "") else str(v)


_REFERANS = re.compile(r"^=\+?(?:(?:'(?P<q>(?:[^']|'')+)'|(?P<u>[^'!=+\-*/()&,;<>\" ]+))!)?\$?(?P<c>[A-Z]{1,3})\$?(?P<r>\d+)$")


@dataclass
class MusavirSonucu:
    icerik: bytes
    dosya_adi: str
    uyarilar: list[str] = field(default_factory=list)
    degisen_hucre: int = 0
    urun_sayfasi: int = 0
    yazilan_urun: int = 0


class _Yazici:
    """Hücre yazımı + formül önbellekleri + uyarılar."""

    def __init__(self, wb_f, wb_v):
        self.wb_f, self.wb_v = wb_f, wb_v
        self.yazilan: dict[tuple[str, str], object] = {}
        self.onbellek: dict[tuple[str, str], object] = {}
        self.bekleyen: list[tuple[str, str, object, str]] = []
        self.uyarilar: list[str] = []
        self.degisen = 0

    def uyari(self, metin: str) -> None:
        if metin not in self.uyarilar:
            self.uyarilar.append(metin)

    def deger(self, sayfa: str, adres: str):
        """Hücrenin dosyadaki son hali: yazılan sabit > önbellek (formül sonucu) > şablondaki önbellek değeri."""
        k = (sayfa, adres)
        if k in self.yazilan:
            return self.yazilan[k]
        if k in self.onbellek:
            return self.onbellek[k]
        try:
            return self.wb_v[sayfa][adres].value
        except (KeyError, ValueError):
            return None

    def yaz(self, ws, adres: str, deger, aciklama: str, formul_degeri=_YOK) -> None:
        """Sabitse ve farklıysa yazar. Formülse dokunmaz: `formul_degeri` biliniyorsa önbelleğe o yazılır (None: uygulama değeri),
        bilinmiyorsa sonraya (düz başvuru çözümü) bırakılır."""
        h = ws[adres]
        mevcut = h.value
        anahtar = (ws.title, adres)
        if eo.formul_mu(mevcut):
            if formul_degeri is _YOK:
                self.bekleyen.append((ws.title, adres, deger, aciklama))
                return
            sonuc = deger if formul_degeri is None else formul_degeri
            self.onbellek[anahtar] = sonuc
            if not _ayni(sonuc, deger):
                self.uyari(f"{ws.title}!{adres} ({aciklama}): uygulamada {_goster(deger)}, Excel'de formül var ({_goster(sonuc)}); "
                           "formüle dokunulmadı.")
            return
        if _ayni(mevcut, deger):
            return
        if isinstance(h, MergedCell):
            self.uyari(f"{ws.title}!{adres} ({aciklama}): birleştirilmiş hücre; yazılmadı.")
            return
        h.value = _hucre_degeri(deger)
        self.yazilan[anahtar] = h.value
        self.degisen += 1

    def formul_yaz(self, ws, adres: str, formul: str, sonuc) -> None:
        h = ws[adres]
        if str(h.value).replace(" ", "") != formul:
            h.value = formul
            self.degisen += 1
        self.onbellek[(ws.title, adres)] = _hucre_degeri(sonuc)

    def _referans(self, sayfa: str, formul) -> object:
        """Düz başvuru formülünün (='001'!F150, =K17) değeri; başvuru değilse _YOK."""
        if not isinstance(formul, str):
            return _YOK
        e = _REFERANS.match(formul.replace(" ", ""))
        if e is None:
            return _YOK
        hedef = e.group("q").replace("''", "'") if e.group("q") else (e.group("u") or sayfa)
        if hedef not in self.wb_f.sheetnames:
            return _YOK
        return self.deger(hedef, f"{e.group('c')}{e.group('r')}")

    def bekleyenleri_coz(self) -> None:
        for _ in range(3):   # başvuru zinciri (A -> B -> C) için birkaç tur
            for sayfa, adres, deger, aciklama in self.bekleyen:
                ref = self._referans(sayfa, self.wb_f[sayfa][adres].value)
                if ref is not _YOK:
                    self.onbellek[(sayfa, adres)] = ref
        for sayfa, adres, deger, aciklama in self.bekleyen:
            ref = self._referans(sayfa, self.wb_f[sayfa][adres].value)
            if ref is _YOK:
                eski = self.wb_v[sayfa][adres].value
                self.onbellek[(sayfa, adres)] = eski if eski is not None else _hucre_degeri(deger)
                sonuc = eski
            else:
                sonuc = ref
            if not _ayni(sonuc, deger):
                self.uyari(f"{sayfa}!{adres} ({aciklama}): uygulamada {_goster(deger)}, Excel'de formül var ({_goster(sonuc)}); "
                           "formüle dokunulmadı, Excel açılınca formülün sonucu görünür.")


# ---------------------------------------------------------------- sayfa yazıcıları
def _sayfa(wb, ad_esler):
    from .yukleme_guvenligi import sayfa_bul
    ad, esler = ad_esler
    return wb[ad] if ad in wb.sheetnames else sayfa_bul(wb, ad, esler)


def _salma_yaz(y: _Yazici, ws, malzemeler: dict, kullanilan: set[str]) -> dict[str, Decimal]:
    """S.ALMA BF: A kod, B ad, C tip, D birim, E para birimi, F fiyat, G Z/S, I revize. Dönüş: kod -> dosyadaki son F (M aramaları için)."""
    ws_v = y.wb_v[ws.title]
    gorulen: set[str] = set()
    fiyatlar: dict[str, Decimal] = {}
    for r in range(2, ws.max_row + 1):
        kod = ws_v[f"A{r}"].value
        if kod is None or not str(kod).strip():
            continue
        kod = str(kod).strip()
        gorulen.add(kod)
        mz = malzemeler.get(kod)
        if mz is not None:
            fiyat = mz.fiyat if mz.fiyat != SIFIR else None
            y.yaz(ws, f"B{r}", mz.ad or "", f"{kod} açıklama")
            y.yaz(ws, f"C{r}", mz.tip, f"{kod} malzeme tipi")
            y.yaz(ws, f"D{r}", mz.birim, f"{kod} stok birimi")
            y.yaz(ws, f"E{r}", mz.para_birimi, f"{kod} para birimi")
            y.yaz(ws, f"F{r}", fiyat, f"{kod} bütçe birim fiyatı")   # fiyat kaydı yoksa boş (okuyucu 0 okur)
            y.yaz(ws, f"G{r}", mz.zs, f"{kod} Z/S")
            i_h = ws[f"I{r}"].value
            if i_h not in (None, ""):   # revize sütunu doluysa güncel fiyatla aynı yazılır (okuyucu: I = F ise revize yok)
                y.yaz(ws, f"I{r}", fiyat, f"{kod} revize fiyat")
        f = y.deger(ws.title, f"F{r}")
        fiyatlar[kod] = _dec(f) or SIFIR
    eksik = sorted(k for k in kullanilan if k not in gorulen and k in malzemeler and malzemeler[k].fiyat != SIFIR)
    for kod in eksik:
        y.uyari(f"S.ALMA BF: {kod} uygulamada var, kitapta satırı yok; yeni satır açılmadı (ürün sayfalarında bu malzemenin fiyatı 0 görünür).")
    return fiyatlar


def _gider_yaz(y: _Yazici, ws, havuzlar: dict, ambalajlar: list) -> None:
    from .import_servisi import HAVUZ_ESLEME
    ws_v = y.wb_v[ws.title]
    alan_kod = {toplam_alani: kod for kod, _, toplam_alani, *_ in HAVUZ_ESLEME}
    for alan, adres in eo.HAVUZ_TOPLAM_HUCRELERI.items():
        kod = alan_kod[alan]
        h = havuzlar.get(kod)
        if h is None:
            y.uyari(f"Gider Dağıtım: {kod} havuzu uygulamada yok; {adres} değiştirilmedi.")
            continue
        mevcut = ws[adres].value
        toplam = h.toplam_tutar
        _, carpanlar = gider_servisi.carpan_degerleri(h)
        if eo.formul_mu(mevcut) and eo.taban_carpan_coz(mevcut) is not None:
            if h.taban_tutar is not None and carpanlar:
                y.formul_yaz(ws, adres, "=" + "*".join([_sayi_metni(h.taban_tutar)] + [_sayi_metni(c) for c in carpanlar]), toplam)
            else:   # uygulamada toplam doğrudan girilmiş: sabit ifade sabit değere döner
                ws[adres].value = _hucre_degeri(toplam)
                y.yazilan[(ws.title, adres)] = ws[adres].value
                y.degisen += 1
        else:
            y.yaz(ws, adres, toplam, f"{h.ad} gider toplamı")
    for kod, adres in SANIYE_HUCRELERI.items():
        h = havuzlar.get(kod)
        if h is not None and h.baz_miktar is not None:
            y.yaz(ws, adres, h.baz_miktar, f"{h.ad} dağıtım bazı")
    for kod, satirlar, ad_sutunu in PAY_BLOKLARI:
        h = havuzlar.get(kod)
        if h is None:
            continue
        anahtarlar = {a.alt_kalem.strip(): a for a in h.anahtarlar}
        gorulen = set()
        for r in satirlar:
            ad = ws_v[f"{ad_sutunu}{r}"].value
            if not ad:
                continue
            ad = str(ad).strip()
            a = anahtarlar.get(ad)
            if a is None:
                y.uyari(f"Gider Dağıtım: {h.ad} / {ad} uygulamada yok; satıra dokunulmadı.")
                continue
            gorulen.add(ad)
            y.yaz(ws, f"G{r}", a.pay_orani, f"{h.ad} / {ad} pay")
            y.yaz(ws, f"E{r}", a.baz_miktar, f"{h.ad} / {ad} baz")
        for ad in anahtarlar:
            if ad not in gorulen:
                y.uyari(f"Gider Dağıtım: {h.ad} / {ad} uygulamada var, kitapta satırı yok; yazılmadı.")
    uyg = {a.ad.strip(): a for a in ambalajlar}
    gorulen = set()
    for r in range(70, 92):
        ad = ws_v[f"A{r}"].value
        if not ad:
            continue
        ad = str(ad).strip()
        a = uyg.get(ad)
        if a is None:
            y.uyari(f"Gider Dağıtım: ambalaj sınıfı {ad} uygulamada yok; satıra dokunulmadı.")
            continue
        gorulen.add(ad)
        y.yaz(ws, f"B{r}", a.hacim, f"ambalaj {ad} hacim")
        y.yaz(ws, f"C{r}", a.uretim_adedi, f"ambalaj {ad} üretim adedi")
        y.yaz(ws, f"D{r}", a.katsayi, f"ambalaj {ad} katsayı")
    for ad in uyg:
        if ad not in gorulen:
            y.uyari(f"Gider Dağıtım: ambalaj sınıfı {ad} uygulamada var, kitapta satırı yok; yazılmadı.")


def _uretim_adetleri_yaz(y: _Yazici, ws, kapasiteler: dict[str, m.UretimKapasitesi]) -> None:
    ws_v = y.wb_v[ws.title]
    gorulen = set()
    for r in range(4, ws.max_row + 1):
        kod = ws_v[f"A{r}"].value
        if kod is None or not str(kod).strip():
            continue
        kod = str(kod).strip()
        k = kapasiteler.get(kod)
        if k is None or kod in gorulen:
            continue
        gorulen.add(kod)
        if k.urun_ad:
            y.yaz(ws, f"B{r}", k.urun_ad, f"{kod} ürün adı")
        for alan, sutun in URETIM_SUTUNLARI.items():
            y.yaz(ws, f"{sutun}{r}", getattr(k, alan), f"{kod} {alan}")
    for kod in kapasiteler:
        if kod not in gorulen:
            y.uyari(f"Üretim Adetleri: {kod} uygulamada var, kitapta satırı yok; yazılmadı.")


def _recete_eslestir(excel_satirlari: list[tuple[int, str]], app_satirlari: list) -> tuple[list[tuple[int, object]], list[int], list]:
    """Excel satırları ile uygulama reçete satırları: sıra ve kod aynıysa birebir; değilse kod sırasıyla (her Excel satırına aynı kodlu ilk
    kullanılmamış satır). Dönüş: (eşleşen (excel satırı, uygulama satırı), eşleşmeyen Excel satırları, eşleşmeyen uygulama satırları)."""
    if [k for _, k in excel_satirlari] == [x.malzeme_kodu for x in app_satirlari]:
        return [(r, x) for (r, _), x in zip(excel_satirlari, app_satirlari)], [], []
    kullanildi = [False] * len(app_satirlari)
    eslesen, bos_excel = [], []
    for r, kod in excel_satirlari:
        i = next((i for i, x in enumerate(app_satirlari) if not kullanildi[i] and x.malzeme_kodu == kod), None)
        if i is None:
            bos_excel.append(r)
            continue
        kullanildi[i] = True
        eslesen.append((r, app_satirlari[i]))
    return eslesen, bos_excel, [x for i, x in enumerate(app_satirlari) if not kullanildi[i]]


def _urun_yaz(y: _Yazici, ws, cikti, u: m.Urun, p, degerler: dict, notlar: list[str], salma_fiyat: dict[str, Decimal],
              kartlar: dict) -> None:
    ad = ws.title
    ws_v = y.wb_v[ad]
    E = lambda etiket: eo._etiket_satiri(ws_v, etiket)
    Et = lambda etiket: eo._etiket_satiri(ws_v, etiket, tam=True)
    girdi, ub = cikti.girdi, cikti.girdi.uretim

    # Reçete
    r100 = E("HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    excel_satirlari = [(r, str(ws_v[f"D{r}"].value).strip()) for r in range(6, r100) if ws_v[f"D{r}"].value]
    eslesen, bos_excel, bos_app = _recete_eslestir(excel_satirlari, list(girdi.recete))
    for r in bos_excel:
        y.uyari(f"{ad}: satır {r} ({ws_v[f'D{r}'].value}) uygulamanın reçetesinde yok; satıra dokunulmadı.")
    for x in bos_app:
        y.uyari(f"{ad}: reçetede {x.malzeme_kodu} uygulamada var, kitapta satırı yok; yeni satır açılmadı.")
    for r, x in eslesen:
        kod = x.malzeme_kodu
        if x.ad:
            y.yaz(ws, f"E{r}", x.ad, f"{kod} adı")
        y.yaz(ws, f"I{r}", x.miktar, f"{kod} miktar")
        y.yaz(ws, f"J{r}", x.fire_orani, f"{kod} fire")
        if x.birim:
            y.yaz(ws, f"L{r}", x.birim, f"{kod} birim")
        i_son, j_son = _dec(y.deger(ad, f"I{r}")) or SIFIR, _dec(y.deger(ad, f"J{r}")) or SIFIR
        try:
            brut_formul = brut_miktar(i_son, j_son)
        except ValueError:
            brut_formul = None
        hedef_k = x.brut_miktar_elle if x.brut_miktar_elle is not None else brut_miktar(x.miktar, x.fire_orani)
        kf = ws[f"K{r}"].value
        if eo.formul_mu(kf) and not eo.k_elle_mi(kf, r) and brut_formul is not None:
            y.yaz(ws, f"K{r}", hedef_k, f"{kod} brüt miktar", formul_degeri=brut_formul)
        else:
            y.yaz(ws, f"K{r}", hedef_k, f"{kod} brüt miktar")
        liste = salma_fiyat.get(kod, SIFIR)
        hedef_m = x.birim_fiyat_elle if x.birim_fiyat_elle is not None else liste
        mf = ws[f"M{r}"].value
        if eo.formul_mu(mf) and "VLOOKUP" in mf.upper() and "ALMA" in mf.upper():
            y.yaz(ws, f"M{r}", hedef_m, f"{kod} birim fiyat", formul_degeri=liste)
        else:
            y.yaz(ws, f"M{r}", hedef_m, f"{kod} birim fiyat")
        kart = kartlar.get(kod)
        for sutun, elle, kart_degeri, ne in (("N", x.zs_elle, kart.zs if kart else None, "Z/S"),
                                             ("O", x.para_birimi_elle, kart.para_birimi if kart else None, "para birimi")):
            h = ws[f"{sutun}{r}"].value
            if eo.formul_mu(h):
                if elle is not None and elle != kart_degeri:
                    y.uyari(f"{ad}!{sutun}{r} ({kod} {ne}): uygulamada elle {elle}, Excel'de formül var; formüle dokunulmadı.")
            elif elle is not None:
                y.yaz(ws, f"{sutun}{r}", elle, f"{kod} {ne}")
            elif h not in (None, "") and kart_degeri:
                y.yaz(ws, f"{sutun}{r}", kart_degeri, f"{kod} {ne}")

    # Ürün ve üretim bilgileri
    y.yaz(ws, "P2", ub.pazar, "pazar")
    if girdi.ad:
        y.yaz(ws, "E6", girdi.ad, "ürün adı")
    r104 = E("Mal Kabul ve Fermantasyon Giderleri")
    y.yaz(ws, f"I{r104}", ub.mal_kabul_miktar_kg, "mal kabul miktarı (kg)")
    y.yaz(ws, f"J{r104}", ub.mal_kabul_fire, "mal kabul firesi")
    for etiket, tam, deger, ne in (("Süzme Miktar", False, ub.suzme_kg, "süzme kg"), ("Vardiya Üretim Adedi", False, ub.vardiya_uretim_adedi, "vardiya üretim adedi"),
                                   ("Dolum İşçilik Pers", False, ub.dolum_personel, "dolum personeli"), ("Etiketleme Adedi", False, ub.etiketleme_adedi, "etiketleme adedi"),
                                   ("Etiket İşçilik Pers", False, ub.etiket_personel, "etiket personeli"), ("Üretim", True, ub.hat, "hat"),
                                   ("Taze / Turşu", False, ub.taze_tursu_sinifi, "taze/turşu sınıfı"), ("Ambalaj", True, ub.ambalaj_hacmi, "ambalaj hacmi")):
        r = Et(etiket) if tam else E(etiket)
        y.yaz(ws, f"E{r}", deger, ne)

    # Gider satırlarında elle hücreler (I/K/M/P) ve pazarlama/yönetim anahtarı
    for kalem, etiket in GIDER_KALEMLERI.items():
        r = E(etiket)
        elle = girdi.gider_elle.get(kalem)
        for alan, sutun in GIDER_ELLE_ALANLARI.items():
            if (kalem, alan) in eo._GIDER_ELLE_DISI:
                continue
            h = ws[f"{sutun}{r}"].value
            v = getattr(elle, alan) if elle is not None else None
            if eo.formul_mu(h):
                if v is not None:
                    y.uyari(f"{ad}!{sutun}{r} ({etiket}): uygulamada elle {_goster(v)}, Excel'de formül var; formüle dokunulmadı.")
            elif v is not None:
                y.yaz(ws, f"{sutun}{r}", v, f"{etiket} elle")
            elif h not in (None, ""):
                y.uyari(f"{ad}!{sutun}{r} ({etiket}): Excel'de elle {_goster(h)} yazılı, uygulamada elle değer yok; formül geri konamadı, dokunulmadı.")
    r118, r119 = E("PAZARLAMA SATIŞ GİDERLERİ"), E("GENEL YÖNETİM GİDERLERİ")
    excel_pyu = not (eo._sabit_sifir(ws, f"P{r118}") and eo._sabit_sifir(ws, f"P{r119}"))
    if excel_pyu != ub.pazarlama_yonetim_uygula:
        y.uyari(f"{ad}: pazarlama/yönetim gideri uygulamada {'uygulanıyor' if ub.pazarlama_yonetim_uygula else 'uygulanmıyor'}, kitapta "
                f"{'uygulanıyor' if excel_pyu else 'uygulanmıyor'}; P{r118}/P{r119} formüllerine dokunulmadı.")

    # Parametreler (sayfa başına; ürün kapsamlı farklar dahil)
    r124, r145, r146, r147 = E("FİNANSMAN GİDERLERİ"), E("Taze / Turşu"), Et("Ambalaj"), Et("Ürün Adı")
    r148, r150 = Et("Enflasyon"), E("Döviz Kurları")
    y.yaz(ws, f"F{r148}", p.enflasyon, "enflasyon")
    if "maliyet_sapma" in degerler:
        try:
            y.yaz(ws, f"F{Et('Maliyet Sapma')}", degerler["maliyet_sapma"], "maliyet sapma oranı")
        except KeyError:
            pass
    gorulen = set()
    for i in range(5):
        pb = ws_v[f"I{r124 + i}"].value
        if not pb:
            continue
        pb = str(pb)
        gorulen.add(pb)
        if pb in p.faiz_oranlari:
            y.yaz(ws, f"J{r124 + i}", p.faiz_oranlari[pb], f"{pb} faiz oranı")
        if pb in p.stok_sureleri_ay:
            y.yaz(ws, f"K{r124 + i}", p.stok_sureleri_ay[pb], f"{pb} stok süresi (ay)")
    for pb in set(p.faiz_oranlari) - gorulen:
        y.uyari(f"{ad}: {pb} faiz oranı uygulamada var, kitapta satırı yok; yazılmadı.")
    gorulen = set()
    for i in range(6):
        pb = ws_v[f"E{r150 + i}"].value
        if not pb:
            continue
        pb = str(pb)
        gorulen.add(pb)
        if pb in p.kurlar:
            y.yaz(ws, f"F{r150 + i}", p.kurlar[pb], f"{pb} kuru")
    for pb in set(p.kurlar) - gorulen:
        y.uyari(f"{ad}: {pb} kuru uygulamada var, kitapta satırı yok; yazılmadı.")
    for r, oran in zip((r145, r146, r147), p.teklif_kar_oranlari):
        y.yaz(ws, f"L{r}", oran, "teklif kâr oranı")
    if notlar:
        try:
            r_not = E("Süzme Miktar") + 1
            if not eo.formul_mu(ws[f"G{r_not}"].value):
                y.yaz(ws, f"G{r_not}", notlar[0], "satış fiyatı notu")
        except KeyError:
            pass


# ---------------------------------------------------------------- önbellek (formül sonuçları) xlsx XML'ine
def _sayfa_yollari(z: zipfile.ZipFile) -> dict[str, str]:
    """Sayfa adı -> xl/worksheets/sheetN.xml (workbook.xml + ilişkiler)."""
    wb = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    hedef = {}
    for e in re.finditer(r"<Relationship\b([^>]*)/?>", rels):
        a = dict(re.findall(r'(\w+)="([^"]*)"', e.group(1)))
        if "Id" in a and "Target" in a:
            t = a["Target"].lstrip("/")
            hedef[a["Id"]] = t if t.startswith("xl/") else "xl/" + t
    out = {}
    for e in re.finditer(r"<(?:\w+:)?sheet\b([^>]*)/?>", wb):
        a = dict(re.findall(r'([\w:]+)="([^"]*)"', e.group(1)))
        rid = next((v for k, v in a.items() if k.endswith(":id")), None)
        if "name" in a and rid in hedef:
            out[unescape(a["name"], {"&quot;": '"', "&apos;": "'"})] = hedef[rid]
    return out


_HUCRE = re.compile(r'<c r="(?P<r>[A-Z]+\d+)"(?P<a>[^>]*)>(?P<f><f\b[^>]*/>|<f\b[^>]*>.*?</f>)(?:<v\s*/>|<v></v>|<v>[^<]*</v>)?</c>', re.S)


def onbellek_ekle(icerik: bytes, degerler: dict[str, dict[str, object]]) -> bytes:
    """openpyxl'in boş bıraktığı formül önbelleklerine (<v/>) değer yazar: {sayfa adı: {hücre: sayı|metin}}."""
    if not degerler:
        return icerik
    giris, cikis = BytesIO(icerik), BytesIO()
    with zipfile.ZipFile(giris) as zin, zipfile.ZipFile(cikis, "w", zipfile.ZIP_DEFLATED) as zout:
        yollar = {v: k for k, v in _sayfa_yollari(zin).items()}
        for bilgi in zin.infolist():
            veri = zin.read(bilgi.filename)
            sayfa = yollar.get(bilgi.filename)
            if sayfa in degerler:
                d = degerler[sayfa]

                def degistir(e):
                    v = d.get(e.group("r"), _YOK)
                    if v is _YOK or v is None or isinstance(v, bool):
                        return e.group(0)
                    a = re.sub(r'\st="[^"]*"', "", e.group("a"))
                    if isinstance(v, str):
                        return f'<c r="{e.group("r")}"{a} t="str">{e.group("f")}<v>{escape(v)}</v></c>'
                    sayi = repr(float(v)) if not isinstance(v, int) else str(v)
                    return f'<c r="{e.group("r")}"{a}>{e.group("f")}<v>{sayi}</v></c>'
                veri = _HUCRE.sub(degistir, veri.decode("utf-8")).encode("utf-8")
            zout.writestr(bilgi, veri)
    return cikis.getvalue()


# ---------------------------------------------------------------- üretim
def _dosya_adi(sablon_adi: str, tarih: date) -> str:
    kok = re.sub(r"\.(xlsx|xlsm|xls)$", "", sablon_adi or "Fiyat Çalışması", flags=re.I).strip() or "Fiyat Çalışması"
    return f"{kok} - uygulama {tarih:%d.%m.%Y}.xlsx"


def fiyat_kitabi_hazirla(s: Session, senaryo_id: int, tarih: date | None = None) -> MusavirSonucu:
    tarih = tarih or date.today()
    sen = hesap_servisi.senaryo_getir(s, senaryo_id)
    sb = sablon(s, senaryo_id)
    if sb is None:
        raise BulunamadiHatasi(SABLON_YOK_MESAJI, {"senaryo_id": senaryo_id}, kod=SABLON_YOK)
    try:
        wb_f = openpyxl.load_workbook(BytesIO(sb.icerik), data_only=False, keep_vba=False)
        wb_v = openpyxl.load_workbook(BytesIO(sb.icerik), data_only=True, keep_vba=False)
    except Exception as e:   # noqa: BLE001 — saklı şablon bozuksa anlaşılır hata
        raise DogrulamaHatasi(f"Saklanan şablon açılamadı: {e}", kod="sablon_bozuk")
    y = _Yazici(wb_f, wb_v)

    malzemeler = fiyat_servisi.gecerli_fiyatlar(s, senaryo_id, tarih)
    baglam = hesap_servisi.HesapBaglami()
    urun_sayfalari = [a for a in eo.urun_sayfalarini_listele(wb_v) if "(2)" not in a]
    # Önce hesaplar (reçetede kullanılan malzemeler S.ALMA BF uyarısı için gerekir)
    hazir: list[tuple[str, object, m.Urun]] = []
    kullanilan: set[str] = set()
    sayfadaki_kodlar: set[str] = set()
    for ad in urun_sayfalari:
        d6 = wb_v[ad]["D6"].value
        kod = str(d6).strip() if d6 not in (None, "") else f"SAYFA-{ad}"
        sayfadaki_kodlar.add(kod)
        u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        if u is None:
            y.uyari(f"{ad}: ürün {kod} uygulamada yok; sayfaya dokunulmadı.")
            continue
        try:
            c = hesap_servisi.hesapla(s, kod, senaryo_id, tarih, baglam=baglam)
        except ServisHatasi as e:
            y.uyari(f"{ad}: {kod} bu çalışmada hesaplanamadı ({e.mesaj}); sayfaya dokunulmadı.")
            continue
        kullanilan |= {x.malzeme_kodu for x in c.girdi.recete}
        hazir.append((ad, c, u))

    ws_salma = _sayfa(wb_f, SAYFA_SALMA)
    salma_fiyat: dict[str, Decimal] = {}
    if ws_salma is None:
        y.uyari("S.ALMA BF sayfası kitapta yok; malzeme fiyatları yazılmadı.")
    else:
        salma_fiyat = _salma_yaz(y, ws_salma, malzemeler, kullanilan)

    ws_gider = _sayfa(wb_f, SAYFA_GIDER)
    if ws_gider is None:
        y.uyari("Gider Dağıtım sayfası kitapta yok; gider havuzları yazılmadı.")
    else:
        _gider_yaz(y, ws_gider, gider_servisi.havuzlar(s, senaryo_id), gider_servisi.ambalajlar(s, senaryo_id))

    ws_uretim = _sayfa(wb_f, SAYFA_URETIM)
    kapasiteler = {k.urun_kodu: k for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo_id))}
    if ws_uretim is not None:
        _uretim_adetleri_yaz(y, ws_uretim, kapasiteler)
    elif kapasiteler:
        y.uyari("Üretim Adetleri sayfası kitapta yok; üretim kapasiteleri yazılmadı.")

    notlar = [k.deger for k in parametre_servisi.metin_gecerli(s, senaryo_id, tarih)]
    kartlar = {mz.kod: mz for mz in s.scalars(select(m.Malzeme))}
    sabit_uyarisi = False
    yazilan_urun = 0
    for ad, c, u in hazir:
        try:
            p = parametre_servisi.gecerli_parametreler(s, senaryo_id, tarih, u.id)
            degerler = parametre_servisi.gecerli_degerler(s, senaryo_id, tarih, u.id)
        except ServisHatasi as e:
            y.uyari(f"{ad}: parametreler okunamadı ({e.mesaj}); sayfaya dokunulmadı.")
            continue
        if not sabit_uyarisi:
            for anahtar, sabit in OKUYUCU_SABITLERI.items():
                if anahtar in degerler and degerler[anahtar] != sabit:
                    y.uyari(f"{anahtar} uygulamada {_goster(degerler[anahtar])}; kitapta bu değerin hücresi yok (Excel {_goster(sabit)} kullanır).")
            sabit_uyarisi = True
        try:
            _urun_yaz(y, wb_f[ad], c, u, p, degerler, notlar, salma_fiyat, kartlar)
            yazilan_urun += 1
        except KeyError as e:
            y.uyari(f"{ad}: sayfa beklenen düzende değil ({e}); kısmen yazıldı.")
    uyeler = _senaryo_urunleri(s, senaryo_id)
    for kod in sorted(uyeler - sayfadaki_kodlar):
        y.uyari(f"Ürün {kod} uygulamada var, kitapta sayfası yok; yeni sayfa açılmadı.")

    y.bekleyenleri_coz()
    wb_f.calculation.fullCalcOnLoad = True
    simdi = datetime.now()
    wb_f.properties.description = (f"Uygulamadan üretildi: {simdi:%d.%m.%Y %H:%M}, senaryo: {sen.ad} (#{sen.id}), "
                                   f"değerler {tarih:%d.%m.%Y} tarihli. Şablon: {sb.dosya_adi}.")[:1000]
    wb_f.properties.modified = simdi
    wb_f.properties.lastModifiedBy = "Fiyat Çalışması uygulaması"
    tampon = BytesIO()
    wb_f.save(tampon)
    onbellek: dict[str, dict[str, object]] = {}
    for (sayfa, adres), v in y.onbellek.items():
        onbellek.setdefault(sayfa, {})[adres] = _hucre_degeri(v)
    icerik = onbellek_ekle(tampon.getvalue(), onbellek)
    uyarilar = y.uyarilar
    if len(uyarilar) > AZAMI_UYARI:
        uyarilar = uyarilar[:AZAMI_UYARI] + [f"… ve {len(y.uyarilar) - AZAMI_UYARI} uyarı daha."]
    return MusavirSonucu(icerik=icerik, dosya_adi=_dosya_adi(sb.dosya_adi, tarih), uyarilar=uyarilar, degisen_hucre=y.degisen,
                         urun_sayfasi=len(urun_sayfalari), yazilan_urun=yazilan_urun)


def _senaryo_urunleri(s: Session, senaryo_id: int) -> set[str]:
    """Senaryoda aktif reçetesi olan aktif ürünler."""
    q = (select(m.Urun.kod).join(m.Recete, m.Recete.urun_id == m.Urun.id)
         .where(m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True, m.Urun.aktif == True))   # noqa: E712
    return set(s.scalars(q))


def fiyat_kitabi_uret(s: Session, senaryo_id: int, tarih: date | None = None) -> bytes:
    return fiyat_kitabi_hazirla(s, senaryo_id, tarih).icerik
