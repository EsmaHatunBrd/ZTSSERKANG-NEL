import { Fragment, lazy, Suspense, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Download, Info } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import {
  ONEM_ESIKLERI,
  onemEsigi,
  onemliMalzemelerXlsxAdresi,
  useOnemliMalzemeler,
  VARSAYILAN_ESIK,
} from "@/api/sorgular/onemliMalzemeler";
import type { OnemliMalzemeSatiri } from "@/api/tipler";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { buttonVariants } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";

const ParetoGrafigi = lazy(() => import("./onemliMalzemeler/ParetoGrafigi").then((m) => ({ default: m.ParetoGrafigi })));

/** Sunucudan yüzde metni gelir ("12.34" = %12,34): "%12,3". */
const yuzdeMetni = (p: string) => `%${paraBicimle(p, "", 1).trim()}`;
/** Türkçe belirtme eki: "%80'ini", "%90'ını". */
const esikMetni = (esik: number) => `%${esik}'${esik === 90 ? "ını" : "ini"}`;
const sayiMetni = (x: string, basamak: number) => paraBicimle(x, "", basamak).trim();
/**
 * Maliyete giren (enflasyon/kur dahil) birim fiyat: yıllık tutar ÷ yıllık miktar, TL, 4 hane (Decimal). Miktar 0 ise "—"; tutar 0
 * (fiyatsız kalem) ise de "—" (0,0000 TL fiyat varmış gibi okunmasın).
 */
function maliyeteGirenBirimFiyat(r: Pick<OnemliMalzemeSatiri, "yillik_tutar_tl" | "yillik_miktar">): string {
  const miktar = D(r.yillik_miktar);
  const tutar = D(r.yillik_tutar_tl);
  return miktar.isZero() || tutar.isZero() ? "—" : paraBicimle(tutar.div(miktar), "TL", 4);
}

/** Adres çubuğundaki parametreyle eşlenen yerel durum (bkz. FiyatEgilimi): denetim anında değişir, adres dışarıdan değişirse ona uyar. */
function useAdresDegeri<T>(ham: string | null, coz: (ham: string | null) => T): [T, (t: T) => void] {
  const [kaynak, setKaynak] = useState(ham);
  const [deger, setDeger] = useState(() => coz(ham));
  if (kaynak !== ham) {
    setKaynak(ham);
    setDeger(coz(ham));
  }
  return [deger, setDeger];
}

/**
 * Önemli malzemeler (80/20): yıllık üretim adediyle ağırlıklı malzeme tutarları büyükten küçüğe; toplam tutarın eşik kadarını (%70/80/90)
 * oluşturan malzemeler vurgulanır. Eşik (`?esik=`) sunucuya gider; arama sayfa içidir. Sayfa yalnız okur (düzenleme kilidi kapsamı dışında).
 */
export default function OnemliMalzemeler() {
  const { senaryoId } = useSenaryo();
  const git = useNavigate();
  const [params, setParams] = useSearchParams();
  const [esik, setEsik] = useAdresDegeri(params.get("esik"), onemEsigi);
  const [arama, setArama] = useState("");
  const q = useOnemliMalzemeler(senaryoId, esik);
  const v = q.data;
  const tum = useMemo(() => v?.satirlar ?? [], [v]);

  const satirlar = useMemo(() => {
    const s = arama.trim().toLocaleLowerCase("tr");
    if (!s) return tum;
    return tum.filter((r) => r.kod.toLocaleLowerCase("tr").includes(s) || r.ad.toLocaleLowerCase("tr").includes(s));
  }, [tum, arama]);
  const fiyatsiz = useMemo(() => tum.filter((r) => D(r.yillik_tutar_tl).isZero()).length, [tum]);
  const araniyor = arama.trim() !== "";

  function esikSec(deger: string) {
    setEsik(onemEsigi(deger));
    setParams(
      (p) => {
        const y = new URLSearchParams(p);
        if (deger === String(VARSAYILAN_ESIK)) y.delete("esik");
        else y.set("esik", deger);
        return y;
      },
      { replace: true },
    );
  }

  /** Malzemenin fiyat kaydına gider (Zam etkisi sayfası adresten malzeme okumadığı için Malzeme Fiyatları araması). */
  function malzemeyeGit(r: OnemliMalzemeSatiri) {
    if (!r.kod) return;
    const p = new URLSearchParams();
    if (senaryoId !== null) p.set("senaryo", String(senaryoId));
    p.set("arama", r.kod);
    git(`/fiyatlar?${p.toString()}`);
  }

  const yukleniyor = q.isPending && senaryoId !== null;
  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Önemli malzemeler"
        altBaslik={`Maliyetin ${esikMetni(esik)} oluşturan malzemeler, yıllık üretim adediyle ağırlıklı`}
        eylemler={
          senaryoId !== null && (
            <a href={onemliMalzemelerXlsxAdresi(senaryoId, esik)} download className={cn(buttonVariants({ variant: "outline" }))}>
              <Download aria-hidden />
              Excel&apos;e aktar
            </a>
          )
        }
      />

      <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Eşik</span>
          <select
            aria-label="Eşik"
            className="h-9 rounded-lg border bg-background px-2 text-sm"
            value={esik}
            onChange={(e) => esikSec(e.target.value)}
          >
            {ONEM_ESIKLERI.map((e) => (
              <option key={e} value={e}>
                %{e}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Ara</span>
          <Input
            type="search"
            aria-label="Malzeme ara"
            placeholder="Kod ya da ad…"
            className="w-56"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
          />
        </label>
        {v && tum.length > 0 && (
          <p role="status" aria-label="Özet" className="ml-auto text-sm text-muted-foreground tabular-nums">
            <span className="font-semibold text-foreground">{v.esik_icindeki_sayi}</span> malzeme toplam tutarın {esikMetni(esik)}{" "}
            oluşturuyor (<span className="font-medium text-foreground">{tum.length}</span> malzemeden) · yıllık malzeme tutarı{" "}
            <span className="font-medium text-foreground">{paraBicimle(v.toplam_tutar_tl, "TL", 0)}</span>
          </p>
        )}
      </div>

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Yıllık tutar = ürünün yıllık adedi × o malzemenin üründeki (fireli) tutarı, tüm ürünlerde toplanır. Yıllık adet geçen yılın satış
          adedidir. Maliyete giren birim fiyat = yıllık tutar ÷ yıllık miktar (TL; enflasyon ve kur dahil); altındaki gri "liste" değeri
          fiyat listesindeki fiyattır ve malzemenin kendi para birimindedir. Fiyat kaydına gitmek için satıra tıklayın. Hiçbir şey
          kaydedilmez.
          {v && v.adetsiz_urun > 0 && (
            <span data-testid="adetsiz-notu">
              {" "}
              <strong className="font-medium text-foreground">{v.adetsiz_urun} ürünün</strong> yıllık adedi (geçen yıl satışı) olmadığı için
              hesaba girmedi.
            </span>
          )}
          {v && v.hatali_urun > 0 && <span> {v.hatali_urun} ürün hesaplanamadığı için hesaba girmedi.</span>}
          {fiyatsiz > 0 && <span> Tutarı 0 olan {fiyatsiz} kalem (fiyatsız ya da fiyat listesinde yok) listenin sonundadır.</span>}
        </span>
      </p>

      {q.error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}
      {yukleniyor && (
        <p role="status" className="text-sm text-muted-foreground">
          Yükleniyor…
        </p>
      )}

      {v && tum.length === 0 && (
        <div className="flex flex-col items-center gap-1 rounded-xl border border-dashed bg-card px-6 py-10 text-center">
          <p className="font-medium">Bu çalışmada yıllık adedi olan ürün yok</p>
          <p className="text-sm text-muted-foreground">
            Yıllık adet geçen yılın satış adedinden gelir; önce Satış Geçmişi&apos;ni yükleyin.
          </p>
        </div>
      )}

      {v && tum.length > 0 && (
        <>
          <div className="rounded-xl border bg-card p-4">
            <Suspense
              fallback={
                <div role="status" className="h-[300px] animate-pulse rounded-lg bg-muted" aria-label="Grafik yükleniyor">
                  <span className="sr-only">Grafik yükleniyor…</span>
                </div>
              }
            >
              <ParetoGrafigi satirlar={tum} esik={esik} />
            </Suspense>
          </div>

          <div className="min-w-0 overflow-x-auto rounded-xl border bg-card">
            <Table aria-label="Önemli malzemeler">
              <TableHeader>
                <TableRow>
                  <TableHead className="text-right">Sıra</TableHead>
                  <TableHead>Kod</TableHead>
                  <TableHead>Malzeme</TableHead>
                  <TableHead className="text-right">Maliyete giren birim fiyat (TL)</TableHead>
                  <TableHead className="text-right">Yıllık miktar</TableHead>
                  <TableHead className="text-right">Yıllık tutar</TableHead>
                  <TableHead className="text-right">Pay %</TableHead>
                  <TableHead className="text-right">Kümülatif %</TableHead>
                  <TableHead className="text-right">Kullanan ürün</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {satirlar.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={9} className="py-8 text-center text-muted-foreground">
                      Aramaya uyan malzeme yok
                    </TableCell>
                  </TableRow>
                )}
                {satirlar.map((r, i) => (
                  <Fragment key={`${r.sira}-${r.kod}`}>
                    {/* Eşik sınırı: eşik içindeki son satırdan sonra (arama yokken). */}
                    {!araniyor && i > 0 && satirlar[i - 1].esik_icinde && !r.esik_icinde && (
                      <TableRow data-testid="esik-ayraci" className="hover:bg-transparent">
                        <TableCell
                          colSpan={9}
                          className="border-y-2 border-primary/50 bg-muted/60 py-1 text-xs font-medium text-muted-foreground"
                        >
                          Eşik sınırı — yukarıdaki {v.esik_icindeki_sayi} malzeme toplam tutarın {esikMetni(esik)} oluşturuyor
                        </TableCell>
                      </TableRow>
                    )}
                    <TableRow
                      tabIndex={0}
                      data-esik-icinde={r.esik_icinde ? "evet" : "hayir"}
                      onClick={() => malzemeyeGit(r)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") malzemeyeGit(r);
                      }}
                      className={cn(
                        "cursor-pointer focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset",
                        r.esik_icinde && "bg-primary/5",
                      )}
                    >
                      <TableCell className="text-right tabular-nums text-muted-foreground">{r.sira}</TableCell>
                      <TableCell className="font-mono text-xs">{r.kod}</TableCell>
                      <TableCell>
                        <span className="flex flex-col">
                          <span className={r.esik_icinde ? "font-medium" : undefined}>{r.ad}</span>
                          {r.tip && <span className="text-xs text-muted-foreground">{r.tip}</span>}
                        </span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        <span className="flex flex-col items-end">
                          <span>{maliyeteGirenBirimFiyat(r)}</span>
                          {r.birim_fiyat !== null && (
                            <span className="text-xs text-muted-foreground">
                              liste {paraBicimle(r.birim_fiyat, r.para_birimi ?? "", 4)}
                            </span>
                          )}
                        </span>
                      </TableCell>
                      <TableCell className="text-right tabular-nums whitespace-nowrap">
                        {sayiMetni(r.yillik_miktar, 0)}
                        {r.birim && <span className="text-muted-foreground"> {r.birim}</span>}
                      </TableCell>
                      <TableCell className="text-right font-medium tabular-nums whitespace-nowrap">
                        {paraBicimle(r.yillik_tutar_tl, "TL", 0)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{yuzdeMetni(r.pay_yuzde)}</TableCell>
                      <TableCell className="text-right tabular-nums">{yuzdeMetni(r.kumulatif_yuzde)}</TableCell>
                      <TableCell className="text-right tabular-nums">{r.kullanan_urun_sayisi}</TableCell>
                    </TableRow>
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </section>
  );
}
