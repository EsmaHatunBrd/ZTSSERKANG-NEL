"""Satış geçmişi: 'geçen yıl kaça sattım' karşılaştırması için ürün başına satış satırları. Tutarlar Decimal."""
from datetime import date
from decimal import Decimal
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, DogrulamaHatasi

PARA_BIRIMLERI = ("TL", "USD", "EUR", "GBP", "CHF", "RUB", "ZAR")
MAKS_MUSTERI = 200


def _hatalar(urun, musteri, tarih, fiyat, para_birimi, adet, degerler: bool = True) -> list[str]:
    """`degerler=False`: tarih/fiyat/adet okuyucuda zaten başarısız (None) — yinelenen mesaj üretilmez."""
    h = []
    if urun is None:
        h.append("ürün bulunamadı")
    if not (musteri or "").strip():
        h.append("müşteri boş olamaz")
    elif len(musteri.strip()) > MAKS_MUSTERI:
        h.append(f"müşteri {MAKS_MUSTERI} karakterden uzun")
    if para_birimi not in PARA_BIRIMLERI:
        h.append(f"para birimi {'/'.join(PARA_BIRIMLERI)} olmalı")
    if degerler:
        if not isinstance(tarih, date):
            h.append("tarih geçersiz")
        if fiyat is None or fiyat < 0:
            h.append("fiyat 0 veya büyük olmalı")
        if adet is None or adet <= 0:
            h.append("adet 0'dan büyük olmalı")
    else:
        if fiyat is not None and fiyat < 0:
            h.append("fiyat 0 veya büyük olmalı")
        if adet is not None and adet <= 0:
            h.append("adet 0'dan büyük olmalı")
    return h


def _urun(s: Session, kod: str) -> m.Urun | None:
    return s.scalar(select(m.Urun).where(m.Urun.kod == (kod or "").strip()))


def _yaz(s: Session, urun: m.Urun, musteri: str, tarih: date, fiyat: Decimal, para_birimi: str, adet: Decimal, kullanici: str, denetim: bool = True,
         neden: str | None = None) -> m.SatisGecmisi:
    k = m.SatisGecmisi(urun_id=urun.id, musteri=musteri.strip(), tarih=tarih, fiyat=fiyat, para_birimi=para_birimi, adet=adet, olusturan=kullanici)
    s.add(k); s.flush()
    if denetim:
        yeni = decimal_str({"urun_kodu": urun.kod, "musteri": k.musteri, "tarih": tarih, "fiyat": fiyat, "para_birimi": para_birimi, "adet": adet})
        s.add(m.DegisiklikKaydi(tablo="satis_gecmisi", kayit_id=k.id, islem="ekle", eski=None, kullanici=kullanici,
                                yeni={**yeni, "_neden": neden} if neden else yeni))
    return k


def _cikis(k: m.SatisGecmisi, urun: m.Urun) -> dict:
    return {"id": k.id, "urun_kodu": urun.kod, "urun_ad": urun.ad, "musteri": k.musteri, "tarih": k.tarih.isoformat(),
            "fiyat": str(k.fiyat), "para_birimi": k.para_birimi, "adet": str(k.adet), "olusturan": k.olusturan}


def _icerir(kolon, metin: str):
    """Büyük/küçük harf duyarsız 'içerir'. SQLite lower() yalnız ASCII bildiğinden Türkçe harfler için girilen/küçük/baş harfi büyük biçimler de denenir."""
    q = metin.strip()
    varyantlar = {q, q.lower(), q.capitalize(), q.upper()}
    return or_(func.lower(kolon).contains(q.lower(), autoescape=True), *(kolon.contains(v, autoescape=True) for v in varyantlar))


def listele(s: Session, urun_kodu: str | None = None, musteri: str | None = None, bas: date | None = None, son: date | None = None,
            sayfa: int = 1, boyut: int = 50) -> tuple[list[dict], int]:
    q = select(m.SatisGecmisi, m.Urun).join(m.Urun, m.Urun.id == m.SatisGecmisi.urun_id)
    if urun_kodu and urun_kodu.strip():
        q = q.where(_icerir(m.Urun.kod, urun_kodu))
    if musteri and musteri.strip():
        q = q.where(_icerir(m.SatisGecmisi.musteri, musteri))
    if bas:
        q = q.where(m.SatisGecmisi.tarih >= bas)
    if son:
        q = q.where(m.SatisGecmisi.tarih <= son)
    toplam = s.scalar(select(func.count()).select_from(q.subquery()))
    satirlar = s.execute(q.order_by(m.SatisGecmisi.tarih.desc(), m.SatisGecmisi.id.desc()).offset((sayfa - 1) * boyut).limit(boyut)).all()
    return [_cikis(k, u) for k, u in satirlar], toplam


def ekle(s: Session, urun_kodu: str, musteri: str, tarih: date, fiyat: Decimal, para_birimi: str, adet: Decimal, kullanici: str = "sistem",
         neden: str | None = None) -> dict:
    """Elle tek satır. `neden` Değişiklik Günlüğü'ne yazılır (API ucunda zorunlu)."""
    urun = _urun(s, urun_kodu)
    if urun is None:
        raise BulunamadiHatasi(f"{urun_kodu} kodlu ürün bulunamadı.", {"urun_kodu": urun_kodu})
    para_birimi = (para_birimi or "").strip().upper()
    h = _hatalar(urun, musteri, tarih, fiyat, para_birimi, adet)
    if h:
        raise DogrulamaHatasi(f"Satış satırı kaydedilmedi: {'; '.join(h)}.", {"hatalar": h})
    return _cikis(_yaz(s, urun, musteri, tarih, fiyat, para_birimi, adet, kullanici, neden=neden), urun)


def _anahtar(urun_id: int, musteri: str, tarih: date, fiyat: Decimal, adet: Decimal) -> tuple:
    return (urun_id, (musteri or "").strip().casefold(), tarih, Decimal(fiyat).normalize(), Decimal(adet).normalize())


def _kayitli_sayaci(s: Session, urun_idleri: set[int]) -> dict[tuple, int]:
    """Sistemdeki satış satırları (ürün, müşteri, tarih, fiyat, adet) anahtarına göre adet (aynı satır birden çok kez kayıtlı olabilir)."""
    sayac: dict[tuple, int] = {}
    if not urun_idleri:
        return sayac
    for k in s.scalars(select(m.SatisGecmisi).where(m.SatisGecmisi.urun_id.in_(urun_idleri))):
        a = _anahtar(k.urun_id, k.musteri, k.tarih, k.fiyat, k.adet)
        sayac[a] = sayac.get(a, 0) + 1
    return sayac


def _ayikla(s: Session, satirlar: list[dict]) -> tuple[list[dict], list[tuple]]:
    """(hatalar, geçerli satırlar [(satır, ürün, para)])."""
    hatalar: list[dict] = []
    gecerli = []
    onbellek: dict[str, m.Urun | None] = {}
    for r in satirlar:
        kod = (r.get("urun_kodu") or "").strip()
        if kod not in onbellek:
            onbellek[kod] = _urun(s, kod)
        urun = onbellek[kod]
        okuyucu_hatasi = list(r.get("hatalar") or [])
        para = (r.get("para_birimi") or "").strip().upper()
        mesajlar = okuyucu_hatasi + _hatalar(urun, r.get("musteri"), r.get("tarih"), r.get("fiyat"), para, r.get("adet"), degerler=not okuyucu_hatasi)
        if mesajlar:
            hatalar.append({"satir_no": r["satir_no"], "mesaj": "; ".join(mesajlar)})
        else:
            gecerli.append((r, urun, para))
    return hatalar, gecerli


def _kayitlilari_ayir(s: Session, gecerli: list[tuple]) -> tuple[list[tuple], list[tuple]]:
    """(eklenecek, zaten kayıtlı). Sistemde aynı (ürün, müşteri, tarih, fiyat, adet) satırı kaç kez varsa dosyadaki o kadar satır kayıtlı
    sayılır (aynı gün aynı fiyatla iki ayrı fatura dosyada iki kez geçebilir; fazlası eklenir)."""
    sayac = _kayitli_sayaci(s, {u.id for _, u, _ in gecerli})
    eklenecek, kayitli = [], []
    for x in gecerli:
        r, u, _ = x
        a = _anahtar(u.id, r["musteri"], r["tarih"], r["fiyat"], r["adet"])
        if sayac.get(a, 0) > 0:
            sayac[a] -= 1
            kayitli.append(x)
        else:
            eklenecek.append(x)
    return eklenecek, kayitli


def onizle(s: Session, satirlar: list[dict]) -> dict:
    """Hiçbir şey yazmaz: eklenecek, zaten kayıtlı (atlanacak) ve hatalı satırlar."""
    from .yukleme_guvenligi import ozet, sorunlu
    hatalar, gecerli = _ayikla(s, satirlar)
    eklenecek, kayitli = _kayitlilari_ayir(s, gecerli)
    uyarilar = []
    if kayitli:
        uyarilar.append(f"{len(kayitli)} satır zaten kayıtlı (aynı ürün, müşteri, tarih, fiyat, adet); atlanacak.")
    if hatalar:
        uyarilar.append("Hatalı satırlar düzeltilmeden hiçbir satır eklenmez.")
    oz = ozet(okunan=len(satirlar), yeni=len(eklenecek), ayni=len(kayitli), atlanan=len(kayitli) + len(hatalar),
              sorunlu_satirlar=[sorunlu(h["satir_no"], None, None, None, h["mesaj"]) for h in hatalar], uyarilar=uyarilar)
    return {"okunan": len(satirlar), "eklenecek": len(eklenecek), "kayitli": len(kayitli), "hatalar": hatalar, "ozet": oz}


def toplu_yukle(s: Session, satirlar: list[dict], kullanici: str = "sistem", dosya_adi: str = "",
                kayitlilari_da_ekle: bool = False) -> tuple[int, list[dict]]:
    """Tek işlem: herhangi bir satır hatalıysa hiçbiri yazılmaz. `satirlar` öğeleri satis_okuyucu çıktısı biçimindedir.
    Sistemde zaten kayıtlı satırlar (ürün, müşteri, tarih, fiyat, adet) varsayılan olarak atlanır (aynı dosya iki kez yüklenince ikilenmez).
    Denetim: satır başına değil, toplu işlem başına TEK DegisiklikKaydi (islem=toplu_yukle; adet ve dosya adı). Yazmadan önce yedek.
    Dönüş: (eklenen, hatalar[{satir_no, mesaj}]); hata varsa eklenen = 0. Atlanan sayısı için `toplu_yukle_ayrintili`."""
    eklenen, hatalar, _ = toplu_yukle_ayrintili(s, satirlar, kullanici, dosya_adi, kayitlilari_da_ekle)
    return eklenen, hatalar


def toplu_yukle_ayrintili(s: Session, satirlar: list[dict], kullanici: str = "sistem", dosya_adi: str = "",
                          kayitlilari_da_ekle: bool = False) -> tuple[int, list[dict], int]:
    """(eklenen, hatalar, atlanan_kayitli)."""
    from .yukleme_guvenligi import GENEL, yedek_guncelle, yedekle
    hatalar, gecerli = _ayikla(s, satirlar)
    if hatalar:
        return 0, hatalar, 0
    eklenecek, kayitli = (gecerli, []) if kayitlilari_da_ekle else _kayitlilari_ayir(s, gecerli)
    y = yedekle(s, "satis_gecmisi", GENEL, {"eklenen_idler": []}, f"{len(eklenecek)} satış satırı", (dosya_adi or None), kullanici) \
        if eklenecek else None
    idler = [_yaz(s, urun, r["musteri"], r["tarih"], r["fiyat"], para, r["adet"], kullanici, denetim=False).id for r, urun, para in eklenecek]
    if y is not None:
        yedek_guncelle(y, eklenen_idler=idler)
    if eklenecek:
        s.add(m.DegisiklikKaydi(tablo="satis_gecmisi", kayit_id=0, islem="toplu_yukle", eski=None, kullanici=kullanici,
                                yeni={"eklenen": len(eklenecek), "atlanan_kayitli": len(kayitli), "dosya": (dosya_adi or "")[:200]}))
        s.flush()
    return len(eklenecek), [], len(kayitli)


def sil(s: Session, id: int, kullanici: str = "sistem", neden: str | None = None) -> None:
    """Satış kaydı kalıcı silinir (append-only değil); silinen içerik DegisiklikKaydi.eski içinde saklanır."""
    k = s.get(m.SatisGecmisi, id)
    if k is None:
        raise BulunamadiHatasi("Satış kaydı bulunamadı.", {"id": id})
    urun = s.get(m.Urun, k.urun_id)
    s.add(m.DegisiklikKaydi(tablo="satis_gecmisi", kayit_id=k.id, islem="sil", yeni={"_neden": neden} if neden else None, kullanici=kullanici,
                            eski=decimal_str({"urun_kodu": urun.kod if urun else None, "musteri": k.musteri, "tarih": k.tarih, "fiyat": k.fiyat,
                                              "para_birimi": k.para_birimi, "adet": k.adet})))
    s.delete(k)
    s.flush()
