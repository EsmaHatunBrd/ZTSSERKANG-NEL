import { useState } from "react";
import { ChevronRight, Calculator, Factory, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { ALAN_ADI, ALAN_ANAHTARI, useGorunurGruplar, type Alan, type MenuGrubu } from "@/bilesenler/Kabuk";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { cn } from "@/lib/utils";
import { VeriKontroluSeridi } from "@/sayfalar/dashboard/VeriKontroluSeridi";
import { SiradakiAdim } from "@/sayfalar/smm/SiradakiAdim";

/**
 * Fiyat çalışması gruplarının sütunlara dağılımı: boyları dengelensin diye elle. Burada adı geçmeyen yeni bir grup son sütuna eklenir.
 */
const SUTUNLAR = [["Çalışma"], ["Kayıtlar"], ["Veri girişi", "Kontrol", "Yönetim"]];

/** Bölüm başına simge kutusu rengi (yeni bir bölüm yeşil kalır). */
const GRUP_RENGI: Record<string, string> = {
  Çalışma: "bg-kart-yesil text-green-800 dark:text-green-200",
  Kayıtlar: "bg-kart-mavi text-sky-800 dark:text-sky-200",
  "Veri girişi": "bg-kart-turuncu text-orange-800 dark:text-orange-200",
  Kontrol: "bg-kart-sari text-amber-800 dark:text-amber-200",
  Yönetim: "bg-muted text-foreground",
};

const ISLER: { alan: Alan; simge: LucideIcon; aciklama: string }[] = [
  { alan: "fiyat", simge: Calculator, aciklama: "Bütçe maliyeti, satış ve liste fiyatı, teklifler, analizler" },
  { alan: "smm", simge: Factory, aciklama: "Aylık SMM: dönem başı, alım, sayım, sarf ve ortalama maliyet" },
];

function kayitliAlan(): Alan {
  try {
    return localStorage.getItem(ALAN_ANAHTARI) === "smm" ? "smm" : "fiyat";
  } catch {
    return "fiyat";
  }
}

/**
 * Açılış sayfası: önce iş seçilir (Fiyat Çalışması / Maliyet Muhasebesi), altında o işin bölümleri kart olarak (rolün gördükleri).
 * Son kullanılan iş hatırlanır. Fiyat çalışması bağlantıları seçili çalışmayı (?senaryo=) taşır.
 */
export default function AnaSayfa() {
  const { senaryoId, senaryo } = useSenaryo();
  const [alan, setAlan] = useState<Alan>(kayitliAlan);
  const gruplar = useGorunurGruplar(alan)
    .map((g) => ({ ...g, ogeler: g.ogeler.filter((o) => o.yol !== "/") }))
    .filter((g) => g.ogeler.length > 0);
  const yol = (y: string) => (senaryoId === null || alan === "smm" ? y : `${y}?senaryo=${senaryoId}`);
  const bilinen = new Set(SUTUNLAR.flat());
  const sutunlar: MenuGrubu[][] =
    alan === "smm"
      ? [gruplar]
      : SUTUNLAR.map((adlar, i) => [
          ...gruplar.filter((g) => adlar.includes(g.grup)),
          ...(i === SUTUNLAR.length - 1 ? gruplar.filter((g) => !bilinen.has(g.grup)) : []),
        ]).filter((s) => s.length > 0);

  function sec(a: Alan) {
    setAlan(a);
    try {
      localStorage.setItem(ALAN_ANAHTARI, a);
    } catch {
      /* depolama kapalı */
    }
  }

  const kutu = (g: MenuGrubu) => (
    <section
      key={g.grup}
      aria-labelledby={`ana-${g.grup.replace(/\s+/g, "-")}`}
      className="flex flex-col overflow-hidden rounded-2xl border bg-card shadow-xs"
    >
      <h2
        id={`ana-${g.grup.replace(/\s+/g, "-")}`}
        className="px-6 pt-5 pb-2 text-sm font-semibold tracking-wider text-muted-foreground uppercase"
      >
        {g.grup}
      </h2>
      <ul className="flex flex-col gap-1 p-2">
        {g.ogeler.map((o) => {
          const Simge = o.simge;
          return (
            <li key={o.yol}>
              <Link
                to={yol(o.yol)}
                className="group flex items-center gap-4 rounded-xl px-4 py-3.5 transition-colors hover:bg-accent/50 focus-visible:bg-accent/50 focus-visible:outline-none"
              >
                <span
                  className={cn(
                    "flex size-12 shrink-0 items-center justify-center rounded-xl transition-transform group-hover:scale-105",
                    GRUP_RENGI[g.grup] ?? "bg-kart-yesil text-primary",
                  )}
                  aria-hidden
                >
                  <Simge className="size-6" />
                </span>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="text-lg font-semibold">{o.etiket}</span>
                  {o.aciklama && <span className="text-sm text-muted-foreground">{o.aciklama}</span>}
                </span>
                <ChevronRight
                  className="size-5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );

  return (
    <section className="mx-auto flex w-full max-w-[2000px] flex-col gap-8 xl:px-10 2xl:px-16">
      <div className="flex flex-col gap-1 rounded-xl border bg-card px-8 py-6 shadow-xs">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Hoş geldiniz</h1>
        <p className="text-base text-muted-foreground">
          {alan === "fiyat" && senaryo
            ? `Çalışma: ${senaryo.sezon_ad} · ${senaryo.ad}. Nereden başlamak istersiniz?`
            : "Hangi işle devam etmek istersiniz?"}
        </p>
      </div>

      <div role="group" aria-label="İş seçimi" className="grid gap-6 md:grid-cols-2 xl:gap-8">
        {ISLER.map((is) => {
          const Simge = is.simge;
          const secili = alan === is.alan;
          return (
            <button
              key={is.alan}
              type="button"
              aria-pressed={secili}
              onClick={() => sec(is.alan)}
              className={cn(
                "flex items-center gap-4 rounded-2xl border-2 bg-card p-5 text-left shadow-xs transition-colors",
                secili ? "border-primary bg-card" : "border-transparent hover:border-border hover:bg-accent/40",
              )}
            >
              <span
                className={cn(
                  "flex size-14 shrink-0 items-center justify-center rounded-2xl",
                  secili ? "bg-accent text-primary" : "bg-muted text-muted-foreground",
                )}
                aria-hidden
              >
                <Simge className="size-7" />
              </span>
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="text-xl font-semibold">{ALAN_ADI[is.alan]}</span>
                <span className="text-sm text-muted-foreground">{is.aciklama}</span>
              </span>
            </button>
          );
        })}
      </div>

      {/* Veri Kontrolü'nde ilgi bekleyen konu varsa (ör. hedef marjın altındaki ürün, eksik fiyat) tek satır; yoksa hiçbir şey çizilmez. */}
      {alan === "fiyat" && (
        <div className="empty:hidden">
          <VeriKontroluSeridi senaryoId={senaryoId} />
        </div>
      )}
      {alan === "smm" && <SiradakiAdim />}

      <div className={cn("grid items-start gap-6 xl:gap-8", alan === "fiyat" ? "md:grid-cols-2 xl:grid-cols-3" : "md:grid-cols-2")}>
        {sutunlar.map((s, i) => (
          <div key={i} className="flex flex-col gap-6 xl:gap-8">
            {s.map(kutu)}
          </div>
        ))}
      </div>
    </section>
  );
}
