"""ORM tabloları. Para/oran alanları ParaTipi; fiyat, parametre değeri ve fire kuralı append-only."""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .veritabani import Base, ParaTipi


class Ortak:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    olusturma_zamani: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    olusturan: Mapped[str] = mapped_column(String(64), default="sistem")


class Sezon(Base, Ortak):
    __tablename__ = "sezon"
    ad: Mapped[str] = mapped_column(String(32), unique=True)
    baslangic: Mapped[date] = mapped_column(Date)
    bitis: Mapped[date] = mapped_column(Date)


class Senaryo(Base, Ortak):
    __tablename__ = "senaryo"
    sezon_id: Mapped[int] = mapped_column(ForeignKey("sezon.id"))
    tur: Mapped[str] = mapped_column(String(20))            # fiyat_calismasi | gerceklesen
    ad: Mapped[str] = mapped_column(String(100))
    aciklama: Mapped[str | None] = mapped_column(String(500))
    kilitli: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")   # True: yazma uçları 409 (kilit-aç hariç)
    kaynak_dosya: Mapped[str | None] = mapped_column(String(200))                       # import/aktarımda yüklenen son dosya adı
    sezon: Mapped[Sezon] = relationship()


class Parametre(Base, Ortak):
    __tablename__ = "parametre"
    anahtar: Mapped[str] = mapped_column(String(64), unique=True)
    aciklama: Mapped[str | None] = mapped_column(String(200))
    birim: Mapped[str | None] = mapped_column(String(16))


class ParametreDegeri(Base, Ortak):
    __tablename__ = "parametre_degeri"
    parametre_id: Mapped[int] = mapped_column(ForeignKey("parametre.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    kapsam_tipi: Mapped[str] = mapped_column(String(8), default="genel")   # genel | urun
    kapsam_id: Mapped[int | None] = mapped_column(Integer)
    deger: Mapped[Decimal] = mapped_column(ParaTipi)
    gecerlilik_basi: Mapped[date] = mapped_column(Date)
    neden: Mapped[str | None] = mapped_column(String(300))
    parametre: Mapped[Parametre] = relationship()


class Malzeme(Base, Ortak):
    __tablename__ = "malzeme"
    kod: Mapped[str] = mapped_column(String(32), unique=True)
    ad: Mapped[str] = mapped_column(String(200))
    tip: Mapped[str | None] = mapped_column(String(64))
    birim: Mapped[str | None] = mapped_column(String(8))
    para_birimi: Mapped[str | None] = mapped_column(String(4))
    zs: Mapped[str | None] = mapped_column(String(1))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)


class MalzemeFiyati(Base, Ortak):
    __tablename__ = "malzeme_fiyati"
    malzeme_id: Mapped[int] = mapped_column(ForeignKey("malzeme.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    fiyat: Mapped[Decimal] = mapped_column(ParaTipi)
    para_birimi: Mapped[str | None] = mapped_column(String(4))
    gecerlilik_basi: Mapped[date] = mapped_column(Date)
    kaynak: Mapped[str] = mapped_column(String(16), default="elle")
    neden: Mapped[str | None] = mapped_column(String(300))
    malzeme: Mapped[Malzeme] = relationship()


class GiderHavuzu(Base, Ortak):
    __tablename__ = "gider_havuzu"
    __table_args__ = (UniqueConstraint("senaryo_id", "kod"),)
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    kod: Mapped[str] = mapped_column(String(64))
    ad: Mapped[str] = mapped_column(String(200))
    toplam_tutar: Mapped[Decimal] = mapped_column(ParaTipi)
    baz_tipi: Mapped[str] = mapped_column(String(8))         # saniye | kg | adet
    baz_miktar: Mapped[Decimal | None] = mapped_column(ParaTipi)
    taban_tutar: Mapped[Decimal | None] = mapped_column(ParaTipi)   # doluysa toplam_tutar = taban_tutar × Π çarpan (sunucu hesaplar)
    carpanlar: Mapped[list | None] = mapped_column(JSON)            # [{"ad": "SGK", "deger": "1.35"}, ...]; değerler Decimal metni
    anahtarlar: Mapped[list["DagitimAnahtari"]] = relationship(cascade="all, delete-orphan")


class DagitimAnahtari(Base, Ortak):
    __tablename__ = "dagitim_anahtari"
    gider_havuzu_id: Mapped[int] = mapped_column(ForeignKey("gider_havuzu.id"))
    alt_kalem: Mapped[str] = mapped_column(String(100))
    pay_orani: Mapped[Decimal] = mapped_column(ParaTipi)
    baz_miktar: Mapped[Decimal] = mapped_column(ParaTipi)


class AmbalajSinifi(Base, Ortak):
    __tablename__ = "ambalaj_sinifi"
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    ad: Mapped[str] = mapped_column(String(100))
    hacim: Mapped[Decimal] = mapped_column(ParaTipi)
    uretim_adedi: Mapped[Decimal] = mapped_column(ParaTipi)
    katsayi: Mapped[Decimal] = mapped_column(ParaTipi)


class Urun(Base, Ortak):
    __tablename__ = "urun"
    kod: Mapped[str] = mapped_column(String(32), unique=True)
    ad: Mapped[str] = mapped_column(String(200))
    ambalaj_hacmi: Mapped[Decimal] = mapped_column(ParaTipi)
    hat: Mapped[str | None] = mapped_column(String(64))
    taze_tursu_sinifi: Mapped[str | None] = mapped_column(String(64))
    suzme_kg: Mapped[Decimal] = mapped_column(ParaTipi)
    pazar: Mapped[str] = mapped_column(String(32), default="Yurtiçi")
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    gecici_kod: Mapped[bool] = mapped_column(Boolean, default=False)   # True: ERP kodu yok, SAYFA-<ad> geçici kodu
    aile: Mapped[str | None] = mapped_column(String(120))   # ürün ailesi (aynı ürün, farklı ambalaj); boşsa addan türetilir (servisler/aile.py)
    aile_ad: Mapped[str | None] = mapped_column(String(120))   # elle yazılan görünen aile adı; boşsa addan türetilir (anahtar `aile` ile eşleşir)
    marka: Mapped[str | None] = mapped_column(String(64))   # "Berrak" -> liste fiyatı uygulanır; NULL: bilinmiyor (açılışta addan türetilir), "": bilerek boş


class UretimHedefi(Base, Ortak):
    __tablename__ = "uretim_hedefi"
    __table_args__ = (UniqueConstraint("urun_id", "senaryo_id"),)
    urun_id: Mapped[int] = mapped_column(ForeignKey("urun.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    vardiya_uretim_adedi: Mapped[Decimal] = mapped_column(ParaTipi)
    dolum_personel: Mapped[Decimal] = mapped_column(ParaTipi)
    etiketleme_adedi: Mapped[Decimal] = mapped_column(ParaTipi)
    etiket_personel: Mapped[Decimal] = mapped_column(ParaTipi)
    mal_kabul_miktar_kg: Mapped[Decimal] = mapped_column(ParaTipi)
    mal_kabul_fire: Mapped[Decimal] = mapped_column(ParaTipi)
    pazarlama_yonetim_uygula: Mapped[bool] = mapped_column(Boolean, default=True)
    # Gider satırlarında formül yerine elle yazılmış hücreler: {"dolum_iscilik": {"tutar": "20"}, ...}; değerler Decimal metni.
    gider_elle: Mapped[dict | None] = mapped_column(JSON)


class Recete(Base, Ortak):
    __tablename__ = "recete"
    __table_args__ = (UniqueConstraint("urun_id", "senaryo_id", "versiyon"),)
    urun_id: Mapped[int] = mapped_column(ForeignKey("urun.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    versiyon: Mapped[int] = mapped_column(Integer)
    kaynak: Mapped[str | None] = mapped_column(String(16))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    neden: Mapped[str | None] = mapped_column(String(300))   # elle/ekrandan açılan sürümün nedeni (günlükte görünür); Excel aktarımında boş
    satirlar: Mapped[list["ReceteSatiri"]] = relationship(order_by="ReceteSatiri.sira", cascade="all, delete-orphan")


class ReceteSatiri(Base, Ortak):
    __tablename__ = "recete_satiri"
    recete_id: Mapped[int] = mapped_column(ForeignKey("recete.id"))
    sira: Mapped[int] = mapped_column(Integer)
    malzeme_kodu: Mapped[str] = mapped_column(String(32))   # bilerek string: ara mamul kodları fiyat listesinde olmayabilir
    ad: Mapped[str | None] = mapped_column(String(200))
    miktar: Mapped[Decimal] = mapped_column(ParaTipi)
    birim: Mapped[str | None] = mapped_column(String(8))
    fire_override: Mapped[Decimal | None] = mapped_column(ParaTipi)
    dugum_tipi: Mapped[str] = mapped_column(String(16), default="yaprak")
    brut_miktar_elle: Mapped[Decimal | None] = mapped_column(ParaTipi)   # elle girilen brüt miktar; varsa fire kuralı atlanır
    birim_fiyat_elle: Mapped[Decimal | None] = mapped_column(ParaTipi)   # elle girilen birim fiyat; varsa fiyat listesi atlanır
    seviye: Mapped[int | None] = mapped_column(Integer)                  # Excel A sütunu (0-3); yalnız gösterim/hiyerarşi, hesaba girmez
    zs_elle: Mapped[str | None] = mapped_column(String(1))               # elle Z/S (Excel N); varsa malzeme kartınınkinin yerine
    para_birimi_elle: Mapped[str | None] = mapped_column(String(8))      # elle para birimi (Excel O); varsa kartınkinin yerine


class FireKurali(Base, Ortak):
    __tablename__ = "fire_kurali"
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    kapsam_tipi: Mapped[str] = mapped_column(String(8))     # tip | grup | malzeme
    kapsam_deger: Mapped[str] = mapped_column(String(64))
    oran: Mapped[Decimal] = mapped_column(ParaTipi)
    oncelik: Mapped[int] = mapped_column(Integer)
    gecerlilik_basi: Mapped[date] = mapped_column(Date)
    neden: Mapped[str | None] = mapped_column(String(300))


class MalzemeGrubu(Base, Ortak):
    __tablename__ = "malzeme_grubu"
    ad: Mapped[str] = mapped_column(String(100), unique=True)
    uyeler: Mapped[list["MalzemeGrubuUyesi"]] = relationship(cascade="all, delete-orphan")


class MalzemeGrubuUyesi(Base, Ortak):
    __tablename__ = "malzeme_grubu_uyesi"
    grup_id: Mapped[int] = mapped_column(ForeignKey("malzeme_grubu.id"))
    malzeme_kodu: Mapped[str] = mapped_column(String(32))


class MaliyetHesabi(Base, Ortak):
    __tablename__ = "maliyet_hesabi"
    urun_id: Mapped[int] = mapped_column(ForeignKey("urun.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    hesap_tarihi: Mapped[date] = mapped_column(Date)
    girdi_snapshot: Mapped[dict] = mapped_column(JSON)
    sonuc_snapshot: Mapped[dict] = mapped_column(JSON)
    uyarilar: Mapped[list] = mapped_column(JSON)


class Teklif(Base, Ortak):
    __tablename__ = "teklif"
    maliyet_hesabi_id: Mapped[int] = mapped_column(ForeignKey("maliyet_hesabi.id"))
    tur_no: Mapped[int] = mapped_column(Integer)
    kar_orani: Mapped[Decimal] = mapped_column(ParaTipi)
    fiyat_tl: Mapped[Decimal] = mapped_column(ParaTipi)
    fiyat_usd: Mapped[Decimal | None] = mapped_column(ParaTipi)
    fiyat_eur: Mapped[Decimal | None] = mapped_column(ParaTipi)
    musteri: Mapped[str | None] = mapped_column(String(200))
    durum: Mapped[str] = mapped_column(String(16), default="taslak")
    notu: Mapped[str | None] = mapped_column(String(500))   # `not` Python'da ayrılmış kelime


class SatisGecmisi(Base, Ortak):
    __tablename__ = "satis_gecmisi"
    urun_id: Mapped[int] = mapped_column(ForeignKey("urun.id"))
    musteri: Mapped[str] = mapped_column(String(200))
    tarih: Mapped[date] = mapped_column(Date)
    fiyat: Mapped[Decimal] = mapped_column(ParaTipi)
    para_birimi: Mapped[str] = mapped_column(String(4))
    adet: Mapped[Decimal] = mapped_column(ParaTipi)


class ListeFiyati(Base, Ortak):
    """Ürünün bir yıldaki, bir pazardaki (yurtici | yurtdisi) liste fiyatı (TL, KDV hariç) ve isteğe bağlı o yılki birim maliyeti. ornek=True: gerçek veri gelene kadar
    üretilmiş tahmini satır (ekranda etiketlenir, tek tıkla silinir)."""
    __tablename__ = "liste_fiyati"
    __table_args__ = (UniqueConstraint("urun_id", "yil", "pazar"),)
    urun_id: Mapped[int] = mapped_column(ForeignKey("urun.id"))
    yil: Mapped[int] = mapped_column(Integer)
    pazar: Mapped[str] = mapped_column(String(8), default="yurtici", server_default="yurtici")   # yurtici | yurtdisi
    liste_fiyati: Mapped[Decimal] = mapped_column(ParaTipi)
    birim_maliyet: Mapped[Decimal | None] = mapped_column(ParaTipi)
    bolen: Mapped[Decimal | None] = mapped_column(ParaTipi)   # kaydedildiği andaki pazar böleni (izlenebilirlik); eski kayıtlarda boş
    ornek: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class StokDevri(Base, Ortak):
    """Fiyat çalışmasında ürünün geçen yıldan stokta kalan miktarı ve birim maliyeti (çalışmaya bağlı; çalışma kopyalanırken taşınmaz).
    enflasyon ve uretim_adedi elle girilirse kullanılır; boşsa çalışmanın `enflasyon` parametresi / geçen yıl satış adedi - stok.
    Değişiklikler DegisiklikKaydi'na (tablo="stok_devri") yazılır."""
    __tablename__ = "stok_devri"
    __table_args__ = (UniqueConstraint("urun_id", "senaryo_id"),)
    urun_id: Mapped[int] = mapped_column(ForeignKey("urun.id"))
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    adet: Mapped[Decimal] = mapped_column(ParaTipi)
    birim_maliyet: Mapped[Decimal | None] = mapped_column(ParaTipi)   # TL; adet 0 iken boş olabilir
    enflasyon: Mapped[Decimal | None] = mapped_column(ParaTipi)       # elle; 0,40 = %40
    uretim_adedi: Mapped[Decimal | None] = mapped_column(ParaTipi)    # elle; bu yıl üretilecek adet


class DegisiklikKaydi(Base, Ortak):
    __tablename__ = "degisiklik_kaydi"
    tablo: Mapped[str] = mapped_column(String(64))
    kayit_id: Mapped[int] = mapped_column(Integer)
    islem: Mapped[str] = mapped_column(String(16))
    eski: Mapped[dict | None] = mapped_column(JSON)
    yeni: Mapped[dict | None] = mapped_column(JSON)
    kullanici: Mapped[str] = mapped_column(String(64), default="sistem")
    zaman: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class MetinParametre(Base, Ortak):
    """Metin değerli parametre (ör. satış fiyatı notu). ParametreDegeri ParaTipi olduğundan ayrı tablo; append-only."""
    __tablename__ = "metin_parametre"
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    anahtar: Mapped[str] = mapped_column(String(64))
    deger: Mapped[str] = mapped_column(String(1000))
    gecerlilik_basi: Mapped[date] = mapped_column(Date)
    neden: Mapped[str | None] = mapped_column(String(300))


class UretimKapasitesi(Base, Ortak):
    """Excel `Üretim Adetleri` sayfası: ürün başına vardiyalık kapasite/hedef. Değişiklikler DegisiklikKaydi'na yazılır."""
    __tablename__ = "uretim_kapasitesi"
    __table_args__ = (UniqueConstraint("senaryo_id", "urun_kodu"),)
    senaryo_id: Mapped[int] = mapped_column(ForeignKey("senaryo.id"))
    urun_kodu: Mapped[str] = mapped_column(String(32))
    urun_ad: Mapped[str | None] = mapped_column(String(200))
    net_kapasite: Mapped[Decimal] = mapped_column(ParaTipi)
    net_sure: Mapped[Decimal] = mapped_column(ParaTipi)
    toplam_kapasite: Mapped[Decimal] = mapped_column(ParaTipi)
    toplam_sure: Mapped[Decimal] = mapped_column(ParaTipi)
    hedef_uretim: Mapped[Decimal] = mapped_column(ParaTipi)
    ortalama_isci: Mapped[Decimal] = mapped_column(ParaTipi)


class Kullanici(Base, Ortak):
    """Uygulamaya giriş yapan kişi. Şifre yalnız karma olarak (servisler/kimlik_servisi.sifre_karma) saklanır."""
    __tablename__ = "kullanici"
    kullanici_adi: Mapped[str] = mapped_column(String(64), unique=True)   # giriş adı; küçük harf; değişiklik kayıtlarına bu yazılır
    ad: Mapped[str] = mapped_column(String(120))                           # görünen ad
    sifre_karma: Mapped[str] = mapped_column(String(300))
    rol: Mapped[str] = mapped_column(String(20))                           # genel_direktor | muhasebe | satin_alma | izleyici
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    sifre_degismeli: Mapped[bool] = mapped_column(Boolean, default=True)   # geçici şifre: ilk girişte kendi şifresini belirler
    hatali_deneme: Mapped[int] = mapped_column(Integer, default=0)
    kilit_bitis: Mapped[datetime | None] = mapped_column(DateTime)         # art arda hatalı denemeden sonra (UTC)
    son_giris: Mapped[datetime | None] = mapped_column(DateTime)


class GirisOturumu(Base, Ortak):
    """Açık oturum: tarayıcıdaki çerez belirtecinin karması. Çıkışta, pasifleştirmede ya da şifre sıfırlamada kapanır."""
    __tablename__ = "giris_oturumu"
    belirtec_karma: Mapped[str] = mapped_column(String(64), unique=True)
    kullanici_id: Mapped[int] = mapped_column(ForeignKey("kullanici.id"))
    acik: Mapped[bool] = mapped_column(Boolean, default=True)
    son_kullanim: Mapped[datetime | None] = mapped_column(DateTime)
    kullanici: Mapped[Kullanici] = relationship()


# ---------------------------------------------------------------- Maliyet muhasebesi (SMM)
class SmmDonem(Base, Ortak):
    """Bir aylık SMM çalışması (ör. Eylül 2026). Veriler SMM Excel'inden yüklenir; yeniden yükleme dönemin kalemlerini baştan yazar.
    `finansman`: alımlara dağıtılacak finansman tutarı (Excel TABLO!J1). `excel_kontrol`: yüklenen Excel'in kendi hesabıyla karşılaştırma."""
    __tablename__ = "smm_donem"
    __table_args__ = (UniqueConstraint("yil", "ay"),)
    yil: Mapped[int] = mapped_column(Integer)
    ay: Mapped[int] = mapped_column(Integer)
    kaynak_dosya: Mapped[str | None] = mapped_column(String(200))
    finansman: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    excel_kontrol: Mapped[dict | None] = mapped_column(JSON)
    # Aşama maliyeti (20/40/50): dağıtılacak işçilik/GÜG havuzları (Excel aşama sayfalarının 1. satırı; ekrandan değiştirilebilir),
    # Excel'deki ilk değerleri, gider mizanı (720/730 bakiyesi) ve Excel'in kendi hesapladığı aşama birim maliyetleri (karşılaştırma için).
    dagitim: Mapped[dict | None] = mapped_column(JSON)
    dagitim_excel: Mapped[dict | None] = mapped_column(JSON)
    gider_mizan: Mapped[dict | None] = mapped_column(JSON)
    excel_asama: Mapped[dict | None] = mapped_column(JSON)
    # Aşama sayfalarında ürün satırına elle yazılmış değerler: {"40": {kod: {"gug_sn": "0"}}, "50": {kod: {"sure": "123"}}}
    asama_elle: Mapped[dict | None] = mapped_column(JSON)
    # SMM özeti için Excel'den: {"dss": {kod: tutar}, "stok_mizan": [{hesap, ad, bakiye}], "gider_mizan": {hesap: bakiye}, "mizan_tarihi": "…"}
    excel_ozet: Mapped[dict | None] = mapped_column(JSON)
    # Aşama hesabının reçete kaynağı: 'excel' (dönemle yüklenen SMM Excel'inin 20/40/50 sayfaları) ya da 'ana' (kalıcı Canias reçeteleri)
    recete_kaynagi: Mapped[str] = mapped_column(String(10), default="excel", server_default="excel")
    # Dönem başı stok önceki dönemden devredildiyse o dönemin id'si
    devir_donem_id: Mapped[int | None] = mapped_column(Integer)
    # Aylık veri kaynaklarının son yüklemesi: {"alim": {"dosya", "zaman", "kullanici", "satir"}, "sayim": {...}, ...}
    veri_kaynaklari: Mapped[dict | None] = mapped_column(JSON)
    # Kapanış: kilitli dönemde hiçbir veri ve hesap ayarı değiştirilemez
    kilitli: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    kilitleyen: Mapped[str | None] = mapped_column(String(64))


class SmmKalem(Base, Ortak):
    """Dönemde bir stok kartının hareketleri: dönem başı (DBS), dönem içi alım (HM-YM ALIŞ SATIŞ), iade, üretim ve sayım (DSS)."""
    __tablename__ = "smm_kalem"
    __table_args__ = (UniqueConstraint("donem_id", "kod"),)
    donem_id: Mapped[int] = mapped_column(ForeignKey("smm_donem.id"))
    kod: Mapped[str] = mapped_column(String(40))
    ad: Mapped[str | None] = mapped_column(String(200))
    birim: Mapped[str | None] = mapped_column(String(16))
    tur: Mapped[str | None] = mapped_column(String(60))          # mizan adı: 0001-Hammadde, 0002-Üretim Yarı Mamul…
    mizan_kodu: Mapped[str | None] = mapped_column(String(30))   # 150.01.001, 151.04.002…
    dbs_miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    dbs_tutar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    alim_miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    alim_tutar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    iade_miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    iade_tutar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    uretim_miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    sayim_miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    envanterde: Mapped[bool] = mapped_column(Boolean, default=True)   # ENVANTER sayfasında kartı var mı (aşama fiyatı yalnız oradan okunur)
    # ENVANTER!P (üretim birim fiyatı) hangi aşama sayfasından okunuyor: 20 / 40 / 50 (kartın türüne göre Excel'de satır satır yazılmış)
    uretim_asamasi: Mapped[int | None] = mapped_column(Integer)
    satis_miktar: Mapped[Decimal | None] = mapped_column(ParaTipi)   # dönem içi HM/YM satışı (HM-YM ALIŞ SATIŞ, tür 'Satış' satırları)
    sahit_miktar: Mapped[Decimal | None] = mapped_column(ParaTipi)   # şahit numune (ŞAHİT!J; sayıma dahil değil)


class SmmReceteSatiri(Base, Ortak):
    """Aşama reçetesi satırı (20 sebze kabul / 40 üretim hattı / 50 etiketleme): ana ürün başına malzeme miktarı ve fire oranı."""
    __tablename__ = "smm_recete_satiri"
    donem_id: Mapped[int] = mapped_column(ForeignKey("smm_donem.id"))
    asama: Mapped[int] = mapped_column(Integer)
    ana_kod: Mapped[str] = mapped_column(String(40))
    ana_ad: Mapped[str | None] = mapped_column(String(200))
    ana_miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(1))
    ana_birim: Mapped[str | None] = mapped_column(String(16))
    malzeme_kod: Mapped[str] = mapped_column(String(40))
    malzeme_ad: Mapped[str | None] = mapped_column(String(200))
    miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    birim: Mapped[str | None] = mapped_column(String(16))
    fire_orani: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    # Excel'de bu satırın formülü sayfanın standart formülünden farklıysa: {"carpan": "1"} (elle çarpan), {"hm": "0"} / {"ym": "0"}
    # (elle ya da standart dışı formüllü fiyat; Excel'in hesapladığı değer), {"hm_bolen": "800"} (standart fiyat / 800, ör. rulodan metreye).
    ozel: Mapped[dict | None] = mapped_column(JSON)


class SmmIscilik(Base, Ortak):
    """Üretim süreleri (Excel '51' sayfası): vardiya üretimi ve adet başına dolum/etiket saniyesi; işçilik ve GÜG dağıtımında kullanılır."""
    __tablename__ = "smm_iscilik"
    donem_id: Mapped[int] = mapped_column(ForeignKey("smm_donem.id"))
    kod: Mapped[str] = mapped_column(String(40))
    mamul_kod: Mapped[str | None] = mapped_column(String(40))        # 51!B: 50 aşaması (etiketleme) bununla arar
    yari_mamul_kod: Mapped[str | None] = mapped_column(String(40))   # 51!C: 40 aşaması (üretim hattı) bununla arar
    ad: Mapped[str | None] = mapped_column(String(200))
    vardiya_uretim: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    dolum_isci: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    etiket_isci: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    dolum_sn: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    dolum_adam_sn: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    etiket_sn: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    etiket_adam_sn: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))


class SmmAnaRecete(Base, Ortak):
    """Kalıcı üretim reçetesi (Canias ürün ağacı dökümü; dönemden bağımsız). Bir ürünün birden çok alternatifi olabilir ('00' ana).
    `asama` koddan: 02 -> 40, 03 -> 50, diğerleri (01, 11-19) -> 20. `fire_orani` oran (Canias'taki %33,33 -> 0,3333)."""
    __tablename__ = "smm_ana_recete"
    ana_kod: Mapped[str] = mapped_column(String(40), index=True)
    ana_ad: Mapped[str | None] = mapped_column(String(200))
    alternatif: Mapped[str] = mapped_column(String(8), default="00")
    satir_no: Mapped[int] = mapped_column(Integer, default=0)
    kalem_tipi: Mapped[int | None] = mapped_column(Integer)
    asama: Mapped[int] = mapped_column(Integer)
    malzeme_kod: Mapped[str] = mapped_column(String(40))
    malzeme_ad: Mapped[str | None] = mapped_column(String(200))
    miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    birim: Mapped[str | None] = mapped_column(String(16))
    fire_orani: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))


class SmmCaniasRecete(Base, Ortak):
    """Son yüklenen Canias dökümünün değiştirilmemiş kopyası (SmmAnaRecete ile aynı alanlar). Elle değiştirilmiş bir ürünü
    'Canias'a döndürmek' ve yeniden yüklemede farkı göstermek için."""
    __tablename__ = "smm_canias_recete"
    ana_kod: Mapped[str] = mapped_column(String(40), index=True)
    ana_ad: Mapped[str | None] = mapped_column(String(200))
    alternatif: Mapped[str] = mapped_column(String(8), default="00")
    satir_no: Mapped[int] = mapped_column(Integer, default=0)
    kalem_tipi: Mapped[int | None] = mapped_column(Integer)
    asama: Mapped[int] = mapped_column(Integer)
    malzeme_kod: Mapped[str] = mapped_column(String(40))
    malzeme_ad: Mapped[str | None] = mapped_column(String(200))
    miktar: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))
    birim: Mapped[str | None] = mapped_column(String(16))
    fire_orani: Mapped[Decimal] = mapped_column(ParaTipi, default=Decimal(0))


class SmmReceteElle(Base, Ortak):
    """Reçetesi uygulamada elle değiştirilmiş (ya da elle açılmış) ürün. Canias dökümü yeniden yüklenince bu ürünlerin reçetesi korunur."""
    __tablename__ = "smm_recete_elle"
    ana_kod: Mapped[str] = mapped_column(String(40), unique=True)
    son_degistiren: Mapped[str] = mapped_column(String(64), default="sistem")


class SmmReceteYukleme(Base, Ortak):
    """Kalıcı reçetelerin son yüklemesi (kaynak dosya, satır ve ürün sayısı); yükleme tüm reçeteleri baştan yazar."""
    __tablename__ = "smm_recete_yukleme"
    kaynak_dosya: Mapped[str | None] = mapped_column(String(200))
    satir_sayisi: Mapped[int] = mapped_column(Integer, default=0)
    urun_sayisi: Mapped[int] = mapped_column(Integer, default=0)


class YuklemeYedegi(Base, Ortak):
    """Excel yüklemesinden ÖNCEKİ verinin JSON kopyası ("son yüklemeyi geri al"). `alan`: yükleme noktası
    (ör. "satin_alma_fiyat", "smm_kaynak:alim_satis"); `kapsam`: senaryo/dönem kimliği metni. Geri yükleme alana özel servistedir."""
    __tablename__ = "yukleme_yedegi"
    alan: Mapped[str] = mapped_column(String(64), index=True)
    kapsam: Mapped[str] = mapped_column(String(64), default="")
    ozet: Mapped[str] = mapped_column(String(300), default="")
    kaynak_dosya: Mapped[str | None] = mapped_column(String(200))
    veri: Mapped[dict] = mapped_column(JSON)
    geri_alindi: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class ExcelSablonu(Base, Ortak):
    """Müşavir Excel'i için şablon: muhasebenin yüklediği kendi Excel'inin olduğu gibi kopyası. `tur`: "fiyat_kitabi" | "smm_donem";
    `kapsam`: senaryo/dönem kimliği metni. Kapsam başına yalnız en son yüklenen tutulur. Uygulama dışa aktarırken bu kopyaya
    güncel rakamları yazar; formül, biçim ve sayfa adlarına dokunmaz."""
    __tablename__ = "excel_sablonu"
    tur: Mapped[str] = mapped_column(String(32), index=True)
    kapsam: Mapped[str] = mapped_column(String(64), default="")
    dosya_adi: Mapped[str] = mapped_column(String(200))
    boyut: Mapped[int] = mapped_column(Integer, default=0)
    icerik: Mapped[bytes] = mapped_column(LargeBinary)


class SmmAlternatifSecimi(Base, Ortak):
    """Ürün için hesapta kullanılacak reçete alternatifi (yoksa '00')."""
    __tablename__ = "smm_alternatif_secimi"
    ana_kod: Mapped[str] = mapped_column(String(40), unique=True)
    alternatif: Mapped[str] = mapped_column(String(8))
