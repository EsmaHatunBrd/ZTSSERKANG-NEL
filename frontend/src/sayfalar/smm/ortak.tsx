import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSmmDonemleri } from "@/api/sorgular/smm";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";

export const SECIM_SINIFI = "h-8 rounded-lg border border-input bg-background px-2 text-sm";
/** Büyük tutar kısaltılır: 723567044 -> "723,6 mn TL" (özet kutularında tek satıra sığsın). */
export const milyon = (x: string) => `${paraBicimle(D(x).dividedBy(1_000_000), "", 1)} mn TL`;
export const miktar = (x: string) => new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 3 }).format(D(x).toNumber());
/** Mizan adındaki kod önekini atar: '0001-Hammadde' -> 'Hammadde'. */
export const turAdi = (t: string | null) => (t ?? "Diğer").replace(/^\d+-/, "");

/** Miktar hücresi: sıfır '—', eksi kırmızı, birim yanında küçük. */
export function Miktar({ deger, birim }: { deger: string; birim?: string | null }) {
  const sifir = D(deger).isZero();
  return (
    <span
      className={cn(
        "block text-right tabular-nums",
        sifir && "text-muted-foreground",
        D(deger).isNegative() && "font-medium text-red-600 dark:text-red-400",
      )}
    >
      {sifir ? "—" : miktar(deger)}
      {!sifir && birim ? <span className="ml-1 text-xs text-muted-foreground">{birim}</span> : null}
    </span>
  );
}

/** Seçili SMM dönemi: ?donem= yoksa en yeni dönem. */
export function useSmmDonemSecimi() {
  const [params, setParams] = useSearchParams();
  const donemler = useSmmDonemleri();
  const liste = donemler.data?.kayitlar ?? [];
  const donemId = params.get("donem") ? Number(params.get("donem")) : (liste[0]?.id ?? null);
  const sec = (id: string) => setParams((p) => (p.set("donem", id), p));
  return { donemler, liste, donemId, sec, bos: Boolean(donemler.data) && liste.length === 0 };
}

export function DonemSecici({ secim }: { secim: ReturnType<typeof useSmmDonemSecimi> }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Dönem</span>
      <select aria-label="Dönem" className={SECIM_SINIFI} value={secim.donemId ?? ""} onChange={(e) => secim.sec(e.target.value)}>
        {secim.liste.map((d) => (
          <option key={d.id} value={d.id}>
            {d.ad}
          </option>
        ))}
      </select>
    </label>
  );
}

export function DonemYok() {
  return (
    <p className="rounded-2xl border border-dashed bg-card p-5 text-sm text-muted-foreground">
      Henüz dönem yok.{" "}
      <Link to="/smm" className="font-medium text-primary underline-offset-4 hover:underline">
        Dönemler
      </Link>{" "}
      sayfasından bir SMM Excel'i yükleyin.
    </p>
  );
}

/** Arama kutusu için gecikmeli değer (her tuşta sunucuya gitmesin). */
export function useGecikmeli(deger: string, ms = 300) {
  const [g, setG] = useState(deger);
  useEffect(() => {
    const t = setTimeout(() => setG(deger.trim()), ms);
    return () => clearTimeout(t);
  }, [deger, ms]);
  return g;
}
