import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useGorunurGruplar, type MenuGrubu } from "@/bilesenler/Kabuk";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";

/**
 * Grupların sütunlara dağılımı: boyları dengelensin diye elle (Çalışma 4, Kayıtlar 5, kısa gruplar üçüncü sütunda alt alta).
 * Burada adı geçmeyen yeni bir grup son sütuna eklenir.
 */
const SUTUNLAR = [["Çalışma"], ["Kayıtlar"], ["Veri girişi", "Kontrol", "Yönetim"]];

/**
 * Açılış sayfası: ürün tablosu yerine menüdeki bölümler (rolün gördükleri). Her menü grubu bir kutu, bölümler kutunun içinde
 * alt alta; kutular üç dengeli sütunda. Bağlantılar seçili çalışmayı (?senaryo=) taşır.
 */
export default function AnaSayfa() {
  const { senaryoId, senaryo } = useSenaryo();
  const gruplar = useGorunurGruplar()
    .map((g) => ({ ...g, ogeler: g.ogeler.filter((o) => o.yol !== "/") }))
    .filter((g) => g.ogeler.length > 0);
  const yol = (y: string) => (senaryoId === null ? y : `${y}?senaryo=${senaryoId}`);
  const bilinen = new Set(SUTUNLAR.flat());
  const sutunlar: MenuGrubu[][] = SUTUNLAR.map((adlar, i) => [
    ...gruplar.filter((g) => adlar.includes(g.grup)),
    ...(i === SUTUNLAR.length - 1 ? gruplar.filter((g) => !bilinen.has(g.grup)) : []),
  ]).filter((s) => s.length > 0);

  const kutu = (g: MenuGrubu) => (
    <section
      key={g.grup}
      aria-labelledby={`ana-${g.grup}`}
      // Geniş ekranda kutu, sütun yüksekliğini bölüm sayısı oranında paylaşır (başlık payı +0,6).
      style={{ flexGrow: g.ogeler.length + 0.6 }}
      className="flex basis-0 flex-col overflow-hidden rounded-2xl border bg-card shadow-sm max-xl:basis-auto"
    >
      <h2 id={`ana-${g.grup}`} className="border-b px-8 py-5 text-base font-semibold tracking-wider text-muted-foreground uppercase">
        {g.grup}
      </h2>
      <ul className="flex flex-1 flex-col divide-y">
        {g.ogeler.map((o) => {
          const Simge = o.simge;
          return (
            <li key={o.yol} className="flex flex-1">
              <Link
                to={yol(o.yol)}
                className="group flex flex-1 items-center gap-6 px-8 py-6 transition-colors hover:bg-accent/40 focus-visible:bg-accent/40 focus-visible:outline-none"
              >
                <span
                  className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-accent text-accent-foreground"
                  aria-hidden
                >
                  <Simge className="size-8" />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="text-2xl font-semibold">{o.etiket}</span>
                  {o.aciklama && <span className="text-lg text-muted-foreground">{o.aciklama}</span>}
                </span>
                <ChevronRight
                  className="size-7 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
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
    // Geniş ekranda sayfa ekran yüksekliğini doldurur (üst çubuk ve kenar boşlukları düşülür); dar ekranda doğal yükseklik.
    <section className="mx-auto flex w-full max-w-[1900px] flex-col gap-8 xl:h-[calc(100dvh-9rem)] xl:min-h-[640px] xl:px-12">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-4xl font-semibold tracking-tight lg:text-5xl">Hoş geldiniz</h1>
        <p className="text-lg text-muted-foreground lg:text-xl">
          {senaryo ? `Çalışma: ${senaryo.sezon_ad} · ${senaryo.ad}. Nereden başlamak istersiniz?` : "Nereden başlamak istersiniz?"}
        </p>
      </div>
      <div className="grid items-start gap-6 md:grid-cols-2 xl:min-h-0 xl:flex-1 xl:grid-cols-3 xl:items-stretch">
        {sutunlar.map((s, i) => (
          <div key={i} className="flex flex-col gap-6 xl:min-h-0">
            {s.map(kutu)}
          </div>
        ))}
      </div>
    </section>
  );
}
