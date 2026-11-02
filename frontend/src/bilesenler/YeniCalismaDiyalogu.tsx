import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useForm, type FieldErrors, type UseFormRegister } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { hataMetni } from "@/api/istemci";
import { useSenaryoKopyala, useSenaryoOlustur } from "@/api/sorgular/senaryolar";
import type { KopyalananSayilar, Senaryo, SenaryoKopyaCikis, SenaryoKopyaSecimi } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/bilesenler/ui/tabs";
import { Girdi } from "@/bilesenler/Girdi";
import { senaryoEtiketi, TUR_ADI } from "@/yardimcilar/senaryo";

export type YeniCalismaSekmesi = "bos" | "kopya" | "excel";

const SELECT =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** Backend sezon adını `YYYY-YYYY` ister (422); aynı kural burada da uygulanır ki hata kaydetmeden önce görünsün. */
export const SEZON_BICIMI = /^\d{4}-\d{4}$/;
export const SEZON_BICIM_MESAJI = "Sezon adı YYYY-YYYY biçiminde olmalı (örn. 2027-2028)";

const ortakAlanlar = {
  sezon_ad: z.string().trim().min(1, "Sezon adı zorunlu").regex(SEZON_BICIMI, SEZON_BICIM_MESAJI),
  ad: z.string().trim().min(1, "Çalışma adı zorunlu"),
  tur: z.enum(["fiyat_calismasi", "gerceklesen"]),
  aciklama: z.string().trim(),
};
type OrtakForm = z.infer<z.ZodObject<typeof ortakAlanlar>>;

/** Kopyalanabilen bölümler; sıra ekrandaki sırayla aynıdır, hepsi varsayılan işaretlidir. */
export const KOPYA_BOLUMLERI: {
  anahtar: keyof SenaryoKopyaSecimi;
  etiket: string;
  aciklama: string;
}[] = [
  {
    anahtar: "receteler",
    etiket: "Ürünler ve reçeteler",
    aciklama: "Her ürünün aktif reçetesi yeni çalışmada 1. versiyon olur",
  },
  {
    anahtar: "fiyatlar",
    etiket: "Malzeme fiyatları",
    aciklama: "Bugün geçerli fiyatlar (malzeme başına tek kayıt)",
  },
  {
    anahtar: "parametreler",
    etiket: "Parametreler",
    aciklama: "Kur, enflasyon, faiz, stok süresi, kâr oranları ve metin parametreleri",
  },
  {
    anahtar: "gider",
    etiket: "Gider dağıtımı ve ambalaj sınıfları",
    aciklama: "Havuzlar (taban × çarpanlar, alt kalemler) ve ambalaj sınıfları",
  },
  {
    anahtar: "uretim",
    etiket: "Üretim bilgileri ve kapasite",
    aciklama: "Ürün üretim hedefleri ve hat kapasiteleri",
  },
  {
    anahtar: "fire_kurallari",
    etiket: "Fire kuralları",
    aciklama: "Bugün geçerli fire kuralları",
  },
];

const KOPYALANAN_ETIKETI: {
  anahtar: keyof KopyalananSayilar;
  etiket: string;
}[] = [
  { anahtar: "recete", etiket: "reçete" },
  { anahtar: "fiyat", etiket: "malzeme fiyatı" },
  { anahtar: "parametre", etiket: "parametre" },
  { anahtar: "metin", etiket: "metin parametresi" },
  { anahtar: "havuz", etiket: "gider havuzu" },
  { anahtar: "ambalaj", etiket: "ambalaj sınıfı" },
  { anahtar: "hedef", etiket: "üretim hedefi" },
  { anahtar: "kapasite", etiket: "kapasite kaydı" },
  { anahtar: "fire", etiket: "fire kuralı" },
];

/** "Kopyalandı: 67 reçete, 661 malzeme fiyatı, …" (sıfır olanlar yazılmaz). */
export function kopyaOzeti(k: KopyalananSayilar): string {
  const parcalar = KOPYALANAN_ETIKETI.filter(({ anahtar }) => (k[anahtar] ?? 0) > 0).map(
    ({ anahtar, etiket }) => `${new Intl.NumberFormat("tr-TR").format(k[anahtar])} ${etiket}`,
  );
  return parcalar.length === 0 ? "Kopyalanacak kayıt bulunmadı (kaynak çalışma boş olabilir)." : `Kopyalandı: ${parcalar.join(", ")}.`;
}

function HataSatiri({ mesaj }: { mesaj?: string | null }) {
  return mesaj ? (
    <p role="alert" className="text-sm text-destructive">
      {mesaj}
    </p>
  ) : null;
}

/** Sezon / ad / tür / açıklama — boş ve kopya sekmelerinde ortak. */
function OrtakAlanlar<T extends OrtakForm>({
  id,
  register,
  errors,
}: {
  id: string;
  register: UseFormRegister<T>;
  errors: FieldErrors<OrtakForm>;
}) {
  // Jenerik formda alan adı tipini daraltmak için tek yerde dönüşüm.
  const kayit = register as unknown as UseFormRegister<OrtakForm>;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-sezon`} className="text-sm font-medium">
          Sezon adı
        </label>
        <Girdi id={`${id}-sezon`} placeholder="örn. 2027-2028" aria-invalid={!!errors.sezon_ad} {...kayit("sezon_ad")} />
        <HataSatiri mesaj={errors.sezon_ad?.message} />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-ad`} className="text-sm font-medium">
          Çalışma adı
        </label>
        <Girdi id={`${id}-ad`} placeholder="örn. Fiyat çalışması" aria-invalid={!!errors.ad} {...kayit("ad")} />
        <HataSatiri mesaj={errors.ad?.message} />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-tur`} className="text-sm font-medium">
          Tür
        </label>
        <select id={`${id}-tur`} className={SELECT} {...kayit("tur")}>
          {Object.entries(TUR_ADI).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-aciklama`} className="text-sm font-medium">
          Açıklama <span className="font-normal text-muted-foreground">(isteğe bağlı)</span>
        </label>
        <Girdi id={`${id}-aciklama`} {...kayit("aciklama")} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Boş çalışma */

const bosSemasi = z.object({
  ...ortakAlanlar,
  parametre_al: z.boolean(),
  parametre_kaynak_id: z.string(),
});
type BosForm = z.infer<typeof bosSemasi>;

/** Boş çalışmaya yalnız parametreleri kopyalarken gönderilen seçim: diğer bölümler boş kalır. */
export const YALNIZ_PARAMETRELER: SenaryoKopyaSecimi = {
  receteler: false,
  fiyatlar: false,
  parametreler: true,
  gider: false,
  uretim: false,
  fire_kurallari: false,
};

/** Sekmeler arası geçişte yazılanlar kaybolmasın (B4): sekme içeriği kaldırılınca form değerleri diyalogda saklanır. */
interface TaslakSaklayici<T> {
  taslak?: Partial<T>;
  taslakKaydet?: (t: Partial<T>) => void;
}

function BosSekmesi({
  senaryolar,
  kaynakId,
  onOlusturuldu,
  onKapat,
  taslak,
  taslakKaydet,
}: {
  senaryolar: Senaryo[];
  kaynakId: number | null;
  onOlusturuldu: (id: number) => void;
  onKapat: () => void;
} & TaslakSaklayici<BosForm>) {
  const id = useId();
  const olustur = useSenaryoOlustur();
  const kopyala = useSenaryoKopyala();
  const ilkKaynak = senaryolar.find((s) => s.id === kaynakId) ?? senaryolar[senaryolar.length - 1] ?? null;
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<BosForm>({
    resolver: zodResolver(bosSemasi),
    defaultValues: {
      sezon_ad: "",
      ad: "Fiyat çalışması",
      tur: "fiyat_calismasi",
      aciklama: "",
      parametre_al: false,
      parametre_kaynak_id: ilkKaynak ? String(ilkKaynak.id) : "",
      ...taslak,
    },
  });
  useEffect(() => {
    if (!taslakKaydet) return;
    const abone = watch((v) => taslakKaydet(v as Partial<BosForm>));
    return () => abone.unsubscribe();
  }, [watch, taslakKaydet]);
  const [sezon, ad, tur, parametreAl, kaynakSecim] = watch(["sezon_ad", "ad", "tur", "parametre_al", "parametre_kaynak_id"]);
  const kaynak = senaryolar.find((s) => String(s.id) === kaynakSecim) ?? null;
  const parametreli = parametreAl && kaynak !== null;
  const bitti = {
    onSuccess: (y: { id: number }) => {
      onOlusturuldu(y.id);
      onKapat();
    },
  };
  const bekliyor = olustur.isPending || kopyala.isPending;
  const hata = olustur.error ?? kopyala.error;

  return (
    <form
      noValidate
      aria-label="Boş çalışma"
      className="flex flex-col gap-3"
      onSubmit={handleSubmit((v) => {
        const k = senaryolar.find((s) => String(s.id) === v.parametre_kaynak_id);
        if (v.parametre_al && k) {
          // Kısayol: kopyalama ucu yalnız parametrelerle çağrılır; ürün, fiyat, gider, üretim ve fire boş kalır.
          kopyala.mutate(
            {
              kaynakId: k.id,
              govde: {
                sezon_ad: v.sezon_ad,
                ad: v.ad,
                tur: v.tur,
                aciklama: v.aciklama || null,
                neden: `Boş çalışma; parametreler "${senaryoEtiketi(k)}" çalışmasından alındı`,
                kopyala: YALNIZ_PARAMETRELER,
              },
            },
            bitti,
          );
        } else {
          olustur.mutate(
            {
              sezon_ad: v.sezon_ad,
              ad: v.ad,
              tur: v.tur,
              aciklama: v.aciklama || null,
            },
            bitti,
          );
        }
      })}
    >
      <p className="text-sm text-muted-foreground">
        Hiç verisi olmayan bir çalışma açılır: ürünler, malzeme fiyatları, parametre değerleri ve gider dağıtımı sonradan Veri Girişi,
        Malzeme Fiyatları ve Gider Dağıtım sayfalarından girilir.
      </p>
      <OrtakAlanlar id={id} register={register} errors={errors} />
      {senaryolar.length > 0 && (
        <fieldset className="flex flex-col gap-2 rounded-md border p-3">
          <legend className="px-1 text-sm font-medium">Parametreler</legend>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" {...register("parametre_al")} />
            <span>
              Parametreleri başka bir çalışmadan al
              <span className="block text-xs text-muted-foreground">
                Kur, enflasyon, faiz, stok süresi, kâr oranları ve metin parametreleri gelir; hesap hemen çalışır. Ürünler, fiyatlar ve
                gider boş kalır.
              </span>
            </span>
          </label>
          {parametreAl && (
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-parametre-kaynak`} className="text-sm font-medium">
                Parametre kaynağı
              </label>
              <select id={`${id}-parametre-kaynak`} className={SELECT} {...register("parametre_kaynak_id")}>
                {senaryolar.map((s) => (
                  <option key={s.id} value={s.id}>
                    {senaryoEtiketi(s)}
                  </option>
                ))}
              </select>
            </div>
          )}
        </fieldset>
      )}
      <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
        {sezon.trim() && ad.trim()
          ? parametreli
            ? `Özet: "${sezon.trim()} · ${ad.trim()}" (${TUR_ADI[tur]}) açılacak; parametreler "${senaryoEtiketi(kaynak)}" çalışmasından alınacak, diğer her şey boş.`
            : `Özet: "${sezon.trim()} · ${ad.trim()}" (${TUR_ADI[tur]}) boş bir çalışma olarak açılacak ve seçili çalışma olacak.`
          : "Özet: sezon ve çalışma adını girin."}
      </p>
      <HataSatiri mesaj={hata ? hataMetni(hata) : null} />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onKapat}>
          Vazgeç
        </Button>
        <Button type="submit" disabled={bekliyor}>
          {bekliyor ? "Açılıyor…" : parametreli ? "Parametrelerle aç" : "Boş çalışma aç"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/* ------------------------------------------------------------------ Geçen sezondan kopyala */

const kopyaSemasi = z.object({
  ...ortakAlanlar,
  kaynak_id: z.string().min(1, "Kaynak çalışma seçin"),
  neden: z.string().trim().min(1, "Neden zorunlu"),
  kopyala: z.object({
    receteler: z.boolean(),
    fiyatlar: z.boolean(),
    parametreler: z.boolean(),
    gider: z.boolean(),
    uretim: z.boolean(),
    fire_kurallari: z.boolean(),
  }),
});
type KopyaForm = z.infer<typeof kopyaSemasi>;

function KopyaSekmesi({
  senaryolar,
  kaynakId,
  onOlusturuldu,
  onKapat,
  taslak,
  taslakKaydet,
}: {
  senaryolar: Senaryo[];
  kaynakId: number | null;
  onOlusturuldu: (id: number) => void;
  onKapat: () => void;
} & TaslakSaklayici<KopyaForm>) {
  const id = useId();
  const kopyala = useSenaryoKopyala();
  const [sonuc, setSonuc] = useState<SenaryoKopyaCikis | null>(null);
  const ilkKaynak = useMemo(
    () => senaryolar.find((s) => s.id === kaynakId) ?? senaryolar[senaryolar.length - 1] ?? null,
    [senaryolar, kaynakId],
  );
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<KopyaForm>({
    resolver: zodResolver(kopyaSemasi),
    defaultValues: {
      kaynak_id: ilkKaynak ? String(ilkKaynak.id) : "",
      sezon_ad: "",
      ad: ilkKaynak?.ad ?? "Fiyat çalışması",
      tur: ilkKaynak?.tur ?? "fiyat_calismasi",
      aciklama: "",
      neden: "",
      kopyala: {
        receteler: true,
        fiyatlar: true,
        parametreler: true,
        gider: true,
        uretim: true,
        fire_kurallari: true,
      },
      ...(taslak as Partial<KopyaForm>),
    },
  });
  useEffect(() => {
    if (!taslakKaydet) return;
    const abone = watch((v) => taslakKaydet(v as Partial<KopyaForm>));
    return () => abone.unsubscribe();
  }, [watch, taslakKaydet]);
  const [kaynakSecim, sezon, ad, secim] = watch(["kaynak_id", "sezon_ad", "ad", "kopyala"]);
  const kaynak = senaryolar.find((s) => String(s.id) === kaynakSecim) ?? null;
  const secilen = KOPYA_BOLUMLERI.filter((b) => secim?.[b.anahtar]).length;

  if (senaryolar.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Kopyalanacak bir çalışma yok. Önce &quot;Boş&quot; sekmesinden ya da Excel&apos;den bir çalışma açın.
      </p>
    );
  }

  if (sonuc) {
    return (
      <div className="flex flex-col gap-3">
        <p role="status" className="rounded-md border border-marka/40 bg-accent/60 p-3 text-sm">
          <span className="block font-medium">{kopyaOzeti(sonuc.kopyalanan)}</span>
          <span className="block text-muted-foreground">
            Yeni çalışma seçildi: {senaryoEtiketi(sonuc)}. Şimdi yalnız değişenleri güncelleyin (fiyatlar, parametreler, üretim adetleri).
          </span>
        </p>
        <DialogFooter>
          <Button type="button" onClick={onKapat}>
            Kapat
          </Button>
        </DialogFooter>
      </div>
    );
  }

  return (
    <form
      noValidate
      aria-label="Geçen sezondan kopyala"
      className="flex flex-col gap-3"
      onSubmit={handleSubmit((v) =>
        kopyala.mutate(
          {
            kaynakId: Number(v.kaynak_id),
            govde: {
              sezon_ad: v.sezon_ad,
              ad: v.ad,
              tur: v.tur,
              aciklama: v.aciklama || null,
              neden: v.neden,
              kopyala: v.kopyala,
            },
          },
          {
            onSuccess: (y) => {
              setSonuc(y);
              onOlusturuldu(y.id);
            },
          },
        ),
      )}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-kaynak`} className="text-sm font-medium">
          Kaynak çalışma
        </label>
        <select id={`${id}-kaynak`} className={SELECT} {...register("kaynak_id")}>
          {senaryolar.map((s) => (
            <option key={s.id} value={s.id}>
              {senaryoEtiketi(s)}
              {s.urun_sayisi !== undefined ? ` (${s.urun_sayisi} ürün)` : ""}
            </option>
          ))}
        </select>
        <HataSatiri mesaj={errors.kaynak_id?.message} />
      </div>
      <OrtakAlanlar id={id} register={register} errors={errors} />
      <fieldset className="flex flex-col gap-1.5 rounded-md border p-3">
        <legend className="px-1 text-sm font-medium">Kopyalanacaklar</legend>
        {KOPYA_BOLUMLERI.map((b) => (
          <label key={b.anahtar} className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" {...register(`kopyala.${b.anahtar}`)} />
            <span>
              {b.etiket}
              <span className="block text-xs text-muted-foreground">{b.aciklama}</span>
            </span>
          </label>
        ))}
        <p className="text-xs text-muted-foreground">
          Kayıtlı hesaplar, teklifler ve kilit kopyalanmaz; yeni çalışma açık (kilitsiz) başlar.
        </p>
      </fieldset>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-neden`} className="text-sm font-medium">
          Neden
        </label>
        <Girdi id={`${id}-neden`} placeholder="örn. 2027-2028 sezonu açılışı" aria-invalid={!!errors.neden} {...register("neden")} />
        <HataSatiri mesaj={errors.neden?.message} />
      </div>
      <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
        {kaynak && sezon.trim() && ad.trim()
          ? `Özet: "${kaynak.sezon_ad} · ${kaynak.ad}" çalışmasından ${secilen}/${KOPYA_BOLUMLERI.length} bölüm "${sezon.trim()} · ${ad.trim()}" adıyla yeni çalışmaya kopyalanacak.`
          : "Özet: kaynak çalışmayı, yeni sezon ve çalışma adını girin."}
      </p>
      <HataSatiri mesaj={kopyala.error ? hataMetni(kopyala.error) : null} />
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onKapat}>
          Vazgeç
        </Button>
        <Button type="submit" disabled={kopyala.isPending || secilen === 0}>
          {kopyala.isPending ? "Kopyalanıyor…" : "Kopyala ve aç"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/* ------------------------------------------------------------------ Diyalog */

interface Props {
  /** Açılışta seçili sekme. */
  sekme?: YeniCalismaSekmesi;
  senaryolar: Senaryo[];
  /** Şu an seçili çalışma: kopya sekmesinde varsayılan kaynak, Excel bağlantısında `?senaryo=`. */
  seciliId: number | null;
  onKapat: () => void;
  /** Yeni çalışma oluşunca (liste tazelendikten sonra) çağrılır; çağıran seçimi buna çevirir. */
  onOlusturuldu: (id: number) => void;
}

/** "Yeni çalışma": Boş / Geçen sezondan kopyala / Excel'den — üç yol tek diyalogda. */
export function YeniCalismaDiyalogu({ sekme = "bos", senaryolar, seciliId, onKapat, onOlusturuldu }: Props) {
  const [aktif, setAktif] = useState<YeniCalismaSekmesi>(sekme);
  // Sekme içerikleri değişince kaldırılır; yazılanlar burada saklanır ve sekmeye dönünce geri yüklenir.
  const taslaklar = useRef<{ bos?: Partial<BosForm>; kopya?: Partial<KopyaForm> }>({});
  const bosKaydet = useMemo(() => (t: Partial<BosForm>) => (taslaklar.current.bos = t), []);
  const kopyaKaydet = useMemo(() => (t: Partial<KopyaForm>) => (taslaklar.current.kopya = t), []);
  const excelYolu = seciliId === null ? "/recete-aktar" : `/recete-aktar?senaryo=${seciliId}`;
  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Yeni çalışma</DialogTitle>
          <DialogDescription>
            Yeni sezon ya da yeni bir fiyat çalışması: boş açın, geçen sezondan kopyalayın ya da Excel yükleyin.
          </DialogDescription>
        </DialogHeader>
        <Tabs value={aktif} onValueChange={(v) => setAktif(v as YeniCalismaSekmesi)}>
          <TabsList aria-label="Yeni çalışma yolu" className="w-full">
            <TabsTrigger value="bos">Boş</TabsTrigger>
            <TabsTrigger value="kopya">Geçen sezondan kopyala</TabsTrigger>
            <TabsTrigger value="excel">Excel&apos;den</TabsTrigger>
          </TabsList>
          <TabsContent value="bos" className="pt-3">
            <BosSekmesi
              senaryolar={senaryolar}
              kaynakId={seciliId}
              onOlusturuldu={onOlusturuldu}
              onKapat={onKapat}
              taslak={taslaklar.current.bos}
              taslakKaydet={bosKaydet}
            />
          </TabsContent>
          <TabsContent value="kopya" className="pt-3">
            <KopyaSekmesi
              senaryolar={senaryolar}
              kaynakId={seciliId}
              onOlusturuldu={onOlusturuldu}
              onKapat={onKapat}
              taslak={taslaklar.current.kopya}
              taslakKaydet={kopyaKaydet}
            />
          </TabsContent>
          <TabsContent value="excel" className="flex flex-col gap-3 pt-3">
            <p className="text-sm text-muted-foreground">
              Excel çalışma kitabının tamamı (ürün sayfaları, S.ALMA BF, Gider Dağıtım, Üretim Adetleri) yeni bir çalışma olarak içe
              aktarılır; yaklaşık 1 dakika sürer.
            </p>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onKapat}>
                Vazgeç
              </Button>
              <Link
                to={excelYolu}
                onClick={onKapat}
                className="inline-flex h-8 items-center justify-center rounded-lg bg-primary px-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/80"
              >
                Veri Aktar → Tüm çalışma kitabı
              </Link>
            </DialogFooter>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
