"""Dashboard önbelleğini yazma sonrası arka planda ısıtır.

Her yazan istek önbelleği boşaltır (uygulama.py middleware); eskiden bir sonraki dashboard açılışı soğuk hesabı (67 ürün, 1,5-5 sn)
kullanıcıya bekletiyordu. Isıtıcı, boşaltmadan kısa süre sonra sunucunun kendi GET /api/v1/urunler ve /uyarilar uçlarına istek atar;
böylece hesap kullanıcı sayfayı açmadan önce biter. Kendi ucuna istek attığı için api/urunler iç yapısına bağımlı değildir
(önbellek anahtarları, `tum` gibi parametreler değişse de UI'nin kullandığı varsayılan yol ısınır).

Varsayımlar: tek süreç; peş peşe yazmalar tek ısıtmaya birleşir (debounce); ısıtma sırasında yeni yazma olursa onbellek.koy nesil
kontrolüyle eski sonucu yazmaz ve bir sonraki tetik yeniden ısıtır. Hata olursa sessizce loglanır (ısıtma hiçbir isteği düşürmez)."""
from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from collections.abc import Callable

log = logging.getLogger("fiyat.isitici")

GECIKME_SN = float(os.environ.get("ONBELLEK_ISITMA_GECIKME_SN", "0.8"))
ACIK = os.environ.get("ONBELLEK_ISITMA", "1") not in ("0", "false", "hayir")
UCLAR = ("/api/v1/urunler?senaryo={id}&boyut=1", "/api/v1/uyarilar?senaryo={id}")
# Süreç başına rastgele iç anahtar: giriş zorunluyken ısıtıcı kendi GET isteklerini bununla yapar (dışarıya hiç verilmez).
IC_ANAHTAR = secrets.token_urlsafe(32)


def _istek(url: str):
    import urllib.request
    return urllib.request.Request(url, headers={"X-Ic-Anahtar": IC_ANAHTAR})


def _varsayilan_getir(url: str) -> None:
    import urllib.request
    with urllib.request.urlopen(_istek(url), timeout=120) as y:   # noqa: S310 — yalnız kendi sunucumuzun adresi
        y.read(1)


def _varsayilan_senaryolar(taban: str, getir_json: Callable[[str], object]) -> list[int]:
    veri = getir_json(f"{taban}/api/v1/senaryolar")
    kayitlar = veri.get("kayitlar", []) if isinstance(veri, dict) else []
    return [int(k["id"]) for k in kayitlar if not k.get("kilitli")]   # kilitli senaryo değişmez, soğuması önemsiz


def _varsayilan_getir_json(url: str) -> object:
    import json
    import urllib.request
    with urllib.request.urlopen(_istek(url), timeout=30) as y:   # noqa: S310
        return json.load(y)


class Isitici:
    def __init__(self, getir: Callable[[str], None] = _varsayilan_getir, getir_json: Callable[[str], object] = _varsayilan_getir_json,
                 gecikme_sn: float = GECIKME_SN, uyku: Callable[[float], None] = time.sleep):
        self._getir, self._getir_json, self._gecikme, self._uyku = getir, getir_json, gecikme_sn, uyku
        self._kilit = threading.Lock()
        self._bekleyen: str | None = None     # son tetiğin taban adresi; None = iş yok
        self._calisiyor = False
        self.isitma_sayisi = 0                 # testler ve gözlem için

    def tetikle(self, taban_adres: str) -> None:
        """Yazma sonrası çağrılır. Çalışan bir ısıtma varsa yalnız 'yeniden yap' notu düşer; yoksa arka plan iş parçacığı açar."""
        taban = taban_adres.rstrip("/")
        with self._kilit:
            self._bekleyen = taban
            if self._calisiyor:
                return
            self._calisiyor = True
        threading.Thread(target=self._dongu, name="onbellek-isitici", daemon=True).start()

    def _dongu(self) -> None:
        try:
            while True:
                self._uyku(self._gecikme)   # peş peşe yazmaları birleştir
                with self._kilit:
                    taban, self._bekleyen = self._bekleyen, None
                if taban is None:
                    return
                self._isit(taban)
                with self._kilit:
                    if self._bekleyen is None:
                        self._calisiyor = False
                        return
        except BaseException:   # noqa: BLE001 — iş parçacığı asla gürültüsüz ölmesin
            log.exception("ısıtıcı döngüsü düştü")
            with self._kilit:
                self._calisiyor = False

    def _isit(self, taban: str) -> None:
        try:
            idler = _varsayilan_senaryolar(taban, self._getir_json)
        except Exception as e:   # noqa: BLE001
            log.warning("ısıtma: senaryolar alınamadı: %s", e)
            return
        for sid in idler:
            for uc in UCLAR:
                try:
                    self._getir(f"{taban}{uc.format(id=sid)}")
                except Exception as e:   # noqa: BLE001
                    log.warning("ısıtma başarısız (%s): %s", uc, e)
                    break
        self.isitma_sayisi += 1


ISITICI = Isitici()


def yazma_sonrasi(taban_adres: str) -> None:
    """Middleware kancası: ONBELLEK_ISITMA=0 ile kapatılabilir; test istemcisinin sahte sunucusu için atlanır."""
    if not ACIK or "testserver" in taban_adres:
        return
    ISITICI.tetikle(taban_adres)
