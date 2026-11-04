"""Fiyat Çalışma Excel'inden motor girdileri ve beklenen (altın) değerleri okur.
Ürün sayfalarında satır numaraları sabit değildir ('053' kaymış); konumlar D sütunundaki etiketlerle bulunur."""
import re
from decimal import Decimal
from pathlib import Path
import openpyxl
from .modeller import (GIDER_ELLE_ALANLARI, GIDER_KALEMLERI, AmbalajSinifi, GiderElle, GiderHavuzlari, Malzeme, Parametreler,
                       ReceteSatiri, UretimBilgisi, UrunGirdisi)
from .fire import brut_miktar
from .para import D, SIFIR

ELLE_ESIK = Decimal("1e-9")   # K/M elle ayrımı eşiği; TOLERANS (1e-6) çok gevşek: miktar x fiyat çarpımıyla tutar parite eşiğini aşar
URUN_SAYFA = re.compile(r"^\d{3}( \(2\))?$")


def excel_ac(yol: Path):
    return openpyxl.load_workbook(yol, data_only=False), openpyxl.load_workbook(yol, data_only=True)


def malzemeleri_oku(wb_deger) -> dict[str, Malzeme]:
    ws = wb_deger["S.ALMA BF"]
    out = {}
    for kod, ad, tip, birim, para, fiyat, zs, *_ in ws.iter_rows(min_row=2, values_only=True):
        if not kod:
            continue
        strip = lambda x: x.strip() if isinstance(x, str) else x
        out[str(kod).strip()] = Malzeme(kod=str(kod).strip(), ad=(ad or "").strip(), tip=strip(tip), birim=strip(birim),
                                        para_birimi=strip(para), fiyat=D(fiyat), zs=strip(zs))
    return out


def _paylar(ws, satirlar, ad_sutunu, pay_sutunu, baz_sutunu):
    return {str(ws[f"{ad_sutunu}{r}"].value).strip(): (D(ws[f"{pay_sutunu}{r}"].value), D(ws[f"{baz_sutunu}{r}"].value))
            for r in satirlar if ws[f"{ad_sutunu}{r}"].value}


# Gider Dağıtım sayfasında her havuzun "Gider Toplamı" hücresi (GiderHavuzlari alanı -> adres).
HAVUZ_TOPLAM_HUCRELERI = {
    "dolum_iscilik_toplam": "D4", "mal_kabul_iscilik_toplam": "A6", "etiket_iscilik_toplam": "D13", "endirekt_iscilik_toplam": "D18",
    "mal_kabul_gug_toplam": "A20", "diger_gug_toplam": "D27", "elektrik_toplam": "D38", "dogalgaz_toplam": "D49",
    "amortisman_toplam": "D60", "yonetim_toplam": "D64", "pazarlama_toplam": "D67",
}

_SAYI = r"\d+(?:\.\d+)?"
# =taban*ç1*ç2... ; taban tek sayı ya da parantezli toplam: =(10875000+3571433)*1.4*1.25
_TABAN_CARPAN = re.compile(rf"^=\+?(?P<taban>{_SAYI}|\(\+?{_SAYI}(?:\+{_SAYI})*\))(?P<carpanlar>(?:\*{_SAYI})+)$")


def taban_carpan_coz(formul) -> tuple[Decimal, tuple[Decimal, ...]] | None:
    """Gider toplamı formülünü taban ve çarpanlara ayırır: '=49024334.97*1.35*1.3' -> (49024334.97, (1.35, 1.3)).
    Parantezli taban toplanır ('=(a+b)*1.4' -> a+b). Kalıba uymayan (düz sayı, hücre başvurusu, çarpansız) -> None."""
    if not isinstance(formul, str):
        return None
    e = _TABAN_CARPAN.match(formul.replace(" ", ""))
    if e is None:
        return None
    taban = sum((Decimal(x) for x in re.findall(_SAYI, e.group("taban"))), Decimal(0))
    return taban, tuple(Decimal(x) for x in e.group("carpanlar").split("*")[1:])


def havuz_formulleri_oku(ws_formul) -> dict[str, tuple[Decimal, tuple[Decimal, ...]]]:
    """Gider Dağıtım (formül görünümü): taban × çarpan kalıbındaki toplam hücreleri, GiderHavuzlari alanına göre."""
    out = {}
    for alan, adres in HAVUZ_TOPLAM_HUCRELERI.items():
        coz = taban_carpan_coz(ws_formul[adres].value)
        if coz is not None:
            out[alan] = coz
    return out


def havuzlari_oku(wb_deger) -> GiderHavuzlari:
    ws = wb_deger["Gider Dağıtım"]
    v = lambda a: D(ws[a].value)
    t = {alan: v(adres) for alan, adres in HAVUZ_TOPLAM_HUCRELERI.items()}
    return GiderHavuzlari(
        **t,
        dolum_iscilik_saniye=v("F4"),
        mal_kabul_paylari=_paylar(ws, range(7, 10), "C", "G", "E"),
        etiket_iscilik_saniye=v("F13"),
        endirekt_saniye=v("F18"),
        mal_kabul_gug_paylari=_paylar(ws, range(21, 24), "C", "G", "E"),
        diger_gug_saniye=v("F27"),
        elektrik_hatlar=_paylar(ws, range(30, 38), "A", "G", "E"),
        dogalgaz_hatlar=_paylar(ws, range(41, 49), "A", "G", "E"),
        amortisman_hatlar=_paylar(ws, range(52, 60), "A", "G", "E"),
        ambalajlar=tuple(AmbalajSinifi(ad=str(ws[f"A{r}"].value), hacim=D(ws[f"B{r}"].value),
                                       uretim_adedi=D(ws[f"C{r}"].value), katsayi=D(ws[f"D{r}"].value))
                         for r in range(70, 92) if ws[f"A{r}"].value),
    )


def urun_sayfalarini_listele(wb) -> list[str]:
    return [ws.title for ws in wb.worksheets if URUN_SAYFA.match(ws.title)]


def _etiket_satiri(ws, etiket: str, tam: bool = False, sutun: str = "D") -> int:
    for r in range(1, ws.max_row + 1):
        val = ws[f"{sutun}{r}"].value
        if isinstance(val, str):
            s = val.strip()
            if (s == etiket) if tam else s.startswith(etiket):
                return r
    raise KeyError(f"etiket bulunamadı: {etiket!r}")


def _sabit_sifir(ws_formul, adres: str) -> bool:
    v = ws_formul[adres].value
    return v in (0, None) or (isinstance(v, (int, float)) and v == 0)


def formul_mu(deger) -> bool:
    return isinstance(deger, str) and deger.startswith("=")


def k_elle_mi(k_formul, satir: int) -> bool:
    """TANI amaçlı biçim kuralı (scripts/excel_elle_hucre_tara.py): K formül değil ya da =I{r}/(1-J{r}) kalıbında değil."""
    if not formul_mu(k_formul):
        return True
    return k_formul.replace(" ", "").replace("+", "") != f"=I{satir}/(1-J{satir})"


def m_elle_mi(m_formul) -> bool:
    """TANI amaçlı biçim kuralı: M hücresi fiyat listesi aramasi yerine elle yazilmis mi (formül değil)."""
    return not formul_mu(m_formul)


def k_sayisal_elle_mi(k, i, j) -> bool:
    """Okuyucunun kuralı: K değeri I/(1-J)'den (J boş = 0) en az ELLE_ESIK (1e-9) farklıysa elle. Geçersiz J (>= 1) elle sayılır."""
    k, i, j = D(k), D(i), D(j)
    if j < SIFIR or j >= 1:
        return True
    return abs(k - brut_miktar(i, j)) >= ELLE_ESIK


def m_sayisal_elle_mi(m, malzeme: Malzeme | None) -> bool:
    """M değeri fiyat listesi fiyatından en az ELLE_ESIK (1e-9) farklıysa elle (listede yok/0 ise yalnız M != 0 elle)."""
    liste = malzeme.fiyat if malzeme is not None else SIFIR
    return abs(D(m) - liste) >= ELLE_ESIK


def _m_elle(m_deger, m_formul, kod: str, malzemeler) -> bool:
    if malzemeler is None:                      # fiyat listesi verilmediyse biçime bak (geri uyumlu)
        return m_elle_mi(m_formul)
    return m_sayisal_elle_mi(m_deger, malzemeler.get(kod))


def zs_elle_oku(n_formul) -> str | None:
    """Reçete N hücresi (Z/S) formül yerine elle yazılmışsa o değer ('Z'/'S'); formülse ya da boşsa None."""
    if n_formul is None or formul_mu(n_formul):
        return None
    zs = str(n_formul).strip().upper()
    return zs if zs in ("Z", "S") else None


def para_birimi_elle_oku(o_formul) -> str | None:
    """Reçete O hücresi (para birimi) formül yerine elle yazılmışsa o değer; formülse ya da boşsa None."""
    if o_formul is None or formul_mu(o_formul) or not str(o_formul).strip():
        return None
    return str(o_formul).strip().upper()


# Gider satırında formül yerine yazılmış sabit Excel'in normal düzeni olan hücreler (elle sayılmaz):
# I104 mal kabul miktarı üretim bilgisi olarak zaten okunur; K118/K119 her sayfada sabit 1; P118/P119 = 0
# pazarlama_yonetim_uygula anahtarıyla taşınır.
_GIDER_ELLE_DISI = {("mal_kabul_iscilik", "miktar"), ("pazarlama", "brut_miktar"), ("yonetim", "brut_miktar"),
                    ("pazarlama", "tutar"), ("yonetim", "tutar")}


def gider_elle_oku(ws_f, ws_v) -> dict[str, GiderElle]:
    """Gider satırlarında (104-113, 118-119) formül yerine sabit yazılmış I/K/M/P hücreleri: kalem -> GiderElle."""
    out = {}
    for kalem, etiket in GIDER_KALEMLERI.items():
        r = _etiket_satiri(ws_v, etiket)
        degerler = {}
        for alan, sutun in GIDER_ELLE_ALANLARI.items():
            h = ws_f[f"{sutun}{r}"].value
            if (kalem, alan) in _GIDER_ELLE_DISI or h is None or formul_mu(h):
                continue
            degerler[alan] = D(h)
        if degerler:
            out[kalem] = GiderElle(**degerler)
    return out


def urun_oku(ws_f, ws_v, malzemeler: dict[str, Malzeme] | None = None) -> tuple[UrunGirdisi, Parametreler, dict[str, Decimal | None]]:
    E = lambda r: _etiket_satiri(ws_v, r)
    Et = lambda r: _etiket_satiri(ws_v, r, tam=True)
    val = lambda a: ws_v[a].value
    d = lambda a: D(val(a))

    r100 = E("HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    urun_kodu = str(val("D6")).strip() if val("D6") not in (None, "") else ""
    recete = tuple(
        ReceteSatiri(malzeme_kodu=str(val(f"D{r}")).strip(), ad=str(val(f"E{r}") or "").strip(),
                     miktar=d(f"I{r}"), fire_orani=d(f"J{r}"), birim=val(f"L{r}"),
                     dugum_tipi="ara_mamul" if urun_kodu and str(val(f"D{r}")).strip() == urun_kodu else "yaprak",
                     brut_miktar_elle=d(f"K{r}") if k_sayisal_elle_mi(val(f"K{r}"), val(f"I{r}"), val(f"J{r}")) else None,
                     birim_fiyat_elle=d(f"M{r}") if _m_elle(val(f"M{r}"), ws_f[f"M{r}"].value, str(val(f"D{r}")).strip(), malzemeler) else None,
                     zs_elle=zs_elle_oku(ws_f[f"N{r}"].value), para_birimi_elle=para_birimi_elle_oku(ws_f[f"O{r}"].value))
        for r in range(6, r100) if val(f"D{r}")
    )
    r103, r104, r105, r106 = E("DİREKT İŞÇİLİK GİDERLERİ"), E("Mal Kabul ve Fermantasyon Giderleri"), \
        E("Dolum Doğrudan İşçilik Giderleri"), E("Etiketleme İşçilik Giderleri")
    r107 = E("GENEL ÜRETİM GİDERLERİ")
    r108 = E("Endirekt İşçilik Giderleri"); r109 = E("Mal Kabul ve Fermantasyon Genel Üretim Giderleri")
    r110, r111, r112, r113 = E("Elektrik Giderleri"), E("Doğalgaz Giderleri"), E("Amortisman Giderleri"), E("Diğer Genel Üretim Giderleri")
    r114, r116 = Et("GİDER TOPLAMI"), E("TOPLAM BİRİM MALİYET")
    r118, r119 = E("PAZARLAMA SATIŞ GİDERLERİ"), E("GENEL YÖNETİM GİDERLERİ")
    r120, r122 = E("DİĞER GİDERLER TOPLAMI"), E("DİĞER GİDERLER GİYDİRİLMİŞ BİRİM MALİYET")
    r124, r130 = E("FİNANSMAN GİDERLERİ"), E("FİNANSMAN GİDERİ DAHİL EDİLMİŞ MALİYET")
    r136, r138, r140, r141, r143 = E("Süzme Miktar"), E("Vardiya Üretim Adedi"), E("Dolum İşçilik Pers"), E("Etiketleme Adedi"), E("Etiket İşçilik Pers")
    r144, r145, r146, r147 = Et("Üretim"), E("Taze / Turşu"), Et("Ambalaj"), Et("Ürün Adı")
    r148, r150 = Et("Enflasyon"), E("Döviz Kurları")

    faiz, stok = {}, {}
    for i in range(5):                                   # TL, USD, EUR, GBP, ZAR
        pb = val(f"I{r124 + i}")
        if pb:
            faiz[str(pb)] = d(f"J{r124 + i}"); stok[str(pb)] = d(f"K{r124 + i}")
    kurlar = {str(val(f"E{r150 + i}")): d(f"F{r150 + i}") for i in range(6) if val(f"E{r150 + i}")}  # USD, EUR, GBP, CHF, RUB, ZAR

    p = Parametreler(enflasyon=d(f"F{r148}"), kurlar=kurlar, faiz_oranlari=faiz, stok_sureleri_ay=stok,
                     satis_kar_orani=Decimal("0.2"),
                     teklif_kar_oranlari=(d(f"L{r145}"), d(f"L{r146}"), d(f"L{r147}")), vardiya_saati=Decimal("7.5"))
    uretim = UretimBilgisi(
        pazar=str(val("P2") or "Yurtiçi"), vardiya_uretim_adedi=d(f"E{r138}"), dolum_personel=d(f"E{r140}"),
        etiketleme_adedi=d(f"E{r141}"), etiket_personel=d(f"E{r143}"), hat=str(val(f"E{r144}") or ""),
        taze_tursu_sinifi=str(val(f"E{r145}") or ""), ambalaj_hacmi=d(f"E{r146}"), suzme_kg=d(f"E{r136}"),
        mal_kabul_miktar_kg=d(f"I{r104}"), mal_kabul_fire=d(f"J{r104}"),
        pazarlama_yonetim_uygula=not (_sabit_sifir(ws_f, f"P{r118}") and _sabit_sifir(ws_f, f"P{r119}")),
    )
    girdi = UrunGirdisi(kod=urun_kodu, ad=str(val("E6") or "").strip(), recete=recete, uretim=uretim,
                        gider_elle=gider_elle_oku(ws_f, ws_v))

    bek = {}
    for ad, r in [("P100", r100), ("P103", r103), ("P104", r104), ("P105", r105), ("P106", r106), ("P107", r107),
                  ("P108", r108), ("P109", r109), ("P110", r110), ("P111", r111), ("P112", r112), ("P113", r113),
                  ("P114", r114), ("P116", r116), ("P118", r118), ("P119", r119), ("P120", r120), ("P122", r122),
                  ("P124", r124), ("P125", r124 + 1), ("P130", r130), ("P131", r130 + 1), ("P132", r130 + 2), ("P133", r130 + 3),
                  ("P137", r136 + 1), ("P138", r136 + 2), ("P143", r143), ("P145", r145), ("P146", r146), ("P147", r147)]:
        bek[ad] = D(val(f"P{r}"))
    for ad, r in [("100", r100), ("103", r103), ("107", r107), ("118", r118), ("119", r119), ("124", r124)]:
        bek["R" + ad], bek["S" + ad] = D(val(f"R{r}")), D(val(f"S{r}"))
    return girdi, p, bek


def ek_parametreleri_oku(ws_v) -> dict:
    """Salt okuma: maliyet sapma oranı (F, 'Maliyet Sapma' satırı; yalnız gösterim) ve satış fiyatı notu (G, 'Süzme Miktar'tan sonraki satır).
    Dönüş: {'maliyet_sapma': Decimal, 'satis_fiyati_notu': str | None}."""
    r_sapma = _etiket_satiri(ws_v, "Maliyet Sapma", tam=True)
    r_not = _etiket_satiri(ws_v, "Süzme Miktar") + 1
    n = ws_v[f"G{r_not}"].value
    n = str(n).strip() if n not in (None, "") else None
    return {"maliyet_sapma": D(ws_v[f"F{r_sapma}"].value), "satis_fiyati_notu": n or None}


def urun_oku_excel_hucreleri(ws_f, ws_v) -> tuple[UrunGirdisi, dict[str, Malzeme], Parametreler, dict[str, Decimal]]:
    """TEST ORAKELI okuyucusu, uretim yolu degildir. Recete satirlarini Excel'in kendi hucre degerleriyle kurar:
    miktar = K (brut miktar, fire_orani = 0); M/N/O elle yazilmissa o satir icin satira ozel Malzeme uretilir
    (kod '<kod>#<satir>'). Donus: (girdi, satira ozel malzemeler, parametreler, beklenen degerler)."""
    girdi, p, bek = urun_oku(ws_f, ws_v)
    r100 = _etiket_satiri(ws_v, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    satirlar, ozel = [], {}
    sabit = lambda a: not (isinstance(ws_f[a].value, str) and ws_f[a].value.startswith("="))
    for r in range(6, r100):
        if not ws_v[f"D{r}"].value:
            continue
        kod = str(ws_v[f"D{r}"].value).strip()
        ara_mamul = "ara_mamul" if girdi.kod and kod == girdi.kod else "yaprak"
        if sabit(f"M{r}") or sabit(f"N{r}") or sabit(f"O{r}"):
            kod = f"{kod}#{r}"
            ozel[kod] = Malzeme(kod=kod, ad="", tip=None, birim=ws_v[f"L{r}"].value,
                                para_birimi=ws_v[f"O{r}"].value, fiyat=D(ws_v[f"M{r}"].value),
                                zs=str(ws_v[f"N{r}"].value).upper())
        satirlar.append(ReceteSatiri(malzeme_kodu=kod, ad=str(ws_v[f"E{r}"].value or "").strip(),
                                     miktar=D(ws_v[f"K{r}"].value), fire_orani=SIFIR, birim=ws_v[f"L{r}"].value,
                                     dugum_tipi=ara_mamul))
    from dataclasses import replace
    return replace(girdi, recete=tuple(satirlar)), ozel, p, bek


URETIM_ADETLERI_SAYFA = "Üretim Adetleri"


def uretim_adetlerini_oku(wb_deger) -> list[dict]:
    """`Üretim Adetleri` sayfası: başlık satır 2, veri satır 4'ten (satır 3 alt başlık). Sütunlar A-H sırasıyla ürün kodu, ürün adı,
    net süredeki vardiyalık kapasite, net süre, toplam süredeki kapasite, toplam süre, hedef vardiyalık üretim, ortalama işçi sayısı.
    Tekrarlayan kodlar da döner (ayıklama çağıranın işi); boş kodlu satırlar atlanır; sayı olmayan hücreler ('-', '#DIV/0!') 0 okunur."""
    ws = wb_deger[URETIM_ADETLERI_SAYFA]
    baslik = next(ws.iter_rows(min_row=2, max_row=2, max_col=8, values_only=True), ())
    norm = lambda x: str(x).strip().upper() if x else ""
    if len(baslik) < 7 or (norm(baslik[0]), norm(baslik[1]), norm(baslik[6])) != ("ÜRÜN KODU", "ÜRÜN ADI", "HEDEF VARDİYALIK ÜRETİM"):
        raise ValueError("Üretim Adetleri sayfası beklenen başlıklarda değil")
    sayi = lambda x: D(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else SIFIR   # '-' ve '#DIV/0!' gibi sayı olmayan hücreler 0
    out = []
    for kod, ad, nk, ns, tk, ts, hedef, isci, *_ in ws.iter_rows(min_row=4, max_col=9, values_only=True):
        if not kod or not str(kod).strip():
            continue
        out.append({"urun_kodu": str(kod).strip(), "urun_ad": str(ad).strip() if ad else "", "net_kapasite": sayi(nk), "net_sure": sayi(ns),
                    "toplam_kapasite": sayi(tk), "toplam_sure": sayi(ts), "hedef_uretim": sayi(hedef), "ortalama_isci": sayi(isci)})
    return out
