"""Veri Kontrolü (D7): seçili çalışmadaki veri sorunlarını tek listede toplar. Yeni hesap kuralı yoktur; mevcut toplu hesabın
hata/uyarılarından ve tablolardan okunur. Her kontrol: durum (tamam | bilgi | dikkat | hata), sayı, kısa açıklama, çözüm bağlantısı ve
ilgili kayıtlar (en çok OGE_SINIRI). Bağlantılar arayüz yollarıdır (?senaryo= eki istemcide)."""
import re
from datetime import date
from decimal import Decimal
from urllib.parse import quote
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from fiyat_motoru.modeller import GIDER_ELLE_ALANLARI
from . import gider_servisi, hesap_servisi as hs, senaryo_servisi
from .hatalar import HEDEF_YOK, PARAMETRE_EKSIK

OGE_SINIRI = 200
_FIYATSIZ = re.compile(r"^(?P<kod>\S+) \((?P<ad>.*)\): (fiyat listesinde yok|birim fiyatı 0)")
_HAT = ("üretim hattı bulunamadı", "taze/turşu sınıfı bulunamadı", "dağıtım tablosunda yok")
_KART = re.compile(r"^(?P<kod>\S+) \((?P<ad>.*)\): (?P<mesaj>(para birimi tanımsız|Z/S bayrağı tanımsız|Ziraat kaynaklı ama döviz fiyatlı).*)$")
_PARAMETRE = ("kuru tanımsız", "USD kuru yok", "faiz/stok süresi", "TL finansman parametresi yok", "vardiya saati 0")


def _urun_yolu(kod: str) -> str:
    return f"/urunler/{quote(kod, safe='')}"


# Elle hücre açıklamaları: gider kalemi -> kısa ad, hücre -> Excel sütunu ile ad.
_GIDER_KISA = {"mal_kabul_iscilik": "Mal kabul işçilik", "dolum_iscilik": "Dolum işçilik", "etiket_iscilik": "Etiket işçilik",
               "endirekt_iscilik": "Endirekt işçilik", "mal_kabul_gug": "Mal kabul GÜG", "elektrik": "Elektrik", "dogalgaz": "Doğalgaz",
               "amortisman": "Amortisman", "diger_gug": "Diğer GÜG", "pazarlama": "Pazarlama", "yonetim": "Yönetim"}
_HUCRE_ADI = {"miktar": "miktar", "brut_miktar": "brüt miktar", "birim_fiyat": "birim fiyat", "tutar": "tutar"}


def _elle_hucreler(girdi) -> str | None:
    """Ürünün formül yerine elle yazılmış hücrelerinin kısa özeti (gider I/K/M/P, reçete brüt/fiyat/Z-S/para birimi); yoksa None."""
    parcalar = []
    for kalem, e in girdi.gider_elle.items():
        hucreler = ", ".join(f"{_HUCRE_ADI[a]} ({GIDER_ELLE_ALANLARI[a]}) {getattr(e, a).normalize():f}".replace(".", ",") for a in e.dolu_alanlar())
        parcalar.append(f"{_GIDER_KISA.get(kalem, kalem)}: {hucreler}")
    sayac = {"brüt miktar": sum(1 for r in girdi.recete if r.brut_miktar_elle is not None),
             "birim fiyat": sum(1 for r in girdi.recete if r.birim_fiyat_elle is not None),
             "Z/S": sum(1 for r in girdi.recete if r.zs_elle), "para birimi": sum(1 for r in girdi.recete if r.para_birimi_elle)}
    recete = ", ".join(f"{n} satırda {ad}" for ad, n in sayac.items() if n)
    if recete:
        parcalar.append(f"reçete: {recete}")
    return "; ".join(parcalar) or None


def _kontrol(kod: str, baslik: str, aciklama: str, cozum: tuple[str, str], ogeler: list[dict], agir: bool = False,
             bilgi: bool = False) -> dict:
    """bilgi=True: kayıt varsa durum 'bilgi' (sorun değil, bilinmesi gereken); yoksa 'tamam'."""
    durum = ("bilgi" if bilgi else "hata" if agir else "dikkat") if ogeler else "tamam"
    return {"kod": kod, "baslik": baslik, "aciklama": aciklama, "durum": durum,
            "sayi": len(ogeler), "cozum": {"etiket": cozum[0], "yol": cozum[1]}, "ogeler": ogeler[:OGE_SINIRI]}


def kontroller(s: Session, senaryo_id: int, tarih: date | None = None) -> dict:
    sen = hs.senaryo_getir(s, senaryo_id)
    urunler = {u.kod: u for u in s.scalars(select(m.Urun))}
    uyeler = senaryo_servisi.uye_urun_kodlari(s, sen.id)
    sonuclar = hs.toplu_hesapla(s, sen.id, tarih)

    hesaplanamayan, parametre_eksik, fiyatsiz, hat, param_uyari, kart, elle = [], [], {}, [], [], {}, []
    for kod, c in sonuclar:
        u = urunler[kod]
        if isinstance(c, Exception):
            hata_kodu = getattr(c, "kod", None)
            mesaj = "üretim bilgileri (vardiya adedi, personel, mal kabul) girilmemiş" if hata_kodu == HEDEF_YOK else str(getattr(c, "mesaj", None) or c)
            oge = {"etiket": f"{kod} · {u.ad}", "aciklama": mesaj, "yol": _urun_yolu(kod)}
            (parametre_eksik if hata_kodu == PARAMETRE_EKSIK else hesaplanamayan).append(oge)
            continue
        for w in c.sonuc.uyarilar:
            e = _FIYATSIZ.match(w)
            if e:
                f = fiyatsiz.setdefault(e["kod"], {"ad": e["ad"], "urunler": []})
                f["urunler"].append(kod)
            elif (e := _KART.match(w)):
                kart.setdefault(e["kod"], {"ad": e["ad"], "mesaj": e["mesaj"], "urunler": set()})["urunler"].add(kod)
            elif any(x in w for x in _HAT):
                hat.append({"etiket": f"{kod} · {u.ad}", "aciklama": w, "yol": _urun_yolu(kod)})
            elif any(x in w for x in _PARAMETRE):
                param_uyari.append({"etiket": f"{kod} · {u.ad}", "aciklama": w, "yol": "/parametreler"})
        if (ozet := _elle_hucreler(c.girdi)):
            elle.append({"etiket": f"{kod} · {u.ad}", "aciklama": ozet, "yol": _urun_yolu(kod)})
        if c.girdi.uretim.vardiya_uretim_adedi == 0:
            hat.append({"etiket": f"{kod} · {u.ad}", "aciklama": "vardiya üretim adedi 0: saniye bazlı giderler 0 alınıyor", "yol": _urun_yolu(kod)})

    fiyatsiz_ogeler = sorted(
        ({"etiket": f"{k} · {v['ad']}", "aciklama": f"{len(set(v['urunler']))} üründe kullanılıyor: " + ", ".join(sorted(set(v["urunler"]))[:5])
          + (" …" if len(set(v["urunler"])) > 5 else ""), "yol": f"/fiyatlar?fiyatsiz=1&arama={quote(k, safe='')}", "_n": len(set(v["urunler"]))}
         for k, v in fiyatsiz.items()), key=lambda x: (-x["_n"], x["etiket"]))
    for x in fiyatsiz_ogeler:
        del x["_n"]

    kart_ogeler = [{"etiket": f"{k} · {v['ad']}", "aciklama": f"{v['mesaj']} ({len(v['urunler'])} üründe)",
                    "yol": f"/fiyatlar?arama={quote(k, safe='')}"} for k, v in sorted(kart.items())]
    paylar = [{"etiket": x["havuz"], "aciklama": f"pay toplamı %{(x['toplam'] * 100).quantize(Decimal('0.01'))}".replace(".", ","), "yol": "/gider"}
              for x in gider_servisi.pay_toplami_kontrol(s, sen.id)]
    recetesiz = [{"etiket": f"{k} · {u.ad}", "aciklama": "bu çalışmada aktif reçetesi yok", "yol": _urun_yolu(k)}
                 for k, u in sorted(urunler.items()) if u.aktif and k not in uyeler]
    gecici = [{"etiket": f"{k} · {urunler[k].ad}", "aciklama": "geçici kod; ERP kodu atanmalı", "yol": _urun_yolu(k)}
              for k in sorted(uyeler) if urunler[k].gecici_kod]
    kapasite = list(s.scalars(select(m.UretimKapasitesi).where(m.UretimKapasitesi.senaryo_id == sen.id).order_by(m.UretimKapasitesi.urun_kodu)))
    eslesmeyen = [{"etiket": f"{k.urun_kodu} · {k.urun_ad or ''}".rstrip(" ·"), "aciklama": "bu kodla ürün kartı yok",
                   "yol": "/uretim-adetleri"} for k in kapasite if k.urun_kodu not in urunler]

    liste = [
        _kontrol("hesaplanamayan", "Hesaplanamayan ürün", "Bu ürünlerin maliyeti hiç hesaplanamıyor; Genel Bakış'ta boş görünürler.",
                 ("Ürün Maliyeti", "/urunler"), hesaplanamayan, agir=True),
        _kontrol("parametre_eksik", "Eksik zorunlu parametre", "Enflasyon, satış kârı ya da vardiya saati tanımlı değil; hesap yapılamıyor.",
                 ("Parametreler", "/parametreler"), parametre_eksik, agir=True),
        _kontrol("fiyatsiz", "Fiyatı olmayan malzeme", "Reçetede kullanılan ama fiyatı olmayan malzemeler 0 TL sayılıyor; maliyet eksik çıkar.",
                 ("Malzeme Fiyatları (yalnız fiyatsızlar)", "/fiyatlar?fiyatsiz=1"), fiyatsiz_ogeler),
        _kontrol("malzeme_karti", "Eksik malzeme kartı bilgisi", "Para birimi ya da Ziraat/Satın alma bayrağı eksik veya çelişkili; "
                 "fiyat 0 ya da yanlış kurla alınabilir.", ("Malzeme Fiyatları", "/fiyatlar"), kart_ogeler),
        _kontrol("pay", "Gider payı %100 değil", "Bir gider havuzunun alt kalem payları toplamı %100 değil; dağıtılan gider eksik ya da fazla.",
                 ("Gider Dağıtım", "/gider"), paylar),
        _kontrol("hat", "Gideri eksik hesaplanan ürün", "Hattı, taze/turşu sınıfı ya da ambalajı gider dağıtım tablosunda bulunamayan veya "
                 "vardiya üretim adedi 0 olan ürünler; ilgili gider 0 alınıyor.", ("Gider Dağıtım", "/gider"), hat),
        _kontrol("parametre_uyari", "Kur / finansman uyarısı", "Kur, faiz ya da stok süresi eksik olduğu için bir tutar 0 alınmış.",
                 ("Parametreler", "/parametreler"), param_uyari),
        _kontrol("recetesiz", "Reçetesi olmayan ürün", "Aktif ürün kartı var ama bu çalışmada reçetesi yok; listelerde görünmez.",
                 ("Çalışma dışı ürünleri göster", "/urunler?tum=1"), recetesiz),
        _kontrol("gecici_kod", "Geçici kodlu ürün", "Excel'de kodu olmayan sayfalardan gelen ürünler (SAYFA-0xx); ERP kodu atanmalı.",
                 ("Ürün ekranında kodu değiştir", "/urunler"), gecici),
        _kontrol("uretim_adetleri", "Üretim Adetleri'nde eşleşmeyen kod", "Üretim Adetleri kaydındaki kod hiçbir ürünle eşleşmiyor; "
                 "hedef adetle maliyet hesaplanamaz.", ("Üretim Adetleri", "/uretim-adetleri"), eslesmeyen),
        _kontrol("elle_hucre", "Elle girilmiş hücre", "Formül yerine elle yazılmış değerler (Excel'den geldiği gibi ya da ürün ekranında "
                 "girilmiş). Hata değildir; formüle dönmek için ürün ekranında hücredeki ↺ düğmesi.", ("Ürün Maliyeti", "/urunler"), elle,
                 bilgi=True),
    ]
    return {"senaryo_id": sen.id, "kontroller": liste,
            "ozet": {d: sum(1 for k in liste if k["durum"] == d) for d in ("hata", "dikkat", "tamam", "bilgi")}}
