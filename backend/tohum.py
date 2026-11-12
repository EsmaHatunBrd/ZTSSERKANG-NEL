# backend/tohum.py
"""Parametre tanımları ve fire varsayılanları. Çalıştır: python -m backend.tohum"""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from .depo import modeller as m
from .servisler import liste_kurallari as lk, recete_servisi

PARAMETRELER = [("enflasyon", "Enflasyon öngörüsü (yalnız fiyat çalışması)", "oran"), ("satis_kar", "Satış fiyatı kâr oranı", "oran"), ("vardiya_saati", "Vardiya süresi", "saat"),
                ("maliyet_sapma", "Maliyet sapma oranı (yalnız gösterim; motor kullanmaz)", "oran"),
                ("liste_bolen_yurtici", "Berrak yurtiçi liste fiyatı böleni (liste = satış fiyatı ÷ bölen, KDV hariç; girilmezse 0,63)", "oran"),
                ("liste_bolen_yurtdisi", "Berrak yurtdışı liste fiyatı böleni (liste = satış fiyatı ÷ bölen, KDV hariç; girilmezse 0,90)", "oran"),
                ("liste_yuvarlama", "Liste fiyatı yuvarlama adımı, TL (en yakına; 0,01 / 0,05 / 0,10 / 0,25 / 0,50 / 1 / 5; girilmezse 0,01)", "TL"),
                ("marj_esigi", "Hedef kâr oranı eşiği: altındaki ürünler uyarılır (girilmezse %10)", "oran"),
                ("fiyat_uyari_esigi.TL", "TL malzeme fiyatı tek seferde bundan fazla değişirse onay sorulur (girilmezse %15)", "oran"),
                ("fiyat_uyari_esigi.doviz", "Dövizli malzeme fiyatı tek seferde bundan fazla değişirse onay sorulur (girilmezse %10)", "oran"),
                ("satis_ortalama_maliyetten", "Stokta kalan varsa satış fiyatı ortalama maliyetten (1 = evet, 0 = hayır; girilmezse hayır)", "evet_hayir")]
PARAMETRELER += [(f"kur.{pb}", f"{pb} kuru", "TL") for pb in ("USD", "EUR", "GBP", "CHF", "RUB", "ZAR")]
METIN_PARAMETRELER = [("satis_fiyati_notu", "Satış fiyatı notu (Excel G137)")]   # değerleri /metin-parametreler ile girilir
PARAMETRELER += [(f"faiz.{pb}", f"{pb} yıllık faiz", "oran") for pb in ("TL", "USD", "EUR", "GBP", "ZAR")]
PARAMETRELER += [(f"stok_ay.{pb}", f"{pb} ortalama stok süresi", "ay") for pb in ("TL", "USD", "EUR", "GBP", "ZAR")]
PARAMETRELER += [(f"teklif_kar.{i}", f"{i}. teklif kâr oranı", "oran") for i in (1, 2, 3)]
PARAMETRELER += [(f"dagitim_carpani.{k}", f"{k} havuzu bütçe çarpanı", "çarpan") for k in
                 ("dolum_iscilik", "mal_kabul_iscilik", "etiket_iscilik", "endirekt_iscilik", "mal_kabul_gug", "diger_gug", "elektrik", "dogalgaz", "amortisman", "yonetim", "pazarlama")]
FIRE_TIP_VARSAYILAN = {"0008-Ambalaj Malzeme": Decimal("0.02"), "0017-Yardımcı Malzeme": Decimal(0), "0001-Hammadde": Decimal(0),
                       "0018-Sarf Malzemesi": Decimal(0), "0004-Ticari Malzeme": Decimal(0)}


def liste_bolen_gocu(s: Session) -> int:
    """Eski tek `liste_bolen` tanımını `liste_bolen_yurtici` olarak yeniden adlandırır (değer kayıtları aynı tanıma bağlı kalır).
    İkisi birden varsa eski tanımın değer kayıtları yeni tanıma taşınır ve eski tanım silinir. İdempotent. Dönüş: taşınan değer sayısı."""
    eski = s.scalar(select(m.Parametre).where(m.Parametre.anahtar == lk.ESKI_BOLEN_ANAHTARI))
    if eski is None:
        return 0
    yeni_anahtar = lk.BOLEN_ANAHTARLARI["yurtici"]
    yeni = s.scalar(select(m.Parametre).where(m.Parametre.anahtar == yeni_anahtar))
    degerler = list(s.scalars(select(m.ParametreDegeri).where(m.ParametreDegeri.parametre_id == eski.id)))
    if yeni is None:
        aciklama = next(ac for a, ac, _ in PARAMETRELER if a == yeni_anahtar)
        eski.anahtar, eski.aciklama = yeni_anahtar, aciklama
    else:
        for d in degerler:
            d.parametre_id = yeni.id
        s.flush()
        s.delete(eski)
    s.add(m.DegisiklikKaydi(tablo="parametre", kayit_id=(yeni or eski).id, islem="yeniden_adlandir", kullanici="sistem",
                            eski={"anahtar": lk.ESKI_BOLEN_ANAHTARI}, yeni={"anahtar": yeni_anahtar, "tasinan_deger": len(degerler)}))
    s.flush()
    return len(degerler)


def markalari_doldur(s: Session) -> int:
    """Markası bilinmeyen (NULL) ve adında "berrak" geçen ürünlere "Berrak" yazar. Bilerek boş bırakılan ("") markaya dokunmaz. İdempotent."""
    n = 0
    for u in s.scalars(select(m.Urun).where(m.Urun.marka.is_(None))):
        marka = lk.marka_turet(u.ad)
        if marka:
            u.marka = marka; n += 1
    if n:
        s.add(m.DegisiklikKaydi(tablo="urun", kayit_id=0, islem="marka_turet", eski=None, yeni={"marka": lk.BERRAK, "doldurulan": n}, kullanici="sistem"))
        s.flush()
    return n


def parametreleri_tohumla(s: Session) -> int:
    liste_bolen_gocu(s)
    mevcut = set(s.scalars(select(m.Parametre.anahtar)))
    yeni = [m.Parametre(anahtar=a, aciklama=ac, birim=b) for a, ac, b in PARAMETRELER if a not in mevcut]
    s.add_all(yeni); s.flush()
    return len(yeni)


def fire_varsayilanlarini_tohumla(s: Session, senaryo_id: int, tarih: date) -> int:
    n = 0
    for tip, oran in FIRE_TIP_VARSAYILAN.items():
        var = s.scalar(select(m.FireKurali).where(m.FireKurali.senaryo_id == senaryo_id, m.FireKurali.kapsam_tipi == "tip", m.FireKurali.kapsam_deger == tip))
        if var is None:
            recete_servisi.fire_kurali_ekle(s, senaryo_id, "tip", tip, oran, tarih, "Excel analizinden varsayılan"); n += 1
    return n


def aileleri_tohumla(s: Session) -> int:
    from .servisler.aile import aileleri_doldur
    return aileleri_doldur(s)


if __name__ == "__main__":
    from .depo.veritabani import Base, eksik_kolonlari_tamamla, liste_fiyati_gocu, motor_olustur, oturum_fabrikasi
    e = motor_olustur(); Base.metadata.create_all(e); liste_fiyati_gocu(e); eksik_kolonlari_tamamla(e)
    with oturum_fabrikasi(e)() as s:
        print("yeni parametre:", parametreleri_tohumla(s)); print("doldurulan aile:", aileleri_tohumla(s))
        print("doldurulan marka:", markalari_doldur(s)); s.commit()
