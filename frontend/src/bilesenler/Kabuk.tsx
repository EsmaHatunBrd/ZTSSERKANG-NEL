import { Suspense, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Boxes,
  CalendarRange,
  ChartPie,
  ClipboardList,
  FileSpreadsheet,
  GitCompareArrows,
  Handshake,
  History,
  House,
  ListChecks,
  Layers,
  Menu as MenuSimgesi,
  PackageSearch,
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
      { yol: "/urunler", etiket: "Ürün Maliyeti", son: false, simge: PackageSearch, aciklama: "Tek ürünün reçetesi, giderleri ve fiyatı" },
      { yol: "/teklifler", etiket: "Teklifler", son: false, simge: Handshake, aciklama: "Teklif turları ve Teklif Kapak" },
      {
        yol: "/ya-olursa",
        etiket: "Analiz",
        son: false,
        simge: TrendingUp,
        ekYollar: ["/zam-etkisi", "/kur-riski", "/karlilik", "/hedef-fiyat", "/liste-calismasi"],
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

/** Üst çubukta iki iş arasında geçiş (Ana Sayfa'ya dönmeden). */
function AlanSecici() {
  const alan = useAlan();
  const { senaryoId } = useSenaryo();
  const hedef: Record<Alan, string> = { fiyat: senaryoId === null ? "/genel-bakis" : `/genel-bakis?senaryo=${senaryoId}`, smm: "/smm" };
  return (
    <nav aria-label="İş alanı" className="flex rounded-full border bg-muted p-0.5 text-sm">
      {(["fiyat", "smm"] as Alan[]).map((a) => (
        <NavLink
          key={a}
          to={hedef[a]}
          aria-current={alan === a ? "page" : undefined}
          className={cn(
            "rounded-full px-3 py-1 font-medium text-muted-foreground transition-colors hover:text-foreground",
            alan === a && "bg-card text-foreground shadow-xs",
          )}
        >
          {ALAN_ADI[a]}
        </NavLink>
      ))}
    </nav>
  );
}

/** Menü bağlantıları seçili senaryoyu `?senaryo=` ile taşır (sayfa değişince senaryo sıfırlanmasın). */
function Menu({ kapat }: { kapat: () => void }) {
  const { senaryoId } = useSenaryo();
  const { pathname } = useLocation();
  const alan = useAlan();
  const gruplar = useGorunurGruplar(alan);
  const ekte = (m: MenuOgesi) => !!m.ekYollar?.some((y) => pathname === y || pathname.startsWith(`${y}/`));
  return (
    <nav className="flex flex-col gap-4 px-3" aria-label="Ana menü">
      {gruplar.map((g) => (
        <div key={g.grup} role="group" aria-label={g.grup} className="flex flex-col gap-0.5">
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-sidebar-foreground/65 uppercase">{g.grup}</div>
          {g.ogeler.map((m) => {
            const Simge = m.simge;
            return (
              <NavLink
                key={m.yol}
                to={senaryoId === null || alan === "smm" ? m.yol : `${m.yol}?senaryo=${senaryoId}`}
                end={m.son}
                onClick={kapat}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-full px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                    (isActive || ekte(m)) &&
                      "bg-sidebar-primary font-semibold text-sidebar-primary-foreground hover:bg-sidebar-primary hover:text-sidebar-primary-foreground",
                  )
                }
              >
                <Simge className="size-4 shrink-0" aria-hidden />
                {m.etiket}
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
            className={cn(
              "z-40 w-60 shrink-0 flex-col gap-6 border-r border-sidebar-border bg-sidebar py-5 text-sidebar-foreground md:sticky md:top-3 md:my-3 md:ml-3 md:flex md:h-[calc(100vh-1.5rem)] md:overflow-y-auto md:rounded-2xl md:border md:shadow-sm",
              acik ? "fixed inset-y-0 left-0 flex shadow-xl md:static md:shadow-none" : "hidden",
            )}
          >
            <div className="flex flex-col gap-1.5 px-5">
              <Logo className="self-start" rozet />
              <div className="px-0.5 text-xs font-medium text-sidebar-foreground/70">
                {alan === "smm" ? "Maliyet Muhasebesi · SMM" : "Fiyat Çalışması · Berrak"}
              </div>
            </div>
            <Menu kapat={() => setAcik(false)} />
          </aside>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Dar görünümde başlık satırı sarar; kullanıcı adı kısaltılır, yatay taşma olmaz. */}
          <header className="sticky top-0 z-20 flex min-h-14 flex-wrap items-center justify-between gap-3 border-b bg-background/85 px-4 py-2 backdrop-blur-md lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              {anaSayfa ? (
                <Logo />
              ) : (
                <button
                  type="button"
                  className="inline-flex size-8 items-center justify-center rounded-lg border bg-background hover:bg-muted md:hidden"
                  aria-label={acik ? "Menüyü kapat" : "Menüyü aç"}
                  aria-expanded={acik}
                  onClick={() => setAcik((a) => !a)}
                >
                  {acik ? <X className="size-4" /> : <MenuSimgesi className="size-4" />}
                </button>
              )}
              {!anaSayfa && <AlanSecici />}
              {alan === "fiyat" && <SenaryoSecici />}
            </div>
            <div className="flex min-w-0 items-center gap-2">
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
              <Outlet />
            </Suspense>
          </main>
        </div>
      </div>
    </SenaryoSaglayici>
  );
}
