# backend/tohum.py
"""Parametre tanımları ve fire varsayılanları. Çalıştır: python -m backend.tohum"""
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from .depo import modeller as m
from .servisler import recete_servisi

PARAMETRELER = [("enflasyon", "Enflasyon öngörüsü (yalnız fiyat çalışması)", "oran"), ("satis_kar", "Satış fiyatı kâr oranı", "oran"), ("vardiya_saati", "Vardiya süresi", "saat"),
                ("maliyet_sapma", "Maliyet sapma oranı (yalnız gösterim; motor kullanmaz)", "oran"),
                ("liste_bolen", "Liste fiyatı böleni (liste = satış fiyatı ÷ bölen; girilmezse 0,63)", "oran"),
                ("marj_esigi", "Hedef kâr oranı eşiği: altındaki ürünler uyarılır (girilmezse %10)", "oran"),
                ("fiyat_uyari_esigi.TL", "TL malzeme fiyatı tek seferde bundan fazla değişirse onay sorulur (girilmezse %15)", "oran"),
                ("fiyat_uyari_esigi.doviz", "Dövizli malzeme fiyatı tek seferde bundan fazla değişirse onay sorulur (girilmezse %10)", "oran")]
PARAMETRELER += [(f"kur.{pb}", f"{pb} kuru", "TL") for pb in ("USD", "EUR", "GBP", "CHF", "RUB", "ZAR")]
METIN_PARAMETRELER = [("satis_fiyati_notu", "Satış fiyatı notu (Excel G137)")]   # değerleri /metin-parametreler ile girilir
PARAMETRELER += [(f"faiz.{pb}", f"{pb} yıllık faiz", "oran") for pb in ("TL", "USD", "EUR", "GBP", "ZAR")]
PARAMETRELER += [(f"stok_ay.{pb}", f"{pb} ortalama stok süresi", "ay") for pb in ("TL", "USD", "EUR", "GBP", "ZAR")]
PARAMETRELER += [(f"teklif_kar.{i}", f"{i}. teklif kâr oranı", "oran") for i in (1, 2, 3)]
PARAMETRELER += [(f"dagitim_carpani.{k}", f"{k} havuzu bütçe çarpanı", "çarpan") for k in
                 ("dolum_iscilik", "mal_kabul_iscilik", "etiket_iscilik", "endirekt_iscilik", "mal_kabul_gug", "diger_gug", "elektrik", "dogalgaz", "amortisman", "yonetim", "pazarlama")]
FIRE_TIP_VARSAYILAN = {"0008-Ambalaj Malzeme": Decimal("0.02"), "0017-Yardımcı Malzeme": Decimal(0), "0001-Hammadde": Decimal(0),
                       "0018-Sarf Malzemesi": Decimal(0), "0004-Ticari Malzeme": Decimal(0)}


def parametreleri_tohumla(s: Session) -> int:
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
    from .depo.veritabani import Base, eksik_kolonlari_tamamla, motor_olustur, oturum_fabrikasi
    e = motor_olustur(); Base.metadata.create_all(e); eksik_kolonlari_tamamla(e)
    with oturum_fabrikasi(e)() as s:
        print("yeni parametre:", parametreleri_tohumla(s)); print("doldurulan aile:", aileleri_tohumla(s)); s.commit()
