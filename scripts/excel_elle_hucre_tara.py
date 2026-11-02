r"""Urun sayfalarinin recete satirlarinda elle mudahale edilmis hucreleri adresiyle listeler:
  K_sabit   : J (fire) sifir degilken K sabit sayi (ya da J=0 iken I'dan farkli sabit K)
  K_formul  : K formulu =I/(1-J) degil (ornegin =I/0.98 veya =I/(1-J)*0.8)
  M_sabit   : M (birim fiyat) fiyat listesi aramasi yerine sabit sayi
  N_sabit   : N (Z/S) sabit deger
'*' ile isaretli adresler, satirin Excel P tutarinin motor hesabindan TOLERANS'tan fazla ayrismasina yol acan satirlardadir.
Kullanim: .\.venv\Scripts\python scripts/excel_elle_hucre_tara.py ["Fiyat Çalışma - 2026-2027 - Berrak.xlsx"]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fiyat_motoru.excel_okuyucu import (_etiket_satiri, excel_ac, formul_mu as _formul_mu, k_elle_mi, malzemeleri_oku,
                                        urun_oku, urun_sayfalarini_listele)
from fiyat_motoru.fire import brut_miktar
from fiyat_motoru.malzeme import malzeme_tutari
from fiyat_motoru.modeller import ReceteSatiri
from fiyat_motoru.para import D, TOLERANS

YAKIN = D("1e-9")


def tara_sayfa(ws_f, ws_v, malzemeler) -> dict[str, list[tuple[str, bool]]]:
    """Donus: {'K_sabit': [(adres, etkili)], 'K_formul': [...], 'M_sabit': [...], 'N_sabit': [...]}"""
    _, p, _ = urun_oku(ws_f, ws_v)
    r100 = _etiket_satiri(ws_v, "HAMMADE - YARDIMCI MALZEME MALİYETİ TOPLAMI")
    out = {"K_sabit": [], "K_formul": [], "M_sabit": [], "N_sabit": []}
    for r in range(6, r100):
        if not ws_v[f"D{r}"].value:
            continue
        kod = str(ws_v[f"D{r}"].value).strip()
        malzeme = malzemeler.get(kod)
        i, j, k = D(ws_v[f"I{r}"].value), D(ws_v[f"J{r}"].value), D(ws_v[f"K{r}"].value)
        satir = ReceteSatiri(malzeme_kodu=kod, ad="", miktar=i, fire_orani=j, birim=None)
        etkili = abs(D(ws_v[f"P{r}"].value) - malzeme_tutari(satir, malzeme, p)[0].tutar) >= TOLERANS
        kf = ws_f[f"K{r}"].value
        if not _formul_mu(kf):
            if j != 0 or k != i:
                out["K_sabit"].append((f"K{r}", etkili and abs(k - brut_miktar(i, j)) >= YAKIN))
        elif k_elle_mi(kf, r):
            out["K_formul"].append((f"K{r}", etkili and abs(k - brut_miktar(i, j)) >= YAKIN))
        mf = ws_f[f"M{r}"].value
        if not _formul_mu(mf):
            out["M_sabit"].append((f"M{r}", etkili and (malzeme is None or D(mf) != malzeme.fiyat)))
        nf = ws_f[f"N{r}"].value
        if not _formul_mu(nf):
            out["N_sabit"].append((f"N{r}", etkili and (malzeme is None or str(nf).upper() != (malzeme.zs or ""))))
    return out


def _yaz(liste) -> str:
    return ",".join(a + ("*" if e else "") for a, e in liste)


def main():
    yol = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Fiyat Çalışma - 2026-2027 - Berrak.xlsx")
    wb_f, wb_v = excel_ac(yol)
    malzemeler = malzemeleri_oku(wb_v)
    for ad in urun_sayfalarini_listele(wb_v):
        t = tara_sayfa(wb_f[ad], wb_v[ad], malzemeler)
        if any(t.values()):
            print(ad, " | ".join(f"{k}: {_yaz(v)}" for k, v in t.items() if v))


if __name__ == "__main__":
    main()
