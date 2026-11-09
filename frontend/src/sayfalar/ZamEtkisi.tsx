import { useEffect, useState, type FormEvent } from "react";
import { TriangleAlert } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { useZamEtkisi } from "@/api/sorgular/analiz";
import { useMalzemeler } from "@/api/sorgular/malzemeler";
import type { Malzeme } from "@/api/tipler";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { cn } from "@/lib/utils";
import { AnalizSonucu } from "@/sayfalar/analiz/AnalizSonucu";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";

/**
 * Zam etkisi: bir malzeme seçilir ve yüzde zam yazılır; o malzemeyi kullanan ürünlerin maliyeti kaydetmeden yeniden hesaplanır.
 * Satın almanın zam görüşmesinde "bu zam bize ürün başına ne kadara mal olur" sorusunu cevaplar.
 */
export default function ZamEtkisi() {
  const { senaryoId } = useSenaryo();
  const [arama, setArama] = useState("");
  const [gecikmeli, setGecikmeli] = useState("");
  const [secili, setSecili] = useState<Malzeme | null>(null);
  const [oranMetni, setOranMetni] = useState("10");
  const [uygulanan, setUygulanan] = useState<{ kod: string; oran: string } | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setGecikmeli(arama.trim()), 300);
    return () => clearTimeout(t);
  }, [arama]);

  const adaylar = useMalzemeler(gecikmeli.length >= 2 ? senaryoId : null, { arama: gecikmeli, boyut: 8 });
  const q = useZamEtkisi(senaryoId, uygulanan?.kod ?? null, uygulanan?.oran ?? null);
  const oranApi = oranMetni.trim() === "" ? null : sayiApi(oranMetni.replace("%", ""), true);
  const oran = oranApi === null ? null : D(oranApi).dividedBy(100).toFixed();

  // Fiyatı olmayan (0 / boş) kaleme zam uygulanamaz: sonuç hep "etkisiz" çıkar, kullanıcı nedenini göremez.
  const fiyatVar = Boolean(secili?.fiyat && !D(secili.fiyat).isZero());

  function hesapla(e: FormEvent) {
    e.preventDefault();
    if (secili && fiyatVar && oran !== null) setUygulanan({ kod: secili.kod, oran });
  }

  const m = q.data?.malzeme;
  const oz = q.data?.ozet;
  // Yazılan metin aramaya yansıyana (300 ms) ve sonuç gelene kadar eski liste gösterilmez: yanlış kaleme tıklanmasın.
  const araniyor = gecikmeli !== arama.trim() || adaylar.isPending || adaylar.isPlaceholderData;
  const secenekler = araniyor ? [] : (adaylar.data?.kayitlar ?? []);
  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Zam etkisi"
        altBaslik="Bir malzemeye zam gelirse onu kullanan ürünlerin maliyeti ve kârı ne olur? Hiçbir şey kaydedilmez."
      />
      <form onSubmit={hesapla} aria-label="Zam" className="flex flex-col gap-3 rounded-xl border bg-card p-4">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[2fr_1fr]">
          <div className="flex min-w-0 flex-col gap-1 text-sm">
            <label htmlFor="zam-malzeme" className="font-medium">
              Malzeme
            </label>
            <Input
              id="zam-malzeme"
              placeholder="Kod ya da ad yazın (en az 2 harf)"
              value={arama}
              onChange={(e) => {
                setArama(e.target.value);
                setSecili(null);
              }}
            />
            {secili ? (
              <>
                <p className="text-sm">
                  Seçili: <span className="font-medium">{secili.ad}</span> <span className="text-muted-foreground">({secili.kod})</span>
                  {fiyatVar && (
                    <span className="text-muted-foreground">
                      {" "}
                      · bugünkü fiyat {paraBicimle(secili.fiyat as string, secili.para_birimi || "TL", 4)}
                    </span>
                  )}
                </p>
                {!fiyatVar && (
                  <p role="alert" className="flex items-start gap-2 rounded-lg bg-kart-sari px-3 py-2 text-sm">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-700" aria-hidden />
                    <span>
                      Bu kalemin satın alma fiyatı yok (0 TL). Yarı mamul ya da fiyatı girilmemiş bir malzeme olabilir; zam uygulanacak bir
                      fiyat olmadığı için hiçbir ürünün maliyeti değişmez. İçindeki hammadde ya da ambalaja zam deneyin
                      {secili.tip ? ` (bu kalemin türü: ${secili.tip.replace(/^\d+-/, "")})` : ""}.
                    </span>
                  </p>
                )}
              </>
            ) : (
              gecikmeli.length >= 2 && (
                <ul aria-label="Malzeme seçenekleri" className="flex max-h-64 flex-col overflow-y-auto rounded-lg border">
                  {secenekler.length === 0 && (
                    <li className="px-3 py-2 text-muted-foreground">{araniyor ? "Aranıyor…" : "Eşleşen malzeme yok"}</li>
                  )}
                  {secenekler.map((x) => (
                    <li key={x.kod}>
                      <button
                        type="button"
                        className={cn("flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left hover:bg-accent/60")}
                        onClick={() => {
                          setSecili(x);
                          setArama(x.ad ?? x.kod);
                        }}
                      >
                        <span className="min-w-0 truncate">{x.ad ?? x.kod}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {x.kod}
                          {x.tip ? ` · ${x.tip.replace(/^\d+-/, "")}` : ""}
                          {" · "}
                          {x.fiyat && !D(x.fiyat).isZero() ? (
                            paraBicimle(x.fiyat, x.para_birimi || "TL", 2)
                          ) : (
                            <span className="text-amber-700 dark:text-amber-400">fiyat yok</span>
                          )}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )
            )}
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Zam</span>
            <span className="flex items-center gap-1.5">
              <Input
                inputMode="decimal"
                aria-label="Zam oranı (%)"
                placeholder="ör. 10"
                className="w-24 text-right tabular-nums"
                value={oranMetni}
                aria-invalid={(oranMetni.trim() !== "" && oran === null) || undefined}
                onChange={(e) => setOranMetni(e.target.value)}
              />
              <span className="text-muted-foreground">%</span>
            </span>
            <span className="text-xs text-muted-foreground">İndirim için eksi yazın (ör. -5).</span>
          </label>
        </div>
        <div>
          <Button type="submit" disabled={!secili || !fiyatVar || oran === null || q.isFetching}>
            {q.isFetching ? "Hesaplanıyor…" : "Hesapla"}
          </Button>
        </div>
      </form>
      {m && (
        <p className="text-sm">
          <span className="font-medium">{m.ad}</span>: {m.fiyat ? paraBicimle(m.fiyat, m.para_birimi || "TL", 4) : "fiyat yok"}
          {m.yeni_fiyat && ` → ${paraBicimle(m.yeni_fiyat, m.para_birimi || "TL", 4)}`}. Bu malzemeyi {oz?.urun_sayisi ?? 0} ürün kullanıyor
          {oz && oz.urun_sayisi > 0 && (
            <>
              ; <b>{oz.etkilenen}</b> ürünün maliyeti değişiyor
              {oz.ort_fark_yuzde !== null && (
                <>
                  , ortalama <b>{yuzdeBicimle(oz.ort_fark_yuzde, 2)}</b>
                </>
              )}
              {oz.en_yuksek_fark_yuzde !== null && <>, en çok {yuzdeBicimle(oz.en_yuksek_fark_yuzde, 2)}</>}
              {oz.esik_alti > 0 && <> · {oz.esik_alti} ürün fiyat aynı kalırsa hedef marjın altına düşüyor</>}
            </>
          )}
          .
        </p>
      )}
      {uygulanan === null ? (
        <p className="rounded-xl border border-dashed bg-card p-5 text-sm text-muted-foreground">
          Malzemeyi seçip zam oranını yazın; sonuçta etkilenen ürünler en çok etkilenen üstte listelenir.
        </p>
      ) : (
        <AnalizSonucu
          ozet={q.data?.ozet}
          kayitlar={q.data?.kayitlar ?? []}
          marjEsigi={q.data?.marj_esigi}
          yukleniyor={q.isPending}
          hata={q.error as ApiHatasi | null}
          bosMetin="Bu malzemeyi kullanan ürün yok"
        />
      )}
    </section>
  );
}
