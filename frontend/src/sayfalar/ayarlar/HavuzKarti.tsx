import type { GiderHavuzu } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";
import { D, paraBicimle, topla, yuzdeBicimle } from "@/yardimcilar/para";

interface Props {
  havuz: GiderHavuzu;
  /** `pay_kontrol` listesinde bu havuz varsa, sunucunun hesapladığı pay toplamı. */
  payKontrolToplam?: string;
  onDuzenle: () => void;
  /** Senaryo kilitliyse düzenleme pasif. */
  kilitli?: boolean;
  /** Düzenle düğmesinin ipucu (ör. "Düzenleme kilitli"). */
  kilitNedeni?: string;
}

/** Excel'deki Gider Dağıtım bloğunun sütun adları: baz tipine göre "Çalışılan Saniye / B.M. / SN" vb. */
const BAZ_ETIKETI: Record<GiderHavuzu["baz_tipi"], { baz: string; bm: string }> = {
  saniye: { baz: "Çalışılan Saniye", bm: "B.M. / SN" },
  kg: { baz: "Kg", bm: "B.M. / KG" },
  adet: { baz: "Adet", bm: "B.M. / AD" },
};

const sayi = (x: string | import("decimal.js").Decimal) => paraBicimle(x, "", 0);
const birimMaliyet = (tutar: import("decimal.js").Decimal, baz: import("decimal.js").Decimal | null) =>
  baz && baz.gt(0) ? paraBicimle(tutar.div(baz), "TL", 6) : "—";

export function HavuzKarti({ havuz, payKontrolToplam, onDuzenle, kilitli = false, kilitNedeni }: Props) {
  const yerel = topla(havuz.anahtarlar.map((a) => a.pay_orani));
  const listede = payKontrolToplam !== undefined;
  const toplam = listede ? D(payKontrolToplam) : yerel;
  const kirmizi = listede || (havuz.anahtarlar.length > 0 && !yerel.equals(1));
  const etiket = BAZ_ETIKETI[havuz.baz_tipi];
  const giderToplami = D(havuz.toplam_tutar);
  const anahtarli = havuz.anahtarlar.length > 0;
  // Anahtarlı havuzda baz, alt kalemlerin toplamıdır (Excel'in toplam satırı); anahtarsızda havuz düzeyinde girilir.
  const baz = havuz.baz_miktar !== null ? D(havuz.baz_miktar) : anahtarli ? topla(havuz.anahtarlar.map((a) => a.baz_miktar)) : null;

  return (
    <section aria-labelledby={`havuz-${havuz.kod}`} className="flex flex-col gap-3 rounded-lg border p-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={`havuz-${havuz.kod}`} className="text-lg font-medium">
          {havuz.ad} <span className="font-mono text-xs text-muted-foreground">({havuz.kod})</span>
        </h2>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`Havuzu düzenle ${havuz.kod}`}
          disabled={kilitli}
          title={kilitli ? kilitNedeni : undefined}
          onClick={onDuzenle}
        >
          Düzenle
        </Button>
      </header>
      <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-muted-foreground">Gider Toplamı</dt>
          <dd className="tabular-nums">{paraBicimle(giderToplami, "TL", 2)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Dağıtım bazı</dt>
          <dd>{havuz.baz_tipi}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{etiket.baz}</dt>
          <dd className="tabular-nums">{baz ? sayi(baz) : "—"}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">{etiket.bm}</dt>
          {/* Anahtarlı havuzda birim maliyet alt kalem bazındadır; Excel de toplam satırında boş bırakır. */}
          <dd className="tabular-nums">{anahtarli ? "—" : birimMaliyet(giderToplami, baz)}</dd>
        </div>
      </dl>
      {havuz.taban_tutar !== null && havuz.taban_tutar !== undefined && havuz.carpanlar.length > 0 && (
        // Excel'deki "taban × 1,35 × 1,30 = toplam" satırı: Gider Toplamı nasıl oluştu.
        <p data-testid={`carpan-${havuz.kod}`} className="text-sm tabular-nums text-muted-foreground">
          {paraBicimle(havuz.taban_tutar, "", 2)}
          {havuz.carpanlar.map((c) => ` × ${c.deger.replace(".", ",")}`).join("")} ={" "}
          <span className="text-foreground">{paraBicimle(giderToplami, "TL", 2)}</span>
          {havuz.carpanlar.some((c) => c.ad) && (
            <span className="ml-2 text-xs">(çarpanlar: {havuz.carpanlar.map((c) => c.ad || "—").join(", ")})</span>
          )}
        </p>
      )}
      {anahtarli && (
        <div>
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[24%]">Alt kalem</TableHead>
                <TableHead className="w-[22%] text-right">Gider Toplamı</TableHead>
                <TableHead className="w-[20%] text-right">{etiket.baz}</TableHead>
                <TableHead className="w-[18%] text-right">{etiket.bm}</TableHead>
                <TableHead className="w-[16%] text-right">Gider %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {havuz.anahtarlar.map((a) => {
                const altGider = giderToplami.times(D(a.pay_orani));
                const altBaz = D(a.baz_miktar);
                return (
                  <TableRow key={a.alt_kalem}>
                    <TableCell>{a.alt_kalem}</TableCell>
                    <TableCell className="text-right tabular-nums">{paraBicimle(altGider, "TL", 2)}</TableCell>
                    <TableCell className="text-right tabular-nums">{sayi(altBaz)}</TableCell>
                    <TableCell className="text-right tabular-nums">{birimMaliyet(altGider, altBaz)}</TableCell>
                    <TableCell className="text-right tabular-nums">{yuzdeBicimle(a.pay_orani, 1)}</TableCell>
                  </TableRow>
                );
              })}
              <TableRow className="font-medium">
                <TableCell>Toplam</TableCell>
                <TableCell className="text-right tabular-nums">{paraBicimle(giderToplami, "TL", 2)}</TableCell>
                <TableCell className="text-right tabular-nums">{baz ? sayi(baz) : "—"}</TableCell>
                <TableCell className="text-right text-muted-foreground">—</TableCell>
                <TableCell className="text-right tabular-nums">
                  <strong
                    data-testid={`pay-toplam-${havuz.kod}`}
                    className={cn("tabular-nums", kirmizi ? "text-red-600 dark:text-red-400" : "text-foreground")}
                  >
                    {yuzdeBicimle(toplam, 1)}
                  </strong>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      )}
      {!anahtarli && <p className="text-sm text-muted-foreground">Anahtar tanımlı değil; gider tüm baz üzerinden tek oranla dağıtılır.</p>}
      {kirmizi && (
        <p className="text-sm text-red-600 dark:text-red-400">
          {anahtarli ? (
            "Pay toplamı %100 olmalı"
          ) : (
            <>
              Pay toplamı{" "}
              <strong data-testid={`pay-toplam-${havuz.kod}`} className="tabular-nums">
                {yuzdeBicimle(toplam, 1)}
              </strong>{" "}
              — toplam %100 olmalı
            </>
          )}
        </p>
      )}
    </section>
  );
}
