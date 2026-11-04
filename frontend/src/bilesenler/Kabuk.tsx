import { Suspense, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Calculator,
  Coins,
  FileText,
  LayoutDashboard,
  ListChecks,
  Menu as MenuSimgesi,
  PencilLine,
  Scale,
  ScrollText,
  Settings2,
  Upload,
  Wallet,
  Factory,
  X,
  CircleHelp,
  History,
  House,
  UsersRound,
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
      { yol: "/genel-bakis", etiket: "Genel Bakış", son: false, simge: LayoutDashboard, aciklama: "Tüm ürünlerin maliyet ve satış özeti" },
      { yol: "/urunler", etiket: "Ürün Maliyeti", son: false, simge: Calculator, aciklama: "Tek ürünün reçetesi, giderleri ve fiyatı" },
      { yol: "/teklifler", etiket: "Teklifler", son: false, simge: FileText, aciklama: "Teklif turları ve Teklif Kapak" },
      // Bütçe vs Gerçekleşen, ürün aileleri ve geçmiş kayıtlar tek öğe; sayfalar arası geçiş sekmelerle (SayfaSekmeleri).
      {
        yol: "/butce-gerceklesen",
        etiket: "Kıyasla",
        son: false,
        simge: Scale,
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
        simge: PencilLine,
        aciklama: "Fiyat, parametre, gider, üretim bilgisini tek tek gir",
      },
      { yol: "/recete-aktar", etiket: "Veri Aktar", son: false, simge: Upload, aciklama: "Excel'den toplu yükle" },
    ],
  },
  {
    // Girilen veriyi nerede görürüm: tam listeler, geçmiş ve düzenleme.
    grup: "Kayıtlar",
    ogeler: [
      { yol: "/fiyatlar", etiket: "Malzeme Fiyatları", son: false, simge: Coins, aciklama: "Malzeme kartları, fiyatlar ve revizeler" },
      { yol: "/parametreler", etiket: "Parametreler", son: false, simge: Settings2, aciklama: "Enflasyon, kurlar, faiz, kâr oranları" },
      { yol: "/gider", etiket: "Gider Dağıtım", son: false, simge: Wallet, aciklama: "Gider havuzları ve dağıtım payları" },
      { yol: "/uretim-adetleri", etiket: "Üretim Adetleri", son: false, simge: Factory, aciklama: "Vardiya kapasitesi ve hedef adetler" },
      { yol: "/satis-gecmisi", etiket: "Satış Geçmişi", son: false, simge: History, aciklama: "Geçen yıl satış fiyatları" },
    ],
  },
  {
    grup: "Kontrol",
    ogeler: [
      {
        yol: "/veri-kontrolu",
        etiket: "Veri Kontrolü",
        son: false,
        simge: ListChecks,
        ekYollar: ["/uyarilar"],
        aciklama: "Eksik ya da çelişkili veriler tek listede",
      },
      { yol: "/gunluk", etiket: "Değişiklik Günlüğü", son: false, simge: ScrollText, aciklama: "Kim, ne zaman, neyi değiştirdi" },
    ],
  },
  {
    grup: "Yönetim",
    yoneticiye: true,
    ogeler: [
      { yol: "/kullanicilar", etiket: "Kullanıcılar", son: false, simge: UsersRound, aciklama: "Kullanıcı ekle, rol ata, şifre sıfırla" },
    ],
  },
];

export const MENU: readonly MenuOgesi[] = MENU_GRUPLARI.flatMap((g) => g.ogeler);

/** Oturumdaki rolün gördüğü menü grupları (Yönetim yalnız Genel Direktör'e, Veri girişi izleyiciye gösterilmez). */
export function useGorunurGruplar(): MenuGrubu[] {
  const { girisZorunlu, yonetici, yazabilir } = useOturum();
  return MENU_GRUPLARI.filter((g) => (!g.yoneticiye || (girisZorunlu && yonetici)) && (!g.yazanlara || yazabilir));
}

/** Menü bağlantıları seçili senaryoyu `?senaryo=` ile taşır (sayfa değişince senaryo sıfırlanmasın). */
function Menu({ kapat }: { kapat: () => void }) {
  const { senaryoId } = useSenaryo();
  const { pathname } = useLocation();
  const gruplar = useGorunurGruplar();
  const ekte = (m: MenuOgesi) => !!m.ekYollar?.some((y) => pathname === y || pathname.startsWith(`${y}/`));
  return (
    <nav className="flex flex-col gap-4 px-3" aria-label="Ana menü">
      {gruplar.map((g) => (
        <div key={g.grup} role="group" aria-label={g.grup} className="flex flex-col gap-0.5">
          <div className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{g.grup}</div>
          {g.ogeler.map((m) => {
            const Simge = m.simge;
            return (
              <NavLink
                key={m.yol}
                to={senaryoId === null ? m.yol : `${m.yol}?senaryo=${senaryoId}`}
                end={m.son}
                onClick={kapat}
                className={({ isActive }) =>
                  cn(
                    "relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                    (isActive || ekte(m)) &&
                      "bg-sidebar-accent font-semibold text-sidebar-accent-foreground before:absolute before:inset-y-1.5 before:left-0 before:w-1 before:rounded-full before:bg-marka",
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
  return (
    <SenaryoSaglayici>
      <div className="flex min-h-screen bg-background text-foreground">
        {acik && !anaSayfa && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" aria-hidden onClick={() => setAcik(false)} />}
        {!anaSayfa && (
          <aside
            className={cn(
              "z-40 w-60 shrink-0 flex-col gap-5 border-r bg-sidebar py-4 text-sidebar-foreground md:flex",
              acik ? "fixed inset-y-0 left-0 flex shadow-xl md:static md:shadow-none" : "hidden",
            )}
          >
            <div className="flex flex-col gap-1.5 px-5">
              <Logo />
              <div className="text-xs font-medium text-muted-foreground">Fiyat Çalışması · Berrak</div>
            </div>
            <Menu kapat={() => setAcik(false)} />
          </aside>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Dar görünümde başlık satırı sarar; kullanıcı adı kısaltılır, yatay taşma olmaz. */}
          <header className="sticky top-0 z-20 flex min-h-14 flex-wrap items-center justify-between gap-3 border-b bg-background/90 px-4 py-2 backdrop-blur lg:px-8">
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
              <SenaryoSecici />
            </div>
            <div className="flex min-w-0 items-center gap-2">
              <HizliArama />
              <HesapDugmesi />
              <YardimBaglantisi />
              <TemaAnahtari />
            </div>
          </header>
          <main className="flex-1 px-4 py-6 lg:px-8">
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
