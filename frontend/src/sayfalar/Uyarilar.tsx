import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useUyarilar } from "@/api/sorgular/uyarilar";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import type { Uyari } from "@/api/tipler";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KONTROL_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";

export type UyariKategorisi = "fiyat" | "kur" | "hat" | "sinif" | "yurtdisi" | "vardiya" | "diger";

/** Sınıflandırma sırası (eşitlikte öncelik) ve başlıklar. */
const KATEGORILER: { kod: UyariKategorisi; baslik: string; desen: RegExp | null }[] = [
  { kod: "fiyat", baslik: "Fiyat listesinde yok", desen: /fiyat listesinde yok/u },
  { kod: "kur", baslik: "Kur", desen: /(^|[^\p{L}])kur(u|lar|lari|ları)?(?![\p{L}])/u },
  { kod: "hat", baslik: "Hat", desen: /(^|[^\p{L}])hat(tı|ti|ta|tında|lar)?(?![\p{L}])/u },
  { kod: "sinif", baslik: "Sınıf", desen: /sınıf/u },
  { kod: "yurtdisi", baslik: "Yurtdışı", desen: /yurt ?dışı/u },
  { kod: "vardiya", baslik: "Vardiya", desen: /vardiya/u },
  { kod: "diger", baslik: "Diğer", desen: null },
];

/** Gösterim sırası: müdahale gerektiren az sayıdaki uyarılar önce, kalabalık "fiyat listesinde yok" en sonda. */
const GOSTERIM_SIRASI: UyariKategorisi[] = ["kur", "hat", "sinif", "yurtdisi", "vardiya", "diger", "fiyat"];

const FIYAT_YOK = /\s*:?\s*fiyat listesinde yok.*$/u;

export interface FiyatsizMalzeme {
  /** Uyarı metnindeki malzeme kısmı: "02.004.001.002.00001 (Biberiye Turşu 370 ml Berrak)". */
  malzeme: string;
  urunler: string[];
}

/** "fiyat listesinde yok" uyarılarını malzemeye göre toplar (aynı malzeme birçok üründe geçer); çok geçen önce. */
export function fiyatsizMalzemeler(uyarilar: Uyari[]): FiyatsizMalzeme[] {
  const h = new Map<string, Set<string>>();
  for (const u of uyarilar) {
    const malzeme = u.uyari.replace(FIYAT_YOK, "").trim() || u.uyari;
    h.set(malzeme, (h.get(malzeme) ?? new Set()).add(u.urun_kodu));
  }
  return [...h.entries()]
    .map(([malzeme, urunler]) => ({ malzeme, urunler: [...urunler] }))
    .sort((a, b) => b.urunler.length - a.urunler.length || a.malzeme.localeCompare(b.malzeme, "tr"));
}

/** Uyarı metnini türüne ayırır: metinde en erken geçen anahtar kazanır (ön ek öncelikli), eşitlikte liste sırası. */
export function uyariKategorisi(metin: string): UyariKategorisi {
  // "KOD (Malzeme adı): mesaj" biçiminde yalnız mesaja bakılır: "Kuru Maydanoz" gibi adlar 'kur' sayılmasın.
  const ayrac = metin.indexOf("): ");
  const m = (ayrac >= 0 ? metin.slice(ayrac + 3) : metin).toLocaleLowerCase("tr");
  let en: { kod: UyariKategorisi; konum: number } | null = null;
  for (const k of KATEGORILER) {
    if (!k.desen) continue;
    const e = k.desen.exec(m);
    if (!e) continue;
    // Eşleşme başındaki ayırıcı karakter konuma dahil edilmez.
    const konum = e.index + (e[1] ? e[1].length : 0);
    if (!en || konum < en.konum) en = { kod: k.kod, konum };
  }
  return en?.kod ?? "diger";
}

/** Fiyatsız malzemeler: malzeme başına tek satır, geçtiği ürünler açılır listede (muhasebeye sorulacak liste). */
function FiyatsizBolumu({ uyarilar, url }: { uyarilar: Uyari[]; url: (kod: string) => string }) {
  const malzemeler = useMemo(() => fiyatsizMalzemeler(uyarilar), [uyarilar]);
  return (
    <section id="uyari-fiyat" aria-labelledby="uyari-baslik-fiyat" role="region" className="rounded-lg border">
      <div className="flex flex-col gap-1 border-b px-3 py-2">
        <h2 id="uyari-baslik-fiyat" className="flex items-center gap-2 font-medium">
          Fiyat listesinde yok
          <Badge variant="outline" data-sayi>
            {malzemeler.length}
          </Badge>
        </h2>
        <p className="text-xs text-muted-foreground">
          Bu malzemeler S.ALMA BF fiyat listesinde yok, hesapta 0 TL alınıyor. Çoğu kendi ürettiğimiz turşu/salamura olabilir; hangisinin
          bilerek 0, hangisinin eksik veri olduğunu muhasebe ayırmalı. Altında alt satırları olan ara ürünler (maliyeti alt satırlardan
          gelir) bu listeye girmez.
        </p>
      </div>
      <ul className="divide-y">
        {malzemeler.map((m) => (
          <li key={m.malzeme} className="px-3 py-2 text-sm">
            <details>
              <summary className="flex cursor-pointer flex-wrap items-baseline justify-between gap-x-3 [&::-webkit-details-marker]:hidden">
                <span>{m.malzeme}</span>
                <span className="text-xs text-muted-foreground tabular-nums">{m.urunler.length} üründe</span>
              </summary>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                {m.urunler.map((kod) => (
                  <Link key={kod} to={url(kod)} className="text-primary underline-offset-4 hover:underline">
                    {kod}
                  </Link>
                ))}
              </div>
            </details>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function Uyarilar() {
  const { senaryoId } = useSenaryo();
  const sorgu = useUyarilar(senaryoId);
  const hata = (sorgu.error as ApiHatasi | null) ?? null;
  const kayitlar = useMemo<Uyari[]>(() => sorgu.data?.kayitlar ?? [], [sorgu.data]);

  const gruplar = useMemo(() => {
    const h = new Map<UyariKategorisi, Uyari[]>();
    for (const u of kayitlar) {
      const k = uyariKategorisi(u.uyari);
      h.set(k, [...(h.get(k) ?? []), u]);
    }
    return GOSTERIM_SIRASI.filter((kod) => h.has(kod)).map((kod) => {
      const k = KATEGORILER.find((x) => x.kod === kod)!;
      return { ...k, uyarilar: h.get(kod) ?? [] };
    });
  }, [kayitlar]);

  const urunSayisi = useMemo(() => new Set(kayitlar.map((u) => u.urun_kodu)).size, [kayitlar]);
  const url = (kod: string) => `/urunler/${encodeURIComponent(kod)}?senaryo=${senaryoId}`;

  return (
    <div className="flex flex-col gap-4 p-4">
      <SayfaSekmeleri etiket="Kontrol türü" sekmeler={KONTROL_SEKMELERI} />
      <SayfaBasligi baslik="Uyarılar" altBaslik="Seçili senaryodaki tüm ürünlerin hesap uyarıları, türüne göre." />

      {hata ? (
        <div role="alert" className="rounded-md border border-destructive/40 p-3 text-destructive">
          {hataMetni(hata)}
        </div>
      ) : sorgu.isPending ? (
        <div role="status" className="text-muted-foreground">
          Yükleniyor…
        </div>
      ) : kayitlar.length === 0 ? (
        <div className="rounded-md border p-6 text-center text-muted-foreground">Bu senaryoda uyarı yok</div>
      ) : (
        <>
          <p className="text-sm font-medium">{`${kayitlar.length} uyarı, ${urunSayisi} ürün`}</p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {gruplar.map((g) => (
              <a
                key={g.kod}
                href={`#uyari-${g.kod}`}
                className="rounded-xl border bg-card p-3 shadow-xs hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                <div className="text-sm text-muted-foreground">{g.baslik}</div>
                <div className="text-2xl font-semibold tabular-nums">
                  {g.kod === "fiyat" ? fiyatsizMalzemeler(g.uyarilar).length : g.uyarilar.length}
                </div>
                {g.kod === "fiyat" && <div className="text-xs text-muted-foreground">malzeme · {g.uyarilar.length} satır</div>}
              </a>
            ))}
          </div>
          {gruplar.map((g) =>
            g.kod === "fiyat" ? (
              <FiyatsizBolumu key={g.kod} uyarilar={g.uyarilar} url={url} />
            ) : (
              <section
                key={g.kod}
                id={`uyari-${g.kod}`}
                aria-labelledby={`uyari-baslik-${g.kod}`}
                role="region"
                className="rounded-lg border"
              >
                <h2 id={`uyari-baslik-${g.kod}`} className="flex items-center gap-2 border-b px-3 py-2 font-medium">
                  {g.baslik}
                  <Badge variant="destructive" data-sayi>
                    {g.uyarilar.length}
                  </Badge>
                </h2>
                <ul className="divide-y">
                  {g.uyarilar.map((u, i) => (
                    <li key={`${u.urun_kodu}-${i}`} className="flex flex-wrap items-baseline gap-x-3 px-3 py-2 text-sm">
                      <Link to={url(u.urun_kodu)} className="font-medium text-primary underline-offset-4 hover:underline">
                        {u.urun_kodu}
                      </Link>
                      <span>{u.uyari}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ),
          )}
        </>
      )}
    </div>
  );
}
