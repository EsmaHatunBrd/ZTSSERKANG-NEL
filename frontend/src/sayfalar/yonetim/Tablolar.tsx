import type { KeyboardEvent, ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { YonetimOzeti } from "@/api/tipler";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";
import { paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { teklifDurumAdi } from "@/yardimcilar/teklif";
import { puanMetni } from "./bicim";
import { YonetimKarti } from "./YonetimKarti";

interface Sutun<T> {
  baslik: string;
  hucre: (r: T) => ReactNode;
  sag?: boolean;
}

/**
 * Özet sayfasının küçük tablosu: sıralama/arama yok (kâğıtta düğme görünmez), satır tıklanınca ve Enter ile `hedef`e gider;
 * ilk hücre ayrıca bağlantıdır (klavye ve ekran okuyucu için).
 */
function OzetTablosu<T>({
  etiket,
  satirlar,
  sutunlar,
  anahtar,
  hedef,
  bos,
}: {
  etiket: string;
  satirlar: T[];
  sutunlar: Sutun<T>[];
  anahtar: (r: T) => string;
  hedef?: (r: T) => string;
  bos: string;
}) {
  const gezin = useNavigate();
  if (satirlar.length === 0) return <p className="text-sm text-muted-foreground">{bos}</p>;
  const tusa = (e: KeyboardEvent<HTMLTableRowElement>, r: T) => {
    if (hedef && e.key === "Enter" && e.target === e.currentTarget) {
      e.preventDefault();
      gezin(hedef(r));
    }
  };
  return (
    <div className="overflow-x-auto">
      <Table aria-label={etiket}>
        <TableHeader>
          <TableRow>
            {sutunlar.map((s) => (
              <TableHead key={s.baslik} className={cn(s.sag && "text-right")}>
                {s.baslik}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {satirlar.map((r) => (
            <TableRow
              key={anahtar(r)}
              tabIndex={hedef ? 0 : undefined}
              onKeyDown={(e) => tusa(e, r)}
              onClick={
                hedef
                  ? (e) => {
                      if ((e.target as HTMLElement).closest("a, button")) return;
                      gezin(hedef(r));
                    }
                  : undefined
              }
              className={cn(
                hedef &&
                  "cursor-pointer focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset",
              )}
            >
              {sutunlar.map((s, i) => (
                <TableCell key={s.baslik} className={cn(s.sag && "text-right tabular-nums whitespace-nowrap")}>
                  {i === 0 && hedef ? (
                    <Link to={hedef(r)} className="underline-offset-4 hover:underline" tabIndex={-1}>
                      {s.hucre(r)}
                    </Link>
                  ) : (
                    s.hucre(r)
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

const para = (x: string | null, basamak = 2) => (x === null ? "—" : paraBicimle(x, "TL", basamak));
/** Ürün adı ve altında kodu (tek hücre). */
const urunHucresi = (ad: string, kod: string) => (
  <span className="flex flex-col">
    <span>{ad}</span>
    <span className="font-mono text-xs text-muted-foreground">{kod}</span>
  </span>
);

interface KartProps {
  ozet: YonetimOzeti;
  /** `?senaryo=` eki ("" ya da "?senaryo=1"). */
  sorgu: string;
}

export function HedefAltiKarti({ ozet, sorgu }: KartProps) {
  const h = ozet.hedef_alti;
  return (
    <YonetimKarti
      baslik="Marj eşiğinin altındaki ürünler"
      aciklama={`Geçen yılın satış fiyatıyla (satış geçmişi yoksa hesaplanan fiyatla) kâr oranı marj eşiği ${yuzdeBicimle(h.esik)} altında kalanlar · toplam ${h.toplam} ürün${h.toplam > h.kayitlar.length ? ` (ilk ${h.kayitlar.length})` : ""}`}
      bagla={`/hedef-fiyat${sorgu}`}
      baglaMetni="Marjı koruyan fiyat"
    >
      <OzetTablosu
        etiket="Marj eşiğinin altındaki ürünler"
        satirlar={h.kayitlar}
        anahtar={(r) => r.kod}
        hedef={(r) => `/urunler/${encodeURIComponent(r.kod)}${sorgu}`}
        bos="Marj eşiğinin altında ürün yok."
        sutunlar={[
          { baslik: "Ürün", hucre: (r) => urunHucresi(r.ad, r.kod) },
          { baslik: "Kâr %", hucre: (r) => <span className="font-semibold text-destructive">{yuzdeBicimle(r.kar_orani)}</span>, sag: true },
          { baslik: "Maliyet", hucre: (r) => para(r.maliyet), sag: true },
          { baslik: "Satış", hucre: (r) => para(r.satis), sag: true },
          { baslik: "Fiyat", hucre: (r) => (r.fiyat_kaynagi === "gecen_yil" ? "geçen yıl" : "hesap") },
        ]}
      />
    </YonetimKarti>
  );
}

export function KurRiskiKarti({ ozet, sorgu }: KartProps) {
  const k = ozet.kur_riski;
  return (
    <YonetimKarti
      baslik="En riskli ürünler (kur)"
      aciklama={`Kurlar +${yuzdeBicimle(k.oran, 0)} artarsa yıllık etkisi en büyük ${k.en_riskli.length} ürün · toplam ${paraBicimle(k.yillik_etki_tl, "TL", 0)}${
        k.adetsiz_urun > 0 ? ` · ${k.adetsiz_urun} ürünün yıllık adedi yok` : ""
      }`}
      bagla={`/kur-riski${sorgu}`}
      baglaMetni="Kur riski"
    >
      <OzetTablosu
        etiket="En riskli ürünler"
        satirlar={k.en_riskli}
        anahtar={(r) => r.kod}
        hedef={(r) => `/urunler/${encodeURIComponent(r.kod)}${sorgu}`}
        bos="Döviz payı olan ürün yok."
        sutunlar={[
          { baslik: "Ürün", hucre: (r) => urunHucresi(r.ad, r.kod) },
          { baslik: "Döviz payı", hucre: (r) => puanMetni(r.doviz_payi_yuzde), sag: true },
          { baslik: "Birim etki", hucre: (r) => para(r.birim_etki), sag: true },
          { baslik: "Yıllık etki", hucre: (r) => <span className="font-semibold">{para(r.yillik_etki, 0)}</span>, sag: true },
        ]}
      />
    </YonetimKarti>
  );
}

export function AcikTekliflerKarti({ ozet, sorgu }: KartProps) {
  const t = ozet.teklifler;
  const d = t.durumlar;
  return (
    <YonetimKarti
      baslik="En eski açık teklifler"
      aciklama={`Taslak ${d.taslak ?? 0} · gönderildi ${d.gonderildi ?? 0} · kabul ${d.kabul ?? 0} · red ${d.red ?? 0}`}
      bagla={`/teklifler${sorgu}`}
      baglaMetni="Teklifler"
    >
      <OzetTablosu
        etiket="En eski açık teklifler"
        satirlar={t.en_eski_acik}
        anahtar={(r) => String(r.teklif_id)}
        hedef={() => `/teklifler${sorgu}`}
        bos="Açık teklif yok."
        sutunlar={[
          { baslik: "Ürün", hucre: (r) => urunHucresi(r.urun_ad, r.urun_kodu) },
          { baslik: "Müşteri", hucre: (r) => r.musteri ?? "—" },
          { baslik: "Tur", hucre: (r) => `${r.tur_no} · ${teklifDurumAdi(r.durum)}` },
          { baslik: "Tarih", hucre: (r) => (r.tarih ? goster(r.tarih) : goster(r.hesap_tarihi)), sag: true },
          { baslik: "Fiyat", hucre: (r) => paraBicimle(r.fiyat_tl), sag: true },
        ]}
      />
    </YonetimKarti>
  );
}

export function EnPahaliKarti({ ozet, sorgu }: KartProps) {
  return (
    <YonetimKarti
      baslik="En pahalı ürünler"
      aciklama="Birim maliyeti en yüksek ürünler ve satış fiyatları"
      bagla={`/genel-bakis${sorgu}`}
      baglaMetni="Genel Bakış"
    >
      <OzetTablosu
        etiket="En pahalı ürünler"
        satirlar={ozet.en_pahali}
        anahtar={(r) => r.kod}
        hedef={(r) => `/urunler/${encodeURIComponent(r.kod)}${sorgu}`}
        bos="Hesaplanan ürün yok."
        sutunlar={[
          { baslik: "Ürün", hucre: (r) => urunHucresi(r.ad, r.kod) },
          { baslik: "Maliyet", hucre: (r) => <span className="font-semibold">{paraBicimle(r.maliyet)}</span>, sag: true },
          { baslik: "Satış", hucre: (r) => paraBicimle(r.satis), sag: true },
        ]}
      />
    </YonetimKarti>
  );
}
