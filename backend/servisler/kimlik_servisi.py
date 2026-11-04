"""Giriş, oturum ve roller. Hesaplar uygulamanın kendi veritabanındadır (internetsiz çalışır).

- Şifre: hashlib.scrypt (tuzlu; geri çözülemez). Biçim `scrypt$n$r$p$tuz_hex$karma_hex`.
- Oturum: rastgele belirteç tarayıcıda httpOnly çerezde, veritabanında yalnız SHA-256 karması. Süresi dolmaz; çıkışta, kullanıcı
  pasifleştirilince ya da şifresi sıfırlanınca kapanır.
- Art arda HATALI_SINIR hatalı denemede hesap KILIT_DAKIKA dakika kilitlenir.
- Roller: genel_direktor (her şey + kullanıcı yönetimi), muhasebe (her şey), satin_alma (malzeme kartı ve fiyatları), izleyici (salt okunur).
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi, KimlikHatasi, YetkiHatasi

ROLLER = {"genel_direktor": "Genel Direktör", "muhasebe": "Muhasebe", "satin_alma": "Satın alma", "izleyici": "İzleyici"}
YONETICI_ROL = "genel_direktor"
HATALI_SINIR = 5
KILIT_DAKIKA = 15
EN_KISA_SIFRE = 8
_SCRYPT = (2 ** 14, 8, 1)
_KULLANICI_ADI = re.compile(r"^[a-z0-9._-]{3,64}$")

# Veri yazmayan POST'lar: her rol kullanabilir (önizleme hesabı, aktarım önizlemeleri).
_SALT_OKUNUR_POST = re.compile(r"(/hesapla|/onizle|/import/fiyat-listesi)$")
# Satın alma rolünün yazabildiği uçlar: malzeme kartı, fiyatları, fiyat listesi ve S.ALMA BF aktarımı.
_SATIN_ALMA_YAZAR = re.compile(r"^/api/v1/(malzemeler(/[^/]+/(fiyatlar|pasif))?|import/fiyat-listesi/uygula|satin-alma/uygula)$")
_YAZMA = ("POST", "PUT", "PATCH", "DELETE")


def _simdi() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)   # SQLite saat dilimi tutmaz: UTC saklanır


def sifre_karma(sifre: str) -> str:
    n, r, p = _SCRYPT
    tuz = secrets.token_bytes(16)
    k = hashlib.scrypt(sifre.encode("utf-8"), salt=tuz, n=n, r=r, p=p)
    return f"scrypt${n}${r}${p}${tuz.hex()}${k.hex()}"


def sifre_dogru(sifre: str, karma: str) -> bool:
    try:
        _, n, r, p, tuz, beklenen = karma.split("$")
        k = hashlib.scrypt(sifre.encode("utf-8"), salt=bytes.fromhex(tuz), n=int(n), r=int(r), p=int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(k.hex(), beklenen)


def _belirtec_karma(belirtec: str) -> str:
    return hashlib.sha256(belirtec.encode("utf-8")).hexdigest()


def _sifre_denetle(sifre: str) -> None:
    if len(sifre) < EN_KISA_SIFRE:
        raise DogrulamaHatasi(f"şifre en az {EN_KISA_SIFRE} karakter olmalı", {"sifre": "kısa"})


def yazabilir_mi(rol: str, yontem: str, yol: str) -> bool:
    """Rolün bu isteği yapmaya izni var mı (okuma her rolde serbest; kullanıcı yönetimi ayrıca denetlenir)."""
    if yontem not in _YAZMA:
        return True
    yol = yol.rstrip("/")
    if yontem == "POST" and _SALT_OKUNUR_POST.search(yol):
        return True
    if rol in ("genel_direktor", "muhasebe"):
        return True
    if rol == "satin_alma":
        return bool(_SATIN_ALMA_YAZAR.match(yol))
    return False


def kullanici_olustur(s: Session, kullanici_adi: str, ad: str, rol: str, gecici_sifre: str, olusturan: str = "sistem",
                      sifre_degismeli: bool = True) -> m.Kullanici:
    kullanici_adi = kullanici_adi.strip().lower()
    if not _KULLANICI_ADI.match(kullanici_adi):
        raise DogrulamaHatasi("kullanıcı adı 3-64 karakter; yalnız küçük harf, rakam, nokta, tire, alt çizgi", {"kullanici_adi": kullanici_adi})
    if rol not in ROLLER:
        raise DogrulamaHatasi(f"bilinmeyen rol: {rol}", {"rol": rol})
    if not ad.strip():
        raise DogrulamaHatasi("ad boş olamaz", {"ad": ""})
    _sifre_denetle(gecici_sifre)
    if s.scalar(select(m.Kullanici.id).where(m.Kullanici.kullanici_adi == kullanici_adi)) is not None:
        raise CatismaHatasi("bu kullanıcı adı zaten var", {"kullanici_adi": kullanici_adi})
    k = m.Kullanici(kullanici_adi=kullanici_adi, ad=ad.strip(), rol=rol, sifre_karma=sifre_karma(gecici_sifre), aktif=True,
                    sifre_degismeli=sifre_degismeli, hatali_deneme=0, olusturan=olusturan)
    s.add(k); s.flush()
    s.add(m.DegisiklikKaydi(tablo="kullanici", kayit_id=k.id, islem="ekle", eski=None,
                            yeni={"kullanici_adi": k.kullanici_adi, "ad": k.ad, "rol": k.rol}, kullanici=olusturan))
    return k


def giris(s: Session, kullanici_adi: str, sifre: str) -> tuple[m.Kullanici, str]:
    """Doğruysa (kullanıcı, çerez belirteci). Yanlış ad ve yanlış şifre aynı mesajı verir (hangisinin yanlış olduğu sızmaz)."""
    k = s.scalar(select(m.Kullanici).where(m.Kullanici.kullanici_adi == kullanici_adi.strip().lower()))
    simdi = _simdi()
    if k is None or not k.aktif:
        raise KimlikHatasi("kullanıcı adı ya da şifre yanlış")
    if k.kilit_bitis is not None and k.kilit_bitis > simdi:
        dakika = max(1, int((k.kilit_bitis - simdi).total_seconds() // 60) + 1)
        raise KimlikHatasi(f"çok fazla hatalı deneme; {dakika} dakika sonra tekrar deneyin", kod="kilitli")
    if not sifre_dogru(sifre, k.sifre_karma):
        k.hatali_deneme = (k.hatali_deneme or 0) + 1
        if k.hatali_deneme >= HATALI_SINIR:
            k.kilit_bitis, k.hatali_deneme = simdi + timedelta(minutes=KILIT_DAKIKA), 0
        s.flush()
        raise KimlikHatasi("kullanıcı adı ya da şifre yanlış")
    k.hatali_deneme, k.kilit_bitis, k.son_giris = 0, None, simdi
    belirtec = secrets.token_urlsafe(32)
    s.add(m.GirisOturumu(belirtec_karma=_belirtec_karma(belirtec), kullanici_id=k.id, acik=True, son_kullanim=simdi,
                         olusturan=k.kullanici_adi))
    s.flush()
    return k, belirtec


def oturumdaki_kullanici(s: Session, belirtec: str | None) -> m.Kullanici:
    if not belirtec:
        raise KimlikHatasi("giriş yapılmamış")
    o = s.scalar(select(m.GirisOturumu).where(m.GirisOturumu.belirtec_karma == _belirtec_karma(belirtec)))
    if o is None or not o.acik or not o.kullanici.aktif:
        raise KimlikHatasi("oturum kapanmış; yeniden giriş yapın")
    simdi = _simdi()
    if o.son_kullanim is None or simdi - o.son_kullanim > timedelta(minutes=5):   # her istekte yazmamak için seyrek güncellenir
        o.son_kullanim = simdi
    return o.kullanici


def cikis(s: Session, belirtec: str | None) -> None:
    if belirtec:
        o = s.scalar(select(m.GirisOturumu).where(m.GirisOturumu.belirtec_karma == _belirtec_karma(belirtec)))
        if o is not None:
            o.acik = False


def _oturumlari_kapat(s: Session, kullanici_id: int, haric_belirtec: str | None = None) -> None:
    haric = _belirtec_karma(haric_belirtec) if haric_belirtec else None
    for o in s.scalars(select(m.GirisOturumu).where(m.GirisOturumu.kullanici_id == kullanici_id, m.GirisOturumu.acik == True)):  # noqa: E712
        if o.belirtec_karma != haric:
            o.acik = False


def sifre_degistir(s: Session, k: m.Kullanici, eski: str, yeni: str, belirtec: str | None) -> None:
    """Kendi şifresi. Bu oturum açık kalır, diğer cihazlardaki oturumlar kapanır."""
    if not sifre_dogru(eski, k.sifre_karma):
        raise DogrulamaHatasi("mevcut şifre yanlış", {"eski_sifre": "yanlış"})
    _sifre_denetle(yeni)
    if eski == yeni:
        raise DogrulamaHatasi("yeni şifre eskisiyle aynı olamaz", {"yeni_sifre": "aynı"})
    k.sifre_karma, k.sifre_degismeli = sifre_karma(yeni), False
    _oturumlari_kapat(s, k.id, haric_belirtec=belirtec)
    s.add(m.DegisiklikKaydi(tablo="kullanici", kayit_id=k.id, islem="sifre_degistir", eski=None, yeni={}, kullanici=k.kullanici_adi))
    s.flush()


def yonetici_denetle(k: m.Kullanici) -> None:
    if k.rol != YONETICI_ROL:
        raise YetkiHatasi("kullanıcı yönetimi yalnız Genel Direktör'e açık")


def listele(s: Session) -> list[m.Kullanici]:
    return list(s.scalars(select(m.Kullanici).order_by(m.Kullanici.aktif.desc(), m.Kullanici.ad)))


def _getir(s: Session, kullanici_id: int) -> m.Kullanici:
    k = s.get(m.Kullanici, kullanici_id)
    if k is None:
        raise BulunamadiHatasi("kullanıcı yok", {"kullanici_id": kullanici_id})
    return k


def _aktif_yonetici_sayisi(s: Session) -> int:
    return len(list(s.scalars(select(m.Kullanici.id).where(m.Kullanici.rol == YONETICI_ROL, m.Kullanici.aktif == True))))  # noqa: E712


def guncelle(s: Session, kullanici_id: int, yapan: str, ad: str | None = None, rol: str | None = None,
             aktif: bool | None = None) -> m.Kullanici:
    """Ad, rol, aktiflik. Son aktif Genel Direktör'ün rolü düşürülemez ve pasifleştirilemez (kimse kullanıcı yönetemez hale gelmesin)."""
    k = _getir(s, kullanici_id)
    eski = {"ad": k.ad, "rol": k.rol, "aktif": k.aktif}
    if rol is not None and rol not in ROLLER:
        raise DogrulamaHatasi(f"bilinmeyen rol: {rol}", {"rol": rol})
    if ad is not None and not ad.strip():
        raise DogrulamaHatasi("ad boş olamaz", {"ad": ""})
    yonetici_gidiyor = k.rol == YONETICI_ROL and k.aktif and ((rol is not None and rol != YONETICI_ROL) or aktif is False)
    if yonetici_gidiyor and _aktif_yonetici_sayisi(s) <= 1:
        raise CatismaHatasi("son aktif Genel Direktör'ün rolü değiştirilemez ya da pasifleştirilemez")
    if ad is not None:
        k.ad = ad.strip()
    if rol is not None:
        k.rol = rol
    if aktif is not None:
        k.aktif = aktif
        if not aktif:
            _oturumlari_kapat(s, k.id)
    yeni = {"ad": k.ad, "rol": k.rol, "aktif": k.aktif}
    if yeni != eski:
        s.add(m.DegisiklikKaydi(tablo="kullanici", kayit_id=k.id, islem="guncelle", eski=eski, yeni=yeni, kullanici=yapan))
    s.flush()
    return k


def sifre_sifirla(s: Session, kullanici_id: int, gecici_sifre: str, yapan: str) -> m.Kullanici:
    """Geçici şifre verir; kullanıcının açık oturumları kapanır, ilk girişte kendi şifresini belirler. Kilit de kalkar."""
    k = _getir(s, kullanici_id)
    _sifre_denetle(gecici_sifre)
    k.sifre_karma, k.sifre_degismeli, k.hatali_deneme, k.kilit_bitis = sifre_karma(gecici_sifre), True, 0, None
    _oturumlari_kapat(s, k.id)
    s.add(m.DegisiklikKaydi(tablo="kullanici", kayit_id=k.id, islem="sifre_sifirla", eski=None, yeni={}, kullanici=yapan))
    s.flush()
    return k


def kullanici_dict(k: m.Kullanici) -> dict:
    return {"id": k.id, "kullanici_adi": k.kullanici_adi, "ad": k.ad, "rol": k.rol, "rol_ad": ROLLER.get(k.rol, k.rol), "aktif": k.aktif,
            "sifre_degismeli": k.sifre_degismeli,
            "son_giris": k.son_giris.replace(tzinfo=timezone.utc).isoformat() if k.son_giris else None}
