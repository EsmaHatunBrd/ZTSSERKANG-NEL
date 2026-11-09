import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Boxes, CircleDollarSign, Percent, TrendingUp, Wallet } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { useKurRiski } from "@/api/sorgular/analiz";
import type { KurRiskiSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";

const RENK: Record<string, string> = { USD: "var(--chart-2)", EUR: "var(--chart-4)" };
const DIGER_RENK = ["var(--chart-3)", "var(--chart-5)", "var(--chart-1)"];
const renk = (pb: string, i: number) => RENK[pb] ?? DIGER_RENK[i % DIGER_RENK.length];

/** Sıralama için sayı (boş en alta). */
const sayi = (x: string | null) => (x === null ? null : Number(x));

/** Para birimi kırılımı: yıllık etkisi olan para birimleri, etkisi büyük olan üstte (yatay çubuk). Hepsi 0 ise gösterilmez. */
function ParaBirimleri({ satirlar: tum }: { satirlar: { para_birimi: string; yillik_etki: string; pay: string | null }[] }) {
  const digerleri = tum.filter((p) => p.para_birimi !== "USD" && p.para_birimi !== "EUR").map((p) => p.para_birimi);
  const satirlar = tum
    .filter((p) => !D(p.yillik_etki).isZero())
    .sort((a, b) => D(b.yillik_etki).comparedTo(D(a.yillik_etki)))
    .map((p) => ({ ...p, renk: renk(p.para_birimi, Math.max(0, digerleri.indexOf(p.para_birimi))) }));
  if (satirlar.length === 0) return null;
  return (
    <section aria-label="Para birimi kırılımı" className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      <h2 className="text-sm font-semibold">Yıllık etkinin para birimine göre dağılımı</h2>
      <ul className="flex flex-col gap-3">
        {satirlar.map((p) => (
          <li key={p.para_birimi} className="flex flex-col gap-1">
            <span className="flex items-baseline justify-between gap-3 text-sm">
              <span className="flex items-center gap-2">
                <span className="size-2.5 rounded-sm" style={{ background: p.renk }} aria-hidden />
                {p.para_birimi}
              </span>
              <span className="flex items-baseline gap-2 tabular-nums">
                <span className="font-semibold">{paraBicimle(p.yillik_etki, "TL", 0)}</span>
                <span className="text-xs text-muted-foreground">{p.pay === null ? "—" : yuzdeBicimle(p.pay)}</span>
              </span>
            </span>
            <span className="h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
              <span
                className="block h-full rounded-full"
                style={{
                  width: `${p.pay === null ? 0 : D(p.pay).times(100).clamp(0, 100).toFixed(2)}%`,
                  background: p.renk,
                }}
              />
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * Kur riski: ürün maliyetinin döviz payı ve tüm kurlar yazılan oran kadar artarsa ürün başına / yıllık etkisi.
 * Yıllık adet geçen yılın satış adedidir (Satış Geçmişi); satışı olmayan üründe yıllık etki hesaplanmaz. Hiçbir şey kaydedilmez.
 */
export default function KurRiski() {
  const { senaryoId } = useSenaryo();
  const gezin = useNavigate();
  const [oranMetni, setOranMetni] = useState("10");
  const [uygulanan, setUygulanan] = useState<string>("0.1");
  const oranApi = oranMetni.trim() === "" ? null : sayiApi(oranMetni.replace("%", ""), true);
  const oran = oranApi === null ? null : D(oranApi).dividedBy(100).toFixed();
  const q = useKurRiski(senaryoId, uygulanan);
  const oz = q.data?.ozet;
  const oranEtiketi = yuzdeBicimle(q.data?.oran ?? uygulanan, 0);
  // Hiçbir ürünün yıllık adeti yoksa yıllık tutarlar hesaplanamaz: "0 TL" yanıltıcı olur.
  const adetYok = !!oz && oz.urun_sayisi > 0 && oz.adetsiz_urun >= oz.urun_sayisi;

  function hesapla(e: FormEvent) {
    e.preventDefault();
    if (oran !== null) setUygulanan(oran);
  }

  // En çok etkilenen üstte: yıllık etki, yoksa birim etki; hatalılar sonda.
  const kayitlar = useMemo(() => {
    const k = [...(q.data?.kayitlar ?? [])];
    const anahtar = (r: KurRiskiSatiri) => D(r.yillik_etki ?? r.birim_etki ?? "-1e30");
    return k.sort((a, b) => {
      if (!!a.yillik_etki !== !!b.yillik_etki) return a.yillik_etki ? -1 : 1;
      return anahtar(b).comparedTo(anahtar(a));
    });
  }, [q.data]);

  const sutunlar = useMemo<SutunTanimi<KurRiskiSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex flex-col">
            <span>{c.row.original.ad}</span>
            <span className="text-xs text-muted-foreground">
              {c.row.original.hata ? <span className="text-destructive">{c.row.original.hata}</span> : c.row.original.kod}
            </span>
          </span>
        ),
      },
      { id: "maliyet", accessorFn: (r) => sayi(r.maliyet), header: "Maliyet", cell: (c) => <ParaHucresi deger={c.row.original.maliyet} /> },
      {
        id: "doviz_payi",
        accessorFn: (r) => sayi(r.doviz_payi),
        header: "Döviz payı",
        cell: (c) => <YuzdeHucresi deger={c.row.original.doviz_payi} className="font-medium" />,
      },
      {
        id: "usd_eur",
        accessorFn: (r) => sayi(r.usd_payi),
        header: "USD / EUR payı",
        cell: (c) => (
          <span className="block text-right text-sm text-muted-foreground tabular-nums">
            {c.row.original.usd_payi === null ? "—" : yuzdeBicimle(c.row.original.usd_payi)} /{" "}
            {c.row.original.eur_payi === null ? "—" : yuzdeBicimle(c.row.original.eur_payi)}
          </span>
        ),
      },
      {
        id: "birim_etki",
        accessorFn: (r) => sayi(r.birim_etki),
        header: "Birim etki",
        cell: (c) => <ParaHucresi deger={c.row.original.birim_etki} />,
      },
      {
        id: "yeni_maliyet",
        accessorFn: (r) => sayi(r.yeni_maliyet),
        header: "Yeni maliyet",
        cell: (c) => <ParaHucresi deger={c.row.original.yeni_maliyet} className="font-semibold" />,
      },
      {
        id: "yillik_adet",
        accessorFn: (r) => sayi(r.yillik_adet),
        header: "Yıllık adet",
        cell: (c) => <ParaHucresi deger={c.row.original.yillik_adet} paraBirimi="" basamak={0} />,
      },
      {
        id: "yillik_etki",
        accessorFn: (r) => sayi(r.yillik_etki),
        header: "Yıllık etki",
        cell: (c) => <ParaHucresi deger={c.row.original.yillik_etki} basamak={0} className="font-semibold" />,
      },
    ],
    [],
  );

  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Kur riski"
        altBaslik="Maliyetin ne kadarı döviz? Kur artarsa ürün başına ve yıllık ne kadar etkiler? Hiçbir şey kaydedilmez."
      />
      <form onSubmit={hesapla} aria-label="Kur artışı" className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Kur artışı</span>
          <span className="flex items-center gap-1.5">
            <Input
              inputMode="decimal"
              aria-label="Kur artış oranı (%)"
              className="w-24 text-right tabular-nums"
              value={oranMetni}
              aria-invalid={oran === null || undefined}
              onChange={(e) => setOranMetni(e.target.value)}
            />
            <span className="text-muted-foreground">%</span>
          </span>
        </label>
        <Button type="submit" disabled={senaryoId === null || oran === null || q.isFetching}>
          {q.isFetching ? "Hesaplanıyor…" : "Hesapla"}
        </Button>
        <span className="text-xs text-muted-foreground">
          USD, EUR ve diğer tüm kurlar aynı oranda artar. Düşüş için eksi yazın (ör. -5).
          {q.data && Object.keys(q.data.kurlar).length > 0 && (
            <>
              {" "}
              Bugünkü kurlar:{" "}
              {Object.entries(q.data.kurlar)
                .map(([pb, k]) => `${pb} ${paraBicimle(k, "", 4)}`)
                .join(" · ")}
            </>
          )}
        </span>
        {oran === null && (
          <p role="alert" className="w-full text-sm text-destructive">
            Kur artışı için sayı yazın (ör. 10 ya da -5).
          </p>
        )}
      </form>

      {oz && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kart baslik="Ortalama döviz payı" deger={oz.doviz_payi_ort === null ? "—" : yuzdeBicimle(oz.doviz_payi_ort)} simge={Percent} />
          <Kart baslik="Yıllık maliyet" deger={adetYok ? "—" : paraBicimle(oz.yillik_maliyet, "TL", 0)} simge={Wallet} />
          <Kart
            baslik={`Kur +${oranEtiketi} yıllık etkisi`}
            deger={adetYok ? "—" : paraBicimle(oz.yillik_etki, "TL", 0)}
            simge={TrendingUp}
          />
          <Kart
            baslik="Adeti olmayan ürün"
            deger={`${oz.adetsiz_urun} / ${oz.urun_sayisi}`}
            simge={Boxes}
            ton={oz.adetsiz_urun ? "dikkat" : "sakin"}
            hedef={senaryoId === null ? "/satis-gecmisi" : `/satis-gecmisi?senaryo=${senaryoId}`}
            eylem="Satış geçmişi"
          />
        </div>
      )}
      {q.data && <ParaBirimleri satirlar={q.data.para_birimleri} />}

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <CircleDollarSign className="size-3.5" aria-hidden />
        <span>
          En çok etkilenen ürün üstte. Yıllık adeti olmayan üründe yıllık etki "—" görünür: yıllık adet geçen yılın satış adedidir (Satış
          Geçmişi). Ürün ekranına gitmek için satıra tıklayın.
          {oz && oz.hatali > 0 && ` ${oz.hatali} ürünün maliyeti hesaplanamadı.`}
        </span>
      </div>
      <VeriTablosu
        veri={kayitlar}
        sutunlar={sutunlar}
        yukleniyor={q.isPending && senaryoId !== null}
        hata={q.error as ApiHatasi | null}
        bosMetin="Ürün yok"
        bosAciklama="Bu senaryoda hesaplanacak ürün bulunamadı."
        aramaAlani="ad"
        satirTikla={(r) => gezin(`/urunler/${encodeURIComponent(r.kod)}${senaryoId === null ? "" : `?senaryo=${senaryoId}`}`)}
      />
    </section>
  );
}
