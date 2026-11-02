"""Faz 5b: PUT /urunler/{kod}/uretim-hedefi neden alır (Veri Girişi kartı); neden değişiklik kaydına ve günlüğe düşer."""
from tests.backend.test_api import _kur, _senaryo, istemci  # noqa: F401 — fixture


def test_uretim_hedefi_neden_gunluge_duser(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    govde = {"vardiya_uretim_adedi": "70000", "dolum_personel": "13", "etiketleme_adedi": "35000", "etiket_personel": "7",
             "mal_kabul_miktar_kg": "0.19", "neden": "Sezon planı güncellendi"}
    r = istemci.put(f"/api/v1/urunler/TEST/uretim-hedefi?senaryo={sid}", json=govde, headers={"X-Kullanici": "esma"})
    assert r.status_code == 200 and r.json()["vardiya_uretim_adedi"] == "70000" and "neden" not in r.json()
    g = istemci.get(f"/api/v1/gunluk?senaryo={sid}&tur=hedef").json()
    assert any(x.get("neden") == "Sezon planı güncellendi" and x["kullanici"] == "esma" for x in g["kayitlar"]), g["kayitlar"][:3]


def test_uretim_hedefi_nedensiz_eskisi_gibi(istemci, oturum):
    sid = _senaryo(istemci); _kur(istemci, sid, oturum)
    r = istemci.put(f"/api/v1/urunler/TEST/uretim-hedefi?senaryo={sid}", json={"vardiya_uretim_adedi": "66000", "dolum_personel": "13",
                    "etiketleme_adedi": "35000", "etiket_personel": "7", "mal_kabul_miktar_kg": "0.19"})
    assert r.status_code == 200 and r.json()["vardiya_uretim_adedi"] == "66000"
