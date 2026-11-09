import { useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Banknote, CircleAlert, Percent, TrendingUp } from "lucide-react";
import type { ApiHatasi } from "@/api/istemci";
import { useHedefFiyat } from "@/api/sorgular/analiz";
import type { HedefFiyatSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { ANALIZ_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";

/** Kârlılık haritasıyla aynı bölge etiketleri ve sırası (önce müdahale gereken). */
const BOLGELER = [
  { ad: "yuksek_adet_dusuk_marj", etiket: "Fiyatı gözden geçir", renk: "var(--chart-5)" },
  { ad: "yuksek_adet_yuksek_marj", etiket: "Yıldız", renk: "var(--chart-1)" },
  { ad: "dusuk_adet_yuksek_marj", etiket: "Büyütülebilir", renk: "var(--chart-2)" },
  { ad: "dusuk_adet_dusuk_marj", etiket: "Sorgula", renk: "var(--chart-4)" },
] as const;
const BOLGE: Record<string, (typeof BOLGELER)[number]> = Object.fromEntries(BOLGELER.map((b) => [b.ad, b]));

const sayi = (x: string | null) => (x === null ? null : Number(x));
/** Oran ("0.15") -> kutuya yazılacak yüzde metni ("15", "12,5"). */
const yuzdeMetni = (oran: string) => D(oran).times(100).toFixed().replace(".", ",");
const zamVar = (r: HedefFiyatSatiri) => r.gereken_zam !== null && D(r.gereken_zam).greaterThan(0);

/**
 * Marjı koruyan fiyat: bugünkü maliyetle hedef marjı tutturan satış fiyatı, geçen yılın gerçek fiyatına göre gereken zam ve liste
 * fiyatı. Hedef marj boşsa sunucu marj eşiğini kullanır. Hiçbir şey kaydedilmez.
 */
export default function HedefFiyat() {
  const { senaryoId } = useSenaryo();
  const gezin = useNavigate();
  const [params, setParams] = useSearchParams();
  const bolge = params.get("bolge");
  const seciliBolge = bolge && bolge in BOLGE ? bolge : null;
  const [yalnizZam, setYalnizZam] = useState(true);

  // null: kullanıcı kutuya dokunmadı; kutu sunucunun kullandığı marjı gösterir.
  const [marjMetni, setMarjMetni] = useState<string | null>(null);
  const [uygulanan, setUygulanan] = useState<string | null>(null);
  const q = useHedefFiyat(senaryoId, uygulanan);
  const v = q.data;
  const oz = v?.ozet;

  const kutuDegeri = marjMetni ?? (v ? yuzdeMetni(v.marj) : "");
  const bos = kutuDegeri.trim() === "";
  const marjApi = bos ? null : sayiApi(kutuDegeri.replace("%", ""));
  const marj = marjApi === null ? null : D(marjApi).dividedBy(100).toFixed();
  const gecersiz = !bos && marj === null;

  function hesapla(e: FormEvent) {
    e.preventDefault();
    if (gecersiz) return;
    // Boş kutu: sunucu marj eşiğini kullanır; kutu yeniden gelen değeri gösterir.
    setUygulanan(marj);
    if (marj === null) setMarjMetni(null);
  }

  function bolgeSec(ad: string | null) {
    setParams(
      (p) => {
        const y = new URLSearchParams(p);
        if (ad === null) y.delete("bolge");
        else y.set("bolge", ad);
        return y;
      },
      { replace: true },
    );
  }

  const hatalilar = useMemo(() => (v?.kayitlar ?? []).filter((r) => r.hata), [v]);

  // Yıllık ek geliri büyük olan üstte; ek geliri hesaplanamayanlar gereken zama göre, sonra sonda.
  const kayitlar = useMemo(() => {
    const k = (v?.kayitlar ?? []).filter((r) => !r.hata && (seciliBolge === null || r.bolge === seciliBolge) && (!yalnizZam || zamVar(r)));
    const ek = (r: HedefFiyatSatiri) => D(r.yillik_ek_gelir ?? "-1e30");
    const zam = (r: HedefFiyatSatiri) => D(r.gereken_zam ?? "-1e30");
    return k.sort((a, b) => ek(b).comparedTo(ek(a)) || zam(b).comparedTo(zam(a)));
  }, [v, seciliBolge, yalnizZam]);

  const sutunlar = useMemo<SutunTanimi<HedefFiyatSatiri>[]>(
    () => [
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: (c) => (
          <span className="flex flex-col">
            <span>{c.row.original.ad}</span>
            <span className="text-xs text-muted-foreground">{c.row.original.kod}</span>
          </span>
        ),
      },
      {
        id: "bolge",
        accessorFn: (r) => (r.bolge && BOLGE[r.bolge] ? BOLGE[r.bolge].etiket : ""),
        header: "Bölge",
        cell: (c) => {
          const b = c.row.original.bolge ? BOLGE[c.row.original.bolge] : undefined;
          if (!b) return <span className="text-muted-foreground">—</span>;
          return (
            <span className="flex items-center gap-1.5 whitespace-nowrap">
              <span className="size-2.5 rounded-full" style={{ background: b.renk }} aria-hidden />
              {b.etiket}
            </span>
          );
        },
      },
      { id: "maliyet", accessorFn: (r) => sayi(r.maliyet), header: "Maliyet", cell: (c) => <ParaHucresi deger={c.row.original.maliyet} /> },
      {
        id: "gecen_yil_fiyat",
        accessorFn: (r) => sayi(r.gecen_yil_fiyat),
        header: "Geçen yıl fiyatı",
        cell: (c) => <ParaHucresi deger={c.row.original.gecen_yil_fiyat} />,
      },
      {
        id: "mevcut_marj",
        accessorFn: (r) => sayi(r.mevcut_marj),
        header: "Mevcut marj",
        cell: (c) => <YuzdeHucresi deger={c.row.original.mevcut_marj} />,
      },
      {
        id: "hedef_fiyat",
        accessorFn: (r) => sayi(r.hedef_fiyat),
        header: "Hedef fiyat",
        cell: (c) => <ParaHucresi deger={c.row.original.hedef_fiyat} className="font-semibold" />,
      },
      {
        id: "gereken_zam",
        accessorFn: (r) => sayi(r.gereken_zam),
        header: "Gereken zam",
        cell: (c) => (
          <YuzdeHucresi
            deger={c.row.original.gereken_zam}
            className={cn("font-medium", zamVar(c.row.original) && "text-amber-700 dark:text-amber-400")}
          />
        ),
      },
      {
        id: "liste_fiyati",
        accessorFn: (r) => sayi(r.liste_fiyati),
        header: "Liste fiyatı",
        cell: (c) => <ParaHucresi deger={c.row.original.liste_fiyati} />,
      },
      {
        id: "adet",
        accessorFn: (r) => sayi(r.adet),
        header: "Yıllık adet",
        cell: (c) => <ParaHucresi deger={c.row.original.adet} paraBirimi="" basamak={0} />,
      },
      {
        id: "yillik_ek_gelir",
        accessorFn: (r) => sayi(r.yillik_ek_gelir),
        header: "Yıllık ek gelir",
        cell: (c) => <ParaHucresi deger={c.row.original.yillik_ek_gelir} basamak={0} className="font-semibold" />,
      },
    ],
    [],
  );

  // Kartla aynı: yalnız zam gereken (pozitif) ek gelirler toplanır.
  const toplamSatiri = (satirlar: HedefFiyatSatiri[]) => ({
    ad: <span className="font-semibold">Toplam ({satirlar.length} ürün)</span>,
    yillik_ek_gelir: (
      <ParaHucresi
        deger={satirlar
          .reduce((t, r) => (r.yillik_ek_gelir === null || D(r.yillik_ek_gelir).lte(0) ? t : t.plus(r.yillik_ek_gelir)), D(0))
          .toFixed()}
        basamak={0}
        className="font-semibold"
      />
    ),
  });

  const urunYolu = (kod: string) => `/urunler/${encodeURIComponent(kod)}${senaryoId === null ? "" : `?senaryo=${senaryoId}`}`;
  const bolen = v ? paraBicimle(v.bolen, "", 2) : "…";

  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Marjı koruyan fiyat"
        altBaslik={`Hedef fiyat = maliyet × (1 + hedef marj). Gereken zam, geçen yılın gerçek satış fiyatına göredir. Liste fiyatı = hedef fiyat ÷ ${bolen}. Hiçbir şey kaydedilmez.`}
      />

      <form onSubmit={hesapla} aria-label="Hedef marj" className="flex flex-wrap items-end gap-3 rounded-xl border bg-card p-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Hedef marj</span>
          <span className="flex items-center gap-1.5">
            <Input
              inputMode="decimal"
              aria-label="Hedef marj (%)"
              className="w-24 text-right tabular-nums"
              value={kutuDegeri}
              aria-invalid={gecersiz || undefined}
              onChange={(e) => setMarjMetni(e.target.value)}
            />
            <span className="text-muted-foreground">%</span>
          </span>
        </label>
        <Button type="submit" disabled={senaryoId === null || gecersiz || q.isFetching}>
          {q.isFetching ? "Hesaplanıyor…" : "Hesapla"}
        </Button>
        <span className="text-xs text-muted-foreground">
          Boş bırakırsanız Parametreler'deki marj eşiği kullanılır.
          {v && ` Bölen: ${bolen}. Yıllık adet: ${v.adet_kaynagi === "satis_gecmisi" ? "geçen yılın satış adedi" : v.adet_kaynagi}.`}
        </span>
        {gecersiz && (
          <p role="alert" className="w-full text-sm text-destructive">
            Hedef marj için sayı yazın (ör. 15 ya da 12,5).
          </p>
        )}
      </form>

      {oz && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Kart
            baslik="Zam gereken ürün"
            deger={`${oz.zam_gereken} / ${oz.urun_sayisi}`}
            simge={TrendingUp}
            ton={oz.zam_gereken ? "dikkat" : "sakin"}
          />
          <Kart
            baslik="Ortalama gereken zam (ciro ağırlıklı)"
            deger={oz.ort_zam === null ? "—" : yuzdeBicimle(oz.ort_zam)}
            simge={Percent}
          />
          <Kart baslik="Yıllık ek gelir (zam yapılırsa)" deger={paraBicimle(oz.yillik_ek_gelir, "TL", 0)} simge={Banknote} />
          <Kart
            baslik="Geçen yıl fiyatı olmayan ürün"
            deger={`${oz.fiyatsiz} / ${oz.urun_sayisi}`}
            simge={CircleAlert}
            ton={oz.fiyatsiz ? "dikkat" : "sakin"}
            hedef={senaryoId === null ? "/satis-gecmisi" : `/satis-gecmisi?senaryo=${senaryoId}`}
            eylem="Satış geçmişi"
          />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Bölge" className="flex flex-wrap gap-1 rounded-xl border bg-muted p-1">
          {[{ ad: null, etiket: "Tümü", renk: null }, ...BOLGELER].map((b) => {
            const acik = seciliBolge === b.ad;
            return (
              <button
                key={b.ad ?? "tumu"}
                type="button"
                aria-pressed={acik}
                onClick={() => bolgeSec(b.ad)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                  acik ? "bg-background font-medium shadow-xs" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {b.renk && <span className="size-2.5 rounded-full" style={{ background: b.renk }} aria-hidden />}
                {b.etiket}
              </button>
            );
          })}
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="size-4 accent-primary" checked={yalnizZam} onChange={(e) => setYalnizZam(e.target.checked)} />
          Yalnız zam gerekenler
        </label>
      </div>

      <p className="text-xs text-muted-foreground">
        Yıllık ek geliri büyük olan üstte. Geçen yıl fiyatı olmayan üründe zam ve ek gelir "—" görünür. Ürün ekranına gitmek için satıra
        tıklayın.
      </p>
      <VeriTablosu
        veri={kayitlar}
        sutunlar={sutunlar}
        toplamSatiri={toplamSatiri}
        yukleniyor={q.isPending && senaryoId !== null}
        hata={q.error as ApiHatasi | null}
        bosMetin={yalnizZam ? "Zam gereken ürün yok" : "Ürün yok"}
        bosAciklama={
          yalnizZam
            ? 'Bu süzmede tüm ürünler hedef marjı tutturuyor. Tümünü görmek için "Yalnız zam gerekenler" kutusunu kaldırın.'
            : "Bu süzmede hesaplanacak ürün bulunamadı."
        }
        aramaAlani="ad"
        satirTikla={(r) => gezin(urunYolu(r.kod))}
      />

      {hatalilar.length > 0 && (
        <section aria-label="Hesaplanamayan ürünler" className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
          <h2 className="font-semibold text-destructive">{hatalilar.length} ürünün hedef fiyatı hesaplanamadı</h2>
          <ul className="mt-2 flex flex-col gap-1">
            {hatalilar.map((r) => (
              <li key={r.kod}>
                <button type="button" className="text-left underline-offset-2 hover:underline" onClick={() => gezin(urunYolu(r.kod))}>
                  {r.ad} ({r.kod})
                </button>
                : <span className="text-muted-foreground">{r.hata}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  );
}
