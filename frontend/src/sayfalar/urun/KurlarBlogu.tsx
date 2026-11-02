import { Link } from "react-router-dom";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { ParametreGirdisi } from "./ParametreGirdisi";
import type { ParametreGorunumu } from "./yardimci";

const KUR_SIRASI = ["USD", "EUR", "GBP", "CHF", "RUB", "ZAR"];

interface Props {
  parametreler: ParametreGorunumu;
  /** `Taslak.parametreler` dilimi (anahtar -> API değeri). */
  taslak: Record<string, string>;
  onParametre: (anahtar: string, deger: string | null) => void;
  /** Sunucu tabanı (anahtar -> API değeri): "Eski değer" ipucu için. */
  taban?: Record<string, string>;
  /** Kayıtlı hesap görünümü: değerler yalnızca gösterilir. */
  saltOkunur?: boolean;
}

/** Enflasyon, maliyet sapma ve döviz kurları: yazılan değer hesaba hemen girer, "Kaydet" ile kalıcı olur. */
export function KurlarBlogu({ parametreler: p, taslak, onParametre, taban, saltOkunur = false }: Props) {
  const { senaryoId } = useSenaryo();
  const kurlar = [...KUR_SIRASI.filter((pb) => pb in p.kurlar), ...Object.keys(p.kurlar).filter((pb) => !KUR_SIRASI.includes(pb))];
  const baglanti = senaryoId === null ? "/parametreler" : `/parametreler?senaryo=${senaryoId}`;
  const o = taslak;
  return (
    <section aria-label="Kurlar ve enflasyon" className="flex flex-col gap-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Kurlar ve enflasyon</h2>
        <Link to={baglanti} className="text-sm text-primary underline-offset-4 hover:underline">
          Parametrelerde kalıcı değiştir
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        <label className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">Enflasyon (%)</span>
          <ParametreGirdisi
            etiket="Enflasyon (%)"
            tur="yuzde"
            negatifIzin
            deger={p.enflasyon}
            eskiDeger={taban ? (taban.enflasyon ?? null) : undefined}
            taslak={o.enflasyon}
            onDegis={(d) => onParametre("enflasyon", d)}
            disabled={saltOkunur}
          />
        </label>
        <label className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">Maliyet sapma (%)</span>
          <ParametreGirdisi
            etiket="Maliyet sapma (%)"
            tur="yuzde"
            negatifIzin
            deger={p.maliyet_sapma}
            eskiDeger={taban ? (taban.maliyet_sapma ?? null) : undefined}
            taslak={o.maliyet_sapma}
            onDegis={(d) => onParametre("maliyet_sapma", d)}
            disabled={saltOkunur}
          />
        </label>
        {kurlar.map((pb) => (
          <label key={pb} className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">{`${pb} kuru`}</span>
            <ParametreGirdisi
              etiket={`Kur ${pb}`}
              deger={p.kurlar[pb]}
              eskiDeger={taban ? (taban[`kur.${pb}`] ?? null) : undefined}
              taslak={o[`kur.${pb}`]}
              onDegis={(d) => onParametre(`kur.${pb}`, d)}
              disabled={saltOkunur}
            />
          </label>
        ))}
      </div>
    </section>
  );
}
