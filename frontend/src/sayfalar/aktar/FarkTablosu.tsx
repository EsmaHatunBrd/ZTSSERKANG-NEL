import type { ReactNode } from "react";

const AZAMI_SATIR = 300;

interface Props {
  baslik: string;
  sutunlar: string[];
  satirlar: ReactNode[][];
  /** Sağa yaslanacak sütun indisleri (sayılar). */
  sagda?: number[];
}

/** Önizleme bölümü: başlık (sayı ile) + tablo. Satır yoksa hiçbir şey çizilmez. */
export function FarkTablosu({ baslik, sutunlar, satirlar, sagda = [] }: Props) {
  if (satirlar.length === 0) return null;
  const gorunen = satirlar.slice(0, AZAMI_SATIR);
  return (
    <section aria-label={baslik} className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">
        {baslik} ({satirlar.length})
      </h3>
      <div className="max-h-72 overflow-auto rounded-md border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-muted text-left">
            <tr>
              {sutunlar.map((s, i) => (
                <th key={s} className={`px-2 py-1 font-medium ${sagda.includes(i) ? "text-right" : ""}`}>
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {gorunen.map((satir, i) => (
              <tr key={i} className="border-t">
                {satir.map((h, j) => (
                  <td key={j} className={`px-2 py-1 ${sagda.includes(j) ? "text-right tabular-nums" : ""}`}>
                    {h}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {satirlar.length > gorunen.length && (
        <p className="text-xs text-muted-foreground">İlk {AZAMI_SATIR} satır gösteriliyor; hepsi uygulanır.</p>
      )}
    </section>
  );
}

/** "Aynı: n" gibi tek satırlık sayaç. */
export function Sayac({ etiket, deger }: { etiket: string; deger: number }) {
  return (
    <p className="text-sm">
      {etiket}: <span className="font-medium tabular-nums">{deger}</span>
    </p>
  );
}
