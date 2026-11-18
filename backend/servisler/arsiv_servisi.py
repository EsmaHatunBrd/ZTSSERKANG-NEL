"""Arşiv: sezon -> senaryo -> tarihli kayıtlı hesaplar; iki kayıtlı hesabın yan yana kıyası; senaryo kilidi.
Salt okunur (kilit işlemi hariç). Tutarlar Decimal; çıktıda str."""
from decimal import Decimal, InvalidOperation
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import zaman_iso
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

TOPLAM_ALANLARI = (("malzeme_toplami", "Malzeme toplamı"), ("direkt_iscilik_toplami", "Direkt işçilik"), ("gug_toplami", "GÜG"),
                   ("uretim_gideri_toplami", "Üretim gideri"), ("diger_giderler_toplami", "Diğer giderler"), ("giydirilmis_maliyet", "Giydirilmiş maliyet"),
                   ("finansman_dahil_maliyet_tl", "Maliyet (TL, finansman dahil)"))
FIYAT_ALANLARI = (("satis_fiyati_tl", "Satış fiyatı (TL)"), ("suzme_kg_fiyati_tl", "Süzme kg fiyatı (TL)"))


def _d(v) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def agac(s: Session) -> list[dict]:
    """Sezonlar -> senaryolar (sayılar toplu sorguyla: ürün [reçetesi olan], kayıtlı hesap, teklif)."""
    urun = dict(s.execute(select(m.Recete.senaryo_id, func.count(func.distinct(m.Recete.urun_id))).group_by(m.Recete.senaryo_id)).all())
    hesap = dict(s.execute(select(m.MaliyetHesabi.senaryo_id, func.count()).group_by(m.MaliyetHesabi.senaryo_id)).all())
    teklif = dict(s.execute(select(m.MaliyetHesabi.senaryo_id, func.count(m.Teklif.id))
                            .join(m.Teklif, m.Teklif.maliyet_hesabi_id == m.MaliyetHesabi.id).group_by(m.MaliyetHesabi.senaryo_id)).all())
    senaryolar: dict[int, list[m.Senaryo]] = {}
    for x in s.scalars(select(m.Senaryo).order_by(m.Senaryo.id.desc())):
        senaryolar.setdefault(x.sezon_id, []).append(x)
    out = []
    for z in s.scalars(select(m.Sezon).order_by(m.Sezon.baslangic.desc(), m.Sezon.id.desc())):
        out.append({"id": z.id, "ad": z.ad, "baslangic": z.baslangic.isoformat(), "bitis": z.bitis.isoformat(),
                    "senaryolar": [{"id": x.id, "tur": x.tur, "ad": x.ad, "aciklama": x.aciklama, "olusturma_zamani": zaman_iso(x.olusturma_zamani),
                                    "olusturan": x.olusturan, "kilitli": bool(x.kilitli), "kaynak_dosya": x.kaynak_dosya,
                                    "urun_sayisi": urun.get(x.id, 0), "hesap_sayisi": hesap.get(x.id, 0), "teklif_sayisi": teklif.get(x.id, 0)}
                                   for x in senaryolar.get(z.id, [])]})
    return out


def kayitlar(s: Session, senaryo_id: int, sayfa: int = 1, boyut: int = 50, urun_kodu: str | None = None) -> tuple[list[dict], int]:
    """Senaryonun kayıtlı hesapları, tarih sırasıyla (en yeni önce: hesap_tarihi, sonra kayıt kimliği)."""
    if s.get(m.Senaryo, senaryo_id) is None:
        raise BulunamadiHatasi("Çalışma bulunamadı.", {"senaryo_id": senaryo_id})
    q = select(m.MaliyetHesabi, m.Urun.kod, m.Urun.ad).join(m.Urun, m.Urun.id == m.MaliyetHesabi.urun_id).where(m.MaliyetHesabi.senaryo_id == senaryo_id)
    if urun_kodu:
        kacis = urun_kodu.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        q = q.where(m.Urun.kod.ilike(f"%{kacis}%", escape="\\"))
    toplam = s.scalar(select(func.count()).select_from(q.subquery()))
    sat = s.execute(q.order_by(m.MaliyetHesabi.hesap_tarihi.desc(), m.MaliyetHesabi.id.desc()).offset((sayfa - 1) * boyut).limit(boyut)).all()
    teklif = dict(s.execute(select(m.Teklif.maliyet_hesabi_id, func.count()).where(m.Teklif.maliyet_hesabi_id.in_([h.id for h, _, _ in sat]))
                            .group_by(m.Teklif.maliyet_hesabi_id)).all()) if sat else {}
    out = []
    for h, kod, ad in sat:
        sn = h.sonuc_snapshot or {}
        out.append({"id": h.id, "urun_kodu": kod, "urun_ad": ad, "hesap_tarihi": h.hesap_tarihi.isoformat(), "olusturma_zamani": zaman_iso(h.olusturma_zamani),
                    "olusturan": h.olusturan, "neden": (h.girdi_snapshot or {}).get("neden"), "maliyet_tl": sn.get("finansman_dahil_maliyet_tl"),
                    "satis_tl": sn.get("satis_fiyati_tl"), "teklif_sayisi": teklif.get(h.id, 0)})
    return out, toplam


def _hesap_getir(s: Session, hesap_id: int) -> tuple[m.MaliyetHesabi, m.Urun]:
    h = s.get(m.MaliyetHesabi, hesap_id)
    if h is None:
        raise BulunamadiHatasi("Kayıtlı hesap bulunamadı.", {"hesap_id": hesap_id})
    return h, s.get(m.Urun, h.urun_id)


def _fark(a, b) -> str | None:
    x, y = _d(a), _d(b)
    return None if x is None or y is None else str(y - x)


def _alan_satirlari(sa: dict, sb: dict, alanlar) -> list[dict]:
    return [{"alan": k, "etiket": e, "a": sa.get(k), "b": sb.get(k), "fark": _fark(sa.get(k), sb.get(k))} for k, e in alanlar]


def _malzeme_tutarlari(sn: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for x in sn.get("satirlar", []):
        if x.get("grup") == "malzeme":
            kod = x.get("kod") or x.get("kalem")
            if kod in out:   # aynı kod iki satırda: tutarlar toplanır
                out[kod]["tutar"] = str(Decimal(out[kod]["tutar"]) + Decimal(str(x["tutar"])))
            else:
                out[kod] = {"ad": x.get("kalem"), "tutar": str(x["tutar"])}
    return out


def kiyas(s: Session, hesap_a: int, hesap_b: int) -> dict:
    ha, ua = _hesap_getir(s, hesap_a)
    hb, ub = _hesap_getir(s, hesap_b)
    sa, sb = ha.sonuc_snapshot or {}, hb.sonuc_snapshot or {}
    ta, tb = _malzeme_tutarlari(sa), _malzeme_tutarlari(sb)
    satirlar = []
    for kod in sorted(set(ta) | set(tb)):
        x, y = ta.get(kod), tb.get(kod)
        satirlar.append({"malzeme_kodu": kod, "ad": (x or y)["ad"], "a_tutar": x["tutar"] if x else None, "b_tutar": y["tutar"] if y else None,
                         "fark": str(Decimal(y["tutar"] if y else "0") - Decimal(x["tutar"] if x else "0")),
                         "durum": "ortak" if x and y else ("sadece_a" if x else "sadece_b")})
    ozet = lambda h, u: {"id": h.id, "urun_kodu": u.kod, "urun_ad": u.ad, "senaryo_id": h.senaryo_id, "hesap_tarihi": h.hesap_tarihi.isoformat(),
                         "olusturma_zamani": zaman_iso(h.olusturma_zamani), "olusturan": h.olusturan}
    uyari = None
    if ua.id != ub.id:
        uyari = f"Farklı ürünler kıyaslanıyor: {ua.kod} ve {ub.kod}."
    elif ha.senaryo_id != hb.senaryo_id:
        uyari = "Farklı senaryolardan kayıtlar kıyaslanıyor."
    return {"a": ozet(ha, ua), "b": ozet(hb, ub), "uyari": uyari, "toplamlar": _alan_satirlari(sa, sb, TOPLAM_ALANLARI),
            "fiyatlar": _alan_satirlari(sa, sb, FIYAT_ALANLARI), "satirlar": satirlar}


def kilitle(s: Session, senaryo_id: int, neden: str, kullanici: str = "sistem") -> m.Senaryo:
    return _kilit_degistir(s, senaryo_id, True, neden, kullanici)


def kilit_ac(s: Session, senaryo_id: int, neden: str, kullanici: str = "sistem") -> m.Senaryo:
    return _kilit_degistir(s, senaryo_id, False, neden, kullanici)


def _kilit_degistir(s: Session, senaryo_id: int, kilitli: bool, neden: str, kullanici: str) -> m.Senaryo:
    if not (neden or "").strip():
        raise DogrulamaHatasi("Neden girin.", {"neden": "boş olamaz"})
    sen = s.get(m.Senaryo, senaryo_id)
    if sen is None:
        raise BulunamadiHatasi("Çalışma bulunamadı.", {"senaryo_id": senaryo_id})
    if bool(sen.kilitli) == kilitli:
        raise DogrulamaHatasi("Çalışma zaten kilitli." if kilitli else "Çalışma zaten kilitli değil.", {"senaryo_id": senaryo_id})
    sen.kilitli = kilitli
    s.add(m.DegisiklikKaydi(tablo="senaryo", kayit_id=sen.id, islem="kilitle" if kilitli else "kilit_ac", eski={"kilitli": not kilitli},
                            yeni={"kilitli": kilitli, "_neden": neden.strip()}, kullanici=kullanici))
    s.flush()
    return sen
