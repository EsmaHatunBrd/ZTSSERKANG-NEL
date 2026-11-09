import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Columns3, Copy, Download, PackagePlus, Upload, X } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import type Decimal from "decimal.js";
import { useTutarlilik } from "@/api/sorgular/tutarlilik";
import { useUrunler } from "@/api/sorgular/urunler";
import { useUyarilar } from "@/api/sorgular/uyarilar";
import type { ApiHatasi } from "@/api/istemci";
import type { DashboardSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button, buttonVariants } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { D, paraBicimle, topla } from "@/yardimcilar/para";
import { ambalajMetni } from "@/yardimcilar/ambalaj";
import { useSenaryoSayfasi } from "@/yardimcilar/sayfalama";
import { AmbalajOzeti } from "./dashboard/AmbalajOzeti";
import { GerceklesenSeridi } from "./dashboard/GerceklesenSeridi";
import { VeriKontroluSeridi } from "./dashboard/VeriKontroluSeridi";
import { GenelGrafikler } from "./dashboard/GenelGrafikler";
import { OneCikanlar } from "./dashboard/OneCikanlar";
import { UstKartlar } from "./dashboard/UstKartlar";
import { UyariHucresi } from "./dashboard/UyariHucresi";
import { EnflasyonRozeti } from "./karsilastirma/EnflasyonRozeti";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";

/** Tek sayfada tüm ürünler (sunucu üst sınırı 500): arama ve süzgeçler hepsini kapsar. Daha fazlası olursa sayfalama görünür. */
const BOYUT = 500;

/** Üretim adedi: tam sayı gösterimi (Intl'e metin verilir, Number() ile hassasiyet kaybı olmaz). */
function adetBicimle(d: string | Decimal): string {
  const metin = typeof d === "string" ? d : d.toFixed(0);
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 }).format(metin as unknown as number);
}

const tr = (s: string) => s.toLocaleLowerCase("tr");

/** İsteğe bağlı sütun grupları: varsayılan tablo sade kalır, kullanıcı "Sütunlar" menüsünden açar (tarayıcıda hatırlanır). */
export const SUTUN_GRUPLARI = [
  {
    anahtar: "kirilim",
    etiket: "Maliyet kırılımı",
    aciklama: "Reçete maliyeti, GÜG, faaliyet, finans, gider %",
  },
  {
    anahtar: "firesiz",
    etiket: "Firesiz maliyet",
    aciklama: "Tüm fireler 0 iken maliyet",
  },
  {
    anahtar: "doviz",
    etiket: "Maliyet USD / EUR",
    aciklama: "Senaryo kurlarıyla",
  },
  {
    anahtar: "karsilastirma",
    etiket: "Karşılaştırma",
    aciklama: "Geçen yıl, enflasyon eşiği, hedef adetle maliyet",
  },
  {
    anahtar: "uretim",
    etiket: "Üretim adedi",
    aciklama: "Vardiya üretim adedi; toplam satırında toplanır",
  },
] as const;
export type SutunGrubu = (typeof SUTUN_GRUPLARI)[number]["anahtar"];
type SutunSecimi = Record<SutunGrubu, boolean>;

export const SUTUN_ANAHTARI = "fiyat-calismasi.dashboard.sutunlar";
const VARSAYILAN_SUTUNLAR: SutunSecimi = {
  kirilim: false,
  firesiz: false,
  doviz: false,
  karsilastirma: false,
  uretim: true,
};

function sutunSecimiOku(): SutunSecimi {
  try {
    const ham = localStorage.getItem(SUTUN_ANAHTARI);
    return ham ? { ...VARSAYILAN_SUTUNLAR, ...(JSON.parse(ham) as Partial<SutunSecimi>) } : VARSAYILAN_SUTUNLAR;
  } catch {
    return VARSAYILAN_SUTUNLAR;
  }
}

const SECIM =
  "h-9 rounded-lg border border-input bg-card px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** "Sütunlar" açılır menüsü (yerel <details>): isteğe bağlı sütun gruplarını açıp kapatır. */
function SutunMenusu({ secim, degistir }: { secim: SutunSecimi; degistir: (g: SutunGrubu, acik: boolean) => void }) {
  const acikSayisi = SUTUN_GRUPLARI.filter((g) => secim[g.anahtar]).length;
  return (
    <details className="group relative">
      <summary className={cn(buttonVariants({ variant: "outline" }), "h-9 cursor-pointer list-none [&::-webkit-details-marker]:hidden")}>
        <Columns3 aria-hidden />
        Sütunlar{acikSayisi > 0 ? ` (${acikSayisi})` : ""}
        <ChevronDown className="transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <fieldset className="absolute right-0 z-30 mt-1 flex w-80 flex-col gap-2 rounded-xl border bg-popover p-3 text-popover-foreground shadow-lg">
        <legend className="sr-only">Gösterilecek sütunlar</legend>
        {SUTUN_GRUPLARI.map((g) => (
          <label key={g.anahtar} className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" checked={secim[g.anahtar]} onChange={(e) => degistir(g.anahtar, e.target.checked)} />
            <span>
              {g.etiket}
              <span className="block text-xs text-muted-foreground">{g.aciklama}</span>
            </span>
          </label>
        ))}
      </fieldset>
    </details>
  );
}

/** Hedef adetle maliyet + bütçe maliyetinden farkı küçük gri metin (TL). */
function HedefAdetHucresi({ satir }: { satir: DashboardSatiri }) {
  const hedef = satir.hedef_adet_maliyet_tl ?? null;
  if (hedef === null) return <span className="block text-right text-muted-foreground">—</span>;
  const fark = satir.maliyet_tl != null ? D(hedef).minus(D(satir.maliyet_tl)).toDecimalPlaces(2) : null;
  return (
    <span className="flex flex-col items-end">
      <ParaHucresi deger={hedef} />
      {fark !== null && (
        <span className="text-xs text-muted-foreground tabular-nums" aria-label="Bütçe maliyetinden fark">
          {fark.isPositive() && !fark.isZero() ? "+" : ""}
          {paraBicimle(fark.isZero() ? "0" : fark, "TL", 2)}
        </span>
      )}
    </span>
  );
}

export default function Dashboard() {
  const { senaryoId, senaryo, senaryolar, yukleniyor: senaryoYukleniyor, yeniCalismaAc } = useSenaryo();
  const gezin = useNavigate();
  const [gecici, setGecici] = useState(false);
  const [arama, setArama] = useState("");
  const [hat, setHat] = useState("");
  const [enflasyon, setEnflasyon] = useState("");
  const [yalnizHatali, setYalnizHatali] = useState(false);
  const [sutunSecimi, setSutunSecimi] = useState<SutunSecimi>(sutunSecimiOku);

  function sutunDegistir(g: SutunGrubu, acik: boolean) {
    setSutunSecimi((onceki) => {
      const yeni = { ...onceki, [g]: acik };
      try {
        localStorage.setItem(SUTUN_ANAHTARI, JSON.stringify(yeni));
      } catch {
        /* localStorage kullanılamıyor */
      }
      return yeni;
    });
  }

  function sayfaDegistir(n: number) {
    setSayfa(n);
    setHat("");
  }

  const [sayfa, setSayfa] = useSenaryoSayfasi(senaryoId);
  // Senaryo değişince hat filtresi de sıfırlanır (hatlar senaryoya göre değişir).
  useEffect(() => setHat(""), [senaryoId]);

  const urunler = useUrunler(senaryoId, {
    sayfa,
    boyut: BOYUT,
    gecici: gecici || undefined,
  });
  // Fiyatsız malzeme sayısı Veri Kontrolü ile aynı kaynaktan: yalnız reçetede kullanılan fiyatsız malzemeler (tüm kartlar değil).
  const tutarlilik = useTutarlilik(senaryoId);
  const uyarilar = useUyarilar(senaryoId);

  const satirlar = useMemo(() => urunler.data?.kayitlar ?? [], [urunler.data]);
  const hatlar = useMemo(() => [...new Set(satirlar.map((s) => s.hat))].sort((a, b) => a.localeCompare(b, "tr")), [satirlar]);

  const gorunen = useMemo(() => {
    const q = tr(arama.trim());
    return satirlar.filter(
      (s) =>
        (!hat || s.hat === hat) &&
        (!enflasyon || s.enflasyon_durumu === enflasyon) &&
        (!yalnizHatali || !!s.hata) &&
        (!q || tr(s.kod).includes(q) || tr(s.ad).includes(q)),
    );
  }, [satirlar, arama, hat, enflasyon, yalnizHatali]);

  const enflasyonAltinda = urunler.data?.enflasyon_altinda_toplam ?? null;

  const uyariHaritasi = useMemo(() => {
    const h = new Map<string, string[]>();
    for (const u of uyarilar.data?.kayitlar ?? []) h.set(u.urun_kodu, [...(h.get(u.urun_kodu) ?? []), u.uyari]);
    return h;
  }, [uyarilar.data]);

  const uyariYukleniyor = uyarilar.isPending;
  /** "Durum" sütunu yalnız hesaplanamayan ürün varken: aksi halde boş sütun yer kaplamasın. */
  const hataVar = satirlar.some((s) => !!s.hata);
  const sutunlar = useMemo<SutunTanimi<DashboardSatiri>[]>(() => {
    const para = (id: keyof DashboardSatiri, baslik: string, birim: "TL" | "USD" | "EUR" = "TL", basamak = 2) =>
      ({
        accessorKey: id,
        header: baslik,
        cell: ({ getValue }: { getValue: () => unknown }) => (
          <ParaHucresi deger={getValue() as string | null} paraBirimi={birim} basamak={basamak} />
        ),
      }) as SutunTanimi<DashboardSatiri>;
    const { kirilim, firesiz, doviz, karsilastirma, uretim } = sutunSecimi;
    const grup = (acik: boolean, liste: SutunTanimi<DashboardSatiri>[]) => (acik ? liste : []);
    return [
      {
        accessorKey: "kod",
        header: "Kod",
        cell: ({ getValue }) => (
          <span className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{getValue() as string}</span>
        ),
      },
      {
        accessorKey: "ad",
        header: "Ürün",
        cell: ({ getValue }) => <span className="font-medium">{getValue() as string}</span>,
      },
      {
        accessorKey: "ambalaj_hacmi",
        header: "Ambalaj",
        cell: ({ row }) => (
          <span className="block text-right tabular-nums">{ambalajMetni(row.original.ambalaj_etiket, row.original.ambalaj_hacmi)}</span>
        ),
      },
      { accessorKey: "hat", header: "Hat" },
      ...grup(kirilim, [
        para("recete_maliyeti", "Reçete Maliyeti"),
        para("gug", "GÜG"),
        para("faaliyet", "Faaliyet"),
        para("finans", "Finans"),
        {
          accessorKey: "gider_yuzdesi",
          header: "Gider %",
          cell: ({ getValue }) => <YuzdeHucresi deger={getValue() as string | null} />,
        },
      ]),
      para("maliyet_tl", "Maliyet TL"),
      ...grup(firesiz, [para("maliyet_tl_firesiz", "Maliyet TL (firesiz)")]),
      ...grup(doviz, [para("maliyet_usd", "Maliyet USD", "USD", 3), para("maliyet_eur", "Maliyet EUR", "EUR", 3)]),
      {
        accessorKey: "satis_tl",
        header: "Satış TL",
        cell: ({ getValue }) => (
          <span className="font-semibold">
            <ParaHucresi deger={getValue() as string | null} />
          </span>
        ),
      },
      ...grup(karsilastirma, [
        para("gecen_yil_tl", "Geçen yıl (TL)"),
        {
          accessorKey: "enflasyon_fark_yuzde",
          header: "Enf. eşiği",
          cell: ({ row }) => <EnflasyonRozeti durum={row.original.enflasyon_durumu} farkYuzde={row.original.enflasyon_fark_yuzde} />,
        },
        {
          accessorKey: "hedef_adet_maliyet_tl",
          header: "Hedef adetle maliyet (TL)",
          cell: ({ row }) => <HedefAdetHucresi satir={row.original} />,
        },
      ]),
      ...grup(uretim, [
        {
          accessorKey: "uretim_adedi",
          header: "Üretim Adedi",
          cell: ({ getValue }) => {
            const v = getValue() as string | null;
            return v === null ? (
              <span className="block text-right text-muted-foreground">—</span>
            ) : (
              <span className="block text-right tabular-nums">{adetBicimle(v)}</span>
            );
          },
        },
      ]),
      {
        accessorKey: "uyari_sayisi",
        header: "Uyarı",
        cell: ({ row }) => (
          <UyariHucresi
            sayi={row.original.uyari_sayisi}
            uyarilar={uyariHaritasi.get(row.original.kod) ?? []}
            yukleniyor={uyariYukleniyor}
          />
        ),
      },
      ...grup(hataVar, [
        {
          id: "durum",
          header: "Durum",
          enableSorting: false,
          cell: ({ row }) =>
            row.original.hata ? (
              <Badge variant="destructive" className="h-auto whitespace-normal">
                {row.original.hata}
              </Badge>
            ) : null,
        },
      ]),
    ];
  }, [uyariHaritasi, uyariYukleniyor, sutunSecimi, hataVar]);

  if (senaryoId === null) {
    if (!senaryoYukleniyor && senaryolar.length === 0) {
      return (
        <section>
          <SayfaBasligi baslik="Genel Bakış" />
          <p className="mt-2 text-muted-foreground">
            Henüz senaryo yok —{" "}
            <button type="button" onClick={() => yeniCalismaAc("bos")} className="text-primary underline-offset-4 hover:underline">
              Yeni çalışma
            </button>{" "}
            ile boş bir çalışma açın ya da{" "}
            <Link to="/recete-aktar" className="text-primary underline-offset-4 hover:underline">
              Veri Aktar
            </Link>{" "}
            ile Excel&apos;i yükleyin.
          </p>
        </section>
      );
    }
    return (
      <section>
        <SayfaBasligi baslik="Genel Bakış" />
        <p className="mt-2 text-muted-foreground">Başlamak için yukarıdan bir senaryo seçin.</p>
      </section>
    );
  }

  const toplam = urunler.data?.toplam ?? null;
  const sayfaSayisi = Math.max(1, Math.ceil((toplam ?? 0) / BOYUT));
  const sayfali = toplam !== null && toplam > BOYUT;
  const hataSayisi = urunler.data ? satirlar.filter((s) => s.hata).length : null;

  // Faz 5c: senaryo var ama üye ürün yok (boş ya da yeni açılmış çalışma) — tablo yerine üç yol gösterilir.
  if (toplam === 0 && !gecici) {
    const kopyalanabilir = senaryolar.length > 1;
    const sorgu = `?senaryo=${senaryoId}`;
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Genel Bakış" altBaslik={senaryo ? `${senaryo.sezon_ad} · ${senaryo.ad}` : undefined} />
        <div role="region" aria-labelledby="bos-calisma-baslik" className="flex flex-col gap-4 rounded-xl border border-dashed bg-card p-6">
          <div>
            <h2 id="bos-calisma-baslik" className="text-base font-semibold">
              Bu çalışmada henüz ürün yok
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Ürünler bu çalışmaya reçeteleriyle dahil olur. Geçen sezonun verisini kopyalayıp yalnız değişenleri güncelleyebilir, tek tek
              yeni ürün açabilir ya da Excel çalışma kitabını yükleyebilirsiniz.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {kopyalanabilir && (
              <Button type="button" onClick={() => yeniCalismaAc("kopya")}>
                <Copy aria-hidden />
                Geçen sezondan kopyala
              </Button>
            )}
            <Link
              to={`/veri-girisi${sorgu}`}
              className={cn(
                buttonVariants({
                  variant: kopyalanabilir ? "outline" : "default",
                }),
              )}
            >
              <PackagePlus aria-hidden />
              Yeni ürün
            </Link>
            <Link to={`/recete-aktar${sorgu}`} className={cn(buttonVariants({ variant: "outline" }))}>
              <Upload aria-hidden />
              Excel yükle
            </Link>
          </div>
          {!kopyalanabilir && (
            <p className="text-xs text-muted-foreground">
              Kopyalanacak başka bir çalışma olmadığı için &quot;Geçen sezondan kopyala&quot; görünmüyor.
            </p>
          )}
        </div>
      </section>
    );
  }

  const suzgecVar = !!(arama.trim() || hat || enflasyon || yalnizHatali);
  function suzgecleriTemizle() {
    setArama("");
    setHat("");
    setEnflasyon("");
    setYalnizHatali(false);
  }

  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        bant
        baslik="Genel Bakış"
        altBaslik={senaryo ? `${senaryo.sezon_ad} · ${senaryo.ad} — ürünlerin maliyet ve satış özeti` : "Ürünlerin maliyet ve satış özeti"}
        eylemler={
          <a href={`/api/v1/disa-aktar/urunler.xlsx?senaryo=${senaryoId}`} download className={cn(buttonVariants({ variant: "outline" }))}>
            <Download aria-hidden />
            Excel&apos;e aktar
          </a>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <UstKartlar
          urunSayisi={toplam}
          hataSayisi={hataSayisi}
          uyariliUrun={uyarilar.data ? uyariHaritasi.size : null}
          enflasyonAltinda={enflasyonAltinda}
          fiyatsizMalzeme={tutarlilik.data ? (tutarlilik.data.kontroller.find((k) => k.kod === "fiyatsiz")?.sayi ?? 0) : null}
          senaryoId={senaryoId}
          onEnflasyonSuz={() => setEnflasyon("altinda")}
          onHataSuz={() => setYalnizHatali(true)}
        />
        <OneCikanlar satirlar={satirlar} uyarilar={uyariHaritasi} />
      </div>
      <VeriKontroluSeridi senaryoId={senaryoId} />
      <GerceklesenSeridi />
      <GenelGrafikler satirlar={satirlar} />

      <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="search"
            aria-label="Ürün ara"
            placeholder="Ürün adı ya da kodu ara"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
            className="h-9 w-full sm:w-72"
          />
          <select aria-label="Hat" value={hat} onChange={(e) => setHat(e.target.value)} className={SECIM}>
            <option value="">Tüm hatlar</option>
            {hatlar.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
          <select aria-label="Enflasyon eşiği" value={enflasyon} onChange={(e) => setEnflasyon(e.target.value)} className={SECIM}>
            <option value="">Enflasyon: tümü</option>
            <option value="altinda">Enflasyonun altında</option>
            <option value="ustunde">Enflasyonun üstünde</option>
          </select>
          <label className="flex h-9 items-center gap-2 rounded-lg px-1 text-sm">
            <input
              type="checkbox"
              checked={gecici}
              onChange={(e) => {
                setGecici(e.target.checked);
                setSayfa(1);
                setHat("");
              }}
            />
            Geçici kodlu
          </label>
          {yalnizHatali && (
            <Badge variant="destructive" className="h-7">
              Yalnız hesaplanamayanlar
            </Badge>
          )}
          {suzgecVar && (
            <Button type="button" variant="ghost" size="sm" onClick={suzgecleriTemizle}>
              <X aria-hidden />
              Süzgeçleri temizle
            </Button>
          )}
          <div className="ml-auto flex items-center gap-3">
            <span className="text-sm text-muted-foreground tabular-nums" aria-live="polite">
              {urunler.data ? `${gorunen.length} / ${satirlar.length} ürün` : ""}
            </span>
            <SutunMenusu secim={sutunSecimi} degistir={sutunDegistir} />
          </div>
        </div>
        {sayfali && (
          <p className="text-xs text-muted-foreground">
            Bu sayfada {satirlar.length} / {toplam} ürün görüntüleniyor; arama ve süzgeçler yalnız bu sayfayı kapsar.
          </p>
        )}

        <div className="overflow-x-auto">
          <VeriTablosu
            veri={gorunen}
            sutunlar={sutunlar}
            yukleniyor={urunler.isPending}
            hata={(urunler.error as ApiHatasi | null) ?? null}
            bosMetin="Ürün bulunamadı"
            bosAciklama={suzgecVar ? "Süzgeçleri temizleyip tekrar deneyin" : "Henüz kayıt yok — Veri Aktar ile yükleyin"}
            satirTikla={(s) => gezin(`/urunler/${encodeURIComponent(s.kod)}?senaryo=${senaryoId}`)}
            toplamSatiri={(rows) => ({
              kod: "Toplam (görünen)",
              uretim_adedi: (
                <span className="block text-right">
                  {adetBicimle(topla(rows.filter((r) => !r.hata && r.uretim_adedi !== null).map((r) => r.uretim_adedi as string)))}
                </span>
              ),
              uyari_sayisi: <span className="block text-center">{rows.reduce((t, r) => t + (r.uyari_sayisi ?? 0), 0)}</span>,
            })}
          />
        </div>

        {sayfali && (
          <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
            <Button variant="outline" size="sm" disabled={sayfa <= 1} onClick={() => sayfaDegistir(sayfa - 1)}>
              Önceki
            </Button>
            <span aria-live="polite">
              Sayfa {sayfa} / {sayfaSayisi}
            </span>
            <Button variant="outline" size="sm" disabled={sayfa >= sayfaSayisi} onClick={() => sayfaDegistir(sayfa + 1)}>
              Sonraki
            </Button>
          </nav>
        )}
      </div>

      <details className="group rounded-xl border bg-card shadow-xs">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm font-semibold [&::-webkit-details-marker]:hidden">
          Ambalaj ve kapak özeti
          <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
        </summary>
        <div className="border-t">
          <AmbalajOzeti senaryoId={senaryoId} />
        </div>
      </details>
    </section>
  );
}
