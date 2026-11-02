"""F4/F8: Gider Dağıtım sayfası. Havuz toplamlarını saniye, kg ve adet başına birim gidere çevirir."""
from decimal import Decimal
from .modeller import GiderHavuzlari, GiderOranlari
from .para import SIFIR


def anahtar(s: str) -> str:
    """Excel VLOOKUP büyük/küçük harfe duyarsızdır; 'Turşu/turşu' ile 'Turşu/Turşu' aynı anahtardır."""
    return (s or "").strip().casefold()


def _bol(pay: Decimal, payda: Decimal) -> Decimal:
    return SIFIR if payda == SIFIR else pay / payda


def _paylastir(toplam: Decimal, paylar: dict[str, tuple[Decimal, Decimal]]) -> dict[str, Decimal]:
    # her satır: toplam * pay% / baz(kg veya saniye)
    sonuc: dict[str, Decimal] = {}
    for k, (pay, baz) in paylar.items():
        a = anahtar(k)
        if a in sonuc:
            raise ValueError(f"dağıtım anahtarı tekrarı: {a}")
        sonuc[a] = _bol(toplam * pay, baz)
    return sonuc


def oranlari_hesapla(h: GiderHavuzlari) -> GiderOranlari:
    hacimler = [a.hacim for a in h.ambalajlar]
    for hacim in hacimler:
        if hacimler.count(hacim) > 1:
            raise ValueError(f"ambalaj hacim tekrarı: {hacim}")
    agirlikli_adet = sum((a.uretim_adedi * a.katsayi for a in h.ambalajlar), SIFIR)
    paz_birim = _bol(h.pazarlama_toplam, agirlikli_adet)
    yon_birim = _bol(h.yonetim_toplam, agirlikli_adet)
    return GiderOranlari(
        dolum_iscilik_sn=_bol(h.dolum_iscilik_toplam, h.dolum_iscilik_saniye),
        etiket_iscilik_sn=_bol(h.etiket_iscilik_toplam, h.etiket_iscilik_saniye),
        endirekt_iscilik_sn=_bol(h.endirekt_iscilik_toplam, h.endirekt_saniye),
        diger_gug_sn=_bol(h.diger_gug_toplam, h.diger_gug_saniye),
        mal_kabul_iscilik_kg=_paylastir(h.mal_kabul_iscilik_toplam, h.mal_kabul_paylari),
        mal_kabul_gug_kg=_paylastir(h.mal_kabul_gug_toplam, h.mal_kabul_gug_paylari),
        elektrik_sn=_paylastir(h.elektrik_toplam, h.elektrik_hatlar),
        dogalgaz_sn=_paylastir(h.dogalgaz_toplam, h.dogalgaz_hatlar),
        amortisman_sn=_paylastir(h.amortisman_toplam, h.amortisman_hatlar),
        pazarlama_adet={a.hacim: paz_birim * a.katsayi for a in h.ambalajlar},
        yonetim_adet={a.hacim: yon_birim * a.katsayi for a in h.ambalajlar},
    )
