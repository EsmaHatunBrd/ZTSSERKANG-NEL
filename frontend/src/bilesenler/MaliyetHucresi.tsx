import { ParaHucresi } from "./ParaHucresi";

export const ORTALAMA_IPUCU = "Stokta kalanla ortalama maliyet";

/**
 * Analiz tablolarındaki maliyet hücresi: maliyet stokta kalanla ağırlıklı ortalamadan geliyorsa (`maliyet_kaynagi === "ortalama"`)
 * tutarın yanında küçük "ort." rozeti ve ipucu gösterilir; aksi halde düz tutar.
 */
export function MaliyetHucresi({ deger, kaynak }: { deger: string | null; kaynak?: "bu_yil" | "ortalama" | null }) {
  if (kaynak !== "ortalama") return <ParaHucresi deger={deger} />;
  return (
    <span className="flex items-center justify-end gap-1.5">
      <abbr
        title={ORTALAMA_IPUCU}
        aria-label={ORTALAMA_IPUCU}
        className="rounded border border-amber-300 bg-amber-50 px-1 text-[10px] leading-4 font-medium text-amber-900 no-underline dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
      >
        ort.
      </abbr>
      <ParaHucresi deger={deger} />
    </span>
  );
}
