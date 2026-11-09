import type { DashboardSatiri } from "@/api/tipler";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";

/** Dört bölge: üretim adedi eşiği (medyan) × kâr oranı eşiği (hedef `satis_kar`, yoksa medyan). */
export type Bolge = "guclu" | "risk" | "nis" | "zayif";

export const BOLGE_ADI: Record<Bolge, string> = {
  guclu: "Çok satan, kârlı",
  risk: "Çok satan, marjı zayıf",
  nis: "Az satan, kârlı",
  zayif: "Az satan, marjı zayıf",
};

/**
 * Kârın hangi satış fiyatıyla ölçüleceği. `hesap` = fiyat çalışmasının satış fiyatı (maliyet × (1 + hedef kâr)); bütçede her ürün
 * tanım gereği eşiğin üstünde çıkar. `gecen_yil` = Satış Geçmişi'nden gelen geçen yılın adet ağırlıklı gerçek satış fiyatı
 * (dashboard `gecen_yil_tl`): gerçek kârlılığı gösterir.
 */
export type FiyatKaynagi = "hesap" | "gecen_yil";

export const FIYAT_KAYNAGI_ADI: Record<FiyatKaynagi, string> = {
  hesap: "Hesaplanan satış fiyatı",
  gecen_yil: "Geçen yıl gerçek satış fiyatı",
};

export interface KarlilikNoktasi {
  kod: string;
  ad: string;
  hat: string;
  adet: number; // yalnız çizim için sayı
  kar: number; // kâr oranı, yüzde (çizim için)
  adetMetni: string;
  satisMetni: string;
  maliyetMetni: string;
  karMetni: string;
  bolge: Bolge;
}

export interface KarlilikHaritasiVerisi {
  noktalar: KarlilikNoktasi[];
  /** Üretim adedi eşiği (medyan). */
  adetEsigi: number;
  /** Kâr oranı eşiği, yüzde. */
  karEsigi: number;
  karEsigiKaynagi: "hedef" | "medyan";
  sayilar: Record<Bolge, number>;
  /** Hesapsız, seçili fiyatı olmayan ya da adetsiz olduğu için haritaya girmeyen ürün sayısı. */
  disarida: number;
  /** Tüm noktalar aynı kâr oranındaysa (bütçe satışı = maliyet × hedef kâr) harita dikeyde bilgi taşımaz. */
  duz: boolean;
}

const tamSayi = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });

function medyan(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const n = s.length;
  return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2;
}

/** Satırlardan en az birinde geçen yıl fiyatı varsa o kaynak seçilebilir. */
export function gecenYilVar(satirlar: DashboardSatiri[]): boolean {
  return satirlar.some((s) => s.gecen_yil_tl != null);
}

/**
 * Dashboard satırlarından kârlılık haritası verisi. Kâr oranı = (satış − maliyet) / maliyet (projedeki `satis_kar` ile aynı ölçü).
 * Hatalı, seçili fiyatı/maliyeti olmayan ya da üretim adedi 0 olan ürünler haritaya girmez (`disarida`).
 * `hedefKarOrani` = `satis_kar` parametresi (0,2 gibi oran); verilmezse eşik medyandır.
 */
export function karlilikHaritasi(
  satirlar: DashboardSatiri[],
  hedefKarOrani: string | null | undefined,
  kaynak: FiyatKaynagi = "hesap",
): KarlilikHaritasiVerisi {
  const ham: Omit<KarlilikNoktasi, "bolge">[] = [];
  let disarida = 0;
  for (const s of satirlar) {
    const fiyat = kaynak === "gecen_yil" ? s.gecen_yil_tl : s.satis_tl;
    if (s.hata || fiyat == null || s.maliyet_tl == null || s.uretim_adedi == null) {
      disarida += 1;
      continue;
    }
    const satis = D(fiyat),
      maliyet = D(s.maliyet_tl),
      adet = D(s.uretim_adedi);
    if (maliyet.lte(0) || adet.lte(0)) {
      disarida += 1;
      continue;
    }
    const kar = satis.minus(maliyet).div(maliyet); // oran
    ham.push({
      kod: s.kod,
      ad: s.ad,
      hat: s.hat,
      adet: Number(adet.toFixed(0)),
      kar: Number(kar.times(100).toDecimalPlaces(2).toString()),
      adetMetni: tamSayi.format(Number(adet.toFixed(0))),
      satisMetni: paraBicimle(satis, "TL", 2),
      maliyetMetni: paraBicimle(maliyet, "TL", 2),
      karMetni: yuzdeBicimle(kar, 1),
    });
  }
  const sayilar: Record<Bolge, number> = { guclu: 0, risk: 0, nis: 0, zayif: 0 };
  if (ham.length === 0) {
    return { noktalar: [], adetEsigi: 0, karEsigi: 0, karEsigiKaynagi: hedefKarOrani ? "hedef" : "medyan", sayilar, disarida, duz: false };
  }
  const adetEsigi = medyan(ham.map((n) => n.adet));
  const hedef = hedefKarOrani ? Number(D(hedefKarOrani).times(100).toDecimalPlaces(2).toString()) : null;
  const karEsigi = hedef ?? medyan(ham.map((n) => n.kar));
  const noktalar = ham.map((n) => {
    const cokSatan = n.adet >= adetEsigi;
    const karli = n.kar >= karEsigi;
    const bolge: Bolge = cokSatan ? (karli ? "guclu" : "risk") : karli ? "nis" : "zayif";
    sayilar[bolge] += 1;
    return { ...n, bolge };
  });
  const karlar = noktalar.map((n) => n.kar);
  const duz = noktalar.length > 1 && Math.max(...karlar) - Math.min(...karlar) < 0.5;
  return { noktalar, adetEsigi, karEsigi, karEsigiKaynagi: hedef === null ? "medyan" : "hedef", sayilar, disarida, duz };
}
