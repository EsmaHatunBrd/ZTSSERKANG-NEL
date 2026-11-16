import { lazy, Suspense, useMemo, useState } from "react";
import { ClipboardList, PackageCheck, TrendingDown, TrendingUp, TriangleAlert } from "lucide-react";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useSmmSarfFarki, useSmmSarfOzeti } from "@/api/sorgular/smm";
import type { SmmSarfSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { DonemSecici, DonemYok, Miktar, SECIM_SINIFI, milyon, turAdi, useGecikmeli, useSmmDonemSecimi } from "./ortak";

const ESIKLER = [0, 1_000, 10_000, 100_000];

const SarfFarkiGrafigi = lazy(() => import("./SarfFarkiGrafigi").then((m) => ({ default: m.SarfFarkiGrafigi })));

/**
 * En büyük farklar: özet şerit (net fark, fazla, eksik) ve tutara göre ilk 20 kalem için çift yönlü çubuk grafik.
 * Kaleme tıklayınca alttaki tablo o kalemle süzülür; "Tümü" süzgeci kaldırır.
 */
function EnBuyukFarklar({
  donemId,
  seciliKod,
  onSec,
  onTumu,
}: {
  donemId: number;
  seciliKod: string;
  onSec: (kod: string) => void;
  onTumu: () => void;
}) {
  const q = useSmmSarfOzeti(donemId);
  const v = q.data;
  if (q.isPending) return null;
  if (q.error || !v)
    return (
      <p role="alert" className="text-sm text-destructive">
        {hataMetni(q.error as ApiHatasi)}
      </p>
    );
  const o = v.ozet;
  const secili = v.kalemler.some((k) => k.kod === seciliKod);
  return (
    <section aria-label="En büyük farklar" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <h2 className="text-base font-semibold">En büyük farklar</h2>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-sm tabular-nums">
          <div className="flex gap-1.5">
            <dt className="text-muted-foreground">Net fark</dt>
            <dd className="font-semibold">{paraBicimle(o.toplam_fark_tutari, "TL", 0)}</dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="text-muted-foreground">Fazla harcanan</dt>
            <dd className="font-semibold text-red-700 dark:text-red-400">
              {paraBicimle(o.fazla_tutar, "TL", 0)} <span className="font-normal text-muted-foreground">({o.fazla_sayisi} kalem)</span>
            </dd>
          </div>
          <div className="flex gap-1.5">
            <dt className="text-muted-foreground">Az harcanan</dt>
            <dd className="font-semibold text-green-700 dark:text-green-400">
              {paraBicimle(D(o.eksik_tutar).abs(), "TL", 0)}{" "}
              <span className="font-normal text-muted-foreground">({o.eksik_sayisi} kalem)</span>
            </dd>
          </div>
          {o.birim_uyumsuz_sayisi > 0 && (
            <div className="flex gap-1.5">
              <dt className="text-muted-foreground">Birim uyumsuz (sıralamada yok)</dt>
              <dd className="font-semibold">{o.birim_uyumsuz_sayisi}</dd>
            </div>
          )}
        </dl>
      </div>
      <Suspense fallback={<p className="text-sm text-muted-foreground">Grafik yükleniyor…</p>}>
        <SarfFarkiGrafigi kalemler={v.kalemler} onSec={onSec} />
      </Suspense>
      {v.kalemler.length > 0 && (
        <details className="rounded-xl border">
          <summary className="cursor-pointer px-3 py-2 text-sm font-medium">Liste olarak göster (tıklayınca tabloda süzülür)</summary>
          <ol aria-label="En büyük farklar listesi" className="flex flex-col divide-y border-t text-sm">
            {v.kalemler.map((k) => (
              <li key={k.kod}>
                <button
                  type="button"
                  aria-pressed={k.kod === seciliKod}
                  onClick={() => onSec(k.kod)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left hover:bg-muted/50",
                    k.kod === seciliKod && "bg-kart-yesil",
                  )}
                >
                  <span className="flex flex-col">
                    <span>{k.ad ?? k.kod}</span>
                    <span className="text-xs text-muted-foreground">
                      {k.kod} · {k.yon === "fazla" ? "fazla harcanan" : "az harcanan"}
                      {k.fark_yuzde !== null && ` · ${yuzdeBicimle(k.fark_yuzde)}`}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "font-semibold tabular-nums",
                      k.yon === "fazla" ? "text-red-700 dark:text-red-400" : "text-green-700 dark:text-green-400",
                    )}
                  >
                    {paraBicimle(k.fark_tutar, "TL", 0)}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </details>
      )}
      {secili && (
        <p className="flex items-center gap-2 text-sm">
          Tablo <b>{seciliKod}</b> ile süzüldü.
          <Button type="button" size="sm" variant="outline" onClick={onTumu}>
            Tümü
          </Button>
        </p>
      )}
    </section>
  );
}

/**
 * Sarf farkı: malzeme başına reçeteye göre olması gereken sarf (üretim × reçete × (1 + fire)) ile sayımla bulunan sarf
 * (dönem başı + alım − iade − sayım). Pozitif fark: reçetenin söylediğinden fazla harcanmış (kayıp ya da kayıt eksiği).
 */
export default function SmmSarfFarki() {
  const secim = useSmmDonemSecimi();
  const [arama, setArama] = useState("");
  const gecikmeli = useGecikmeli(arama);
  const [tur, setTur] = useState("");
  const [esik, setEsik] = useState(1_000);
  const q = useSmmSarfFarki(secim.donemId, { arama: gecikmeli, tur, esik });
  const v = q.data;

  const sutunlar = useMemo<SutunTanimi<SmmSarfSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Malzeme",
        cell: (c) => (
          <span className="flex max-w-[22rem] min-w-[14rem] flex-col whitespace-normal">
            <span className="flex items-center gap-1.5">
              {c.row.original.birim_uyumsuz && <TriangleAlert className="size-3.5 shrink-0 text-amber-600" aria-label="Birim uyumsuz" />}
              {c.row.original.ad ?? c.row.original.kod}
            </span>
            <span className="text-xs text-muted-foreground">
              {c.row.original.kod} · {turAdi(c.row.original.tur)} · {c.row.original.urun_sayisi} üründe
            </span>
            {c.row.original.birim_uyumsuz && (
              <span className="text-xs text-amber-700 dark:text-amber-400">
                Reçetede {c.row.original.recete_birimleri.join(", ")}, kartta {c.row.original.birim}: karşılaştırılamaz
              </span>
            )}
            {D(c.row.original.uretim_girisi).gt(0) && (
              <span className="text-xs text-muted-foreground">Üretim girişi dahil: {c.row.original.uretim_girisi.replace(".", ",")}</span>
            )}
            {(D(c.row.original.satis_miktar).gt(0) || D(c.row.original.sahit_miktar).gt(0)) && (
              <span className="text-xs text-muted-foreground">
                Düşüldü:{D(c.row.original.satis_miktar).gt(0) && ` satış ${c.row.original.satis_miktar.replace(".", ",")}`}
                {D(c.row.original.sahit_miktar).gt(0) && ` şahit ${c.row.original.sahit_miktar.replace(".", ",")}`}
              </span>
            )}
          </span>
        ),
      },
      {
        id: "recete",
        accessorFn: (r) => Number(r.recete_sarf),
        header: "Reçeteye göre",
        cell: (c) => <Miktar deger={c.row.original.recete_sarf} birim={c.row.original.birim} />,
      },
      {
        id: "stok",
        accessorFn: (r) => Number(r.stok_sarf),
        header: "Sayıma göre",
        cell: (c) => <Miktar deger={c.row.original.stok_sarf} birim={c.row.original.birim} />,
      },
      {
        id: "fark",
        accessorFn: (r) => Number(r.fark),
        header: "Fark",
        cell: (c) => <Miktar deger={c.row.original.fark} birim={c.row.original.birim} />,
      },
      {
        id: "oran",
        accessorFn: (r) => (r.fark_orani === null ? 0 : Number(r.fark_orani)),
        header: "Fark %",
        cell: (c) =>
          c.row.original.fark_orani === null ? (
            <span className="block text-right text-muted-foreground">—</span>
          ) : (
            <span className="block text-right tabular-nums">{yuzdeBicimle(c.row.original.fark_orani)}</span>
          ),
      },
      {
        id: "ort",
        accessorFn: (r) => Number(r.ortalama_fiyat),
        header: "Birim fiyat",
        cell: (c) => <ParaHucresi deger={c.row.original.ortalama_fiyat} basamak={4} />,
      },
      {
        id: "tutar",
        accessorFn: (r) => Math.abs(Number(r.fark_tutar)),
        header: "Fark tutarı",
        cell: (c) => (
          <ParaHucresi
            deger={c.row.original.fark_tutar}
            basamak={0}
            className={cn("font-semibold", D(c.row.original.fark_tutar).isPositive() && "text-red-700 dark:text-red-400")}
          />
        ),
      },
    ],
    [],
  );

  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Sarf Farkı" />
        <DonemYok />
      </section>
    );
  }

  const top = v?.toplamlar;
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Sarf Farkı"
        altBaslik="Reçeteye göre harcanması gereken malzeme ile sayıma göre harcanan malzeme. Büyük TL farkları üstte."
        eylemler={<DonemSecici secim={secim} />}
      />

      {secim.donemId !== null && (
        <EnBuyukFarklar
          donemId={secim.donemId}
          seciliKod={arama}
          onSec={(kod) => {
            setArama(kod);
            setTur("");
            setEsik(0);
          }}
          onTumu={() => setArama("")}
        />
      )}

      {top && (
        <div className="grid grid-cols-1 gap-3 rounded-2xl bg-kart-yesil p-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kart baslik="Reçeteye göre sarf" deger={milyon(top.recete_tutar)} simge={ClipboardList} renk="acik" />
          <Kart baslik="Sayıma göre sarf" deger={milyon(top.stok_tutar)} simge={PackageCheck} renk="acik" />
          <Kart baslik="Fazla harcanan" deger={milyon(top.fazla)} simge={TrendingUp} renk="acik" />
          <Kart baslik="Az harcanan" deger={milyon(top.eksik)} simge={TrendingDown} renk="acik" />
        </div>
      )}
      <p className="-mt-2 text-xs text-muted-foreground">
        Fazla harcanan: sayıma göre reçetenin söylediğinden çok malzeme çıkmış (kayıp, fire fazlası ya da eksik üretim kaydı). Az harcanan:
        reçete, sayımın gösterdiğinden çok malzeme bekliyor (reçete fazla ya da sayım/alım kaydı eksik). Sayıma göre sarfa üretim girişi
        dahildir; birim fiyat dönem ortalaması, üretilen kalemde aşama maliyetidir.
        {v && v.birim_uyumsuz_sayisi > 0 && (
          <> {v.birim_uyumsuz_sayisi} malzemede reçete birimi kart biriminden farklı; bunlar toplamlara girmez ve listenin sonundadır.</>
        )}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label="Malzeme ara"
          placeholder="Kod ya da ad ara"
          className="max-w-xs"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
        />
        <select aria-label="Tür" className={SECIM_SINIFI} value={tur} onChange={(e) => setTur(e.target.value)}>
          <option value="">Tüm türler</option>
          {(v?.turler ?? []).map((t) => (
            <option key={t} value={t}>
              {turAdi(t)}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">En az fark</span>
          <select aria-label="En az fark" className={SECIM_SINIFI} value={esik} onChange={(e) => setEsik(Number(e.target.value))}>
            {ESIKLER.map((e) => (
              <option key={e} value={e}>
                {e === 0 ? "Hepsi" : `${e.toLocaleString("tr-TR")} TL`}
              </option>
            ))}
          </select>
        </label>
        <span className="ml-auto text-sm text-muted-foreground">{v ? `${v.kayitlar.length} malzeme` : ""}</span>
      </div>
      <VeriTablosu
        veri={v?.kayitlar ?? []}
        sutunlar={sutunlar}
        yukleniyor={q.isPending}
        hata={q.error as ApiHatasi | null}
        bosMetin="Bu süzgeçle fark yok"
      />
    </section>
  );
}
