"""3 yıllık deneme veritabanı: üç sezon (2024-2025, 2025-2026, 2026-2027), her birinde bütçe (fiyat çalışması) + gerçekleşen,
ve Haziran 2023'ten bugüne aylık satış geçmişi. Karşılaştırma ekranlarını (geçen yıl, enflasyon eşiği, aile trendi, arşiv,
Bütçe vs Gerçekleşen) gerçekçi hacimle incelemek için. Canlı veritabanına (veri/fiyat.db) asla yazmaz.

Kaynaklar: asıl fiyat çalışması kitabı (bütçeler) ve deneme gerçekleşen kitabı (scripts/10-27-2026-gerceklesen-deneme-uret.py).
Eski sezonlar aynı kitaplardan yüklenip geriye çekilir: TL malzeme fiyatları ve gider havuzları sezon katsayısıyla (malzeme başına
±%8 gürültü), döviz fiyatları %5 aşağı, kurlar o yılın düzeyine. Satış fiyatları o sezonun gerçekleşen hesabından ±%8 sapmayla,
müşteriler uydurmadır (Deneme Market / Deneme Toptan TL, Deneme İhracat USD). Geçmiş sezonlar kilitlenir.

Kullanım: .venv/Scripts/python scripts/10-27-2026-deneme-verisi-uret.py [--yeniden]
Sonra: VERITABANI_URL=sqlite:///veri/10-27-2026-deneme.db  uvicorn backend.uygulama:app --port 8001
"""
import random
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from sqlalchemy import select  # noqa: E402
from backend.depo import modeller as m  # noqa: E402
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi  # noqa: E402
from backend.servisler import hesap_servisi as hs, import_servisi as ims  # noqa: E402
from backend.tohum import parametreleri_tohumla  # noqa: E402

HEDEF = KOK / "veri" / "10-27-2026-deneme.db"
BUTCE = KOK / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"
GERCEKLESEN = KOK / "10-27-2026-gerceklesen-deneme-2026-2027.xlsx"
# sezon -> (TL katsayısı 2026-2027'ye göre, USD kuru, EUR kuru); 2026-2027 kitaplardaki gibi kalır.
GECMIS = {"2024-2025": (Decimal(1) / Decimal("1.914"), Decimal("33.5"), Decimal("36.4")),
          "2025-2026": (Decimal(1) / Decimal("1.32"), Decimal("41.2"), Decimal("46.8"))}
MUSTERILER = (("Deneme Market A.Ş.", "TL"), ("Deneme Toptan Ltd.", "TL"), ("Deneme İhracat GmbH", "USD"))
D4 = Decimal("0.0001")


def _geriye_cek(s, sen: m.Senaryo, tl_k: Decimal, usd: Decimal, eur: Decimal, rnd: random.Random) -> None:
    for f in s.scalars(select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == sen.id)):
        k = tl_k * Decimal(str(rnd.uniform(0.92, 1.08))) if (f.para_birimi or "TL") == "TL" else Decimal("0.95")
        f.fiyat = (f.fiyat * k).quantize(D4)
    for p in s.scalars(select(m.ParametreDegeri).join(m.Parametre).where(m.ParametreDegeri.senaryo_id == sen.id,
                                                                         m.Parametre.anahtar.in_(("kur.USD", "kur.EUR")))):
        p.deger = usd if p.parametre.anahtar == "kur.USD" else eur
    for h in s.scalars(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == sen.id)):
        h.toplam_tutar = (h.toplam_tutar * tl_k).quantize(D4)
        if h.taban_tutar is not None:
            h.taban_tutar = (h.taban_tutar * tl_k).quantize(D4)


def _satislar(s, sen: m.Senaryo, rnd: random.Random) -> int:
    """Sezon penceresinde (Haziran-Mayıs, bugünden sonrası yok) her ürün x müşteri için aylık bir satış kaydı."""
    n = 0
    urunler = {u.kod: u for u in s.scalars(select(m.Urun))}
    y1 = sen.sezon.baslangic.year
    aylar = [date(y1 + (a > 12), (a - 1) % 12 + 1, 15) for a in range(6, 18)]
    aylar = [a for a in aylar if a <= date.today()]
    for kod, c in hs.toplu_hesapla(s, sen.id):
        if isinstance(c, Exception):
            continue
        fiyat = {"TL": c.sonuc.satis_fiyati_tl, "USD": c.sonuc.satis_fiyati_doviz.get("USD")}
        for musteri, pb in MUSTERILER:
            if fiyat[pb] is None or rnd.random() < 0.25:   # her ürün her müşteriye satılmaz
                continue
            for ay in aylar:
                if rnd.random() < 0.3:
                    continue
                s.add(m.SatisGecmisi(urun_id=urunler[kod].id, musteri=musteri, tarih=ay, para_birimi=pb, olusturan="deneme",
                                     fiyat=(fiyat[pb] * Decimal(str(rnd.uniform(0.92, 1.08)))).quantize(D4),
                                     adet=Decimal(rnd.randrange(200, 6000, 50))))
                n += 1
    return n


def main() -> None:
    yeniden = "--yeniden" in sys.argv
    if HEDEF.name == "fiyat.db":
        sys.exit("canlı veritabanına yazılmaz")
    if HEDEF.exists():
        if not yeniden:
            sys.exit(f"{HEDEF} zaten var; yeniden üretmek için --yeniden")
        for ek in ("", "-wal", "-shm"):
            Path(str(HEDEF) + ek).unlink(missing_ok=True)
    rnd = random.Random(20261027)
    engine = motor_olustur(f"sqlite:///{HEDEF}")
    Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    parametreleri_tohumla(s)
    satis = 0
    for sezon in ("2024-2025", "2025-2026", "2026-2027"):
        for ad, yol, tur in (("Bütçe", BUTCE, "fiyat_calismasi"), ("Gerçekleşen", GERCEKLESEN, "gerceklesen")):
            oz = ims.excel_tam_yukle(s, yol, sezon, ad, tur=tur, kartlari_guncelle=False, kaynak_dosya=yol.name)
            sen = s.get(m.Senaryo, oz["senaryo_id"])
            if sezon in GECMIS:
                _geriye_cek(s, sen, *GECMIS[sezon], rnd)
            s.flush()
            if tur == "gerceklesen":
                satis += _satislar(s, sen, rnd)
            if sezon in GECMIS:
                sen.kilitli = True
            s.commit()
            print(f"{sezon} {ad}: #{sen.id}, {oz['urun']} ürün")
    print(f"satış kaydı: {satis}")
    s.close()
    print(f"yazıldı: {HEDEF}")


if __name__ == "__main__":
    main()
