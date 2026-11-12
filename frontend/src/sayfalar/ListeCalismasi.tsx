import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, Scale, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import { ApiHatasi, hataMetni, hataMetniVarsa } from "@/api/istemci";
import { useListeCalismasi, useListeOrnekSil, useListeOrnekUret, useListeYukle } from "@/api/sorgular/liste";
import { useParametreEkle } from "@/api/sorgular/parametreler";
import type { ListeCalismaSatiri, ListePazari } from "@/api/tipler";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
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
import { GecmisListeCekmecesi } from "@/sayfalar/liste/GecmisListeCekmecesi";
import { adimMetni, kutuMetni, PAZAR_ADI, PAZARLAR, yuvarlamaEtiketi } from "@/sayfalar/liste/listeYardimci";
import { YillikArtisGrafigi } from "@/sayfalar/liste/YillikArtisGrafigi";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { bugunIso } from "@/yardimcilar/tarih";

const SABLON_ADRESI = "/api/v1/liste-fiyatlari/sablon.xlsx";

/** Oran farkı (−0.1) -> "−10,0 puan". */
export function puanBicimle(fark: string | null): string {
  return fark === null ? "—" : `${paraBicimle(D(fark).times(100), "", 1)} puan`;
}

interface YuklemeHatasi {
  satir_no: number;
  mesaj: string;
}

function yuklemeHatalari(e: unknown): YuklemeHatasi[] {
  if (!(e instanceof ApiHatasi) || !Array.isArray(e.alanlar.hatalar)) return [];
  return (e.alanlar.hatalar as YuklemeHatasi[]).filter((h) => typeof h?.satir_no === "number");
}

function FarkHucresi({ fark }: { fark: string | null }) {
  const negatif = fark !== null && D(fark).isNegative() && !D(fark).isZero();
  return (
    <span
      className={cn(
        "block text-right tabular-nums",
        fark === null && "text-muted-foreground",
        negatif && "font-medium text-red-600 dark:text-red-400",
      )}
    >
      {fark === null ? "—" : paraBicimle(D(fark).times(100), "", 1)}
    </span>
  );
}

/**
 * Liste fiyatı çalışması (yalnız Berrak ürünleri, KDV hariç): her ürünün iki liste fiyatı var — yurtiçi (bölen vars. 0,63) ve
 * yurtdışı (vars. 0,90). Liste fiyatı = satış fiyatı ÷ bölen, seçilen adıma en yakına yuvarlanır. Bölen kutusu ve yuvarlama
 * seçimi kaydetmeden dener; "Ayarı kaydet" seçili pazarın bölenini ve/veya yuvarlamayı senaryo parametresine (geçmişli) yazar.
 * Geçmiş yılların liste fiyatı pazar bazında elle (ürün satırına tıklayınca) ya da Excel'den girilir; gerçek veri yokken örnek
 * veri üretilebilir (açıkça etiketli, tek tıkla silinir).
 */
export default function ListeCalismasi() {
  const { senaryoId, kilitli } = useSenaryo();
  const [params, setParams] = useSearchParams();
  const pazar: ListePazari = params.get("pazar") === "yurtdisi" ? "yurtdisi" : "yurtici";
  const kayitliSorgu = useListeCalismasi(senaryoId, { pazar });
  // Pazar değişirken önceki pazarın verisi (placeholder) kayıtlı değer sayılmaz.
  const kayitliVeri = kayitliSorgu.isPlaceholderData ? undefined : kayitliSorgu.data;
  const [bolenMetni, setBolenMetni] = useState<string | null>(null);
  const [deneme, setDeneme] = useState<string | undefined>(undefined);
  const [yuvarlamaSecimi, setYuvarlamaSecimi] = useState<string | null>(null);
  const kayitliBolen = kayitliVeri?.bolen;
  const kayitliYuvarlama = kayitliVeri?.yuvarlama;
  const yuvarlamaDeneme =
    yuvarlamaSecimi !== null && kayitliYuvarlama && !D(yuvarlamaSecimi).eq(D(kayitliYuvarlama)) ? yuvarlamaSecimi : undefined;

  function pazarSec(p: ListePazari) {
    if (p === pazar) return;
    setBolenMetni(null);
    setDeneme(undefined);
    setParams(
      (eski) => {
        const y = new URLSearchParams(eski);
        if (p === "yurtici") y.delete("pazar");
        else y.set("pazar", p);
        return y;
      },
      { replace: true },
    );
  }

  // Kutu yazıldıkça 400 ms sonra kaydetmeden yeniden hesaplanır; kayıtlı değere eşitse deneme yok.
  useEffect(() => {
    const t = setTimeout(() => {
      const api = bolenMetni === null ? null : sayiApi(bolenMetni);
      const gecerli = api !== null && D(api).gt(0) && D(api).lte(1);
      setDeneme(gecerli && kayitliBolen && !D(api).eq(D(kayitliBolen)) ? api : undefined);
    }, 400);
    return () => clearTimeout(t);
  }, [bolenMetni, kayitliBolen]);

  const denemeVar = deneme !== undefined || yuvarlamaDeneme !== undefined;
  const denenen = useListeCalismasi(senaryoId, { pazar, bolen: deneme, yuvarlama: yuvarlamaDeneme });
  const sorgu = denemeVar ? denenen : kayitliSorgu;
  const veri = sorgu.data;
  const yuvarlamaSecenekleri = useMemo(() => {
    const s = kayitliVeri?.yuvarlama_secenekleri ?? [];
    return kayitliYuvarlama && !s.some((x) => D(x).eq(D(kayitliYuvarlama))) ? [...s, kayitliYuvarlama] : s;
  }, [kayitliVeri, kayitliYuvarlama]);
  const seciliYuvarlama = (() => {
    const hedef = yuvarlamaSecimi ?? kayitliYuvarlama;
    if (!hedef) return "";
    return yuvarlamaSecenekleri.find((x) => D(x).eq(D(hedef))) ?? hedef;
  })();
  const etkinYuvarlama = yuvarlamaDeneme ?? kayitliYuvarlama ?? veri?.yuvarlama;
  const [secili, setSecili] = useState<string | null>(null);
  const [yalnizGeride, setYalnizGeride] = useState(false);
  const [kaydetAcik, setKaydetAcik] = useState(false);
  const [neden, setNeden] = useState("");
  const parametreEkle = useParametreEkle();
  const ornekUret = useListeOrnekUret();
  const ornekSil = useListeOrnekSil();
  const yukle = useListeYukle(senaryoId);
  const dosyaRef = useRef<HTMLInputElement>(null);
  const [dosya, setDosya] = useState<File | null>(null);
  const [yuklenen, setYuklenen] = useState<number | null>(null);

  const bolenGecersiz =
    bolenMetni !== null &&
    (() => {
      const a = sayiApi(bolenMetni);
      return a === null || !D(a).gt(0) || !D(a).lte(1);
    })();
  const kayitlar = useMemo(
    () => (veri?.kayitlar ?? []).filter((k) => !yalnizGeride || (k.fark !== null && D(k.fark).isNegative())),
    [veri, yalnizGeride],
  );
  const gecmisVar = (veri?.kayitlar ?? []).some((k) => k.gecmis.length > 0);
  const seciliSatir = (veri?.kayitlar ?? []).find((k) => k.kod === secili) ?? null;
  const oncekiYil = veri ? veri.yil - 1 : null;

  const sutunlar = useMemo<SutunTanimi<ListeCalismaSatiri>[]>(
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
      { accessorKey: "maliyet_tl", header: "Maliyet", cell: (c) => <ParaHucresi deger={c.row.original.maliyet_tl} /> },
      { accessorKey: "satis_tl", header: "Satış", cell: (c) => <ParaHucresi deger={c.row.original.satis_tl} /> },
      {
        id: "yeni_liste",
        accessorFn: (r) => (r.yeni_liste === null ? null : Number(r.yeni_liste)),
        header: "Yeni liste fiyatı",
        cell: (c) => {
          const ham = c.row.original.yeni_liste_ham;
          return (
            <span title={ham ? `Yuvarlamasız: ${paraBicimle(ham, "TL", 4)}` : undefined}>
              <ParaHucresi deger={c.row.original.yeni_liste} className="font-semibold" />
            </span>
          );
        },
      },
      {
        accessorKey: "onceki_liste",
        header: "Önceki liste",
        cell: (c) => (
          <span className="flex flex-col items-end">
            <ParaHucresi deger={c.row.original.onceki_liste} />
            {c.row.original.onceki_yil !== null && <span className="text-xs text-muted-foreground">{c.row.original.onceki_yil}</span>}
          </span>
        ),
      },
      {
        id: "liste_artis",
        accessorFn: (r) => (r.liste_artis === null ? null : Number(r.liste_artis)),
        header: "Liste artışı",
        cell: (c) => <YuzdeHucresi deger={c.row.original.liste_artis} />,
      },
      {
        id: "maliyet_artis",
        accessorFn: (r) => (r.maliyet_artis === null ? null : Number(r.maliyet_artis)),
        header: "Maliyet artışı",
        cell: (c) => <YuzdeHucresi deger={c.row.original.maliyet_artis} />,
      },
      {
        id: "fark",
        accessorFn: (r) => (r.fark === null ? null : Number(r.fark)),
        header: "Fark (puan)",
        cell: (c) => <FarkHucresi fark={c.row.original.fark} />,
      },
    ],
    [],
  );

  const ozet = veri?.ozet;
  const farkNegatif = ozet?.fark != null && D(ozet.fark).isNegative();
  const hatalar = yuklemeHatalari(yukle.error);
  const pazarAdi = PAZAR_ADI[pazar];

  async function ayarKaydet() {
    if (senaryoId === null || !neden.trim()) return;
    const ortak = { gecerlilik_basi: bugunIso(), neden: neden.trim(), kapsam_tipi: "genel" as const };
    try {
      if (deneme)
        await parametreEkle.mutateAsync({ anahtar: `liste_bolen_${pazar}`, senaryo: senaryoId, govde: { deger: deneme, ...ortak } });
      if (yuvarlamaDeneme)
        await parametreEkle.mutateAsync({ anahtar: "liste_yuvarlama", senaryo: senaryoId, govde: { deger: yuvarlamaDeneme, ...ortak } });
      setKaydetAcik(false);
      setBolenMetni(null);
      setDeneme(undefined);
      setYuvarlamaSecimi(null);
    } catch {
      // Hata diyalogda `parametreEkle.error` ile gösterilir.
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <SayfaSekmeleri etiket="Analiz türü" sekmeler={ANALIZ_SEKMELERI} />
      <SayfaBasligi
        baslik="Liste Çalışması"
        altBaslik={`${veri ? `${veri.yil} liste fiyatı önceki yıllarla ve maliyet artışıyla kıyaslanır. ` : ""}Her Berrak ürününün yurtiçi ve yurtdışı olmak üzere iki liste fiyatı vardır.`}
        eylemler={
          <a
            href={SABLON_ADRESI}
            download
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-input bg-background px-2.5 text-sm font-medium hover:bg-muted"
          >
            <Download className="size-4" aria-hidden />
            Şablonu indir
          </a>
        }
      />
      <KilitSeridi />

      <div className="flex flex-col gap-3 rounded-xl border bg-card p-4" aria-label="Liste ayarı">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Pazar</span>
            <div role="group" aria-label="Pazar" className="flex gap-1 rounded-lg border bg-muted p-1">
              {PAZARLAR.map((p) => (
                <button
                  key={p}
                  type="button"
                  aria-pressed={pazar === p}
                  onClick={() => pazarSec(p)}
                  className={cn(
                    "rounded-md px-3 py-1 text-sm transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
                    pazar === p ? "bg-background font-medium shadow-xs" : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {PAZAR_ADI[p]}
                </button>
              ))}
            </div>
          </div>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">{pazarAdi} böleni</span>
            <Input
              inputMode="decimal"
              aria-label={`${pazarAdi} böleni`}
              className="w-28 text-right tabular-nums"
              value={bolenMetni ?? (kayitliBolen ? kutuMetni(kayitliBolen) : "")}
              onChange={(e) => setBolenMetni(e.target.value)}
              aria-invalid={bolenGecersiz || undefined}
              title={kayitliVeri ? `Varsayılan: ${kutuMetni(kayitliVeri.varsayilan_bolen)}` : undefined}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">Yuvarlama</span>
            <select
              aria-label="Yuvarlama"
              value={seciliYuvarlama}
              disabled={yuvarlamaSecenekleri.length === 0}
              onChange={(e) => setYuvarlamaSecimi(e.target.value)}
              className="h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {yuvarlamaSecenekleri.map((x) => (
                <option key={x} value={x}>
                  {yuvarlamaEtiketi(x)}
                </option>
              ))}
            </select>
          </label>
          {denemeVar && (
            <div className="ml-auto flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setBolenMetni(null);
                  setDeneme(undefined);
                  setYuvarlamaSecimi(null);
                }}
              >
                Vazgeç
              </Button>
              <Button
                type="button"
                size="sm"
                disabled={kilitli || senaryoId === null || bolenGecersiz}
                title={kilitli ? "Senaryo kilitli" : undefined}
                onClick={() => {
                  parametreEkle.reset();
                  setNeden("");
                  setKaydetAcik(true);
                }}
              >
                Ayarı kaydet
              </Button>
            </div>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {kayitliVeri && (
            <>
              {kayitliVeri.bolen_kayitli
                ? `Kayıtlı ${pazarAdi.toLocaleLowerCase("tr")} böleni ${kutuMetni(kayitliVeri.bolen)}`
                : `Varsayılan ${pazarAdi.toLocaleLowerCase("tr")} böleni ${kutuMetni(kayitliVeri.varsayilan_bolen)} kullanılıyor`}
              {" · "}
              {kayitliVeri.yuvarlama_kayitli
                ? `kayıtlı yuvarlama ${yuvarlamaEtiketi(kayitliVeri.yuvarlama).toLocaleLowerCase("tr")}`
                : `varsayılan yuvarlama ${yuvarlamaEtiketi(kayitliVeri.varsayilan_yuvarlama).toLocaleLowerCase("tr")}`}
              .{" "}
            </>
          )}
          {denemeVar
            ? "Seçilen değerlerle deneniyor; kaydetmeden kalıcı olmaz."
            : "Değiştirince liste fiyatları anında yeniden hesaplanır."}
        </p>
        {bolenGecersiz && (
          <p role="alert" className="text-sm text-destructive">
            Bölen 0 ile 1 arasında bir sayı olmalı (ör. 0,63).
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1 text-sm text-muted-foreground" aria-label="Hesap kuralı">
        <p>
          Yalnız Berrak ürünleri · KDV hariç · liste fiyatı = satış fiyatı ÷ bölen
          {etkinYuvarlama ? `, en yakın ${adimMetni(etkinYuvarlama)} TL'ye yuvarlanır` : ""}
        </p>
        {veri && veri.berrak_disi > 0 && <p>{veri.berrak_disi} ürün Berrak olmadığı için listede yok.</p>}
      </div>

      {veri?.ornek_var && (
        <div
          role="note"
          className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-300 bg-sari px-4 py-3 text-sm dark:border-amber-800"
        >
          <p className="min-w-0 flex-1">
            <span className="font-semibold">Örnek veri.</span> Geçmiş yılların liste fiyatları ve maliyetleri tahminidir (yıllık yaklaşık
            %35–50 artış varsayımı). Gerçek liste fiyatları yüklenince ya da girilince değişir.
          </p>
          <Button type="button" variant="outline" size="sm" disabled={ornekSil.isPending} onClick={() => ornekSil.mutate()}>
            Örnek veriyi sil
          </Button>
        </div>
      )}

      {veri && !gecmisVar && (
        <div className="flex flex-col gap-3 rounded-xl border border-dashed bg-card p-5">
          <div>
            <h2 className="text-base font-semibold">Geçmiş liste fiyatı yok</h2>
            <p className="text-sm text-muted-foreground">
              Artışları görmek için önceki yılların liste fiyatları gerekli. Excel'den yükleyin, ürün satırına tıklayıp elle girin ya da
              gerçek veri gelene kadar örnek veriyle görünümü inceleyin.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={ornekUret.isPending || senaryoId === null}
              onClick={() => senaryoId !== null && ornekUret.mutate(senaryoId)}
            >
              Örnek veriyle göster
            </Button>
          </div>
          {ornekUret.error && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetni(ornekUret.error)}
            </p>
          )}
        </div>
      )}

      {veri && gecmisVar && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Kart
              baslik={`Ortalama liste artışı (${oncekiYil}→${veri.yil})`}
              deger={ozet?.liste_artis_ort ? yuzdeBicimle(ozet.liste_artis_ort) : "—"}
              simge={TrendingUp}
              renk="yesil"
            />
            <Kart
              baslik={`Ortalama maliyet artışı (${oncekiYil}→${veri.yil})`}
              deger={ozet?.maliyet_artis_ort ? yuzdeBicimle(ozet.maliyet_artis_ort) : "—"}
              simge={Wallet}
              renk="turuncu"
            />
            <Kart
              baslik="Fark (liste − maliyet)"
              deger={puanBicimle(ozet?.fark ?? null)}
              simge={Scale}
              renk="mavi"
              ton={farkNegatif ? "hata" : "sakin"}
            />
            <Kart
              baslik="Maliyetin gerisinde kalan ürün"
              deger={ozet ? `${ozet.gerisinde} / ${ozet.karsilastirilan}` : "—"}
              simge={TrendingDown}
              renk="sari"
              ton={ozet?.gerisinde ? "dikkat" : "sakin"}
              onTikla={() => setYalnizGeride(true)}
              eylem="Göster"
            />
          </div>
          {veri.yillar.length > 0 && <YillikArtisGrafigi yillar={veri.yillar} />}
        </>
      )}

      {veri && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-base font-semibold">Ürünler</h2>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={yalnizGeride} onChange={(e) => setYalnizGeride(e.target.checked)} />
              Yalnız maliyetin gerisinde kalanlar
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            Geçmiş yılların liste fiyatını girmek ya da düzeltmek için ürün satırına tıklayın.
          </p>
        </div>
      )}
      <VeriTablosu
        veri={kayitlar}
        sutunlar={sutunlar}
        yukleniyor={sorgu.isPending}
        hata={sorgu.error as ApiHatasi | null}
        bosMetin={yalnizGeride ? "Maliyetin gerisinde kalan ürün yok" : "Ürün yok"}
        aramaAlani="ad"
        satirTikla={(r) => setSecili(r.kod)}
      />

      <div className="flex flex-col gap-2 rounded-xl border bg-card p-4" aria-label="Excel'den yükleme">
        <h2 className="text-base font-semibold">Excel'den yükle</h2>
        <p className="text-sm text-muted-foreground">
          Sütunlar: ürün kodu, yıl, liste fiyatı, birim maliyet (isteğe bağlı), pazar (isteğe bağlı: Yurtiçi/Yurtdışı; boşsa Yurtiçi). Aynı
          ürün, yıl ve pazar tekrar yüklenirse eski değerin yerine geçer; örnek veri gerçek değerle değiştirilir.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <Input
            ref={dosyaRef}
            type="file"
            accept=".csv,.xlsx"
            aria-label="Dosya seç"
            className="max-w-sm"
            onChange={(e) => {
              setDosya(e.target.files?.[0] ?? null);
              setYuklenen(null);
              yukle.reset();
            }}
          />
          <Button
            type="button"
            disabled={!dosya || yukle.isPending}
            onClick={() =>
              dosya &&
              yukle.mutate(dosya, {
                onSuccess: (o) => {
                  setYuklenen(o.yazilan);
                  setDosya(null);
                  if (dosyaRef.current) dosyaRef.current.value = "";
                },
              })
            }
          >
            Yükle
          </Button>
        </div>
        <div aria-live="polite">
          {yuklenen !== null && (
            <p role="status" className="text-sm text-green-800 dark:text-green-300">
              {yuklenen} satır yazıldı.
            </p>
          )}
          {yukle.error && (
            <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-900 dark:bg-red-950/40 dark:text-red-200">
              {hatalar.length > 0 ? (
                <>
                  <p className="font-medium">Dosyada hatalı satırlar var; hiçbir satır yazılmadı.</p>
                  <ul className="mt-1 list-disc pl-5">
                    {hatalar.map((h) => (
                      <li key={h.satir_no}>
                        Satır {h.satir_no}: {h.mesaj}
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                hataMetni(yukle.error)
              )}
            </div>
          )}
        </div>
      </div>

      {veri && (
        <GecmisListeCekmecesi
          satir={seciliSatir}
          yil={veri.yil}
          pazar={pazar}
          bolen={veri.bolen}
          yuvarlama={veri.yuvarlama}
          onKapat={() => setSecili(null)}
        />
      )}

      {kaydetAcik && denemeVar && senaryoId !== null && (
        <OnayDiyalogu
          baslik="Liste ayarı kaydedilsin mi?"
          onayMetni="Kaydet"
          bekliyor={parametreEkle.isPending}
          hata={hataMetniVarsa(parametreEkle.error)}
          onOnayla={() => void ayarKaydet()}
          onVazgec={() => setKaydetAcik(false)}
        >
          <ul className="list-disc pl-5">
            {deneme && (
              <li>
                {pazarAdi} böleni {kayitliBolen ? kutuMetni(kayitliBolen) : "—"} yerine {kutuMetni(deneme)} olacak.
              </li>
            )}
            {yuvarlamaDeneme && (
              <li>
                Yuvarlama {kayitliYuvarlama ? yuvarlamaEtiketi(kayitliYuvarlama).toLocaleLowerCase("tr") : "—"} yerine{" "}
                {yuvarlamaEtiketi(yuvarlamaDeneme).toLocaleLowerCase("tr")} olacak.
              </li>
            )}
          </ul>
          <p>Değişiklik Parametreler'de geçmişiyle saklanır.</p>
          <label className="flex flex-col gap-1">
            <span className="text-muted-foreground">Neden (zorunlu)</span>
            <Input aria-label="Neden" value={neden} onChange={(e) => setNeden(e.target.value)} />
          </label>
        </OnayDiyalogu>
      )}
    </section>
  );
}
