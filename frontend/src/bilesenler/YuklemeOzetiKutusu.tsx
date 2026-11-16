import { useState } from "react";
import { Download } from "lucide-react";
import { Button } from "@/bilesenler/ui/button";
import { dosyaIndir } from "@/yardimcilar/indir";

/** Backend `semalar.SorunluSatir`. */
export interface SorunluSatirT {
  satir?: number | null;
  kod?: string | null;
  alan?: string | null;
  deger?: string | null;
  neden: string;
}

/** Backend `semalar.YuklemeOzeti`: her önizleme yanıtında `ozet` alanı. */
export interface YuklemeOzetiT {
  okunan: number;
  yeni: number;
  degisen: number;
  ayni: number;
  silinecek: number;
  atlanan: number;
  sorunlu: SorunluSatirT[];
  uyarilar: string[];
}

const GOSTERILEN = 50;

/** Sorunlu satırların tümünü Excel olarak indirir (POST /api/v1/sablonlar/sorunlu-satirlar.xlsx). */
export function sorunluSatirlariIndir(baslik: string, satirlar: SorunluSatirT[]): Promise<void> {
  return dosyaIndir("/api/v1/sablonlar/sorunlu-satirlar.xlsx", "sorunlu-satirlar.xlsx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ baslik, satirlar }),
  });
}

/**
 * Önizleme kutusunun standart kısmı: okunan / yeni / değişen / aynı / silinecek / atlanan sayıları, uyarılar ve sorunlu satırlar
 * tablosu (ilk 50; "Tümünü Excel indir").
 */
export function YuklemeOzetiKutusu({ ozet, baslik = "Sorunlu satırlar" }: { ozet: YuklemeOzetiT; baslik?: string }) {
  const [indiriliyor, setIndiriliyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);
  const sayilar: [string, number][] = [
    ["Okunan", ozet.okunan],
    ["Yeni", ozet.yeni],
    ["Değişen", ozet.degisen],
    ["Aynı", ozet.ayni],
    ["Silinecek", ozet.silinecek],
    ["Atlanan", ozet.atlanan],
  ];

  async function indir() {
    setIndiriliyor(true);
    setHata(null);
    try {
      await sorunluSatirlariIndir(baslik, ozet.sorunlu);
    } catch (e) {
      setHata(e instanceof Error ? e.message : "İndirilemedi");
    } finally {
      setIndiriliyor(false);
    }
  }

  return (
    <div className="flex flex-col gap-2" aria-label="Yükleme özeti">
      <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {sayilar.map(([ad, n]) => (
          <div key={ad} className="flex gap-1">
            <dt className="text-muted-foreground">{ad}:</dt>
            <dd className={ad === "Silinecek" && n > 0 ? "font-semibold text-destructive" : "font-medium tabular-nums"}>{n}</dd>
          </div>
        ))}
        {ozet.sorunlu.length > 0 && (
          <div className="flex gap-1">
            <dt className="text-muted-foreground">Sorunlu:</dt>
            <dd className="font-semibold text-amber-700 dark:text-amber-400">{ozet.sorunlu.length}</dd>
          </div>
        )}
      </dl>
      {ozet.uyarilar.length > 0 && (
        <ul
          className="list-disc rounded-md bg-amber-50 py-2 pl-8 pr-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          aria-label="Uyarılar"
        >
          {ozet.uyarilar.map((u, i) => (
            <li key={i}>{u}</li>
          ))}
        </ul>
      )}
      {ozet.sorunlu.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium">
              Sorunlu satırlar (yazılmaz){ozet.sorunlu.length > GOSTERILEN ? ` — ilk ${GOSTERILEN} / ${ozet.sorunlu.length}` : ""}
            </p>
            <Button type="button" variant="outline" size="sm" disabled={indiriliyor} onClick={indir}>
              <Download className="size-4" aria-hidden />
              {indiriliyor ? "Hazırlanıyor…" : "Tümünü Excel indir"}
            </Button>
          </div>
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
          <div className="max-h-64 overflow-auto rounded-md border">
            <table className="w-full text-sm" aria-label="Sorunlu satırlar">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-2 py-1 font-medium">Satır</th>
                  <th className="px-2 py-1 font-medium">Kod</th>
                  <th className="px-2 py-1 font-medium">Alan</th>
                  <th className="px-2 py-1 font-medium">Değer</th>
                  <th className="px-2 py-1 font-medium">Neden</th>
                </tr>
              </thead>
              <tbody>
                {ozet.sorunlu.slice(0, GOSTERILEN).map((s, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-2 py-1 tabular-nums">{s.satir ?? "—"}</td>
                    <td className="px-2 py-1">{s.kod ?? "—"}</td>
                    <td className="px-2 py-1">{s.alan ?? "—"}</td>
                    <td className="px-2 py-1">{s.deger ?? "—"}</td>
                    <td className="px-2 py-1">{s.neden}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
