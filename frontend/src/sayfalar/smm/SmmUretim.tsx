import { useMemo, useState } from "react";
import { ArrowRight, Pencil, TriangleAlert } from "lucide-react";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useSmmDagitim, useSmmUretim, useSmmUrunElle, useSmmUrunRecetesi } from "@/api/sorgular/smm";
import type { SmmAsamaUrunu, SmmDagitim } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/bilesenler/ui/sheet";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { DonemSecici, DonemYok, Miktar, milyon, useGecikmeli, useSmmDonemSecimi } from "./ortak";

const KAYNAK_ADI: Record<string, string> = {
  ortalama: "Dönem ortalama fiyatı",
  envanter: "Envanter birim fiyatı",
  asama_20: "20 aşama maliyeti",
  asama_40: "40 aşama maliyeti",
  envanter_bolen: "Envanter birim fiyatı, Excel'de bölünerek (ör. rulodan metreye)",
  excel_elle: "Excel'de elle yazılmış fiyat",
  kod_bosluklu: "Kodda boşluk var: Excel kartı bulamıyor, fiyat 0",
  yok: "Fiyat bulunamadı",
};

const ANAHTAR_SECENEK_ADI: Record<string, string> = {
  uretim: "Üretim miktarı",
  dolum_sn: "Üretim × dolum sn",
  dolum_adam_sn: "Üretim × dolum adam-sn",
  etiket_sn: "Üretim × etiket sn",
  etiket_adam_sn: "Üretim × etiket adam-sn",
};
const ELLE_ALAN_ADI: Record<string, string> = {
  malzeme: "Malzeme",
  iscilik: "İşçilik",
  gug: "Genel üretim gideri",
  fire: "Fire",
  birim_maliyet: "Birim maliyet",
};

/** Aşama değeri: hesaplanan ya da elle girilen; kalemle elle girilir, "formüle dön" ile geri alınır. */
function ElleDeger({
  alan,
  deger,
  elle,
  bekliyor,
  onKaydet,
}: {
  alan: string;
  deger: string;
  elle: boolean;
  bekliyor: boolean;
  onKaydet: (v: string | null) => void;
}) {
  const [duzenle, setDuzenle] = useState(false);
  const [metin, setMetin] = useState(kutu(deger));
  const api = sayiApi(metin);
  return (
    <>
      <dt className="flex items-center gap-1.5 text-muted-foreground">
        {ELLE_ALAN_ADI[alan]}
        {elle && <span className="rounded-full bg-kart-sari px-1.5 text-[11px] font-medium text-foreground">Elle</span>}
      </dt>
      <dd className="flex items-center justify-end gap-1 tabular-nums">
        {duzenle ? (
          <>
            <Input
              aria-label={`${ELLE_ALAN_ADI[alan]} (elle)`}
              inputMode="decimal"
              className="h-7 w-32 text-right"
              value={metin}
              onChange={(e) => setMetin(e.target.value)}
            />
            <Button type="button" size="sm" disabled={api === null || bekliyor} onClick={() => (onKaydet(api), setDuzenle(false))}>
              Kaydet
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setDuzenle(false)}>
              Vazgeç
            </Button>
          </>
        ) : (
          <>
            <span className={cn(alan === "birim_maliyet" && "font-semibold")}>{paraBicimle(deger, "TL", 4)}</span>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              aria-label={`${ELLE_ALAN_ADI[alan]} elle gir`}
              onClick={() => {
                setMetin(kutu(deger));
                setDuzenle(true);
              }}
            >
              <Pencil className="size-3.5" />
            </Button>
            {elle && (
              <Button type="button" size="sm" variant="ghost" disabled={bekliyor} onClick={() => onKaydet(null)}>
                Formüle dön
              </Button>
            )}
          </>
        )}
      </dd>
    </>
  );
}

/** API sayı metni -> giriş kutusu metni ("5720896.74" -> "5720896,74"). */
const kutu = (x: string) => D(x).toFixed().replace(".", ",");

/** Dağıtılan işçilik ve genel üretim gideri havuzları (Excel aşama sayfalarının 1. satırı); değiştirilebilir. */
function DagitimKarti({ donemId, dagitim }: { donemId: number; dagitim: SmmDagitim }) {
  const kaydet = useSmmDagitim(donemId);
  const [taslak, setTaslak] = useState<Record<string, string>>({});
  const degisen = Object.entries(taslak).filter(([k, v]) => {
    const h = dagitim.havuzlar.find((x) => x.anahtar === k);
    return h && v !== kutu(h.tutar);
  });
  const gecersiz = degisen.some(([, v]) => sayiApi(v) === null);
  return (
    <details className="group rounded-2xl border bg-card shadow-xs">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-1 px-5 py-4">
        <span className="text-base font-semibold">Dağıtılan işçilik ve genel gider</span>
        <span className="text-sm text-muted-foreground">
          {paraBicimle(dagitim.dagitilan, "TL", 0)} dağıtıldı
          {dagitim.dagitilmayan !== null && <> · mizan 720 + 730: {paraBicimle(D(dagitim.mizan_720).plus(dagitim.mizan_730), "TL", 0)}</>}
        </span>
        <span className="ml-auto text-sm font-medium text-primary group-open:hidden">Göster / değiştir</span>
      </summary>
      <div className="flex flex-col gap-3 border-t px-5 py-4">
        <p className="text-sm text-muted-foreground">
          Tutarlar Excel'deki aşama sayfalarının ilk satırından geldi. Değiştirirseniz aşama maliyetleri yeniden hesaplanır; Excel'deki ilk
          değer yanında kalır.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          {dagitim.havuzlar.map((h) => (
            <label key={h.anahtar} className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">
                {h.ad}
                {h.degisti && (
                  <span className="ml-1 text-xs text-amber-700 dark:text-amber-400">(Excel: {paraBicimle(h.excel, "TL", 0)})</span>
                )}
              </span>
              <Input
                inputMode="decimal"
                aria-label={h.ad}
                value={taslak[h.anahtar] ?? kutu(h.tutar)}
                onChange={(e) => setTaslak((t) => ({ ...t, [h.anahtar]: e.target.value }))}
              />
            </label>
          ))}
        </div>
        <div className="flex flex-col gap-2 rounded-xl bg-muted/50 p-3">
          <p className="text-sm font-medium">Dağıtım anahtarı: havuz ürünlere neye göre dağıtılsın?</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {(dagitim.anahtarlar ?? []).map((a) => (
              <label key={a.anahtar} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-muted-foreground">
                  {a.ad}
                  {a.alan !== a.excel_varsayilani && (
                    <span className="ml-1 text-xs text-amber-700 dark:text-amber-400">
                      (Excel: {ANAHTAR_SECENEK_ADI[a.excel_varsayilani]})
                    </span>
                  )}
                </span>
                <select
                  aria-label={`Dağıtım anahtarı — ${a.ad}`}
                  className="h-8 rounded-lg border border-input bg-background px-2 text-sm"
                  value={a.alan}
                  disabled={kaydet.isPending}
                  onChange={(e) => kaydet.mutate({ anahtarlar: { [a.anahtar]: e.target.value } })}
                >
                  {Object.entries(ANAHTAR_SECENEK_ADI).map(([k, ad]) => (
                    <option key={k} value={k}>
                      {ad}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            Süreler "Üretim Süreleri" ekranından düzenlenir; süre × üretim miktarı oranında dağıtılır.
          </p>
        </div>
        {dagitim.dagitilmayan !== null && (
          <p className="text-sm">
            Gider mizanı: 720 direkt işçilik {paraBicimle(dagitim.mizan_720, "TL", 0)}, 730 genel üretim{" "}
            {paraBicimle(dagitim.mizan_730, "TL", 0)}. Aşamalara dağıtılmayan: <b>{paraBicimle(dagitim.dagitilmayan, "TL", 0)}</b>.
          </p>
        )}
        {kaydet.error && (
          <p role="alert" className="text-sm text-destructive">
            {hataMetni(kaydet.error)}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" size="sm" disabled={degisen.length === 0} onClick={() => setTaslak({})}>
            Vazgeç
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={degisen.length === 0 || gecersiz || kaydet.isPending}
            onClick={() =>
              kaydet.mutate(
                { havuzlar: Object.fromEntries(degisen.map(([k, v]) => [k, sayiApi(v) as string])) },
                { onSuccess: () => setTaslak({}) },
              )
            }
          >
            {kaydet.isPending ? "Kaydediliyor…" : "Kaydet ve yeniden hesapla"}
          </Button>
        </div>
      </div>
    </details>
  );
}

/** Ürünün reçete satırları ve fiyat kaynakları. */
function ReceteCekmecesi({
  donemId,
  asama,
  urun,
  onKapat,
}: {
  donemId: number;
  asama: number;
  urun: SmmAsamaUrunu | null;
  onKapat: () => void;
}) {
  const q = useSmmUrunRecetesi(donemId, asama, urun?.kod ?? null);
  const r = q.data;
  const elleKaydet = useSmmUrunElle(donemId);
  // Güncel değerler reçete sorgusundan (elle giriş sonrası yenilenir); ilk açılışta tablodaki satır
  const u = r?.urun ?? urun;
  return (
    <Sheet open={urun !== null} onOpenChange={(a) => !a && onKapat()}>
      <SheetContent side="right" className="data-[side=right]:sm:max-w-2xl">
        {urun && (
          <>
            <SheetHeader>
              <SheetTitle>{urun.ad ?? urun.kod}</SheetTitle>
              <SheetDescription>
                {urun.kod} · {asama} aşaması · birim maliyet {paraBicimle((u ?? urun).birim_maliyet, "TL", 4)}
                {urun.excel_birim !== null && ` (Excel: ${paraBicimle(urun.excel_birim, "TL", 4)})`}
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-4 overflow-y-auto px-4 pb-4">
              <dl className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1 rounded-xl bg-muted/50 p-3 text-sm">
                {(["malzeme", "iscilik", ...(asama === 40 ? ["gug"] : []), "fire", "birim_maliyet"] as const).map((alan) => (
                  <ElleDeger
                    key={`${alan}-${u?.[alan]}`}
                    alan={alan}
                    deger={u?.[alan] ?? "0"}
                    elle={(u?.elle_alanlar ?? []).includes(alan)}
                    bekliyor={elleKaydet.isPending}
                    onKaydet={(v) => elleKaydet.mutate({ asama, kod: urun.kod, alanlar: { [alan]: v } })}
                  />
                ))}
                {u?.alim_kurali && (
                  <>
                    <dt className="text-muted-foreground">Alım fiyatı esas alındı</dt>
                    <dd className="text-right tabular-nums">{paraBicimle(u.alim_fiyati, "TL", 4)}</dd>
                  </>
                )}
              </dl>
              <p className="-mt-2 text-xs text-muted-foreground">
                Elle girilen değer hesaplananın yerine geçer; birim maliyet elle girilirse üst aşamalar ve dönem sonu stok değeri de onu
                kullanır.
              </p>
              {elleKaydet.error && (
                <p role="alert" className="text-sm text-destructive">
                  {hataMetni(elleKaydet.error)}
                </p>
              )}
              {q.isPending ? (
                <p className="text-sm text-muted-foreground">Yükleniyor…</p>
              ) : q.error ? (
                <p role="alert" className="text-sm text-destructive">
                  {hataMetni(q.error)}
                </p>
              ) : (
                <table className="w-full text-sm">
                  <caption className="sr-only">Reçete satırları</caption>
                  <thead>
                    <tr className="text-left text-xs text-muted-foreground uppercase">
                      <th className="py-1.5 font-medium">Malzeme</th>
                      <th className="py-1.5 text-right font-medium">Miktar</th>
                      <th className="py-1.5 text-right font-medium">Fiyat</th>
                      <th className="py-1.5 text-right font-medium">Tutar</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {r?.satirlar.map((s, i) => (
                      <tr key={`${s.malzeme_kod}-${i}`} className="align-top">
                        <td className="py-1.5">
                          <span className="block">{s.malzeme_ad ?? s.malzeme_kod}</span>
                          <span className="block text-xs text-muted-foreground">
                            {s.malzeme_kod} · {KAYNAK_ADI[s.fiyat_kaynagi] ?? s.fiyat_kaynagi}
                            {D(s.fire_orani).gt(0) &&
                              ` · fire %${D(s.fire_orani).times(100).toDecimalPlaces(2).toString().replace(".", ",")}`}
                          </span>
                        </td>
                        <td className="py-1.5">
                          <Miktar deger={s.carpan} birim={s.birim} />
                        </td>
                        <td className={cn("py-1.5 text-right tabular-nums", s.fiyat_kaynagi === "yok" && "text-red-600 dark:text-red-400")}>
                          {paraBicimle(s.fiyat, "TL", 4)}
                        </td>
                        <td className="py-1.5 text-right font-medium tabular-nums">{paraBicimle(s.tutar, "TL", 4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

/**
 * Üretim maliyeti (Excel 20 KOD / 40 KOD / 50 KOD): aşama zinciri, dağıtılan işçilik/GÜG ve ürün başına birim maliyet.
 * Ürüne tıklayınca reçete satırları ve fiyat kaynakları açılır.
 */
export default function SmmUretim() {
  const secim = useSmmDonemSecimi();
  const [asama, setAsama] = useState(50);
  const [arama, setArama] = useState("");
  const gecikmeli = useGecikmeli(arama);
  const [yalnizFarkli, setYalnizFarkli] = useState(false);
  // Reçetesi olup bu dönem hiç üretilmeyen ürünler varsayılan listede gösterilmez (50'de ~500 ürün).
  const [yalnizUretilen, setYalnizUretilen] = useState(true);
  const [secili, setSecili] = useState<SmmAsamaUrunu | null>(null);
  const q = useSmmUretim(secim.donemId, { asama, arama: gecikmeli, yalniz_farkli: yalnizFarkli });
  const v = q.data;
  const ozet = v?.ozetler.find((o) => o.asama === asama);
  const kayitlar = (v?.kayitlar ?? []).filter((u) => !yalnizUretilen || yalnizFarkli || D(u.uretim_miktar).gt(0));

  const sutunlar = useMemo<SutunTanimi<SmmAsamaUrunu>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex max-w-[24rem] min-w-[14rem] flex-col whitespace-normal">
            <span className="flex items-center gap-1.5">
              {c.row.original.excel_farkli && <TriangleAlert className="size-3.5 shrink-0 text-amber-600" aria-label="Excel'den farklı" />}
              {c.row.original.ad ?? c.row.original.kod}
            </span>
            <span className="text-xs text-muted-foreground">{c.row.original.kod}</span>
          </span>
        ),
      },
      {
        id: "uretim",
        accessorFn: (r) => Number(r.uretim_miktar),
        header: "Üretim",
        cell: (c) => <Miktar deger={c.row.original.uretim_miktar} birim={c.row.original.birim} />,
      },
      {
        id: "malzeme",
        accessorFn: (r) => Number(r.malzeme),
        header: "Malzeme",
        cell: (c) => <ParaHucresi deger={c.row.original.malzeme} basamak={4} />,
      },
      {
        id: "iscilik",
        accessorFn: (r) => Number(r.iscilik),
        header: asama === 40 ? "İşçilik" : "İşçilik + GÜG",
        cell: (c) => <ParaHucresi deger={c.row.original.iscilik} basamak={4} />,
      },
      ...(asama === 40
        ? [
            {
              id: "gug",
              accessorFn: (r: SmmAsamaUrunu) => Number(r.gug),
              header: "GÜG",
              cell: (c: { row: { original: SmmAsamaUrunu } }) => <ParaHucresi deger={c.row.original.gug} basamak={4} />,
            } as SutunTanimi<SmmAsamaUrunu>,
          ]
        : []),
      {
        id: "fire",
        accessorFn: (r) => Number(r.fire),
        header: "Fire",
        cell: (c) => <ParaHucresi deger={c.row.original.fire} basamak={4} />,
      },
      {
        id: "birim",
        accessorFn: (r) => Number(r.birim_maliyet),
        header: "Birim maliyet",
        cell: (c) => (
          <span className="flex flex-col items-end">
            <ParaHucresi deger={c.row.original.birim_maliyet} basamak={4} className="font-semibold" />
            {c.row.original.alim_kurali && <span className="text-xs text-muted-foreground">alım fiyatı</span>}
          </span>
        ),
      },
      {
        id: "excel",
        accessorFn: (r) => (r.excel_birim === null ? -1 : Number(r.excel_birim)),
        header: "Excel",
        cell: (c) =>
          c.row.original.excel_birim === null ? (
            <span className="block text-right text-muted-foreground">—</span>
          ) : (
            <ParaHucresi
              deger={c.row.original.excel_birim}
              basamak={4}
              className={cn(c.row.original.excel_farkli ? "font-medium text-amber-700 dark:text-amber-400" : "text-muted-foreground")}
            />
          ),
      },
      {
        id: "toplam",
        accessorFn: (r) => Number(r.toplam),
        header: "Toplam",
        cell: (c) => <ParaHucresi deger={c.row.original.toplam} basamak={0} />,
      },
    ],
    [asama],
  );

  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Üretim Maliyeti" />
        <DonemYok />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Üretim Maliyeti"
        altBaslik="20 sebze kabul → 40 üretim hattı → 50 etiketleme: malzeme, işçilik, genel gider ve fire ile ürün birim maliyeti."
        eylemler={<DonemSecici secim={secim} />}
      />

      {v && (
        <div role="group" aria-label="Aşama" className="grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr] lg:items-stretch">
          {v.ozetler.map((o, i) => (
            <div key={o.asama} className="contents">
              {i > 0 && <ArrowRight className="hidden size-5 self-center text-muted-foreground lg:block" aria-hidden />}
              <button
                type="button"
                aria-pressed={asama === o.asama}
                onClick={() => {
                  setAsama(o.asama);
                  setSecili(null);
                }}
                className={cn(
                  "flex flex-col gap-1 rounded-2xl border-2 bg-card p-4 text-left shadow-xs transition-colors",
                  asama === o.asama ? "border-marka bg-kart-yesil" : "border-transparent hover:border-border",
                )}
              >
                <span className="text-sm font-medium text-muted-foreground">
                  {o.asama} · {o.ad}
                </span>
                <span className="text-2xl font-semibold tabular-nums">{milyon(o.toplam)}</span>
                <span className="text-xs text-muted-foreground">
                  {o.uretilen_urun} ürün üretildi · Excel'le {o.excel.esit}/{o.excel.karsilastirilan} aynı
                </span>
              </button>
            </div>
          ))}
        </div>
      )}

      {ozet && (
        <dl className="grid grid-cols-2 gap-3 rounded-2xl bg-kart-yesil p-4 text-sm sm:grid-cols-4">
          {[
            ["Malzeme", ozet.malzeme],
            [asama === 40 ? "İşçilik" : "İşçilik + GÜG", ozet.iscilik],
            ...(asama === 40 ? [["Genel üretim gideri", ozet.gug]] : []),
            ["Fire", ozet.fire],
          ].map(([ad, tutar]) => (
            <div key={ad} className="flex flex-col">
              <dt className="text-muted-foreground">{ad}</dt>
              <dd className="text-lg font-semibold tabular-nums">{milyon(tutar)}</dd>
            </div>
          ))}
        </dl>
      )}

      {ozet && (ozet.excel.farkli > 0 || ozet.sure_yok > 0 || ozet.alim_kurali > 0 || ozet.kod_bosluklu > 0 || ozet.excel_elle > 0) && (
        <ul className="flex flex-col gap-1 text-sm">
          {ozet.excel.farkli > 0 && (
            <li className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
              {ozet.excel.farkli} üründe birim maliyet Excel'in hesapladığından farklı.
            </li>
          )}
          {ozet.sure_yok > 0 && (
            <li className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
              {ozet.sure_yok} üretilen ürünün 51 sayfasında üretim süresi yok; işçilik payı almadı.
            </li>
          )}
          {ozet.alim_kurali > 0 && (
            <li className="text-muted-foreground">
              {ozet.alim_kurali} üründe hesaplanan maliyet alım fiyatından düşük olduğu için alım fiyatı esas alındı (Excel kuralı).
            </li>
          )}
          {ozet.kod_bosluklu > 0 && (
            <li className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
              {ozet.kod_bosluklu} reçete satırında malzeme kodunun başında ya da sonunda boşluk var; Excel kartı bulamadığı için fiyatı 0
              alıyor. Excel'de kod düzeltilmeli.
            </li>
          )}
          {ozet.excel_elle > 0 && (
            <li className="text-muted-foreground">
              {ozet.excel_elle} hücre Excel'de formül yerine elle yazılmış ya da farklı formüllü; o değerler aynen kullanıldı (reçetede
              işaretli).
            </li>
          )}
        </ul>
      )}

      {v && secim.donemId !== null && <DagitimKarti key={secim.donemId} donemId={secim.donemId} dagitim={v.dagitim} />}

      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label="Ürün ara"
          placeholder="Kod ya da ad ara"
          className="max-w-xs"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={yalnizFarkli} onChange={(e) => setYalnizFarkli(e.target.checked)} />
          Yalnız Excel'den farklı olanlar
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={yalnizUretilen} onChange={(e) => setYalnizUretilen(e.target.checked)} />
          Yalnız bu dönem üretilenler
        </label>
        <span className="ml-auto text-sm text-muted-foreground">{v ? `${kayitlar.length} / ${v.kayitlar.length} ürün` : ""}</span>
      </div>
      <VeriTablosu
        veri={kayitlar}
        sutunlar={sutunlar}
        yukleniyor={q.isPending}
        hata={q.error as ApiHatasi | null}
        bosMetin={yalnizFarkli ? "Excel'den farklı ürün yok" : "Ürün yok"}
        satirTikla={(u: SmmAsamaUrunu) => setSecili(u)}
      />
      {secim.donemId !== null && <ReceteCekmecesi donemId={secim.donemId} asama={asama} urun={secili} onKapat={() => setSecili(null)} />}
    </section>
  );
}
