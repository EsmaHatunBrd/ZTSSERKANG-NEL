"""Müşavir Excel'i — Fiyat Çalışması kitabı: muhasebenin kendi kitabının (şablon) düzeninde, rakamları uygulamadan gelen dosya.
İndirme her rol için açıktır (veri yazmaz; diğer disa-aktar uçlarıyla aynı kural)."""
from datetime import date
from urllib.parse import quote
from fastapi import APIRouter, Query
from fastapi.responses import Response
from ..servisler import hesap_servisi as hs, musavir_excel_servisi as mx
from .bagimliliklar import OturumDep
from .semalar import HATA_404_422, FiyatKitabiDurumu

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
router = APIRouter(tags=["disa-aktar"])


def ek_basligi(dosya_adi: str) -> str:
    """Content-Disposition: ASCII yedek ad + RFC 5987 UTF-8 ad (Türkçe harfler için)."""
    ascii_ad = dosya_adi.encode("ascii", "ignore").decode().replace('"', "") or "musavir.xlsx"
    return f"attachment; filename=\"{ascii_ad}\"; filename*=UTF-8''{quote(dosya_adi)}"


@router.get("/disa-aktar/musavir/fiyat-kitabi.xlsx", response_model=None, summary="Müşavir Excel'i (Fiyat Çalışması kitabının düzeninde)",
            responses={200: {"content": {XLSX: {"schema": {"type": "string", "format": "binary"}}},
                             "description": "Şablon kitap, girdi hücreleri uygulamanın güncel değerleriyle (.xlsx)"}, **HATA_404_422})
def fiyat_kitabi_xlsx(s: OturumDep, senaryo_id: int = Query(...), tarih: date | None = None):
    """Şablon yoksa 404 `sablon_yok`. Formüller, biçimler ve sayfa düzeni şablondaki gibi kalır; Excel açılınca toplamlar yeniden hesaplanır.
    `X-Uyari-Sayisi` başlığı: dokunulmayan/yazılamayan hücre uyarılarının sayısı (ayrıntı: .../fiyat-kitabi/durum?uyarilar=true)."""
    sonuc = mx.fiyat_kitabi_hazirla(s, hs.senaryo_getir(s, senaryo_id).id, tarih)
    return Response(content=sonuc.icerik, media_type=XLSX,
                    headers={"Content-Disposition": ek_basligi(sonuc.dosya_adi), "X-Uyari-Sayisi": str(len(sonuc.uyarilar)),
                             "Access-Control-Expose-Headers": "Content-Disposition, X-Uyari-Sayisi"})


@router.get("/disa-aktar/musavir/fiyat-kitabi/durum", response_model=FiyatKitabiDurumu, responses=HATA_404_422,
            summary="Müşavir Excel'i: şablon var mı, (istenirse) uyarılar")
def fiyat_kitabi_durum(s: OturumDep, senaryo_id: int = Query(...), uyarilar: bool = Query(False), tarih: date | None = None):
    sen = hs.senaryo_getir(s, senaryo_id)
    oz = mx.sablon_ozeti(s, sen.id)
    out = {"sablon": oz, "uyarilar_ozeti": None}
    if oz is not None and uyarilar:
        r = mx.fiyat_kitabi_hazirla(s, sen.id, tarih)
        out["uyarilar_ozeti"] = {"sayi": len(r.uyarilar), "uyarilar": r.uyarilar[:100], "degisen_hucre": r.degisen_hucre,
                                 "urun_sayfasi": r.urun_sayfasi, "yazilan_urun": r.yazilan_urun}
    return out
