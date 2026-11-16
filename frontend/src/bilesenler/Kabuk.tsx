import { Suspense, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Boxes,
  Calculator,
  CalendarRange,
  ChartColumn,
  ChartPie,
  ClipboardList,
  Factory,
  FileSpreadsheet,
  FileText,
  GitCompareArrows,
  Handshake,
  History,
  House,
  ListChecks,
  Layers,
  Menu as MenuSimgesi,
  PackageSearch,
  PanelLeftClose,
  PanelLeftOpen,
  ReceiptText,
  Scale,
  ShieldCheck,
  Sigma,
  SlidersHorizontal,
  Split,
  SquarePen,
  Tags,
  Timer,
  TrendingUp,
  UserCog,
  Warehouse,
  X,
  CircleHelp,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { DuzenlemeKilidiSaglayici } from "./DuzenlemeKilidi";
import { useOturum } from "./GirisKapisi";
import { HesapDugmesi } from "./HesapDugmesi";
import { HizliArama } from "./HizliAramaKutusu";
import { Logo } from "./Logo";
import { SenaryoSaglayici, SenaryoSecici, useSenaryo } from "./SenaryoSecici";
import { TemaAnahtari } from "./TemaAnahtari";

export interface MenuOgesi {
  yol: string;
  etiket: string;
  son: boolean;
  simge: LucideIcon;
  /** Bu öğeyi de seçili gösteren yollar (sekmeyle bağlı kardeş sayfalar). */
  ekYollar?: string[];
  /** Ana Sayfa kartındaki kısa açıklama. */
  aciklama?: string;
}

export interface MenuGrubu {
  grup: string;
  ogeler: MenuOgesi[];
  /** Yalnız veri yazabilen rollere (izleyici hariç) gösterilir. */
  yazanlara?: boolean;
  /** Yalnız Genel Direktör'e gösterilir (giriş zorunluyken). */
  yoneticiye?: boolean;
}

export const MENU_GRUPLARI: MenuGrubu[] = [
  {
    grup: "Çalışma",
    ogeler: [
      { yol: "/", etiket: "Ana Sayfa", son: true, simge: House },
      { yol: "/genel-bakis", etiket: "Genel Bakış", son: false, simge: ChartPie, aciklama: "Tüm ürünlerin maliyet ve satış özeti" },
      {
        yol: "/yonetim-ozeti",
        etiket: "Yönetim Özeti",
        son: false,
        simge: FileText,
        aciklama: "Marj, risk, teklif ve veri durumu tek sayfada",
      },
      { yol: "/urunler", etiket: "Ürün Maliyeti", son: false, simge: PackageSearch, aciklama: "Tek ürünün reçetesi, giderleri ve fiyatı" },
      { yol: "/teklifler", etiket: "Teklifler", son: false, simge: Handshake, aciklama: "Teklif turları ve Teklif Kapak" },
      {
        yol: "/ya-olursa",
        etiket: "Analiz",
        son: false,
        simge: TrendingUp,
        ekYollar: ["/zam-etkisi", "/kur-riski", "/karlilik", "/hedef-fiyat", "/liste-calismasi", "/fiyat-egilimi", "/onemli-malzemeler"],
        aciklama: "Ya olursa, zam etkisi, liste fiyatı çalışması",
      },
      // Bütçe vs Gerçekleşen, ürün aileleri ve geçmiş kayıtlar tek öğe; sayfalar arası geçiş sekmelerle (SayfaSekmeleri).
      {
        yol: "/butce-gerceklesen",
        etiket: "Kıyasla",
        son: false,
        simge: GitCompareArrows,
        ekYollar: ["/karsilastirma", "/arsiv"],
        aciklama: "Bütçe vs gerçekleşen, ürün aileleri, geçmiş kayıtlar",
      },
    ],
  },
  {
    // Veriyi nereden girerim: tek tek (Veri Girişi) ya da Excel'den toplu (Veri Aktar).
    grup: "Veri girişi",
    yazanlara: true,
    ogeler: [
      {
        yol: "/veri-girisi",
        etiket: "Veri Girişi",
        son: false,
        simge: SquarePen,
        aciklama: "Fiyat, parametre, gider, üretim bilgisini tek tek gir",
      },
      { yol: "/recete-aktar", etiket: "Veri Aktar", son: false, simge: FileSpreadsheet, aciklama: "Excel'den toplu yükle" },
    ],
  },
  {
    // Girilen veriyi nerede görürüm: tam listeler, geçmiş ve düzenleme.
    grup: "Kayıtlar",
    ogeler: [
      { yol: "/fiyatlar", etiket: "Malzeme Fiyatları", son: false, simge: Tags, aciklama: "Malzeme kartları, fiyatlar ve revizeler" },
      {
        yol: "/parametreler",
        etiket: "Parametreler",
        son: false,
        simge: SlidersHorizontal,
        aciklama: "Enflasyon, kurlar, faiz, kâr oranları",
      },
      { yol: "/gider", etiket: "Gider Dağıtım", son: false, simge: Split, aciklama: "Gider havuzları ve dağıtım payları" },
      { yol: "/uretim-adetleri", etiket: "Üretim Adetleri", son: false, simge: Boxes, aciklama: "Vardiya kapasitesi ve hedef adetler" },
      { yol: "/satis-gecmisi", etiket: "Satış Geçmişi", son: false, simge: ReceiptText, aciklama: "Geçen yıl satış fiyatları" },
    ],
  },
  {
    grup: "Kontrol",
    ogeler: [
      {
        yol: "/veri-kontrolu",
        etiket: "Veri Kontrolü",
        son: false,
        simge: ShieldCheck,
        ekYollar: ["/uyarilar"],
        aciklama: "Eksik ya da çelişkili veriler tek listede",
      },
      { yol: "/gunluk", etiket: "Değişiklik Günlüğü", son: false, simge: History, aciklama: "Kim, ne zaman, neyi değiştirdi" },
    ],
  },
  {
    grup: "Yönetim",
    yoneticiye: true,
    ogeler: [
      { yol: "/kullanicilar", etiket: "Kullanıcılar", son: false, simge: UserCog, aciklama: "Kullanıcı ekle, rol ata, şifre sıfırla" },
    ],
  },
];

export const MENU: readonly MenuOgesi[] = MENU_GRUPLARI.flatMap((g) => g.ogeler);

/** İkinci iş: maliyet muhasebesi (aylık SMM). Kendi menüsü vardır; fiyat çalışmasının menüsüyle karışmaz. */
export const SMM_MENU_GRUPLARI: MenuGrubu[] = [
  {
    grup: "Maliyet Muhasebesi",
    ogeler: [
      { yol: "/", etiket: "Ana Sayfa", son: true, simge: House },
      { yol: "/smm", etiket: "Dönemler", son: true, simge: CalendarRange, aciklama: "SMM Excel'ini yükle, aylık dönemleri yönet" },
      {
        yol: "/smm/veri",
        etiket: "Veri Girişi",
        son: false,
        simge: ListChecks,
        aciklama: "Aylık veriler: kontrol listesi, kaynak bazında yükleme, kapanış",
      },
      {
        yol: "/smm/stok",
        etiket: "Stok ve Envanter",
        son: false,
        simge: Warehouse,
        aciklama: "Dönem başı, alım, sayım, sarf ve ortalama maliyet",
      },
      {
        yol: "/smm/uretim",
        etiket: "Üretim Maliyeti",
        son: false,
        simge: Layers,
        aciklama: "20 → 40 → 50 aşama maliyetleri, işçilik ve genel gider dağıtımı",
      },
      {
        yol: "/smm/sarf-farki",
        etiket: "Sarf Farkı",
        son: false,
        simge: Scale,
        aciklama: "Reçeteye göre sarf ile sayıma göre sarf",
      },
      {
        yol: "/smm/ozet",
        etiket: "SMM Özeti",
        son: false,
        simge: Sigma,
        aciklama: "Satılan mamul maliyeti, stok mizanı karşılaştırması ve fiş taslağı",
      },
      {
        yol: "/smm/butce-kiyas",
        etiket: "Bütçe Kıyası",
        son: false,
        simge: GitCompareArrows,
        aciklama: "Fiyat çalışmasındaki bütçe maliyeti ile fiili birim maliyet, ürün ürün",
      },
      {
        yol: "/smm/aylar-arasi",
        etiket: "Aylar Arası",
        son: false,
        simge: ChartColumn,
        aciklama: "SMM tablosunun dönemler arası karşılaştırması ve değişim",
      },
    ],
  },
  {
    grup: "Ana veriler",
    ogeler: [
      {
        yol: "/smm/receteler",
        etiket: "Reçeteler",
        son: false,
        simge: ClipboardList,
        aciklama: "Canias ürün ağacı: kalıcı 20 / 40 / 50 reçeteleri ve alternatifler",
      },
      {
        yol: "/smm/sureler",
        etiket: "Üretim Süreleri",
        son: false,
        simge: Timer,
        aciklama: "Dolum ve etiket süreleri; işçilik ve genel gider dağıtımı",
      },
    ],
  },
];

export type Alan = "fiyat" | "smm";
export const ALAN_ANAHTARI = "fiyat-calismasi.alan";
export const ALAN_ADI: Record<Alan, string> = { fiyat: "Fiyat Çalışması", smm: "Maliyet Muhasebesi" };
const ALAN_SIMGESI: Record<Alan, LucideIcon> = { fiyat: Calculator, smm: Factory };
/** Kenar menü daraltma tercihi ("1" dar, "0" geniş; yoksa geniş). */
export const MENU_DAR_ANAHTARI = "fiyat-calismasi.menu-dar";

function kayitliDar(): boolean {
  try {
    return localStorage.getItem(MENU_DAR_ANAHTARI) === "1";
  } catch {
    return false;
  }
}

/** Bulunulan iş alanı: /smm ile başlayan sayfalar maliyet muhasebesi, diğerleri fiyat çalışması. */
export function useAlan(): Alan {
  return useLocation().pathname.startsWith("/smm") ? "smm" : "fiyat";
}

/** Oturumdaki rolün gördüğü menü grupları (Yönetim yalnız Genel Direktör'e, Veri girişi izleyiciye gösterilmez). */
export function useGorunurGruplar(alan: Alan = "fiyat"): MenuGrubu[] {
  const { girisZorunlu, yonetici, yazabilir } = useOturum();
  const kaynak = alan === "smm" ? SMM_MENU_GRUPLARI : MENU_GRUPLARI;
  return kaynak.filter((g) => (!g.yoneticiye || (girisZorunlu && yonetici)) && (!g.yazanlara || yazabilir));
}

/**
 * Kenar menünün tepesinde iki iş arasında geçiş (Ana Sayfa'ya dönmeden). Koyu zeminde (kenar menü) açık renkli segment;
 * dar menüde yalnız simgeler, ad `title` ile.
 */
function AlanSecici({ dar = false }: { dar?: boolean }) {
  const alan = useAlan();
  const { senaryoId } = useSenaryo();
  const hedef: Record<Alan, string> = { fiyat: senaryoId === null ? "/genel-bakis" : `/genel-bakis?senaryo=${senaryoId}`, smm: "/smm" };
  return (
    <nav aria-label="İş alanı" className={cn("flex flex-col rounded-xl bg-sidebar-accent p-0.5 text-xs", !dar && "w-full")}>
      {(["fiyat", "smm"] as Alan[]).map((a) => {
        const Simge = ALAN_SIMGESI[a];
        // Link (NavLink değil): seçili alan adrese değil bulunulan alana göre işaretlenir (/parametreler de "Fiyat Çalışması").
        return (
          <Link
            key={a}
            to={hedef[a]}
            aria-current={alan === a ? "page" : undefined}
            title={ALAN_ADI[a]}
            className={cn(
              "flex items-center gap-2 rounded-lg py-1.5 font-medium whitespace-nowrap text-sidebar-foreground/80 transition-colors hover:text-sidebar-accent-foreground",
              dar ? "justify-center px-0" : "px-2.5",
              alan === a && "bg-card text-foreground shadow-xs hover:text-foreground",
            )}
          >
            <Simge className="size-3.5 shrink-0" aria-hidden />
            <span className={cn(dar && "sr-only")}>{ALAN_ADI[a]}</span>
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * Menü bağlantıları seçili senaryoyu `?senaryo=` ile taşır (sayfa değişince senaryo sıfırlanmasın).
 * Dar menüde yalnız simge görünür; ad `title` ve ekran okuyucu metni olarak kalır, grup başlıkları gizlenir.
 */
function Menu({ kapat, dar = false }: { kapat: () => void; dar?: boolean }) {
  const { senaryoId } = useSenaryo();
  const { pathname } = useLocation();
  const alan = useAlan();
  const gruplar = useGorunurGruplar(alan);
  const ekte = (m: MenuOgesi) => !!m.ekYollar?.some((y) => pathname === y || pathname.startsWith(`${y}/`));
  return (
    <nav className={cn("flex flex-col gap-4", dar ? "px-2" : "px-3")} aria-label="Ana menü">
      {gruplar.map((g) => (
        <div key={g.grup} role="group" aria-label={g.grup} className="flex flex-col gap-0.5">
          <div className={cn("px-3 pb-1 text-[11px] font-semibold tracking-wider text-sidebar-foreground/65 uppercase", dar && "hidden")}>
            {g.grup}
          </div>
          {g.ogeler.map((m) => {
            const Simge = m.simge;
            return (
              <NavLink
                key={m.yol}
                to={senaryoId === null || alan === "smm" ? m.yol : `${m.yol}?senaryo=${senaryoId}`}
                end={m.son}
                onClick={kapat}
                title={dar ? m.etiket : undefined}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-full py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                    dar ? "justify-center px-0" : "px-3",
                    (isActive || ekte(m)) &&
                      "bg-sidebar-primary font-semibold text-sidebar-primary-foreground hover:bg-sidebar-primary hover:text-sidebar-primary-foreground",
                  )
                }
              >
                <Simge className="size-4 shrink-0" aria-hidden />
                <span className={cn(dar && "sr-only")}>{m.etiket}</span>
              </NavLink>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

/** Sağ üstte küçük "?" — Yardım sayfası ana menüde yer almaz (göz önünde değil, ulaşılabilir). */
function YardimBaglantisi() {
  const { senaryoId } = useSenaryo();
  return (
    <NavLink
      to={senaryoId === null ? "/yardim" : `/yardim?senaryo=${senaryoId}`}
      aria-label="Yardım"
      title="Yardım"
      className="inline-flex size-9 items-center justify-center rounded-full border text-muted-foreground hover:bg-accent/70 hover:text-foreground"
    >
      <CircleHelp className="size-4" aria-hidden="true" />
    </NavLink>
  );
}

export function Kabuk() {
  const [acik, setAcik] = useState(false);
  // Masaüstünde menü daraltılabilir (yalnız simgeler); tercih hatırlanır. Mobil çekmece (acik) her zaman geniştir.
  const [darTercih, setDarTercih] = useState(kayitliDar);
  const dar = darTercih && !acik;
  function darAyarla(d: boolean) {
    setDarTercih(d);
    try {
      localStorage.setItem(MENU_DAR_ANAHTARI, d ? "1" : "0");
    } catch {
      /* depolama kapalı */
    }
  }
  // Ana Sayfa bölüm seçme ekranıdır: sol panel yok (kartlar menünün yerini tutar); bir bölüm seçilince panel gelir.
  const anaSayfa = useLocation().pathname === "/";
  const alan = useAlan();
  // Ana Sayfa son kullanılan işi açsın diye bulunulan alan hatırlanır (Ana Sayfa'nın kendisi seçimi değiştirmez).
  useEffect(() => {
    if (anaSayfa) return;
    try {
      localStorage.setItem(ALAN_ANAHTARI, alan);
    } catch {
      /* depolama kapalı */
    }
  }, [alan, anaSayfa]);
  return (
    <SenaryoSaglayici>
      <div className="flex min-h-screen bg-background text-foreground">
        {acik && !anaSayfa && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" aria-hidden onClick={() => setAcik(false)} />}
        {!anaSayfa && (
          <aside
            data-dar={dar ? "true" : undefined}
            className={cn(
              "z-40 w-60 shrink-0 flex-col gap-5 overflow-x-hidden border-r border-sidebar-border bg-sidebar py-4 text-sidebar-foreground md:sticky md:top-3 md:my-3 md:ml-3 md:flex md:h-[calc(100vh-1.5rem)] md:overflow-y-auto md:rounded-2xl md:border md:shadow-sm",
              dar && "md:w-16",
              acik ? "fixed inset-y-0 left-0 flex shadow-xl md:static md:shadow-none" : "hidden",
            )}
          >
            {/* Üst blok: logo + alt yazı, hemen altında iş alanı anahtarı (üst çubuk tek satırda kalsın diye buraya taşındı). */}
            <div className={cn("flex flex-col gap-3", dar ? "items-center px-2" : "px-4")}>
              {!dar && (
                <div className="flex flex-col gap-1.5 px-1">
                  <Logo className="self-start" rozet />
                  <div className="px-0.5 text-xs font-medium text-sidebar-foreground/70">
                    {alan === "smm" ? "Maliyet Muhasebesi · SMM" : "Fiyat Çalışması · Berrak"}
                  </div>
                </div>
              )}
              <AlanSecici dar={dar} />
            </div>
            <Menu kapat={() => setAcik(false)} dar={dar} />
            <div className={cn("mt-auto hidden md:flex", dar ? "justify-center px-2" : "justify-end px-3")}>
              <button
                type="button"
                className="inline-flex size-8 items-center justify-center rounded-full text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none"
                aria-label={dar ? "Menüyü genişlet" : "Menüyü daralt"}
                title={dar ? "Menüyü genişlet" : "Menüyü daralt"}
                aria-expanded={!dar}
                onClick={() => darAyarla(!darTercih)}
              >
                {dar ? <PanelLeftOpen className="size-4" aria-hidden /> : <PanelLeftClose className="size-4" aria-hidden />}
              </button>
            </div>
          </aside>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Masaüstünde tek satır: sol grup daralır (senaryo seçici sınırlı genişlik), sağ grup küçülmez. Dar ekranda sarar. */}
          <header className="sticky top-0 z-20 flex min-h-14 flex-wrap items-center justify-between gap-3 border-b bg-background/85 px-4 py-2 backdrop-blur-md md:flex-nowrap lg:px-6">
            <div className="flex min-w-0 flex-1 items-center gap-3 [&_label]:sr-only [&_select]:max-w-[22rem] [&_select]:truncate xl:[&_label]:not-sr-only">
              {anaSayfa ? (
                <Logo />
              ) : (
                <button
                  type="button"
                  className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg border bg-background hover:bg-muted md:hidden"
                  aria-label={acik ? "Menüyü kapat" : "Menüyü aç"}
                  aria-expanded={acik}
                  onClick={() => setAcik((a) => !a)}
                >
                  {acik ? <X className="size-4" /> : <MenuSimgesi className="size-4" />}
                </button>
              )}
              {alan === "fiyat" && <SenaryoSecici />}
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <HizliArama />
              <HesapDugmesi />
              <YardimBaglantisi />
              <TemaAnahtari />
            </div>
          </header>
          <main className="sayfa-belir flex-1 px-4 py-6 lg:px-8">
            <Suspense
              fallback={
                <div role="status" className="text-sm text-muted-foreground">
                  Sayfa yükleniyor…
                </div>
              }
            >
              <DuzenlemeKilidiSaglayici>
                <Outlet />
              </DuzenlemeKilidiSaglayici>
            </Suspense>
          </main>
        </div>
      </div>
    </SenaryoSaglayici>
  );
}
