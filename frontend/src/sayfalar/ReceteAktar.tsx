import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ElleReceteFormu } from "./aktar/ElleReceteFormu";
import { ReceteDosyaAktar } from "./aktar/ReceteDosyaAktar";
import { GiderDagitimAktar } from "./aktar/GiderDagitimAktar";
import { SatinAlmaAktar } from "./aktar/SatinAlmaAktar";
import { SatisGecmisiYonlendirme } from "./aktar/SatisGecmisiYonlendirme";
import { StokDevriAktar } from "./aktar/StokDevriAktar";
import { TamKitapFormu } from "./aktar/TamKitapFormu";
import { UretimAdetleriAktar } from "./aktar/UretimAdetleriAktar";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { DuzenlemeKilidi, YazmaAlaniSaglayici } from "@/bilesenler/DuzenlemeKilidi";
import { useOturum } from "@/bilesenler/GirisKapisi";

const SEKMELER = [
  { kimlik: "tam", etiket: "Tüm çalışma kitabı" },
  { kimlik: "fiyat", etiket: "Satın alma fiyat listesi" },
  { kimlik: "uretim", etiket: "Üretim adetleri" },
  { kimlik: "gider", etiket: "Gider dağıtım" },
  { kimlik: "satis", etiket: "Satış geçmişi" },
  { kimlik: "recete", etiket: "Ürün reçetesi" },
  { kimlik: "stok", etiket: "Stokta kalan" },
] as const;

type Sekme = (typeof SEKMELER)[number]["kimlik"];

const PANELLER: Record<Sekme, ReactNode> = {
  tam: <TamKitapFormu />,
  fiyat: <SatinAlmaAktar />,
  uretim: <UretimAdetleriAktar />,
  gider: <GiderDagitimAktar />,
  satis: <SatisGecmisiYonlendirme />,
  stok: <StokDevriAktar />,
  recete: (
    <div className="flex flex-col gap-8">
      <ReceteDosyaAktar />
      <section aria-labelledby="elle-recete-baslik" className="flex flex-col gap-3 border-t pt-6">
        <h2 id="elle-recete-baslik" className="text-base font-semibold">
          Elle reçete girişi
        </h2>
        <ElleReceteFormu />
      </section>
    </div>
  ),
};

/** Satın alma rolü yalnız kendi işi olan fiyat listesini yükler; diğer roller tüm sekmeleri görür. */
const SATIN_ALMA_SEKMELERI = SEKMELER.filter((s) => s.kimlik === "fiyat");

export default function ReceteAktar() {
  const { girisZorunlu, rol } = useOturum();
  const sekmeler: readonly (typeof SEKMELER)[number][] = girisZorunlu && rol === "satin_alma" ? SATIN_ALMA_SEKMELERI : SEKMELER;
  const [secili, setAktif] = useState<Sekme>(sekmeler[0].kimlik);
  // Rol sonradan değişirse (oturum yenilenir) görünmeyen bir sekme açık kalmasın.
  const aktif: Sekme = sekmeler.some((s) => s.kimlik === secili) ? secili : sekmeler[0].kimlik;
  const dugmeler = useRef<Record<string, HTMLButtonElement | null>>({});

  function tusa(e: KeyboardEvent<HTMLButtonElement>, i: number) {
    let hedef = -1;
    if (e.key === "ArrowRight") hedef = (i + 1) % sekmeler.length;
    else if (e.key === "ArrowLeft") hedef = (i - 1 + sekmeler.length) % sekmeler.length;
    else if (e.key === "Home") hedef = 0;
    else if (e.key === "End") hedef = sekmeler.length - 1;
    if (hedef < 0) return;
    e.preventDefault();
    const k = sekmeler[hedef].kimlik;
    setAktif(k);
    dugmeler.current[k]?.focus();
  }

  // Satın alma fiyat listesi sekmesi "malzeme" yazma alanıdır (satın alma rolü yalnız burada kilidi açar; bkz. rolYetkisi.ts).
  return (
    <YazmaAlaniSaglayici alan={aktif === "fiyat" ? "malzeme" : "genel"}>
      <div className="flex flex-col gap-4">
        <SayfaBasligi baslik="Veri Aktar" altBaslik="Excel'den veri yükleme ve elle reçete girişi" />
        <KilitSeridi />
        <DuzenlemeKilidi />

        <div role="tablist" aria-label="Aktarım türü" className="flex gap-1 overflow-x-auto border-b">
          {sekmeler.map((s, i) => (
            <button
              key={s.kimlik}
              ref={(el) => {
                dugmeler.current[s.kimlik] = el;
              }}
              type="button"
              role="tab"
              id={`sekme-${s.kimlik}`}
              aria-selected={aktif === s.kimlik}
              aria-controls={`panel-${s.kimlik}`}
              tabIndex={aktif === s.kimlik ? 0 : -1}
              onClick={() => setAktif(s.kimlik)}
              onKeyDown={(e) => tusa(e, i)}
              className={cn(
                "-mb-px shrink-0 rounded-t-md border-b-2 px-3 py-2 text-sm whitespace-nowrap focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none",
                aktif === s.kimlik ? "border-primary font-medium" : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {s.etiket}
            </button>
          ))}
        </div>

        <div role="tabpanel" id={`panel-${aktif}`} aria-labelledby={`sekme-${aktif}`}>
          {PANELLER[aktif]}
        </div>
      </div>
    </YazmaAlaniSaglayici>
  );
}
