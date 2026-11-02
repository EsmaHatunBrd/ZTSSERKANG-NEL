import { useId, useState } from "react";
import { UyariRozeti } from "@/bilesenler/UyariRozeti";

interface Props {
  sayi: number | null;
  /** Bu ürüne ait uyarı metinleri (yüklenene kadar boş olabilir). */
  uyarilar: string[];
  yukleniyor?: boolean;
}

/** Uyarı sayısı rozeti; tıklayınca ürünün uyarı listesini açar/kapatır. */
export function UyariHucresi({ sayi, uyarilar, yukleniyor }: Props) {
  const [acik, setAcik] = useState(false);
  const kimlik = useId();
  if (!sayi) return <span className="block text-center text-muted-foreground">—</span>;
  return (
    <div className="relative flex justify-center">
      <button
        type="button"
        aria-label={`${sayi} uyarı`}
        aria-expanded={acik}
        aria-controls={kimlik}
        onClick={() => setAcik((a) => !a)}
        className="rounded-full focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        <UyariRozeti sayi={sayi} />
      </button>
      {acik && (
        <ul
          id={kimlik}
          className="absolute top-full right-0 z-10 mt-1 w-72 list-disc rounded-md border bg-popover p-3 pl-6 text-left text-xs text-popover-foreground shadow-md"
        >
          {yukleniyor ? (
            <li className="list-none">Yükleniyor…</li>
          ) : uyarilar.length === 0 ? (
            <li className="list-none">Uyarı ayrıntısı bulunamadı</li>
          ) : (
            uyarilar.map((u, i) => <li key={i}>{u}</li>)
          )}
        </ul>
      )}
    </div>
  );
}
