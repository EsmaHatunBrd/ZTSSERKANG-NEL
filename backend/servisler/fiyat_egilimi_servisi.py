"""Fiyat eğilimi (analiz önerisi 9): senaryodaki her malzemenin son `ay` aydaki fiyat değişimi, yıllıklandırılmış artış ve enflasyon eşiği.
Yeni hesap kuralı yoktur; malzeme fiyatı kayıtları (append-only bütçe fiyatı) ve `enflasyon` parametresi okunur, hiçbir şey kaydedilmez.

Pencere: [tarih - ay ay, tarih]. Pencere başındaki geçerli fiyat (`ilk`) = gecerlilik_basi <= pencere başı olan son kayıt; yoksa pencere
içindeki ilk kayıt (ilk bütçe fiyatı). Pencere sonundaki geçerli fiyat (`son`) = gecerlilik_basi <= tarih olan son kayıt. Tarihten sonra
başlayan kayıtlar sayılmaz; hiç kaydı olmayan malzeme listeye girmez. Kayıt sayısı = ilk kayıttan son kayda kadar olan kayıt sayısı; 1 ise
değişim 0.
Yüzdeler: degisim_yuzde = (son/ilk - 1) x 100; yillik_yuzde = ((son/ilk)^(12/ay) - 1) x 100; ikisi de 2 basamağa yuvarlanır (ROUND_HALF_UP).
Eşik: TL fiyatlarda senaryonun `enflasyon` parametresi (oran; 0,25 = %25 -> esik_yuzde 25), döviz fiyatlarda 0 (Excel kuralı: dövizde
enflasyon uygulanmaz). enflasyonu_asiyor = yillik_yuzde > esik_yuzde + TOLERANS (1 puan).
İlk ve son kaydın para birimi farklıysa oran anlamsızdır: değişim alanları null, aşmıyor sayılır (`para_birimi` son kaydınki)."""
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from . import hesap_servisi as hs, parametre_servisi as ps
from .donusum import decimal_str
from .hatalar import DogrulamaHatasi

TOLERANS_PUAN = Decimal(1)   # eşik üstü 1 puana kadar artış "aşıyor" sayılmaz (yuvarlama gürültüsü)
_YUZ = Decimal(100)
_IKI_BASAMAK = Decimal("0.01")


def ay_geri(tarih: date, ay: int) -> date:
    """`tarih`ten `ay` ay öncesi; gün sayısı o ayda yoksa ayın son günü (31 Mart - 1 ay = 28/29 Şubat)."""
    toplam = tarih.year * 12 + (tarih.month - 1) - ay
    yil, ay_no = divmod(toplam, 12)
    ay_no += 1
    son_gun = (date(yil + (ay_no == 12), (ay_no % 12) + 1, 1) - timedelta(days=1)).day
    return date(yil, ay_no, min(tarih.day, son_gun))


def _yuzde(x: Decimal) -> Decimal:
    return (x * _YUZ).quantize(_IKI_BASAMAK, ROUND_HALF_UP)


def pencere_degisimi(kayitlar: list[tuple[date, Decimal]], bas: date, son: date, ay: int) -> dict | None:
    """Saf hesap. `kayitlar`: (gecerlilik_basi, fiyat) geçerlilik sırasıyla (eşit tarihte ekleniş sırası). Dönüş: ilk_fiyat, ilk_tarih,
    son_fiyat, son_tarih, kayit_sayisi, degisim_yuzde, yillik_yuzde (Decimal); kayıt yoksa (ya da hepsi `son`dan sonra) None.
    ilk fiyat 0 ise oran tanımsız: degisim_yuzde ve yillik_yuzde None."""
    if ay <= 0:
        raise DogrulamaHatasi("Ay sayısı 1 ya da daha büyük olmalı.", {"ay": str(ay)})
    ilgili = [k for k in kayitlar if k[0] <= son]
    if not ilgili:
        return None
    ilk_i = 0
    for i, k in enumerate(ilgili):
        if k[0] <= bas:
            ilk_i = i
    ilk, son_k = ilgili[ilk_i], ilgili[-1]
    out = {"ilk_fiyat": ilk[1], "ilk_tarih": ilk[0], "son_fiyat": son_k[1], "son_tarih": son_k[0], "kayit_sayisi": len(ilgili) - ilk_i,
           "degisim_yuzde": None, "yillik_yuzde": None}
    if out["kayit_sayisi"] < 2:
        out["degisim_yuzde"] = out["yillik_yuzde"] = Decimal(0)
    elif ilk[1] and ilk[1] > 0 and son_k[1] >= 0:
        oran = son_k[1] / ilk[1]
        out["degisim_yuzde"] = _yuzde(oran - 1)
        out["yillik_yuzde"] = _yuzde(oran ** (Decimal(12) / Decimal(ay)) - 1) if oran > 0 else _yuzde(Decimal(-1))
    return out


def _kullanim_sayilari(s: Session, senaryo_id: int) -> dict[str, int]:
    """Malzeme kodu -> aktif reçetesinde geçtiği senaryo üyesi aktif ürün sayısı (tek sorgu)."""
    q = (select(m.ReceteSatiri.malzeme_kodu, func.count(func.distinct(m.Urun.id)))
         .join(m.Recete, m.Recete.id == m.ReceteSatiri.recete_id).join(m.Urun, m.Urun.id == m.Recete.urun_id)
         .where(m.Recete.senaryo_id == senaryo_id, m.Recete.aktif == True, m.Urun.aktif == True)   # noqa: E712
         .group_by(m.ReceteSatiri.malzeme_kodu))
    return {kod: int(n) for kod, n in s.execute(q)}


def _kayitlar(s: Session, senaryo_id: int) -> dict[int, list[m.MalzemeFiyati]]:
    q = (select(m.MalzemeFiyati).where(m.MalzemeFiyati.senaryo_id == senaryo_id)
         .order_by(m.MalzemeFiyati.gecerlilik_basi.asc(), m.MalzemeFiyati.id.asc()))
    out: dict[int, list[m.MalzemeFiyati]] = {}
    for k in s.scalars(q):
        out.setdefault(k.malzeme_id, []).append(k)
    return out


def enflasyon_yuzde(s: Session, senaryo_id: int, tarih: date) -> Decimal | None:
    """Senaryonun `enflasyon` parametresi yüzde olarak (0,25 -> 25); girilmemişse None (TL eşiği de 0 alınır)."""
    v = ps.gecerli_degerler(s, senaryo_id, tarih).get("enflasyon")
    return None if v is None else v * _YUZ


def egilim(s: Session, senaryo_id: int, ay: int = 12, tarih: date | None = None, yalniz_asan: bool = False) -> dict:
    """Satırlar: {kod, ad, tip, para_birimi, ilk_fiyat, ilk_tarih, son_fiyat, son_tarih, kayit_sayisi, degisim_yuzde, yillik_yuzde,
    esik_yuzde, enflasyonu_asiyor, kullanan_urun_sayisi}; sıralama aşanlar önce, sonra yillik_yuzde azalan (null sonda), sonra kod.
    Toplam: {senaryo_id, ay, tarih, pencere_basi, enflasyon_yuzde, satirlar, asan_sayisi, toplam}. Sayılar decimal_str ile metin."""
    sen = hs.senaryo_getir(s, senaryo_id)
    if ay <= 0:
        raise DogrulamaHatasi("Ay sayısı 1 ya da daha büyük olmalı.", {"ay": str(ay)})
    t = tarih or date.today()
    bas = ay_geri(t, ay)
    enf = enflasyon_yuzde(s, sen.id, t)
    esik_tl = enf if enf is not None else Decimal(0)
    kullanim = _kullanim_sayilari(s, sen.id)
    kayitlar = _kayitlar(s, sen.id)
    satirlar = []
    for mz in s.scalars(select(m.Malzeme).where(m.Malzeme.id.in_(list(kayitlar))).order_by(m.Malzeme.kod)):
        ks = kayitlar[mz.id]
        d = pencere_degisimi([(k.gecerlilik_basi, k.fiyat) for k in ks], bas, t, ay)
        if d is None:
            continue
        ilgili = [k for k in ks if k.gecerlilik_basi <= t]
        son_k = ilgili[-1]
        ilk_k = ilgili[len(ilgili) - d["kayit_sayisi"]]
        pb = (son_k.para_birimi or mz.para_birimi or "TL").upper()
        if (ilk_k.para_birimi or mz.para_birimi or "TL").upper() != pb:
            d["degisim_yuzde"] = d["yillik_yuzde"] = None
        esik = esik_tl if pb == "TL" else Decimal(0)
        asiyor = d["yillik_yuzde"] is not None and d["yillik_yuzde"] > esik + TOLERANS_PUAN
        satirlar.append({"kod": mz.kod, "ad": mz.ad, "tip": mz.tip, "para_birimi": pb, **d, "esik_yuzde": esik, "enflasyonu_asiyor": asiyor,
                         "kullanan_urun_sayisi": kullanim.get(mz.kod, 0)})
    satirlar.sort(key=lambda r: (not r["enflasyonu_asiyor"], r["yillik_yuzde"] is None, -(r["yillik_yuzde"] or Decimal(0)), r["kod"]))
    asan = sum(1 for r in satirlar if r["enflasyonu_asiyor"])
    if yalniz_asan:
        satirlar = [r for r in satirlar if r["enflasyonu_asiyor"]]
    return decimal_str({"senaryo_id": sen.id, "ay": ay, "tarih": t, "pencere_basi": bas, "enflasyon_yuzde": enf,
                        "satirlar": satirlar, "asan_sayisi": asan, "toplam": len(satirlar)})


def _yuzde_metni(x: str) -> str:
    return f"%{Decimal(x).quantize(Decimal('0.1'), ROUND_HALF_UP):f}".replace(".", ",")


def kontrol_ogeleri(s: Session, senaryo_id: int, tarih: date | None = None, ay: int = 12) -> list[dict]:
    """Veri Kontrolü ögeleri: enflasyonu aşan malzemeler; {etiket, aciklama, yol}. Aynı `egilim` hesabı, ek sorgu yok."""
    d = egilim(s, senaryo_id, ay, tarih, yalniz_asan=True)
    return [{"etiket": f"{r['kod']} · {r['ad']}",
             "aciklama": f"yıllık {_yuzde_metni(r['yillik_yuzde'])} (eşik {_yuzde_metni(r['esik_yuzde'])}) · {r['kullanan_urun_sayisi']} üründe",
             "yol": f"/fiyat-egilimi?arama={quote(r['kod'], safe='')}"} for r in d["satirlar"]]
