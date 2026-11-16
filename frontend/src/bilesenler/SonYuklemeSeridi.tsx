import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Undo2 } from "lucide-react";
import { api, cagir, hataMetni } from "@/api/istemci";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { Button } from "@/bilesenler/ui/button";

/** Backend `semalar.SonYukleme`. */
export interface SonYuklemeT {
  id: number;
  zaman: string | null;
  olusturan: string;
  ozet: string;
  kaynak_dosya: string | null;
}

type Sorgu = Record<string, string | number>;

function adres(yol: string, sorgu: Sorgu): string {
  const q = new URLSearchParams(Object.entries(sorgu).map(([k, v]) => [k, String(v)])).toString();
  return q ? `${yol}?${q}` : yol;
}

function zamanMetni(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return "";
  const iki = (n: number) => String(n).padStart(2, "0");
  return `${iki(d.getDate())}.${iki(d.getMonth() + 1)}.${d.getFullYear()} ${iki(d.getHours())}:${iki(d.getMinutes())}`;
}

/** Son yükleme sorgusunun anahtarı: bir yükleme başarıyla yazınca bu önekle tazelenmeli (`["son-yukleme"]`). */
export const SON_YUKLEME_ANAHTARI = "son-yukleme";

interface Props {
  /** Uçların ortak öneki, ör. "/api/v1/import/fiyat-listesi" → `${yol}/son-yukleme`, `${yol}/son-yuklemeyi-geri-al`. */
  yol: string;
  /** Sorgu parametreleri (ör. { senaryo: 3 } ya da { donem: 7 }). */
  sorgu: Sorgu;
  /** Yazma kilidi (useYazmaKilidi().kilitli); true ise Geri al pasif. */
  kilitli?: boolean;
  kilitNedeni?: string;
  /** Geri alınca tazelenecek sorgu önekleri. */
  gecersiz?: string[];
}

/** "Son yükleme: 16.11.2026 14:20, esma, 312 fiyat — Geri al" şeridi; geri alınacak yükleme yoksa hiçbir şey göstermez. */
export function SonYuklemeSeridi({ yol, sorgu, kilitli = false, kilitNedeni, gecersiz = [] }: Props) {
  const qc = useQueryClient();
  const [soruluyor, setSoruluyor] = useState(false);
  const son = useQuery({
    queryKey: [SON_YUKLEME_ANAHTARI, yol, sorgu],
    queryFn: () => cagir(api.GET(adres(`${yol}/son-yukleme`, sorgu) as never)) as unknown as Promise<{ son: SonYuklemeT | null }>,
  });
  const geriAl = useMutation({
    mutationFn: () =>
      cagir(api.POST(adres(`${yol}/son-yuklemeyi-geri-al`, sorgu) as never, {} as never)) as unknown as Promise<{ mesaj: string }>,
    onSuccess: () => {
      setSoruluyor(false);
      return Promise.all([SON_YUKLEME_ANAHTARI, ...gecersiz].map((k) => qc.invalidateQueries({ queryKey: [k] })));
    },
  });
  const y = son.data?.son;

  return (
    <div aria-live="polite">
      {geriAl.isSuccess && (
        <p role="status" className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-900 dark:bg-green-950/40 dark:text-green-200">
          {geriAl.data.mesaj}
        </p>
      )}
      {y && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-dashed px-3 py-2 text-sm" aria-label="Son yükleme">
          <span className="text-muted-foreground">Son yükleme:</span>
          <span>
            {[zamanMetni(y.zaman), y.olusturan, y.ozet].filter(Boolean).join(", ")}
            {y.kaynak_dosya ? ` (${y.kaynak_dosya})` : ""}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={kilitli || geriAl.isPending}
            title={kilitli ? kilitNedeni : undefined}
            onClick={() => {
              geriAl.reset();
              setSoruluyor(true);
            }}
          >
            <Undo2 className="size-4" aria-hidden />
            Geri al
          </Button>
        </div>
      )}
      {soruluyor && y && (
        <OnayDiyalogu
          baslik="Son yüklemeyi geri al"
          onayMetni="Geri al"
          bekliyor={geriAl.isPending}
          hata={geriAl.error ? hataMetni(geriAl.error) : null}
          onOnayla={() => geriAl.mutate()}
          onVazgec={() => setSoruluyor(false)}
        >
          <p>
            {y.ozet} yüklemesi geri alınacak; veri yüklemeden önceki haline döner. Bu yüklemeden sonra elle yapılan değişiklikler de
            kaybolabilir.
          </p>
        </OnayDiyalogu>
      )}
    </div>
  );
}
