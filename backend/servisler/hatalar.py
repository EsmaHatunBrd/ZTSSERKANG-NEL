class ServisHatasi(Exception):
    """`kod`: arayüzün mesaj metnine bakmadan tanıyacağı kararlı ayrıntı kodu (ör. HEDEF_YOK); yoksa None."""
    def __init__(self, mesaj: str, alanlar: dict | None = None, kod: str | None = None):
        super().__init__(mesaj); self.mesaj = mesaj; self.alanlar = alanlar or {}; self.kod = kod


# Kararlı hata kodları (yanıt gövdesinde "kod"): metin değişse de arayüz bunlarla tanır.
HEDEF_YOK = "hedef_yok"               # ürünün senaryoda üretim hedefi yok
PARAMETRE_EKSIK = "parametre_eksik"   # zorunlu parametre (kur, enflasyon...) girilmemiş


class BulunamadiHatasi(ServisHatasi): ...
class DogrulamaHatasi(ServisHatasi): ...
class KilitliHatasi(ServisHatasi): ...   # 409 "senaryo kilitli"
class CatismaHatasi(ServisHatasi): ...   # 409 "catisma": işlem mevcut durumla çelişiyor (ör. kayıtlı hesabı olan senaryo silinemez)
