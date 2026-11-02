"""Süreç içi dashboard önbelleği. Anahtar: (senaryo_id, tarih_iso, gecici) -> satırlar.
Kilitli, TTL'li, en çok EN_COK girdi (fazlası en eski girdiden atılır). Saf: zaman enjekte edilebilir.

Varsayımlar: tek süreç (uvicorn --workers>1 ise her sürecin kendi önbelleği olur, temizle() diğerine ulaşmaz).
API dışından (doğrudan veritabanı) yapılan değişiklikler TTL (600 sn) dolana ya da ?yenile=1 gelene kadar görünmez.
temizle() nesil sayacını artırır; hesap sürerken temizlenmişse koy(nesil=...) eski sonucu yazmaz."""
import threading
import time
from typing import Any, Callable

TTL_SN = 600
EN_COK = 10


class Onbellek:
    def __init__(self, ttl: float = TTL_SN, en_cok: int = EN_COK, zaman: Callable[[], float] = time.monotonic):
        self._ttl, self._en_cok, self._zaman = ttl, en_cok, zaman
        self._kilit = threading.Lock()
        self._veri: dict[tuple, tuple[float, Any]] = {}
        self._nesil = 0
        self._isabet = 0
        self._hesap = 0

    def al(self, anahtar: tuple):
        """Girdi taze ise değeri, yoksa None döner (ve 'hesap' sayacı artar)."""
        with self._kilit:
            g = self._veri.get(anahtar)
            if g is not None and self._zaman() - g[0] <= self._ttl:
                self._isabet += 1
                return g[1]
            self._veri.pop(anahtar, None)
            self._hesap += 1
            return None

    def hesap_say(self) -> None:
        """Önbellek atlanarak (yenile=1) hesaplanan istekleri 'hesap' sayacına işler."""
        with self._kilit:
            self._hesap += 1

    def nesil(self) -> int:
        """Geçersizleme sayacı: hesaplamaya başlamadan okunur, koy()'a verilir."""
        with self._kilit:
            return self._nesil

    def koy(self, anahtar: tuple, deger, nesil: int | None = None) -> bool:
        """nesil verilmişse ve okunduğundan beri temizle() çağrılmışsa (eski veri) yazmaz, False döner."""
        with self._kilit:
            if nesil is not None and nesil != self._nesil:
                return False
            self._veri[anahtar] = (self._zaman(), deger)
            while len(self._veri) > self._en_cok:
                self._veri.pop(min(self._veri, key=lambda k: self._veri[k][0]))
            return True

    def temizle(self, senaryo_id: int | None = None) -> None:
        with self._kilit:
            self._nesil += 1
            if senaryo_id is None:
                self._veri.clear()
            else:
                for k in [k for k in self._veri if k[0] == senaryo_id]:
                    del self._veri[k]

    def istatistik(self) -> dict:
        with self._kilit:
            return {"isabet": self._isabet, "hesap": self._hesap, "girdi": len(self._veri)}


_varsayilan = Onbellek()
al, koy, temizle, istatistik, nesil, hesap_say = (_varsayilan.al, _varsayilan.koy, _varsayilan.temizle,
                                                   _varsayilan.istatistik, _varsayilan.nesil, _varsayilan.hesap_say)
