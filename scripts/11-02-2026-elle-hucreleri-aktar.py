"""Tek seferlik: Excel'de formül yerine elle yazılmış hücreleri mevcut bir çalışmaya (senaryo) yazar. Ürünlere, fiyatlara ve
diğer verilere dokunmaz; yalnız
  - üretim hedefindeki elle gider hücreleri (Excel I/K/M/P, satır 104-113 ve 118-119) ve
  - aktif reçetedeki elle Z/S (N) ile elle para birimi (O)
yazılır. Elle hücre desteğinden (11.02.2026) önce yüklenmiş veritabanları içindir; yeni yüklemeler bunları zaten alır.

Varsayılan kuru çalıştırmadır: ne değişeceğini listeler, hiçbir şey yazmaz. --uygula ile önce veri/yedek/ altına yedek alınır,
sonra yazılır. Reçete değişikliği yeni reçete sürümü olarak (kaynak 'elle-hucre'), hedef değişikliği değişiklik kaydıyla yazılır.
Excel ile veritabanındaki reçete satırları (sıra ve malzeme kodu) eşleşmeyen ürün atlanır ve raporlanır.

Kullanım: .venv/Scripts/python scripts/11-02-2026-elle-hucreleri-aktar.py [--db veri/fiyat.db] [--excel <kitap>] [--senaryo 1] [--uygula]
"""
import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

from sqlalchemy import select  # noqa: E402
from backend.depo import modeller as m  # noqa: E402
from backend.depo.veritabani import eksik_kolonlari_tamamla, motor_olustur, oturum_fabrikasi  # noqa: E402
from backend.servisler import hesap_servisi as hs, recete_servisi as rs  # noqa: E402
from fiyat_motoru import excel_okuyucu as eo  # noqa: E402

KULLANICI = "elle-hucre-aktarimi"
NEDEN = "Excel'de formül yerine elle yazılmış hücreler aktarıldı (11.02.2026)"


def _yedek_al(db: Path) -> Path:
    hedef = db.parent / "yedek" / f"11-02-2026-elle-hucre-oncesi-{db.name}"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    if hedef.exists():
        raise SystemExit(f"yedek zaten var, üzerine yazılmaz: {hedef}")
    with sqlite3.connect(db) as kaynak, sqlite3.connect(hedef) as yedek:
        kaynak.backup(yedek)
    return hedef


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--db", default=str(KOK / "veri" / "fiyat.db"))
    a.add_argument("--excel", default=str(KOK / "Fiyat Çalışma - 2026-2027 - Berrak.xlsx"))
    a.add_argument("--senaryo", type=int, default=1)
    a.add_argument("--uygula", action="store_true")
    g = a.parse_args()
    db = Path(g.db).resolve()
    if not db.exists():
        raise SystemExit(f"veritabanı yok: {db}")

    if g.uygula:
        print(f"yedek: {_yedek_al(db)}")
        calisma = db
    else:   # kuru çalıştırma geçici kopyada: eksik kolon eklemesi dahil asıl dosyaya hiçbir şey yazılmaz
        calisma = Path(tempfile.mkdtemp()) / db.name
        with sqlite3.connect(db) as kaynak, sqlite3.connect(calisma) as kopya:
            kaynak.backup(kopya)
    engine = motor_olustur(f"sqlite:///{calisma.as_posix()}")
    eksik_kolonlari_tamamla(engine)   # yeni kolonlar (gider_elle, zs_elle, para_birimi_elle); idempotent
    s = oturum_fabrikasi(engine)()
    sen = hs.senaryo_getir(s, g.senaryo)
    if sen.kilitli:
        raise SystemExit(f"senaryo {sen.id} kilitli; yazılamaz")

    wb_f, wb_v = eo.excel_ac(Path(g.excel))
    malzemeler = eo.malzemeleri_oku(wb_v)
    hedef_say = recete_say = 0
    for ad in eo.urun_sayfalarini_listele(wb_v):
        girdi, _, _ = eo.urun_oku(wb_f[ad], wb_v[ad], malzemeler)
        u = s.scalar(select(m.Urun).where(m.Urun.kod == girdi.kod)) if girdi.kod else None
        if u is None:
            continue   # kodsuz sayfa (SAYFA-0xx) ya da kartı olmayan ürün: ad eşlemesi yapılmaz
        h = s.scalar(select(m.UretimHedefi).where(m.UretimHedefi.urun_id == u.id, m.UretimHedefi.senaryo_id == sen.id))
        elle = hs.gider_elle_normalle(girdi.gider_elle)
        if h is not None and elle and h.gider_elle != elle:
            print(f"{ad} {u.kod}: gider elle {h.gider_elle} -> {elle}")
            hedef_say += 1
            if g.uygula:
                hs.uretim_hedefi_kaydet(s, u.id, sen.id, KULLANICI, NEDEN, gider_elle=elle,
                                        **{x: getattr(h, x) for x in hs.URETIM_ALANLARI})

        r = rs.aktif_recete_veya_none(s, u.id, sen.id)
        if r is None or not any(x.zs_elle or x.para_birimi_elle for x in girdi.recete):
            continue
        if [x.malzeme_kodu for x in r.satirlar] != [x.malzeme_kodu for x in girdi.recete]:
            print(f"{ad} {u.kod}: ATLANDI — reçete satırları Excel'le eşleşmiyor (ekrandan değiştirilmiş olabilir)")
            continue
        degisen = [(x.sira, e.zs_elle, e.para_birimi_elle) for x, e in zip(r.satirlar, girdi.recete)
                   if (x.zs_elle, x.para_birimi_elle) != (e.zs_elle, e.para_birimi_elle)]
        if not degisen:
            continue
        print(f"{ad} {u.kod}: reçete elle Z/S, para birimi (sıra, Z/S, para birimi) {degisen}")
        recete_say += 1
        if g.uygula:
            yeni = {sira: (zs, pb) for sira, zs, pb in degisen}
            satirlar = [{"malzeme_kodu": x.malzeme_kodu, "ad": x.ad, "miktar": x.miktar, "birim": x.birim, "fire_override": x.fire_override,
                         "dugum_tipi": x.dugum_tipi, "brut_miktar_elle": x.brut_miktar_elle, "birim_fiyat_elle": x.birim_fiyat_elle,
                         "seviye": x.seviye, "zs_elle": yeni.get(x.sira, (x.zs_elle, x.para_birimi_elle))[0],
                         "para_birimi_elle": yeni.get(x.sira, (x.zs_elle, x.para_birimi_elle))[1]} for x in r.satirlar]
            rs.yeni_versiyon(s, u.id, sen.id, satirlar, "elle-hucre", KULLANICI)

    print(f"özet: {hedef_say} üründe elle gider, {recete_say} üründe reçete Z/S-para birimi" + ("" if g.uygula else " (kuru çalıştırma, yazılmadı)"))
    if g.uygula:
        s.commit()
        print("yazıldı.")
    else:
        s.rollback()
    s.close()


if __name__ == "__main__":
    main()
