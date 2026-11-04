# backend/servisler/import_servisi.py
"""Excel içe aktarma. Faz 1 excel_okuyucu'yu kullanır; önizleme olmadan fiyat yazmaz."""
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import SIFIR
from ..depo import modeller as m
from .. import tohum
from .hatalar import DogrulamaHatasi
from . import fiyat_servisi, gider_servisi, hesap_servisi, kapasite_servisi, parametre_servisi, recete_servisi

HAVUZ_ESLEME = [  # (kod, ad, GiderHavuzlari alanı toplam, baz_tipi, baz alanı veya None, pay alanı veya None)
    ("dolum_iscilik", "Dolum doğrudan işçilik", "dolum_iscilik_toplam", "saniye", "dolum_iscilik_saniye", None),
    ("mal_kabul_iscilik", "Mal kabul doğrudan işçilik", "mal_kabul_iscilik_toplam", "kg", None, "mal_kabul_paylari"),
    ("etiket_iscilik", "Etiketleme doğrudan işçilik", "etiket_iscilik_toplam", "saniye", "etiket_iscilik_saniye", None),
    ("endirekt_iscilik", "Endirekt işçilik", "endirekt_iscilik_toplam", "saniye", "endirekt_saniye", None),
    ("mal_kabul_gug", "Mal kabul genel üretim gideri", "mal_kabul_gug_toplam", "kg", None, "mal_kabul_gug_paylari"),
    ("diger_gug", "Diğer genel üretim giderleri", "diger_gug_toplam", "saniye", "diger_gug_saniye", None),
    ("elektrik", "Elektrik", "elektrik_toplam", "saniye", None, "elektrik_hatlar"),
    ("dogalgaz", "Doğalgaz", "dogalgaz_toplam", "saniye", None, "dogalgaz_hatlar"),
    ("amortisman", "Amortisman", "amortisman_toplam", "saniye", None, "amortisman_hatlar"),
    ("yonetim", "Genel yönetim giderleri", "yonetim_toplam", "adet", None, None),
    ("pazarlama", "Pazarlama satış giderleri", "pazarlama_toplam", "adet", None, None),
]


# S.ALMA BF: F (6. sütun) ilk bütçe fiyatı, I (9. sütun, aynı başlık) sonradan yapılan güncelleme (muhasebe: eski değer görünsün diye sağa yazılır).
# İkisi aynı güne iki kayıt olarak girer; sonradan eklenen (I) geçerli olandır.
SUTUN_ILK_FIYAT = 5
SUTUN_REVIZE_FIYAT = 8
NEDEN_ILK = "İlk bütçe (S.ALMA BF F)"
NEDEN_REVIZE = "Revize (S.ALMA BF I)"
KAYNAK_REVIZE = "import-revize"


def _ondalik(v) -> Decimal | None:
    """Hücre değeri -> Decimal; boş -> None. Sayı değilse/negatifse/sonsuzsa ValueError."""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise ValueError("bool")
    try:
        d = Decimal(str(v).strip()) if isinstance(v, str) else Decimal(str(v))
    except ArithmeticError as e:
        raise ValueError(str(e)) from e
    if not d.is_finite() or d < 0:
        raise ValueError("negatif ya da sonsuz")
    return d


_TR = str.maketrans("İIışğüöçŞĞÜÖÇ", "iiisguocsguoc")


def _revize_basligi_uygun(ws) -> bool:
    """I sütununun başlığı boş ya da 'fiyat' içermeli; başka bir başlık varsa (farklı düzen) I yok sayılır."""
    baslik = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    v = baslik[SUTUN_REVIZE_FIYAT] if len(baslik) > SUTUN_REVIZE_FIYAT else None
    return v is None or v == "" or "fiyat" in str(v).translate(_TR).lower()


def revize_fiyatlarini_oku(ws) -> tuple[dict[str, Decimal], list[str]]:
    """(kod -> I fiyatı, hatalı kodlar). I boş ya da F'ye eşitse revize yok. I sayı değilse / negatifse kod hatalıdır.
    I başlığı fiyat başlığı değilse (farklı düzen) hiç okunmaz."""
    revize: dict[str, Decimal] = {}
    hatali: list[str] = []
    if not _revize_basligi_uygun(ws):
        return revize, hatali
    for satir in ws.iter_rows(min_row=2, values_only=True):
        kod = satir[0] if satir else None
        if not kod or not str(kod).strip():
            continue
        kod = str(kod).strip()
        ham = satir[SUTUN_REVIZE_FIYAT] if len(satir) > SUTUN_REVIZE_FIYAT else None
        if ham is None or ham == "":
            continue
        try:
            i = _ondalik(ham)
        except ValueError:
            hatali.append(kod); continue
        try:
            f = _ondalik(satir[SUTUN_ILK_FIYAT] if len(satir) > SUTUN_ILK_FIYAT else None)
        except ValueError:
            f = None
        if f is not None and f == i:
            continue
        revize[kod] = i
    return revize, hatali


def revize_fiyatlarini_oku_dosyadan(dosya_yolu: Path) -> dict[str, Decimal]:
    """Tam kitap ya da tek sayfalık dosyadan revize fiyatları (S.ALMA BF sayfası, yoksa ilk sayfa). Hatalı satırlar atlanır."""
    wb = openpyxl.load_workbook(dosya_yolu, data_only=True, read_only=True)
    try:
        ws = wb["S.ALMA BF"] if "S.ALMA BF" in wb.sheetnames else wb.worksheets[0]
        return revize_fiyatlarini_oku(ws)[0]
    finally:
        wb.close()


def _ayni_fiyat_kaydi_var_mi(s: Session, senaryo_id: int, kod: str, fiyat: Decimal) -> bool:
    return s.scalar(select(m.MalzemeFiyati.id).join(m.Malzeme, m.Malzeme.id == m.MalzemeFiyati.malzeme_id).where(
        m.Malzeme.kod == kod, m.MalzemeFiyati.senaryo_id == senaryo_id, m.MalzemeFiyati.fiyat == fiyat).limit(1)) is not None


def revize_ile_fiyat_ekle(s: Session, senaryo_id: int, kod: str, ilk: Decimal | None, revize: Decimal | None, gecerlilik_basi: date, neden: str,
                          kullanici: str, para_birimi: str | None = None, yeni_kayit: bool = False) -> int:
    """İlk bütçe (F) ve varsa revize (I) fiyatını aynı güne iki kayıt olarak yazar; sonradan eklenen revize geçerli olandır.
    Revize varsa F yalnız senaryoda o değerde kayıt yoksa yazılır (eski yüklemeden gelen F ya da önceki revizyon turu yinelenmez).
    yeni_kayit=True: senaryoda bu kodun kaydı olmadığı biliniyor, sorgu atlanır. Döner: yazılan revize kaydı sayısı (0/1)."""
    ilk_var = ilk is not None and ilk != SIFIR
    if revize is None:
        if ilk_var:
            fiyat_servisi.fiyat_ekle(s, senaryo_id, kod, ilk, gecerlilik_basi, neden, kaynak="import", para_birimi=para_birimi, olusturan=kullanici)
        return 0
    if ilk_var and (yeni_kayit or not _ayni_fiyat_kaydi_var_mi(s, senaryo_id, kod, ilk)):
        fiyat_servisi.fiyat_ekle(s, senaryo_id, kod, ilk, gecerlilik_basi, f"{neden} · {NEDEN_ILK}", kaynak="import", para_birimi=para_birimi, olusturan=kullanici)
    fiyat_servisi.fiyat_ekle(s, senaryo_id, kod, revize, gecerlilik_basi, f"{neden} · {NEDEN_REVIZE}", kaynak=KAYNAK_REVIZE, para_birimi=para_birimi,
                             olusturan=kullanici)
    return 1


def _seviye_degeri(v) -> int | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v) if v == int(v) and v >= 0 else None
    v = str(v).strip()
    return int(v) if v.isdigit() else None   # boş ve sayı olmayan hücreler ('A' gibi) -> None


def recete_seviyeleri_oku(ws_v) -> list[int | None]:
    """Ürün sayfasının reçete bloğunda (urun_oku ile aynı satır aralığı ve aynı 'D dolu' süzgeci) A sütunundaki seviyeyi sırayla döner.
    Salt okuma; fiyat_motoru.excel_okuyucu'ya dokunmaz."""
    r100 = eo._etiket_satiri(ws_v, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    return [_seviye_degeri(ws_v[f"A{r}"].value) for r in range(6, r100) if ws_v[f"D{r}"].value]


def sezon_getir_veya_olustur(s: Session, ad: str) -> m.Sezon:
    if not re.fullmatch(r"\d{4}-\d{4}", ad or ""):
        raise DogrulamaHatasi("sezon adı YYYY-YYYY olmalı", {"sezon_ad": ad})
    sz = s.scalar(select(m.Sezon).where(m.Sezon.ad == ad))
    if sz is None:
        y1 = int(ad.split("-")[0]); sz = m.Sezon(ad=ad, baslangic=date(y1, 6, 1), bitis=date(y1 + 1, 5, 31)); s.add(sz); s.flush()
    return sz


_sezon = sezon_getir_veya_olustur


def _parametre_sozlugu(p) -> dict[str, Decimal]:
    """Parametreler -> {anahtar: değer} (parametre_servisi anahtar biçimi)."""
    d = {"enflasyon": p.enflasyon, "satis_kar": p.satis_kar_orani, "vardiya_saati": p.vardiya_saati}
    d.update({f"kur.{k}": v for k, v in p.kurlar.items()})
    d.update({f"faiz.{k}": v for k, v in p.faiz_oranlari.items()})
    d.update({f"stok_ay.{k}": v for k, v in p.stok_sureleri_ay.items()})
    d.update({f"teklif_kar.{i}": v for i, v in enumerate(p.teklif_kar_oranlari, 1)})
    return d


def _genel_parametre_var_mi(s: Session, senaryo_id: int, anahtar: str) -> bool:
    return s.scalar(select(m.ParametreDegeri.id).join(m.Parametre).where(
        m.Parametre.anahtar == anahtar, m.ParametreDegeri.senaryo_id == senaryo_id, m.ParametreDegeri.kapsam_tipi == "genel").limit(1)) is not None


def _parametreleri_yaz(s, senaryo_id, p, tarih, neden, ek: dict | None = None, yalniz_eksik: bool = False):
    """yalniz_eksik=True: senaryoda genel kaydı olan anahtarlara dokunulmaz. ek: ek_parametreleri_oku çıktısı (maliyet sapma + not)."""
    n = 0
    degerler = _parametre_sozlugu(p)
    if ek is not None:
        degerler["maliyet_sapma"] = ek["maliyet_sapma"]
    for anahtar, v in degerler.items():
        if yalniz_eksik and _genel_parametre_var_mi(s, senaryo_id, anahtar):
            continue
        parametre_servisi.deger_ekle(s, senaryo_id, anahtar, v, tarih, neden, olusturan="import"); n += 1
    return n


def _satis_notunu_yaz(s, senaryo_id, ek: dict, tarih, neden) -> int:
    """Not senaryoda hiç yoksa yazar (var olana dokunmaz); yazdıysa 1."""
    if not ek["satis_fiyati_notu"] or parametre_servisi.metin_gecmis(s, senaryo_id, "satis_fiyati_notu"):
        return 0
    parametre_servisi.metin_deger_ekle(s, senaryo_id, "satis_fiyati_notu", ek["satis_fiyati_notu"], tarih, neden, olusturan="import")
    return 1


MALZEME_KART_ALANLARI = ("ad", "tip", "birim", "para_birimi", "zs")
URUN_KART_ALANLARI = ("ad", "ambalaj_hacmi", "hat", "taze_tursu_sinifi", "suzme_kg", "pazar")


def _fiyati_var_mi(s: Session, senaryo_id: int, kod: str) -> bool:
    return s.scalar(select(m.MalzemeFiyati.id).join(m.Malzeme, m.Malzeme.id == m.MalzemeFiyati.malzeme_id).where(
        m.Malzeme.kod == kod, m.MalzemeFiyati.senaryo_id == senaryo_id).limit(1)) is not None


def _fark_alanlari(kayit, yeni: dict) -> list[str]:
    return [a for a, v in yeni.items() if getattr(kayit, a) != v]


def excel_tam_yukle(s: Session, excel_yolu: Path, sezon_ad: str, senaryo_ad: str, tur: str = "fiyat_calismasi", kullanici: str = "sistem",
                    kartlari_guncelle: bool = True, senaryo_id: int | None = None, kaynak_dosya: str | None = None, revize_uygula: bool = True) -> dict:
    """kaynak_dosya: arşivde gösterilen dosya adı (Senaryo.kaynak_dosya). senaryo_id verilirse 'tamamla' modu: Sezon/Senaryo açılmaz (sezon_ad/senaryo_ad/tur yok sayılır); yalnız senaryoda eksik olanlar yazılır, var olan hiçbir şey ezilmez.
    kartlari_guncelle=False: var olan Urun/Malzeme kartlarına dokunulmaz (yalnız yeniler açılır); iki modda da farklar ozet['kart_farklari']'nda.
    revize_uygula=False: S.ALMA BF I sütunu (revize fiyat) yok sayılır, yalnız F yazılır (Excel paritesi testleri; Excel ürün sayfaları F'ye bakar)."""
    try:
        ozet = _excel_tam_yukle(s, excel_yolu, sezon_ad, senaryo_ad, tur, kullanici, kartlari_guncelle, senaryo_id, revize_uygula)
        if kaynak_dosya:
            s.get(m.Senaryo, ozet["senaryo_id"]).kaynak_dosya = kaynak_dosya
            s.flush()
        return ozet
    except (KeyError, ValueError, StopIteration) as e:
        raise DogrulamaHatasi(f"çalışma kitabı beklenen yapıda değil: {e!r}")


def _excel_tam_yukle(s: Session, excel_yolu: Path, sezon_ad: str, senaryo_ad: str, tur: str, kullanici: str, kartlari_guncelle: bool, senaryo_id: int | None = None,
                     revize_uygula: bool = True) -> dict:
    wb_f, wb_v = eo.excel_ac(Path(excel_yolu))
    tamamla = senaryo_id is not None
    if tamamla:
        sen = hesap_servisi.senaryo_getir(s, senaryo_id); sz = sen.sezon
        kartlari_guncelle = False   # tamamla modu hiçbir kartı ezmez
    else:
        sz = _sezon(s, sezon_ad)
        sen = m.Senaryo(sezon_id=sz.id, tur=tur, ad=senaryo_ad, olusturan=kullanici); s.add(sen); s.flush()
    tohum.parametreleri_tohumla(s)
    ozet = {"senaryo_id": sen.id, "malzeme": 0, "fiyat": 0, "havuz": 0, "ambalaj": 0, "urun": 0, "recete": 0, "parametre": 0, "atlanan": [], "uyarilar": [],
            "kart_farklari": [], "yeniden_adlandirilan": [], "urun_parametre_farklari": [], "kapasite": 0,
            "mod": "tamamla" if tamamla else "yeni", "satis_notu": 0, "revize": 0}

    mevcut_malzeme = {mz.kod: mz for mz in s.scalars(select(m.Malzeme))}
    excel_malzemeleri = eo.malzemeleri_oku(wb_v)
    revize, revize_hatali = revize_fiyatlarini_oku(wb_v["S.ALMA BF"]) if revize_uygula else ({}, [])
    for kod in revize_hatali:
        ozet["uyarilar"].append(f"S.ALMA BF: {kod} satırında I sütunu (revize fiyat) sayı değil ya da negatif; revize yok sayıldı, F yazıldı")
    for kod, mz in excel_malzemeleri.items():
        kart = mevcut_malzeme.get(kod)
        if kart is None:
            fiyat_servisi.malzeme_ekle_veya_guncelle(s, kod, mz.ad, mz.tip, mz.birim, mz.para_birimi, mz.zs, kullanici)
        else:
            fark = _fark_alanlari(kart, {a: getattr(mz, a) for a in MALZEME_KART_ALANLARI})
            if fark:
                ozet["kart_farklari"].append({"tur": "malzeme", "kod": kod, "alanlar": fark})
            if kartlari_guncelle:
                fiyat_servisi.malzeme_ekle_veya_guncelle(s, kod, mz.ad, mz.tip, mz.birim, mz.para_birimi, mz.zs, kullanici)
        if not tamamla or kart is None:
            ozet["malzeme"] += 1
        fiyat_var = (mz.fiyat and mz.fiyat != SIFIR) or kod in revize
        if fiyat_var and not (tamamla and _fiyati_var_mi(s, sen.id, kod)):
            ozet["revize"] += revize_ile_fiyat_ekle(s, sen.id, kod, mz.fiyat, revize.get(kod), sz.baslangic, "Excel bütçe fiyatı", kullanici,
                                                    yeni_kayit=not tamamla)
            ozet["fiyat"] += 1

    h = eo.havuzlari_oku(wb_v)
    formuller = eo.havuz_formulleri_oku(wb_f["Gider Dağıtım"])   # taban × çarpan kalıbı (B3): çarpanlar arayüzde düzenlenebilir kalır
    mevcut_havuz = gider_servisi.havuzlar(s, sen.id) if tamamla else {}
    for kod, ad, toplam_alani, baz_tipi, baz_alani, pay_alani in HAVUZ_ESLEME:
        paylar = [(k, p, b) for k, (p, b) in getattr(h, pay_alani).items()] if pay_alani else []
        if tamamla and kod in mevcut_havuz:
            continue
        toplam, taban, carpanlar = gider_servisi.excel_taban_carpan(getattr(h, toplam_alani), formuller.get(toplam_alani))
        gider_servisi.havuz_kaydet(s, sen.id, kod, ad, toplam, baz_tipi, getattr(h, baz_alani) if baz_alani else None, paylar, kullanici,
                                   taban_tutar=taban, carpanlar=carpanlar)
        ozet["havuz"] += 1
    if not (tamamla and gider_servisi.ambalajlar(s, sen.id)):
        gider_servisi.ambalaj_kaydet(s, sen.id, [(a.ad, a.hacim, a.uretim_adedi, a.katsayi) for a in h.ambalajlar], kullanici); ozet["ambalaj"] = len(h.ambalajlar)

    sayfalar = eo.urun_sayfalarini_listele(wb_v)
    ilk = next(a for a in sayfalar if "(2)" not in a)
    _, p, _ = eo.urun_oku(wb_f[ilk], wb_v[ilk], excel_malzemeleri)
    genel_parametreler = _parametre_sozlugu(p)
    ek = eo.ek_parametreleri_oku(wb_v[ilk])
    ozet["parametre"] = _parametreleri_yaz(s, sen.id, p, sz.baslangic, f"Excel {ilk} sayfası", ek, yalniz_eksik=tamamla)
    ozet["satis_notu"] = _satis_notunu_yaz(s, sen.id, ek, sz.baslangic, f"Excel {ilk} sayfası G{eo._etiket_satiri(wb_v[ilk], 'Süzme Miktar') + 1}")

    gorulen: set[str] = set()
    yeni_urunler: set[str] = set()   # bu içe aktarmada açılan/işlenen kodlar: aynı kodlu ikinci sayfa kart farkı sayılmaz
    for ad in sayfalar:
        if "(2)" in ad:
            ozet["atlanan"].append(ad); continue
        try:
            girdi, p_sayfa, _ = eo.urun_oku(wb_f[ad], wb_v[ad], excel_malzemeleri)
        except Exception as e:
            ozet["atlanan"].append(f"{ad}: {e}"); continue
        kod = girdi.kod
        if kod == "":
            kod = f"SAYFA-{ad}"
            ozet["uyarilar"].append(f"{ad}: ürün kodu yok, geçici kod {kod} verildi; ERP kodu atanmalı")
        elif kod in gorulen:
            ozet["uyarilar"].append(f"{ad}: ürün kodu {kod} daha önce yüklendi, yeni reçete versiyonu açıldı")
        yeni_kod_ilk_kez = kod not in gorulen
        gorulen.add(kod)
        if girdi.kod and yeni_kod_ilk_kez and s.scalar(select(m.Urun.id).where(m.Urun.kod == kod)) is None:
            gecici = s.scalar(select(m.Urun).where(m.Urun.kod == f"SAYFA-{ad}"))
            if gecici is not None:   # sayfaya ERP kodu girilmiş: yeni ürün açma, geçici kodlu ürünü yeniden adlandır
                hesap_servisi.urun_kod_degistir(s, gecici.kod, kod, kullanici)
                ozet["yeniden_adlandirilan"].append({"eski": f"SAYFA-{ad}", "yeni": kod})
        ub = girdi.uretim
        kart_yeni = {"ad": girdi.ad, "ambalaj_hacmi": ub.ambalaj_hacmi, "hat": ub.hat, "taze_tursu_sinifi": ub.taze_tursu_sinifi,
                     "suzme_kg": ub.suzme_kg, "pazar": ub.pazar}
        var = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        if var is None:
            u = hesap_servisi.urun_kaydet(s, kod, **kart_yeni, kullanici=kullanici)
            if kod.startswith("SAYFA-"):
                u.gecici_kod = True
        else:
            u = var
            fark = _fark_alanlari(var, kart_yeni) if kod not in yeni_urunler else []
            if fark:
                ozet["kart_farklari"].append({"tur": "urun", "kod": kod, "alanlar": fark})
            if kartlari_guncelle:
                u = hesap_servisi.urun_kaydet(s, kod, **kart_yeni, kullanici=kullanici)
        yeni_urunler.add(kod)
        if tamamla and recete_servisi.versiyonlar(s, u.id, sen.id):
            continue   # tamamla: senaryoda reçetesi olan ürüne dokunulmaz
        for anahtar, deger in _parametre_sozlugu(p_sayfa).items():   # sayfanın ilk sayfadan farklı parametreleri ürün kapsamlı yazılır
            if anahtar in genel_parametreler and genel_parametreler[anahtar] != deger:
                parametre_servisi.deger_ekle(s, sen.id, anahtar, deger, sz.baslangic, f"Excel {ad} sayfası farkı",
                                             kapsam_tipi="urun", kapsam_id=u.id, olusturan="import")
                ozet["urun_parametre_farklari"].append({"ad": ad, "anahtar": anahtar, "deger": str(deger)})
        if not (tamamla and s.scalar(select(m.UretimHedefi.id).where(m.UretimHedefi.urun_id == u.id, m.UretimHedefi.senaryo_id == sen.id)) is not None):
            hesap_servisi.uretim_hedefi_kaydet(s, u.id, sen.id, kullanici, vardiya_uretim_adedi=ub.vardiya_uretim_adedi, dolum_personel=ub.dolum_personel,
                                               etiketleme_adedi=ub.etiketleme_adedi, etiket_personel=ub.etiket_personel, mal_kabul_miktar_kg=ub.mal_kabul_miktar_kg,
                                               mal_kabul_fire=ub.mal_kabul_fire, pazarlama_yonetim_uygula=ub.pazarlama_yonetim_uygula,
                                               gider_elle=girdi.gider_elle)
        seviyeler = recete_seviyeleri_oku(wb_v[ad])
        if len(seviyeler) != len(girdi.recete):
            ozet["uyarilar"].append(f"{ad}: reçete seviye sayısı ({len(seviyeler)}) satır sayısıyla ({len(girdi.recete)}) eşleşmedi; seviye yazılmadı")
            seviyeler = [None] * len(girdi.recete)
        recete_servisi.yeni_versiyon(s, u.id, sen.id, [{"malzeme_kodu": r.malzeme_kodu, "ad": r.ad, "miktar": r.miktar, "birim": r.birim,
                                                        "fire_override": r.fire_orani, "dugum_tipi": r.dugum_tipi,
                                                        "brut_miktar_elle": r.brut_miktar_elle, "birim_fiyat_elle": r.birim_fiyat_elle, "seviye": sv,
                                                        "zs_elle": r.zs_elle, "para_birimi_elle": r.para_birimi_elle}
                                                       for r, sv in zip(girdi.recete, seviyeler)], "import", kullanici)
        ozet["urun"] += 1; ozet["recete"] += 1

    if eo.URETIM_ADETLERI_SAYFA in wb_v.sheetnames:   # eski/sade kitaplarda sayfa yoksa kapasite 0 kalır
        satirlar_k = eo.uretim_adetlerini_oku(wb_v)
        if tamamla:   # yalnız senaryoda kaydı olmayan kodlar eklenir
            var_kod = set(s.scalars(select(m.UretimKapasitesi.urun_kodu).where(m.UretimKapasitesi.senaryo_id == sen.id)))
            satirlar_k = [r for r in satirlar_k if r["urun_kodu"] not in var_kod]
        ozet["kapasite"], kap_uyari = kapasite_servisi.importla(s, sen.id, satirlar_k, kullanici)
        ozet["uyarilar"] += kap_uyari

    tohum.fire_varsayilanlarini_tohumla(s, sen.id, sz.baslangic)
    s.flush()
    return ozet


def _fiyat_satirlari(dosya_yolu: Path):
    wb = openpyxl.load_workbook(dosya_yolu, data_only=True, read_only=True)
    try:
        ws = wb.worksheets[0]
        for satir in ws.iter_rows(min_row=2, values_only=True):
            if satir and satir[0]:
                yield (str(satir[0]).strip(), satir[SUTUN_ILK_FIYAT] if len(satir) > SUTUN_ILK_FIYAT else None,
                       satir[SUTUN_REVIZE_FIYAT] if len(satir) > SUTUN_REVIZE_FIYAT else None)
    finally:
        wb.close()


def fiyat_listesi_onizle(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date | None = None) -> dict:
    """Mevcut fiyatlar `gecerlilik_basi` tarihindeki geçerli fiyatlardır (uygulama ile aynı karşılaştırma).
    F ilk bütçe, I revize: karşılaştırma geçerli olacak fiyatla (varsa I) yapılır; `revize` listesi bilgi amaçlıdır."""
    mevcut = fiyat_servisi.gecerli_fiyatlar(s, senaryo_id, gecerlilik_basi or date.today())
    out = {"yeni": [], "degisen": [], "ayni": 0, "hatali": [], "revize": [], "_yazilacak": {}}
    for kod, fiyat, revize_ham in _fiyat_satirlari(dosya_yolu):
        try:
            f = _ondalik(fiyat); r = _ondalik(revize_ham)
        except ValueError:
            out["hatali"].append(kod); continue
        if r is not None and r == f:
            r = None
        etkin = r if r is not None else f
        if etkin is None:
            continue
        if r is not None:
            out["revize"].append({"kod": kod, "ilk": str(f) if f is not None else None, "revize": str(r)})
        if kod not in mevcut:
            out["yeni"].append({"kod": kod, "yeni": str(etkin)})
        elif mevcut[kod].fiyat != etkin:
            out["degisen"].append({"kod": kod, "eski": str(mevcut[kod].fiyat), "yeni": str(etkin)})
            out["_yazilacak"][kod] = (f, r)
        else:
            out["ayni"] += 1
    return out


def fiyat_listesi_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, gecerlilik_basi: date, neden: str, kullanici: str = "sistem") -> dict:
    """Yalnız önizlemenin 'degisen' listesini (aynı tarih, aynı fonksiyon) yazar; revize varsa F + I iki kayıt. Kartı olmayan ('yeni') kodlar
    bu yoldan yazılmaz (kart açmak için Veri Aktar → Satın alma). Yazılan kodları döner."""
    on = fiyat_listesi_onizle(s, senaryo_id, dosya_yolu, gecerlilik_basi)
    kodlar = []
    for d in on["degisen"]:
        ilk, revize = on["_yazilacak"][d["kod"]]
        revize_ile_fiyat_ekle(s, senaryo_id, d["kod"], ilk, revize, gecerlilik_basi, neden, kullanici); kodlar.append(d["kod"])
    return {"yazilan": len(kodlar), "kodlar": kodlar}
