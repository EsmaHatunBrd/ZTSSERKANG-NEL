class ServisHatasi(Exception):
    """`kod`: arayüzün mesaj metnine bakmadan tanıyacağı kararlı ayrıntı kodu (ör. HEDEF_YOK); yoksa None.
    `mesaj` kullanıcıya olduğu gibi gösterilir: kendi başına anlaşılır, büyük harfle başlayan Türkçe cümle; gereken bilgi (kod, ad)
    metnin içinde okunur biçimde yer alır, ekranda "senaryo" yerine "çalışma" denir. `alanlar` yalnız makine içindir (form alanı eşlemesi);
    arayüz onları mesaja eklemez. Kod/ad ile başlayan mesajlar ('03.99.008 ürününün ...') bilerek olduğu gibi bırakılır."""
    def __init__(self, mesaj: str, alanlar: dict | None = None, kod: str | None = None):
        super().__init__(mesaj); self.mesaj = mesaj; self.alanlar = alanlar or {}; self.kod = kod


def liste_metni(ogeler, en_cok: int = 10) -> str:
    """['A', 'B', ...] -> 'A, B, …' (en çok `en_cok` öğe)."""
    ogeler = [str(x) for x in ogeler]
    return ", ".join(ogeler[:en_cok]) + (f" ve {len(ogeler) - en_cok} tane daha" if len(ogeler) > en_cok else "")


def hatali_satirlar_mesaji(hatalar: list, fiil: str = "yazılmadı") -> str:
    """Dosya yüklemesinde satır hataları [{satir_no, mesaj}] -> 'Dosyada 3 hatalı satır var; hiçbir satır yazılmadı. İlk hata (5. satır): ...'"""
    ilk = hatalar[0] if hatalar else None
    ek = ""
    if isinstance(ilk, dict) and ilk.get("mesaj"):
        ek = f" İlk hata ({ilk['satir_no']}. satır): {ilk['mesaj']}." if ilk.get("satir_no") is not None else f" İlk hata: {ilk['mesaj']}."
    return f"Dosyada {len(hatalar)} hatalı satır var; hiçbir satır {fiil}.{ek}"


def alan_adi(anahtar: str) -> str:
    """Teknik alan anahtarının ekrandaki adı ('birim_maliyet' -> 'Birim maliyet'); Değişiklik Günlüğü etiketleriyle aynı."""
    from .gunluk_servisi import _alan   # yerel: döngüsel içe aktarma olmasın
    return _alan(None, anahtar)[0]


# Kararlı hata kodları (yanıt gövdesinde "kod"): metin değişse de arayüz bunlarla tanır.
HEDEF_YOK = "hedef_yok"               # ürünün senaryoda üretim hedefi yok
PARAMETRE_EKSIK = "parametre_eksik"   # zorunlu parametre (kur, enflasyon...) girilmemiş


class BulunamadiHatasi(ServisHatasi): ...
class DogrulamaHatasi(ServisHatasi): ...
class KilitliHatasi(ServisHatasi): ...   # 409 "senaryo kilitli"
class CatismaHatasi(ServisHatasi): ...   # 409 "catisma": işlem mevcut durumla çelişiyor (ör. kayıtlı hesabı olan senaryo silinemez)
class KimlikHatasi(ServisHatasi): ...    # 401 "giris": oturum yok ya da kapanmış
class YetkiHatasi(ServisHatasi): ...     # 403 "yetki": rolün bu işleme izni yok


NEDEN_GIRIN = "Neden girin."


def neden_zorunlu(neden: str | None, sinir: int = 300) -> str:
    """Elle ekleme/silme uçlarının ortak neden denetimi: boşsa 422 'Neden girin.'; kırpılmış metni döndürür."""
    if not (neden or "").strip():
        raise DogrulamaHatasi(NEDEN_GIRIN, {"neden": "zorunlu"})
    return neden.strip()[:sinir]
