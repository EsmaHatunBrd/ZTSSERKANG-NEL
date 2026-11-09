"""Maliyet muhasebesi, 3. adım: dönem sonu stok değerlemesi (Excel DSS), SMM tablosu, stok mizanı karşılaştırması ve SMM fişi taslağı.

Dönem sonu stok (DSS) tutarı, kalem başına (Excel DSS!D/E):
    birim fiyat = envanter birim fiyatı (aşama maliyetiyle; bkz. smm_asama_servisi); 0 ise dönem ortalama fiyatı (TABLO)
    tutar       = birim fiyat × sayım, 2 haneye yukarı yuvarlanır (Excel YUKARIYUVARLA)
Hesap grubu kalemin türünden: hammadde / ambalaj / yardımcı malzeme -> 150, üretim yarı mamulü / yarı mamul -> 151, ürün -> 152.

SMM tablosu (dönemsellik ilkesi; Excel SMM sayfasının düzeni):
    710 ilk madde ve malzeme gideri = 150 dönem başı + alım (finansman dahil) − iade − satılan HM − şahit numune − 150 dönem sonu
    üretim maliyeti                 = 710 + 720 direkt işçilik + 730 genel üretim gideri (gider mizanı bakiyeleri)
    üretilen mamul maliyeti         = üretim maliyeti + 151 dönem başı + alım − iade − satılan YM − şahit − 151 dönem sonu
    satılan mamul maliyeti (620)    = üretilen + 152 dönem başı + alım − iade − şahit − 152 dönem sonu
Fiş taslağı bu tutarlarla (Excel STOK MİZAN'daki kurallar): 710-B/150-A, 151-B/711-A, 151-B/721-A, 151-B/731-A, 152-B/151-A, 620-B/152-A."""
from collections import defaultdict
from decimal import ROUND_UP, Decimal
from sqlalchemy.orm import Session
from .donusum import decimal_str
from .smm_asama_servisi import _Baglam
from .smm_servisi import SIFIR, _d, _yakin, donem_cikis, donem_getir

KURUS = Decimal("0.01")
TUR_GRUBU = {"0001": "150", "0008": "150", "0017": "150", "0002": "151", "0015": "151", "0003": "152"}
GRUP_ADI = {"150": "İlk madde ve malzeme", "151": "Yarı mamuller", "152": "Mamuller", "153": "Ticari mallar"}
HESAP_ADI = {"150": "İlk Madde ve Malzeme", "151": "Yarı Mamuller", "152": "Mamuller", "620": "Satılan Mamuller Maliyeti",
             "710": "Direkt İlk Madde ve Malzeme Giderleri", "711": "Direkt İlk Madde ve Malzeme Yansıtma",
             "720": "Direkt İşçilik Giderleri", "721": "Direkt İşçilik Giderleri Yansıtma",
             "730": "Genel Üretim Giderleri", "731": "Genel Üretim Giderleri Yansıtma"}


def grup(tur: str | None, mizan_kodu: str | None) -> str | None:
    """Kalemin stok hesabı grubu (150/151/152/153)."""
    t = (tur or "")[:4]
    if t in TUR_GRUBU:
        return TUR_GRUBU[t]
    m = (mizan_kodu or "")[:3]
    return m if m in GRUP_ADI else None


def _dss(b: _Baglam) -> dict[str, dict]:
    """Kalem başına dönem sonu stok değerlemesi ve satış / şahit tutarları."""
    sonuc = {}
    for kod, k in b.kalem.items():
        env = b.envanter_fiyati(kod) if k.envanterde else SIFIR
        fiyat = env or b.ortalama(kod)
        tutar = (fiyat * k.sayim_miktar).quantize(KURUS, rounding=ROUND_UP)
        satis, sahit = k.satis_miktar or SIFIR, k.sahit_miktar or SIFIR
        sonuc[kod] = {"grup": grup(k.tur, k.mizan_kodu), "fiyat": fiyat, "tutar": tutar,
                      "satis_tutar": satis * env, "sahit_tutar": (sahit * fiyat).quantize(KURUS, rounding=ROUND_UP)}
    return sonuc


def _yon(hesap: str, tutar: Decimal, borc: bool, aciklama: str) -> dict:
    """Fiş satırı; tutar eksiyse taraf değişir."""
    if tutar < 0:
        borc, tutar = not borc, -tutar
    return {"hesap": hesap, "ad": HESAP_ADI.get(hesap, hesap), "aciklama": aciklama,
            "borc": tutar if borc else SIFIR, "alacak": SIFIR if borc else tutar}


def smm_ozeti(s: Session, donem_id: int) -> dict:
    d = donem_getir(s, donem_id)
    b = _Baglam(s, d)
    dss = _dss(b)
    ozet = d.excel_ozet or {}

    # grup toplamları
    g = defaultdict(lambda: defaultdict(lambda: SIFIR))
    for kod, k in b.kalem.items():
        x = dss[kod]
        if x["grup"] is None:
            continue
        t = g[x["grup"]]
        t["db"] += k.dbs_tutar
        t["alim"] += k.alim_tutar + b.stok[kod]["finansman_payi"]
        t["iade"] += k.iade_tutar
        t["satis"] += x["satis_tutar"]
        t["sahit"] += x["sahit_tutar"]
        t["ds"] += x["tutar"]
        t["kalem"] += 1

    def hareket(gr: str) -> Decimal:
        t = g[gr]
        return t["db"] + t["alim"] - t["iade"] - t["satis"] - t["sahit"] - t["ds"]

    gm = {h: _d(v) for h, v in (ozet.get("gider_mizan") or {}).items()}
    if not gm and d.gider_mizan:
        gm = {h: _d(v) for h, v in d.gider_mizan.items()}
    iscilik, gug = gm.get("720", SIFIR), gm.get("730", SIFIR)
    ilk_madde = hareket("150")
    uretim = ilk_madde + iscilik + gug
    uretilen = uretim + hareket("151")
    smm = uretilen + hareket("152")

    def blok(gr: str, sonuc_ad: str, sonuc: Decimal, onceki: tuple[str, Decimal] | None = None) -> dict:
        t = g[gr]
        satirlar = []
        if onceki:
            satirlar.append({"ad": onceki[0], "isaret": "+", "tutar": onceki[1]})
        satirlar += [{"ad": "Dönem başı stok", "isaret": "+", "tutar": t["db"]},
                     {"ad": "Dönem içi alım (finansman dahil)", "isaret": "+", "tutar": t["alim"]},
                     {"ad": "Alım iadesi", "isaret": "−", "tutar": t["iade"]},
                     {"ad": "Dönem içi satılan", "isaret": "−", "tutar": t["satis"]},
                     {"ad": "Şahit numune", "isaret": "−", "tutar": t["sahit"]},
                     {"ad": "Dönem sonu stok (sayım)", "isaret": "−", "tutar": t["ds"]}]
        return {"hesap": gr, "ad": GRUP_ADI[gr], "kalem": int(t["kalem"]), "satirlar": satirlar, "sonuc_ad": sonuc_ad, "sonuc": sonuc}

    tablo = [
        blok("150", "710 · İlk madde ve malzeme gideri", ilk_madde),
        {"hesap": "72x", "ad": "Üretim giderleri", "kalem": 0, "sonuc_ad": "Üretim maliyeti", "sonuc": uretim,
         "satirlar": [{"ad": "710 İlk madde ve malzeme gideri", "isaret": "+", "tutar": ilk_madde},
                      {"ad": "720 Direkt işçilik (gider mizanı)", "isaret": "+", "tutar": iscilik},
                      {"ad": "730 Genel üretim gideri (gider mizanı)", "isaret": "+", "tutar": gug}]},
        blok("151", "Üretilen mamul maliyeti", uretilen, ("Üretim maliyeti", uretim)),
        blok("152", "620 · Satılan mamul maliyeti", smm, ("Üretilen mamul maliyeti", uretilen)),
    ]

    # Excel'in DSS tutarlarıyla karşılaştırma
    excel_dss = {k: _d(v) for k, v in (ozet.get("dss") or {}).items()}
    esit = farkli = 0
    ornek = []
    for kod, e in excel_dss.items():
        x = dss.get(kod)
        if x is None:
            continue
        if _yakin(x["tutar"], e):
            esit += 1
        else:
            farkli += 1
            if len(ornek) < 20:
                ornek.append(kod)

    # stok mizanı ile karşılaştırma (3 haneli hesap)
    mizan = defaultdict(lambda: SIFIR)
    for x in ozet.get("stok_mizan") or []:
        mizan[x["hesap"][:3]] += _d(x["bakiye"])
    mizan_kiyas = [{"hesap": gr, "ad": GRUP_ADI[gr], "mizan": mizan.get(gr, SIFIR), "sayim": g[gr]["ds"],
                    "fark": mizan.get(gr, SIFIR) - g[gr]["ds"]} for gr in ("150", "151", "152", "153") if gr in g or gr in mizan]

    fis = [
        _yon("710", ilk_madde, True, "İlk madde ve malzeme kullanımı"), _yon("150", ilk_madde, False, "İlk madde ve malzeme kullanımı"),
        _yon("151", ilk_madde, True, "710 yansıtma"), _yon("711", ilk_madde, False, "710 yansıtma"),
        _yon("151", iscilik, True, "720 yansıtma"), _yon("721", iscilik, False, "720 yansıtma"),
        _yon("151", gug, True, "730 yansıtma"), _yon("731", gug, False, "730 yansıtma"),
        _yon("152", uretilen, True, "Üretilen mamul"), _yon("151", uretilen, False, "Üretilen mamul"),
        _yon("620", smm, True, "Satılan mamul maliyeti"), _yon("152", smm, False, "Satılan mamul maliyeti"),
    ]
    fis = [x for x in fis if x["borc"] or x["alacak"]]

    return decimal_str({
        "donem": donem_cikis(d, len(b.kalem)),
        "smm": smm, "uretim_maliyeti": uretim, "uretilen": uretilen, "ilk_madde": ilk_madde,
        "donem_sonu_stok": sum((t["ds"] for t in g.values()), SIFIR),
        "satilan_hm_ym": g["150"]["satis"] + g["151"]["satis"],
        "tablo": tablo,
        "dss_kiyas": {"karsilastirilan": esit + farkli, "esit": esit, "farkli": farkli, "farkli_ornek": ornek,
                      "excel_toplam": sum(excel_dss.values(), SIFIR),
                      "bizim_toplam": sum((dss[k]["tutar"] for k in excel_dss if k in dss), SIFIR)},
        "mizan_kiyas": mizan_kiyas, "mizan_tarihi": ozet.get("mizan_tarihi"),
        "yansitilan": {"721": gm.get("721"), "731": gm.get("731")},
        "fis": fis, "fis_borc": sum((x["borc"] for x in fis), SIFIR), "fis_alacak": sum((x["alacak"] for x in fis), SIFIR),
    })
