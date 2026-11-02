"""Gider havuzları ve dağıtım anahtarları -> motorun GiderHavuzlari/GiderOranlari."""
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from fiyat_motoru.gider_dagitim import oranlari_hesapla
from fiyat_motoru.modeller import AmbalajSinifi, GiderHavuzlari, GiderOranlari
from ..depo import modeller as m
from .hatalar import DogrulamaHatasi

HAVUZ_KODLARI = ("dolum_iscilik", "mal_kabul_iscilik", "etiket_iscilik", "endirekt_iscilik", "mal_kabul_gug", "diger_gug",
                 "elektrik", "dogalgaz", "amortisman", "yonetim", "pazarlama")
PAYLI = ("mal_kabul_iscilik", "mal_kabul_gug", "elektrik", "dogalgaz", "amortisman")
AMBALAJ_BAZLI = ("yonetim", "pazarlama")   # baz miktarı ambalaj sınıflarından gelir; baz_miktar girilmez
BAZ_TIPLERI = ("saniye", "kg", "adet")


def toplam_hesapla(taban_tutar: Decimal, carpanlar: list[tuple[str, Decimal]] | None) -> Decimal:
    """Gider toplamı = taban × Π çarpan (Excel'deki "taban × 1,35 × 1,30" düzeni). Çarpan > 0 olmalı."""
    if taban_tutar < 0:
        raise DogrulamaHatasi("taban_tutar negatif olamaz", {"taban_tutar": str(taban_tutar)})
    toplam = taban_tutar
    for ad, deger in carpanlar or []:
        if deger <= 0:
            raise DogrulamaHatasi(f"çarpan 0'dan büyük olmalı: {ad or '(adsız)'}", {"carpan": ad, "deger": str(deger)})
        toplam = toplam * deger
    return toplam


EXCEL_ESLESME_TOLERANSI = Decimal("0.01")   # taban × çarpan, Excel'in hesapladığı toplamı kuruşta tutmalı


def excel_taban_carpan(toplam_excel: Decimal, formul: tuple[Decimal, tuple[Decimal, ...]] | None
                       ) -> tuple[Decimal, Decimal | None, list[tuple[str, Decimal]] | None]:
    """Excel toplam hücresinin formülü taban × çarpan kalıbındaysa (excel_okuyucu.taban_carpan_coz) ve sonuç Excel değerini kuruşta
    tutuyorsa (toplam, taban, çarpanlar) döner; toplam taban × Π çarpan'dır (havuz_kaydet'in hesabıyla aynı). Aksi halde (toplam_excel, None, None)."""
    if formul is None:
        return toplam_excel, None, None
    taban, degerler = formul
    carpanlar = [(f"Excel çarpanı {i}", d) for i, d in enumerate(degerler, 1)]
    try:
        toplam = toplam_hesapla(taban, carpanlar)
    except DogrulamaHatasi:   # 0 çarpan vb.: Excel değeri doğrudan toplam
        return toplam_excel, None, None
    if abs(toplam - toplam_excel) > EXCEL_ESLESME_TOLERANSI:
        return toplam_excel, None, None
    return toplam, taban, carpanlar


def carpan_degerleri(h: m.GiderHavuzu | None) -> tuple[Decimal | None, tuple[Decimal, ...]]:
    """Kayıtlı havuzun (taban, çarpan değerleri); karşılaştırma için (adlar hariç)."""
    if h is None:
        return None, ()
    return h.taban_tutar, tuple(Decimal(str(c["deger"])) for c in (h.carpanlar or []))


def _carpan_json(carpanlar: list[tuple[str, Decimal]] | None) -> list[dict] | None:
    return None if not carpanlar else [{"ad": ad, "deger": str(deger)} for ad, deger in carpanlar]


def _pay_cozumle(anahtarlar: list[tuple], toplam: Decimal) -> list[tuple[str, Decimal, Decimal]]:
    """(alt_kalem, pay, baz[, tutar]) -> (alt_kalem, pay, baz). pay None ise pay = tutar / toplam (ham bölüm, yuvarlama yok)."""
    out = []
    for a in anahtarlar:
        alt_kalem, pay, baz = a[0], a[1], a[2]
        tutar = a[3] if len(a) > 3 else None
        if pay is None:
            if tutar is None:
                raise DogrulamaHatasi(f"anahtar için pay_orani ya da tutar verilmeli: {alt_kalem}", {"alt_kalem": alt_kalem})
            if tutar < 0:
                raise DogrulamaHatasi(f"tutar negatif olamaz: {alt_kalem}", {"alt_kalem": alt_kalem})
            if toplam <= 0:
                raise DogrulamaHatasi("tutarla pay hesaplamak için havuz toplamı 0'dan büyük olmalı", {"alt_kalem": alt_kalem})
            pay = tutar / toplam
        out.append((alt_kalem, pay, baz))
    return out


def havuz_kaydet(s: Session, senaryo_id: int, kod: str, ad: str, toplam_tutar: Decimal | None, baz_tipi: str, baz_miktar: Decimal | None,
                 anahtarlar: list[tuple], kullanici: str = "sistem", neden: str | None = None, *,
                 taban_tutar: Decimal | None = None, carpanlar: list[tuple[str, Decimal]] | None = None) -> m.GiderHavuzu:
    """Havuzu yazar. `taban_tutar` verilmişse toplam = taban × Π çarpan (toplam_tutar yok sayılır); verilmemişse toplam doğrudan girilir
    ve eski taban/çarpanlar temizlenir (artık toplamı açıklamazlar). Anahtar: (alt_kalem, pay_orani | None, baz_miktar[, tutar])."""
    if kod not in HAVUZ_KODLARI:
        raise DogrulamaHatasi(f"bilinmeyen havuz: {kod}", {"kod": kod})
    if baz_tipi not in BAZ_TIPLERI:
        raise DogrulamaHatasi("baz_tipi saniye|kg|adet olmalı", {"baz_tipi": baz_tipi})
    if baz_tipi in ("saniye", "adet") and not anahtarlar and kod not in AMBALAJ_BAZLI and (baz_miktar is None or baz_miktar <= 0):
        raise DogrulamaHatasi("anahtarsız saniye/adet havuzunda baz_miktar > 0 olmalı", {"kod": kod})
    if taban_tutar is not None:
        toplam_tutar = toplam_hesapla(taban_tutar, carpanlar)
    elif toplam_tutar is None:
        raise DogrulamaHatasi("toplam_tutar ya da taban_tutar verilmeli", {"kod": kod})
    else:
        carpanlar = None
    if toplam_tutar < 0:
        raise DogrulamaHatasi("toplam_tutar negatif olamaz", {"kod": kod})
    anahtarlar = _pay_cozumle(anahtarlar, toplam_tutar)
    carpan_json = _carpan_json(carpanlar)
    h = s.scalar(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == senaryo_id, m.GiderHavuzu.kod == kod))
    yeni = {"ad": ad, "toplam_tutar": str(toplam_tutar), "baz_tipi": baz_tipi, "baz_miktar": None if baz_miktar is None else str(baz_miktar),
            "taban_tutar": None if taban_tutar is None else str(taban_tutar), "carpanlar": carpan_json,
            "anahtarlar": [[a, str(p), str(b)] for a, p, b in anahtarlar]}
    if h is None:
        h = m.GiderHavuzu(senaryo_id=senaryo_id, kod=kod, ad=ad, toplam_tutar=toplam_tutar, baz_tipi=baz_tipi, baz_miktar=baz_miktar,
                          taban_tutar=taban_tutar, carpanlar=carpan_json, olusturan=kullanici)
        s.add(h)
    else:
        eski = {"ad": h.ad, "toplam_tutar": str(h.toplam_tutar), "baz_tipi": h.baz_tipi, "baz_miktar": None if h.baz_miktar is None else str(h.baz_miktar),
                "taban_tutar": None if h.taban_tutar is None else str(h.taban_tutar), "carpanlar": h.carpanlar or None,
                "anahtarlar": [[a.alt_kalem, str(a.pay_orani), str(a.baz_miktar)] for a in h.anahtarlar]}
        h.ad, h.toplam_tutar, h.baz_tipi, h.baz_miktar = ad, toplam_tutar, baz_tipi, baz_miktar
        h.taban_tutar, h.carpanlar = taban_tutar, carpan_json
        if eski != yeni:
            s.add(m.DegisiklikKaydi(tablo="gider_havuzu", kayit_id=h.id, islem="guncelle", eski=eski,
                                    yeni=yeni if neden is None else {**yeni, "_neden": neden}, kullanici=kullanici))
    h.anahtarlar = [m.DagitimAnahtari(alt_kalem=a, pay_orani=p, baz_miktar=b) for a, p, b in anahtarlar]
    s.flush()
    return h


def ambalaj_kaydet(s: Session, senaryo_id: int, siniflar: list[tuple[str, Decimal, Decimal, Decimal]], kullanici: str = "sistem",
                   neden: str | None = None) -> list[m.AmbalajSinifi]:
    if not siniflar:
        raise DogrulamaHatasi("ambalaj sınıfı listesi boş olamaz")
    mevcut = ambalajlar(s, senaryo_id)
    eski_liste = [[a.ad, str(a.hacim), str(a.uretim_adedi), str(a.katsayi)] for a in mevcut]
    yeni_liste = [[ad, str(h), str(u), str(k)] for ad, h, u, k in siniflar]
    if eski_liste != yeni_liste:
        # neden verilmişse `yeni` {"siniflar": [...], "_neden": ...} biçimini alır (migrasyonsuz); verilmezse eski liste biçimi korunur
        s.add(m.DegisiklikKaydi(tablo="ambalaj_sinifi", kayit_id=senaryo_id, islem="guncelle", eski=eski_liste,
                                yeni=yeni_liste if neden is None else {"siniflar": yeni_liste, "_neden": neden}, kullanici=kullanici))
    for eski in mevcut:
        s.delete(eski)
    kayitlar = [m.AmbalajSinifi(senaryo_id=senaryo_id, ad=ad, hacim=h, uretim_adedi=u, katsayi=k) for ad, h, u, k in siniflar]
    s.add_all(kayitlar); s.flush()
    return kayitlar


def havuzlar(s: Session, senaryo_id: int) -> dict[str, m.GiderHavuzu]:
    return {h.kod: h for h in s.scalars(select(m.GiderHavuzu).where(m.GiderHavuzu.senaryo_id == senaryo_id))}


_havuzlar = havuzlar


def ambalajlar(s: Session, senaryo_id: int) -> list[m.AmbalajSinifi]:
    return list(s.scalars(select(m.AmbalajSinifi).where(m.AmbalajSinifi.senaryo_id == senaryo_id).order_by(m.AmbalajSinifi.id)))


def _paylar(h: m.GiderHavuzu) -> dict[str, tuple[Decimal, Decimal]]:
    return {a.alt_kalem: (a.pay_orani, a.baz_miktar) for a in h.anahtarlar}


def havuzlari_getir(s: Session, senaryo_id: int) -> GiderHavuzlari:
    h = _havuzlar(s, senaryo_id)
    eksik = [k for k in HAVUZ_KODLARI if k not in h]
    if eksik:
        raise DogrulamaHatasi("gider havuzu eksik", {"eksik": eksik})
    amb = s.scalars(select(m.AmbalajSinifi).where(m.AmbalajSinifi.senaryo_id == senaryo_id).order_by(m.AmbalajSinifi.id))
    return GiderHavuzlari(
        dolum_iscilik_toplam=h["dolum_iscilik"].toplam_tutar, dolum_iscilik_saniye=h["dolum_iscilik"].baz_miktar,
        mal_kabul_iscilik_toplam=h["mal_kabul_iscilik"].toplam_tutar, mal_kabul_paylari=_paylar(h["mal_kabul_iscilik"]),
        etiket_iscilik_toplam=h["etiket_iscilik"].toplam_tutar, etiket_iscilik_saniye=h["etiket_iscilik"].baz_miktar,
        endirekt_iscilik_toplam=h["endirekt_iscilik"].toplam_tutar, endirekt_saniye=h["endirekt_iscilik"].baz_miktar,
        mal_kabul_gug_toplam=h["mal_kabul_gug"].toplam_tutar, mal_kabul_gug_paylari=_paylar(h["mal_kabul_gug"]),
        diger_gug_toplam=h["diger_gug"].toplam_tutar, diger_gug_saniye=h["diger_gug"].baz_miktar,
        elektrik_toplam=h["elektrik"].toplam_tutar, elektrik_hatlar=_paylar(h["elektrik"]),
        dogalgaz_toplam=h["dogalgaz"].toplam_tutar, dogalgaz_hatlar=_paylar(h["dogalgaz"]),
        amortisman_toplam=h["amortisman"].toplam_tutar, amortisman_hatlar=_paylar(h["amortisman"]),
        yonetim_toplam=h["yonetim"].toplam_tutar, pazarlama_toplam=h["pazarlama"].toplam_tutar,
        ambalajlar=tuple(AmbalajSinifi(ad=a.ad, hacim=a.hacim, uretim_adedi=a.uretim_adedi, katsayi=a.katsayi) for a in amb),
    )


def oranlar(s: Session, senaryo_id: int) -> GiderOranlari:
    return oranlari_hesapla(havuzlari_getir(s, senaryo_id))


def pay_toplami_kontrol(s: Session, senaryo_id: int) -> list[dict]:
    out = []
    for kod, h in _havuzlar(s, senaryo_id).items():
        if kod in PAYLI:
            toplam = sum((a.pay_orani for a in h.anahtarlar), Decimal(0))
            if abs(toplam - 1) >= Decimal("0.0005"):
                out.append({"havuz": kod, "toplam": toplam})
    return out
