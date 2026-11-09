import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Factory, PackageCheck, Pencil, Plus, ShoppingCart, TriangleAlert, Warehouse } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { useSmmDonemleri, useSmmStok } from "@/api/sorgular/smm";
import { useSmmElleDegisenler } from "@/api/sorgular/smmStok";
import type { SmmStokSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, paraBicimle } from "@/yardimcilar/para";
import { SmmKalemDuzenle } from "./SmmKalemDuzenle";

const SECIM_SINIFI = "h-8 rounded-lg border border-input bg-background px-2 text-sm";
/** Büyük tutar kısaltılır: 723567044 -> "723,6 mn TL" (özet kutularında tek satıra sığsın). */
const milyon = (x: string) => `${paraBicimle(D(x).dividedBy(1_000_000), "", 1)} mn TL`;
const miktar = (x: string) => new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 3 }).format(D(x).toNumber());
/** Mizan adındaki kod önekini atar: '0001-Hammadde' -> 'Hammadde'. */
const turAdi = (t: string | null) => (t ?? "Diğer").replace(/^\d+-/, "");

function Miktar({ deger, birim }: { deger: string; birim?: string | null }) {
  const sifir = D(deger).isZero();
  return (
    <span
      className={cn(
        "block text-right tabular-nums",
        sifir && "text-muted-foreground",
        D(deger).isNegative() && "font-medium text-red-600 dark:text-red-400",
      )}
    >
      {sifir ? "—" : miktar(deger)}
      {!sifir && birim ? <span className="ml-1 text-xs text-muted-foreground">{birim}</span> : null}
    </span>
  );
}

/**
 * Stok ve envanter (Excel TABLO): malzeme başına dönem başı + alım = toplam; ortalama birim fiyat; sayım (dönem sonu stok) ve sarf.
 * Sarfı eksi çıkan kalemler (sayım, eldekinden fazla) "kontrol edin" olarak işaretlenir.
 */
export default function SmmStok() {
  const [params, setParams] = useSearchParams();
  const donemler = useSmmDonemleri();
  const liste = donemler.data?.kayitlar ?? [];
  const donemId = params.get("donem") ? Number(params.get("donem")) : (liste[0]?.id ?? null);
  const [tur, setTur] = useState("");
  const [arama, setArama] = useState("");
  const [gecikmeli, setGecikmeli] = useState("");
  const [yalnizKontrol, setYalnizKontrol] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setGecikmeli(arama.trim()), 300);
    return () => clearTimeout(t);
  }, [arama]);
  const q = useSmmStok(donemId, { tur, arama: gecikmeli, yalniz_kontrol: yalnizKontrol });
  const v = q.data;
  const elle = useSmmElleDegisenler(donemId).data?.kayitlar ?? {};
  const [duzenlenen, setDuzenlenen] = useState<SmmStokSatiri | null | "yeni">(null);
  const [mesaj, setMesaj] = useState<string | null>(null);

  const sutunlar = useMemo<SutunTanimi<SmmStokSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Malzeme",
        cell: (c) => (
          <span className="flex max-w-[22rem] min-w-[14rem] flex-col whitespace-normal">
            <span className="flex items-center gap-1.5">
              {c.row.original.kontrol && <TriangleAlert className="size-3.5 shrink-0 text-amber-600" aria-label="Kontrol edin" />}
              {c.row.original.ad ?? c.row.original.kod}
              {elle[c.row.original.kod] && (
                <Badge
                  variant="outline"
                  title={`Elle değişti: ${elle[c.row.original.kod].alanlar.join(", ")} · ${elle[c.row.original.kod].kullanici ?? ""}`}
                >
                  elle
                </Badge>
              )}
            </span>
            <span className="text-xs text-muted-foreground">
              {c.row.original.kod} · {turAdi(c.row.original.tur)}
            </span>
          </span>
        ),
      },
      {
        id: "dbs",
        accessorFn: (r) => Number(r.dbs_tutar),
        header: "Dönem başı",
        cell: (c) => <ParaHucresi deger={c.row.original.dbs_tutar} basamak={0} />,
      },
      {
        id: "alim",
        accessorFn: (r) => Number(r.alim_tutar),
        header: "Alım",
        cell: (c) => <ParaHucresi deger={c.row.original.alim_tutar} basamak={0} />,
      },
      {
        id: "ort",
        accessorFn: (r) => Number(r.ortalama_fiyat),
        header: "Ort. birim fiyat",
        cell: (c) => <ParaHucresi deger={c.row.original.ortalama_fiyat} basamak={4} />,
      },
      {
        id: "sayim",
        accessorFn: (r) => Number(r.sayim_miktar),
        header: "Sayım",
        cell: (c) => <Miktar deger={c.row.original.sayim_miktar} birim={c.row.original.birim} />,
      },
      {
        id: "dss",
        accessorFn: (r) => Number(r.dss_tutar),
        header: "Dönem sonu stok",
        cell: (c) => <ParaHucresi deger={c.row.original.dss_tutar} basamak={0} />,
      },
      {
        id: "sarf",
        accessorFn: (r) => Number(r.sarf_miktar),
        header: "Sarf",
        cell: (c) => <Miktar deger={c.row.original.sarf_miktar} birim={c.row.original.birim} />,
      },
      {
        id: "sarf_tutar",
        accessorFn: (r) => Number(r.sarf_tutar),
        header: "Sarf maliyeti",
        cell: (c) => <ParaHucresi deger={c.row.original.sarf_tutar} basamak={0} className="font-semibold" />,
      },
      {
        id: "duzenle",
        header: "",
        enableSorting: false,
        cell: (c) => (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            aria-label={`Düzenle ${c.row.original.kod}`}
            onClick={() => setDuzenlenen(c.row.original)}
          >
            <Pencil className="size-4" aria-hidden />
          </Button>
        ),
      },
    ],
    [elle],
  );

  if (donemler.data && liste.length === 0) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Stok ve Envanter" />
        <p className="rounded-2xl border border-dashed bg-card p-5 text-sm text-muted-foreground">
          Henüz dönem yok.{" "}
          <Link to="/smm" className="font-medium text-primary underline-offset-4 hover:underline">
            Dönemler
          </Link>{" "}
          sayfasından bir SMM Excel'i yükleyin.
        </p>
      </section>
    );
  }

  const top = v?.toplamlar;
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Stok ve Envanter"
        altBaslik="Dönem başı + alım = toplam; ortalama fiyatla sayım (dönem sonu stok) ve sarf. Excel'deki TABLO sayfasının karşılığı."
        eylemler={
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="outline" disabled={donemId === null} onClick={() => setDuzenlenen("yeni")}>
              <Plus className="size-4" aria-hidden />
              Kalem ekle
            </Button>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Dönem</span>
              <select
                aria-label="Dönem"
                className={SECIM_SINIFI}
                value={donemId ?? ""}
                onChange={(e) => setParams((p) => (p.set("donem", e.target.value), p))}
              >
                {liste.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.ad}
                  </option>
                ))}
              </select>
            </label>
          </div>
        }
      />
      {mesaj && (
        <p role="status" className="rounded-md bg-muted px-3 py-2 text-sm">
          {mesaj}
        </p>
      )}
      {duzenlenen !== null && donemId !== null && (
        <SmmKalemDuzenle
          donemId={donemId}
          kalem={duzenlenen === "yeni" ? null : duzenlenen}
          onKapat={() => setDuzenlenen(null)}
          onKaydedildi={setMesaj}
        />
      )}

      {top && (
        <div className="grid grid-cols-1 gap-3 rounded-2xl bg-kart-yesil p-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kart baslik="Dönem başı stok" deger={milyon(top.dbs_tutar)} simge={Warehouse} renk="acik" />
          <Kart baslik="Dönem içi alım" deger={milyon(top.alim_tutar)} simge={ShoppingCart} renk="acik" />
          <Kart baslik="Dönem sonu stok (sayım)" deger={milyon(top.dss_tutar)} simge={PackageCheck} renk="acik" />
          <Kart baslik="Üretime giden (sarf)" deger={milyon(top.uretime_giden)} simge={Factory} renk="acik" />
        </div>
      )}

      {v && v.turler.length > 0 && (
        <section aria-label="Türe göre" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
          <h2 className="text-base font-semibold">Türe göre</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground uppercase">
                  <th className="py-1.5 font-medium">Tür</th>
                  <th className="py-1.5 text-right font-medium">Kalem</th>
                  <th className="py-1.5 text-right font-medium">Dönem başı</th>
                  <th className="py-1.5 text-right font-medium">Alım</th>
                  <th className="py-1.5 text-right font-medium">Dönem sonu</th>
                  <th className="py-1.5 text-right font-medium">Sarf</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {v.turler.map((t) => (
                  <tr key={t.tur}>
                    <td className="py-1.5">
                      <button
                        type="button"
                        className={cn("text-left hover:underline", tur === t.tur && "font-semibold text-primary")}
                        onClick={() => setTur(tur === t.tur ? "" : t.tur)}
                      >
                        {turAdi(t.tur)}
                      </button>
                    </td>
                    <td className="py-1.5 text-right tabular-nums">{t.kalem}</td>
                    <td className="py-1.5 text-right tabular-nums">{paraBicimle(t.dbs_tutar, "TL", 0)}</td>
                    <td className="py-1.5 text-right tabular-nums">{paraBicimle(t.alim_tutar, "TL", 0)}</td>
                    <td className="py-1.5 text-right tabular-nums">{paraBicimle(t.dss_tutar, "TL", 0)}</td>
                    <td className="py-1.5 text-right font-semibold tabular-nums">{paraBicimle(t.sarf_tutar, "TL", 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

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
            <option key={t.tur} value={t.tur}>
              {turAdi(t.tur)}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={yalnizKontrol} onChange={(e) => setYalnizKontrol(e.target.checked)} />
          Yalnız kontrol edilecekler{v ? ` (${v.kontrol_sayisi})` : ""}
        </label>
        <span className="ml-auto text-sm text-muted-foreground">{v ? `${v.kayitlar.length} kalem` : ""}</span>
      </div>
      <p className="-mt-3 text-xs text-muted-foreground">
        Kontrol edilecekler: sayım, dönem başı + alımdan fazla çıkan (sarfı eksi) kalemler; üretim girişi ya da sayım kontrol edilmeli.
      </p>
      <VeriTablosu
        veri={v?.kayitlar ?? []}
        sutunlar={sutunlar}
        yukleniyor={q.isPending}
        hata={q.error as ApiHatasi | null}
        bosMetin={yalnizKontrol ? "Kontrol edilecek kalem yok" : "Kalem yok"}
      />
    </section>
  );
}
