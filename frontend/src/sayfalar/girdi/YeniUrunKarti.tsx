import { useId, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { PackagePlus } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useGiderHavuzlari } from "@/api/sorgular/gider";
import { useUrunOlustur } from "@/api/sorgular/urunler";
import { Button } from "@/bilesenler/ui/button";
import { Girdi } from "@/bilesenler/Girdi";
import { sayiApi } from "@/yardimcilar/sayi";
import { hatListesi, PAZARLAR, SINIFLAR } from "@/yardimcilar/urunKarti";
import { sayiKurali, sayiPozitif } from "../ayarlar/ortak";
import { Alan, Kart, SELECT } from "./ortak";

const sema = z.object({
  kod: z
    .string()
    .trim()
    .min(1, "Ürün kodu zorunlu")
    .refine((k) => !/[\s/?#]/.test(k), "Kod boşluk ya da / ? # içeremez"),
  ad: z.string().trim().min(1, "Ürün adı zorunlu"),
  ambalaj_hacmi: z
    .string()
    .trim()
    .min(1, "Ambalaj hacmi zorunlu")
    .superRefine(sayiKurali())
    .refine((v) => sayiPozitif(v), "Ambalaj hacmi 0'dan büyük olmalı"),
  hat: z.string().trim().min(1, "Hat zorunlu"),
  taze_tursu_sinifi: z.string().trim().min(1, "Sınıf zorunlu"),
  suzme_kg: z.string().trim().min(1, "Süzme kg zorunlu").superRefine(sayiKurali()),
  pazar: z.enum(PAZARLAR),
  marka: z.string().trim(),
});
type Form = z.infer<typeof sema>;

const BOS: Form = {
  kod: "",
  ad: "",
  ambalaj_hacmi: "",
  hat: "",
  taze_tursu_sinifi: SINIFLAR[1],
  suzme_kg: "",
  pazar: "Yurtiçi",
  marka: "",
};

/**
 * Yeni ürün kartı (Faz 5c): kart `PUT /urunler/{kod}` ile açılır (kod tekilliği önce denetlenir); ürün, reçetesi
 * kaydedilince çalışmaya dahil olur — bu yüzden başarıda "Reçeteyi kur" bağlantısı ürün ekranına götürür.
 */
export function YeniUrunKarti({
  senaryoId,
  kilitli = false,
  onMesaj,
}: {
  senaryoId: number;
  /** Düzenleme kilidi kapalı: kart kaydedilemez (ürün kartı senaryodan bağımsızdır; senaryo kilidi etkilemez). */
  kilitli?: boolean;
  onMesaj: (m: string) => void;
}) {
  const id = useId();
  const havuzlar = useGiderHavuzlari(senaryoId);
  const hatlar = useMemo(() => hatListesi(havuzlar.data?.kayitlar), [havuzlar.data]);
  const olustur = useUrunOlustur();
  const [acilan, setAcilan] = useState<{ kod: string; ad: string } | null>(null);
  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(sema), defaultValues: BOS });
  const [kod, ad] = watch(["kod", "ad"]);

  function gonder(v: Form) {
    setAcilan(null);
    olustur.mutate(
      {
        kod: v.kod,
        govde: {
          ad: v.ad,
          ambalaj_hacmi: sayiApi(v.ambalaj_hacmi) ?? v.ambalaj_hacmi,
          hat: v.hat,
          taze_tursu_sinifi: v.taze_tursu_sinifi,
          suzme_kg: sayiApi(v.suzme_kg) ?? v.suzme_kg,
          pazar: v.pazar,
          // Boş bırakılırsa sunucu marka bilgisini ürün adından türetir.
          marka: v.marka.trim() || null,
        },
      },
      {
        onSuccess: (y) => {
          setAcilan({ kod: y.kod, ad: y.ad });
          onMesaj(`${y.kod} ürün kartı açıldı; reçetesi kaydedilince çalışmaya dahil olur.`);
          reset(BOS);
        },
      },
    );
  }

  return (
    <Kart
      baslik="Yeni ürün"
      aciklama="Ürün kartını açın, sonra ürün ekranında reçetesini kurun. Ürün, reçetesi kaydedilince bu çalışmaya dahil olur ve hesabı gelir."
      simge={<PackagePlus />}
    >
      <form noValidate className="flex flex-col gap-3" aria-label="Yeni ürün" onSubmit={handleSubmit(gonder)}>
        <div className="grid grid-cols-2 gap-3">
          <Alan etiket="Ürün kodu" htmlFor={`${id}-kod`} hata={errors.kod?.message}>
            <Girdi
              id={`${id}-kod`}
              placeholder="ERP ürün kodu (yoksa geçici bir kod, örn. YENI-2027-01)"
              aria-invalid={!!errors.kod}
              {...register("kod")}
            />
          </Alan>
          <Alan etiket="Ürün adı" htmlFor={`${id}-ad`} hata={errors.ad?.message}>
            <Girdi id={`${id}-ad`} placeholder="örn. Kornişon 720 ml" aria-invalid={!!errors.ad} {...register("ad")} />
          </Alan>
          <Alan etiket="Ambalaj hacmi (ml)" htmlFor={`${id}-hacim`} hata={errors.ambalaj_hacmi?.message}>
            <Girdi
              id={`${id}-hacim`}
              inputMode="decimal"
              className="text-right tabular-nums"
              aria-invalid={!!errors.ambalaj_hacmi}
              {...register("ambalaj_hacmi")}
            />
          </Alan>
          <Alan etiket="Süzme miktar (kg)" htmlFor={`${id}-suzme`} hata={errors.suzme_kg?.message}>
            <Girdi
              id={`${id}-suzme`}
              inputMode="decimal"
              className="text-right tabular-nums"
              aria-invalid={!!errors.suzme_kg}
              {...register("suzme_kg")}
            />
          </Alan>
          <Alan etiket="Hat" htmlFor={`${id}-hat`} hata={errors.hat?.message}>
            <Girdi
              id={`${id}-hat`}
              list={`${id}-hatlar`}
              placeholder={hatlar.length ? "Listeden seçin ya da yazın" : "örn. Cam Hattı"}
              aria-invalid={!!errors.hat}
              {...register("hat")}
            />
            <datalist id={`${id}-hatlar`}>
              {hatlar.map((h) => (
                <option key={h} value={h} />
              ))}
            </datalist>
          </Alan>
          <Alan etiket="Taze/Turşu sınıfı" htmlFor={`${id}-sinif`} hata={errors.taze_tursu_sinifi?.message}>
            <select id={`${id}-sinif`} className={SELECT} {...register("taze_tursu_sinifi")}>
              {SINIFLAR.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Alan>
          <Alan etiket="Marka" htmlFor={`${id}-marka`} hata={errors.marka?.message}>
            <Girdi
              id={`${id}-marka`}
              placeholder="Boş bırakılırsa addan türetilir (ör. Berrak)"
              title="Liste fiyatı yalnız Berrak ürünlerinde hesaplanır."
              {...register("marka")}
            />
          </Alan>
          <Alan etiket="Pazar" htmlFor={`${id}-pazar`} hata={errors.pazar?.message}>
            <select id={`${id}-pazar`} className={SELECT} {...register("pazar")}>
              {PAZARLAR.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </Alan>
        </div>
        {hatlar.length === 0 && !havuzlar.isPending && (
          <p className="text-xs text-muted-foreground">Bu çalışmada hat bazlı gider havuzu yok; hat adını elle yazın.</p>
        )}
        <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
          {kod.trim() && ad.trim()
            ? `Özet: "${kod.trim()}" kodlu "${ad.trim()}" kartı açılacak; reçetesi ürün ekranında girilecek.`
            : "Özet: ürün kodu ve adını girin."}
        </p>
        {olustur.error && (
          <p role="alert" className="text-sm text-destructive">
            {hataMetni(olustur.error)}
          </p>
        )}
        {acilan && (
          <p role="status" className="rounded-md border border-marka/40 bg-accent/60 p-2 text-sm">
            {`${acilan.kod} · ${acilan.ad} kaydedildi. `}
            <Link
              to={`/urunler/${encodeURIComponent(acilan.kod)}?senaryo=${senaryoId}`}
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              Reçeteyi kur
            </Link>
          </p>
        )}
        <div>
          <Button type="submit" size="sm" disabled={olustur.isPending || kilitli} title={kilitli ? "Düzenleme kilitli" : undefined}>
            {olustur.isPending ? "Kaydediliyor…" : "Ürünü kaydet"}
          </Button>
        </div>
      </form>
    </Kart>
  );
}
