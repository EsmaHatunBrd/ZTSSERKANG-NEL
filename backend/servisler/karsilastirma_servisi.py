"""Karşılaştırmalar: geçen yıl satış fiyatı, enflasyon eşiği, üretim adedi etkisi, ambalaj/kg trendi, ürün ailesi. Tüm tutarlar Decimal, çıktı decimal_str."""
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from . import aile as aile_servisi, hesap_servisi as hs
from .donusum import decimal_str
from .hatalar import ServisHatasi

PENCERE_GUN = 365
YUZ = Decimal(100)


def pencere(senaryo: m.Senaryo) -> tuple[date, date]:
    """Sezon başlangıcından 12 ay geriye: [başlangıç-365g, başlangıç-1g]."""
    b = senaryo.sezon.baslangic
    return b - timedelta(days=PENCERE_GUN), b - timedelta(days=1)


def _ozetle(kayitlar: list[tuple[str, str, Decimal, Decimal]], bas: date, son: date) -> dict | None:
    """kayitlar: (musteri, para_birimi, fiyat, adet). Para birimi bazında adet ağırlıklı ortalama fiyat."""
    if not kayitlar:
        return None
    pb: dict[str, dict] = {}
    for musteri, para, fiyat, adet in kayitlar:
        d = pb.setdefault(para, {"tutar": SIFIR, "adet": SIFIR, "musteriler": set(), "kayit_sayisi": 0})
        d["tutar"] += fiyat * adet; d["adet"] += adet; d["musteriler"].add(musteri); d["kayit_sayisi"] += 1
    para_birimleri = {p: {"fiyat": d["tutar"] / d["adet"], "adet": d["adet"], "musteri_sayisi": len(d["musteriler"]), "kayit_sayisi": d["kayit_sayisi"]}
                      for p, d in sorted(pb.items()) if d["adet"] > 0}   # Σadet = 0: ağırlıklı ortalama tanımsız, para birimi atlanır
    if not para_birimleri:
        return None
    return decimal_str({"donem_basi": bas, "donem_sonu": son, "kayit_sayisi": len(kayitlar),
                        "musteri_sayisi": len({k[0] for k in kayitlar}), "para_birimleri": para_birimleri})


def gecen_yil_toplu(s: Session, senaryo: m.Senaryo, urun_idleri: set[int] | None = None, musteri: str | None = None) -> dict[int, dict]:
    """Tek sorgu (N+1 yok): {urun_id: gecen_yil özeti}; satışı olmayan ürün sözlükte yoktur."""
    bas, son = pencere(senaryo)
    q = select(m.SatisGecmisi.urun_id, m.SatisGecmisi.musteri, m.SatisGecmisi.para_birimi, m.SatisGecmisi.fiyat, m.SatisGecmisi.adet).where(
        m.SatisGecmisi.tarih >= bas, m.SatisGecmisi.tarih <= son)
    if urun_idleri is not None:
        if not urun_idleri:
            return {}
        q = q.where(m.SatisGecmisi.urun_id.in_(urun_idleri))
    if musteri and musteri.strip():
        q = q.where(m.SatisGecmisi.musteri == musteri.strip())
    gruplar: dict[int, list] = {}
    for uid, mus, para, fiyat, adet in s.execute(q):
        gruplar.setdefault(uid, []).append((mus, para, fiyat, adet))
    return {uid: _ozetle(k, bas, son) for uid, k in gruplar.items()}


def gecen_yil(s: Session, urun: m.Urun, senaryo: m.Senaryo, musteri: str | None = None) -> dict | None:
    """Sezon başlangıcından önceki 12 ayın satışları; yoksa None. `musteri` tam eşleşme süzgecidir (boşluk kırpılır)."""
    return gecen_yil_toplu(s, senaryo, {urun.id}, musteri).get(urun.id)


def enflasyon_esigi(s: Session, urun: m.Urun, senaryo: m.Senaryo, hesap, gecen: dict | None = None) -> dict | None:
    """Her para birimi için yeni_fiyat / (gecen_yil_fiyat x (1 + enflasyon_pb)). TL'de senaryo enflasyonu, dövizde 0 (Excel kuralı).
    oran < 1 'altinda' (eşiğin altında), aksi halde 'ustunde'. fark_yuzde = (oran - 1) x 100. Geçen yıl yoksa None."""
    return enflasyon_esigi_hesapla(gecen_yil(s, urun, senaryo), hesap)


def enflasyon_esigi_hesapla(gecen: dict | None, hesap) -> dict | None:
    """Saf hesap (sorgu yok): `gecen` önceden alınmış geçen yıl özeti (yoksa None). Dashboard toplu yolu ve tek ürün ucu bunu kullanır."""
    if not gecen:
        return None
    r = hesap.sonuc
    yeni = {"TL": r.satis_fiyati_tl, **{pb: v for pb, v in r.satis_fiyati_doviz.items()}}
    enf = hesap.parametreler.enflasyon
    out: dict[str, dict] = {}
    for pb, g in gecen["para_birimleri"].items():
        gy = Decimal(g["fiyat"])
        y = yeni.get(pb)
        if y is None or gy <= 0:
            continue
        esik = gy * (1 + (enf if pb == "TL" else SIFIR))
        if esik <= 0:
            continue   # eşik paydası 0/negatif (enflasyon <= -%100): oran tanımsız
        oran = Decimal(y) / esik
        out[pb] = {"gecen_yil": gy, "yeni": Decimal(y), "oran": oran, "fark_yuzde": (oran - 1) * YUZ, "durum": "altinda" if oran < 1 else "ustunde"}
    return decimal_str(out) if out else None


def uretim_adedi_etkisi(s: Session, urun: m.Urun, senaryo: m.Senaryo, tarih: date | None = None, hesap=None, hedef: Decimal | None = None) -> dict | None:
    """Üretim Adetleri sayfasındaki hedef üretimle yeniden hesap (Excel Teklif Kapak ikinci 'Birim Maliyet' bloğu). Kapasite kaydı yoksa None.
    `hesap` (bütçe hesabı) ve `hedef` verilirse yeniden sorgu/hesap yapılmaz (toplu dashboard için)."""
    if hedef is None:
        k = s.scalar(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == senaryo.id, m.UretimKapasitesi.urun_kodu == urun.kod))
        if k is None:
            return None
        hedef = k.hedef_uretim
    if hedef is None or hedef <= 0:
        return None
    butce = hesap if hesap is not None else hs.hesapla(s, urun.kod, senaryo.id, tarih)
    yeni = hs.hesapla(s, urun.kod, senaryo.id, tarih, override={"uretim": {"vardiya_uretim_adedi": hedef}})
    b_adet = butce.girdi.uretim.vardiya_uretim_adedi
    d = {"butce_adedi": b_adet, "hedef_adedi": hedef, "oran": hedef / b_adet if b_adet else None}
    for ad, c in (("butce", butce.sonuc), ("hedef", yeni.sonuc)):
        d[f"maliyet_tl_{ad}"] = c.finansman_dahil_maliyet_tl
        d[f"maliyet_usd_{ad}"] = c.doviz_maliyet.get("USD")
        d[f"maliyet_eur_{ad}"] = c.doviz_maliyet.get("EUR")
        d[f"satis_tl_{ad}"] = c.satis_fiyati_tl
        d[f"satis_usd_{ad}"] = c.satis_fiyati_doviz.get("USD")
        d[f"satis_eur_{ad}"] = c.satis_fiyati_doviz.get("EUR")
    return decimal_str(d)


def _kapsam_urunleri(s: Session, senaryo_id: int | None) -> list[m.Urun]:
    """senaryo_id verilmişse yalnız senaryo üyesi (aktif reçeteli) aktif ürünler; None ise tüm aktif ürünler."""
    urunler = hs.urunler(s)
    if senaryo_id is None:
        return urunler
    from . import senaryo_servisi
    uyeler = senaryo_servisi.uye_urun_kodlari(s, senaryo_id)
    return [u for u in urunler if u.kod in uyeler]


def aile_urunleri(s: Session, aile: str, senaryo_id: int | None = None) -> list[m.Urun]:
    """Ailenin aktif ürünleri (senaryo verilmişse yalnız üyeler), ambalaj hacmine (sonra koda) göre sıralı."""
    return sorted((u for u in _kapsam_urunleri(s, senaryo_id) if (u.aile or aile_servisi.aile_turet(u.ad)) == aile),
                  key=lambda u: (aile_servisi.ambalaj_ml(u.ad, u.ambalaj_hacmi), u.kod))


def aileler(s: Session, senaryo_id: int | None = None) -> list[dict]:
    """Aktif ürünlerin (senaryo verilmişse yalnız üyelerin) aile listesi (ada göre sıralı); tek üyeli ailelerde tek_uyeli=True."""
    gruplar: dict[str, list[m.Urun]] = {}
    for u in _kapsam_urunleri(s, senaryo_id):
        gruplar.setdefault(u.aile or aile_servisi.aile_turet(u.ad), []).append(u)
    return [{"aile": a, "aile_ad": aile_servisi.aile_gorunen_ad(a, sorted(us, key=lambda u: (aile_servisi.ambalaj_ml(u.ad, u.ambalaj_hacmi), u.kod))), "urun_sayisi": len(us), "tek_uyeli": len(us) == 1,
             "urunler": [{"kod": u.kod, "ad": u.ad, "ambalaj_hacmi": str(u.ambalaj_hacmi), "ambalaj_etiket": aile_servisi.ambalaj_etiket(u.ad)} for u in sorted(us, key=lambda u: (aile_servisi.ambalaj_ml(u.ad, u.ambalaj_hacmi), u.kod))]}
            for a, us in sorted(gruplar.items())]


def ambalaj_kg_trendi(s: Session, aile: str, senaryo: m.Senaryo, tarih: date | None = None, tum: bool = False) -> list[dict]:
    """Ailenin ürünleri ambalaj hacmine göre; her biri için canlı hesap. Hesap hatası satırda `hata`, liste kırılmaz.
    kg_basi_satis_tl = satis_tl / suzme_kg; onceki_ile_fark_yuzde = bir önceki geçerli satıra göre kg başı satış değişimi (%)."""
    out: list[dict] = []
    onceki: Decimal | None = None
    for u in aile_urunleri(s, aile, None if tum else senaryo.id):
        satir = {"kod": u.kod, "ad": u.ad, "ambalaj_hacmi": u.ambalaj_hacmi, "ambalaj_etiket": aile_servisi.ambalaj_etiket(u.ad),
                 "ambalaj_ml": aile_servisi.ambalaj_ml(u.ad, u.ambalaj_hacmi), "suzme_kg": u.suzme_kg, "satis_tl": None, "satis_usd": None,
                 "suzme_kg_fiyati": None, "kg_basi_satis_tl": None, "onceki_ile_fark_yuzde": None, "hata": None}
        try:
            c = hs.hesapla(s, u.kod, senaryo.id, tarih)
        except (ServisHatasi, KeyError, ValueError, ArithmeticError) as e:
            satir["hata"] = str(getattr(e, "mesaj", None) or e)
        else:
            r = c.sonuc
            satir.update(satis_tl=r.satis_fiyati_tl, satis_usd=r.satis_fiyati_doviz.get("USD"), suzme_kg_fiyati=r.suzme_kg_fiyati_tl)
            if u.suzme_kg and u.suzme_kg > 0:
                kg = r.satis_fiyati_tl / u.suzme_kg
                satir["kg_basi_satis_tl"] = kg
                if onceki:
                    satir["onceki_ile_fark_yuzde"] = (kg / onceki - 1) * YUZ
                onceki = kg
        out.append(decimal_str(satir))
    return out
