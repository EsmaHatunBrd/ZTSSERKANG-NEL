"""Append-only parametre değerleri. Geçerli değer = gecerlilik_basi <= tarih olan en yeni kayıt; ürün override geneli ezer."""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.modeller import Parametreler
from ..depo import modeller as m
from . import liste_kurallari as lk
from .hatalar import DogrulamaHatasi, PARAMETRE_EKSIK, liste_metni

ZORUNLU = ("enflasyon", "satis_kar", "vardiya_saati")
# Anahtara özgü değer doğrulaması (422): liste bölenleri 0 < b <= 1, yuvarlama adımı izinli kümeden.
EVET_HAYIR = ("satis_ortalama_maliyetten",)   # birim "evet_hayir": yalnız 0 ya da 1


def evet_hayir_dogrula(deger) -> Decimal:
    d = Decimal(str(deger))
    if d not in (0, 1):
        raise DogrulamaHatasi("Bu parametre yalnız 0 (hayır) ya da 1 (evet) olabilir.", {"deger": str(deger)})
    return Decimal(int(d))


DOGRULAYICILAR = {**{a: lk.bolen_dogrula for a in lk.BOLEN_ANAHTARLARI.values()}, lk.YUVARLAMA_ANAHTARI: lk.yuvarlama_dogrula,
                  **{a: evet_hayir_dogrula for a in EVET_HAYIR}}


# Değer sınırları (422): yanlış birimle girilen değerin (ör. %25 yerine 25 = %2.500) maliyeti uçurmasını önler.
YUZDE_UST = Decimal(3)                                   # oran türü parametreler en çok 3 (= %300)
NEGATIF_OLABILIR = ("enflasyon", "maliyet_sapma")         # bunlar -1'den büyük (> -%100) olabilir; diğer oranlar en az 0
VARDIYA_UST = Decimal(24)
YUZDE_ANAHTARLARI = ("enflasyon", "satis_kar", "maliyet_sapma", "marj_esigi")
YUZDE_ONEKLERI = ("faiz.", "teklif_kar.", "fiyat_uyari_esigi.")
OLAGAN_DISI_ORAN = Decimal(1)                            # uyarı (Veri Kontrolü / arayüz onayı): oran %100'ün üstü


def _okunur_ad(p: m.Parametre) -> str:
    """Açıklamanın parantezsiz ilk kısmı ("Satış fiyatı kâr oranı"); açıklama boşsa tohum tanımındaki açıklama, o da yoksa anahtar."""
    aciklama = p.aciklama
    if not aciklama:
        from ..tohum import PARAMETRELER   # yerel içe aktarma: tohum servisleri içe aktarır
        aciklama = next((ac for a, ac, _ in PARAMETRELER if a == p.anahtar), None) or p.anahtar
    return aciklama.split(" (")[0].split(":")[0].strip()


def yuzde_mi(anahtar: str, birim: str | None) -> bool:
    """Kullanıcıya yüzde olarak gösterilen oran parametresi mi? Liste bölenleri (0,63 gibi) oran birimli ama yüzde değildir."""
    if anahtar in lk.BOLEN_ANAHTARLARI.values():
        return False
    return birim == "oran" or anahtar in YUZDE_ANAHTARLARI or anahtar.startswith(YUZDE_ONEKLERI)   # birim boş kalmış eski tanımlar için


def sinir_hatasi(anahtar: str, birim: str | None, deger: Decimal, ad: str | None = None) -> str | None:
    """Değer izinli aralıkta değilse sade Türkçe mesaj; değilse None. Bölen / yuvarlama / evet-hayır kendi doğrulayıcısıyla denetlenir."""
    ad = ad or anahtar
    if not deger.is_finite():
        return f"{ad} için geçerli bir sayı girin."
    if anahtar.startswith("kur."):
        return None if deger > 0 else f"{ad} 0'dan büyük olmalı."
    if anahtar == "vardiya_saati":
        return None if Decimal(0) < deger <= VARDIYA_UST else f"{ad} 0'dan büyük, en çok 24 saat olmalı."
    if yuzde_mi(anahtar, birim):
        alt_tamam = deger > -1 if anahtar in NEGATIF_OLABILIR else deger >= 0
        if alt_tamam and deger <= YUZDE_UST:
            return None
        aralik = "-%100'den büyük, en çok %300" if anahtar in NEGATIF_OLABILIR else "%0 ile %300 arasında"
        return f"{ad} {aralik} olmalı."
    return None


def olagan_disi(anahtar: str, birim: str | None, deger: Decimal) -> str | None:
    """Kaydedilmiş ama olağan dışı görünen değer (Veri Kontrolü 'dikkat'); değilse None. Kayıt sınırı dışındaki eski değerler de yakalanır."""
    if not deger.is_finite():
        return "değer sayı değil"
    if anahtar.startswith("kur."):
        return "kur 0 ya da eksi" if deger <= 0 else None
    if anahtar == "vardiya_saati":
        return None if Decimal(0) < deger <= VARDIYA_UST else "vardiya saati 0 ile 24 arasında değil"
    if yuzde_mi(anahtar, birim):
        if deger > OLAGAN_DISI_ORAN:
            return "%100'ün üstünde"
        if deger < 0 and anahtar not in NEGATIF_OLABILIR:
            return "eksi değer"
        if deger <= -1:
            return "-%100 ya da altında"
    return None


def _parametre(s: Session, anahtar: str) -> m.Parametre:
    p = s.scalar(select(m.Parametre).where(m.Parametre.anahtar == anahtar))
    if p is None:
        raise DogrulamaHatasi(f"Bilinmeyen parametre: {anahtar}.", {"anahtar": anahtar})
    return p


def olagan_disi_degerler(s: Session, senaryo_id: int, tarih: date) -> list[dict]:
    """Tarihte geçerli (genel ve ürün kapsamlı) parametre değerlerinden olağan dışı olanlar: anahtar, ad, birim, kapsam_tipi, kapsam_id,
    deger, neden (olagan_disi metni). Anahtar sırasıyla, genel önce."""
    tanim = {p.anahtar: p for p in tanimlar(s)}
    gorulen: set[tuple[str, str, int | None]] = set()
    out = []
    for anahtar, kapsam_tipi, kapsam_id, deger in parametre_satirlari(s, senaryo_id, tarih):   # en yeni önce: ilk görülen geçerlidir
        k = (anahtar, kapsam_tipi, kapsam_id if kapsam_tipi == "urun" else None)
        if k in gorulen:
            continue
        gorulen.add(k)
        p = tanim.get(anahtar)
        if p is None or anahtar in DOGRULAYICILAR:
            continue
        if (neden := olagan_disi(anahtar, p.birim, Decimal(deger))):
            out.append({"anahtar": anahtar, "ad": _okunur_ad(p), "birim": p.birim, "kapsam_tipi": kapsam_tipi, "kapsam_id": k[2],
                        "deger": Decimal(deger), "neden": neden})
    out.sort(key=lambda x: (x["anahtar"], x["kapsam_tipi"] != "genel", x["kapsam_id"] or 0))
    return out


def tanimlar(s: Session) -> list[m.Parametre]:
    return list(s.scalars(select(m.Parametre).order_by(m.Parametre.id)))


def deger_ekle(s: Session, senaryo_id: int, anahtar: str, deger: Decimal, gecerlilik_basi: date, neden: str,
               kapsam_tipi: str = "genel", kapsam_id: int | None = None, olusturan: str = "sistem") -> m.ParametreDegeri:
    if kapsam_tipi not in ("genel", "urun") or (kapsam_tipi == "urun" and kapsam_id is None):
        raise DogrulamaHatasi("Parametre kapsamı genel ya da ürün olmalı.", {"kapsam_tipi": kapsam_tipi})
    p = _parametre(s, anahtar)
    if anahtar in DOGRULAYICILAR:
        deger = DOGRULAYICILAR[anahtar](deger)
    else:
        try:
            d = Decimal(str(deger))
        except ArithmeticError:
            raise DogrulamaHatasi(f"{_okunur_ad(p)} için geçerli bir sayı girin.") from None
        if (mesaj := sinir_hatasi(anahtar, p.birim, d, _okunur_ad(p))):
            raise DogrulamaHatasi(mesaj)
    kayit = m.ParametreDegeri(parametre_id=p.id, senaryo_id=senaryo_id, kapsam_tipi=kapsam_tipi,
                              kapsam_id=kapsam_id, deger=Decimal(deger), gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(kayit); s.flush()
    return kayit


def gecmis(s: Session, senaryo_id: int, anahtar: str) -> list[m.ParametreDegeri]:
    q = (select(m.ParametreDegeri).join(m.Parametre).where(m.Parametre.anahtar == anahtar, m.ParametreDegeri.senaryo_id == senaryo_id)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    return list(s.scalars(q))


ParametreSatirlari = list[tuple[str, str, int | None, Decimal]]   # (anahtar, kapsam_tipi, kapsam_id, deger) — geçerlilik sırasına göre (en yeni önce)


def parametre_satirlari(s: Session, senaryo_id: int, tarih: date) -> ParametreSatirlari:
    """Senaryoda tarihte geçerli olabilecek tüm parametre kayıtları, tek sorgu. toplu_hesapla bunu bir kez çeker; ürün başına
    `degerleri_coz` ile çözülür (eskiden 67 ürün × aynı sorgu)."""
    q = (select(m.ParametreDegeri, m.Parametre.anahtar).join(m.Parametre)
         .where(m.ParametreDegeri.senaryo_id == senaryo_id, m.ParametreDegeri.gecerlilik_basi <= tarih)
         .order_by(m.ParametreDegeri.gecerlilik_basi.desc(), m.ParametreDegeri.id.desc()))
    return [(anahtar, kayit.kapsam_tipi, kayit.kapsam_id, kayit.deger) for kayit, anahtar in s.execute(q)]


def degerleri_coz(satirlar: ParametreSatirlari, urun_id: int | None = None) -> dict[str, Decimal]:
    """Genel kapsam + (verilmişse) ürün kapsamı; her anahtar için en yeni kayıt; ürün kapsamı geneli ezer."""
    genel: dict[str, Decimal] = {}
    urun: dict[str, Decimal] = {}
    for anahtar, kapsam_tipi, kapsam_id, deger in satirlar:
        if kapsam_tipi == "urun":
            if urun_id is not None and kapsam_id == urun_id:
                urun.setdefault(anahtar, deger)
        else:
            genel.setdefault(anahtar, deger)
    return {**genel, **urun}


def gecerli_degerler(s: Session, senaryo_id: int, tarih: date, urun_id: int | None = None) -> dict[str, Decimal]:
    return degerleri_coz(parametre_satirlari(s, senaryo_id, tarih), urun_id)


def _grup(d: dict[str, Decimal], onek: str) -> dict[str, Decimal]:
    return {k[len(onek):]: v for k, v in d.items() if k.startswith(onek)}


def gecerli_parametreler(s: Session, senaryo_id: int, tarih: date, urun_id: int | None = None,
                         satirlar: ParametreSatirlari | None = None) -> Parametreler:
    """`satirlar` verilmişse (toplu hesap önbelleği) sorgu yinelenmez."""
    d = degerleri_coz(satirlar, urun_id) if satirlar is not None else gecerli_degerler(s, senaryo_id, tarih, urun_id)
    eksik = [z for z in ZORUNLU if z not in d]
    if eksik:
        raise DogrulamaHatasi(f"Bu çalışmada zorunlu parametreler girilmemiş: {liste_metni(eksik)}; Parametreler ekranından girin.", {"eksik": eksik}, kod=PARAMETRE_EKSIK)
    teklif = _grup(d, "teklif_kar.")
    return Parametreler(
        enflasyon=d["enflasyon"], kurlar=_grup(d, "kur."), faiz_oranlari=_grup(d, "faiz."), stok_sureleri_ay=_grup(d, "stok_ay."),
        satis_kar_orani=d["satis_kar"], teklif_kar_oranlari=tuple(teklif[k] for k in sorted(teklif, key=int)),
        vardiya_saati=d["vardiya_saati"])


METIN_ANAHTARLARI = ("satis_fiyati_notu",)


def metin_deger_ekle(s: Session, senaryo_id: int, anahtar: str, deger: str, gecerlilik_basi: date, neden: str, olusturan: str = "sistem") -> m.MetinParametre:
    if anahtar not in METIN_ANAHTARLARI:
        raise DogrulamaHatasi(f"Bilinmeyen metin parametresi: {anahtar}.", {"anahtar": anahtar})
    if not (neden or "").strip():
        raise DogrulamaHatasi("Neden girin.")
    k = m.MetinParametre(senaryo_id=senaryo_id, anahtar=anahtar, deger=deger, gecerlilik_basi=gecerlilik_basi, neden=neden, olusturan=olusturan)
    s.add(k); s.flush()
    return k


def _metin_sirali(s: Session, senaryo_id: int):
    return (select(m.MetinParametre).where(m.MetinParametre.senaryo_id == senaryo_id)
            .order_by(m.MetinParametre.gecerlilik_basi.desc(), m.MetinParametre.id.desc()))


def metin_gecmis(s: Session, senaryo_id: int, anahtar: str | None = None) -> list[m.MetinParametre]:
    q = _metin_sirali(s, senaryo_id)
    if anahtar is not None:
        q = q.where(m.MetinParametre.anahtar == anahtar)
    return list(s.scalars(q))


def metin_gecerli(s: Session, senaryo_id: int, tarih: date) -> list[m.MetinParametre]:
    """Her anahtar için tarihte geçerli (gecerlilik_basi <= tarih, en yeni) kayıt; anahtar sırasına göre."""
    gorulen: dict[str, m.MetinParametre] = {}
    for k in s.scalars(_metin_sirali(s, senaryo_id).where(m.MetinParametre.gecerlilik_basi <= tarih)):
        gorulen.setdefault(k.anahtar, k)
    return [gorulen[a] for a in sorted(gorulen)]
