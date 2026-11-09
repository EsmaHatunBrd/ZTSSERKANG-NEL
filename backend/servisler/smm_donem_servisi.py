"""Maliyet muhasebesi: Excel'siz yeni dönem açma ve dönem devri.

Yeni dönemin dönem başı stoku (DBS) önceki dönemin sayımla bulunan dönem sonu stokudur: miktar = önceki sayım, tutar = önceki dönem
sonu stok değerlemesi (smm_ozet_servisi._dss; Excel DSS ile aynı kural). Stok kartları, üretim süreleri ve dağıtım havuzları önceki
dönemden kopyalanır; alım, iade, satış, üretim ve sayım boş başlar (sonradan yüklenir/girilir). Reçete kaynağı kalıcı reçetelerdir."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .hatalar import CatismaHatasi, DogrulamaHatasi
from .smm_asama_servisi import _Baglam
from .smm_ozet_servisi import _dss
from .smm_servisi import AY_ADLARI, SIFIR, donem_adi, donem_cikis, donem_getir, kilit_denetle

KAYNAKLAR = ("excel", "ana")


def onceki_donem(s: Session, yil: int, ay: int) -> m.SmmDonem | None:
    return s.scalar(select(m.SmmDonem).where((m.SmmDonem.yil * 12 + m.SmmDonem.ay) < yil * 12 + ay)
                    .order_by(m.SmmDonem.yil.desc(), m.SmmDonem.ay.desc()))


def yeni_donem(s: Session, yil: int, ay: int, kullanici: str = "sistem") -> dict:
    if not (2000 <= yil <= 2100 and 1 <= ay <= 12):
        raise DogrulamaHatasi("dönem geçersiz", {"yil": yil, "ay": ay})
    if s.scalar(select(m.SmmDonem).where(m.SmmDonem.yil == yil, m.SmmDonem.ay == ay)) is not None:
        raise CatismaHatasi(f"{AY_ADLARI[ay]} {yil} dönemi zaten var")
    onceki = onceki_donem(s, yil, ay)
    d = m.SmmDonem(yil=yil, ay=ay, olusturan=kullanici, recete_kaynagi="ana", finansman=SIFIR,
                   devir_donem_id=onceki.id if onceki else None,
                   dagitim=dict(onceki.dagitim) if onceki and onceki.dagitim else None)
    s.add(d)
    s.flush()
    devir_tutar = SIFIR
    kalem_sayisi = devir_kalem = 0
    if onceki is not None:
        b = _Baglam(s, onceki)
        dss = _dss(b)
        for kod, k in b.kalem.items():
            sayim = k.sayim_miktar or SIFIR
            tutar = dss[kod]["tutar"] if sayim else SIFIR
            s.add(m.SmmKalem(donem_id=d.id, kod=kod, ad=k.ad, birim=k.birim, tur=k.tur, mizan_kodu=k.mizan_kodu, envanterde=k.envanterde,
                             uretim_asamasi=k.uretim_asamasi, dbs_miktar=sayim, dbs_tutar=tutar, olusturan=kullanici))
            kalem_sayisi += 1
            if sayim:
                devir_kalem += 1
                devir_tutar += tutar
        for x in s.scalars(select(m.SmmIscilik).where(m.SmmIscilik.donem_id == onceki.id)):
            s.add(m.SmmIscilik(donem_id=d.id, kod=x.kod, mamul_kod=x.mamul_kod, yari_mamul_kod=x.yari_mamul_kod, ad=x.ad,
                               vardiya_uretim=x.vardiya_uretim, dolum_isci=x.dolum_isci, etiket_isci=x.etiket_isci, dolum_sn=x.dolum_sn,
                               dolum_adam_sn=x.dolum_adam_sn, etiket_sn=x.etiket_sn, etiket_adam_sn=x.etiket_adam_sn, olusturan=kullanici))
    d.excel_kontrol = None
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="ekle", eski=None, kullanici=kullanici,
                            yeni={"donem": donem_adi(d), "devir": donem_adi(onceki) if onceki else None, "devir_kalem": devir_kalem,
                                  "devir_tutar": str(devir_tutar)}))
    s.flush()
    return {**donem_cikis(d, kalem_sayisi), "devir": {"onceki": donem_adi(onceki) if onceki else None, "kalem": devir_kalem,
                                                       "tutar": str(devir_tutar)}}


def recete_kaynagi(s: Session, donem_id: int, kaynak: str, kullanici: str = "sistem") -> dict:
    if kaynak not in KAYNAKLAR:
        raise DogrulamaHatasi("reçete kaynağı 'excel' ya da 'ana' olmalı", {"kaynak": kaynak})
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    if kaynak == "excel" and s.scalar(select(m.SmmReceteSatiri.id).where(m.SmmReceteSatiri.donem_id == d.id).limit(1)) is None:
        raise DogrulamaHatasi("bu dönemle Excel reçetesi yüklenmedi; yalnız kalıcı reçeteler kullanılabilir")
    if kaynak == "ana" and s.scalar(select(m.SmmAnaRecete.id).limit(1)) is None:
        raise DogrulamaHatasi("kalıcı reçete yok; önce Reçeteler sayfasından Canias dökümünü yükleyin")
    eski = d.recete_kaynagi or "excel"
    if eski != kaynak:
        d.recete_kaynagi = kaynak
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="recete_kaynagi", eski={"kaynak": eski}, yeni={"kaynak": kaynak},
                                kullanici=kullanici))
        s.flush()
    return donem_cikis(d)
