import { useState, type FormEvent } from "react";
import type { ApiHatasi } from "@/api/istemci";
import { useYaOlursa, type YaOlursaVarsayimi } from "@/api/sorgular/analiz";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { AnalizSonucu } from "@/sayfalar/analiz/AnalizSonucu";
import { D } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";

const ALANLAR: { ad: keyof YaOlursaVarsayimi; etiket: string; aciklama: string }[] = [
  { ad: "kur", etiket: "Döviz kuru", aciklama: "USD, EUR ve diğer tüm kurlar" },
  { ad: "ambalaj", etiket: "Ambalaj fiyatları", aciklama: "kavanoz, kapak, etiket, koli…" },
  { ad: "hammadde", etiket: "Hammadde fiyatları", aciklama: "biber, zeytin, salça…" },
  { ad: "adet", etiket: "Üretim adedi", aciklama: "vardiya üretim adedi (giderler buna bölünür)" },
];

type Metinler = Record<keyof YaOlursaVarsayimi, string>;
const BOS: Metinler = { kur: "", ambalaj: "", hammadde: "", adet: "" };

/** "10" -> "0.1"; boş -> "0"; geçersiz -> null. Eksi (düşüş) girilebilir. */
function oran(metin: string): string | null {
  if (metin.trim() === "") return "0";
  const a = sayiApi(metin.replace("%", ""), true);
  return a === null ? null : D(a).dividedBy(100).toFixed();
}

/**
 * Ya olursa: kur, ambalaj, hammadde ve üretim adedi için yüzde değişim yazılır; "Hesapla" ile tüm ürünler kaydetmeden yeniden hesaplanır.
 * Satış fiyatı aynı kalırsa kâr oranının marj eşiğinin altına düştüğü ürünler işaretlenir.
 */
export default function YaOlursa() {
  const { senaryoId } = useSenaryo();
  const [metin, setMetin] = useState<Metinler>(BOS);
  const [uygulanan, setUygulanan] = useState<YaOlursaVarsayimi | null>(null);
  const q = useYaOlursa(senaryoId, uygulanan);
  const oranlar = Object.fromEntries(ALANLAR.map((a) => [a.ad, oran(metin[a.ad])])) as Record<keyof YaOlursaVarsayimi, string | null>;
  const gecersiz = ALANLAR.filter((a) => oranlar[a.ad] === null);

  function hesapla(e: FormEvent) {
    e.preventDefault();
    if (gecersiz.length) return;
    setUygulanan(oranlar as YaOlursaVarsayimi);
  }

  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Ya olursa"
        altBaslik="Kur, ambalaj, hammadde ya da üretim adedi değişirse maliyet ve kâr ne olur? Hiçbir şey kaydedilmez."
      />
      <form onSubmit={hesapla} aria-label="Varsayımlar" className="flex flex-col gap-3 rounded-xl border bg-card p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {ALANLAR.map((a) => (
            <label key={a.ad} className="flex flex-col gap-1 text-sm">
              <span className="font-medium">{a.etiket}</span>
              <span className="flex items-center gap-1.5">
                <Input
                  inputMode="decimal"
                  aria-label={`${a.etiket} değişimi (%)`}
                  placeholder="0"
                  className="w-24 text-right tabular-nums"
                  value={metin[a.ad]}
                  aria-invalid={oranlar[a.ad] === null || undefined}
                  onChange={(e) => setMetin({ ...metin, [a.ad]: e.target.value })}
                />
                <span className="text-muted-foreground">%</span>
              </span>
              <span className="text-xs text-muted-foreground">{a.aciklama}</span>
            </label>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={senaryoId === null || gecersiz.length > 0 || q.isFetching}>
            {q.isFetching ? "Hesaplanıyor…" : "Hesapla"}
          </Button>
          <Button type="button" variant="outline" onClick={() => setMetin(BOS)}>
            Temizle
          </Button>
          <span className="text-xs text-muted-foreground">
            Artış için 10, düşüş için -10 yazın. Tüm ürünler hesaplandığı için birkaç saniye sürebilir.
          </span>
        </div>
        {gecersiz.length > 0 && (
          <p role="alert" className="text-sm text-destructive">
            {gecersiz.map((a) => a.etiket).join(", ")}: sayı yazın (ör. 10 ya da -5).
          </p>
        )}
      </form>
      {uygulanan === null ? (
        <p className="rounded-xl border border-dashed bg-card p-5 text-sm text-muted-foreground">
          Varsayımları yazıp Hesapla'ya basın; sonuçta en çok etkilenen ürünler üstte listelenir.
        </p>
      ) : (
        <AnalizSonucu
          ozet={q.data?.ozet}
          kayitlar={q.data?.kayitlar ?? []}
          marjEsigi={q.data?.marj_esigi}
          yukleniyor={q.isPending}
          hata={q.error as ApiHatasi | null}
          bosMetin="Ürün yok"
        />
      )}
    </section>
  );
}
