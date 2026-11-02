import { ArrowRight, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";
import { useTutarlilik } from "@/api/sorgular/tutarlilik";

/** Genel Bakış: Veri Kontrolü'nde ilgi bekleyen konu varsa tek satır ve bağlantı; hepsi tamamsa ya da yüklenirken hiçbir şey çizilmez. */
export function VeriKontroluSeridi({ senaryoId }: { senaryoId: number | null }) {
  const q = useTutarlilik(senaryoId);
  const o = q.data?.ozet;
  if (!o || o.hata + o.dikkat === 0) return null;
  const basliklar = (q.data?.kontroller ?? []).filter((k) => k.durum !== "tamam").map((k) => k.baslik.toLocaleLowerCase("tr"));
  return (
    <div
      role="status"
      aria-label="Veri Kontrolü"
      className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border bg-card px-3 py-2 text-sm"
    >
      <ListChecks className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span>
        <span className="font-medium">Veri Kontrolü:</span> {o.hata + o.dikkat} konu ilgi bekliyor
        {o.hata > 0 && ` (${o.hata} tanesi hesabı engelliyor)`} — {basliklar.slice(0, 3).join(", ")}
        {basliklar.length > 3 ? "…" : ""}
      </span>
      <Link
        to={`/veri-kontrolu?senaryo=${senaryoId}`}
        className="ml-auto inline-flex items-center gap-1 font-medium underline-offset-4 hover:underline"
      >
        Veri Kontrolü
        <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </div>
  );
}
