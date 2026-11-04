"""ORM tabloları. Para/oran alanları ParaTipi; fiyat, parametre değeri ve fire kuralı append-only."""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
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
