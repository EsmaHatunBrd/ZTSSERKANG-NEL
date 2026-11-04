"""Reçete versiyonları ve fire önceliği: satır override > grup > malzeme > tip > 0."""
from datetime import date
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import ReceteSatiri as MotorSatir
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

ONCELIK = {"grup": 10, "malzeme": 20, "tip": 30}


def _ondalik_veya_none(x) -> Decimal | None:
    return None if x is None else Decimal(x)


def _metin_veya_none(x) -> str | None:
    """Elle Z/S / para birimi: kırpılmış büyük harf; boşsa None (karttaki değer kullanılır)."""
    x = (x or "").strip().upper()
    return x or None


def yeni_versiyon(s: Session, urun_id: int, senaryo_id: int, satirlar: list[dict], kaynak: str, kullanici: str = "sistem") -> m.Recete:
    if not satirlar:
        raise DogrulamaHatasi("reçete boş olamaz")
    for eski in s.scalars(select(m.Recete).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True)):
        eski.aktif = False
    son = s.scalar(select(func.max(m.Recete.versiyon)).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id)) or 0
    r = m.Recete(urun_id=urun_id, senaryo_id=senaryo_id, versiyon=son + 1, kaynak=kaynak, aktif=True, olusturan=kullanici)
    r.satirlar = [m.ReceteSatiri(sira=i + 1, malzeme_kodu=d["malzeme_kodu"], ad=d.get("ad", ""), miktar=Decimal(d["miktar"]), birim=d.get("birim"),
                                 fire_override=None if d.get("fire_override") is None else Decimal(d["fire_override"]),
                                 dugum_tipi=d.get("dugum_tipi", "yaprak"),
                                 brut_miktar_elle=_ondalik_veya_none(d.get("brut_miktar_elle")),
                                 birim_fiyat_elle=_ondalik_veya_none(d.get("birim_fiyat_elle")),
                                 seviye=d.get("seviye"), zs_elle=_metin_veya_none(d.get("zs_elle")),
                                 para_birimi_elle=_metin_veya_none(d.get("para_birimi_elle"))) for i, d in enumerate(satirlar)]
    s.add(r); s.flush()
    return r


def kurallara_birak(s: Session, urun_id: int, senaryo_id: int, siralar: list[int] | None, kullanici: str = "sistem",
                    elle_degerleri_kaldir: bool = False) -> m.Recete:
    """Aktif reçeteyi yeni versiyon olarak kopyalar; verilen satırlarda (None: hepsi) fire_override boşaltılır, fire kurallardan gelir.
    elle_degerleri_kaldir=True ise aynı satırlarda brut_miktar_elle de boşaltılır (varsayılan: elle değerler korunur)."""
    r = aktif_recete(s, urun_id, senaryo_id)
    secili = set(range(1, len(r.satirlar) + 1)) if siralar is None else set(siralar)
    gecersiz = sorted(secili - {x.sira for x in r.satirlar})
    if gecersiz:
        raise DogrulamaHatasi("reçetede olmayan satır sırası", {"siralar": gecersiz})
    satirlar = [{"malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": x.miktar, "birim": x.birim, "dugum_tipi": x.dugum_tipi,
                 "fire_override": None if x.sira in secili else x.fire_override,
                 "brut_miktar_elle": None if (elle_degerleri_kaldir and x.sira in secili) else x.brut_miktar_elle,
                 "birim_fiyat_elle": x.birim_fiyat_elle, "seviye": x.seviye, "zs_elle": x.zs_elle,
                 "para_birimi_elle": x.para_birimi_elle} for x in r.satirlar]
    return yeni_versiyon(s, urun_id, senaryo_id, satirlar, "elle", kullanici)


def versiyonlar(s: Session, urun_id: int, senaryo_id: int) -> list[m.Recete]:
    return list(s.scalars(select(m.Recete).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id).order_by(m.Recete.versiyon.desc())))


def recete_getir(s: Session, recete_id: int) -> m.Recete:
    r = s.get(m.Recete, recete_id)
    if r is None:
        raise BulunamadiHatasi("reçete yok", {"recete_id": recete_id})
    return r


def gruplar_listele(s: Session) -> list[m.MalzemeGrubu]:
    return list(s.scalars(select(m.MalzemeGrubu).order_by(m.MalzemeGrubu.id)))


def aktif_recete_veya_none(s: Session, urun_id: int, senaryo_id: int) -> m.Recete | None:
    """Ürünün senaryodaki aktif reçetesi; yoksa None (ürün senaryonun üyesi değil)."""
    return s.scalar(select(m.Recete).where(m.Recete.urun_id == urun_id, m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True))


def aktif_recete(s: Session, urun_id: int, senaryo_id: int) -> m.Recete:
    r = aktif_recete_veya_none(s, urun_id, senaryo_id)
    if r is None:
        raise BulunamadiHatasi("aktif reçete yok", {"urun_id": urun_id, "senaryo_id": senaryo_id})
    return r


def fire_kurali_ekle(s: Session, senaryo_id: int, kapsam_tipi: str, kapsam_deger: str, oran: Decimal, gecerlilik_basi: date, neden: str,
                     oncelik: int | None = None, olusturan: str = "sistem") -> m.FireKurali:
    if kapsam_tipi not in ONCELIK:
        raise DogrulamaHatasi("kapsam_tipi tip|grup|malzeme olmalı", {"kapsam_tipi": kapsam_tipi})
    k = m.FireKurali(senaryo_id=senaryo_id, kapsam_tipi=kapsam_tipi, kapsam_deger=kapsam_deger, oran=Decimal(oran),
                     oncelik=ONCELIK[kapsam_tipi] if oncelik is None else oncelik, gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(k); s.flush()
    return k


def fire_kurallari(s: Session, senaryo_id: int) -> list[m.FireKurali]:
    return list(s.scalars(select(m.FireKurali).where(m.FireKurali.senaryo_id == senaryo_id)
                          .order_by(m.FireKurali.gecerlilik_basi.desc(), m.FireKurali.id.desc())))


def grup_olustur(s: Session, ad: str, malzeme_kodlari: list[str]) -> m.MalzemeGrubu:
    g = m.MalzemeGrubu(ad=ad)
    g.uyeler = [m.MalzemeGrubuUyesi(malzeme_kodu=k) for k in malzeme_kodlari]
    s.add(g); s.flush()
    return g


def _gecerli_kurallar(s: Session, senaryo_id: int, tarih: date) -> dict[tuple[str, str], m.FireKurali]:
    q = (select(m.FireKurali).where(m.FireKurali.senaryo_id == senaryo_id, m.FireKurali.gecerlilik_basi <= tarih)
         .order_by(m.FireKurali.gecerlilik_basi.desc(), m.FireKurali.id.desc()))
    out: dict[tuple[str, str], m.FireKurali] = {}
    for k in s.scalars(q):
        out.setdefault((k.kapsam_tipi, k.kapsam_deger), k)
    return out


def _gruplar(s: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for g in s.scalars(select(m.MalzemeGrubu)):
        for u in g.uyeler:
            out.setdefault(u.malzeme_kodu, []).append(g.ad)
    return out


def fire_uygulanmis(s: Session, recete: m.Recete, senaryo_id: int, tarih: date,
                    malzeme_tipleri: dict[str, str | None], brut_elle_yoksay: frozenset[int] = frozenset()) -> tuple[list[MotorSatir], list[str]]:
    """brut_elle_yoksay: elle brüt değeri geçici yok sayılacak 1 tabanlı satır sıraları (what-if override); fire kaynağı kurallardan çözülür."""
    kurallar = _gecerli_kurallar(s, senaryo_id, tarih)
    gruplar = _gruplar(s)
    satirlar, kaynaklar = [], []
    kayitlar = list(recete.satirlar)
    for i, rs_ in enumerate(kayitlar):
        sonraki = kayitlar[i + 1].seviye if i + 1 < len(kayitlar) else None
        alt_satiri_var = rs_.seviye is not None and sonraki is not None and sonraki > rs_.seviye
        brut_elle = None if rs_.sira in brut_elle_yoksay else rs_.brut_miktar_elle
        if rs_.fire_override is not None:
            oran, kaynak = rs_.fire_override, "satir"
        else:
            adaylar: list[tuple[int, Decimal, str]] = []
            for g in gruplar.get(rs_.malzeme_kodu, []):
                if ("grup", g) in kurallar:
                    adaylar.append((kurallar[("grup", g)].oncelik, kurallar[("grup", g)].oran, f"grup:{g}"))
            if ("malzeme", rs_.malzeme_kodu) in kurallar:
                k = kurallar[("malzeme", rs_.malzeme_kodu)]; adaylar.append((k.oncelik, k.oran, "malzeme"))
            tip = malzeme_tipleri.get(rs_.malzeme_kodu)
            if tip and ("tip", tip) in kurallar:
                k = kurallar[("tip", tip)]; adaylar.append((k.oncelik, k.oran, f"tip:{tip}"))
            if adaylar:
                _, oran, kaynak = min(adaylar, key=lambda a: a[0])
            else:
                oran, kaynak = SIFIR, "yok"
        if brut_elle is not None:
            kaynak = "elle"
        satirlar.append(MotorSatir(malzeme_kodu=rs_.malzeme_kodu, ad=rs_.ad, miktar=rs_.miktar, fire_orani=oran, birim=rs_.birim,
                                   dugum_tipi=rs_.dugum_tipi, brut_miktar_elle=brut_elle, birim_fiyat_elle=rs_.birim_fiyat_elle,
                                   alt_satiri_var=alt_satiri_var, zs_elle=rs_.zs_elle, para_birimi_elle=rs_.para_birimi_elle))
        kaynaklar.append(kaynak)
    return satirlar, kaynaklar
