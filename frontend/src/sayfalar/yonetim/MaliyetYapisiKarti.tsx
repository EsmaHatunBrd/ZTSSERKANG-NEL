import type { YonetimOzeti } from "@/api/tipler";
import { D, paraBicimle } from "@/yardimcilar/para";
import { puanMetni } from "./bicim";
import { YonetimKarti } from "./YonetimKarti";

/** Genel Bakış'taki Maliyet yapısı kartıyla aynı sıra ve renkler. */
const KALEMLER = [
  { anahtar: "malzeme", ad: "Malzeme", renk: "var(--chart-1)" },
  { anahtar: "uretim", ad: "Üretim gideri", renk: "var(--chart-2)" },
  { anahtar: "faaliyet", ad: "Faaliyet gideri", renk: "var(--chart-3)" },
  { anahtar: "finansman", ad: "Finansman", renk: "var(--chart-4)" },
] as const;

/** Maliyet yapısı: hesaplanan ürünlerin birim maliyet toplamında kalem payları (yığılı yatay çubuk + liste). */
export function MaliyetYapisiKarti({ yapi }: { yapi: YonetimOzeti["maliyet_yapisi"] }) {
  const paylar = KALEMLER.map((k) => ({
    ...k,
    ...(yapi.kalemler[k.anahtar] ?? { toplam_tl: "0", pay_yuzde: null, urun_basina_tl: null }),
  }));
  const genislik = (p: string | null) => (p === null ? "0%" : `${D(p).clamp(0, 100).toFixed(2)}%`);
  return (
    <YonetimKarti
      baslik="Maliyet yapısı"
      aciklama={`${yapi.urun_sayisi} hesaplanan ürünün birim maliyet toplamında kalemlerin payı · ürün başına ${
        yapi.urun_basina_tl === null ? "—" : paraBicimle(yapi.urun_basina_tl)
      }`}
    >
      {yapi.urun_sayisi === 0 ? (
        <p className="text-sm text-muted-foreground">Hesaplanan ürün yok.</p>
      ) : (
        <>
          <div className="flex h-4 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
            {paylar.map((p) => (
              <span key={p.anahtar} style={{ width: genislik(p.pay_yuzde), background: p.renk }} />
            ))}
          </div>
          <ul className="flex flex-col gap-2">
            {paylar.map((p) => (
              <li key={p.anahtar} className="flex flex-col gap-1">
                <span className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2">
                    <span className="size-2.5 rounded-sm" style={{ background: p.renk }} aria-hidden />
                    {p.ad}
                  </span>
                  <span className="flex items-baseline gap-2 tabular-nums">
                    <span className="text-xs text-muted-foreground">
                      ürün başına {p.urun_basina_tl === null ? "—" : paraBicimle(p.urun_basina_tl)}
                    </span>
                    <span className="font-semibold">{puanMetni(p.pay_yuzde)}</span>
                  </span>
                </span>
                <span className="h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
                  <span className="block h-full rounded-full" style={{ width: genislik(p.pay_yuzde), background: p.renk }} />
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </YonetimKarti>
  );
}
