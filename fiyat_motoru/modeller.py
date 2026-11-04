from dataclasses import dataclass, field
from decimal import Decimal
from .para import SIFIR


@dataclass(frozen=True)
class Malzeme:
    kod: str
    ad: str
    tip: str | None            # '0008-Ambalaj Malzeme' gibi
    birim: str | None          # 'AD', 'KG'
    para_birimi: str | None    # 'TL', 'USD', 'EUR', 'GBP', 'CHF', None
    fiyat: Decimal             # bütçe birim fiyatı, yoksa SIFIR
    zs: str | None             # 'Z' veya 'S' (Excel N sütunu), bilinmiyorsa None

    def __post_init__(self):
        """Sözleşme sınırında normalleştirme: boşluk kırpma, Z/S ve para birimi büyük harf."""
        ayarla = lambda ad, deger: object.__setattr__(self, ad, deger)
        ayarla("kod", self.kod.strip())
        ayarla("zs", self.zs.strip().upper() if self.zs else self.zs)
        ayarla("para_birimi", self.para_birimi.strip().upper() if self.para_birimi else self.para_birimi)
        ayarla("birim", self.birim.strip() if self.birim else self.birim)
        ayarla("tip", self.tip.strip() if self.tip else self.tip)


@dataclass(frozen=True)
class ReceteSatiri:
    malzeme_kodu: str
    ad: str
    miktar: Decimal            # net miktar (I sütunu)
    fire_orani: Decimal        # 0.02 gibi; yoksa SIFIR (J sütunu)
    birim: str | None
    dugum_tipi: str = "yaprak"  # 'yaprak' | 'ara_mamul' (fiyatsız olması bilinçli, uyarı verilmez)
    brut_miktar_elle: Decimal | None = None   # elle girilen brüt miktar; varsa fire kuralı atlanır
    birim_fiyat_elle: Decimal | None = None   # elle girilen birim fiyat; varsa fiyat listesi atlanır
    alt_satiri_var: bool = False   # reçete ağacında altında (daha derin seviyeli) satırlar var: maliyeti alt satırlardan gelir,
                                   # fiyat listesinde olmaması beklenir -> "fiyat listesinde yok" uyarısı verilmez (fiyat girilebilir)
    zs_elle: str | None = None     # Excel N sütununa elle yazılmış Z/S; varsa malzeme kartının Z/S'si yerine kullanılır
    para_birimi_elle: str | None = None   # Excel O sütununa elle yazılmış para birimi; varsa kartınkinin yerine kullanılır


@dataclass(frozen=True)
class Parametreler:
    enflasyon: Decimal                       # F148, 0.25
    kurlar: dict[str, Decimal]               # {'USD': 50, 'EUR': 60, 'GBP': 68, 'CHF': 63.29..}
    faiz_oranlari: dict[str, Decimal]        # {'TL': 0.40, 'USD': 0.06, 'EUR': 0.06}
    stok_sureleri_ay: dict[str, Decimal]     # {'TL': 6, 'USD': 6, 'EUR': 6}
    satis_kar_orani: Decimal                 # P137'deki 1.2 -> 0.20
    teklif_kar_oranlari: tuple[Decimal, ...] # (0.20, 0.17, 0.14)
    vardiya_saati: Decimal                   # 7.5 (Excel 27000 sn sabitini kullanır = 7.5*3600)


@dataclass(frozen=True)
class UretimBilgisi:
    pazar: str                       # 'Yurtiçi' | 'Yurtdışı' (P2)
    vardiya_uretim_adedi: Decimal    # E138
    dolum_personel: Decimal          # E140
    etiketleme_adedi: Decimal        # E141 (0 ise etiket işçiliği 0)
    etiket_personel: Decimal         # E143
    hat: str                         # E144 'Niko', 'Herbort', ...
    taze_tursu_sinifi: str           # E145 'Taze/Taze', 'Taze/Turşu', 'Turşu/Turşu'
    ambalaj_hacmi: Decimal           # E146 370, 720, 2.5 ...
    suzme_kg: Decimal                # E136
    mal_kabul_miktar_kg: Decimal     # I104 (Excel'de =K17 gibi bir satıra bağlı; burada girdi)
    mal_kabul_fire: Decimal          # J104, genelde SIFIR
    pazarlama_yonetim_uygula: bool   # 14 sayfada P118/P119 elle 0 -> False

    def __post_init__(self):
        if self.pazar not in ("Yurtiçi", "Yurtdışı"):
            raise ValueError(f"pazar 'Yurtiçi' veya 'Yurtdışı' olmalı: {self.pazar!r}")


@dataclass(frozen=True)
class AmbalajSinifi:
    ad: str
    hacim: Decimal
    uretim_adedi: Decimal
    katsayi: Decimal


@dataclass(frozen=True)
class GiderHavuzlari:
    """Gider Dağıtım sayfasının ham girdileri (toplamlar hesaplanmış TL değer olarak)."""
    dolum_iscilik_toplam: Decimal                                            # D4
    dolum_iscilik_saniye: Decimal                                            # F4
    mal_kabul_iscilik_toplam: Decimal                                        # A6
    mal_kabul_paylari: dict[str, tuple[Decimal, Decimal]]                   # sınıf -> (pay, kg)  C7:G9 / E7:E9
    etiket_iscilik_toplam: Decimal                                           # D13
    etiket_iscilik_saniye: Decimal                                           # F13
    endirekt_iscilik_toplam: Decimal                                         # D18
    endirekt_saniye: Decimal                                                 # F18
    mal_kabul_gug_toplam: Decimal                                            # A20
    mal_kabul_gug_paylari: dict[str, tuple[Decimal, Decimal]]               # C21:G23
    diger_gug_toplam: Decimal                                                # D27
    diger_gug_saniye: Decimal                                                # F27
    elektrik_toplam: Decimal                                                 # D38
    elektrik_hatlar: dict[str, tuple[Decimal, Decimal]]                     # hat -> (pay, saniye) A30:G37
    dogalgaz_toplam: Decimal                                                 # D49
    dogalgaz_hatlar: dict[str, tuple[Decimal, Decimal]]                     # A41:G48
    amortisman_toplam: Decimal                                               # D60
    amortisman_hatlar: dict[str, tuple[Decimal, Decimal]]                   # A52:G59
    yonetim_toplam: Decimal                                                  # D64
    pazarlama_toplam: Decimal                                                # D67
    ambalajlar: tuple[AmbalajSinifi, ...]                                    # A70:D91


@dataclass(frozen=True)
class GiderOranlari:
    """Havuzlardan türetilmiş birim oranlar (Gider Dağıtım'ın G/F sütunları)."""
    dolum_iscilik_sn: Decimal                      # G4
    etiket_iscilik_sn: Decimal                     # G13
    endirekt_iscilik_sn: Decimal                   # G18
    diger_gug_sn: Decimal                          # G27
    mal_kabul_iscilik_kg: dict[str, Decimal]       # F7:F9   (anahtar casefold)
    mal_kabul_gug_kg: dict[str, Decimal]           # F21:F23
    elektrik_sn: dict[str, Decimal]                # F30:F37 (anahtar casefold)
    dogalgaz_sn: dict[str, Decimal]                # F41:F48
    amortisman_sn: dict[str, Decimal]              # F52:F59
    pazarlama_adet: dict[Decimal, Decimal]         # hacim -> F70:F91
    yonetim_adet: dict[Decimal, Decimal]           # hacim -> G70:G91


# Gider satırlarının kararlı anahtarları (MaliyetSatiri.kod) ve Excel ürün sayfasındaki etiketleri (satır 104-113, 118-119).
GIDER_KALEMLERI = {
    "mal_kabul_iscilik": "Mal Kabul ve Fermantasyon Giderleri", "dolum_iscilik": "Dolum Doğrudan İşçilik Giderleri",
    "etiket_iscilik": "Etiketleme İşçilik Giderleri", "endirekt_iscilik": "Endirekt İşçilik Giderleri",
    "mal_kabul_gug": "Mal Kabul ve Fermantasyon Genel Üretim Giderleri", "elektrik": "Elektrik Giderleri",
    "dogalgaz": "Doğalgaz Giderleri", "amortisman": "Amortisman Giderleri", "diger_gug": "Diğer Genel Üretim Giderleri",
    "pazarlama": "PAZARLAMA SATIŞ GİDERLERİ", "yonetim": "GENEL YÖNETİM GİDERLERİ",
}
# Elle yazılabilen gider hücreleri: alan adı -> Excel sütunu.
GIDER_ELLE_ALANLARI = {"miktar": "I", "brut_miktar": "K", "birim_fiyat": "M", "tutar": "P"}


@dataclass(frozen=True)
class GiderElle:
    """Gider satırında formül yerine elle yazılan hücreler (Excel I/K/M/P). None olan hücre formülle hesaplanır;
    elle değer Excel'deki gibi sonraki hücrelere akar (I -> K -> P, M -> P)."""
    miktar: Decimal | None = None
    brut_miktar: Decimal | None = None
    birim_fiyat: Decimal | None = None
    tutar: Decimal | None = None

    def dolu_alanlar(self) -> tuple[str, ...]:
        return tuple(a for a in GIDER_ELLE_ALANLARI if getattr(self, a) is not None)


@dataclass(frozen=True)
class UrunGirdisi:
    kod: str
    ad: str
    recete: tuple[ReceteSatiri, ...]
    uretim: UretimBilgisi
    gider_elle: dict[str, GiderElle] = field(default_factory=dict)   # gider kalemi anahtarı -> elle yazılmış hücreler


@dataclass
class MaliyetSatiri:
    kalem: str                 # 'Cam Kavanoz 370 ml Boğumlu' veya 'Dolum Doğrudan İşçilik'
    grup: str                  # 'malzeme' | 'direkt_iscilik' | 'gug' | 'diger' | 'finansman'
    miktar: Decimal
    brut_miktar: Decimal
    birim_fiyat: Decimal
    tutar: Decimal
    maliyet_yuzdesi: Decimal = SIFIR     # R sütunu
    fiyat_yuzdesi: Decimal = SIFIR       # S sütunu
    kod: str = ""                        # kararlı satır anahtarı (malzeme kodu veya sabit gider anahtarı)
    tutar_firesiz: Decimal = SIFIR       # fire uygulanmamış tutar
    miktar_kaynagi: str = "fire"         # 'fire' | 'elle' | '-' (gider satırları)
    fiyat_kaynagi: str = "liste"         # 'liste' | 'elle' | '-' (gider satırları)
    elle_alanlar: tuple[str, ...] = ()   # gider satırı: elle yazılmış hücreler (GIDER_ELLE_ALANLARI anahtarları)


@dataclass
class MaliyetSonucu:
    urun_kodu: str
    satirlar: list[MaliyetSatiri]
    malzeme_toplami: Decimal            # P100
    direkt_iscilik_toplami: Decimal     # P103
    gug_toplami: Decimal                # P107
    uretim_gideri_toplami: Decimal      # P114
    toplam_birim_maliyet: Decimal       # P116
    pazarlama_gideri: Decimal           # P118
    yonetim_gideri: Decimal             # P119
    diger_giderler_toplami: Decimal     # P120
    giydirilmis_maliyet: Decimal        # P122
    finansman: dict[str, Decimal]       # {'TL': P124, 'USD': P125, 'EUR': P126, ...}
    finansman_dahil_maliyet_tl: Decimal # P130
    doviz_maliyet: dict[str, Decimal]   # {'USD': P131, 'EUR': P132, 'GBP': P133}
    satis_fiyati_tl: Decimal            # P137
    satis_fiyati_doviz: dict[str, Decimal]  # {'USD': P138, 'EUR': P139, ...}
    suzme_kg_fiyati_tl: Decimal         # P143
    teklifler_usd: list[Decimal]        # [P145, P146, P147]
    uyarilar: list[str] = field(default_factory=list)
    firesiz: "MaliyetSonucu | None" = None

    def satir(self, kod: str) -> MaliyetSatiri:
        """Koda göre ilk eşleşen maliyet satırı; yoksa KeyError."""
        for s in self.satirlar:
            if s.kod == kod:
                return s
        raise KeyError(kod)
