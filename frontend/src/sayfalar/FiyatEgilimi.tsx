import { lazy, Suspense, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Info, X } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { EGILIM_AYLARI, egilimAyi, useFiyatEgilimi, VARSAYILAN_AY } from "@/api/sorgular/fiyatEgilimi";
import { useFiyatGecmisi } from "@/api/sorgular/malzemeler";
import type { FiyatEgilimiSatiri } from "@/api/tipler";
import { hataMetni } from "@/api/istemci";
import { kaynakMetni } from "@/bilesenler/KaynakRozeti";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { D, paraBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";

const FiyatGecmisiGrafigi = lazy(() => import("./fiyatEgilimi/FiyatGecmisiGrafigi").then((m) => ({ default: m.FiyatGecmisiGrafigi })));

/** Sunucudan yüzde metni gelir ("69.00" = %69): "69,0 %". */
const yuzdeMetni = (p: string | null, basamak = 1) => (p === null ? "—" : `${paraBicimle(p, "", basamak)} %`);
/** Sıralama için sayı (boş en alta). */
const sayi = (x: string | null) => (x === null ? null : Number(x));

type Durum = "asiyor" | "sinirda" | "normal" | "yok";

/**
 * Durum: sunucu `enflasyonu_asiyor`u yıllık % > eşik + 1 puan (tolerans) ile işaretler. Eşik ile eşik+1 arası "Sınırda":
 * aşmıyor sayılır ama izlenmeli. Yıllık yüzde yoksa (ilk fiyat 0 ya da para birimi değişmiş) durum verilmez.
 */
function durum(r: FiyatEgilimiSatiri): Durum {
  if (r.enflasyonu_asiyor) return "asiyor";
  if (r.yillik_yuzde === null) return "yok";
  return D(r.yillik_yuzde).greaterThan(D(r.esik_yuzde)) ? "sinirda" : "normal";
}

function DurumRozeti({ satir }: { satir: FiyatEgilimiSatiri }) {
  const d = durum(satir);
  if (d === "asiyor") return <Badge variant="destructive">Aşıyor</Badge>;
  if (d === "sinirda") return <Badge variant="secondary">Sınırda</Badge>;
  if (d === "normal") return <span className="text-xs text-muted-foreground">Normal</span>;
  return <span className="text-muted-foreground">—</span>;
}

/** Fiyat ve altında tarihi: "5,0000 TL / 12.11.2025". */
function FiyatTarih({ fiyat, tarih, paraBirimi }: { fiyat: string; tarih: string; paraBirimi: string }) {
  return (
    <span className="flex flex-col items-end tabular-nums">
      <span>{paraBicimle(fiyat, paraBirimi, 4)}</span>
      <span className="text-xs text-muted-foreground">{goster(tarih)}</span>
    </span>
  );
}

/** Seçili malzemenin fiyat geçmişi: çizgi grafik (tembel yüklenir) ve kayıt listesi. */
function GecmisPaneli({ satir, senaryoId, kapat }: { satir: FiyatEgilimiSatiri; senaryoId: number | null; kapat: () => void }) {
  const q = useFiyatGecmisi(satir.kod, senaryoId);
  const kayitlar = q.data?.kayitlar ?? [];
  return (
    <section aria-label={`Fiyat geçmişi: ${satir.ad}`} className="flex min-w-0 flex-col gap-4 rounded-xl border bg-card p-4 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{satir.ad}</h2>
          <p className="text-xs text-muted-foreground">
            {satir.kod} · {satir.para_birimi} · {satir.kayit_sayisi} kayıt pencerede · {satir.kullanan_urun_sayisi} ürün kullanıyor
          </p>
        </div>
        <Button type="button" variant="ghost" size="icon" aria-label="Paneli kapat" onClick={kapat}>
          <X aria-hidden />
        </Button>
      </div>
      {q.isPending && (
        <p role="status" className="text-sm text-muted-foreground">
          Geçmiş yükleniyor…
        </p>
      )}
      {q.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}
      {q.data && kayitlar.length === 0 && <p className="text-sm text-muted-foreground">Bu malzemenin fiyat kaydı yok.</p>}
      {kayitlar.length > 0 && (
        <>
          <Suspense
            fallback={
              <div role="status" className="h-60 animate-pulse rounded-lg bg-muted" aria-label="Grafik yükleniyor">
                <span className="sr-only">Grafik yükleniyor…</span>
              </div>
            }
          >
            <FiyatGecmisiGrafigi
              kayitlar={kayitlar}
              paraBirimi={satir.para_birimi}
              ilkFiyat={satir.ilk_fiyat}
              esikYuzde={satir.esik_yuzde}
            />
          </Suspense>
          <div className="overflow-x-auto">
            <Table aria-label="Fiyat kayıtları">
              <TableHeader>
                <TableRow>
                  <TableHead>Tarih</TableHead>
                  <TableHead className="text-right">Fiyat</TableHead>
                  <TableHead>Neden</TableHead>
                  <TableHead>Kaynak</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {kayitlar.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="tabular-nums whitespace-nowrap">{goster(k.gecerlilik_basi)}</TableCell>
                    <TableCell className="text-right tabular-nums whitespace-nowrap">
                      {paraBicimle(k.fiyat, k.para_birimi ?? satir.para_birimi, 4)}
                    </TableCell>
                    <TableCell>{k.neden}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{kaynakMetni(k.kaynak) ?? k.kaynak}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </section>
  );
}

/**
 * Fiyat eğilimi: son N ayda malzeme fiyatı değişimi ve senaryo enflasyonuyla kıyas. Pencere (`?ay=`) ve "yalnız aşanlar"
 * (`?yalniz_asan=1`) sunucuya gider; arama (`?arama=`) sayfa içidir (Veri Kontrolü bu adresle kod gönderir). Hiçbir şey kaydedilmez.
 */
/**
 * Adres çubuğundaki parametreyle eşlenen yerel durum: denetim anında değişir (yönlendirici geçişi beklenmez, kutu titremez);
 * adres dışarıdan değişirse (geri tuşu, Veri Kontrolü bağlantısı) yerel değer adrese uyar.
 */
function useAdresDegeri<T>(ham: string | null, coz: (ham: string | null) => T): [T, (t: T) => void] {
  const [kaynak, setKaynak] = useState(ham);
  const [deger, setDeger] = useState(() => coz(ham));
  if (kaynak !== ham) {
    setKaynak(ham);
    setDeger(coz(ham));
  }
  return [deger, setDeger];
}

export default function FiyatEgilimi() {
  const { senaryoId } = useSenaryo();
  const [params, setParams] = useSearchParams();
  const [ay, setAy] = useAdresDegeri(params.get("ay"), egilimAyi);
  const [yalnizAsan, setYalnizAsan] = useAdresDegeri(params.get("yalniz_asan"), (h) => h === "1");
  // Arama sayfa içidir; Veri Kontrolü `?arama=<kod>` ile gelir.
  const [arama, setArama] = useAdresDegeri(params.get("arama"), (h) => h ?? "");
  const [secili, setSecili] = useState<string | null>(null);
  const q = useFiyatEgilimi(senaryoId, ay, yalnizAsan);
  const v = q.data;

  function paramYaz(ad: string, deger: string | null) {
    setParams(
      (p) => {
        const y = new URLSearchParams(p);
        if (deger === null) y.delete(ad);
        else y.set(ad, deger);
        return y;
      },
      { replace: true },
    );
  }

  const satirlar = useMemo(() => {
    const tum = v?.satirlar ?? [];
    const s = arama.trim().toLocaleLowerCase("tr");
    if (!s) return tum;
    return tum.filter((r) => r.kod.toLocaleLowerCase("tr").includes(s) || r.ad.toLocaleLowerCase("tr").includes(s));
  }, [v, arama]);
  const seciliSatir = useMemo(() => (secili === null ? null : (v?.satirlar.find((r) => r.kod === secili) ?? null)), [v, secili]);

  const sutunlar = useMemo<SutunTanimi<FiyatEgilimiSatiri>[]>(
    () => [
      {
        accessorKey: "kod",
        header: "Kod",
        meta: { hiza: "sol" },
        cell: (c) => <span className="font-mono text-xs">{c.getValue<string>()}</span>,
      },
      {
        accessorKey: "ad",
        header: "Malzeme",
        cell: (c) => (
          <span className="flex flex-col">
            <span>{c.row.original.ad}</span>
            {c.row.original.tip && <span className="text-xs text-muted-foreground">{c.row.original.tip}</span>}
          </span>
        ),
      },
      { accessorKey: "para_birimi", header: "Para", meta: { hiza: "sol" } },
      {
        id: "ilk_fiyat",
        accessorFn: (r) => sayi(r.ilk_fiyat),
        header: "İlk fiyat",
        cell: (c) => (
          <FiyatTarih fiyat={c.row.original.ilk_fiyat} tarih={c.row.original.ilk_tarih} paraBirimi={c.row.original.para_birimi} />
        ),
      },
      {
        id: "son_fiyat",
        accessorFn: (r) => sayi(r.son_fiyat),
        header: "Son fiyat",
        cell: (c) => (
          <FiyatTarih fiyat={c.row.original.son_fiyat} tarih={c.row.original.son_tarih} paraBirimi={c.row.original.para_birimi} />
        ),
      },
      {
        id: "degisim",
        accessorFn: (r) => sayi(r.degisim_yuzde),
        header: "Değişim %",
        meta: { hiza: "sag" },
        cell: (c) => <span className="tabular-nums">{yuzdeMetni(c.row.original.degisim_yuzde)}</span>,
      },
      {
        id: "yillik",
        accessorFn: (r) => sayi(r.yillik_yuzde),
        header: "Yıllık %",
        meta: { hiza: "sag" },
        cell: (c) => <span className="font-semibold tabular-nums">{yuzdeMetni(c.row.original.yillik_yuzde)}</span>,
      },
      {
        id: "esik",
        accessorFn: (r) => sayi(r.esik_yuzde),
        header: "Eşik %",
        meta: { hiza: "sag" },
        cell: (c) => <span className="text-muted-foreground tabular-nums">{yuzdeMetni(c.row.original.esik_yuzde)}</span>,
      },
      {
        id: "durum",
        accessorFn: (r) => ({ asiyor: 0, sinirda: 1, normal: 2, yok: 3 })[durum(r)],
        header: "Durum",
        meta: { hiza: "sol" },
        cell: (c) => <DurumRozeti satir={c.row.original} />,
      },
      { accessorKey: "kullanan_urun_sayisi", header: "Kullanan ürün", meta: { hiza: "sag" } },
    ],
    [],
  );

  const esikTl = v?.enflasyon_yuzde === null || v?.enflasyon_yuzde === undefined ? "—" : `%${paraBicimle(v.enflasyon_yuzde, "", 1)}`;

  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi baslik="Fiyat eğilimi" altBaslik={`Son ${ay} ayda malzeme fiyatı değişimi ve senaryo enflasyonuyla kıyas`} />

      <div className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Pencere</span>
          <select
            aria-label="Pencere"
            className="h-9 rounded-lg border bg-background px-2 text-sm"
            value={ay}
            onChange={(e) => {
              setAy(egilimAyi(e.target.value));
              paramYaz("ay", e.target.value === String(VARSAYILAN_AY) ? null : e.target.value);
            }}
          >
            {EGILIM_AYLARI.map((a) => (
              <option key={a} value={a}>
                Son {a} ay
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
        <label className="flex h-9 items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={yalnizAsan}
            onChange={(e) => {
              setYalnizAsan(e.target.checked);
              paramYaz("yalniz_asan", e.target.checked ? "1" : null);
            }}
          />
          Yalnız enflasyonu aşanlar
        </label>
        {v && (
          <p role="status" aria-label="Özet" className="ml-auto text-sm text-muted-foreground tabular-nums">
            <span className="font-medium text-foreground">{v.toplam}</span> malzeme ·{" "}
            <span className={v.asan_sayisi > 0 ? "font-medium text-destructive" : "font-medium text-foreground"}>{v.asan_sayisi}</span>{" "}
            enflasyonu aşıyor · eşik {esikTl} (TL) / %0 (döviz)
          </p>
        )}
      </div>

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          Yıllık %, pencere başı ile son fiyat arasındaki değişimin yıla çevrilmiş halidir. TL malzemede eşik senaryo enflasyonu, dövizde
          %0'dır; eşiği 1 puandan fazla geçen malzeme "Aşıyor", eşik ile 1 puan üstü arası "Sınırda" sayılır. Geçmişi görmek için satıra
          tıklayın.
        </span>
      </p>

      <div className={seciliSatir ? "grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]" : undefined}>
        <div className="min-w-0 overflow-x-auto">
          <VeriTablosu
            veri={satirlar}
            sutunlar={sutunlar}
            yukleniyor={q.isPending && senaryoId !== null}
            hata={q.error as ApiHatasi | null}
            bosMetin={
              arama.trim() ? "Aramaya uyan malzeme yok" : yalnizAsan ? "Enflasyonu aşan malzeme yok" : "Bu çalışmada fiyat kaydı yok."
            }
            bosAciklama={
              arama.trim()
                ? "Kod ya da adın bir kısmını yazın."
                : yalnizAsan
                  ? 'Tümünü görmek için "Yalnız enflasyonu aşanlar" kutusunu kaldırın.'
                  : undefined
            }
            satirTikla={(r) => setSecili(r.kod === secili ? null : r.kod)}
          />
        </div>
        {seciliSatir && <GecmisPaneli key={seciliSatir.kod} satir={seciliSatir} senaryoId={senaryoId} kapat={() => setSecili(null)} />}
      </div>
    </section>
  );
}
