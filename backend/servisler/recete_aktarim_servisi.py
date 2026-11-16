"""Dosyadan reçete aktarımı (Veri Aktar → Ürün reçetesi): Excel'in kendi ürün sayfası düzeninde bir ya da birkaç sayfa
(tam fiyat çalışması kitabı ya da tek sayfanın kopyası) okunur, seçili çalışmanın aktif reçetesiyle karşılaştırılır (önizle) ve
kullanıcının seçtiği sayfalar için yeni reçete versiyonu açılır (uygula). Eski versiyon geçmişte kalır.

Kurallar:
- Okuma tam kitap aktarımıyla aynıdır (excel_okuyucu.urun_oku + seviye): elle brüt/elle fiyat ayrımı dosyada S.ALMA BF varsa ona
  göre, yoksa hücrenin formül/sayı olmasına göre yapılır.
- Var olan ürün kartına ve üretim bilgilerine dokunulmaz; yalnız reçete yazılır. Sistemde olmayan ürün için kart ve (ilk kez) üretim
  bilgileri sayfadan açılır, yoksa hesap 'üretim hedefi yok' derdi.
- '(2)' ekli sayfalar (alternatif hesap varyantları) okunur ama varsayılan seçili gelmez.
"""
from pathlib import Path
import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru import excel_okuyucu as eo
from ..depo import modeller as m
from . import hesap_servisi, recete_servisi
from .hatalar import DogrulamaHatasi
from .import_servisi import recete_seviyeleri_oku

OKUMA_HATALARI = (KeyError, ValueError, TypeError, ArithmeticError, StopIteration, IndexError, AttributeError)
SATIN_ALMA = "S.ALMA BF"
KARSILASTIRILAN = ("miktar", "fire_override", "brut_miktar_elle", "birim_fiyat_elle", "zs_elle", "para_birimi_elle")
ALAN_ADI = {"miktar": "miktar", "fire_override": "fire", "brut_miktar_elle": "elle brüt", "birim_fiyat_elle": "elle fiyat",
            "zs_elle": "elle Z/S", "para_birimi_elle": "elle para birimi"}


def _kitaplar(dosya_yolu: Path):
    from .excel_ortak import sablon_denetle
    from .import_servisi import DESTEKLENMEYEN_DOSYA
    try:
        wb_f, wb_v = openpyxl.load_workbook(dosya_yolu, data_only=False), openpyxl.load_workbook(dosya_yolu, data_only=True)
    except Exception as e:   # bozuk/xlsx olmayan dosya: 422
        raise DogrulamaHatasi(DESTEKLENMEYEN_DOSYA, kod="desteklenmeyen_dosya") from e
    sablon_denetle(wb_v, "urun_recetesi")
    return wb_f, wb_v


def _recete_satir_numaralari(ws_v) -> list[int]:
    """urun_oku ile aynı satırlar: 6. satırdan toplam etiketine kadar, D'si dolu olanlar."""
    r100 = eo._etiket_satiri(ws_v, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    return [r for r in range(6, r100) if ws_v[f"D{r}"].value]


def _recete_sayilarini_cevir(ws_f, ws_v, ad: str) -> list[dict]:
    """I, J, K, M hücrelerindeki metin sayıları bellekte sayıya çevirir (iki kitapta da); çevrilemeyenler sorunlu."""
    from .excel_ortak import sayi_cevir
    from .yukleme_guvenligi import sorunlu as sorunlu_satir
    sorunlu = []
    for r in _recete_satir_numaralari(ws_v):
        for sutun, alan in (("I", "miktar"), ("J", "fire"), ("K", "brüt miktar"), ("M", "birim fiyat")):
            v = ws_v[f"{sutun}{r}"].value
            if not isinstance(v, str) or (isinstance(ws_f[f"{sutun}{r}"].value, str) and ws_f[f"{sutun}{r}"].value.startswith("=")):
                continue
            if not v.strip():
                ws_v[f"{sutun}{r}"].value = ws_f[f"{sutun}{r}"].value = None
                continue
            d, hata = sayi_cevir(v, alan)
            if hata:
                sorunlu.append(sorunlu_satir(r, str(ws_v[f"D{r}"].value).strip(), f"{ad}!{sutun}{r} ({alan})", v, hata))
            else:
                ws_v[f"{sutun}{r}"].value = ws_f[f"{sutun}{r}"].value = d
    return sorunlu


def _bos_hucre_elle_sayilmasin(ws_f, ws_v, satirlar: list[dict]) -> None:
    """Bilinen hata düzeltmesi: boş M (birim fiyat) 'elle fiyat 0', boş K (brüt) 'elle brüt 0' sayılmasın. Boş = değer yok:
    fiyat malzeme fiyatlarından, brüt miktar fire kuralından gelir."""
    for r, x in zip(_recete_satir_numaralari(ws_v), satirlar):
        if ws_f[f"M{r}"].value in (None, "") and ws_v[f"M{r}"].value in (None, ""):
            x["birim_fiyat_elle"] = None
        if ws_f[f"K{r}"].value in (None, "") and ws_v[f"K{r}"].value in (None, ""):
            x["brut_miktar_elle"] = None


def _urun_sayfalari(wb_v) -> list[str]:
    """Ürün sayfaları: '001', '015 (2)' adlı sayfalar; hiçbiri yoksa ve dosya tek sayfalıysa o sayfa (kopyalanmış tek ürün sayfası)."""
    sayfalar = eo.urun_sayfalarini_listele(wb_v)
    if sayfalar:
        return sayfalar
    if len(wb_v.sheetnames) == 1:
        return wb_v.sheetnames
    return []


def _satir_sozlukleri(girdi, seviyeler) -> list[dict]:
    return [{"malzeme_kodu": r.malzeme_kodu, "ad": r.ad, "miktar": r.miktar, "birim": r.birim, "fire_override": r.fire_orani,
             "dugum_tipi": r.dugum_tipi, "brut_miktar_elle": r.brut_miktar_elle, "birim_fiyat_elle": r.birim_fiyat_elle, "seviye": sv,
             "zs_elle": r.zs_elle, "para_birimi_elle": r.para_birimi_elle}
            for r, sv in zip(girdi.recete, seviyeler)]


def _fark(mevcut: list[dict], yeni: list[dict]) -> dict:
    """Malzeme koduna göre (aynı kod birden çok kez geçebilir: sırayla eşlenir) eklenen, çıkan ve değişen satırlar."""
    kalan: dict[str, list[dict]] = {}
    for x in mevcut:
        kalan.setdefault(x["malzeme_kodu"], []).append(x)
    eklenen, degisen = [], []
    for y in yeni:
        aday = kalan.get(y["malzeme_kodu"])
        if not aday:
            eklenen.append({"kod": y["malzeme_kodu"], "ad": y["ad"]})
            continue
        x = aday.pop(0)
        alanlar = [ALAN_ADI[a] for a in KARSILASTIRILAN if x.get(a) != y.get(a)]
        if alanlar:
            degisen.append({"kod": y["malzeme_kodu"], "ad": y["ad"], "alanlar": alanlar})
    cikan = [{"kod": x["malzeme_kodu"], "ad": x["ad"]} for liste in kalan.values() for x in liste]
    return {"eklenen": eklenen, "cikan": cikan, "degisen": degisen}


def _mevcut_satirlar(r: m.Recete | None) -> list[dict] | None:
    if r is None:
        return None
    return [{"malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": x.miktar, "fire_override": x.fire_override,
             "brut_miktar_elle": x.brut_miktar_elle, "birim_fiyat_elle": x.birim_fiyat_elle, "zs_elle": x.zs_elle,
             "para_birimi_elle": x.para_birimi_elle} for x in r.satirlar]


def recete_onizle(s: Session, senaryo_id: int, dosya_yolu: Path) -> dict:
    """Hiçbir şey yazmaz. Dönüş: {"sayfalar": [...], "hatali": [...], "_okunan": {sayfa: (girdi, satır sözlükleri, ürün kodu)}}."""
    hesap_servisi.senaryo_getir(s, senaryo_id)
    wb_f, wb_v = _kitaplar(dosya_yolu)
    sayfalar = _urun_sayfalari(wb_v)
    if not sayfalar:
        raise DogrulamaHatasi("dosyada ürün sayfası bulunamadı ('001' gibi adlı sayfa ya da tek sayfalık ürün sayfası olmalı)")
    malzemeler = eo.malzemeleri_oku(wb_v) if SATIN_ALMA in wb_v.sheetnames else None
    sonuc, hatali, okunan, sorunlu = [], [], {}, []
    for ad in sayfalar:
        try:
            sayfa_sorunlu = _recete_sayilarini_cevir(wb_f[ad], wb_v[ad], ad)
            if sayfa_sorunlu:
                sorunlu += sayfa_sorunlu
                hatali.append({"sayfa": ad, "mesaj": f"{len(sayfa_sorunlu)} hücre sayıya çevrilemedi (sorunlu satırlara bakın)"})
                continue
            girdi, _, _ = eo.urun_oku(wb_f[ad], wb_v[ad], malzemeler)
            seviyeler = recete_seviyeleri_oku(wb_v[ad])
        except OKUMA_HATALARI as e:
            hatali.append({"sayfa": ad, "mesaj": f"ürün sayfası düzeninde değil ({type(e).__name__}: {e})"})
            continue
        uyarilar = []
        kod = girdi.kod
        if not kod:
            if not eo.URUN_SAYFA.match(ad):
                hatali.append({"sayfa": ad, "mesaj": "ürün kodu yok (D6 hücresi boş)"})
                continue
            # Tam kitap aktarımıyla aynı kural: kodsuz ürün sayfası geçici 'SAYFA-<sayfa>' koduyla eşlenir (056-067 gibi).
            kod = f"SAYFA-{ad}"
            uyarilar.append(f"ürün kodu yok (D6 boş): geçici kod {kod} kullanıldı; ERP kodu atanmalı")
        if not girdi.recete:
            hatali.append({"sayfa": ad, "mesaj": "reçete satırı yok"})
            continue
        if len(seviyeler) != len(girdi.recete):
            uyarilar.append("seviye sütunu satırlarla eşleşmedi; seviye yazılmayacak")
            seviyeler = [None] * len(girdi.recete)
        satirlar = _satir_sozlukleri(girdi, seviyeler)
        _bos_hucre_elle_sayilmasin(wb_f[ad], wb_v[ad], satirlar)
        urun =s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        mevcut = _mevcut_satirlar(recete_servisi.aktif_recete_veya_none(s, urun.id, senaryo_id)) if urun else None
        fark = _fark(mevcut, satirlar) if mevcut is not None else {"eklenen": [], "cikan": [], "degisen": []}
        if urun is None:
            durum = "yeni_urun"
        elif mevcut is None:
            durum = "yeni_recete"
        elif any(fark.values()):
            durum = "degisti"
        else:
            durum = "ayni"
        varyant = "(2)" in ad
        if varyant:
            uyarilar.append("'(2)' ekli sayfa: aynı ürünün alternatif hesabı olabilir; uygulanırsa aktif reçetenin yerine geçer")
        elle_fiyat = sum(1 for x in satirlar if x["birim_fiyat_elle"] is not None)
        if malzemeler is None and elle_fiyat:
            uyarilar.append("dosyada S.ALMA BF yok: formül yerine sayı yazılmış fiyat hücreleri elle fiyat sayıldı")
        sonuc.append({"sayfa": ad, "kod": kod, "ad": girdi.ad, "durum": durum, "satir_sayisi": len(satirlar),
                      "elle_fiyat": elle_fiyat, "elle_brut": sum(1 for x in satirlar if x["brut_miktar_elle"] is not None),
                      **fark, "uyarilar": uyarilar, "secili": durum != "ayni" and not varyant})
        okunan[ad] = (girdi, satirlar, kod)
    from .yukleme_guvenligi import ozet
    sayac = lambda *d: sum(1 for x in sonuc if x["durum"] in d)
    oz = ozet(okunan=len(sayfalar), yeni=sayac("yeni_urun", "yeni_recete"), degisen=sayac("degisti"), ayni=sayac("ayni"),
              atlanan=len(hatali), sorunlu_satirlar=sorunlu + [{"satir": None, "kod": None, "alan": f"sayfa {h['sayfa']}", "deger": None,
                                                                  "neden": h["mesaj"]} for h in hatali if not h["mesaj"].endswith("(sorunlu satırlara bakın)")],
              uyarilar=[f"{x['sayfa']}: {u}" for x in sonuc for u in x["uyarilar"]])
    return {"sayfalar": sonuc, "hatali": hatali, "_okunan": okunan, "ozet": oz}


def recete_uygula(s: Session, senaryo_id: int, dosya_yolu: Path, sayfalar: list[str], neden: str, kullanici: str = "sistem",
                  onay: bool = False, kaynak_dosya: str | None = None) -> dict:
    """Seçilen sayfalar için yeni reçete versiyonu açar (tek işlem; biri hatalıysa hiçbiri yazılmaz). Neden değişiklik günlüğüne düşer."""
    neden = (neden or "").strip()
    if not neden:
        raise DogrulamaHatasi("neden zorunlu")
    secilen = list(dict.fromkeys(x for x in sayfalar if x))
    if not secilen:
        raise DogrulamaHatasi("en az bir sayfa seçin")
    on = recete_onizle(s, senaryo_id, dosya_yolu)
    okunan = on["_okunan"]
    olmayan = [x for x in secilen if x not in okunan]
    if olmayan:
        raise DogrulamaHatasi("dosyada okunabilen ürün sayfası değil", {"sayfalar": olmayan})
    kodlar = [okunan[x][2] for x in secilen]
    tekrar = sorted({k for k in kodlar if kodlar.count(k) > 1})
    if tekrar:
        raise DogrulamaHatasi("aynı ürün için birden çok sayfa seçildi; birini seçin", {"kodlar": tekrar})
    from .yukleme_guvenligi import yedek_guncelle, yedekle
    y = yedekle(s, "recete", senaryo_id, {"senaryo_id": senaryo_id, "urunler": []}, f"{len(secilen)} ürün reçetesi", kaynak_dosya, kullanici)
    yedek_urunler = []
    uygulanan, yeni_urun = [], 0
    for ad in secilen:
        girdi, satirlar, kod = okunan[ad]
        u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        urun_yeni = u is None
        onceki = recete_servisi.aktif_recete_veya_none(s, u.id, senaryo_id) if u is not None else None
        if u is None:
            ub = girdi.uretim
            u = hesap_servisi.urun_kaydet(s, kod, girdi.ad, ub.ambalaj_hacmi, ub.hat, ub.taze_tursu_sinifi, ub.suzme_kg, ub.pazar,
                                          kullanici=kullanici, neden=neden)
            hesap_servisi.uretim_hedefi_kaydet(s, u.id, senaryo_id, kullanici, neden=neden, vardiya_uretim_adedi=ub.vardiya_uretim_adedi,
                                               dolum_personel=ub.dolum_personel, etiketleme_adedi=ub.etiketleme_adedi,
                                               etiket_personel=ub.etiket_personel, mal_kabul_miktar_kg=ub.mal_kabul_miktar_kg,
                                               mal_kabul_fire=ub.mal_kabul_fire, pazarlama_yonetim_uygula=ub.pazarlama_yonetim_uygula,
                                               gider_elle=girdi.gider_elle)
            if kod.startswith("SAYFA-"):
                u.gecici_kod = True
            yeni_urun += 1
        r = recete_servisi.yeni_versiyon(s, u.id, senaryo_id, satirlar, "dosya", kullanici)
        s.add(m.DegisiklikKaydi(tablo="recete", kayit_id=r.id, islem="dosyadan_aktar", eski=None,
                                yeni={"_neden": neden, "sayfa": ad, "versiyon": r.versiyon, "satir": len(satirlar)}, kullanici=kullanici))
        uygulanan.append({"sayfa": ad, "kod": kod, "versiyon": r.versiyon})
        yedek_urunler.append({"urun_id": u.id, "yeni_recete_id": r.id, "onceki_aktif_id": onceki.id if onceki is not None else None,
                              "yeni_urun": urun_yeni})
    yedek_guncelle(y, urunler=yedek_urunler)
    s.flush()
    return {"uygulanan": uygulanan, "yeni_urun": yeni_urun}
