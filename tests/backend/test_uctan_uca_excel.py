"""Excel → import → servis hesabı, Faz 1 parite değerleriyle (ve dolayısıyla Excel'le) aynı olmalı."""
from datetime import date
import pytest
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi
from backend.servisler import hesap_servisi as hs, import_servisi as ims
from fiyat_motoru import excel_okuyucu as eo
from fiyat_motoru.para import TOLERANS
from tests.test_excel_paritesi import BILINEN_ISTISNALAR

ALANLAR = {"P100": lambda r: r.malzeme_toplami, "P114": lambda r: r.uretim_gideri_toplami, "P120": lambda r: r.diger_giderler_toplami,
           "P124": lambda r: r.finansman["TL"], "P130": lambda r: r.finansman_dahil_maliyet_tl, "P131": lambda r: r.doviz_maliyet["USD"],
           "P137": lambda r: r.satis_fiyati_tl, "P145": lambda r: r.teklifler_usd[0], "P146": lambda r: r.teklifler_usd[1], "P147": lambda r: r.teklifler_usd[2]}

# Aynı ürün kodu birden çok sayfada ise (sayfa adı -> gerekçe). Beklenen: boş.
COKLU_SAYFA: dict[str, str] = {}


@pytest.fixture(scope="module")
def ortam(excel_yolu):
    engine = motor_olustur("sqlite://"); Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    # Parite "ilk bütçe" (S.ALMA BF F) ile koşar: Excel ürün sayfaları F'ye bakar; I (revize) uygulanınca sistem bilinçli olarak Excel'den sapar.
    ozet = ims.excel_tam_yukle(s, excel_yolu, "2026-2027", "Berrak", revize_uygula=False); s.commit()
    wb_f, wb_v = eo.excel_ac(excel_yolu)
    yield s, ozet, wb_f, wb_v
    s.close()


def test_tum_urunler_excel_ile_ayni(ortam):
    s, ozet, wb_f, wb_v = ortam
    assert all("(2)" in a for a in ozet["atlanan"]), ozet["atlanan"]
    farklar = []
    tam_ayni = []
    karsilastirilan = 0
    for ad in eo.urun_sayfalarini_listele(wb_v):
        if "(2)" in ad or ad in COKLU_SAYFA:
            continue
        girdi, _, bek = eo.urun_oku(wb_f[ad], wb_v[ad])
        kod = girdi.kod or f"SAYFA-{ad}"  # ürün kodu olmayan sayfalar SAYFA-<ad> olarak içe aktarılır
        c = hs.hesapla(s, kod, ozet["senaryo_id"], date(2026, 10, 21))
        karsilastirilan += 1
        if not any((ad, alan) in BILINEN_ISTISNALAR for alan in ALANLAR):
            tam_ayni.append(ad)
        for alan, al in ALANLAR.items():
            if (ad, alan) in BILINEN_ISTISNALAR:
                continue
            if abs(bek[alan] - al(c.sonuc)) >= TOLERANS:
                farklar.append((ad, alan, bek[alan], al(c.sonuc)))
    print(f"karsilastirilan={karsilastirilan} tam_ayni={len(tam_ayni)} farklar={len(farklar)}")
    assert karsilastirilan == ozet["urun"] == 67
    assert farklar == [], f"karsilastirilan={karsilastirilan}\n" + "\n".join(f"{a} {b}: excel={c} servis={d}" for a, b, c, d in farklar[:30])


def test_uyari_sayilari_faz1_motoruyla_ayni(ortam, excel_yolu):
    """dugum_tipi uçtan uca taşındığı için ara mamul satırları serviste de uyarı üretmez. Servis ayrıca seviyeyi bilir: altında daha
    derin satırları olan (maliyeti alt satırlardan gelen) satırın 'fiyat listesinde yok' uyarısı düşer. Faz 1 motoru (Excel'den, seviyesiz)
    bu uyarıları üretir; fark yalnız bu uyarılardır, başka uyarı eksik ya da fazla değildir."""
    from collections import Counter
    from sqlalchemy import select
    from fiyat_motoru.parite import karsilastir
    from backend.depo import modeller as m
    from backend.servisler import recete_servisi as rs
    s, ozet, wb_f, wb_v = ortam
    _, faz1 = karsilastir(excel_yolu)
    karsilastirilan = dusen_toplam = 0
    for ad in eo.urun_sayfalarini_listele(wb_v):
        if "(2)" in ad or ad not in faz1:
            continue
        girdi, _, _ = eo.urun_oku(wb_f[ad], wb_v[ad])
        kod = girdi.kod or f"SAYFA-{ad}"
        c = hs.hesapla(s, kod, ozet["senaryo_id"], date(2026, 10, 21))
        u = s.scalar(select(m.Urun).where(m.Urun.kod == kod))
        satirlar = list(rs.aktif_recete_veya_none(s, u.id, ozet["senaryo_id"]).satirlar)
        ust = {x.malzeme_kodu for i, x in enumerate(satirlar[:-1])
               if x.seviye is not None and satirlar[i + 1].seviye is not None and satirlar[i + 1].seviye > x.seviye}
        servis, motor = Counter(c.sonuc.uyarilar), Counter(faz1[ad])
        assert not (servis - motor), (ad, servis - motor)   # serviste fazladan uyarı yok
        dusen = motor - servis
        assert all("fiyat listesinde yok" in w and w.split(" ")[0] in ust for w in dusen.elements()), (ad, dusen)
        dusen_toplam += sum(dusen.values())
        karsilastirilan += 1
    assert karsilastirilan == 67 and dusen_toplam > 0


def test_firesiz_malzeme_toplami_motorla_ayni(ortam):
    """Servis (DB'den okunan elle K/M dahil) firesiz malzeme toplamı, aynı sayfanın doğrudan motor sonucuyla birebir aynı."""
    from fiyat_motoru.gider_dagitim import oranlari_hesapla
    from fiyat_motoru.hesapla import urun_maliyeti
    s, ozet, wb_f, wb_v = ortam
    malzemeler, oranlar = eo.malzemeleri_oku(wb_v), oranlari_hesapla(eo.havuzlari_oku(wb_v))
    n = 0
    for ad in eo.urun_sayfalarini_listele(wb_v):
        if "(2)" in ad:
            continue
        girdi, p, _ = eo.urun_oku(wb_f[ad], wb_v[ad], malzemeler)
        motor = urun_maliyeti(girdi, malzemeler, oranlar, p)
        c = hs.hesapla(s, girdi.kod or f"SAYFA-{ad}", ozet["senaryo_id"], date(2026, 10, 21))
        assert c.sonuc.firesiz.malzeme_toplami == motor.firesiz.malzeme_toplami, ad
        for alan in (lambda r: r.finansman_dahil_maliyet_tl, lambda r: r.satis_fiyati_tl, lambda r: r.doviz_maliyet["USD"],
                     lambda r: r.uretim_gideri_toplami):
            assert abs(alan(c.sonuc.firesiz) - alan(motor.firesiz)) < TOLERANS, ad
            assert abs(alan(c.sonuc) - alan(motor)) < TOLERANS, ad          # fireli zincir de aynı
        n += 1
    assert n == 67
