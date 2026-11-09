import { lazy } from "react";
import { createBrowserRouter } from "react-router-dom";
import { HataSayfasi } from "@/bilesenler/HataSayfasi";
import { Kabuk } from "@/bilesenler/Kabuk";
import { SayfaBulunamadi } from "@/bilesenler/SayfaBulunamadi";

// Sayfa başına kod bölme: ilk yüklemede yalnızca Kabuk gelir, sayfa kodu rota açılınca indirilir (Kabuk'ta Suspense).
const AnaSayfa = lazy(() => import("@/sayfalar/AnaSayfa"));
const Arsiv = lazy(() => import("@/sayfalar/Arsiv"));
const ButceGerceklesen = lazy(() => import("@/sayfalar/ButceGerceklesen"));
const KiyasUrun = lazy(() => import("@/sayfalar/KiyasUrun"));
const Dashboard = lazy(() => import("@/sayfalar/Dashboard"));
const GiderDagitim = lazy(() => import("@/sayfalar/GiderDagitim"));
const Gunluk = lazy(() => import("@/sayfalar/Gunluk"));
const HesapGoruntule = lazy(() => import("@/sayfalar/HesapGoruntule"));
const Kullanicilar = lazy(() => import("@/sayfalar/Kullanicilar"));
const ListeCalismasi = lazy(() => import("@/sayfalar/ListeCalismasi"));
const YaOlursa = lazy(() => import("@/sayfalar/YaOlursa"));
const ZamEtkisi = lazy(() => import("@/sayfalar/ZamEtkisi"));
const KurRiski = lazy(() => import("@/sayfalar/KurRiski"));
const KarlilikHaritasi = lazy(() => import("@/sayfalar/KarlilikHaritasi"));
const HedefFiyat = lazy(() => import("@/sayfalar/HedefFiyat"));
const SmmDonemler = lazy(() => import("@/sayfalar/smm/SmmDonemler"));
const SmmStok = lazy(() => import("@/sayfalar/smm/SmmStok"));
const SmmUretim = lazy(() => import("@/sayfalar/smm/SmmUretim"));
const SmmSarfFarki = lazy(() => import("@/sayfalar/smm/SmmSarfFarki"));
const SmmOzet = lazy(() => import("@/sayfalar/smm/SmmOzet"));
const SmmReceteler = lazy(() => import("@/sayfalar/smm/SmmReceteler"));
const SmmSureler = lazy(() => import("@/sayfalar/smm/SmmSureler"));
const SmmVeri = lazy(() => import("@/sayfalar/smm/SmmVeri"));
const MalzemeFiyatlari = lazy(() => import("@/sayfalar/MalzemeFiyatlari"));
const Karsilastirma = lazy(() => import("@/sayfalar/Karsilastirma"));
const Parametreler = lazy(() => import("@/sayfalar/Parametreler"));
const ReceteAktar = lazy(() => import("@/sayfalar/ReceteAktar"));
const SatisGecmisi = lazy(() => import("@/sayfalar/SatisGecmisi"));
const Teklifler = lazy(() => import("@/sayfalar/Teklifler"));
const Urunler = lazy(() => import("@/sayfalar/Urunler"));
const UrunMaliyeti = lazy(() => import("@/sayfalar/UrunMaliyeti"));
const UretimAdetleri = lazy(() => import("@/sayfalar/UretimAdetleri"));
const Uyarilar = lazy(() => import("@/sayfalar/Uyarilar"));
const VeriGirisi = lazy(() => import("@/sayfalar/VeriGirisi"));
const VeriKontrolu = lazy(() => import("@/sayfalar/VeriKontrolu"));
const Yardim = lazy(() => import("@/sayfalar/Yardim"));

export const rotalar = [
  {
    path: "/",
    element: <Kabuk />,
    errorElement: <HataSayfasi />,
    children: [
      // Açılış: menüdeki bölümler kart olarak; ürün tablosu (Genel Bakış) kendi adresinde.
      { index: true, element: <AnaSayfa /> },
      { path: "genel-bakis", element: <Dashboard /> },
      { path: "urunler", element: <Urunler /> },
      { path: "urunler/:kod", element: <UrunMaliyeti /> },
      { path: "hesaplar/:id", element: <HesapGoruntule /> },
      { path: "veri-girisi", element: <VeriGirisi /> },
      { path: "recete-aktar", element: <ReceteAktar /> },
      { path: "fiyatlar", element: <MalzemeFiyatlari /> },
      { path: "parametreler", element: <Parametreler /> },
      { path: "gider", element: <GiderDagitim /> },
      { path: "teklifler", element: <Teklifler /> },
      { path: "liste-calismasi", element: <ListeCalismasi /> },
      { path: "ya-olursa", element: <YaOlursa /> },
      { path: "zam-etkisi", element: <ZamEtkisi /> },
      { path: "kur-riski", element: <KurRiski /> },
      { path: "karlilik", element: <KarlilikHaritasi /> },
      { path: "hedef-fiyat", element: <HedefFiyat /> },
      { path: "smm", element: <SmmDonemler /> },
      { path: "smm/stok", element: <SmmStok /> },
      { path: "smm/uretim", element: <SmmUretim /> },
      { path: "smm/sarf-farki", element: <SmmSarfFarki /> },
      { path: "smm/ozet", element: <SmmOzet /> },
      { path: "smm/receteler", element: <SmmReceteler /> },
      { path: "smm/sureler", element: <SmmSureler /> },
      { path: "smm/veri", element: <SmmVeri /> },
      { path: "uretim-adetleri", element: <UretimAdetleri /> },
      { path: "satis-gecmisi", element: <SatisGecmisi /> },
      { path: "karsilastirma", element: <Karsilastirma /> },
      { path: "butce-gerceklesen", element: <ButceGerceklesen /> },
      { path: "butce-gerceklesen/:kod", element: <KiyasUrun /> },
      { path: "uyarilar", element: <Uyarilar /> },
      { path: "veri-kontrolu", element: <VeriKontrolu /> },
      { path: "yardim", element: <Yardim /> },
      { path: "gunluk", element: <Gunluk /> },
      { path: "arsiv", element: <Arsiv /> },
      { path: "kullanicilar", element: <Kullanicilar /> },
      { path: "*", element: <SayfaBulunamadi /> },
    ],
  },
];

export const yonlendirici = () => createBrowserRouter(rotalar);
