"""Liste fiyatı çalışması (Berrak): liste fiyatı = satış fiyatı ÷ bölen (varsayılan 0,63, senaryo parametresi `liste_bolen`).
Geçmiş yılların liste fiyatı ve birim maliyeti `ListeFiyati` tablosunda (ürün × yıl) tutulur; yıldan yıla liste artışı maliyet
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

BOLEN_ANAHTAR = "liste_bolen"
VARSAYILAN_BOLEN = Decimal("0.63")
EN_ESKI_YIL, EN_YENI_YIL = 2000, 2100
BASLIKLAR = ("urun_kodu", "yil", "liste_fiyati", "birim_maliyet")
ORNEK_YIL_SAYISI = 3
# Örnek veri: geriye doğru yıllık artış varsayımı (en yakın yıldan uzağa). Ürün başına ±4 puan sapma (koddan türetilir, her üretimde aynı).
ORNEK_LISTE_ARTIS = (Decimal("0.42"), Decimal("0.38"), Decimal("0.45"))
ORNEK_MALIYET_ARTIS = (Decimal("0.46"), Decimal("0.35"), Decimal("0.48"))


def bolen_gecerli(s: Session, senaryo_id: int, tarih: date | None = None) -> tuple[Decimal, bool]:
    """(bölen, kayıtlı_mı): senaryoda girilmiş değer yoksa varsayılan 0,63 ve False."""
    d = ps.gecerli_degerler(s, senaryo_id, tarih or date.today())
    return (d[BOLEN_ANAHTAR], True) if BOLEN_ANAHTAR in d else (VARSAYILAN_BOLEN, False)


def bolen_dogrula(b: Decimal) -> Decimal:
    b = Decimal(b)
    if not (Decimal(0) < b <= Decimal(1)):
        raise DogrulamaHatasi("bölen 0 ile 1 arasında olmalı (ör. 0,63)", {"bolen": str(b)})
    return b


def calisma_yili(sen: m.Senaryo) -> int:
    """Yeni liste fiyatının yılı: senaryonun sezon başlangıç yılı (2026-2027 sezonu -> 2026)."""
    return sen.sezon.baslangic.year


def _oran(yeni: Decimal | None, eski: Decimal | None) -> Decimal | None:
    if yeni is None or eski is None or eski == 0:
        return None
    return yeni / eski - 1


def _ort(degerler: list[Decimal]) -> Decimal | None:
    return sum(degerler, Decimal(0)) / len(degerler) if degerler else None


def _gecmis(s: Session, urun_idleri: list[int]) -> dict[int, dict[int, m.ListeFiyati]]:
    out: dict[int, dict[int, m.ListeFiyati]] = {}
    if not urun_idleri:
        return out
    for k in s.scalars(select(m.ListeFiyati).where(m.ListeFiyati.urun_id.in_(urun_idleri))):
        out.setdefault(k.urun_id, {})[k.yil] = k
    return out


def calisma(s: Session, sen: m.Senaryo, satirlar: list[dict], bolen: Decimal) -> dict:
    """`satirlar`: Genel Bakış satırları (id, kod, ad, hat, maliyet_tl, satis_tl, hata). Liste fiyatı ve artışlar burada hesaplanır.
    Yıllık seri: her yıl için, o yılla bir önceki yılın ikisi de bilinen ürünlerin artış ortalaması (basit ortalama)."""
    bolen = bolen_dogrula(bolen)
    yil = calisma_yili(sen)
    gecmis = _gecmis(s, [r["id"] for r in satirlar])
    kayitlar, liste_artislari, maliyet_artislari = [], [], []
    seri: dict[int, dict[str, list[Decimal]]] = {}
    ornek_var = False
    for r in satirlar:
        maliyet = Decimal(r["maliyet_tl"]) if r.get("maliyet_tl") is not None else None
        satis = Decimal(r["satis_tl"]) if r.get("satis_tl") is not None else None
        yeni = satis / bolen if satis is not None else None
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
            "maliyet_tl": maliyet, "satis_tl": satis, "yeni_liste": yeni,
            "onceki_yil": onceki_yil, "onceki_liste": onceki.liste_fiyati if onceki else None,
            "liste_artis": liste_artis, "maliyet_artis": maliyet_artis,
            "fark": (liste_artis - maliyet_artis) if liste_artis is not None and maliyet_artis is not None else None,
            "gecmis": [{"yil": y, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet, "ornek": k.ornek} for y, k in sorted(g.items(), reverse=True)],
        })
    ort_l, ort_m = _ort(liste_artislari), _ort(maliyet_artislari)
    return decimal_str({
        "yil": yil, "bolen": bolen, "ornek_var": ornek_var,
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


def _degerler_hatalari(yil, liste_fiyati, birim_maliyet) -> list[str]:
    h = []
    if not isinstance(yil, int) or not (EN_ESKI_YIL <= yil <= EN_YENI_YIL):
        h.append(f"yıl {EN_ESKI_YIL}–{EN_YENI_YIL} arasında olmalı")
    if liste_fiyati is None or liste_fiyati <= 0:
        h.append("liste fiyatı 0'dan büyük olmalı")
    if birim_maliyet is not None and birim_maliyet <= 0:
        h.append("birim maliyet 0'dan büyük olmalı")
    return h


def _yaz(s: Session, u: m.Urun, yil: int, liste_fiyati: Decimal, birim_maliyet: Decimal | None, kullanici: str) -> tuple[m.ListeFiyati, dict | None]:
    """Upsert; dönüş (kayıt, eski içerik ya da None). Gerçek veri yazılınca satır artık örnek değildir."""
    k = s.scalar(select(m.ListeFiyati).where(m.ListeFiyati.urun_id == u.id, m.ListeFiyati.yil == yil))
    eski = None
    if k is None:
        k = m.ListeFiyati(urun_id=u.id, yil=yil, liste_fiyati=liste_fiyati, birim_maliyet=birim_maliyet, ornek=False, olusturan=kullanici)
        s.add(k)
    else:
        eski = decimal_str({"liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet, "ornek": k.ornek})
        k.liste_fiyati, k.birim_maliyet, k.ornek = liste_fiyati, birim_maliyet, False
    s.flush()
    return k, eski


def kaydet(s: Session, urun_kodu: str, yil: int, liste_fiyati: Decimal, birim_maliyet: Decimal | None = None, kullanici: str = "sistem") -> dict:
    u = _urun(s, urun_kodu)
    h = _degerler_hatalari(yil, liste_fiyati, birim_maliyet)
    if h:
        raise DogrulamaHatasi("liste fiyatı geçersiz", {"hatalar": h})
    k, eski = _yaz(s, u, yil, Decimal(liste_fiyati), Decimal(birim_maliyet) if birim_maliyet is not None else None, kullanici)
    s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=k.id, islem="ekle" if eski is None else "guncelle", eski=eski, kullanici=kullanici,
                            yeni=decimal_str({"urun_kodu": u.kod, "yil": yil, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet})))
    s.flush()
    return cikis(k, u)


def cikis(k: m.ListeFiyati, u: m.Urun) -> dict:
    return decimal_str({"urun_kodu": u.kod, "yil": k.yil, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet, "ornek": k.ornek})


def sil(s: Session, urun_kodu: str, yil: int, kullanici: str = "sistem") -> None:
    u = _urun(s, urun_kodu)
    k = s.scalar(select(m.ListeFiyati).where(m.ListeFiyati.urun_id == u.id, m.ListeFiyati.yil == yil))
    if k is None:
        raise BulunamadiHatasi("liste fiyatı bulunamadı", {"urun_kodu": urun_kodu, "yil": yil})
    s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=k.id, islem="sil", yeni=None, kullanici=kullanici,
                            eski=decimal_str({"urun_kodu": u.kod, "yil": yil, "liste_fiyati": k.liste_fiyati, "birim_maliyet": k.birim_maliyet, "ornek": k.ornek})))
    s.delete(k)
    s.flush()


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
    return {"satir_no": no, "urun_kodu": str(ham.get("urun_kodu") or "").strip(), "yil": yil, "liste_fiyati": liste,
            "birim_maliyet": maliyet, "hatalar": hatalar}


def dosya_oku(icerik: bytes, dosya_adi: str = "") -> list[dict]:
    return satis_okuyucu.oku(icerik, dosya_adi, basliklar=BASLIKLAR, satir_fn=_satir, istege_bagli=("birim_maliyet",))


def toplu_yukle(s: Session, satirlar: list[dict], kullanici: str = "sistem", dosya_adi: str = "") -> tuple[int, list[dict]]:
    """Tek işlem: herhangi bir satır hatalıysa hiçbiri yazılmaz. Var olan (ürün, yıl) güncellenir. Dönüş: (yazılan, hatalar)."""
    hatalar, gecerli = [], []
    onbellek: dict[str, m.Urun | None] = {}
    gorulen: set[tuple[str, int]] = set()
    for r in satirlar:
        kod = r["urun_kodu"]
        if kod not in onbellek:
            onbellek[kod] = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        mesaj = list(r["hatalar"])
        if onbellek[kod] is None:
            mesaj.append("ürün bulunamadı")
        if not r["hatalar"]:
            mesaj += _degerler_hatalari(r["yil"], r["liste_fiyati"], r["birim_maliyet"])
        if (kod, r["yil"]) in gorulen:
            mesaj.append("aynı ürün ve yıl dosyada birden çok kez var")
        gorulen.add((kod, r["yil"]))
        if mesaj:
            hatalar.append({"satir_no": r["satir_no"], "mesaj": "; ".join(mesaj)})
        else:
            gecerli.append((r, onbellek[kod]))
    if hatalar:
        return 0, hatalar
    for r, u in gecerli:
        _yaz(s, u, r["yil"], r["liste_fiyati"], r["birim_maliyet"], kullanici)
    if gecerli:
        s.add(m.DegisiklikKaydi(tablo="liste_fiyati", kayit_id=0, islem="toplu_yukle", eski=None, kullanici=kullanici,
                                yeni={"yazilan": len(gecerli), "dosya": (dosya_adi or "")[:200]}))
        s.flush()
    return len(gecerli), []


def _sapma(kod: str, adim: int) -> Decimal:
    """Ürün ve yıl adımına özgü, -0,04 … +0,04 arası sabit sapma (aynı kod hep aynı sonucu verir)."""
    n = int(hashlib.sha256(f"{kod}:{adim}".encode()).hexdigest()[:8], 16) % 81   # 0..80
    return Decimal(n - 40) / Decimal(1000)


def ornek_uret(s: Session, sen: m.Senaryo, satirlar: list[dict], bolen: Decimal, kullanici: str = "sistem") -> int:
    """Gerçek geçmiş gelene kadar tahmini liste fiyatları: bugünkü liste ve maliyetten geriye doğru yıllık artış varsayımıyla.
    Gerçek (ornek=False) satırı olan (ürün, yıl) atlanır. Dönüş: yazılan satır sayısı."""
    bolen = bolen_dogrula(bolen)
    yil = calisma_yili(sen)
    gecmis = _gecmis(s, [r["id"] for r in satirlar])
    n = 0
    for r in satirlar:
        if r.get("satis_tl") is None or r.get("maliyet_tl") is None:
            continue
        liste, maliyet = Decimal(r["satis_tl"]) / bolen, Decimal(r["maliyet_tl"])
        for adim in range(ORNEK_YIL_SAYISI):
            liste = liste / (1 + ORNEK_LISTE_ARTIS[adim] + _sapma(r["kod"], adim))
            maliyet = maliyet / (1 + ORNEK_MALIYET_ARTIS[adim] + _sapma(r["kod"], adim + 10))
            y = yil - 1 - adim
            var = gecmis.get(r["id"], {}).get(y)
            if var is not None and not var.ornek:
                continue
            l2, m2 = liste.quantize(Decimal("0.01")), maliyet.quantize(Decimal("0.0001"))
            if var is None:
                s.add(m.ListeFiyati(urun_id=r["id"], yil=y, liste_fiyati=l2, birim_maliyet=m2, ornek=True, olusturan=kullanici))
            else:
                var.liste_fiyati, var.birim_maliyet = l2, m2
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
