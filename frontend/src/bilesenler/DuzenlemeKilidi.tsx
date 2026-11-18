import { createContext, useContext, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { Lock, LockOpen } from "lucide-react";
import { hataMetni, yanitDinle } from "@/api/istemci";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { duzenlemeKilidiAcildiBildir } from "@/api/sorgular/duzenlemeKilidi";
import { Button } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";
import { alanaYazabilir, saltOkunurMetni, type YazmaAlani } from "@/yardimcilar/rolYetkisi";
import { useOturum } from "./GirisKapisi";
import { useSenaryoVarsa } from "./SenaryoSecici";

/** Kilidin açık kalacağı bitiş zamanı (epoch ms); sekmeye özel (sessionStorage): sekme kapanınca kilitli başlar. */
export const DUZENLEME_ANAHTARI = "fiyat-calismasi.duzenleme-acik-bitis";
/** İşlem yapılmadan geçen bu süreden sonra kilit kendiliğinden kapanır. */
export const DUZENLEME_SURESI_MS = 15 * 60 * 1000;
export const DUZENLEME_KILITLI_METNI = "Düzenleme kilitli";
export const SENARYO_KILITLI_METNI = "Senaryo kilitli";

type Durum = "acik" | "kilitli" | "doldu";

// ---------------------------------------------------------------- depo (uygulama genelinde tek; sayfa değişince korunur)
let bellekBitis: number | null = null; // sessionStorage kapalıysa yedek
let sureDoldu = false;
let zamanlayici: ReturnType<typeof setTimeout> | null = null;
const dinleyiciler = new Set<() => void>();
/** Bundan uzun kalan süre için zamanlayıcı kurulmaz (setTimeout taşması; yalnız testlerdeki "hep açık" değeri bu kadar uzundur). */
const EN_UZUN_ZAMANLAYICI_MS = 24 * 60 * 60 * 1000;

function bitisOku(): number | null {
  try {
    const v = Number(sessionStorage.getItem(DUZENLEME_ANAHTARI));
    return Number.isFinite(v) && v > 0 ? v : null;
  } catch {
    return bellekBitis;
  }
}

function bitisYaz(bitis: number | null): void {
  bellekBitis = bitis;
  try {
    if (bitis === null) sessionStorage.removeItem(DUZENLEME_ANAHTARI);
    else sessionStorage.setItem(DUZENLEME_ANAHTARI, String(bitis));
  } catch {
    /* depolama kapalı: bellekteki değer kullanılır */
  }
}

function anlik(): Durum {
  const b = bitisOku();
  if (b !== null && b > Date.now()) return "acik";
  return sureDoldu ? "doldu" : "kilitli";
}

function bildir(): void {
  for (const d of dinleyiciler) d();
}

function planla(): void {
  if (zamanlayici !== null) clearTimeout(zamanlayici);
  zamanlayici = null;
  if (dinleyiciler.size === 0) return;
  const b = bitisOku();
  if (b === null) return;
  const kalan = b - Date.now();
  if (kalan <= 0 || kalan > EN_UZUN_ZAMANLAYICI_MS) return;
  zamanlayici = setTimeout(() => {
    zamanlayici = null;
    const simdi = bitisOku();
    if (simdi !== null && simdi > Date.now()) return planla(); // bu arada yenilenmiş
    if (simdi !== null) {
      sureDoldu = true;
      bitisYaz(null);
    }
    bildir();
  }, kalan + 20);
}

function abone(dinleyici: () => void): () => void {
  dinleyiciler.add(dinleyici);
  if (dinleyiciler.size === 1) planla();
  return () => {
    dinleyiciler.delete(dinleyici);
    if (dinleyiciler.size === 0) planla();
  };
}

/** Kilidi açar (süre baştan başlar). */
function depoAc(): void {
  sureDoldu = false;
  bitisYaz(Date.now() + DUZENLEME_SURESI_MS);
  planla();
  bildir();
}

/** Kilidi kapatır. */
export function duzenlemeyiKilitle(): void {
  sureDoldu = false;
  bitisYaz(null);
  planla();
  bildir();
}

/** Kilit açıksa süreyi baştan başlatır (yazma isteği başarıyla tamamlandığında ve kullanıcı bir alana yazdığında). Kısaltmaz. */
export function duzenlemeSuresiniYenile(): void {
  const b = bitisOku();
  const simdi = Date.now();
  if (b === null || b <= simdi) return;
  const yeni = simdi + DUZENLEME_SURESI_MS;
  if (yeni > b) {
    bitisYaz(yeni);
    planla();
  }
}

/** Kilidin kapanmasına kalan saniye (kilitliyse 0). */
export function duzenlemeKalanSn(): number {
  const b = bitisOku();
  return b === null ? 0 : Math.max(0, Math.ceil((b - Date.now()) / 1000));
}

// Giriş/çıkışta kilitli başlanır; veri yazan her başarılı istek süreyi yeniler.
yanitDinle(({ yol, basarili, yazma }) => {
  if (!basarili || !yazma) return;
  if (yol === "/api/v1/kimlik/giris" || yol === "/api/v1/kimlik/cikis") duzenlemeyiKilitle();
  else if (!yol.startsWith("/api/v1/kimlik/")) duzenlemeSuresiniYenile();
});

// ---------------------------------------------------------------- yazma alanı
const YazmaAlaniBaglami = createContext<YazmaAlani>("genel");

/**
 * Altındaki ekran parçasının yazma alanını bildirir (varsayılan "genel"). Satın alma rolü yalnız `malzeme` alanında kilidi açabilir;
 * hangi rolün hangi alana yazdığı `yardimcilar/rolYetkisi.ts` dosyasındadır.
 */
export function YazmaAlaniSaglayici({ alan, children }: { alan: YazmaAlani; children: ReactNode }) {
  return <YazmaAlaniBaglami.Provider value={alan}>{children}</YazmaAlaniBaglami.Provider>;
}

/** Bu bileşenin yazma alanında oturumdaki rol değişiklik yapabilir mi (giriş kapalıysa her zaman evet). */
export function useAlanaYazabilir(alan?: YazmaAlani): boolean {
  const baglam = useContext(YazmaAlaniBaglami);
  const { girisZorunlu, rol } = useOturum();
  return alanaYazabilir(girisZorunlu, rol, alan ?? baglam);
}

// ---------------------------------------------------------------- kancalar
export interface DuzenlemeKilidiDurumu {
  /** Düzenleme açık mı (rolün yazamadığı alanda — izleyicide hiçbir yerde — hiçbir zaman açık değildir). */
  acik: boolean;
  /** Kilit süre dolduğu için kapandı (kullanıcı kapatmadı). */
  sureDoldu: boolean;
  /**
   * Kilidi açar ve olayı sunucuya bildirir (Değişiklik Günlüğü). Bildirim başarısız olsa da kilit açılır; dönen değer
   * kullanıcıya gösterilecek uyarıdır (başarılıysa null).
   */
  ac: (sayfa: string, senaryoId: number | null) => Promise<string | null>;
  kilitle: () => void;
  yenile: () => void;
}

async function ac(sayfa: string, senaryoId: number | null): Promise<string | null> {
  depoAc();
  try {
    await duzenlemeKilidiAcildiBildir({ senaryo_id: senaryoId, sayfa });
    return null;
  } catch (e) {
    return `Kilit açıldı ancak bu işlem Değişiklik Günlüğü'ne yazılamadı (${hataMetni(e)}).`;
  }
}

/**
 * Uygulama genelindeki düzenleme kilidi. Varsayılan kilitlidir; sağlayıcı olmadan da çalışır (durum sekmenin deposundadır).
 * `alan` verilmezse en yakın `YazmaAlaniSaglayici`nın alanı (yoksa "genel") kullanılır: kilit sekme genelinde tek olsa da
 * rolün yazamadığı alanda `acik` false döner (ör. satın alma Malzeme Fiyatları'nda açıp Parametreler'e geçerse orada kilitli).
 */
export function useDuzenlemeKilidi(alan?: YazmaAlani): DuzenlemeKilidiDurumu {
  const durum = useSyncExternalStore(abone, anlik, () => "kilitli" as Durum);
  const yazabilir = useAlanaYazabilir(alan);
  const acik = durum === "acik" && yazabilir;
  return useMemo(
    () => ({ acik, sureDoldu: durum === "doldu", ac, kilitle: duzenlemeyiKilitle, yenile: duzenlemeSuresiniYenile }),
    [acik, durum],
  );
}

/**
 * Sayfaların tek "yazılamaz" bayrağı: senaryo kilitliyse ya da düzenleme kilidi açık değilse `kilitli`. `neden` düğme
 * ipuçlarında kullanılır ("Senaryo kilitli" / "Düzenleme kilitli"). SenaryoSaglayici yoksa yalnız düzenleme kilidine bakar.
 */
export function useYazmaKilidi(alan?: YazmaAlani): {
  kilitli: boolean;
  senaryoKilitli: boolean;
  duzenlemeKilitli: boolean;
  neden: string | undefined;
} {
  const senaryoKilitli = useSenaryoVarsa()?.kilitli ?? false;
  const { acik } = useDuzenlemeKilidi(alan);
  return {
    kilitli: senaryoKilitli || !acik,
    senaryoKilitli,
    duzenlemeKilitli: !acik,
    neden: senaryoKilitli ? SENARYO_KILITLI_METNI : !acik ? DUZENLEME_KILITLI_METNI : undefined,
  };
}

/**
 * Kabuk'u sarar: kullanıcı herhangi bir alana yazdıkça kilit süresini yeniler (15 dakika işlem yapılmazsa kilitlenir).
 * Kilit durumu depodadır; bu yüzden sağlayıcı olmadan çizilen sayfalar (testler) da aynı kancayı kullanabilir.
 */
export function DuzenlemeKilidiSaglayici({ children }: { children: ReactNode }) {
  useEffect(() => {
    const yaz = () => duzenlemeSuresiniYenile();
    document.addEventListener("input", yaz, true);
    return () => document.removeEventListener("input", yaz, true);
  }, []);
  return <>{children}</>;
}

/** Kalan süre metni: bir dakikadan uzunsa dakika, son dakikada saniye. */
export function kalanMetni(sn: number): string {
  return sn > 60 ? `${Math.ceil(sn / 60)} dk kaldı` : `${sn} sn kaldı`;
}

function useKalanSn(acik: boolean): number {
  const [, setTik] = useState(0);
  useEffect(() => {
    // Çok uzak bitiş (testlerdeki "hep açık") için saat işletilmez.
    if (!acik || duzenlemeKalanSn() * 1000 > EN_UZUN_ZAMANLAYICI_MS) return;
    const t = setInterval(() => setTik((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [acik]);
  return acik ? duzenlemeKalanSn() : 0;
}

const SERIT = "flex flex-wrap items-center gap-x-3 gap-y-2 rounded-md border px-3 py-2 text-sm";

export interface DuzenlemeKilidiOzellikleri {
  className?: string;
  /** Senaryodan bağımsız modül (Maliyet Muhasebesi): senaryo kilidine bakılmaz, günlüğe senaryo_id null yazılır. */
  senaryosuz?: boolean;
  /** Şeridin yazma alanı (verilmezse en yakın `YazmaAlaniSaglayici`, yoksa "genel"). Rol bu alana yazamıyorsa düğme görünmez. */
  alan?: YazmaAlani;
  /** Rolün bu modülde ek yazma izni (verilmezse yalnız alan kuralı). false ise düğme görünmez, şerit hep kilitli görünür. */
  yazabilir?: boolean;
  /** `yazabilir` false iken gösterilecek metin (verilmezse rolün "Salt okunur: …" metni; izleyicide her zaman o). */
  yazamazMetni?: string;
  /** Düzenleme açık olsa da yazmayı engelleyen ek durum (ör. kapatılmış dönem); şeritte ikinci satırda gösterilir. */
  engelMetni?: string | null;
}

/**
 * Düzenleme kilidi şeridi (sayfa başlığının altında tek satır). Kilitliyken sayfadaki yazma alanları devre dışıdır;
 * "Düzenlemeyi aç" bilinçli bir adımdır ve Değişiklik Günlüğü'ne yazılır. Senaryo kilitliyse açılamaz; izleyici rolünde düğme yoktur.
 */
export function DuzenlemeKilidi({
  className,
  senaryosuz = false,
  alan,
  yazabilir: yazabilirDis,
  yazamazMetni,
  engelMetni,
}: DuzenlemeKilidiOzellikleri) {
  const senaryoBaglami = useSenaryoVarsa();
  const senaryo = senaryosuz ? null : senaryoBaglami;
  const senaryoId = senaryo?.senaryoId ?? null;
  const senaryoKilitli = senaryo?.kilitli ?? false;
  const oturum = useOturum();
  const alanaYazar = useAlanaYazabilir(alan);
  const yazabilir = alanaYazar && (yazabilirDis ?? true);
  const kilit = useDuzenlemeKilidi(alan);
  const acik = kilit.acik && yazabilir;
  const { sureDoldu: doldu, ac: kilidiAc, kilitle } = kilit;
  const { pathname } = useLocation();
  const [uyari, setUyari] = useState<string | null>(null);
  // Kilit açılırken bir kez sorulur; açık kaldığı sürece (15 dk) her değişiklikte yeniden sorulmaz.
  const [onay, setOnay] = useState(false);
  const kalan = useKalanSn(acik);

  if (acik) {
    return (
      <div
        role="group"
        aria-label="Düzenleme kilidi"
        data-testid="duzenleme-kilidi"
        data-durum="acik"
        className={cn(SERIT, "border-marka/50 bg-sari text-foreground", className)}
      >
        <LockOpen className="size-4 shrink-0 text-marka" aria-hidden />
        <span className="min-w-0 flex-1">
          <span aria-live="polite" className="font-medium">
            Düzenleme açık
          </span>
          {kalan * 1000 <= EN_UZUN_ZAMANLAYICI_MS && <span className="tabular-nums text-muted-foreground"> · {kalanMetni(kalan)}</span>}
          {engelMetni && (
            <span data-testid="duzenleme-engel" className="block font-medium">
              {engelMetni}
            </span>
          )}
          {uyari && (
            <span role="alert" className="block text-xs text-destructive">
              {uyari}
            </span>
          )}
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => {
            setUyari(null);
            kilitle();
          }}
        >
          <Lock aria-hidden /> Kilitle
        </Button>
      </div>
    );
  }

  const metin = !yazabilir
    ? (oturum.yazabilir && yazamazMetni) || saltOkunurMetni(oturum.rol)
    : senaryoKilitli
      ? "Düzenleme kilitli. Bu senaryo kilitli olduğu için düzenleme açılamaz."
      : doldu
        ? "Süre doldu; kaydetmek için kilidi yeniden açın."
        : "Düzenleme kilitli. Değişiklik yapmak için kilidi açın.";
  return (
    <div
      role="group"
      aria-label="Düzenleme kilidi"
      data-testid="duzenleme-kilidi"
      data-durum="kilitli"
      className={cn(SERIT, "border-border bg-muted/50 text-foreground", className)}
    >
      <Lock className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <span aria-live="polite" className="min-w-0 flex-1">
        {metin}
        {engelMetni && (
          <span data-testid="duzenleme-engel" className="block font-medium">
            {engelMetni}
          </span>
        )}
      </span>
      {yazabilir && (
        <Button
          type="button"
          size="sm"
          disabled={senaryoKilitli}
          title={senaryoKilitli ? "Senaryo kilitli: düzenleme açılamaz" : "Düzenlemeyi açar; 15 dakika işlem yapılmazsa yeniden kilitlenir"}
          onClick={() => setOnay(true)}
        >
          <LockOpen aria-hidden /> Düzenlemeyi aç
        </Button>
      )}
      {onay && (
        <OnayDiyalogu
          baslik="Düzenleme açılsın mı?"
          onayMetni="Evet, aç"
          onVazgec={() => setOnay(false)}
          onOnayla={() => {
            setOnay(false);
            setUyari(null);
            void kilidiAc(pathname, senaryoId).then(setUyari);
          }}
        >
          <p>Değişiklik yapmak üzeresiniz. Emin misiniz?</p>
          <p className="text-muted-foreground">
            Düzenleme 15 dakika açık kalır; bu sürede yaptığınız değişiklikler için yeniden sorulmaz. Kilidi açtığınız Değişiklik Günlüğü'ne
            yazılır.
          </p>
        </OnayDiyalogu>
      )}
    </div>
  );
}
