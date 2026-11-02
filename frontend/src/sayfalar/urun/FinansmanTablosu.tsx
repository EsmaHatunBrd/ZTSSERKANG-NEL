import type { Toplamlar } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { apiMetni, D, paraBicimle } from "@/yardimcilar/para";
import { ParametreGirdisi } from "./ParametreGirdisi";
import type { ParametreGorunumu } from "./yardimci";

const SIRA = ["TL", "USD", "EUR", "GBP", "ZAR"];

interface Props {
  parametreler: ParametreGorunumu;
  toplamlar: Toplamlar;
  /** `Taslak.parametreler` dilimi (anahtar -> API değeri). */
  taslak: Record<string, string>;
  onParametre: (anahtar: string, deger: string | null) => void;
  /** Sunucu tabanı (anahtar -> API değeri): "Eski değer" ipucu için. */
  taban?: Record<string, string>;
  saltOkunur?: boolean;
}

function maliyetOf(t: Toplamlar, pb: string): string | null | undefined {
  switch (pb) {
    case "TL":
      return t.maliyet_tl;
    case "USD":
      return t.maliyet_usd;
    case "EUR":
      return t.maliyet_eur;
    case "GBP":
      return t.maliyet_gbp;
    case "ZAR":
      return t.maliyet_zar;
    default:
      return undefined;
  }
}

/** Para birimi başına faiz (faiz tutarları TL cinsindendir), stok süresi, dönem faizi ve faiz tutarı; altında finansman dahil maliyet ve kur. */
export function FinansmanTablosu({ parametreler: p, toplamlar: t, taslak, onParametre, taban, saltOkunur = false }: Props) {
  const o = taslak;
  const birimler = SIRA.filter((pb) => pb in p.faiz || pb in p.stok_ay || (t.finansman && pb in t.finansman));
  const faizTutari = (pb: string) => t.finansman?.[pb] ?? (pb === "TL" ? t.finansman_tl : null) ?? null;

  return (
    <section aria-label="Finansman" className="flex flex-col gap-3 rounded-xl border p-4">
      <h2 className="text-base font-semibold">Finansman</h2>
      <Table aria-label="Finansman tablosu">
        <TableHeader>
          <TableRow>
            <TableHead>Para birimi</TableHead>
            <TableHead className="text-right">Faiz oranı (%)</TableHead>
            <TableHead className="text-right">Stok süresi (ay)</TableHead>
            <TableHead className="text-right">Dönem faizi</TableHead>
            <TableHead className="text-right">Faiz tutarı (TL)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {birimler.map((pb) => {
            const faiz = o[`faiz.${pb}`] ?? p.faiz[pb];
            const stok = o[`stok_ay.${pb}`] ?? p.stok_ay[pb];
            const donem = faiz !== undefined && stok !== undefined ? apiMetni(D(faiz).div(12).times(D(stok))) : null;
            return (
              <TableRow key={pb}>
                <TableCell className="font-medium">{pb}</TableCell>
                <TableCell className="text-right">
                  <ParametreGirdisi
                    etiket={`Faiz ${pb} (%)`}
                    tur="yuzde"
                    deger={p.faiz[pb] ?? null}
                    eskiDeger={taban ? (taban[`faiz.${pb}`] ?? null) : undefined}
                    taslak={o[`faiz.${pb}`]}
                    onDegis={(d) => onParametre(`faiz.${pb}`, d)}
                    disabled={saltOkunur}
                  />
                </TableCell>
                <TableCell className="text-right">
                  <ParametreGirdisi
                    etiket={`Stok süresi ${pb} (ay)`}
                    deger={p.stok_ay[pb] ?? null}
                    eskiDeger={taban ? (taban[`stok_ay.${pb}`] ?? null) : undefined}
                    taslak={o[`stok_ay.${pb}`]}
                    onDegis={(d) => onParametre(`stok_ay.${pb}`, d)}
                    disabled={saltOkunur}
                  />
                </TableCell>
                <TableCell>
                  <YuzdeHucresi deger={donem} />
                </TableCell>
                <TableCell>
                  <ParaHucresi deger={faizTutari(pb)} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <Table aria-label="Finansman dahil maliyet">
        <TableHeader>
          <TableRow>
            <TableHead>Para birimi</TableHead>
            <TableHead className="text-right">Finansman dahil maliyet</TableHead>
            <TableHead className="text-right">Kur</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {SIRA.filter((pb) => maliyetOf(t, pb) != null).map((pb) => (
            <TableRow key={pb}>
              <TableCell className="font-medium">{pb}</TableCell>
              <TableCell>
                <ParaHucresi deger={maliyetOf(t, pb) ?? null} paraBirimi={pb} basamak={pb === "TL" ? 2 : 4} />
              </TableCell>
              <TableCell className="text-right tabular-nums text-muted-foreground">
                {pb === "TL" || p.kurlar[pb] === undefined ? "—" : paraBicimle(p.kurlar[pb], "", 4)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}
