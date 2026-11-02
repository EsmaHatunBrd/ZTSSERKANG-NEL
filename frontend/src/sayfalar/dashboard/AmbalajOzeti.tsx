import { useAmbalajOzeti } from "@/api/sorgular/ambalaj";
import { hataMetni } from "@/api/istemci";

/** Üretim adedi: tam sayı gösterimi (Intl'e metin verilir, Number() ile hassasiyet kaybı olmaz). */
function adet(metin: string): string {
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 }).format(metin as unknown as number);
}

function Liste({ baslik, kayitlar }: { baslik: string; kayitlar: { ad: string; urunSayisi: number; uretimAdedi: string }[] }) {
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-xs font-medium text-muted-foreground">{baslik}</h3>
      {kayitlar.length === 0 ? (
        <p className="text-sm text-muted-foreground">Kayıt yok</p>
      ) : (
        <ul className="flex flex-col divide-y text-sm">
          {kayitlar.map((k) => (
            <li key={k.ad} className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-4 py-1">
              <span>{k.ad}</span>
              <span className="tabular-nums text-muted-foreground">{`${k.urunSayisi} ürün`}</span>
              <span className="min-w-24 text-right tabular-nums">{`${adet(k.uretimAdedi)} adet`}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Dashboard kartı (Excel `Ambalaj Özeti`): ambalaj türü ve kapak bazında ürün sayısı ile üretim adedi. */
export function AmbalajOzeti({ senaryoId }: { senaryoId: number }) {
  const sorgu = useAmbalajOzeti(senaryoId);
  return (
    <section aria-label="Ambalaj özeti" className="flex flex-col gap-3 p-4 text-card-foreground">
      <h2 className="sr-only">Ambalaj özeti</h2>
      {sorgu.isPending ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : sorgu.error ? (
        <p className="text-sm text-destructive">{hataMetni(sorgu.error)}</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <Liste
            baslik="Ambalaj türü"
            kayitlar={sorgu.data.turler.map((t) => ({ ad: t.tur, urunSayisi: t.urun_sayisi, uretimAdedi: t.uretim_adedi }))}
          />
          <Liste
            baslik="Kapak"
            kayitlar={sorgu.data.kapaklar.map((k) => ({ ad: k.ad, urunSayisi: k.urun_sayisi, uretimAdedi: k.uretim_adedi }))}
          />
        </div>
      )}
    </section>
  );
}
