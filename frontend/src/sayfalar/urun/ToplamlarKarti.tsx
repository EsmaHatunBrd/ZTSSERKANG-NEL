import type { Fiyatlar, Toplamlar } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { apiMetni, D, type ParaBirimi } from "@/yardimcilar/para";

interface Props {
  toplamlar: Toplamlar;
  toplamlarFiresiz: Toplamlar | null;
  fiyatlar: Fiyatlar;
  fiyatlarFiresiz: Fiyatlar | null;
  /** Hesap notları (örn. muhasebe açıklamaları); satış fiyatı tablosunun altında vurgulu listelenir. */
  notlar?: string[] | null;
  /** Hesap yanıtındaki `parametreler.kurlar` (para birimi -> TL kuru); satış fiyatı tablosunda gösterilir. */
  kurlar?: Record<string, string> | null;
}

function Satir({
  etiket,
  fireli,
  firesiz,
  birim = "TL",
  basamak = 2,
  vurgulu = false,
}: {
  etiket: string;
  fireli: string | null | undefined;
  firesiz: string | null | undefined;
  birim?: ParaBirimi;
  basamak?: number;
  vurgulu?: boolean;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-6 border-b py-1.5 last:border-0">
      <span data-etiket className={vurgulu ? "text-sm font-medium" : "text-sm text-muted-foreground"}>
        {etiket}
      </span>
      <ParaHucresi deger={fireli ?? null} paraBirimi={birim} basamak={basamak} className="min-w-28" />
      <ParaHucresi deger={firesiz ?? null} paraBirimi={birim} basamak={basamak} className="min-w-28" />
    </div>
  );
}

const toplamBirimMaliyet = (t: Toplamlar | null | undefined) => (t ? apiMetni(D(t.malzeme).plus(D(t.uretim_gideri))) : null);

const var_ = (a: string | null | undefined, b: string | null | undefined) => a != null || b != null;

const kurMetni = (k: string | null | undefined) =>
  k == null
    ? "—"
    : new Intl.NumberFormat("tr-TR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
      }).format(D(k).toDecimalPlaces(4).toFixed() as unknown as number);

/** Kâr oranı (0.2) -> "%20" (en çok bir ondalık); oran yoksa boş metin. */
const oranMetni = (o: string | null | undefined) => (o == null ? "" : `%${D(o).times(100).toDecimalPlaces(1).toFixed().replace(".", ",")}`);

interface SatisProps {
  fiyatlar: Fiyatlar;
  fiyatlarFiresiz: Fiyatlar | null;
  kurlar?: Record<string, string> | null;
  notlar?: string[] | null;
}

/** Excel'deki "Satış fiyatı (%20)" bloğu: para birimi, kur, fireli/firesiz fiyat; not; süzme kg birim fiyatı; teklifler (USD/adet). */
export function SatisFiyatiTablosu({ fiyatlar: f, fiyatlarFiresiz: ff, kurlar, notlar }: SatisProps) {
  const satisKar = oranMetni(f.satis_kar_orani ?? ff?.satis_kar_orani);
  const satirlar: {
    pb: string;
    kur: string | null;
    fireli: string | null | undefined;
    firesiz: string | null | undefined;
    basamak: number;
  }[] = [
    {
      pb: "TL",
      kur: null,
      fireli: f.satis_tl,
      firesiz: ff?.satis_tl,
      basamak: 2,
    },
    {
      pb: "USD",
      kur: kurlar?.USD ?? null,
      fireli: f.satis_usd,
      firesiz: ff?.satis_usd,
      basamak: 3,
    },
    {
      pb: "EUR",
      kur: kurlar?.EUR ?? null,
      fireli: f.satis_eur,
      firesiz: ff?.satis_eur,
      basamak: 3,
    },
    ...(var_(f.satis_gbp, ff?.satis_gbp)
      ? [
          {
            pb: "GBP",
            kur: kurlar?.GBP ?? null,
            fireli: f.satis_gbp,
            firesiz: ff?.satis_gbp,
            basamak: 3,
          },
        ]
      : []),
    ...(var_(f.satis_zar, ff?.satis_zar)
      ? [
          {
            pb: "ZAR",
            kur: kurlar?.ZAR ?? null,
            fireli: f.satis_zar,
            firesiz: ff?.satis_zar,
            basamak: 3,
          },
        ]
      : []),
  ];
  const teklifSayisi = Math.max(f.teklifler_usd.length, ff?.teklifler_usd.length ?? 0);
  const teklifOrani = (i: number) => f.teklif_kar_oranlari?.[i] ?? ff?.teklif_kar_oranlari?.[i];
  const teklifSatirlari: [string, string[]][] = [
    ["Fireli", f.teklifler_usd],
    ["Firesiz", ff?.teklifler_usd ?? []],
  ];
  return (
    <section aria-label="Satış fiyatı" className="flex flex-col gap-3 rounded-xl border p-4">
      <h2 className="text-base font-semibold">{satisKar ? `Satış fiyatı (${satisKar})` : "Satış fiyatı"}</h2>
      <Table aria-label="Satış fiyatı tablosu">
        <TableHeader>
          <TableRow>
            <TableHead>Para birimi</TableHead>
            <TableHead className="text-right">Kur</TableHead>
            <TableHead className="text-right">Fiyat (fireli)</TableHead>
            <TableHead className="text-right">Fiyat (firesiz)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {satirlar.map((r) => (
            <TableRow key={r.pb}>
              <TableCell className="font-medium">{r.pb}</TableCell>
              <TableCell className="text-right tabular-nums text-muted-foreground">{r.pb === "TL" ? "—" : kurMetni(r.kur)}</TableCell>
              <TableCell>
                <ParaHucresi deger={r.fireli ?? null} paraBirimi={r.pb} basamak={r.basamak} />
              </TableCell>
              <TableCell>
                <ParaHucresi deger={r.firesiz ?? null} paraBirimi={r.pb} basamak={r.basamak} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {notlar && notlar.length > 0 && (
        <ul
          aria-label="Hesap notları"
          className="flex flex-col gap-1 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm font-medium text-destructive"
        >
          {notlar.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <Satir etiket="Süzme kg birim fiyatı" fireli={f.suzme_kg_tl} firesiz={ff?.suzme_kg_tl} vurgulu />
      {teklifSayisi > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold">Teklifler (USD/adet)</h3>
          <Table aria-label="Teklifler tablosu">
            <TableHeader>
              <TableRow>
                <TableHead />
                {Array.from({ length: teklifSayisi }, (_, i) => (
                  <TableHead key={i} className="text-right">
                    {`${i + 1}. teklif ${oranMetni(teklifOrani(i))}`.trim()}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {teklifSatirlari.map(([ad, degerler]) => (
                <TableRow key={ad}>
                  <TableCell className="text-muted-foreground">{ad}</TableCell>
                  {Array.from({ length: teklifSayisi }, (_, i) => (
                    <TableCell key={i}>
                      <ParaHucresi deger={degerler[i] ?? null} paraBirimi="USD" basamak={3} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}

/** Excel ürün sayfası sırası: malzeme, işçilik, GÜG, gider toplamı, toplam birim maliyet, diğer, giydirilmiş, finansman, maliyet. Fireli | firesiz yan yana. Satış fiyatları ayrı tabloda. */
export function ToplamlarKarti({ toplamlar: t, toplamlarFiresiz: tf, fiyatlar: f, fiyatlarFiresiz: ff, notlar, kurlar }: Props) {
  return (
    <div className="flex flex-col gap-6">
      <section aria-label="Toplamlar" className="flex flex-col rounded-xl border p-4">
        <div className="grid grid-cols-[1fr_auto_auto] gap-x-6 border-b pb-2 text-sm font-medium">
          <h2 className="text-base font-semibold">Toplamlar</h2>
          <span className="min-w-28 text-right">Fireli</span>
          <span className="min-w-28 text-right">Firesiz</span>
        </div>
        <Satir etiket="Hammadde-yardımcı malzeme toplamı" fireli={t.malzeme} firesiz={tf?.malzeme} />
        <Satir etiket="Direkt işçilik" fireli={t.direkt_iscilik} firesiz={tf?.direkt_iscilik} />
        <Satir etiket="GÜG" fireli={t.gug} firesiz={tf?.gug} />
        <Satir etiket="Gider toplamı" fireli={t.uretim_gideri} firesiz={tf?.uretim_gideri} />
        <Satir etiket="Toplam birim maliyet" fireli={toplamBirimMaliyet(t)} firesiz={toplamBirimMaliyet(tf)} vurgulu />
        <Satir etiket="Diğer giderler" fireli={t.diger} firesiz={tf?.diger} />
        <Satir etiket="Giydirilmiş maliyet" fireli={t.giydirilmis} firesiz={tf?.giydirilmis} />
        <Satir etiket="Finansman (TL)" fireli={t.finansman_tl} firesiz={tf?.finansman_tl} />
        <Satir etiket="Finansman dahil maliyet TL" fireli={t.maliyet_tl} firesiz={tf?.maliyet_tl} vurgulu />
        <Satir etiket="Finansman dahil maliyet USD" fireli={t.maliyet_usd} firesiz={tf?.maliyet_usd} birim="USD" basamak={3} />
        <Satir etiket="Finansman dahil maliyet EUR" fireli={t.maliyet_eur} firesiz={tf?.maliyet_eur} birim="EUR" basamak={3} />
        {var_(t.maliyet_gbp, tf?.maliyet_gbp) && (
          <Satir etiket="Finansman dahil maliyet GBP" fireli={t.maliyet_gbp} firesiz={tf?.maliyet_gbp} birim="GBP" basamak={3} />
        )}
        {var_(t.maliyet_zar, tf?.maliyet_zar) && (
          <Satir etiket="Finansman dahil maliyet ZAR" fireli={t.maliyet_zar} firesiz={tf?.maliyet_zar} birim="ZAR" basamak={3} />
        )}
      </section>
      <SatisFiyatiTablosu fiyatlar={f} fiyatlarFiresiz={ff} kurlar={kurlar} notlar={notlar} />
    </div>
  );
}
