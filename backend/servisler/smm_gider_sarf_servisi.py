"""Maliyet muhasebesi tabloları (16.11.2026): gider dağıtım tablosu (720 / 730 aşamalara nasıl dağıldı) ve en büyük sarf farkları.

Bu modül YENİ HESAP KURALI İÇERMEZ; var olan sonuçları yeniden sunar:
    gider dağıtımı = aşama hesabı (smm_asama_servisi._Baglam) ürün sonuçları: dağıtılan = Σ (birim işçilik + birim GÜG) × üretim miktarı
                     (Üretim Maliyeti ekranındaki aşama özetinin işçilik + GÜG toplamıyla aynı)
    mizan tutarı   = SmmDonem.gider_mizan (aşama ekranının "dağıtılmayan" hesabıyla aynı kaynak; gider mizanı yüklemesi, mizan elle
                     girişi ve dönem ayarlarındaki 720 / 730 alanı bu kaynağı birlikte günceller)
    sarf farkları  = smm_asama_servisi.sarf_farki sonucu (birim fiyat ve birim uyumsuzluk kuralı orada)

720 / 730 ayrımı: aşama hesabında yalnız 40 aşamasının havuzları ayrıdır (40 işçilik -> 720, 40 GÜG -> 730). 20 ve 50 aşamalarının
havuzu Excel'de olduğu gibi "işçilik + GÜG" tek tutardır; bu tutar 720 ile 730 arasında BÖLÜNMEZ (kural uydurulmaz), `ayrilmamis`
olarak ayrı verilir. Bu durumda hesap bazında dağıtılmayan hesaplanamaz (null); kesin olan 720 + 730 toplamıdır (`toplam`).
Oranlar kesir (0.05 = %5). Tutarlar Decimal; çıktıda metin. Hiçbir kayıt değiştirilmez."""
from decimal import ROUND_HALF_UP, Decimal
from sqlalchemy.orm import Session
from .donusum import decimal_str
from .smm_asama_servisi import ASAMA_ADLARI, _Baglam, _havuz, dagitim_anahtarlari, sarf_farki
from .smm_servisi import SIFIR, _d, donem_cikis, donem_getir

KURUS = Decimal("0.01")
ESIK_YUZDE = Decimal("0.05")   # arayüzde sarı vurgu eşiği (dağıtılmayan / mizan)
ANAHTAR_SECENEK_ADI = {"uretim": "Üretim miktarı", "dolum_sn": "Üretim × dolum sn", "dolum_adam_sn": "Üretim × dolum adam-sn",
                       "etiket_sn": "Üretim × etiket sn", "etiket_adam_sn": "Üretim × etiket adam-sn"}
HESAP_ADI = {"720": "Direkt işçilik giderleri", "730": "Genel üretim giderleri"}
URETIM_HAVUZU = {20: ("20_uretim",), 40: ("40_iscilik", "40_gug"), 50: ("50_uretim",)}
STOK_HAVUZU = {20: ("20_stok",), 40: ("40_stok_iscilik", "40_stok_gug"), 50: ("50_stok",)}


def _bol(a: Decimal, b: Decimal) -> Decimal | None:
    return a / b if b else None


def _k(x: Decimal) -> Decimal:
    """Tablo tutarları kuruşa yuvarlanır (yarım yukarı); aşama toplamı = yuvarlanmış işçilik + yuvarlanmış GÜG, dağıtılan = aşama
    toplamlarının toplamı, dağıtılmayan = mizan − dağıtılan (böylece toplamlar kuruşu kuruşuna tutar)."""
    return x.quantize(KURUS, rounding=ROUND_HALF_UP)


def _tl(x: Decimal) -> str:
    """Not metinleri için: 1234567.891 -> '1.234.568 TL'."""
    return f"{x.quantize(Decimal(1)):,.0f}".replace(",", ".") + " TL"


def _anahtar_adi(d, asama: int) -> str:
    a = dagitim_anahtarlari(d)
    if asama == 40:
        return f"İşçilik: {ANAHTAR_SECENEK_ADI[a['40_iscilik']]} · GÜG: {ANAHTAR_SECENEK_ADI[a['40_gug']]}"
    return ANAHTAR_SECENEK_ADI[a[str(asama)]]


def gider_dagitimi(s: Session, donem_id: int, ilk: int = 20) -> dict:
    d = donem_getir(s, donem_id)
    b = _Baglam(s, d)
    havuz = _havuz(d)
    notlar: list[str] = []

    asamalar, urunler = [], []
    ayri = {"720": SIFIR, "730": SIFIR}
    ayrilmamis = SIFIR
    for a in (20, 40, 50):
        sonuc = b.sonuc.get(a, {})
        isc = gug = uretim = SIFIR
        pay_alan = sure_yok = elle = 0
        for x in sonuc.values():
            r = x["uretim_miktar"]
            ui, ug = x["iscilik"] * r, x["gug"] * r
            isc += ui
            gug += ug
            uretim += r
            if ui + ug:
                pay_alan += 1
                ui, ug = _k(ui), _k(ug)
                urunler.append({"kod": x["kod"], "ad": x["ad"], "asama": a, "iscilik": ui, "gug": ug, "toplam": ui + ug})
            if r and x["sure_yok"]:
                sure_yok += 1
            if r and {"iscilik", "gug"} & set(x["elle_alanlar"]):
                elle += 1
        isc, gug = _k(isc), _k(gug)
        toplam = isc + gug
        birlesik = a != 40
        if birlesik:
            ayrilmamis += toplam
        else:
            ayri["720"] += isc
            ayri["730"] += gug
        h = sum((havuz[k] for k in URETIM_HAVUZU[a]), SIFIR)
        asamalar.append({"asama": a, "ad": ASAMA_ADLARI[a], "anahtar": _anahtar_adi(d, a), "birlesik": birlesik, "havuz": h,
                         "iscilik": isc, "gug": gug, "toplam": toplam, "pay_yuzde": None, "urun_sayisi": pay_alan,
                         "uretim_miktar": uretim, "birim_basina_ortalama": _bol(toplam, uretim)})
        # Havuz ile ürünlere dağılan arasındaki farkın mevcut hesaptan görülebilen nedenleri
        fark = h - toplam
        if h and not uretim:
            notlar.append(f"{a} aşamasında bu dönem üretim yok: havuzdaki {_tl(h)} üretimi olmayan aşamaya düşen pay olarak dağıtılmadı.")
        elif h and uretim and not pay_alan:
            notlar.append(f"{a} aşamasında hiçbir ürün pay almadı (dağıtım anahtarının süresi girilmemiş): havuzdaki {_tl(h)} dağıtılmadı.")
        elif abs(fark) >= 1:
            neden = f"; {elle} üründe işçilik / GÜG elle girilmiş" if elle else ""
            notlar.append(f"{a} aşaması: havuz {_tl(h)}, ürünlere dağılan {_tl(toplam)}, fark {_tl(fark)}{neden}.")
        if sure_yok:
            notlar.append(f"{a} aşamasında üretim süresi girilmemiş {sure_yok} ürün pay almadı; havuz süresi olan ürünlere dağıldı.")
        stok = sum((havuz[k] for k in STOK_HAVUZU[a]), SIFIR)
        if stok:
            notlar.append(f"{a} aşamasının dönem sonu stok payı havuzu {_tl(stok)}: birim maliyete stok payı olarak eklenir, "
                          f"bu tablodaki işçilik / GÜG toplamına girmez.")
    dagitilan = sum((x["toplam"] for x in asamalar), SIFIR)
    for x in asamalar:
        x["pay_yuzde"] = _bol(x["toplam"], dagitilan)

    gm = d.gider_mizan or {}
    mizan_var = bool(gm)
    if not mizan_var:
        notlar.insert(0, "Gider mizanı (720 / 730) girilmemiş: dağıtılmayan tutar hesaplanamaz.")
    havuz_top = sum((havuz[k] for ks in URETIM_HAVUZU.values() for k in ks), SIFIR)
    mizan_top = sum((_d(gm.get(h)) for h in ("720", "730")), SIFIR)
    if mizan_var and abs(mizan_top - havuz_top) >= 1:
        notlar.insert(0, f"Aşama havuzlarına girilen işçilik + GÜG {_tl(havuz_top)}, gider mizanı 720 + 730 {_tl(mizan_top)}: "
                         f"{_tl(mizan_top - havuz_top)} havuzlara aktarılmamış (havuzlar Üretim Maliyeti ekranında değiştirilir).")
    if ayrilmamis:
        notlar.append(f"20 ve 50 aşamalarının havuzu işçilik + GÜG tek tutardır ({_tl(ayrilmamis)}); 720 ile 730 arasında bölünmediği için "
                      f"hesap bazında dağıtılmayan verilemez, 720 + 730 toplamı kesindir.")

    kaynaklar = []
    for h in ("720", "730"):
        mz = _d(gm.get(h)) if h in gm else None
        dg = ayri[h]
        kesin = mz is not None and not ayrilmamis
        kaynaklar.append({"hesap": h, "ad": HESAP_ADI[h], "mizan_tutari": mz, "dagitilan": dg,
                          "dagitilan_kapsami": "40 · işçilik" if h == "720" else "40 · GÜG",
                          "dagitilmayan": mz - dg if kesin else None, "dagitilmayan_yuzde": _bol(mz - dg, mz) if kesin else None})
    toplam = {"mizan_tutari": mizan_top if mizan_var else None, "dagitilan": dagitilan,
              "dagitilmayan": mizan_top - dagitilan if mizan_var else None,
              "dagitilmayan_yuzde": _bol(mizan_top - dagitilan, mizan_top) if mizan_var else None}
    urunler.sort(key=lambda x: (-x["toplam"], x["asama"], x["kod"]))
    return decimal_str({"donem": donem_cikis(d, len(b.kalem)), "kaynaklar": kaynaklar, "toplam": toplam, "ayrilmamis": ayrilmamis,
                        "havuz_toplami": havuz_top, "asamalar": asamalar, "urunler_ilk20": urunler[:ilk], "urun_sayisi": len(urunler),
                        "esik_yuzde": ESIK_YUZDE, "notlar": notlar})


def sarf_farki_ozeti(s: Session, donem_id: int, ilk: int = 20) -> dict:
    """Tutara (mutlak) göre en büyük ilk N sarf farkı. Birim uyumsuz satırlar sıralamaya girmez, ayrı sayılır; farkı 0 olanlar girmez.
    fark_tutar = fark miktarı × sarf farkı ekranındaki birim fiyat (dönem ortalaması; üretilen kalemde aşama maliyeti).
    Özet toplamları sarf farkı ekranının toplamlarıyla aynı: eksik_tutar eksi işaretlidir, toplam_fark_tutari = fazla + eksik (net)."""
    v = sarf_farki(s, donem_id)   # süzgeçsiz: tüm kalemler; çıktı metin, Decimal'e kesin döner
    kalemler = []
    for x in v["kayitlar"]:
        if x["birim_uyumsuz"]:
            continue
        ft = Decimal(x["fark_tutar"])
        if not ft:
            continue
        kalemler.append({"kod": x["kod"], "ad": x["ad"], "birim": x["birim"], "tur": x["tur"], "birim_fiyat": x["ortalama_fiyat"],
                         "beklenen_sarf": x["recete_sarf"], "gercek_sarf": x["stok_sarf"], "fark_miktar": x["fark"], "fark_tutar": ft,
                         "fark_yuzde": x["fark_orani"], "yon": "fazla" if ft > 0 else "eksik"})
    kalemler.sort(key=lambda x: (-abs(x["fark_tutar"]), x["kod"]))
    top = v["toplamlar"]
    fazla, eksik = _d(top.get("fazla")), _d(top.get("eksik"))
    return decimal_str({"donem": v["donem"], "ilk": ilk, "kalem_sayisi": len(kalemler), "kalemler": kalemler[:ilk],
                        "ozet": {"toplam_fark_tutari": fazla + eksik, "fazla_tutar": fazla, "eksik_tutar": eksik,
                                 "fazla_sayisi": sum(1 for x in kalemler if x["yon"] == "fazla"),
                                 "eksik_sayisi": sum(1 for x in kalemler if x["yon"] == "eksik"),
                                 "birim_uyumsuz_sayisi": v["birim_uyumsuz_sayisi"]}})
