import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Percent, TrendingUp, TriangleAlert, Boxes } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import type { AnalizOzeti, AnalizSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, yuzdeBicimle } from "@/yardimcilar/para";

/** Artış kırmızı (maliyet yükseliyor), düşüş yeşil; 0 soluk. */
function DegisimHucresi({ deger }: { deger: string | null }) {
  if (deger === null) return <span className="block text-right text-muted-foreground">—</span>;
  const d = D(deger);
  return (
    <span
      className={cn(
        "block text-right font-medium tabular-nums",
        d.isZero() ? "text-muted-foreground" : d.isPositive() ? "text-red-600 dark:text-red-400" : "text-green-700 dark:text-green-400",
      )}
    >
      {d.isPositive() && !d.isZero() ? "+" : ""}
      {yuzdeBicimle(deger)}
    </span>
  );
}

interface Props {
  ozet: AnalizOzeti | undefined;
  kayitlar: AnalizSatiri[];
  marjEsigi: string | undefined;
  yukleniyor: boolean;
  hata: ApiHatasi | null;
  bosMetin: string;
}

/**
 * Ya olursa ve zam etkisi sonucunun ortak gösterimi: özet kartları ve ürün tablosu (en çok etkilenen üstte). "Fiyat aynı kalırsa kâr",
 * satış fiyatı değiştirilmezse kalan kâr oranıdır; marj eşiğinin altındakiler işaretlenir ve süzülebilir. Satıra tıklayınca ürün ekranı açılır.
 */
export function AnalizSonucu({ ozet, kayitlar, marjEsigi, yukleniyor, hata, bosMetin }: Props) {
  const gezin = useNavigate();
  const { senaryoId } = useSenaryo();
  const [yalnizEsikAlti, setYalnizEsikAlti] = useState(false);
  const esik = marjEsigi ? yuzdeBicimle(marjEsigi, 0) : "—";
  const gorunen = useMemo(() => (yalnizEsikAlti ? kayitlar.filter((k) => k.esik_alti) : kayitlar), [kayitlar, yalnizEsikAlti]);

  const sutunlar = useMemo<SutunTanimi<AnalizSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex flex-col">
            <span>{c.row.original.ad}</span>
            <span className="text-xs text-muted-foreground">{c.row.original.hata ?? c.row.original.kod}</span>
          </span>
        ),
      },
      { accessorKey: "maliyet_once", header: "Maliyet (bugün)", cell: (c) => <ParaHucresi deger={c.row.original.maliyet_once} /> },
      {
        accessorKey: "maliyet_sonra",
        header: "Maliyet (varsayımla)",
        cell: (c) => <ParaHucresi deger={c.row.original.maliyet_sonra} className="font-semibold" />,
      },
      { accessorKey: "fark_tl", header: "Fark", cell: (c) => <ParaHucresi deger={c.row.original.fark_tl} /> },
      {
        id: "fark_yuzde",
        accessorFn: (r) => (r.fark_yuzde === null ? null : Number(r.fark_yuzde)),
        header: "Değişim",
        cell: (c) => <DegisimHucresi deger={c.row.original.fark_yuzde} />,
      },
      { accessorKey: "satis_sonra", header: "Yeni satış fiyatı", cell: (c) => <ParaHucresi deger={c.row.original.satis_sonra} /> },
      {
        id: "mevcut_fiyatla_kar",
        accessorFn: (r) => (r.mevcut_fiyatla_kar === null ? null : Number(r.mevcut_fiyatla_kar)),
        header: "Fiyat aynı kalırsa kâr",
        cell: (c) => (
          <span className="flex items-center justify-end gap-1.5">
            {c.row.original.esik_alti && <TriangleAlert className="size-3.5 text-amber-600" aria-label="Eşiğin altında" />}
            <YuzdeHucresi
              deger={c.row.original.mevcut_fiyatla_kar}
              className={cn(c.row.original.esik_alti && "font-semibold text-red-600 dark:text-red-400")}
            />
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      {ozet && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kart baslik="Ortalama maliyet değişimi" deger={ozet.ort_fark_yuzde ? yuzdeBicimle(ozet.ort_fark_yuzde) : "—"} simge={Percent} />
          <Kart
            baslik="En yüksek değişim"
            deger={ozet.en_yuksek_fark_yuzde ? yuzdeBicimle(ozet.en_yuksek_fark_yuzde) : "—"}
            simge={TrendingUp}
          />
          <Kart baslik="Etkilenen ürün" deger={`${ozet.etkilenen} / ${ozet.urun_sayisi}`} simge={Boxes} />
          <Kart
            baslik={`Fiyat aynı kalırsa kârı ${esik} altına düşen`}
            deger={ozet.esik_alti}
            simge={TriangleAlert}
            ton={ozet.esik_alti ? "hata" : "sakin"}
            onTikla={() => setYalnizEsikAlti(true)}
            eylem="Göster"
          />
        </div>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          "Fiyat aynı kalırsa kâr": satış fiyatı bugünkü gibi kalırsa yeni maliyete göre kâr oranı. Ürün ekranına gitmek için satıra
          tıklayın.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={yalnizEsikAlti} onChange={(e) => setYalnizEsikAlti(e.target.checked)} />
          Yalnız kârı {esik} altına düşenler
        </label>
      </div>
      <VeriTablosu
        veri={gorunen}
        sutunlar={sutunlar}
        yukleniyor={yukleniyor}
        hata={hata}
        bosMetin={yalnizEsikAlti ? `Kârı ${esik} altına düşen ürün yok` : bosMetin}
        aramaAlani="ad"
        satirTikla={(r) => gezin(`/urunler/${encodeURIComponent(r.kod)}${senaryoId === null ? "" : `?senaryo=${senaryoId}`}`)}
      />
    </div>
  );
}
