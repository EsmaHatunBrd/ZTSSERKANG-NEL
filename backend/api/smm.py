"""Maliyet muhasebesi (SMM): aylık SMM Excel'ini dönem olarak yükleme, dönemler, stok/envanter tablosu, aşama maliyetleri ve sarf farkı."""
from decimal import Decimal
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from ..servisler import smm_asama_servisi as sa
from ..servisler import smm_ozet_servisi as so
from ..servisler import smm_servisi as ss
from .bagimliliklar import OturumDep, kullanici_ver
from .semalar import (HATA_404_409_422, HATA_404_422, SmmDagitim, SmmDagitimGiris, SmmDonemCikis, SmmDonemListesi, SmmOzeti, SmmSarfFarki,
                      SmmStokTablosu, SmmUretimMaliyeti, SmmUrunRecetesi)
from .semalar import GeriAlSonucu, SmmDonemExcelOnizleme, SonYuklemeYaniti

router = APIRouter(tags=["smm"])


@router.get("/smm/donemler", response_model=SmmDonemListesi)
def donemler(s: OturumDep):
    return {"kayitlar": ss.donemler(s)}


@router.post("/smm/donemler/yukle/onizle", response_model=SmmDonemExcelOnizleme, responses=HATA_404_409_422)
def yukle_onizle(s: OturumDep, dosya: UploadFile = File(...), yil: int | None = Form(None), ay: int | None = Form(None)):
    """SMM Excel'i önizlemesi (yazmaz): dönem, kalem sayıları, dönem varsa yeni / değişen / silinecek kalem, metin sayı hücreleri, uyarılar."""
    return ss.yukle_onizle(s, dosya.file.read(ss.MAKS_BAYT + 1), dosya.filename or "", yil, ay)


@router.post("/smm/donemler/yukle", response_model=SmmDonemCikis, responses=HATA_404_409_422)
def yukle(s: OturumDep, dosya: UploadFile = File(...), yil: int | None = Form(None), ay: int | None = Form(None),
          uzerine_yaz: bool = Form(False), onay: bool = Form(False), k: str = Depends(kullanici_ver)):
    """SMM Excel'i (.xlsx). Dönem verilmezse dosya adından çıkarılır (ör. '09-2026 SMM.xlsx'). Dönem yüklüyse 409; `uzerine_yaz=true` ile baştan yazılır.
    Üzerine yazarken dosyadaki kalem dönemdekinin yarısından azsa 409 `satir_kaybi_onayi`; `onay=true` ile yazılır. Kalem yoksa 422 `bos_dosya`."""
    icerik = dosya.file.read(ss.MAKS_BAYT + 1)
    return ss.yukle(s, icerik, dosya.filename or "", yil, ay, uzerine_yaz, k, onay=onay)


@router.get("/smm/donemler/{donem_id}/son-yukleme", response_model=SonYuklemeYaniti, responses=HATA_404_422)
def donem_son_yukleme(s: OturumDep, donem_id: int):
    """Dönemin geri alınabilecek son SMM Excel'i yüklemesi; yoksa `son: null`."""
    return ss.son_yukleme(s, donem_id)


@router.post("/smm/donemler/{donem_id}/son-yuklemeyi-geri-al", response_model=GeriAlSonucu, responses=HATA_404_409_422)
def donem_geri_al(s: OturumDep, donem_id: int, k: str = Depends(kullanici_ver)):
    """Son SMM Excel'i yüklemesini geri alır: üzerine yazıldıysa dönem önceki hâline döner, yeni dönem açtıysa dönem silinir.
    Dönem kapalıysa 409 `donem_kilitli`; açılışını bu dönemden devralan dönem varsa 409 `devralan_donem_var`; yükleme yoksa 404 `yedek_yok`."""
    return ss.son_yuklemeyi_geri_al(s, donem_id, k)


@router.delete("/smm/donemler/{donem_id}", status_code=204, response_class=Response, responses=HATA_404_422)
def sil(s: OturumDep, donem_id: int, k: str = Depends(kullanici_ver)):
    ss.donem_sil(s, donem_id, k)
    return Response(status_code=204)


@router.get("/smm/donemler/{donem_id}/stok", response_model=SmmStokTablosu, responses=HATA_404_422)
def stok(s: OturumDep, donem_id: int, tur: str | None = None, arama: str | None = None, yalniz_hareketli: bool = Query(True),
         yalniz_kontrol: bool = Query(False)):
    return ss.stok_tablosu(s, donem_id, tur, arama, yalniz_hareketli, yalniz_kontrol)


@router.get("/smm/donemler/{donem_id}/uretim", response_model=SmmUretimMaliyeti, responses=HATA_404_422)
def uretim(s: OturumDep, donem_id: int, asama: int = Query(50), arama: str | None = None, yalniz_farkli: bool = Query(False)):
    """Aşama maliyetleri (20 sebze kabul / 40 üretim hattı / 50 etiketleme): özetler, dağıtım havuzları ve seçilen aşamanın ürünleri."""
    return sa.uretim_maliyeti(s, donem_id, asama, arama, yalniz_farkli)


@router.get("/smm/donemler/{donem_id}/uretim/{asama}/{kod}", response_model=SmmUrunRecetesi, responses=HATA_404_422)
def urun_recetesi(s: OturumDep, donem_id: int, asama: int, kod: str):
    return sa.urun_recetesi(s, donem_id, asama, kod)


@router.put("/smm/donemler/{donem_id}/dagitim", response_model=SmmDagitim, responses=HATA_404_422)
def dagitim(s: OturumDep, donem_id: int, g: SmmDagitimGiris, k: str = Depends(kullanici_ver)):
    """Dağıtılacak işçilik/GÜG havuzlarını ve dağıtım anahtarlarını değiştirir; aşama maliyetleri yeniden hesaplanır."""
    return sa.dagitim_guncelle(s, donem_id, g.havuzlar, k, g.anahtarlar)


@router.get("/smm/donemler/{donem_id}/sarf-farki", response_model=SmmSarfFarki, responses=HATA_404_422)
def sarf_farki(s: OturumDep, donem_id: int, arama: str | None = None, tur: str | None = None, esik: Decimal = Query(Decimal(0), ge=0)):
    """Reçeteye göre sarf ile sayımla bulunan sarfın malzeme bazında farkı (büyük TL farkı üstte)."""
    return sa.sarf_farki(s, donem_id, arama, tur, esik)


@router.get("/smm/donemler/{donem_id}/ozet", response_model=SmmOzeti, responses=HATA_404_422)
def ozet(s: OturumDep, donem_id: int):
    """SMM özeti: dönem sonu stok değerlemesi, SMM tablosu (150 -> 710 -> 151 -> 152 -> 620), stok mizanı karşılaştırması, fiş taslağı."""
    return so.smm_ozeti(s, donem_id)


# ---------------------------------------------------------------- dönem devri ve kalıcı reçeteler
from ..servisler import smm_donem_servisi as sd  # noqa: E402
from ..servisler import smm_recete_servisi as sr  # noqa: E402
from .semalar import (SmmAlternatifGiris, SmmAnaReceteOnizleme, SmmReceteDetayi, SmmReceteKaynagiGiris, SmmReceteKiyas,  # noqa: E402
                      SmmReceteListesi, SmmYeniDonemCikis, SmmYeniDonemGiris)


@router.post("/smm/donemler", response_model=SmmYeniDonemCikis, status_code=201, responses=HATA_404_409_422)
def yeni_donem(s: OturumDep, g: SmmYeniDonemGiris, k: str = Depends(kullanici_ver)):
    """Excel'siz yeni dönem: dönem başı stok önceki dönemin sayımından devreder; kartlar, süreler ve dağıtım havuzları kopyalanır."""
    return sd.yeni_donem(s, g.yil, g.ay, k)


@router.put("/smm/donemler/{donem_id}/recete-kaynagi", response_model=SmmDonemCikis, responses=HATA_404_422)
def recete_kaynagi(s: OturumDep, donem_id: int, g: SmmReceteKaynagiGiris, k: str = Depends(kullanici_ver)):
    return sd.recete_kaynagi(s, donem_id, g.kaynak, k)


@router.get("/smm/receteler", response_model=SmmReceteListesi)
def receteler(s: OturumDep, arama: str | None = None, asama: int | None = None):
    return sr.liste(s, arama, asama)


@router.post("/smm/receteler/onizle", response_model=SmmAnaReceteOnizleme, responses=HATA_404_422)
def recete_onizle(s: OturumDep, dosya: UploadFile = File(...)):
    """Canias ürün ağacı dökümü (.xlsx): kaç ürün eklenecek / değişecek / kalkacak (kaydetmez)."""
    return sr.onizle(s, dosya.file.read(ss.MAKS_BAYT + 1))


@router.post("/smm/receteler/yukle", response_model=SmmAnaReceteOnizleme, responses=HATA_404_409_422)
def recete_yukle(s: OturumDep, dosya: UploadFile = File(...), onay: bool = Form(False), k: str = Depends(kullanici_ver)):
    """Tüm kalıcı reçeteleri dosyadakilerle değiştirir; ürün başına alternatif seçimleri korunur. Okunabilen satır yoksa 422 `bos_dosya`;
    dosyadaki ürün mevcut ürünlerin yarısından azsa 409 `satir_kaybi_onayi` (`onay=true` ile yazılır)."""
    return sr.yukle(s, dosya.file.read(ss.MAKS_BAYT + 1), dosya.filename or "", k, onay=onay)


@router.get("/smm/receteler/son-yukleme", response_model=SonYuklemeYaniti)
def recete_son_yukleme(s: OturumDep):
    """Geri alınabilecek son Canias dökümü yüklemesi; yoksa `son: null`."""
    return sr.son_yukleme_yedegi(s)


@router.post("/smm/receteler/son-yuklemeyi-geri-al", response_model=GeriAlSonucu, responses=HATA_404_422)
def recete_geri_al(s: OturumDep, k: str = Depends(kullanici_ver)):
    """Kalıcı reçeteleri son yüklemeden önceki hâline döndürür (elle değiştirilmiş ürünlere dokunulmaz). Yükleme yoksa 404 `yedek_yok`."""
    return sr.son_yuklemeyi_geri_al(s, k)


@router.get("/smm/receteler/kiyas", response_model=SmmReceteKiyas, responses=HATA_404_422)
def recete_kiyas(s: OturumDep, donem: int = Query(...)):
    """Kalıcı reçeteler ile dönemin Excel 20/40/50 reçetelerinin karşılaştırması."""
    return sr.kiyas(s, donem)


@router.get("/smm/receteler/{kod}", response_model=SmmReceteDetayi, responses=HATA_404_422)
def recete(s: OturumDep, kod: str):
    return sr.urun(s, kod)


@router.put("/smm/receteler/{kod}/alternatif", response_model=SmmReceteDetayi, responses=HATA_404_422)
def alternatif(s: OturumDep, kod: str, g: SmmAlternatifGiris, k: str = Depends(kullanici_ver)):
    return sr.alternatif_sec(s, kod, g.alternatif, k)


# ---------------------------------------------------------------- reçeteyi elle düzenleme
from .semalar import (SmmAlternatifKopyaGiris, SmmMalzemeAdayi, SmmReceteSatirGiris, SmmReceteSatirGuncelle,  # noqa: E402
                      SmmYeniReceteGiris)


@router.get("/smm/malzeme-ara", response_model=list[SmmMalzemeAdayi])
def malzeme_ara(s: OturumDep, q: str = Query("", max_length=60)):
    return sr.malzeme_ara(s, q)


@router.post("/smm/receteler", response_model=SmmReceteDetayi, status_code=201, responses=HATA_404_409_422)
def yeni_recete(s: OturumDep, g: SmmYeniReceteGiris, k: str = Depends(kullanici_ver)):
    """Canias'ta henüz olmayan ürün için elle reçete (ilk satırıyla)."""
    return sr.satir_ekle(s, g.ana_kod, g.alternatif, g.malzeme_kod, g.malzeme_ad, g.miktar, g.birim, g.fire_orani, k, ana_ad=g.ana_ad,
                         yeni_urun=True)


@router.post("/smm/receteler/{kod}/satirlar", response_model=SmmReceteDetayi, status_code=201, responses=HATA_404_409_422)
def satir_ekle(s: OturumDep, kod: str, g: SmmReceteSatirGiris, k: str = Depends(kullanici_ver)):
    return sr.satir_ekle(s, kod, g.alternatif, g.malzeme_kod, g.malzeme_ad, g.miktar, g.birim, g.fire_orani, k)


@router.put("/smm/recete-satirlari/{satir_id}", response_model=SmmReceteDetayi, responses=HATA_404_422)
def satir_guncelle(s: OturumDep, satir_id: int, g: SmmReceteSatirGuncelle, k: str = Depends(kullanici_ver)):
    return sr.satir_guncelle(s, satir_id, g.model_dump(), k)


@router.delete("/smm/recete-satirlari/{satir_id}", response_model=SmmReceteDetayi, responses=HATA_404_422)
def satir_sil(s: OturumDep, satir_id: int, k: str = Depends(kullanici_ver)):
    return sr.satir_sil(s, satir_id, k)


@router.post("/smm/receteler/{kod}/alternatif-kopyala", response_model=SmmReceteDetayi, status_code=201, responses=HATA_404_409_422)
def alternatif_kopyala(s: OturumDep, kod: str, g: SmmAlternatifKopyaGiris, k: str = Depends(kullanici_ver)):
    return sr.alternatif_kopyala(s, kod, g.kaynak, g.yeni, k)


@router.post("/smm/receteler/{kod}/canias-a-don", response_model=SmmReceteDetayi, responses=HATA_404_422)
def caniasa_don(s: OturumDep, kod: str, k: str = Depends(kullanici_ver)):
    """Elle değiştirilmiş reçeteyi son Canias dökümündeki hâline döndürür."""
    return sr.caniasa_don(s, kod, k)


# ---------------------------------------------------------------- aşamayı elle düzenleme, üretim süreleri
from .semalar import SmmAsamaGiris, SmmSure, SmmSureGiris, SmmSureListesi, SmmUrunElleGiris  # noqa: E402


@router.put("/smm/receteler/{kod}/asama", response_model=SmmReceteDetayi, responses=HATA_404_422)
def recete_asamasi(s: OturumDep, kod: str, g: SmmAsamaGiris, k: str = Depends(kullanici_ver)):
    """Ürünün aşamasını (20 / 40 / 50) elle değiştirir."""
    return sr.asama_degistir(s, kod, g.asama, k)


@router.put("/smm/donemler/{donem_id}/uretim/{asama}/{kod}/elle", response_model=SmmUrunRecetesi, responses=HATA_404_422)
def urun_elle(s: OturumDep, donem_id: int, asama: int, kod: str, g: SmmUrunElleGiris, k: str = Depends(kullanici_ver)):
    """Ürünün aşama değerlerini elle girer (malzeme, iscilik, gug, fire, birim_maliyet; birim başına TL). null = formüle dön."""
    return sa.urun_elle_guncelle(s, donem_id, asama, kod, g.alanlar, k)


@router.get("/smm/donemler/{donem_id}/sureler", response_model=SmmSureListesi, responses=HATA_404_422)
def sureler(s: OturumDep, donem_id: int, arama: str | None = None):
    return sa.sure_listesi(s, donem_id, arama)


@router.post("/smm/donemler/{donem_id}/sureler", response_model=SmmSure, status_code=201, responses=HATA_404_422)
def sure_ekle(s: OturumDep, donem_id: int, g: SmmSureGiris, k: str = Depends(kullanici_ver)):
    return sa.sure_ekle(s, donem_id, g.model_dump(), k)


@router.put("/smm/sureler/{sure_id}", response_model=SmmSure, responses=HATA_404_422)
def sure_guncelle(s: OturumDep, sure_id: int, g: SmmSureGiris, k: str = Depends(kullanici_ver)):
    return sa.sure_guncelle(s, sure_id, g.model_dump(), k)


@router.delete("/smm/sureler/{sure_id}", status_code=204, response_class=Response, responses=HATA_404_422)
def sure_sil(s: OturumDep, sure_id: int, k: str = Depends(kullanici_ver)):
    sa.sure_sil(s, sure_id, k)
    return Response(status_code=204)


# ---------------------------------------------------------------- aylık veri girişi ve kapanış
from ..servisler import smm_veri_servisi as sv  # noqa: E402
from ..servisler.hatalar import YetkiHatasi  # noqa: E402
from ..servisler.kimlik_servisi import YONETICI_ROL  # noqa: E402
from .bagimliliklar import GirisKullanicisiDep  # noqa: E402
from .semalar import (SmmAyarGiris, SmmDevirDurumu, SmmDevirYenileCikis, SmmDevirYenileGiris, SmmKilitCikis, SmmKilitGiris,  # noqa: E402
                      SmmVeriDurumu)
from .semalar import SmmKaynakOnizleme  # noqa: E402


@router.get("/smm/donemler/{donem_id}/veri", response_model=SmmVeriDurumu, responses=HATA_404_422)
def veri_durumu(s: OturumDep, donem_id: int):
    """Dönemin veri kontrol listesi: hangi kaynak yüklendi, hangisi eksik."""
    return sv.veri_durumu(s, donem_id)


@router.post("/smm/donemler/{donem_id}/veri/{kaynak}/onizle", response_model=SmmKaynakOnizleme, responses=HATA_404_409_422)
def veri_onizle(s: OturumDep, donem_id: int, kaynak: str, dosya: UploadFile = File(...)):
    """Yüklemeden önce: yeni / değişen / aynı / sıfırlanacak kalem, sorunlu satırlar (yazılmayacak), uyarılar. Hiçbir şey yazılmaz."""
    return sv.kaynak_onizle(s, donem_id, kaynak, dosya.file.read(ss.MAKS_BAYT + 1))


@router.post("/smm/donemler/{donem_id}/veri/{kaynak}", response_model=SmmVeriDurumu, responses=HATA_404_409_422)
def veri_yukle(s: OturumDep, donem_id: int, kaynak: str, dosya: UploadFile = File(...), onay: bool = Form(False),
               k: str = Depends(kullanici_ver)):
    """Tek bir veri kaynağını (alim, iade, uretim, sayim, sahit, gider_mizan, stok_mizan) dosyadan yükler; o kaynağın eski verisi yerine geçer.

    Okunabilen satır yoksa 422 `bos_dosya` (veri değişmez). Dosyadaki kayıt mevcut verinin yarısından azsa 409 `satir_kaybi_onayi`
    (`alanlar`: mevcut, yeni, silinecek); `onay=true` ile yazılır. Başka kaynağın / şablonun dosyası 422 `yanlis_kaynak` / `yanlis_sablon`."""
    return sv.kaynak_yukle(s, donem_id, kaynak, dosya.file.read(ss.MAKS_BAYT + 1), dosya.filename or "", k, onay=onay)


@router.get("/smm/donemler/{donem_id}/veri/{kaynak}/son-yukleme", response_model=SonYuklemeYaniti, responses=HATA_404_422)
def veri_son_yukleme(s: OturumDep, donem_id: int, kaynak: str):
    """Geri alınabilecek son yükleme (tarih, kişi, özet); yoksa `son: null`."""
    return sv.son_yukleme(s, donem_id, kaynak)


@router.post("/smm/donemler/{donem_id}/veri/{kaynak}/son-yuklemeyi-geri-al", response_model=GeriAlSonucu, responses=HATA_404_409_422)
def veri_geri_al(s: OturumDep, donem_id: int, kaynak: str, k: str = Depends(kullanici_ver)):
    """Kaynağın son yüklemesinden önceki hâlini geri yazar. Dönem kapalıysa 409 `donem_kilitli`; geri alınacak yükleme yoksa 404 `yedek_yok`."""
    return sv.son_yuklemeyi_geri_al(s, donem_id, kaynak, k)


@router.put("/smm/donemler/{donem_id}/ayarlar", response_model=SmmVeriDurumu, responses=HATA_404_409_422)
def ayarlar(s: OturumDep, donem_id: int, g: SmmAyarGiris, k: str = Depends(kullanici_ver)):
    """Finansman ve 720 / 730 gider tutarlarını elle girer."""
    return sv.ayarlar_guncelle(s, donem_id, g.finansman, g.gider_720, g.gider_730, k)


@router.put("/smm/donemler/{donem_id}/kilit", response_model=SmmKilitCikis, responses=HATA_404_409_422)
def kilit(s: OturumDep, donem_id: int, g: SmmKilitGiris, giren: GirisKullanicisiDep, k: str = Depends(kullanici_ver)):
    """Dönemi kapatır (kilitler) ya da kilidi açar.

    Kapatma: eksik kaynak, türü boş kalem ya da devir uyumsuzluğu varsa 409 `kapanis_eksik` (`alanlar.eksikler`); `zorla=true` ile kapatılır.
    Kilit açma: yalnız Genel Direktör (403; giriş zorunlu değilken serbest). Açılışı bu dönemden devralmış dönem kilitliyse 409
    `sonraki_kilitli`; kilitli değilse yanıtta `uyari`."""
    if giren is not None and not g.kilitli and giren.rol != YONETICI_ROL:   # giriş kapalıyken (testler, eski kurulum) denetim yok
        raise YetkiHatasi("dönem kilidini yalnız Genel Direktör açabilir", kod="kilit_acma_yetkisi")
    return sv.kilit(s, donem_id, g.kilitli, k, g.zorla)


@router.get("/smm/donemler/{donem_id}/devir-durumu", response_model=SmmDevirDurumu, responses=HATA_404_422)
def devir_durumu(s: OturumDep, donem_id: int):
    """Açılış stoku (dönem başı miktar / tutar) devralınan dönemin şu anki kapanışıyla aynı mı; farklı kalemlerin ilk 20'si."""
    return sd.devir_durumu(s, donem_id)


@router.post("/smm/donemler/{donem_id}/devir-yenile", response_model=SmmDevirYenileCikis, responses=HATA_404_409_422)
def devir_yenile(s: OturumDep, donem_id: int, g: SmmDevirYenileGiris, k: str = Depends(kullanici_ver)):
    """Açılış stokunu önceki dönemin güncel kapanışından yeniden yazar (neden zorunlu). Dönem kilitliyse 409. Elle girilmiş açılış
    değerleri korunur; `elle_ez=true` ile onlar da ezilir."""
    return sd.devir_yenile(s, donem_id, g.neden, g.elle_ez, k)


@router.get("/smm/donemler/{donem_id}/fis.xlsx", responses=HATA_404_422)
def fis_xlsx(s: OturumDep, donem_id: int):
    """SMM fişi taslağı ve SMM tablosu (.xlsx)."""
    from urllib.parse import quote
    icerik, ad = sv.fis_excel(s, donem_id)
    return Response(icerik, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(ad)}"})


# ---------------------------------------------------------------- müşavir Excel'i (kendi SMM Excel'i şablon, rakamlar uygulamadan)
from ..servisler import smm_musavir_excel_servisi as sme  # noqa: E402
from .semalar import SmmMusavirExcelDurumu, SmmMusavirSablonOnizleme  # noqa: E402


@router.get("/smm/donemler/{donem_id}/musavir-excel/durum", response_model=SmmMusavirExcelDurumu, responses=HATA_404_422)
def musavir_excel_durum(s: OturumDep, donem_id: int):
    """Müşavir Excel'i için kullanılacak şablon: dönemin kendi SMM Excel'i, yoksa en yakın önceki dönemin; hiç yoksa `sablon: null`."""
    return sme.durum(s, donem_id)


@router.get("/smm/donemler/{donem_id}/musavir-excel.xlsx", responses=HATA_404_422)
def musavir_excel(s: OturumDep, donem_id: int):
    """Müşavirin alıştığı SMM Excel'i: saklı şablon (kendi SMM Excel'iniz) formül ve biçimiyle, girdi hücrelerinde dönemin güncel
    verisi. Şablon yoksa 404 `sablon_yok`. Kapanmamış dönemde de iner; dosya özelliklerinde "TASLAK — dönem kapatılmadı" yazar.
    Uyarılar (formül olduğu için yazılamayan hücre, yetmeyen satır …) `X-Musavir-Uyarilar` başlığında (URL kodlu JSON listesi)."""
    import json
    from urllib.parse import quote
    icerik, ad, uyarilar = sme.smm_donem_excel_uret(s, donem_id)
    return Response(icerik, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(ad)}",
                             "X-Musavir-Uyarilar": quote(json.dumps(uyarilar[:30], ensure_ascii=False)),
                             "Access-Control-Expose-Headers": "Content-Disposition, X-Musavir-Uyarilar"})


@router.post("/smm/donemler/{donem_id}/musavir-excel/sablon/onizle", response_model=SmmMusavirSablonOnizleme, responses=HATA_404_422)
def musavir_sablon_onizle(s: OturumDep, donem_id: int, dosya: UploadFile = File(...)):
    """"Müşavir şablonu olarak yalnız sakla" önizlemesi (yazmaz): sayfa adları. SMM dönem Excel'i değilse 422 `smm_excel_degil`."""
    return sme.sablon_onizle(s, donem_id, dosya.file.read(ss.MAKS_BAYT + 1), dosya.filename or "")


@router.post("/smm/donemler/{donem_id}/musavir-excel/sablon", response_model=SmmMusavirExcelDurumu, responses=HATA_404_422)
def musavir_sablon_sakla(s: OturumDep, donem_id: int, dosya: UploadFile = File(...), k: str = Depends(kullanici_ver)):
    """Dönem verisine dokunmadan yalnız müşavir şablonunu saklar (dönemin önceki şablonunun yerine geçer). SMM Excel'i değilse 422."""
    return sme.sablon_sakla(s, donem_id, dosya.file.read(ss.MAKS_BAYT + 1), dosya.filename or "", k)
