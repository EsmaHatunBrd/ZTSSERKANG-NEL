"""Liste fiyatı çalışması (YALNIZ Berrak markalı ürünler): liste fiyatı = satış fiyatı ÷ pazarın böleni, KDV hariç, seçilen adıma en yakına
yuvarlanır (kurallar: liste_kurallari). Her ürünün iki pazarı vardır: yurtiçi (vars. bölen 0,63) ve yurtdışı (vars. 0,90); bölenler ve
yuvarlama adımı senaryo parametresi (`liste_bolen_yurtici`, `liste_bolen_yurtdisi`, `liste_yuvarlama`; tarihli).
Geçmiş yılların liste fiyatı ve birim maliyeti `ListeFiyati` tablosunda (ürün × yıl × pazar) tutulur; yıldan yıla liste artışı maliyet
artışıyla kıyaslanır. Gerçek geçmiş gelene kadar `ornek_uret` tahmini satırlar yazar (ornek=True; ekranda etiketli, tek tıkla silinir).
Tutarlar Decimal; oranlar 0,38 = %38."""
import hashlib
from datetime import date
from decimal import Decimal
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from . import parametre_servisi as ps, satis_okuyucu
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, DogrulamaHatasi
from .liste_kurallari import (BOLEN_ANAHTARLARI, PAZARLAR, VARSAYILAN_BOLENLER, VARSAYILAN_YUVARLAMA, YUVARLAMA_ANAHTARI, YUVARLAMA_SECENEKLERI,
                              berrak_mi, bolen_dogrula, liste_fiyati as _liste_fiyati, pazar_dogrula, yuvarlama_dogrula)

__all__ = ["bolen_gecerli", "yuvarlama_gecerli", "bolen_dogrula", "yuvarlama_dogrula", "pazar_dogrula", "berrak_mi", "PAZARLAR",
           "VARSAYILAN_BOLENLER", "VARSAYILAN_YUVARLAMA", "YUVARLAMA_SECENEKLERI"]

EN_ESKI_YIL, EN_YENI_YIL = 2000, 2100
BASLIKLAR = ("urun_kodu", "yil", "liste_fiyati", "birim_maliyet", "pazar")
ISTEGE_BAGLI = ("birim_maliyet", "pazar")
PAZAR_ETIKETI = {"yurtici": "Yurtiçi", "yurtdisi": "Yurtdışı"}
ORNEK_YIL_SAYISI = 3
# Örnek veri: geriye doğru yıllık artış varsayımı (en yakın yıldan uzağa). Ürün başına ±4 puan sapma (koddan türetilir, her üretimde aynı).
ORNEK_LISTE_ARTIS = (Decimal("0.42"), Decimal("0.38"), Decimal("0.45"))
ORNEK_MALIYET_ARTIS = (Decimal("0.46"), Decimal("0.35"), Decimal("0.48"))


def bolen_gecerli(s: Session, senaryo_id: int, tarih: date | None = None, pazar: str = "yurtici") -> tuple[Decimal, bool]:
    """(bölen, kayıtlı_mı): senaryoda o pazar için girilmiş değer yoksa varsayılan (yurtiçi 0,63, yurtdışı 0,90) ve False."""
    pazar = pazar_dogrula(pazar)
    d = ps.gecerli_degerler(s, senaryo_id, tarih or date.today())
    a = BOLEN_ANAHTARLARI[pazar]
    return (d[a], True) if a in d else (VARSAYILAN_BOLENLER[pazar], False)


def bolenler_gecerli(s: Session, senaryo_id: int, tarih: date | None = None) -> dict[str, Decimal]:
    return {p: bolen_gecerli(s, senaryo_id, tarih, p)[0] for p in PAZARLAR}


def yuvarlama_gecerli(s: Session, senaryo_id: int, tarih: date | None = None) -> tuple[Decimal, bool]:
    """(adım, kayıtlı_mı): girilmemişse 0,01 TL ve False."""
    d = ps.gecerli_degerler(s, senaryo_id, tarih or date.today())
    return (yuvarlama_dogrula(d[YUVARLAMA_ANAHTARI]), True) if YUVARLAMA_ANAHTARI in d else (VARSAYILAN_YUVARLAMA, False)


def calisma_yili(sen: m.Senaryo) -> int:
    """Yeni liste fiyatının yılı: senaryonun sezon başlangıç yılı (2026-2027 sezonu -> 2026)."""
    return sen.sezon.baslangic.year


def _oran(yeni: Decimal | None, eski: Decimal | None) -> Decimal | None:
    if yeni is None or eski is None or eski == 0:
        return None
    return yeni / eski - 1


def _ort(degerler: list[Decimal]) -> Decimal | None:
    return sum(degerler, Decimal(0)) / len(degerler) if degerler else None


def _gecmis(s: Session, urun_idleri: list[int], pazar: str) -> dict[int, dict[int, m.ListeFiyati]]:
    out: dict[int, dict[int, m.ListeFiyati]] = {}
    if not urun_idleri:
        return out
    for k in s.scalars(select(m.ListeFiyati).where(m.ListeFiyati.urun_id.in_(urun_idleri), m.ListeFiyati.pazar == pazar)):
        out.setdefault(k.urun_id, {})[k.yil] = k
    return out


def berrak_satirlari(s: Session, satirlar: list[dict]) -> tuple[list[dict], int]:
    """Genel Bakış satırlarından Berrak markalı olanlar ve Berrak olmayanların sayısı."""
    ids = [r["id"] for r in satirlar]
    markalar = dict(s.execute(select(m.Urun.id, m.Urun.marka).where(m.Urun.id.in_(ids))).all()) if ids else {}
    berrak = [r for r in satirlar if berrak_mi(markalar.get(r["id"]))]
    return berrak, len(satirlar) - len(berrak)


def calisma(s: Session, sen: m.Senaryo, satirlar: list[dict], pazar: str = "yurtici", bolen: Decimal | None = None,
            yuvarlama: Decimal | None = None, tarih: date | None = None) -> dict:
    """`satirlar`: Genel Bakış satırları (id, kod, ad, hat, maliyet_tl, satis_tl, hata); yalnız Berrak olanlar çalışmaya girer.
    `bolen` / `yuvarlama` verilirse kaydetmeden deneme (kayıtlı parametrenin yerine). yeni_liste_ham = satış ÷ bölen; yeni_liste yuvarlanmış;
    artışlar yuvarlanmış yeni liste ile o pazarın geçmiş kayıtlarından hesaplanır.
    Yıllık seri: her yıl için, o yılla bir önceki yılın ikisi de bilinen ürünlerin artış ortalaması (basit ortalama)."""
    pazar = pazar_dogrula(pazar)
    kayitli_bolen, bolen_var = bolen_gecerli(s, sen.id, tarih, pazar)
    kayitli_adim, adim_var = yuvarlama_gecerli(s, sen.id, tarih)
    bolen_ = bolen_dogrula(bolen) if bolen is not None else kayitli_bolen
    adim = yuvarlama_dogrula(yuvarlama) if yuvarlama is not None else kayitli_adim
    yil = calisma_yili(sen)
    berrak, berrak_disi = berrak_satirlari(s, satirlar)
    gecmis = _gecmis(s, [r["id"] for r in berrak], pazar)
    kayitlar, liste_artislari, maliyet_artislari = [], [], []
    seri: dict[int, dict[str, list[Decimal]]] = {}
    ornek_var = False
    for r in berrak:
        maliyet = Decimal(r["maliyet_tl"]) if r.get("maliyet_tl") is not None else None
        satis = Decimal(r["satis_tl"]) if r.get("satis_tl") is not None else None
        ham, yeni = _liste_fiyati(satis, bolen_, adim)
        g = {y: k for y, k in gecmis.get(r["id"], {}).items() if y < yil}   # çalışma yılı ve sonrası: yeni liste uygulamadan gelir
        ornek_var = ornek_var or any(k.ornek for k in g.values())
        # yıl -> (liste, maliyet): geçmiş kayıtlar + çalışma yılı (uygulamanın hesabı)
        nokta = {y: (k.liste_fiyati, k.birim_maliyet) for y, k in g.items()}
        if yeni is not None:
            nokta[yil] = (yeni, maliyet)
        yillar = sorted(nokta)
        for onceki, sonraki in zip(yillar, yillar[1:]):
            la = _oran(nokta[sonraki][0], nokta[onceki][0])
            ma = _oran(nokta[sonraki][1], nokta[onceki][1])
            d = seri.setdefault(sonraki, {"liste": [], "maliyet": []})
            if la is not None:
                d["liste"].append(la)
            if ma is not None:
                d["maliyet"].append(ma)
        onceki_yil = max(g) if g else None
        onceki = g.get(onceki_yil) if onceki_yil is not None else None
        liste_artis = _oran(yeni, onceki.liste_fiyati) if onceki else None
        maliyet_artis = _oran(maliyet, onceki.birim_maliyet) if onceki else None
        if liste_artis is not None:
            liste_artislari.append(liste_artis)
        if maliyet_artis is not None:
            maliyet_artislari.append(maliyet_artis)
        kayitlar.append({
            "kod": r["kod"], "ad": r["ad"], "hat": r.get("hat"), "hata": r.get("hata"),
            "maliyet_tl": maliyet, "satis_tl": satis, "yeni_liste_ham": ham, "yeni_liste": yeni,
            "onceki_yil": onceki_yil, "onceki_liste": onceki.liste_fiyati if onceki else None,
            "liste_artis": liste_artis, "maliyet_artis": maliyet_artis,
            "fark": (liste_artis - maliyet_artis) if liste_artis is not None and maliyet_artis is not None else None,
            "gecmis": [{"yil": y, "pazar": k.pazar, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet, "bolen": k.bolen,
                        "ornek": k.ornek} for y, k in sorted(g.items(), reverse=True)],
        })
    ort_l, ort_m = _ort(liste_artislari), _ort(maliyet_artislari)
    return decimal_str({
        "yil": yil, "pazar": pazar, "bolen": bolen_, "bolenler": bolenler_gecerli(s, sen.id, tarih),
        "bolen_kayitli": bolen_var and bolen is None, "varsayilan_bolen": VARSAYILAN_BOLENLER[pazar],
        "yuvarlama": YUVARLAMA_SECENEKLERI[[Decimal(x) for x in YUVARLAMA_SECENEKLERI].index(adim)],
        "yuvarlama_kayitli": adim_var and yuvarlama is None, "varsayilan_yuvarlama": str(VARSAYILAN_YUVARLAMA),
        "yuvarlama_secenekleri": list(YUVARLAMA_SECENEKLERI), "berrak_disi": berrak_disi, "ornek_var": ornek_var,
        "ozet": {"liste_artis_ort": ort_l, "maliyet_artis_ort": ort_m,
                 "fark": (ort_l - ort_m) if ort_l is not None and ort_m is not None else None,
                 "karsilastirilan": len(liste_artislari), "urun_sayisi": len(kayitlar),
                 "gerisinde": sum(1 for k in kayitlar if k["fark"] is not None and k["fark"] < 0)},
        "yillar": [{"yil": y, "liste_artis_ort": _ort(d["liste"]), "maliyet_artis_ort": _ort(d["maliyet"]), "urun_sayisi": len(d["liste"])}
                   for y, d in sorted(seri.items())],
        "kayitlar": kayitlar,
    })


def _urun(s: Session, kod: str) -> m.Urun:
    u = s.scalar(select(m.Urun).where(m.Urun.kod == (kod or "").strip()))
    if u is None:
        raise BulunamadiHatasi("ürün bulunamadı", {"urun_kodu": kod})
    return u


BERRAK_DEGIL = "liste fiyatı yalnız Berrak markalı ürünlere girilir (ürün kartında marka: Berrak)"


def _degerler_hatalari(yil, liste_fiyati, birim_maliyet) -> list[str]:
    h = []
    if not isinstance(yil, int) or not (EN_ESKI_YIL <= yil <= EN_YENI_YIL):
        h.append(f"yıl {EN_ESKI_YIL}–{EN_YENI_YIL} arasında olmalı")
    if liste_fiyati is None or liste_fiyati <= 0:
        h.append("liste fiyatı 0'dan büyük olmalı")
    if birim_maliyet is not None and birim_maliyet <= 0:
        h.append("birim maliyet 0'dan büyük olmalı")
    return h


def _bul(s: Session, u: m.Urun, yil: int, pazar: str) -> m.ListeFiyati | None:
    return s.scalar(select(m.ListeFiyati).where(m.ListeFiyati.urun_id == u.id, m.ListeFiyati.yil == yil, m.ListeFiyati.pazar == pazar))


def _icerik(k: m.ListeFiyati) -> dict:
    return decimal_str({"pazar": k.pazar, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet, "bolen": k.bolen, "ornek": k.ornek})


def _yaz(s: Session, u: m.Urun, yil: int, pazar: str, liste_fiyati: Decimal, birim_maliyet: Decimal | None, bolen: Decimal | None,
         kullanici: str) -> tuple[m.ListeFiyati, dict | None]:
    """Upsert; dönüş (kayıt, eski içerik ya da None). Gerçek veri yazılınca satır artık örnek değildir."""
    k = _bul(s, u, yil, pazar)
    eski = None
    if k is None:
        k = m.ListeFiyati(urun_id=u.id, yil=yil, pazar=pazar, liste_fiyati=liste_fiyati, birim_maliyet=birim_maliyet, bolen=bolen, ornek=False,
                          olusturan=kullanici)
        s.add(k)
    else:
        eski = _icerik(k)
        k.liste_fiyati, k.birim_maliyet, k.bolen, k.ornek = liste_fiyati, birim_maliyet, bolen, False
    s.flush()
    return k, eski


def kaydet(s: Session, urun_kodu: str, yil: int, liste_fiyati: Decimal, birim_maliyet: Decimal | None = None, kullanici: str = "sistem",
           pazar: str = "yurtici", bolen: Decimal | None = None, senaryo_id: int | None = None) -> dict:
    """`bolen` verilmezse kaydedildiği andaki geçerli bölen yazılır: `senaryo_id` varsa o senaryonun bugünkü değeri, yoksa pazarın varsayılanı."""
    pazar = pazar_dogrula(pazar)
    u = _urun(s, urun_kodu)
    h = _degerler_hatalari(yil, liste_fiyati, birim_maliyet)
    if not berrak_mi(u.marka):
        h.append(BERRAK_DEGIL)
    if h:
        raise DogrulamaHatasi("liste fiyatı geçersiz", {"hatalar": h})
    if bolen is not None:
        bolen = bolen_dogrula(bolen)
    elif senaryo_id is not None:
        bolen, _ = bolen_gecerli(s, senaryo_id, None, pazar)
    else:
        bolen = VARSAYILAN_BOLENLER[pazar]
    k, eski = _yaz(s, u, yil, pazar, Decimal(liste_fiyati), Decimal(birim_maliyet) if birim_maliyet is not None else None, bolen, kullanici)
    s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=k.id, islem="ekle" if eski is None else "guncelle", eski=eski, kullanici=kullanici,
                            yeni={"urun_kodu": u.kod, "yil": yil, **_icerik(k)}))
    s.flush()
    return cikis(k, u)


def cikis(k: m.ListeFiyati, u: m.Urun) -> dict:
    return decimal_str({"urun_kodu": u.kod, "yil": k.yil, "pazar": k.pazar, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet,
                        "bolen": k.bolen, "ornek": k.ornek})


def sil(s: Session, urun_kodu: str, yil: int, kullanici: str = "sistem", pazar: str = "yurtici") -> None:
    pazar = pazar_dogrula(pazar)
    u = _urun(s, urun_kodu)
    k = _bul(s, u, yil, pazar)
    if k is None:
        raise BulunamadiHatasi("liste fiyatı bulunamadı", {"urun_kodu": urun_kodu, "yil": yil, "pazar": pazar})
    s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=k.id, islem="sil", yeni=None, kullanici=kullanici,
                            eski={"urun_kodu": u.kod, "yil": yil, **_icerik(k)}))
    s.delete(k)
    s.flush()


def _pazar_hucresi(v) -> str | None:
    """"Yurtiçi" / "Yurtdışı" (büyük/küçük ve Türkçe harf duyarsız; "yurtici"/"yurtdisi" de olur); boş -> yurtiçi; tanınmazsa None."""
    a = satis_okuyucu._baslik_anahtari(v)
    if not a:
        return "yurtici"
    return a if a in PAZARLAR else None


def _satir(no: int, ham: dict) -> dict:
    hatalar: list[str] = []
    yil_ham = str(ham.get("yil") or "").strip()
    try:
        yil = int(Decimal(yil_ham.replace(",", "."))) if yil_ham else None
    except ArithmeticError:
        yil = None
    if yil is None:
        hatalar.append("yıl sayı olmalı (ör. 2025)")
    liste = satis_okuyucu._sayi_alani(ham, "liste_fiyati", hatalar)
    maliyet = None
    if str(ham.get("birim_maliyet") or "").strip():
        maliyet = satis_okuyucu._sayi_alani(ham, "birim_maliyet", hatalar)
    pazar = _pazar_hucresi(ham.get("pazar"))
    if pazar is None:
        hatalar.append(f"pazar 'Yurtiçi', 'Yurtdışı' ya da boş olmalı ('{str(ham.get('pazar')).strip()[:20]}')")
    return {"satir_no": no, "urun_kodu": str(ham.get("urun_kodu") or "").strip(), "yil": yil, "pazar": pazar or "yurtici", "liste_fiyati": liste,
            "birim_maliyet": maliyet, "hatalar": hatalar}


def dosya_oku(icerik: bytes, dosya_adi: str = "") -> list[dict]:
    return satis_okuyucu.oku(icerik, dosya_adi, basliklar=BASLIKLAR, satir_fn=_satir, istege_bagli=ISTEGE_BAGLI, sablon="liste_fiyatlari")


def onizle(s: Session, satirlar: list[dict]) -> dict:
    """Hiçbir şey yazmaz: hangi (ürün, yıl, pazar) yeni, hangisi değişecek; hatalı satırlar (toplu_yukle ile aynı kurallar)."""
    from .yukleme_guvenligi import ozet, sorunlu
    hatalar = _satir_hatalari(s, satirlar)
    hatali_no = {h["satir_no"] for h in hatalar}
    yeni = degisen = ayni = 0
    for r in satirlar:
        if r["satir_no"] in hatali_no:
            continue
        u = s.scalar(select(m.Urun).where(m.Urun.kod == r["urun_kodu"]))
        k = _bul(s, u, r["yil"], r["pazar"])
        if k is None:
            yeni += 1
        elif k.liste_fiyati != r["liste_fiyati"] or k.birim_maliyet != r["birim_maliyet"] or k.ornek:
            degisen += 1
        else:
            ayni += 1
    oz = ozet(okunan=len(satirlar), yeni=yeni, degisen=degisen, ayni=ayni, atlanan=len(hatalar),
              sorunlu_satirlar=[sorunlu(h["satir_no"], None, None, None, h["mesaj"]) for h in hatalar],
              uyarilar=["Hatalı satırlar düzeltilmeden hiçbir satır yazılmaz."] if hatalar else [])
    return {"okunan": len(satirlar), "yeni": yeni, "degisen": degisen, "ayni": ayni, "hatalar": hatalar, "ozet": oz}


def _satir_hatalari(s: Session, satirlar: list[dict]) -> list[dict]:
    return _dogrula(s, satirlar)[0]


def toplu_yukle(s: Session, satirlar: list[dict], kullanici: str = "sistem", dosya_adi: str = "", senaryo_id: int | None = None) -> tuple[int, list[dict]]:
    """Tek işlem: herhangi bir satır hatalıysa hiçbiri yazılmaz. Var olan (ürün, yıl, pazar) güncellenir. Bölen: kaydet'teki gibi
    (senaryonun bugünkü geçerli böleni ya da varsayılan). Yazmadan önce yedek (geri al: eski değerler geri yazılır). Dönüş: (yazılan, hatalar)."""
    from .yukleme_guvenligi import GENEL, liste_icerik, yedekle
    hatalar, gecerli = _dogrula(s, satirlar)
    if hatalar:
        return 0, hatalar
    bolenler = bolenler_gecerli(s, senaryo_id) if senaryo_id is not None else dict(VARSAYILAN_BOLENLER)
    if gecerli:
        yedek = []
        for r, u in gecerli:
            k = _bul(s, u, r["yil"], r["pazar"])
            yedek.append({"urun_id": u.id, "yil": r["yil"], "pazar": r["pazar"], "eski": liste_icerik(k) if k is not None else None})
        yedekle(s, "liste_fiyatlari", GENEL, {"satirlar": yedek}, f"{len(gecerli)} liste fiyatı", (dosya_adi or None), kullanici)
    for r, u in gecerli:
        _yaz(s, u, r["yil"], r["pazar"], r["liste_fiyati"], r["birim_maliyet"], bolenler[r["pazar"]], kullanici)
    if gecerli:
        s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=0, islem="toplu_yukle", eski=None, kullanici=kullanici,
                                yeni={"yazilan": len(gecerli), "dosya": (dosya_adi or "")[:200], "bolenler": decimal_str(bolenler)}))
        s.flush()
    return len(gecerli), []


def _dogrula(s: Session, satirlar: list[dict]) -> tuple[list[dict], list]:
    hatalar, gecerli = [], []
    onbellek: dict[str, m.Urun | None] = {}
    gorulen: set[tuple[str, int, str]] = set()
    for r in satirlar:
        kod = r["urun_kodu"]
        if kod not in onbellek:
            onbellek[kod] = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        mesaj = list(r["hatalar"])
        if onbellek[kod] is None:
            mesaj.append("ürün bulunamadı")
        elif not berrak_mi(onbellek[kod].marka):
            mesaj.append(BERRAK_DEGIL)
        if not r["hatalar"]:
            mesaj += _degerler_hatalari(r["yil"], r["liste_fiyati"], r["birim_maliyet"])
        anahtar = (kod, r["yil"], r["pazar"])
        if anahtar in gorulen:
            mesaj.append("aynı ürün, yıl ve pazar dosyada birden çok kez var")
        gorulen.add(anahtar)
        if mesaj:
            hatalar.append({"satir_no": r["satir_no"], "mesaj": "; ".join(mesaj)})
        else:
            gecerli.append((r, onbellek[kod]))
    return hatalar, gecerli


def _sapma(kod: str, adim: int) -> Decimal:
    """Ürün ve yıl adımına özgü, -0,04 … +0,04 arası sabit sapma (aynı kod hep aynı sonucu verir)."""
    n = int(hashlib.sha256(f"{kod}:{adim}".encode()).hexdigest()[:8], 16) % 81   # 0..80
    return Decimal(n - 40) / Decimal(1000)


def ornek_uret(s: Session, sen: m.Senaryo, satirlar: list[dict], kullanici: str = "sistem") -> int:
    """Gerçek geçmiş gelene kadar tahmini liste fiyatları (yalnız Berrak ürünleri, iki pazar için): bugünkü liste (satış ÷ pazar böleni,
    yuvarlanmış) ve maliyetten geriye doğru yıllık artış varsayımıyla. Gerçek (ornek=False) satırı olan (ürün, yıl, pazar) atlanır.
    Dönüş: yazılan satır sayısı."""
    yil = calisma_yili(sen)
    adim, _ = yuvarlama_gecerli(s, sen.id)
    berrak, _ = berrak_satirlari(s, satirlar)
    n = 0
    for pazar in PAZARLAR:
        bolen, _ = bolen_gecerli(s, sen.id, None, pazar)
        gecmis = _gecmis(s, [r["id"] for r in berrak], pazar)
        for r in berrak:
            if r.get("satis_tl") is None or r.get("maliyet_tl") is None:
                continue
            _, liste = _liste_fiyati(Decimal(r["satis_tl"]), bolen, adim)
            maliyet = Decimal(r["maliyet_tl"])
            for i in range(ORNEK_YIL_SAYISI):
                liste = liste / (1 + ORNEK_LISTE_ARTIS[i] + _sapma(r["kod"], i))
                maliyet = maliyet / (1 + ORNEK_MALIYET_ARTIS[i] + _sapma(r["kod"], i + 10))
                y = yil - 1 - i
                var = gecmis.get(r["id"], {}).get(y)
                if var is not None and not var.ornek:
                    continue
                l2, m2 = liste.quantize(Decimal("0.01")), maliyet.quantize(Decimal("0.0001"))
                if var is None:
                    s.add(m.ListeFiyati(urun_id=r["id"], yil=y, pazar=pazar, liste_fiyati=l2, birim_maliyet=m2, bolen=bolen, ornek=True,
                                        olusturan=kullanici))
                else:
                    var.liste_fiyati, var.birim_maliyet, var.bolen = l2, m2, bolen
                n += 1
    if n:
        s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=0, islem="ornek_uret", eski=None, kullanici=kullanici, yeni={"yazilan": n}))
    s.flush()
    return n


def ornek_sil(s: Session, kullanici: str = "sistem") -> int:
    n = s.execute(delete(m.ListeFiyati).where(m.ListeFiyati.ornek == True)).rowcount or 0   # noqa: E712
    if n:
        s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=0, islem="ornek_sil", eski={"silinen": n}, yeni=None, kullanici=kullanici))
    s.flush()
    return n
