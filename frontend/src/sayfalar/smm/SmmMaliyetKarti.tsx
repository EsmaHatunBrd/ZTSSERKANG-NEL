import { lazy, Suspense } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Printer } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useSmmMaliyetKarti } from "@/api/sorgular/smm";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { DonemSecici, DonemYok, Miktar, useSmmDonemSecimi } from "./ortak";

const AsamaGrafigi = lazy(() => import("./AsamaGrafigi").then((m) => ({ default: m.AsamaGrafigi })));

const tl4 = (x: string) => paraBicimle(x, "TL", 4);
const KAYNAK_ADI: Record<string, string> = {
  ortalama: "dönem ortalama fiyatı",
  envanter: "envanter birim fiyatı",
  asama_20: "20 aşama maliyeti",
  asama_40: "40 aşama maliyeti",
  envanter_bolen: "envanter birim fiyatı (bölünerek)",
  excel_elle: "Excel'de elle yazılmış fiyat",
  kod_bosluklu: "kodda boşluk: fiyat 0",
  yok: "fiyat bulunamadı",
};

/**
 * Ürün birim maliyet kartı: toplam birim maliyet ve önceki aya fark, aşama aşama döküm (grafik + tablo) ve reçete satırları.
 * Üretim Maliyeti ve Bütçe Kıyası sayfalarından açılır; yazdırılabilir.
 */
export default function SmmMaliyetKarti() {
  const { kod = "" } = useParams();
  const secim = useSmmDonemSecimi();
  const q = useSmmMaliyetKarti(secim.donemId, kod || null);
  const v = q.data;
  const geri = `/smm/uretim${secim.donemId !== null ? `?donem=${secim.donemId}` : ""}`;

  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Ürün maliyet kartı" />
        <DonemYok />
      </section>
    );
  }

  const o = v?.onceki ?? null;
  const artti = o !== null && D(o.fark_tl).gt(0);
  return (
    <div data-yazdir="" className="flex flex-col gap-5">
      <header className="flex flex-col gap-2">
        <SayfaBasligi
          baslik={v?.ad ?? kod}
          altBaslik={v ? `${v.donem.ad} · ${v.asama} aşaması · birim maliyet kartı` : "Birim maliyet kartı"}
          eylemler={
            <span className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
                <Printer aria-hidden />
                Yazdır
              </Button>
              <DonemSecici secim={secim} />
            </span>
          }
        />
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant="outline">{kod}</Badge>
          <Link to={geri} className="inline-flex items-center gap-1 text-primary underline-offset-4 hover:underline">
            <ArrowLeft className="size-3.5" aria-hidden /> Üretim Maliyeti
          </Link>
        </p>
      </header>

      {q.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}
      {q.isPending && secim.donemId !== null && <p className="text-sm text-muted-foreground">Hesaplanıyor…</p>}

      {v && (
        <>
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="flex flex-col rounded-2xl bg-kart-yesil p-4">
              <dt className="text-sm text-muted-foreground">Toplam birim maliyet</dt>
              <dd className="text-2xl font-semibold tabular-nums">{tl4(v.birim_maliyet)}</dd>
              {v.alim_kurali && <dd className="text-xs text-muted-foreground">Alım fiyatı esas alındı ({tl4(v.alim_fiyati)})</dd>}
            </div>
            <div className="flex flex-col rounded-2xl border bg-card p-4 shadow-xs">
              <dt className="text-sm text-muted-foreground">Önceki aya göre</dt>
              {o === null ? (
                <dd className="text-sm text-muted-foreground">Önceki dönemde bu ürünün maliyeti yok.</dd>
              ) : (
                <>
                  <dd
                    className={cn(
                      "text-2xl font-semibold tabular-nums",
                      D(o.fark_tl).isZero() ? "" : artti ? "text-red-600 dark:text-red-400" : "text-green-700 dark:text-green-400",
                    )}
                  >
                    {artti ? "+" : ""}
                    {tl4(o.fark_tl)}
                    {o.fark_yuzde !== null && (
                      <span className="ml-2 text-base font-medium">
                        ({artti ? "+" : ""}
                        {yuzdeBicimle(o.fark_yuzde)})
                      </span>
                    )}
                  </dd>
                  <dd className="text-xs text-muted-foreground">
                    {o.donem.ad}: {tl4(o.birim_maliyet)}
                  </dd>
                </>
              )}
            </div>
            <div className="flex flex-col rounded-2xl border bg-card p-4 shadow-xs">
              <dt className="text-sm text-muted-foreground">Bu dönem üretim</dt>
              <dd className="text-2xl font-semibold tabular-nums">
                {D(v.uretim_miktar).isZero()
                  ? "—"
                  : `${new Intl.NumberFormat("tr-TR").format(D(v.uretim_miktar).toNumber())} ${v.birim ?? ""}`}
              </dd>
              <dd className="text-xs text-muted-foreground">Toplam maliyet {paraBicimle(v.toplam, "TL", 0)}</dd>
            </div>
          </dl>

          <section aria-label="Aşama dökümü" className="flex flex-col gap-4 rounded-2xl border bg-card p-5 shadow-xs">
            <h2 className="text-base font-semibold">Aşama aşama birim maliyet</h2>
            <Suspense fallback={<p className="text-sm text-muted-foreground">Grafik yükleniyor…</p>}>
              <AsamaGrafigi asamalar={v.asamalar} />
            </Suspense>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Aşamalara göre birim maliyet dökümü</caption>
                <thead>
                  <tr className="text-left text-xs text-muted-foreground uppercase">
                    <th scope="col" className="py-1.5 font-medium">
                      Aşama
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Malzeme
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      İşçilik
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      GÜG
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Fire
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Birim maliyet
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Üretim
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {v.asamalar.map((a) => (
                    <tr key={`${a.asama}-${a.kod}`} className="align-top">
                      <th scope="row" className="min-w-[14rem] py-1.5 text-left font-normal">
                        <span className="block font-medium">
                          {a.asama} · {a.ad}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {a.urun_ad ?? a.kod} · {a.kod}
                          {a.carpan !== null && ` · üst ürünün biriminde ${paraBicimle(a.carpan, "", 4)} ${a.birim ?? ""}`}
                          {a.alim_kurali && " · alım fiyatı esas"}
                          {(a.elle_alanlar ?? []).length > 0 && " · elle değer var"}
                        </span>
                      </th>
                      <td className="py-1.5 pl-3 text-right whitespace-nowrap tabular-nums">{tl4(a.malzeme)}</td>
                      <td className="py-1.5 pl-3 text-right whitespace-nowrap tabular-nums">{tl4(a.iscilik)}</td>
                      <td className="py-1.5 pl-3 text-right whitespace-nowrap tabular-nums">{tl4(a.gug)}</td>
                      <td className="py-1.5 pl-3 text-right whitespace-nowrap tabular-nums">{tl4(a.fire)}</td>
                      <td className="py-1.5 pl-3 text-right font-semibold whitespace-nowrap tabular-nums">{tl4(a.birim_maliyet)}</td>
                      <td className="py-1.5">
                        <Miktar deger={a.uretim_miktar} birim={a.birim} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-muted-foreground">
              Her satır o aşama ürününün kendi biriminin maliyetidir. Üst aşamanın malzemesi, alt aşamadan gelen yarı mamulün maliyetini
              içerir; satırlar bu yüzden toplanmaz. 20 ve 50 aşamalarında işçilik sütunu işçilik + genel üretim giderini birlikte taşır.
            </p>
          </section>

          <section aria-label="Reçete satırları" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
            <h2 className="text-base font-semibold">
              Reçete satırları <span className="font-normal text-muted-foreground">({v.asama} aşaması)</span>
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="sr-only">Reçete satırları</caption>
                <thead>
                  <tr className="text-left text-xs text-muted-foreground uppercase">
                    <th scope="col" className="py-1.5 font-medium">
                      Malzeme
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Miktar
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Birim fiyat
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Tutar
                    </th>
                    <th scope="col" className="py-1.5 pl-3 text-right font-medium">
                      Fire
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {v.satirlar.map((s, i) => (
                    <tr key={`${s.malzeme_kod}-${i}`} className="align-top">
                      <td className="min-w-[14rem] py-1.5">
                        <span className="block">{s.malzeme_ad ?? s.malzeme_kod}</span>
                        <span className="block text-xs text-muted-foreground">
                          {s.malzeme_kod} · {KAYNAK_ADI[s.fiyat_kaynagi] ?? s.fiyat_kaynagi}
                        </span>
                      </td>
                      <td className="py-1.5">
                        <Miktar deger={s.carpan} birim={s.birim} />
                      </td>
                      <td
                        className={cn(
                          "py-1.5 pl-3 text-right whitespace-nowrap tabular-nums",
                          s.fiyat_kaynagi === "yok" && "text-red-600 dark:text-red-400",
                        )}
                      >
                        {tl4(s.fiyat)}
                      </td>
                      <td className="py-1.5 pl-3 text-right font-medium whitespace-nowrap tabular-nums">{tl4(s.tutar)}</td>
                      <td className="py-1.5 pl-3 text-right whitespace-nowrap tabular-nums">
                        {D(s.fire_tutari).isZero() ? <span className="text-muted-foreground">—</span> : tl4(s.fire_tutari)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
