import os
from pathlib import Path
from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from .depo.veritabani import oturum_ver
from .servisler import isitici, onbellek
from .servisler.hatalar import BulunamadiHatasi, CatismaHatasi, DogrulamaHatasi, KilitliHatasi, KimlikHatasi, YetkiHatasi
from .api import senaryolar, parametreler, malzemeler, gider, urunler, teklifler, fire, import_, disa_aktar, kapasite, satis, karsilastirma, aktarim, gunluk, kiyas, tutarlilik, kimlik
from .api.bagimliliklar import kimlik_denetle


def _hata(kod: int, hata: str, mesaj: str, alanlar: dict | None = None, ayrinti_kodu: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=kod, content={"hata": hata, "mesaj": mesaj, "alanlar": alanlar or {}, "kod": ayrinti_kodu})


YAZMA_YONTEMLERI = ("POST", "PUT", "PATCH", "DELETE")


def onbellegi_temizlemeli_mi(yontem: str, yol: str) -> bool:
    """Yazan /api/v1 istekleri dashboard önbelleğini boşaltır. İstisna: salt okunur POST'lar (`.../hesapla`, fiyat listesi önizlemesi)."""
    if yontem not in YAZMA_YONTEMLERI or not yol.startswith("/api/v1/"):
        return False
    yol = yol.rstrip("/")
    return not (yol.endswith("/hesapla") or yol == "/api/v1/import/fiyat-listesi")


def giris_zorunlu_mu() -> bool:
    """GIRIS_ZORUNLU=0 giriş ekranını kapatır (testler, eski tek kullanıcılı kurulum). Varsayılan: açık."""
    return os.environ.get("GIRIS_ZORUNLU", "1").strip().lower() not in ("0", "false", "hayir")


def uygulama_olustur(oturum_bagimliligi=None, giris_zorunlu: bool | None = None) -> FastAPI:
    app = FastAPI(title="Fiyat Çalışması API", version="0.2.0")
    app.state.giris_zorunlu = giris_zorunlu_mu() if giris_zorunlu is None else giris_zorunlu
    onbellek.temizle()   # yeni uygulama = temiz başlangıç (testlerde uygulamalar arası sızıntı olmaz)

    @app.middleware("http")
    async def _onbellek_gecersiz_kil(request: Request, call_next):
        try:
            return await call_next(request)
        finally:   # hata yanıtında da boşalt: kısmi yazma ihtimaline karşı güvenli taraf
            if onbellegi_temizlemeli_mi(request.method, request.url.path):
                onbellek.temizle()
                isitici.yazma_sonrasi(str(request.base_url))   # arka planda yeniden hesapla: kullanıcı dashboard'u soğuk bulmasın
    kokenler = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=kokenler, allow_methods=["*"], allow_headers=["*"])
    # Giriş ekranının uçları (giriş, çıkış, ben, şifre) denetimsiz; diğer tüm uçlar oturum ve rol denetiminden geçer.
    app.include_router(kimlik.acik_router, prefix="/api/v1")
    for r in (senaryolar, parametreler, malzemeler, gider, urunler, teklifler, fire, import_, disa_aktar, kapasite, satis, karsilastirma, aktarim, gunluk, kiyas, tutarlilik, kimlik):
        app.include_router(r.router, prefix="/api/v1", dependencies=[Depends(kimlik_denetle)])
    if oturum_bagimliligi is not None:
        app.dependency_overrides[oturum_ver] = oturum_bagimliligi

    @app.exception_handler(BulunamadiHatasi)
    async def _404(_: Request, e: BulunamadiHatasi):
        return _hata(404, "bulunamadi", e.mesaj, e.alanlar, e.kod)

    @app.exception_handler(DogrulamaHatasi)
    async def _422(_: Request, e: DogrulamaHatasi):
        return _hata(422, "dogrulama", e.mesaj, e.alanlar, e.kod)

    @app.exception_handler(RequestValidationError)
    async def _422b(_: Request, e: RequestValidationError):
        return _hata(422, "dogrulama", "istek gövdesi geçersiz", {".".join(str(p) for p in x["loc"]): x["msg"] for x in e.errors()})

    @app.exception_handler(KimlikHatasi)
    async def _401(_: Request, e: KimlikHatasi):
        return _hata(401, "giris", e.mesaj, e.alanlar, e.kod)

    @app.exception_handler(YetkiHatasi)
    async def _403(_: Request, e: YetkiHatasi):
        return _hata(403, "yetki", e.mesaj, e.alanlar, e.kod)

    @app.exception_handler(KilitliHatasi)
    async def _409k(_: Request, e: KilitliHatasi):
        return _hata(409, "kilitli", e.mesaj, e.alanlar, e.kod)

    @app.exception_handler(CatismaHatasi)
    async def _409c(_: Request, e: CatismaHatasi):
        return _hata(409, "catisma", e.mesaj, e.alanlar, e.kod)

    @app.exception_handler(IntegrityError)   # oturum_ver oturumu zaten geri alır
    async def _409(_: Request, e: IntegrityError):
        return _hata(409, "cakisma", "kayıt çakışması (benzersiz alan veya ilişki)")

    @app.exception_handler(Exception)        # yığın izi yanıta sızmaz
    async def _500(_: Request, e: Exception):
        return _hata(500, "sunucu", "beklenmeyen hata")
    _arayuzu_bagla(app)
    return app


ARAYUZ_DIZINI = Path(os.environ.get("ARAYUZ_DIZINI", Path(__file__).resolve().parents[1] / "frontend" / "dist"))


def _arayuzu_bagla(app: FastAPI) -> None:
    """Üretim derlemesi (frontend/dist) varsa aynı sunucudan sunulur: http://<sunucu>:8000/ tek adres, Vite dev sunucusu gerekmez.
    /api/* yolları router'larda; diğer yollar dosyaysa dosya, değilse index.html (tarayıcı yönlendirmesi SPA'da çözülür).
    dist yoksa (yalnız API kullanımı, testler) hiçbir şey bağlanmaz."""
    index = ARAYUZ_DIZINI / "index.html"
    if not index.is_file():
        return
    app.mount("/assets", StaticFiles(directory=ARAYUZ_DIZINI / "assets"), name="arayuz-assets")

    @app.get("/{yol:path}", include_in_schema=False)
    async def _arayuz(yol: str):
        if yol.startswith("api/"):
            return _hata(404, "bulunamadi", "uç yok")
        aday = (ARAYUZ_DIZINI / yol) if yol else index
        if yol and aday.is_file() and aday.resolve().is_relative_to(ARAYUZ_DIZINI.resolve()):
            return FileResponse(aday)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


app = uygulama_olustur()   # uvicorn backend.uygulama:app
