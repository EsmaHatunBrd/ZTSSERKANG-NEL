"""Maliyet muhasebesi: Excel'siz yeni dönem açma ve dönem devri.

Yeni dönemin dönem başı stoku (DBS) önceki dönemin sayımla bulunan dönem sonu stokudur: miktar = önceki sayım, tutar = önceki dönem
sonu stok değerlemesi (smm_ozet_servisi._dss; Excel DSS ile aynı kural). Stok kartları, üretim süreleri ve dağıtım havuzları önceki
dönemden kopyalanır; alım, iade, satış, üretim ve sayım boş başlar (sonradan yüklenir/girilir). Reçete kaynağı kalıcı reçetelerdir."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import CatismaHatasi, DogrulamaHatasi
from .smm_asama_servisi import _Baglam
from .smm_ozet_servisi import _dss
from .smm_servisi import AY_ADLARI, SIFIR, donem_adi, donem_cikis, donem_getir, kilit_denetle

KAYNAKLAR = ("excel", "ana")
DEVIR_TOLERANSI = Decimal("0.01")   # açılış ile önceki kapanış arasında kabul edilen fark (miktar ve TL)
DEVIR_ORNEK = 20


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
    uyari = f"{donem_adi(onceki)} kapatılmadı; devir sonradan değişebilir" if onceki is not None and not onceki.kilitli else None
    return {**donem_cikis(d, kalem_sayisi), "devir": {"onceki": donem_adi(onceki) if onceki else None, "kalem": devir_kalem,
                                                       "tutar": str(devir_tutar), "uyari": uyari}}


# ---------------------------------------------------------------- devir: önceki ayın kapanışı = bu ayın açılışı
def devir_kaynagi(s: Session, d: m.SmmDonem) -> m.SmmDonem | None:
    """Dönem başı stokun devralındığı dönem (yeni_donem ile açılanlarda); Excel'den yüklenen ya da kaynağı silinmiş dönemde None."""
    return s.get(m.SmmDonem, d.devir_donem_id) if d.devir_donem_id else None


def sonraki_donemler(s: Session, d: m.SmmDonem) -> list[m.SmmDonem]:
    """Açılışını bu dönemden devralmış dönemler."""
    return list(s.scalars(select(m.SmmDonem).where(m.SmmDonem.devir_donem_id == d.id).order_by(m.SmmDonem.yil, m.SmmDonem.ay)))


def _kapanis(s: Session, onceki: m.SmmDonem) -> dict[str, tuple[Decimal, Decimal, m.SmmKalem]]:
    """Önceki dönemin ŞU ANKİ kapanışı, kalem başına (miktar = sayım, tutar = dönem sonu stok değerlemesi); yeni_donem ile aynı kural."""
    b = _Baglam(s, onceki)
    dss = _dss(b)
    out = {}
    for kod, k in b.kalem.items():
        sayim = k.sayim_miktar or SIFIR
        out[kod] = (sayim, dss[kod]["tutar"] if sayim else SIFIR, k)
    return out


def _farkli(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) > DEVIR_TOLERANSI


def _elle_dbs_kodlari(s: Session, d: m.SmmDonem) -> set[str]:
    """Dönem başı miktarı / tutarı ekrandan elle girilmiş ya da düzeltilmiş kalemler (smm_stok_servisi'nin değişiklik kayıtları).
    Elle değerleri ezen son devir yenilemesinden önceki kayıtlar sayılmaz."""
    son_ez = 0
    for x in s.scalars(select(m.DegisiklikKaydi).where(m.DegisiklikKaydi.tablo == "smm_donem", m.DegisiklikKaydi.kayit_id == d.id,
                                                       m.DegisiklikKaydi.islem == "devir_yenile")):
        if (x.yeni or {}).get("elle_ez"):
            son_ez = max(son_ez, x.id)
    q = (select(m.SmmKalem.kod, m.DegisiklikKaydi.yeni)
         .join(m.DegisiklikKaydi, m.DegisiklikKaydi.kayit_id == m.SmmKalem.id)
         .where(m.SmmKalem.donem_id == d.id, m.DegisiklikKaydi.tablo == "smm_kalem", m.DegisiklikKaydi.islem.in_(("guncelle", "ekle")),
                m.DegisiklikKaydi.id > son_ez))
    return {kod for kod, yeni in s.execute(q) if "dbs_miktar" in (yeni or {}) or "dbs_tutar" in (yeni or {})}


def _donem_kalemleri(s: Session, d: m.SmmDonem) -> dict[str, m.SmmKalem]:
    return {k.kod: k for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id))}


def _devir_farklari(s: Session, d: m.SmmDonem, onceki: m.SmmDonem) -> tuple[list[dict], Decimal, Decimal]:
    """Açılışı (dbs) önceki kapanıştan farklı kalemler + açılış ve kapanış toplam tutarı."""
    kapanis = _kapanis(s, onceki)
    kalemler = _donem_kalemleri(s, d)
    farklar = []
    acilis_toplam = kapanis_toplam = SIFIR
    for kod in sorted(set(kapanis) | set(kalemler)):
        k = kalemler.get(kod)
        am, at = (k.dbs_miktar or SIFIR, k.dbs_tutar or SIFIR) if k is not None else (SIFIR, SIFIR)
        km, kt, ko = kapanis.get(kod, (SIFIR, SIFIR, None))
        acilis_toplam += at
        kapanis_toplam += kt
        if _farkli(am, km) or _farkli(at, kt):
            farklar.append({"kod": kod, "ad": (k.ad if k is not None else None) or (ko.ad if ko is not None else None),
                            "acilis_miktar": am, "kapanis_miktar": km, "acilis_tutar": at, "kapanis_tutar": kt})
    return farklar, acilis_toplam, kapanis_toplam


def devir_durumu(s: Session, donem_id: int) -> dict:
    """Bu dönemin açılış stoku (dbs miktar / tutar) devraldığı dönemin şu anki kapanışıyla (sayım + dönem sonu stok tutarı) aynı mı.
    `fark_tutar` = açılış toplamı − kapanış toplamı (net). Elle düzeltilmiş açılışlar da fark sayılır; `elle_kalem` kaçının öyle olduğunu
    söyler. `ornek`: TL farkı en büyük ilk 20 kalem."""
    d = donem_getir(s, donem_id)
    onceki = devir_kaynagi(s, d)
    if onceki is None:
        return {"onceki": None, "uyumlu": True, "fark_kalem": 0, "fark_tutar": "0", "acilis_tutar": None, "kapanis_tutar": None,
                "elle_kalem": 0, "ornek": []}
    farklar, acilis, kapanis = _devir_farklari(s, d, onceki)
    elle = _elle_dbs_kodlari(s, d) if farklar else set()
    for f in farklar:
        f["elle"] = f["kod"] in elle
    farklar.sort(key=lambda f: (-abs(f["acilis_tutar"] - f["kapanis_tutar"]), f["kod"]))
    return decimal_str({"onceki": {"id": onceki.id, "ad": donem_adi(onceki), "kilitli": bool(onceki.kilitli)}, "uyumlu": not farklar,
                        "fark_kalem": len(farklar), "fark_tutar": acilis - kapanis, "acilis_tutar": acilis, "kapanis_tutar": kapanis,
                        "elle_kalem": sum(1 for f in farklar if f["elle"]), "ornek": farklar[:DEVIR_ORNEK]})


def devir_ozeti(s: Session, d: m.SmmDonem) -> dict | None:
    """Veri kontrol listesi için kısa devir durumu; devir kaynağı yoksa None."""
    onceki = devir_kaynagi(s, d)
    if onceki is None:
        return None
    farklar, acilis, kapanis = _devir_farklari(s, d, onceki)
    return decimal_str({"uyumlu": not farklar, "fark_kalem": len(farklar), "fark_tutar": acilis - kapanis, "onceki_ad": donem_adi(onceki),
                        "onceki_kilitli": bool(onceki.kilitli)})


def devir_yenile(s: Session, donem_id: int, neden: str | None, elle_ez: bool = False, kullanici: str = "sistem") -> dict:
    """Açılış stokunu devralınan dönemin güncel kapanışından yeniden yazar. Önceki dönemde olup burada olmayan kalem eklenir; önceki
    dönemde olmayan kalemin açılışı sıfırlanır. Elle girilmiş açılış değerleri korunur (`elle_ez` ile onlar da ezilir). Eski değerler
    değişiklik kaydında saklanır."""
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu")
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    onceki = devir_kaynagi(s, d)
    if onceki is None:
        raise DogrulamaHatasi("bu dönemin açılışı bir önceki dönemden devralınmamış; yenilenecek devir yok")
    kapanis = _kapanis(s, onceki)
    kalemler = _donem_kalemleri(s, d)
    elle = _elle_dbs_kodlari(s, d)
    eski_toplam = sum((k.dbs_tutar or SIFIR for k in kalemler.values()), SIFIR)
    yeni_toplam = SIFIR
    eski_degerler: dict[str, list[str]] = {}
    guncellenen = eklenen = elle_kalem = 0
    for kod in sorted(set(kapanis) | set(kalemler)):
        km, kt, ko = kapanis.get(kod, (SIFIR, SIFIR, None))
        k = kalemler.get(kod)
        if k is None:
            s.add(m.SmmKalem(donem_id=d.id, kod=kod, ad=ko.ad, birim=ko.birim, tur=ko.tur, mizan_kodu=ko.mizan_kodu, envanterde=ko.envanterde,
                             uretim_asamasi=ko.uretim_asamasi, dbs_miktar=km, dbs_tutar=kt, olusturan=kullanici))
            eklenen += 1
            yeni_toplam += kt
            continue
        if _farkli(k.dbs_miktar or SIFIR, km) or _farkli(k.dbs_tutar or SIFIR, kt):
            korunur = False
            if kod in elle:
                elle_kalem += 1
                korunur = not elle_ez
            if not korunur:
                eski_degerler[kod] = [str(k.dbs_miktar or SIFIR), str(k.dbs_tutar or SIFIR)]
                k.dbs_miktar, k.dbs_tutar = km, kt
                guncellenen += 1
        yeni_toplam += k.dbs_tutar or SIFIR
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="devir_yenile", kullanici=kullanici,
                            eski={"dbs_tutar": str(eski_toplam), "kalemler": eski_degerler},
                            yeni={"donem": donem_adi(d), "onceki": donem_adi(onceki), "neden": neden.strip(), "guncellenen": guncellenen,
                                  "eklenen": eklenen, "elle_kalem": elle_kalem, "elle_ez": bool(elle_ez), "dbs_tutar": str(yeni_toplam)}))
    s.flush()
    return {"donem": donem_cikis(d), "guncellenen": guncellenen, "eklenen": eklenen, "elle_kalem": elle_kalem,
            "elle_korundu": elle_kalem > 0 and not elle_ez, "durum": devir_durumu(s, donem_id)}


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
