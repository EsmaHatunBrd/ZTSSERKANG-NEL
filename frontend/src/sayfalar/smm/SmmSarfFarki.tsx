import { useMemo, useState } from "react";
import { ClipboardList, PackageCheck, TrendingDown, TrendingUp, TriangleAlert } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { useSmmSarfFarki } from "@/api/sorgular/smm";
import type { SmmSarfSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, yuzdeBicimle } from "@/yardimcilar/para";
import { DonemSecici, DonemYok, Miktar, SECIM_SINIFI, milyon, turAdi, useGecikmeli, useSmmDonemSecimi } from "./ortak";

const ESIKLER = [0, 1_000, 10_000, 100_000];

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
