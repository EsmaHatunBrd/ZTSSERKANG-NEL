import { useMemo, useRef, useState } from "react";
import { CircleCheck, FileSpreadsheet, Plus, TriangleAlert, Upload } from "lucide-react";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useSmmDonemleri, useSmmReceteKiyas, useSmmReceteler, useSmmReceteOnizle, useSmmReceteYukle } from "@/api/sorgular/smm";
import type { SmmAnaReceteOnizleme, SmmReceteUrunu } from "@/api/tipler";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { SECIM_SINIFI, useGecikmeli } from "./ortak";
import { ASAMA_ADI, ReceteCekmecesi, YeniReceteDiyalogu } from "./ReceteDuzenleme";

const DURUM_ADI: Record<string, string> = {
  ayni: "Aynı",
  malzeme: "Malzeme listesi farklı",
  miktar: "Miktar farklı",
  fire: "Yalnız fire farklı",
  yalniz_canias: "Yalnız Canias'ta",
  yalniz_excel: "Yalnız Excel'de",
};

function OnizlemeOzeti({ o }: { o: SmmAnaReceteOnizleme }) {
  return (
    <ul className="flex flex-col gap-1 text-sm">
      <li>
        <b>{o.urun_sayisi}</b> ürün, {o.satir_sayisi} satır (
        {Object.entries(o.asama)
          .map(([a, n]) => `${a}: ${n}`)
          .join(" · ")}
        ). {o.alternatifli_urun > 0 && `${o.alternatifli_urun} ürünün birden çok alternatifi var.`}
      </li>
      <li className="text-muted-foreground">
        Mevcut {o.mevcut_urun} ürün → eklenecek {o.eklenecek_urun}, değişecek {o.degisecek_urun}, kalkacak {o.kalkacak_urun}.
      </li>
      {(o.korunan ?? []).length > 0 && (
        <li>
          Elle değiştirilmiş {o.korunan!.length} ürün korunacak (dosyadaki hâli uygulanmaz):
          <ul className="mt-1 ml-4 list-disc text-muted-foreground">
            {o.korunan!.slice(0, 10).map((k) => (
              <li key={k.ana_kod}>
                {k.ana_ad ?? k.ana_kod} ({k.ana_kod})
                {!k.caniasta_var ? " — Canias'ta yok" : k.canias_farkli ? " — Canias'taki hâli farklı" : " — Canias'takiyle aynı"}
              </li>
            ))}
            {o.korunan!.length > 10 && <li>… ve {o.korunan!.length - 10} ürün daha</li>}
          </ul>
        </li>
      )}
    </ul>
  );
}

/** Canias ürün ağacı dökümünü önizleyip yükleme. */
function YuklemeKarti() {
  const ref = useRef<HTMLInputElement>(null);
  const [dosya, setDosya] = useState<File | null>(null);
  const onizle = useSmmReceteOnizle();
  const yukle = useSmmReceteYukle();
  const hata = onizle.error ?? yukle.error;
  return (
    <section aria-label="Canias reçete dökümü" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-kart-yesil text-primary" aria-hidden>
          <Upload className="size-5" />
        </span>
        <div>
          <h2 className="text-base font-semibold">Canias ürün ağacı dökümünü yükle</h2>
          <p className="text-sm text-muted-foreground">
            Canias'tan alınan reçete dökümü (TBLRESULT). Tüm reçeteler dosyadakilerle değiştirilir; ürünlerde seçtiğiniz alternatif korunur.
            Önce önizleyin.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Input
          ref={ref}
          type="file"
          accept=".xlsx"
          aria-label="Reçete dosyası"
          className="max-w-md"
          onChange={(e) => {
            setDosya(e.target.files?.[0] ?? null);
            onizle.reset();
            yukle.reset();
          }}
        />
        <Button type="button" variant="outline" disabled={!dosya || onizle.isPending} onClick={() => dosya && onizle.mutate(dosya)}>
          {onizle.isPending ? "Okunuyor…" : "Önizle"}
        </Button>
        <Button
          type="button"
          disabled={!dosya || !onizle.data || yukle.isPending}
          onClick={() =>
            dosya &&
            yukle.mutate(dosya, {
              onSuccess: () => {
                setDosya(null);
                onizle.reset();
                if (ref.current) ref.current.value = "";
              },
            })
          }
        >
          {yukle.isPending ? "Yükleniyor…" : "Yükle"}
        </Button>
      </div>
      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </p>
      )}
      {onizle.data && !yukle.data && (
        <div className="rounded-xl bg-muted/60 px-4 py-3">
          <OnizlemeOzeti o={onizle.data} />
        </div>
      )}
      {yukle.data && (
        <p role="status" className="flex items-center gap-2 text-sm">
          <CircleCheck className="size-4 text-green-700 dark:text-green-400" aria-hidden />
          Yüklendi: {yukle.data.urun_sayisi} ürün, {yukle.data.satir_sayisi} satır.
        </p>
      )}
    </section>
  );
}

/** Kalıcı reçeteler ile seçilen dönemin Excel 20/40/50 reçetelerinin karşılaştırması. */
function ExcelKiyasi() {
  const donemler = useSmmDonemleri();
  const excelli = (donemler.data?.kayitlar ?? []).filter((d) => d.kaynak_dosya);
  const [secili, setSecili] = useState<number | null>(null);
  const donemId = secili ?? excelli[0]?.id ?? null;
  const q = useSmmReceteKiyas(donemId);
  if (excelli.length === 0) return null;
  const k = q.data;
  return (
    <section aria-label="Excel reçeteleriyle karşılaştırma" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-base font-semibold">SMM Excel'indeki reçetelerle karşılaştırma</h2>
        <select
          aria-label="Karşılaştırılacak dönem"
          className={cn(SECIM_SINIFI, "ml-auto")}
          value={donemId ?? ""}
          onChange={(e) => setSecili(Number(e.target.value))}
        >
          {excelli.map((d) => (
            <option key={d.id} value={d.id}>
              {d.ad}
            </option>
          ))}
        </select>
      </div>
      {q.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}
      {k && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(k.sayilar).map(([a, s]) => {
              const toplam = Object.values(s).reduce((x, y) => x + y, 0);
              return (
                <div key={a} className="rounded-xl bg-muted/60 px-4 py-3 text-sm">
                  <div className="font-medium">{ASAMA_ADI[a] ?? a}</div>
                  <div className="text-2xl font-semibold tabular-nums">
                    {s.ayni ?? 0} <span className="text-base font-normal text-muted-foreground">/ {toplam} aynı</span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {Object.entries(s)
                      .filter(([d]) => d !== "ayni")
                      .map(([d, n]) => `${DURUM_ADI[d] ?? d}: ${n}`)
                      .join(" · ")}
                  </div>
                </div>
              );
            })}
          </div>
          {k.farklar.length > 0 && (
            <details>
              <summary className="cursor-pointer text-sm font-medium text-primary">Farklı {k.farklar.length} ürünü göster</summary>
              <ul className="mt-2 flex max-h-96 flex-col divide-y overflow-y-auto text-sm">
                {k.farklar.map((f) => (
                  <li key={`${f.asama}-${f.ana_kod}`} className="flex flex-wrap items-baseline gap-x-3 py-1.5">
                    <span className="w-8 text-muted-foreground tabular-nums">{f.asama}</span>
                    <span className="min-w-0 flex-1">
                      {f.ana_ad ?? f.ana_kod} <span className="text-xs text-muted-foreground">{f.ana_kod}</span>
                    </span>
                    <span className="text-amber-700 dark:text-amber-400">{DURUM_ADI[f.durum] ?? f.durum}</span>
                    {f.ayrinti?.yalniz_excel?.length ? (
                      <span className="w-full pl-11 text-xs text-muted-foreground">
                        Yalnız Excel'de: {f.ayrinti.yalniz_excel.join(", ")}
                        {f.ayrinti.yalniz_canias?.length ? ` · yalnız Canias'ta: ${f.ayrinti.yalniz_canias.join(", ")}` : ""}
                      </span>
                    ) : f.ayrinti?.yalniz_canias?.length ? (
                      <span className="w-full pl-11 text-xs text-muted-foreground">
                        Yalnız Canias'ta: {f.ayrinti.yalniz_canias.join(", ")}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}

/**
 * Kalıcı üretim reçeteleri (Canias ürün ağacı). Dönemden bağımsızdır; Excel'siz açılan dönemler aşama hesabında bunları kullanır.
 */
export default function SmmReceteler() {
  const [arama, setArama] = useState("");
  const gecikmeli = useGecikmeli(arama);
  const [asama, setAsama] = useState<number | null>(null);
  const [secili, setSecili] = useState<string | null>(null);
  const [yeniAcik, setYeniAcik] = useState(false);
  const q = useSmmReceteler({ arama: gecikmeli, asama });
  const v = q.data;

  const sutunlar = useMemo<SutunTanimi<SmmReceteUrunu>[]>(
    () => [
      {
        accessorKey: "ana_ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex max-w-[30rem] min-w-[16rem] flex-col whitespace-normal">
            <span className="flex items-center gap-1.5">
              {c.row.original.ana_ad ?? c.row.original.ana_kod}
              {c.row.original.elle && <span className="rounded-full bg-kart-sari px-1.5 py-0.5 text-[11px] font-medium">Elle</span>}
            </span>
            <span className="text-xs text-muted-foreground">{c.row.original.ana_kod}</span>
          </span>
        ),
      },
      {
        accessorKey: "asama",
        header: "Aşama",
        cell: (c) => <span className="whitespace-nowrap">{ASAMA_ADI[String(c.row.original.asama)] ?? c.row.original.asama}</span>,
      },
      {
        accessorKey: "satir_sayisi",
        header: "Satır",
        cell: (c) => <span className="tabular-nums">{c.row.original.satir_sayisi}</span>,
      },
      {
        id: "alternatif",
        accessorFn: (r) => r.alternatifler.length,
        header: "Alternatif",
        cell: (c) =>
          c.row.original.alternatifler.length > 1 ? (
            <span className="text-amber-700 dark:text-amber-400">
              {c.row.original.secili_alternatif} ({c.row.original.alternatifler.length} seçenek)
            </span>
          ) : (
            <span className="text-muted-foreground">{c.row.original.secili_alternatif}</span>
          ),
      },
    ],
    [],
  );

  const son = v?.son_yukleme;
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Reçeteler"
        altBaslik="Kalıcı üretim reçeteleri (Canias ürün ağacı). Her ay yeniden yüklenmez; Canias'ta reçete değişince yeni döküm yüklenir."
      />
      {son ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <FileSpreadsheet className="size-4" aria-hidden />
          Son yükleme: {son.kaynak_dosya ?? "—"} · {son.urun_sayisi} ürün · {son.olusturan}
          {son.zaman && ` · ${new Date(son.zaman).toLocaleString("tr-TR")}`}
        </p>
      ) : (
        v && (
          <p className="flex items-center gap-2 text-sm">
            <TriangleAlert className="size-4 text-amber-600" aria-hidden />
            Henüz reçete yüklenmedi. Excel'siz dönemlerin hesabı için Canias ürün ağacı dökümünü yükleyin.
          </p>
        )
      )}
      <YuklemeKarti />
      <ExcelKiyasi />

      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label="Ürün ara"
          placeholder="Kod ya da ad ara"
          className="max-w-xs"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
        />
        <select
          aria-label="Aşama"
          className={SECIM_SINIFI}
          value={asama ?? ""}
          onChange={(e) => setAsama(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Tüm aşamalar</option>
          {Object.entries(v?.asama_sayilari ?? {}).map(([a, n]) => (
            <option key={a} value={a}>
              {ASAMA_ADI[a] ?? a} ({n})
            </option>
          ))}
        </select>
        {v && v.alternatifli_urun > 0 && (
          <span className="text-sm text-muted-foreground">
            {v.alternatifli_urun} ürünün birden çok alternatifi var
            {v.elle_urun ? ` · ${v.elle_urun} ürün elle değiştirildi` : ""}. Görmek ve düzenlemek için satıra tıklayın.
          </span>
        )}
        <span className="ml-auto text-sm text-muted-foreground">{v ? `${v.kayitlar.length} ürün` : ""}</span>
        <Button type="button" size="sm" variant="outline" onClick={() => setYeniAcik(true)}>
          <Plus className="size-3.5" /> Yeni reçete
        </Button>
      </div>
      <VeriTablosu
        veri={v?.kayitlar ?? []}
        sutunlar={sutunlar}
        yukleniyor={q.isPending}
        hata={q.error as ApiHatasi | null}
        bosMetin="Reçete yok"
        satirTikla={(u: SmmReceteUrunu) => setSecili(u.ana_kod)}
      />
      <ReceteCekmecesi kod={secili} onKapat={() => setSecili(null)} />
      <YeniReceteDiyalogu acik={yeniAcik} onKapat={() => setYeniAcik(false)} onAcildi={setSecili} />
    </section>
  );
}
