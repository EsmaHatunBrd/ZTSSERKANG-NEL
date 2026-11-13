"""Maliyet muhasebesi: aylık veri girişi (kaynak bazında yükleme ve elle düzeltme) ve dönem kapanışı (kilit, fiş Excel'i).

Kaynaklar bugünkü SMM Excel'inin sayfa biçimlerini okur (Canias rapor örnekleri gelince uyarlanacak). Dosya, ilgili sayfayı içeren bir
SMM Excel'i de olabilir, tek sayfalık bir rapor da: sayfa adı bulunursa o, yoksa ilk sayfa okunur; başlık satırı ilk satırlarda aranır.
Bir kaynak yüklenince o kaynağın alanları dönemin tüm kalemlerinde sıfırlanıp dosyadakilerle yazılır (yeniden yükleme güvenlidir)."""
import io
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..depo import modeller as m
from .donusum import decimal_str
from .hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi
from .smm_mizan_servisi import elle_sayisi, elle_uyarisi
from .smm_servisi import MAKS_BAYT, SIFIR, _d, _metin, donem_adi, donem_cikis, donem_getir, kilit_denetle

# kaynak -> ad, aranan sayfa, başlık satırını tanıtan metin (kod sütununda), kod sütunu, sıfırlanacak kalem alanları
KAYNAKLAR = {
    "alim": {"ad": "Alım ve satış", "sayfa": "HM-YM ALIŞ SATIŞ", "baslik": "Malzeme(Sınıf)Kodu", "kod": 1,
             "alanlar": ("alim_miktar", "alim_tutar", "satis_miktar")},
    "iade": {"ad": "Alım iadeleri", "sayfa": "İADELER", "baslik": "Malzeme (Sınıf) Kodu", "kod": 0, "alanlar": ("iade_miktar", "iade_tutar")},
    "uretim": {"ad": "Üretim miktarları", "sayfa": "ÜRETİM", "baslik": "MalzemeKodu", "kod": 0, "alanlar": ("uretim_miktar",)},
    "sayim": {"ad": "Sayım (dönem sonu stok)", "sayfa": "DSS", "baslik": "StokKartıKodu", "kod": 0, "alanlar": ("sayim_miktar",)},
    "sahit": {"ad": "Şahit numune", "sayfa": "ŞAHİT", "baslik": "StokKodu", "kod": 0, "alanlar": ("sahit_miktar",)},
    "gider_mizan": {"ad": "Gider mizanı (720 / 730)", "sayfa": "GİDER MİZAN", "baslik": "Hesap Kodu", "kod": 0, "alanlar": ()},
    "stok_mizan": {"ad": "Stok mizanı (150 / 151 / 152)", "sayfa": "STOK MİZAN", "baslik": "Hesap Kodu", "kod": 0, "alanlar": ()},
}
ZORUNLU = ("alim", "uretim", "sayim", "gider_mizan")   # bunlar olmadan SMM hesabı anlamsız


def _satirlar(icerik: bytes, kaynak: str) -> list[tuple]:
    if len(icerik) > MAKS_BAYT:
        raise DogrulamaHatasi("dosya 60 MB'den büyük")
    try:
        wb = load_workbook(io.BytesIO(icerik), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError):
        raise DogrulamaHatasi("dosya geçerli bir .xlsx değil")
    try:
        k = KAYNAKLAR[kaynak]
        ws = wb[k["sayfa"]] if k["sayfa"] in wb.sheetnames else wb.worksheets[0]
        tum = list(ws.iter_rows(values_only=True))
        bas = None
        for i, r in enumerate(tum[:8]):
            if any(_metin(x) == k["baslik"] for x in r):
                bas = i + 1
                break
        if bas is None:
            raise DogrulamaHatasi(f"{k['ad']} dosyasında başlık bulunamadı", {"beklenen": k["baslik"], "sayfa": ws.title})
        return tum[bas:]
    finally:
        wb.close()


def _h(r, i):
    return r[i] if len(r) > i else None


def _kalemler(s: Session, d: m.SmmDonem) -> dict[str, m.SmmKalem]:
    return {k.kod: k for k in s.scalars(select(m.SmmKalem).where(m.SmmKalem.donem_id == d.id))}


def _kaydet_kaynak(d: m.SmmDonem, kaynak: str, dosya: str | None, satir: int, kullanici: str) -> None:
    v = dict(d.veri_kaynaklari or {})
    v[kaynak] = {"dosya": (dosya or "")[-200:] or None, "zaman": datetime.now().isoformat(timespec="seconds"), "kullanici": kullanici,
                 "satir": satir, "excel": False}
    d.veri_kaynaklari = v


def kaynak_yukle(s: Session, donem_id: int, kaynak: str, icerik: bytes, dosya_adi: str, kullanici: str = "sistem") -> dict:
    if kaynak not in KAYNAKLAR:
        raise DogrulamaHatasi("bilinmeyen veri kaynağı", {"kaynak": kaynak, "gecerli": list(KAYNAKLAR)})
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    satirlar = _satirlar(icerik, kaynak)
    k = KAYNAKLAR[kaynak]
    okunan = 0
    elle_silinen = elle_sayisi(d, kaynak)   # yükleme mizanı baştan yazar: elle satırlar ve işaretleri gider
    if kaynak in ("gider_mizan", "stok_mizan"):
        ozet = dict(d.excel_ozet or {})
        isaret = dict(ozet.get("mizan_elle") or {})
        isaret.pop("gider" if kaynak == "gider_mizan" else "stok", None)
        ozet["mizan_elle"] = isaret
        if kaynak == "gider_mizan":
            hesaplar = {}
            for r in satirlar:
                h = _metin(_h(r, 0))
                if h and len(h) == 3 and h.isdigit() and h not in hesaplar and isinstance(_h(r, 6), (int, float)):
                    hesaplar[h] = str(_d(_h(r, 6)))
            if not ({"720", "730"} & set(hesaplar)):
                raise DogrulamaHatasi("gider mizanında 720 / 730 bulunamadı")
            ozet["gider_mizan"] = hesaplar
            ozet.pop("gider_mizan_ad", None)
            d.gider_mizan = {h: hesaplar[h] for h in ("720", "730") if h in hesaplar}
            okunan = len(hesaplar)
        else:
            stok = [{"hesap": _metin(_h(r, 0)), "ad": _metin(_h(r, 1)), "bakiye": str(_d(_h(r, 6)))} for r in satirlar
                    if (_metin(_h(r, 0)) or "")[:2] == "15" and isinstance(_h(r, 6), (int, float))]
            if not stok:
                raise DogrulamaHatasi("stok mizanında 15x hesabı bulunamadı")
            ozet["stok_mizan"] = stok
            okunan = len(stok)
        d.excel_ozet = ozet
    else:
        kalemler = _kalemler(s, d)
        for x in kalemler.values():
            for a in k["alanlar"]:
                setattr(x, a, SIFIR)
        toplam = defaultdict(lambda: defaultdict(lambda: SIFIR))
        adlar: dict[str, dict] = {}
        for r in satirlar:
            kod = _metin(_h(r, k["kod"]))
            if not kod:
                continue
            t = toplam[kod]
            if kaynak == "alim":
                adlar.setdefault(kod, {"ad": _metin(_h(r, 2)), "birim": _metin(_h(r, 5))})
                t["alim_miktar"] += _d(_h(r, 6)); t["alim_tutar"] += _d(_h(r, 10))
                if _metin(_h(r, 19)) == "Satış":
                    t["satis_miktar"] += _d(_h(r, 11))
            elif kaynak == "iade":
                adlar.setdefault(kod, {"ad": _metin(_h(r, 1)), "birim": _metin(_h(r, 4))})
                t["iade_miktar"] += _d(_h(r, 7)); t["iade_tutar"] += _d(_h(r, 8))
            elif kaynak == "uretim":
                adlar.setdefault(kod, {"ad": _metin(_h(r, 1))})
                t["uretim_miktar"] += _d(_h(r, 14))
            elif kaynak == "sayim":
                adlar.setdefault(kod, {"ad": _metin(_h(r, 1))})
                t["sayim_miktar"] += _d(_h(r, 2))
            elif kaynak == "sahit":
                adlar.setdefault(kod, {"ad": _metin(_h(r, 1))})
                if isinstance(_h(r, 9), (int, float)):
                    t["sahit_miktar"] += _d(_h(r, 9))
        for kod, alanlar in toplam.items():
            x = kalemler.get(kod)
            if x is None:
                x = m.SmmKalem(donem_id=d.id, kod=kod, envanterde=False, olusturan=kullanici, **{a: SIFIR for a in (
                    "dbs_miktar", "dbs_tutar", "alim_miktar", "alim_tutar", "iade_miktar", "iade_tutar", "uretim_miktar", "sayim_miktar")})
                s.add(x)
                kalemler[kod] = x
            for a, v in (adlar.get(kod) or {}).items():
                if v and not getattr(x, a, None):
                    setattr(x, a, v)
            for a, v in alanlar.items():
                setattr(x, a, v)
        okunan = len(toplam)
    _kaydet_kaynak(d, kaynak, dosya_adi, okunan, kullanici)
    s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="veri_yukle", eski=None, kullanici=kullanici,
                            yeni={"donem": donem_adi(d), "kaynak": k["ad"], "dosya": dosya_adi, "satir": okunan,
                                  **({"elle_silinen": elle_silinen} if elle_silinen else {})}))
    s.flush()
    return veri_durumu(s, donem_id)


def veri_durumu(s: Session, donem_id: int) -> dict:
    """Dönemin veri kontrol listesi: her kaynak yüklendi mi, kaç kalemde değer var, son kim yükledi; eksik zorunlular."""
    d = donem_getir(s, donem_id)
    kalemler = list(_kalemler(s, d).values())
    vk = d.veri_kaynaklari or {}
    ozet = d.excel_ozet or {}
    kaynaklar = []
    for kod, k in KAYNAKLAR.items():
        if k["alanlar"]:
            dolu = sum(1 for x in kalemler if any(getattr(x, a) for a in k["alanlar"]))
        elif kod == "gider_mizan":
            dolu = len(ozet.get("gider_mizan") or d.gider_mizan or {})
        else:
            dolu = len(ozet.get("stok_mizan") or [])
        son = vk.get(kod)
        elle = elle_sayisi(d, kod)
        kaynaklar.append({"kaynak": kod, "ad": k["ad"], "zorunlu": kod in ZORUNLU, "yuklendi": bool(son) or dolu > 0, "dolu": dolu,
                          "son": son, "elle": elle, "elle_uyari": elle_uyarisi(elle)})
    devir = d.devir_donem_id is not None or (d.kaynak_dosya is not None)
    dbs_dolu = sum(1 for x in kalemler if x.dbs_miktar or x.dbs_tutar)
    gm = d.gider_mizan or {}
    # Stok hesabı (150/151/152) bulunamayan hareketli kalemler SMM tablosuna girmez: tür / mizan kodu boş (ör. alım raporuyla ilk kez gelen kalem)
    from .smm_ozet_servisi import grup
    grupsuz = [x for x in kalemler if grup(x.tur, x.mizan_kodu) is None
               and (x.dbs_tutar or x.alim_tutar or x.iade_tutar or x.sayim_miktar)]
    from .smm_donem_servisi import devir_ozeti
    return decimal_str({
        "devir": devir_ozeti(s, d),   # açılış stoku devralınan dönemin şu anki kapanışıyla uyumlu mu (devir kaynağı yoksa None)
        "donem": donem_cikis(d, len(kalemler)),
        "donem_basi": {"kaynak": "devir" if d.devir_donem_id else ("excel" if d.kaynak_dosya else "yok"), "dolu": dbs_dolu,
                       "tutar": sum((x.dbs_tutar for x in kalemler), SIFIR), "hazir": devir or dbs_dolu > 0},
        "kaynaklar": kaynaklar,
        "eksik": [x["ad"] for x in kaynaklar if x["zorunlu"] and not x["yuklendi"]],
        "ayarlar": {"finansman": d.finansman or SIFIR, "gider_720": _d(gm.get("720")), "gider_730": _d(gm.get("730"))},
        "turler": sorted({x.tur for x in kalemler if x.tur}),
        "grupsuz": {"kalem": len(grupsuz), "alim_tutar": sum((x.alim_tutar or SIFIR for x in grupsuz), SIFIR),
                    "dbs_tutar": sum((x.dbs_tutar or SIFIR for x in grupsuz), SIFIR), "ornek": sorted(x.kod for x in grupsuz)[:10]},
    })


def ayarlar_guncelle(s: Session, donem_id: int, finansman: Decimal | None = None, gider_720: Decimal | None = None,
                     gider_730: Decimal | None = None, kullanici: str = "sistem") -> dict:
    """Finansman (alımlara dağıtılır) ve 720 / 730 gider tutarlarını elle girer."""
    d = donem_getir(s, donem_id)
    kilit_denetle(d)
    for ad, v in (("finansman", finansman), ("gider_720", gider_720), ("gider_730", gider_730)):
        if v is not None and v < 0:
            raise DogrulamaHatasi("tutar eksi olamaz", {ad: str(v)})
    eski = {"finansman": str(d.finansman or SIFIR), **{f"gider_{h}": (d.gider_mizan or {}).get(h) for h in ("720", "730")}}
    if finansman is not None:
        d.finansman = finansman
    gm = dict(d.gider_mizan or {})
    ozet = dict(d.excel_ozet or {})
    gmo = dict(ozet.get("gider_mizan") or {})
    isaret = dict(ozet.get("mizan_elle") or {})
    for h, v in (("720", gider_720), ("730", gider_730)):
        if v is not None:
            if h not in gmo or _d(gmo[h]) != v:
                isaret["gider"] = sorted(set(isaret.get("gider") or []) | {h})   # elle girilen tutar mizan satırında işaretlenir
            gm[h] = str(v)
            gmo[h] = str(v)
    ozet["mizan_elle"] = isaret
    d.gider_mizan = gm
    ozet["gider_mizan"] = gmo
    d.excel_ozet = ozet
    yeni = {"finansman": str(d.finansman or SIFIR), **{f"gider_{h}": gm.get(h) for h in ("720", "730")}}
    if eski != yeni:
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="ayar_guncelle", eski=eski, yeni=yeni, kullanici=kullanici))
    s.flush()
    return veri_durumu(s, donem_id)


def _tl(x) -> str:
    """1234567.891 -> '1.234.567,89' (uyarı metinleri için)."""
    return f"{_d(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def kapanis_eksikleri(s: Session, donem_id: int) -> list[str]:
    """Dönem kapatılmadan önce giderilmesi beklenenler: yüklenmemiş zorunlu kaynak, türü boş kalem, açılış–önceki kapanış uyumsuzluğu."""
    v = veri_durumu(s, donem_id)
    eksikler = [f"Eksik veri: {ad}" for ad in v["eksik"]]
    if v["grupsuz"]["kalem"]:
        eksikler.append(f"{v['grupsuz']['kalem']} kalemin türü / mizan kodu boş; SMM tablosuna girmiyor")
    dv = v.get("devir")
    if dv and not dv["uyumlu"]:
        eksikler.append(f"Açılış stoku {dv['onceki_ad']} kapanışıyla uyuşmuyor ({dv['fark_kalem']} kalem, fark {_tl(dv['fark_tutar'])} TL)")
    return eksikler


def kilit(s: Session, donem_id: int, kilitli: bool, kullanici: str = "sistem", zorla: bool = False) -> dict:
    """Dönemi kapatır ya da kilidi açar. Kapatırken eksik varsa ve `zorla` değilse 409 `kapanis_eksik`. Kilidi açarken: açılışını bu
    dönemden devralmış dönem kilitliyse 409 `sonraki_kilitli`; kilitli değilse yanıtta `uyari` (devri yenileyin). Rol denetimi API'de."""
    from .smm_donem_servisi import sonraki_donemler
    d = donem_getir(s, donem_id)
    uyari = None
    if bool(d.kilitli) != kilitli:
        kayit = {"donem": donem_adi(d)}
        if kilitli:
            eksikler = kapanis_eksikleri(s, donem_id)
            if eksikler and not zorla:
                raise CatismaHatasi(f"{donem_adi(d)} kapatılmadan önce eksikler var", {"eksikler": eksikler}, kod="kapanis_eksik")
            if eksikler:
                kayit.update(zorla=True, eksikler=eksikler)
        else:
            sonrakiler = sonraki_donemler(s, d)
            kapali = next((x for x in sonrakiler if x.kilitli), None)
            if kapali is not None:
                raise CatismaHatasi(f"önce {donem_adi(kapali)} kilidini açın; açılışı bu dönemden devralındı", {"donem_id": kapali.id},
                                    kod="sonraki_kilitli")
            if sonrakiler:
                uyari = f"{donem_adi(sonrakiler[0])} açılışı bu dönemden devralındı; değişiklik sonrası devri yenileyin"
        d.kilitli = kilitli
        d.kilitleyen = kullanici if kilitli else None
        s.add(m.DegisiklikKaydi(tablo="smm_donem", kayit_id=d.id, islem="kilitle" if kilitli else "kilit_ac", eski=None,
                                yeni=kayit, kullanici=kullanici))
        s.flush()
    return {**donem_cikis(d), "uyari": uyari}


def fis_excel(s: Session, donem_id: int) -> tuple[bytes, str]:
    """SMM fişi taslağı ve SMM tablosu (.xlsx): Canias'a aktarım ya da kontrol için."""
    from .smm_ozet_servisi import smm_ozeti
    d = donem_getir(s, donem_id)
    o = smm_ozeti(s, donem_id)
    wb = Workbook()
    ws = wb.active
    ws.title = "SMM Fişi"
    kalin = Font(bold=True)
    ws.append([f"Zeytursan — {donem_adi(d)} SMM fişi taslağı" + ("" if d.kilitli else " (dönem kilitli değil)")])
    ws["A1"].font = kalin
    ws.append(["Hesap Kodu", "Hesap Adı", "Açıklama", "Borç", "Alacak"])
    for c in ws[2]:
        c.font = kalin
    for f in o["fis"]:
        ws.append([f["hesap"], f["ad"], f"{donem_adi(d)} {f['aciklama']}", float(_d(f["borc"])) or None, float(_d(f["alacak"])) or None])
    ws.append(["", "", "Toplam", float(_d(o["fis_borc"])), float(_d(o["fis_alacak"]))])
    for c in ws[ws.max_row]:
        c.font = kalin
    for col, w in zip("ABCDE", (12, 40, 44, 18, 18)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=3, min_col=4, max_col=5):
        for c in row:
            c.number_format = "#,##0.00"
    t = wb.create_sheet("SMM Tablosu")
    t.append([f"{donem_adi(d)} SMM tablosu"])
    t["A1"].font = kalin
    for b in o["tablo"]:
        t.append([])
        t.append([b["hesap"], b["ad"]])
        t[t.max_row][0].font = kalin
        for x in b["satirlar"]:
            t.append(["", f"{x['isaret']} {x['ad']}", float(_d(x["tutar"]))])
        t.append(["", f"= {b['sonuc_ad']}", float(_d(b["sonuc"]))])
        t[t.max_row][1].font = kalin
    t.column_dimensions["B"].width = 44
    t.column_dimensions["C"].width = 20
    for row in t.iter_rows(min_col=3, max_col=3):
        for c in row:
            c.number_format = "#,##0.00"
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue(), f"{d.yil}-{d.ay:02d} SMM fişi.xlsx"
