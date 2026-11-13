import { lazy, Suspense, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { LoaderCircle, TriangleAlert } from "lucide-react";
import { Link, UNSAFE_DataRouterContext, useBlocker, useParams } from "react-router-dom";
import { HATA_KODU, hataMetni, type ApiHatasi } from "@/api/istemci";
import { useHesapla, useTopluKaydet } from "@/api/sorgular/hesaplar";
import { useGiderHavuzlari } from "@/api/sorgular/gider";
import { useRecete, useUrun, useUrunler } from "@/api/sorgular/urunler";
import type { HesapYaniti, Sema } from "@/api/tipler";
import { DegisiklikCubugu } from "@/bilesenler/DegisiklikCubugu";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { DuzenlemeKilidi, useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { UyariRozeti } from "@/bilesenler/UyariRozeti";
import { AYRILMA_UYARISI, useAyrilmaUyarisi } from "@/yardimcilar/ayrilmaUyarisi";
import { sonAcilaniKaydet } from "@/yardimcilar/sonAcilanlar";
import { FinansmanTablosu } from "./urun/FinansmanTablosu";
import { GiderKalemleri } from "./urun/GiderKalemleri";
import { KaydetDiyalogu, type KaydetSecimi } from "./urun/KaydetDiyalogu";
import { AileRozeti } from "./urun/AileRozeti";
import { KarsilastirmaKarti } from "./urun/KarsilastirmaKarti";
import { KurlarBlogu } from "./urun/KurlarBlogu";
import { ReceteTablosu } from "./urun/ReceteTablosu";
import { SonucSeridi } from "./urun/SonucSeridi";
import { StokEtkisiKarti } from "./urun/StokEtkisiKarti";
import {
  degisiklikListesi,
  dusenFireSatirlari,
  sunucuDegerleri,
  taslakBos,
  taslakSayisi,
  taslakYamasi,
  taslaktanKaydetGovdesi,
  taslaktanOverride,
  type Taslak,
  type TaslakYamasi,
} from "./urun/Taslak";
import { TeklifPaneli } from "./urun/TeklifPaneli";
import { HesapGecmisi } from "./urun/HesapGecmisi";
import { ToplamlarKarti } from "./urun/ToplamlarKarti";
import { UretimBilgileri } from "./urun/UretimBilgileri";
import { parametreGorunumu } from "./urun/yardimci";
import { ElleReceteFormu } from "./aktar/ElleReceteFormu";
import { UretimBilgileriKarti } from "./girdi/UretimBilgileriKarti";

export const SENARYO_DISI_METNI = "Bu ürün bu çalışmada yok — reçete kaydedince dahil olur";
export const RECETE_YOK_METNI = "Reçete girilince hesaplanır";
export const HEDEF_YOK_METNI = "Hesap için üretim bilgileri gerekli";
/**
 * Backend'in "üretim hedefi yok" hesap hatası (kod `hedef_yok`; yeni ürünün ilk hesabı): ekranda üretim bilgileri kartı açılır.
 */
const hedefYokHatasi = (e: ApiHatasi | null) => e?.kod === HATA_KODU.hedefYok;
/** Boş çalışmada parametre değerleri (kur, enflasyon, faiz…) girilmeden hesap koşmaz (kod `parametre_eksik`): Parametreler sayfasına yönlendirilir. */
const parametreEksikHatasi = (e: ApiHatasi | null) => e?.kod === HATA_KODU.parametreEksik;

// recharts yalnızca grafik çizilirken indirilir (ilk yükleme paketini şişirmesin).
const YuzdeGrafigi = lazy(() => import("./urun/YuzdeGrafigi").then((m) => ({ default: m.YuzdeGrafigi })));

const DEBOUNCE_MS = 300;

export interface KayitDurumu {
  hesapId: number | null;
  /** "ürün kartı, 3 reçete satırı ..." gibi yazılan kayıtların özeti. */
  ozet: string;
  /** Sunucunun kayıt sırasında döndürdüğü uyarılar. */
  uyarilar: string[];
}

/** Taslak doluyken uygulama içi gezinmeyi engeller (yalnız veri yönlendiricisinde çalışır); tarayıcı diyaloğu `useAyrilmaUyarisi`'nda. */
function GecisEngeli({ aktif }: { aktif: boolean }) {
  const blok = useBlocker(
    ({ currentLocation, nextLocation }) =>
      aktif && currentLocation.pathname + currentLocation.search !== nextLocation.pathname + nextLocation.search,
  );
  return blok.state === "blocked" ? (
    <OnayDiyalogu baslik="Sayfadan ayrılıyorsunuz" onayMetni="Ayrıl" onOnayla={() => blok.proceed()} onVazgec={() => blok.reset()}>
      <p>{AYRILMA_UYARISI}</p>
    </OnayDiyalogu>
  ) : null;
}

/** Değişiklik çubuğu için taslak özeti: değişen satır, fire override'lı satır ve satır dışı alan sayıları. */
function taslakOzeti(t: Taslak) {
  const satirlar = Object.values(t.satirlar);
  const satirAlan = satirlar.reduce((n, s) => n + Object.values(s).filter((v) => v !== undefined).length, 0);
  return {
    satirSayisi: satirlar.filter((s) => Object.values(s).some((v) => v !== undefined)).length,
    fireSayisi: satirlar.filter((s) => s.fire !== undefined).length,
    alanSayisi: taslakSayisi(t) - satirAlan,
  };
}

/** Hesap durumu satırı: yeniden hesap sürüyor, hesap hatası (çubuk yokken) ve son kaydın özeti. */
function HesapDurumu({ hesaplaniyor, hata, kayit }: { hesaplaniyor: boolean; hata: string | null; kayit: KayitDurumu | null }) {
  if (!hesaplaniyor && !hata && !kayit) return null;
  return (
    <div aria-live="polite" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
      {hesaplaniyor && (
        <span role="status" aria-label="Hesaplanıyor" className="flex items-center gap-1.5 text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin" aria-hidden />
          Hesaplanıyor
        </span>
      )}
      {hata && (
        <span role="alert" className="text-destructive">
          {hata}
        </span>
      )}
      {kayit && (
        <span
          role="status"
          aria-label="Kayıt durumu"
          className="rounded-md bg-green-50 px-2.5 py-1 text-green-900 dark:bg-green-950/40 dark:text-green-200"
        >
          {`Kaydedildi${kayit.hesapId !== null ? ` · Hesap #${kayit.hesapId}` : ""}${kayit.ozet ? ` · ${kayit.ozet}` : ""}`}
        </span>
      )}
      {kayit && kayit.uyarilar.length > 0 && (
        <ul className="basis-full text-xs text-muted-foreground" aria-label="Kayıt uyarıları">
          {kayit.uyarilar.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function UrunMaliyeti() {
  const { kod = "" } = useParams();
  // Ürün seçicideki "Son açılanlar": doğrudan adres/hızlı arama ile açılan ürünler de listeye girsin.
  useEffect(() => {
    if (kod) sonAcilaniKaydet(kod);
  }, [kod]);
  const { senaryoId, senaryo } = useSenaryo();
  // Düzenleme kilidi: hücreler kendi içinde kapanır (GirdiHucresi); burada Kaydet ve anında kaydeden kartlar kapatılır.
  // Taslak silinmez: süre dolarsa değerler ekranda kalır, kilit yeniden açılınca kaydedilir.
  const { kilitli: yazmaKilitli, neden: kilitNedeni } = useYazmaKilidi();
  const urun = useUrun(kod, senaryoId);
  const recete = useRecete(kod, senaryoId);
  const veriYonlendirici = useContext(UNSAFE_DataRouterContext) !== null;

  const [tarih, setTarih] = useState("");
  const [taslak, setTaslak] = useState<Taslak>(taslakBos);
  const [sonuc, setSonuc] = useState<HesapYaniti | null>(null);
  /** Taslaksız (kayıtlı değerlerle) son hesap: "eski değer" ve sunucuyla aynı mı karşılaştırması için. */
  const [taban, setTaban] = useState<HesapYaniti | null>(null);
  const [kayit, setKayit] = useState<KayitDurumu | null>(null);
  const [kaydetAcik, setKaydetAcik] = useState(false);
  // Ürün listesi ucu yalnız dashboard hesabıdır (yavaş); bu yüzden yalnız diyalog açılınca ve tek kayıtla (boyut=1) istenir, `toplam` kullanılır.
  const urunSayisi = useUrunler(kaydetAcik ? senaryoId : null, { boyut: 1 }).data?.toplam ?? null;
  const [kaydetHatasi, setKaydetHatasi] = useState<string | null>(null);
  const [uyariAcik, setUyariAcik] = useState(false);
  /** Ekrandan yazılan üretim bilgisi gibi hesabı etkileyen dış kayıtlardan sonra hesabı yeniden koşturur. */
  const [hesapTetik, setHesapTetik] = useState(0);
  const [hedefMesaji, setHedefMesaji] = useState<string | null>(null);

  const hesapla = useHesapla();
  const { mutate: hesaplaCalistir, reset: hesaplaSifirla } = hesapla;
  const topluKaydet = useTopluKaydet();
  const havuzlar = useGiderHavuzlari(senaryoId).data?.kayitlar;

  const receteSatirlari = useMemo(() => recete.data?.satirlar ?? [], [recete.data]);
  const kayitliMarka = urun.data?.marka ?? null;
  const sunucu = useMemo(
    () => ({ ...sunucuDegerleri(taban, receteSatirlari), marka: kayitliMarka }),
    [taban, receteSatirlari, kayitliMarka],
  );
  const sunucuRef = useRef(sunucu);
  sunucuRef.current = sunucu;

  /** Çocuk bileşenlerin tek yazma kapısı: yama taslağa uygulanır, sunucuyla aynı değerler düşer. */
  const onTaslak = useCallback((yama: TaslakYamasi) => {
    setTaslak((t) => taslakYamasi(t, yama, sunucuRef.current));
  }, []);

  const govde = useMemo<Sema["HesaplaGiris"] | null>(() => {
    if (senaryoId === null) return null;
    const g: Sema["HesaplaGiris"] = { senaryo_id: senaryoId };
    if (tarih) g.tarih = tarih;
    const o = taslaktanOverride(taslak, receteSatirlari, sunucu.giderElle);
    if (o) g.override = o;
    return g;
  }, [senaryoId, tarih, taslak, receteSatirlari, sunucu.giderElle]);

  const receteHazir = !recete.isPending;
  const receteSurumu = recete.data?.id ?? null;
  // Faz 5c: reçetesiz ürün (bu çalışmada aktif reçete yok) — sunucu 404 yerine versiyon 0 döner; hesap koşmaz, reçete formu açılır.
  const receteYok = recete.data !== undefined && recete.data.versiyon === 0;
  const senaryoDisi = urun.data?.senaryoda === false;
  const ilkCalisma = useRef(true);
  // Reçete sürümü değişince satır taslakları eski sürümün satırlarına ait olabilir: temizlenir.
  const oncekiSurum = useRef<number | null>(null);

  // Ürün/senaryo değişince önceki ürünün sonucu, hesap hatası ve taslağı gösterilmesin
  // (bayat "üretim hedefi yok" hatası yeni ürün için üretim bilgileri kartını açmasın).
  useEffect(() => {
    oncekiSurum.current = null;
    ilkCalisma.current = true;
    setSonuc(null);
    setTaban(null);
    setTaslak(taslakBos());
    setKayit(null);
    setKaydetAcik(false);
    hesaplaSifirla();
  }, [kod, senaryoId, hesaplaSifirla]);

  useEffect(() => {
    const onceki = oncekiSurum.current;
    oncekiSurum.current = receteSurumu;
    if (onceki === null || receteSurumu === null || onceki === receteSurumu) return;
    setTaslak((t) => (Object.keys(t.satirlar).length === 0 ? t : { ...t, satirlar: {} }));
  }, [receteSurumu]);

  // Hesap gövdesi içerik olarak aynıysa yeniden koşma: her başarılı hesap `taban`ı yeniler, `sunucu` ve dolayısıyla
  // `govde` nesnesi yeni kimlik alır; kimliğe bağlı effect sonsuz hesapla döngüsüne giriyordu (sayfa "titriyor").
  const govdeAnahtari = useMemo(() => (govde ? JSON.stringify(govde) : null), [govde]);
  const govdeRef = useRef(govde);
  govdeRef.current = govde;

  // Her değişiklikte hesabı yeniden koş (ilk çalıştırma hemen, sonrakiler 300 ms debounce). Reçete yeni versiyona geçince de yenilenir.
  useEffect(() => {
    const govde = govdeRef.current;
    if (!govdeAnahtari || !govde || !kod || !receteHazir || receteYok) return;
    const bekle = ilkCalisma.current ? 0 : DEBOUNCE_MS;
    ilkCalisma.current = false;
    const taslaksiz = !govde.override;
    const zamanlayici = setTimeout(() => {
      hesaplaCalistir(
        { kod, govde },
        {
          onSuccess: (y) => {
            setSonuc(y);
            if (taslaksiz) setTaban(y);
          },
        },
      );
    }, bekle);
    return () => clearTimeout(zamanlayici);
  }, [govdeAnahtari, kod, receteHazir, receteYok, receteSurumu, hesapTetik, hesaplaCalistir]);

  const sayi = taslakSayisi(taslak);
  const ozet = useMemo(() => taslakOzeti(taslak), [taslak]);
  useAyrilmaUyarisi(sayi > 0);

  const parametreler = useMemo(() => (sonuc ? parametreGorunumu(sonuc) : null), [sonuc]);
  const uyarilar = sonuc?.uyarilar ?? [];
  const yurtdisi = uyarilar.some((u) => u.includes("Yurtdışı"));

  const parametreDegis = useCallback(
    (anahtar: string, deger: string | null) => onTaslak({ parametreler: { [anahtar]: deger ?? undefined } }),
    [onTaslak],
  );

  const degisiklikler = useMemo(() => degisiklikListesi(taslak, sunucu, havuzlar), [taslak, sunucu, havuzlar]);
  const dusenFire = useMemo(() => dusenFireSatirlari(taslak, receteSatirlari), [taslak, receteSatirlari]);

  function kaydetAc() {
    if (topluKaydet.isPending) return;
    topluKaydet.reset();
    setKaydetHatasi(null);
    setKaydetAcik(true);
  }

  function gonder(secim: KaydetSecimi) {
    if (senaryoId === null || topluKaydet.isPending) return;
    setKaydetHatasi(null);
    let kayitGovdesi: Sema["TopluKaydetGiris"];
    try {
      kayitGovdesi = taslaktanKaydetGovdesi(taslak, {
        senaryoId,
        tarih: tarih || undefined,
        neden: secim.neden,
        hesabiKaydet: secim.hesabiKaydet,
        urun: urun.data,
        hedef: urun.data?.uretim_hedefi ?? taban?.uretim ?? null,
        recete: receteSatirlari,
        kapsamSecimi: secim.kapsamSecimi,
        havuzlar,
        giderElle: sunucu.giderElle,
      });
    } catch (e) {
      setKaydetHatasi(e instanceof Error ? e.message : "Kayıt hazırlanamadı");
      return;
    }
    topluKaydet.mutate(
      { kod, govde: kayitGovdesi },
      {
        onSuccess: (y) => {
          const z = y.yazilan;
          const parcalar = [
            z.urun > 0 && "ürün kartı",
            z.hedef > 0 && "üretim hedefi",
            z.recete > 0 && `${z.recete} reçete satırı`,
            z.parametre > 0 && `${z.parametre} parametre`,
            z.havuz > 0 && `${z.havuz} gider havuzu`,
          ].filter(Boolean);
          setKayit({
            hesapId: y.hesap_id,
            ozet: parcalar.join(", "),
            uyarilar: y.uyarilar,
          });
          setTaslak(taslakBos());
          setKaydetAcik(false);
        },
      },
    );
  }

  const hesaplaHatasi = hesapla.error as ApiHatasi | null;
  const receteHatasi = recete.error as ApiHatasi | null;
  const duzgunHata = hesaplaHatasi ?? receteHatasi;
  const baslikAdi = urun.data?.ad ?? kod;
  // Son yeniden hesap başarısız oldu ama eski sonuç elde: sayılar güncel değil.
  const bayat = !!hesaplaHatasi && sonuc !== null;
  const bayatSinif = bayat ? "opacity-60" : undefined;
  const kaydetKapali = yazmaKilitli || !!hesaplaHatasi || !taban || !urun.data;
  const kaydetNedeni = yazmaKilitli
    ? (kilitNedeni ?? "Senaryo kilitli")
    : hesaplaHatasi
      ? "Hesap hatası var: önce değişikliği düzeltin"
      : "Ürün ve hesap bilgisi yüklenince kaydedilebilir";
  const sunucuHatasi = kaydetHatasi ?? (topluKaydet.error ? hataMetni(topluKaydet.error) : null);

  return (
    <div className="flex flex-col gap-6">
      {veriYonlendirici && <GecisEngeli aktif={sayi > 0} />}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">{baslikAdi}</h1>
          <p className="text-sm text-muted-foreground">
            <Badge variant="outline">{kod}</Badge>
            {senaryo && <span className="ml-2">{`${senaryo.sezon_ad} · ${senaryo.ad}`}</span>}
          </p>
          <AileRozeti kod={kod} aile={urun.data?.aile} aileAd={urun.data?.aile_ad} />
        </div>
        <div className="flex items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <span className="text-muted-foreground">Hesap tarihi</span>
            <Input
              type="date"
              aria-label="Hesap tarihi"
              value={tarih || sonuc?.hesap_tarihi || ""}
              onChange={(e) => setTarih(e.target.value)}
              className="w-40"
            />
          </label>
          {uyarilar.length > 0 && (
            <div className="relative">
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-expanded={uyariAcik}
                aria-controls="uyari-listesi"
                onClick={() => setUyariAcik((a) => !a)}
              >
                Uyarılar
                <UyariRozeti sayi={uyarilar.length} />
              </Button>
              {uyariAcik && (
                <ul
                  id="uyari-listesi"
                  className="absolute right-0 z-20 mt-1 flex w-96 max-w-[90vw] flex-col gap-1.5 rounded-xl border bg-popover p-3 text-sm text-popover-foreground shadow-lg"
                >
                  {uyarilar.map((u) => (
                    <li key={u}>{u}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </header>

      {sonuc && !receteYok && (
        <SonucSeridi
          toplamlar={sonuc.toplamlar}
          toplamlarFiresiz={sonuc.toplamlar_firesiz ?? null}
          fiyatlar={sonuc.fiyatlar}
          bayat={bayat}
        />
      )}

      <KilitSeridi />
      <DuzenlemeKilidi />

      {senaryoDisi && (
        <p
          role="status"
          data-testid="senaryo-disi-seridi"
          className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {SENARYO_DISI_METNI}
            <span className="block text-xs opacity-90">
              Ürün kartı tüm çalışmalarda ortaktır; bu çalışmanın dashboard ve hesaplarına ancak burada kaydedilen reçeteyle girer.
            </span>
          </span>
        </p>
      )}

      {!receteYok && (
        <HesapDurumu
          hesaplaniyor={hesapla.isPending}
          // Taslak varken hesap hatası alttaki çubukta, Kaydet'in yanında gösterilir.
          hata={hesaplaHatasi && sayi === 0 ? hataMetni(hesaplaHatasi) : null}
          kayit={sayi === 0 ? kayit : null}
        />
      )}

      {yurtdisi && (
        <div
          role="note"
          className="flex items-center gap-2 rounded-lg border border-yellow-300 bg-yellow-50 px-3 py-2 text-sm text-yellow-900 dark:border-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-200"
        >
          <TriangleAlert className="size-4 shrink-0" aria-hidden />
          Yurtdışı yüzde kuralı doğrulanmadı
        </div>
      )}

      {hedefYokHatasi(hesaplaHatasi) && senaryoId !== null && (
        <section aria-label={HEDEF_YOK_METNI} className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{HEDEF_YOK_METNI}.</span> Bu ürünün bu çalışmada üretim bilgisi yok; aşağıya girip
            kaydedin, hesap kendiliğinden gelir.
          </p>
          <UretimBilgileriKarti
            key={`${kod}-${senaryoId}`}
            senaryoId={senaryoId}
            kilitli={yazmaKilitli}
            sabitKod={kod}
            onMesaj={setHedefMesaji}
            onKaydedildi={() => setHesapTetik((t) => t + 1)}
          />
          {hedefMesaji && (
            <p role="status" className="text-sm text-muted-foreground">
              {hedefMesaji} Hesap yeniden koşuyor…
            </p>
          )}
        </section>
      )}

      {parametreEksikHatasi(hesaplaHatasi) && !sonuc && (
        <p role="note" className="rounded-lg border border-dashed bg-card px-3 py-2 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Hesap için parametre değerleri gerekli.</span> Bu çalışmada kur, enflasyon, faiz
          gibi değerler henüz girilmemiş;{" "}
          <Link to={`/parametreler?senaryo=${senaryoId}`} className="text-primary underline-offset-4 hover:underline">
            Parametreler
          </Link>{" "}
          sayfasından girin ya da Yeni çalışma → Geçen sezondan kopyala ile taşıyın.
        </p>
      )}

      {receteHatasi && !hesaplaHatasi && (
        <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {hataMetni(receteHatasi)}
        </div>
      )}

      <div aria-live="polite">
        {bayat && (
          <Badge variant="destructive" data-testid="bayat-rozeti">
            Güncel değil — son geçerli sonuç
          </Badge>
        )}
      </div>

      {receteYok ? (
        <section aria-label="Reçete" className="flex flex-col gap-3">
          <h2 className="text-base font-semibold">Reçete</h2>
          <div role="note" className="rounded-lg border border-dashed bg-card p-4 text-sm">
            <p className="font-medium">{RECETE_YOK_METNI}</p>
            <p className="mt-1 text-muted-foreground">
              Bu ürünün bu çalışmada reçetesi yok; malzeme satırlarını aşağıdan girip kaydedin. Gider kalemleri, toplamlar ve satış fiyatı
              ilk reçeteyle birlikte gelir.
            </p>
          </div>
          <ElleReceteFormu key={`${kod}-${senaryoId}`} urunKodu={kod} gomulu />
        </section>
      ) : (
        <section aria-label="Reçete" className={`flex flex-col gap-3 ${bayatSinif ?? ""}`}>
          <h2 className="text-base font-semibold">Reçete</h2>
          <ReceteTablosu
            satirlar={sonuc?.satirlar}
            recete={receteSatirlari}
            uyarilar={uyarilar}
            yukleniyor={sonuc === null && !duzgunHata}
            hata={sonuc === null && duzgunHata ? hataMetni(duzgunHata) : null}
            taslak={taslak.satirlar}
            onTaslak={onTaslak}
            urunKodu={kod}
          />
        </section>
      )}

      {sonuc && parametreler && (
        <div className={`flex flex-col gap-6 ${bayatSinif ?? ""}`}>
          <GiderKalemleri
            satirlar={sonuc.satirlar}
            toplamlar={sonuc.toplamlar}
            uretim={sonuc.uretim}
            taslak={taslak.giderOranlari}
            sunucuOranlari={sunucu.giderOranlari}
            taslakElle={taslak.giderElle}
            sunucuElle={sunucu.giderElle}
            onTaslak={onTaslak}
          />
          <div className="grid gap-6 lg:grid-cols-2">
            <ToplamlarKarti
              toplamlar={sonuc.toplamlar}
              toplamlarFiresiz={sonuc.toplamlar_firesiz ?? null}
              fiyatlar={sonuc.fiyatlar}
              fiyatlarFiresiz={sonuc.fiyatlar_firesiz ?? null}
              notlar={sonuc.notlar}
              kurlar={sonuc.parametreler?.kurlar ?? null}
            />
            <FinansmanTablosu
              parametreler={parametreler}
              toplamlar={sonuc.toplamlar}
              taslak={taslak.parametreler}
              onParametre={parametreDegis}
              taban={taban ? sunucu.parametreler : undefined}
            />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            {sonuc.uretim && senaryoId !== null && (
              <UretimBilgileri
                key={`${kod}-${senaryoId}`}
                senaryoId={senaryoId}
                senaryoAdi={senaryo ? `${senaryo.sezon_ad} · ${senaryo.ad}` : null}
                hesapTarihi={sonuc.hesap_tarihi}
                uretim={sonuc.uretim}
                taslak={taslak}
                onTaslak={onTaslak}
                taban={taban ? sunucu.parametreler : undefined}
                marka={kayitliMarka}
              />
            )}
            <KurlarBlogu
              parametreler={parametreler}
              taslak={taslak.parametreler}
              onParametre={parametreDegis}
              taban={taban ? sunucu.parametreler : undefined}
            />
          </div>
        </div>
      )}

      {/* Stokta kalan: ürün ekranının taslak/tek Kaydet akışından ayrı, anında kaydedilir; kayıt sonrası hesap yeniden koşar. */}
      {!receteYok && (
        <StokEtkisiKarti
          key={`${kod}-${senaryoId}`}
          kod={kod}
          senaryoId={senaryoId}
          kilitli={yazmaKilitli}
          kilitNedeni={kilitNedeni}
          onDegisti={() => setHesapTetik((t) => t + 1)}
        />
      )}

      {!receteYok && <KarsilastirmaKarti kod={kod} senaryoId={senaryoId} tarih={tarih} />}

      {!receteYok && <TeklifPaneli kod={kod} senaryoId={senaryoId} sonKayitId={kayit?.hesapId ?? null} />}

      {!receteYok && <HesapGecmisi kod={kod} senaryoId={senaryoId} />}

      {sonuc && (
        <Suspense
          fallback={
            <div role="status" className="text-sm text-muted-foreground">
              Grafik yükleniyor…
            </div>
          }
        >
          <div className={bayatSinif}>
            <YuzdeGrafigi satirlar={sonuc.satirlar} />
          </div>
        </Suspense>
      )}

      {/* Yalnız taslakta değişiklik varken görünür; reçete/ne-olur taslağının tek Kaydet'i (Stok etkisi kartı kendi düğmeleriyle kaydeder). */}
      {!receteYok && (
        <DegisiklikCubugu
          satirSayisi={ozet.satirSayisi}
          fireSayisi={ozet.fireSayisi}
          alanSayisi={ozet.alanSayisi}
          kaydediyor={topluKaydet.isPending}
          kaydetKapali={kaydetKapali}
          kaydetNedeni={kaydetNedeni}
          hata={hesaplaHatasi ? hataMetni(hesaplaHatasi) : null}
          onKaydet={kaydetAc}
          onVazgec={() => {
            setTaslak(taslakBos());
            setKayit(null);
          }}
        />
      )}

      <KaydetDiyalogu
        acik={kaydetAcik}
        satirlar={degisiklikler}
        dusenFire={dusenFire}
        gonderiliyor={topluKaydet.isPending}
        hata={sunucuHatasi}
        urunSayisi={urunSayisi}
        onGonder={gonder}
        onKapat={() => !topluKaydet.isPending && setKaydetAcik(false)}
      />
    </div>
  );
}
