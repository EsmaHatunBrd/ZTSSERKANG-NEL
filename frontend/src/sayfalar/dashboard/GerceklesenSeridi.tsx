import { ArrowRight, GitCompareArrows } from "lucide-react";
import { Link } from "react-router-dom";
import { useKarsiSenaryo, useKiyasListesi } from "@/api/sorgular/kiyas";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { FarkYuzdesi } from "../kiyas/FarkYuzdesi";
import { varsayilanCift } from "../kiyasCifti";

/** Genel Bakış: aynı sezonda gerçekleşen (ya da bütçe) çalışması varsa kıyasın tek satırlık özeti; yoksa hiçbir şey çizilmez. */
export function GerceklesenSeridi() {
  const { senaryoId, senaryo } = useSenaryo();
  const karsi = useKarsiSenaryo(senaryoId);
  const { a, b } = varsayilanCift(senaryo, karsi.data?.karsi?.id ?? null);
  const liste = useKiyasListesi(a, b, "5");
  const o = liste.data?.ozet;
  if (!karsi.data?.karsi || a === null || b === null) return null;
  return (
    <div
      role="status"
      aria-label="Gerçekleşen kıyası"
      className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border bg-card px-3 py-2 text-sm"
    >
      <GitCompareArrows className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      {o ? (
        <span>
          <span className="font-medium">Gerçekleşen kıyası:</span> {o.karsilastirilan} üründen{" "}
          <strong className="tabular-nums">{o.sapan}</strong> tanesinin maliyeti ±%5&apos;in dışında
          {o.ortalama_sapma_yuzde && (
            <>
              {" "}
              · ortalama sapma <FarkYuzdesi deger={o.ortalama_sapma_yuzde} className="inline" />
            </>
          )}
        </span>
      ) : (
        <span className="text-muted-foreground">
          {liste.error ? "Gerçekleşen kıyası hesaplanamadı." : "Gerçekleşen kıyası hesaplanıyor…"}
        </span>
      )}
      <Link
        to={`/butce-gerceklesen?senaryo=${senaryoId}&a=${a}&b=${b}`}
        className="ml-auto inline-flex items-center gap-1 font-medium underline-offset-4 hover:underline"
      >
        Bütçe vs Gerçekleşen
        <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </div>
  );
}
