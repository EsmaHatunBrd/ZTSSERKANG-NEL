"""Senaryo yönetimi: kopyalama (geçen sezondan), ad/sezon/açıklama güncelleme, silme ve senaryo üyeliği.

Üyelik: bir ürün, o senaryoda **aktif reçetesi** varsa senaryonun üyesidir; dashboard/uyarılar/dışa aktarım yalnız üyeleri alır.
Kopya: kaynaktaki bugün geçerli kayıtlar tek kayıt olarak yeni senaryoya yazılır (kaynak="kopya", neden "Kopya: <kaynak adı>");
kayıtlı hesaplar, teklifler ve kilit kopyalanmaz. Yalnız aktif ürünlerin reçete/hedef/kapasitesi kopyalanır (pasif kart yeni sezona taşınmaz).
Tek işlem: servis yalnız flush eder; commit/rollback oturum sahibinin (router: `oturum_ver`) işidir — ara adımda hata olursa istek
geri alınır, hiçbir şey kalmaz (SQLite/pysqlite'ta SAVEPOINT güvenilir olmadığından bilerek begin_nested kullanılmaz).
Silme: yalnız kayıtlı hesabı olmayan ve kilitsiz senaryo; öncesinde dosya veritabanında otomatik yedek alınır; senaryoya bağlı
günlük satırları silinir, yerine tek bir "senaryo silindi" kaydı (kim/ne zaman/ne silindi/yedek adı) yazılır.
"""
from datetime import date
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from ..depo.yedek import silme_oncesi_yedek_al
from . import fiyat_servisi, hesap_servisi, parametre_servisi, recete_servisi
from .hatalar import CatismaHatasi, DogrulamaHatasi

SECIMLER = ("receteler", "fiyatlar", "parametreler", "gider", "uretim", "fire_kurallari")
SAYI_ANAHTARLARI = ("recete", "fiyat", "parametre", "metin", "havuz", "ambalaj", "hedef", "kapasite", "fire")


def uye_urun_kodlari(s: Session, senaryo_id: int, aktif: bool = True) -> set[str]:
    """Senaryoda aktif reçetesi olan ürünlerin kodları (varsayılan: yalnız aktif ürün kartları)."""
    q = select(m.Urun.kod).join(m.Recete, m.Recete.urun_id == m.Urun.id).where(m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True)
    if aktif:
        q = q.where(m.Urun.aktif == True)
    return set(s.scalars(q.distinct()))


def uye_sayilari(s: Session) -> dict[int, int]:
    """{senaryo_id: üye (aktif reçeteli, aktif) ürün sayısı}; tek sorgu, senaryo listesi için."""
    q = (select(m.Recete.senaryo_id, func.count(func.distinct(m.Recete.urun_id))).join(m.Urun, m.Urun.id == m.Recete.urun_id)
         .where(m.Recete.aktif == True, m.Urun.aktif == True).group_by(m.Recete.senaryo_id))
    return {sid: n for sid, n in s.execute(q)}


def _neden_denetle(neden: str | None) -> str:
    if not (neden or "").strip():
        raise DogrulamaHatasi("neden zorunlu")
    return neden.strip()


def kopyala(s: Session, kaynak_id: int, sezon_ad: str, ad: str, tur: str, aciklama: str | None, secimler: dict[str, bool], neden: str,
            kullanici: str = "sistem", tarih: date | None = None) -> tuple[m.Senaryo, dict[str, int]]:
    """Kaynak senaryodan seçilen bölümleri yeni senaryoya kopyalar; (yeni senaryo, sayılar) döner.
    secimler: {receteler, fiyatlar, parametreler, gider, uretim, fire_kurallari} -> bool (eksik anahtar False sayılır).
    `tarih` (varsayılan bugün): append-only tablolarda o tarihte geçerli kayıt kopyalanır."""
    neden = _neden_denetle(neden)
    bilinmeyen = sorted(set(secimler) - set(SECIMLER))
    if bilinmeyen:
        raise DogrulamaHatasi("bilinmeyen kopya seçimi", {"secimler": bilinmeyen})
    kaynak = hesap_servisi.senaryo_getir(s, kaynak_id)
    tarih = tarih or date.today()
    sec = {k: bool(secimler.get(k)) for k in SECIMLER}
    kopya_neden = f"Kopya: {kaynak.ad}"
    sayilar = {k: 0 for k in SAYI_ANAHTARLARI}
    yeni = hesap_servisi.senaryo_olustur(s, sezon_ad, tur, ad, aciklama, kullanici)
    if sec["receteler"]:
        sayilar["recete"] = _receteleri_kopyala(s, kaynak.id, yeni.id, kullanici)
    if sec["fiyatlar"]:
        sayilar["fiyat"] = _fiyatlari_kopyala(s, kaynak.id, yeni.id, tarih, kopya_neden, kullanici)
    if sec["parametreler"]:
        sayilar["parametre"] = _parametreleri_kopyala(s, kaynak.id, yeni.id, tarih, kopya_neden, kullanici)
        sayilar["metin"] = _metinleri_kopyala(s, kaynak.id, yeni.id, tarih, kopya_neden, kullanici)
    if sec["gider"]:
        sayilar["havuz"] = _havuzlari_kopyala(s, kaynak.id, yeni.id, kullanici)
        sayilar["ambalaj"] = _ambalajlari_kopyala(s, kaynak.id, yeni.id, kullanici)
    if sec["uretim"]:
        sayilar["hedef"] = _hedefleri_kopyala(s, kaynak.id, yeni.id, kullanici)
        sayilar["kapasite"] = _kapasiteleri_kopyala(s, kaynak.id, yeni.id, kullanici)
    if sec["fire_kurallari"]:
        sayilar["fire"] = _fire_kurallarini_kopyala(s, kaynak.id, yeni.id, tarih, kopya_neden, kullanici)
    s.add(m.DegisiklikKaydi(tablo="senaryo", kayit_id=yeni.id, islem="kopyala", eski=None,
                            yeni={**sayilar, "kaynak_senaryo_id": kaynak.id, "kaynak_senaryo_ad": kaynak.ad, "_neden": neden}, kullanici=kullanici))
    s.flush()
    return yeni, sayilar


def _aktif_urun_idleri(s: Session) -> set[int]:
    return set(s.scalars(select(m.Urun.id).where(m.Urun.aktif == True)))


def _receteleri_kopyala(s: Session, kaynak_id: int, hedef_id: int, kullanici: str) -> int:
    n = 0
    aktif = _aktif_urun_idleri(s)
    for r in s.scalars(select(m.Recete).where(m.Recete.senaryo_id == kaynak_id, m.Recete.aktif == True).order_by(m.Recete.urun_id)):
        if r.urun_id not in aktif:
            continue   # pasif ürün kartı: reçetesi yeni sezona taşınmaz (urun_sayisi ile tutarlı)
        yeni = m.Recete(urun_id=r.urun_id, senaryo_id=hedef_id, versiyon=1, kaynak="kopya", aktif=True, olusturan=kullanici)
        yeni.satirlar = [m.ReceteSatiri(sira=x.sira, malzeme_kodu=x.malzeme_kodu, ad=x.ad, miktar=x.miktar, birim=x.birim, fire_override=x.fire_override,
                                        dugum_tipi=x.dugum_tipi, brut_miktar_elle=x.brut_miktar_elle, birim_fiyat_elle=x.birim_fiyat_elle, seviye=x.seviye,
                                        zs_elle=x.zs_elle, para_birimi_elle=x.para_birimi_elle, olusturan=kullanici) for x in r.satirlar]
        s.add(yeni); n += 1
    s.flush()
    return n


def _fiyatlari_kopyala(s: Session, kaynak_id: int, hedef_id: int, tarih: date, neden: str, kullanici: str) -> int:
    kayitlar = fiyat_servisi._gecerli_kayitlar(s, kaynak_id, tarih)
    for k in kayitlar.values():
        s.add(m.MalzemeFiyati(malzeme_id=k.malzeme_id, senaryo_id=hedef_id, fiyat=k.fiyat, para_birimi=k.para_birimi, gecerlilik_basi=k.gecerlilik_basi,
                              kaynak="kopya", neden=neden, olusturan=kullanici))
    s.flush()
    return len(kayitlar)


def _parametreleri_kopyala(s: Session, kaynak_id: int, hedef_id: int, tarih: date, neden: str, kullanici: str) -> int:
    """Her (parametre, kapsam) için tarihte geçerli tek kayıt; ürün kapsamlı değerler de kopyalanır (ürün kartları globaldir)."""
    q = (select(m.ParametreDegeri).where(m.ParametreDegeri.senaryo_id == kaynak_id, m.ParametreDegeri.gecerlilik_basi <= tarih)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    gecerli: dict[tuple, m.ParametreDegeri] = {}
    for k in s.scalars(q):
        gecerli.setdefault((k.parametre_id, k.kapsam_tipi, k.kapsam_id), k)
    for k in gecerli.values():
        s.add(m.ParametreDegeri(parametre_id=k.parametre_id, senaryo_id=hedef_id, kapsam_tipi=k.kapsam_tipi, kapsam_id=k.kapsam_id, deger=k.deger,
                                gecerlilik_basi=k.gecerlilik_basi, neden=neden, olusturan=kullanici))
    s.flush()
    return len(gecerli)


def _metinleri_kopyala(s: Session, kaynak_id: int, hedef_id: int, tarih: date, neden: str, kullanici: str) -> int:
    kayitlar = parametre_servisi.metin_gecerli(s, kaynak_id, tarih)
    for k in kayitlar:
        s.add(m.MetinParametre(senaryo_id=hedef_id, anahtar=k.anahtar, deger=k.deger, gecerlilik_basi=k.gecerlilik_basi, neden=neden, olusturan=kullanici))
    s.flush()
    return len(kayitlar)


def _havuzlari_kopyala(s: Session, kaynak_id: int, hedef_id: int, kullanici: str) -> int:
    n = 0
    for h in s.scalars(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == kaynak_id).order_by(m.GiderHavuzu.id)):
        yeni = m.GiderHavuzu(senaryo_id=hedef_id, kod=h.kod, ad=h.ad, toplam_tutar=h.toplam_tutar, baz_tipi=h.baz_tipi, baz_miktar=h.baz_miktar,
                             taban_tutar=h.taban_tutar, carpanlar=list(h.carpanlar) if h.carpanlar else None, olusturan=kullanici)
        yeni.anahtarlar = [m.DagitimAnahtari(alt_kalem=a.alt_kalem, pay_orani=a.pay_orani, baz_miktar=a.baz_miktar, olusturan=kullanici) for a in h.anahtarlar]
        s.add(yeni); n += 1
    s.flush()
    return n


def _ambalajlari_kopyala(s: Session, kaynak_id: int, hedef_id: int, kullanici: str) -> int:
    n = 0
    for a in s.scalars(select(m.AmbalajSinifi).where(m.AmbalajSinifi.senaryo_id == kaynak_id).order_by(m.AmbalajSinifi.id)):
        s.add(m.AmbalajSinifi(senaryo_id=hedef_id, ad=a.ad, hacim=a.hacim, uretim_adedi=a.uretim_adedi, katsayi=a.katsayi, olusturan=kullanici)); n += 1
    s.flush()
    return n


def _hedefleri_kopyala(s: Session, kaynak_id: int, hedef_id: int, kullanici: str) -> int:
    n = 0
    aktif = _aktif_urun_idleri(s)
    for h in s.scalars(select(m.UretimHedefi).where(m.UretimHedefi.senaryo_id == kaynak_id).order_by(m.UretimHedefi.id)):
        if h.urun_id not in aktif:
            continue
        s.add(m.UretimHedefi(urun_id=h.urun_id, senaryo_id=hedef_id, olusturan=kullanici, gider_elle=h.gider_elle,
                             **{a: getattr(h, a) for a in hesap_servisi.URETIM_ALANLARI})); n += 1
    s.flush()
    return n


def _kapasiteleri_kopyala(s: Session, kaynak_id: int, hedef_id: int, kullanici: str) -> int:
    from .kapasite_servisi import SAYISAL_ALANLAR
    pasif_kodlar = set(s.scalars(select(m.Urun.kod).where(m.Urun.aktif == False)))   # kartı olmayan kodlar (yalnız sayfa satırı) kopyalanır
    n = 0
    for k in s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == kaynak_id).order_by(m.UretimKapasitesi.id)):
        if k.urun_kodu in pasif_kodlar:
            continue
        s.add(m.UretimKapasitesi(senaryo_id=hedef_id, urun_kodu=k.urun_kodu, urun_ad=k.urun_ad, olusturan=kullanici,
                                 **{a: getattr(k, a) for a in SAYISAL_ALANLAR})); n += 1
    s.flush()
    return n


def _fire_kurallarini_kopyala(s: Session, kaynak_id: int, hedef_id: int, tarih: date, neden: str, kullanici: str) -> int:
    kurallar = recete_servisi._gecerli_kurallar(s, kaynak_id, tarih)
    for k in kurallar.values():
        s.add(m.FireKurali(senaryo_id=hedef_id, kapsam_tipi=k.kapsam_tipi, kapsam_deger=k.kapsam_deger, oran=k.oran, oncelik=k.oncelik,
                           gecerlilik_basi=k.gecerlilik_basi, neden=neden, olusturan=kullanici))
    s.flush()
    return len(kurallar)


GUNCELLENEBILIR = ("sezon_ad", "ad", "aciklama")


def guncelle(s: Session, senaryo_id: int, alanlar: dict, neden: str, kullanici: str = "sistem") -> m.Senaryo:
    """alanlar: yalnız gönderilen anahtarlar (sezon_ad, ad, aciklama) değişir; kilitli senaryoda KilitliHatasi (409)."""
    from . import import_servisi
    neden = _neden_denetle(neden)
    sen = hesap_servisi.senaryo_getir(s, senaryo_id)
    hesap_servisi.kilit_denetle(sen)
    bilinmeyen = sorted(set(alanlar) - set(GUNCELLENEBILIR))
    if bilinmeyen:
        raise DogrulamaHatasi("bilinmeyen senaryo alanı", {"alanlar": bilinmeyen})
    if "ad" in alanlar and not (alanlar["ad"] or "").strip():
        raise DogrulamaHatasi("senaryo adı boş olamaz", {"ad": alanlar["ad"]})
    eski, yeni = {}, {}
    if "sezon_ad" in alanlar and alanlar["sezon_ad"] != sen.sezon.ad:
        sezon = import_servisi.sezon_getir_veya_olustur(s, alanlar["sezon_ad"])
        eski["sezon_ad"], yeni["sezon_ad"] = sen.sezon.ad, sezon.ad
        sen.sezon_id = sezon.id; sen.sezon = sezon
    if "ad" in alanlar and alanlar["ad"].strip() != sen.ad:
        eski["ad"], yeni["ad"] = sen.ad, alanlar["ad"].strip()
        sen.ad = yeni["ad"]
    if "aciklama" in alanlar and (alanlar["aciklama"] or None) != (sen.aciklama or None):
        eski["aciklama"], yeni["aciklama"] = sen.aciklama, alanlar["aciklama"] or None
        sen.aciklama = yeni["aciklama"]
    if yeni:
        s.add(m.DegisiklikKaydi(tablo="senaryo", kayit_id=sen.id, islem="guncelle", eski=eski, yeni={**yeni, "_neden": neden}, kullanici=kullanici))
        s.flush()
    return sen


def _yedek_url(s: Session) -> str | None:
    try:
        return s.get_bind().engine.url.render_as_string(hide_password=False)   # Engine ya da Connection bağı
    except Exception:   # noqa: BLE001 — bağsız/olağandışı oturum: yedek atlanır
        return None


def sil(s: Session, senaryo_id: int, yedek_url: str | None = None, kullanici: str = "sistem") -> dict:
    """Senaryoyu ve ona bağlı tüm satırları siler. Kilitli ya da kayıtlı hesabı varsa CatismaHatasi (409).
    Silmeden önce dosya veritabanında `yedek/<tarih>-silme-oncesi-<ad>.db` alınır (bellek içi DB'de atlanır).
    Senaryoya bağlı değişiklik günlüğü kayıtları silinir (yedekte kalır); yerine tek "senaryo silindi" kaydı (kim/ne zaman/sayılar/yedek) yazılır.
    Dönüş: {"yedek": yol|None, "silinen": {tablo: sayı}}."""
    sen = hesap_servisi.senaryo_getir(s, senaryo_id)
    if sen.kilitli:
        raise CatismaHatasi("senaryo kilitli; silmek için önce kilidi açın", {"senaryo_id": sen.id})
    hesap_sayisi = s.scalar(select(func.count()).select_from(m.MaliyetHesabi).where(m.MaliyetHesabi.senaryo_id == sen.id)) or 0
    if hesap_sayisi:
        raise CatismaHatasi(f"senaryoda {hesap_sayisi} kayıtlı hesap var; kayıtlı hesabı olan senaryo silinemez", {"senaryo_id": sen.id, "hesap_sayisi": hesap_sayisi})
    yedek = silme_oncesi_yedek_al(yedek_url or _yedek_url(s) or "", sen.ad)

    silinen: dict[str, int] = {}
    havuz_idleri = select(m.GiderHavuzu.id).where(m.GiderHavuzu.senaryo_id == sen.id)
    recete_idleri = select(m.Recete.id).where(m.Recete.senaryo_id == sen.id)
    hedef_idleri = select(m.UretimHedefi.id).where(m.UretimHedefi.senaryo_id == sen.id)
    kapasite_idleri = select(m.UretimKapasitesi.id).where(m.UretimKapasitesi.senaryo_id == sen.id)
    stok_idleri = select(m.StokDevri.id).where(m.StokDevri.senaryo_id == sen.id)
    gunluk_kosulu = (
        ((m.DegisiklikKaydi.tablo.in_(("senaryo", "ambalaj_sinifi"))) & (m.DegisiklikKaydi.kayit_id == sen.id))
        | ((m.DegisiklikKaydi.tablo == "gider_havuzu") & m.DegisiklikKaydi.kayit_id.in_(havuz_idleri))
        | ((m.DegisiklikKaydi.tablo == "recete") & m.DegisiklikKaydi.kayit_id.in_(recete_idleri))
        | ((m.DegisiklikKaydi.tablo == "uretim_hedefi") & m.DegisiklikKaydi.kayit_id.in_(hedef_idleri))
        | ((m.DegisiklikKaydi.tablo == "uretim_kapasitesi") & m.DegisiklikKaydi.kayit_id.in_(kapasite_idleri))
        | ((m.DegisiklikKaydi.tablo == "stok_devri") & m.DegisiklikKaydi.kayit_id.in_(stok_idleri)))
    silinen["degisiklik_kaydi"] = s.execute(delete(m.DegisiklikKaydi).where(gunluk_kosulu)).rowcount
    silinen["dagitim_anahtari"] = s.execute(delete(m.DagitimAnahtari).where(m.DagitimAnahtari.gider_havuzu_id.in_(havuz_idleri))).rowcount
    silinen["recete_satiri"] = s.execute(delete(m.ReceteSatiri).where(m.ReceteSatiri.recete_id.in_(recete_idleri))).rowcount
    for tablo in (m.GiderHavuzu, m.Recete, m.ParametreDegeri, m.MalzemeFiyati, m.AmbalajSinifi, m.UretimHedefi, m.FireKurali, m.MetinParametre, m.UretimKapasitesi, m.StokDevri):
        silinen[tablo.__tablename__] = s.execute(delete(tablo).where(tablo.senaryo_id == sen.id)).rowcount
    from . import excel_sablon_deposu   # müşavir Excel'i şablonu (yüklenen kitabın kopyası) senaryoyla birlikte gider; yedekte kalır
    excel_sablon_deposu.sil(s, "fiyat_kitabi", str(sen.id))
    kimlik = {"ad": sen.ad, "sezon_ad": sen.sezon.ad, "tur": sen.tur, "aciklama": sen.aciklama}
    s.delete(sen)
    s.flush()
    # günlükte okunur: "ad: …; sezon_ad: …; silinen_satir: N; yedek: …" (eski=None -> tüm alanlar gösterilir); ayrıntı tablo bazında
    s.add(m.DegisiklikKaydi(tablo="senaryo", kayit_id=senaryo_id, islem="sil", eski=None,
                            yeni={**kimlik, "silinen_satir": sum(silinen.values()), "yedek": None if yedek is None else yedek.name, "ayrinti": silinen},
                            kullanici=kullanici))
    s.flush()
    return {"yedek": None if yedek is None else str(yedek), "silinen": silinen}
