import { useEffect, useId, useMemo, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type Decimal from "decimal.js";
import type { GiderHavuzu, Sema } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { cn } from "@/lib/utils";
import { D, paraBicimle, topla, yuzdeBicimle } from "@/yardimcilar/para";
import { Girdi } from "@/bilesenler/Girdi";
import { sayiApi, sayiGecerli, sayiHatasi, sayiKurali, sayiPozitif } from "./ortak";

const sayi = () => z.string().trim().superRefine(sayiKurali());
const sayiD = (s: string) => D(s.trim().replace(",", "."));

const sema = z
  .object({
    ad: z.string().trim().min(1, "Ad zorunlu"),
    neden: z.string().trim().min(1, "Neden zorunlu"),
    /** Boş: toplam doğrudan girilir. Dolu: toplam = taban × Π çarpan. */
    taban_tutar: z.string().trim(),
    carpanlar: z.array(z.object({ ad: z.string().trim(), deger: z.string().trim() })),
    toplam_tutar: z.string().trim(),
    baz_tipi: z.enum(["saniye", "kg", "adet"]),
    baz_miktar: z.string().trim().superRefine((s, ctx) => (s === "" ? undefined : sayiKurali()(s, ctx))),
    mod: z.enum(["tutar", "yuzde"]),
    anahtarlar: z.array(
      z.object({
        alt_kalem: z.string().trim().min(1, "Alt kalem zorunlu"),
        pay: z.string().trim(),
        tutar: z.string().trim(),
        baz_miktar: sayi(),
        /** Kayıttaki özgün pay (0-1); yeni satırda "". Tutar modunda dokunulmayan satır bu payla gider. */
        ozgun_pay: z.string(),
      }),
    ),
  })
  .superRefine((v, ctx) => {
    if (v.taban_tutar !== "") {
      const m = sayiHatasi(v.taban_tutar);
      if (m) ctx.addIssue({ code: "custom", path: ["taban_tutar"], message: m });
      v.carpanlar.forEach((c, i) => {
        if (!sayiPozitif(c.deger)) ctx.addIssue({ code: "custom", path: ["carpanlar", i, "deger"], message: "Çarpan 0'dan büyük olmalı" });
      });
    } else {
      const m = sayiHatasi(v.toplam_tutar);
      if (m) ctx.addIssue({ code: "custom", path: ["toplam_tutar"], message: m });
    }
    const alan = v.mod === "tutar" ? "tutar" : "pay";
    v.anahtarlar.forEach((a, i) => {
      const m = sayiHatasi(a[alan]);
      if (m) ctx.addIssue({ code: "custom", path: ["anahtarlar", i, alan], message: m });
    });
  });
type Form = z.infer<typeof sema>;

export interface HavuzGirdisi {
  ad: string;
  neden: string;
  /** Taban kullanılmıyorsa doğrudan girilen toplam; taban varsa null (sunucu hesaplar). */
  toplam_tutar: string | null;
  taban_tutar: string | null;
  carpanlar: { ad: string; deger: string }[];
  baz_tipi: "saniye" | "kg" | "adet";
  baz_miktar: string | null;
  /** Her alt kalem ya `pay_orani` (0-1) ya `tutar` (TL) taşır. */
  anahtarlar: { alt_kalem: string; pay_orani?: string; tutar?: string; baz_miktar: string }[];
}

/** Diyalog çıktısını API gövdesine çevirir (taban varsa toplam gönderilmez; yoksa taban/çarpan gönderilmez). */
export function havuzGovdesi(v: HavuzGirdisi): Sema["HavuzGiris"] {
  return {
    ad: v.ad,
    neden: v.neden,
    baz_tipi: v.baz_tipi,
    baz_miktar: v.baz_miktar,
    anahtarlar: v.anahtarlar,
    ...(v.taban_tutar !== null ? { taban_tutar: v.taban_tutar, carpanlar: v.carpanlar } : { toplam_tutar: v.toplam_tutar ?? "" }),
  };
}

/** Form içindeki pay yüzdeleri toplamı (yüzde puanı olarak; 100 = tam). */
export function payToplamiYuzde(paylar: (string | undefined)[]) {
  return topla(paylar.filter((p): p is string => !!p && sayiGecerli(p)).map((p) => p.replace(",", ".")));
}

/** Taban × Π çarpan; taban ya da bir çarpan geçersizse null. */
export function giderToplamiHesapla(taban: string, carpanlar: { deger: string }[]): Decimal | null {
  if (!sayiGecerli(taban)) return null;
  let t = sayiD(taban);
  for (const c of carpanlar) {
    if (!sayiGecerli(c.deger)) return null;
    t = t.times(sayiD(c.deger));
  }
  return t;
}

interface Props {
  havuz: GiderHavuzu;
  gonderiliyor: boolean;
  hata: string | null;
  onGonder: (v: HavuzGirdisi) => void;
  onKapat: () => void;
}

const SELECT =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";
const BAZ_ETIKETI = { saniye: "Çalışılan saniye", kg: "Kg", adet: "Adet" } as const;

/** Tutar girişi için ön değer: havuz toplamı × pay, kuruşa yuvarlı (görünüm); dokunulmazsa özgün pay gönderilir. */
const payDanTutar = (toplam: string, pay: string) => D(toplam).times(D(pay)).toDecimalPlaces(2).toFixed();

/**
 * Havuz düzenleme: "Taban tutar × çarpanlar = Gider Toplamı" (taban boşsa toplam doğrudan), alt kalemler tutarla (varsayılan, pay %
 * otomatik) ya da yüzdeyle girilir; pay toplamı canlı hesaplanır, %100 değilse kaydetmeden önce onay istenir.
 */
export function HavuzDiyalogu({ havuz, gonderiliyor, hata, onGonder, onKapat }: Props) {
  const id = useId();
  const varsayilan = useMemo<Form>(
    () => ({
      ad: havuz.ad,
      neden: "",
      taban_tutar: havuz.taban_tutar ?? "",
      carpanlar: havuz.carpanlar.map((c) => ({ ad: c.ad, deger: c.deger })),
      toplam_tutar: havuz.toplam_tutar,
      baz_tipi: havuz.baz_tipi,
      baz_miktar: havuz.baz_miktar ?? "",
      mod: "tutar",
      anahtarlar: havuz.anahtarlar.map((a) => ({
        alt_kalem: a.alt_kalem,
        pay: D(a.pay_orani).times(100).toFixed(),
        tutar: payDanTutar(havuz.toplam_tutar, a.pay_orani),
        baz_miktar: a.baz_miktar,
        ozgun_pay: a.pay_orani,
      })),
    }),
    [havuz],
  );
  const {
    register,
    control,
    handleSubmit,
    watch,
    getValues,
    setValue,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(sema), defaultValues: varsayilan });
  const { fields, append, remove } = useFieldArray({ control, name: "anahtarlar" });
  const carpanAlani = useFieldArray({ control, name: "carpanlar" });

  const [payOnayi, setPayOnayi] = useState<HavuzGirdisi | null>(null);
  const anahtarlar = watch("anahtarlar") ?? [];
  const carpanlar = watch("carpanlar") ?? [];
  const taban = watch("taban_tutar") ?? "";
  const toplamTutar = watch("toplam_tutar") ?? "";
  const bazMiktar = watch("baz_miktar") ?? "";
  const bazTipi = watch("baz_tipi");
  const mod = watch("mod");
  const tabanModu = taban.trim() !== "";

  const giderToplami = tabanModu ? giderToplamiHesapla(taban, carpanlar) : sayiGecerli(toplamTutar) ? sayiD(toplamTutar) : null;
  const bolunebilir = giderToplami !== null && giderToplami.gt(0);
  /** Satırın yüzde payı (yüzde puanı); tutar modunda tutar / toplam. */
  const satirPayi = (a: Form["anahtarlar"][number]): Decimal | null => {
    if (mod === "yuzde") return sayiGecerli(a.pay) ? sayiD(a.pay) : null;
    return bolunebilir && sayiGecerli(a.tutar) ? sayiD(a.tutar).div(giderToplami).times(100) : null;
  };
  const payToplam =
    mod === "yuzde"
      ? payToplamiYuzde(anahtarlar.map((a) => a.pay))
      : topla(anahtarlar.map((a) => satirPayi(a) ?? "0"));
  const tamMi = anahtarlar.length === 0 || payToplam.minus(100).abs().lt("0.05");
  const birimOran = giderToplami && sayiGecerli(bazMiktar) && sayiD(bazMiktar).gt(0) ? giderToplami.div(sayiD(bazMiktar)) : null;

  // Kullanıcının tutar ya da pay alanına elle dokunduğu satırlar (useFieldArray kimliğiyle; silme/sıralamadan etkilenmez).
  // RHF dirtyFields kullanılmaz: çarpan ekleme gibi dizi işlemleri tüm formu varsayılanla kıyaslayıp türetilmiş tutarları "kirli" sayar.
  const [elle, setElle] = useState<Set<string>>(() => new Set());
  const elleIsaretle = (kimlik: string) => setElle((e) => (e.has(kimlik) ? e : new Set(e).add(kimlik)));
  /** Tutar modunda kullanıcının elle değiştirmediği, kayıttan gelen satır: payı korunur, tutarı toplamdan türetilir. */
  const dokunulmamis = (kimlik: string | undefined, a: Form["anahtarlar"][number]) => a.ozgun_pay !== "" && !!kimlik && !elle.has(kimlik);

  // Gider Toplamı değişince (taban/çarpan/toplam) dokunulmamış satırların TL tutarı yeni toplama göre yenilenir;
  // böylece yalnız bir satırı düzenleyen kullanıcı diğerlerini %100 dışına düşürmez.
  const toplamMetni = giderToplami?.toFixed() ?? null;
  useEffect(() => {
    if (toplamMetni === null) return;
    getValues("anahtarlar").forEach((a, i) => {
      if (dokunulmamis(fields[i]?.id, a)) setValue(`anahtarlar.${i}.tutar`, payDanTutar(toplamMetni, a.ozgun_pay));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- yalnız toplam değişince
  }, [toplamMetni]);

  function modDegistir(yeni: Form["mod"]) {
    if (yeni === mod) return;
    getValues("anahtarlar").forEach((a, i) => {
      if (yeni === "yuzde") {
        if (bolunebilir && sayiGecerli(a.tutar))
          setValue(`anahtarlar.${i}.pay`, sayiD(a.tutar).div(giderToplami).times(100).toDecimalPlaces(6).toFixed());
      } else if (giderToplami && sayiGecerli(a.pay)) {
        // Yüzdeyle düzenlenen satır `elle` kümesindedir: tutar moduna dönünce tutarla gider, düzenleme kaybolmaz.
        setValue(`anahtarlar.${i}.tutar`, sayiD(a.pay).div(100).times(giderToplami).toDecimalPlaces(2).toFixed());
      }
    });
    setValue("mod", yeni);
  }

  function girdiYap(v: Form): HavuzGirdisi {
    return {
      ad: v.ad.trim(),
      neden: v.neden.trim(),
      toplam_tutar: tabanModu ? null : sayiApi(v.toplam_tutar) ?? "",
      taban_tutar: tabanModu ? sayiApi(v.taban_tutar) ?? "" : null,
      carpanlar: tabanModu ? v.carpanlar.map((c) => ({ ad: c.ad.trim(), deger: sayiApi(c.deger) ?? "" })) : [],
      baz_tipi: v.baz_tipi,
      baz_miktar: v.baz_miktar.trim() === "" ? null : sayiApi(v.baz_miktar) ?? "",
      anahtarlar: v.anahtarlar.map((a) => {
        const alt_kalem = a.alt_kalem.trim();
        const baz_miktar = sayiApi(a.baz_miktar) ?? "";
        if (v.mod === "yuzde") return { alt_kalem, pay_orani: D(sayiApi(a.pay) ?? "").div(100).toFixed(), baz_miktar };
        // Tutar modunda dokunulmamış satır: kuruşa yuvarlı görünümden değil, özgün paydan gider (kayma olmasın).
        if (dokunulmamis(fields[v.anahtarlar.indexOf(a)]?.id, a)) return { alt_kalem, pay_orani: a.ozgun_pay, baz_miktar };
        return { alt_kalem, tutar: sayiApi(a.tutar) ?? "", baz_miktar };
      }),
    };
  }

  const hataMetni = (m?: string) => m && <p role="alert" className="text-sm text-destructive">{m}</p>;
  const carpanHatasi = Array.isArray(errors.carpanlar) ? errors.carpanlar.find((c) => c?.deger)?.deger?.message : undefined;

  return (
    <>
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      {/* Çok alt kalemli havuzlarda içerik ekranı aşar: diyalog kendi içinde kayar, Kaydet her zaman erişilebilir kalır. */}
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Havuzu düzenle: {havuz.kod}</DialogTitle>
          <DialogDescription>
            Gider Toplamı taban × çarpanlardan hesaplanır (taban boşsa doğrudan girilir). Alt kalemler tutarla ya da yüzdeyle girilir;
            pay toplamı %100 olmalıdır.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          noValidate
          onSubmit={handleSubmit((v) => {
            const girdi = girdiYap(v);
            // Pay toplamı %100 değilse havuz tutarı eksik/fazla dağıtılır: önce onay istenir.
            if (tamMi) onGonder(girdi);
            else setPayOnayi(girdi);
          })}
        >
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-ad`} className="text-sm font-medium">
                Havuz adı
              </label>
              <Girdi id={`${id}-ad`} {...register("ad")} />
              {hataMetni(errors.ad?.message)}
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-baz`} className="text-sm font-medium">
                Baz tipi
              </label>
              <select id={`${id}-baz`} className={SELECT} {...register("baz_tipi")}>
                <option value="saniye">saniye</option>
                <option value="kg">kg</option>
                <option value="adet">adet</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-bazm`} className="text-sm font-medium">
                Baz miktar <span className="font-normal text-muted-foreground">({BAZ_ETIKETI[bazTipi]})</span>
              </label>
              <Girdi id={`${id}-bazm`} inputMode="decimal" {...register("baz_miktar")} />
              {hataMetni(errors.baz_miktar?.message)}
            </div>
          </div>

          <fieldset className="flex flex-col gap-2 rounded-md border p-3">
            <legend className="px-1 text-sm font-medium">Gider Toplamı</legend>
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex w-44 flex-col gap-1">
                <label htmlFor={`${id}-taban`} className="text-xs text-muted-foreground">
                  Taban tutar (TL)
                </label>
                <Girdi id={`${id}-taban`} inputMode="decimal" placeholder="boş: toplamı gir" aria-invalid={!!errors.taban_tutar} {...register("taban_tutar")} />
              </div>
              {carpanAlani.fields.map((f, i) => (
                <div key={f.id} className="flex items-end gap-1">
                  <span className="pb-1.5 text-sm text-muted-foreground" aria-hidden>
                    ×
                  </span>
                  <div className="flex w-28 flex-col gap-1">
                    <label htmlFor={`${id}-cad-${i}`} className="text-xs text-muted-foreground">
                      Çarpan adı {i + 1}
                    </label>
                    <Girdi id={`${id}-cad-${i}`} placeholder="örn. SGK" {...register(`carpanlar.${i}.ad`)} />
                  </div>
                  <div className="flex w-20 flex-col gap-1">
                    <label htmlFor={`${id}-cdeger-${i}`} className="text-xs text-muted-foreground">
                      Çarpan {i + 1}
                    </label>
                    <Girdi
                      id={`${id}-cdeger-${i}`}
                      inputMode="decimal"
                      placeholder="1,35"
                      aria-invalid={!!errors.carpanlar?.[i]?.deger}
                      {...register(`carpanlar.${i}.deger`)}
                    />
                  </div>
                  <Button type="button" variant="ghost" size="sm" aria-label={`Çarpanı sil ${i + 1}`} onClick={() => carpanAlani.remove(i)}>
                    Sil
                  </Button>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" onClick={() => carpanAlani.append({ ad: "", deger: "" })}>
                Çarpan ekle
              </Button>
              <span className="pb-1.5 text-sm text-muted-foreground" aria-hidden>
                =
              </span>
              {tabanModu ? (
                <output data-testid="form-gider-toplami" aria-label="Gider Toplamı" className="pb-1 text-base font-semibold tabular-nums">
                  {giderToplami ? paraBicimle(giderToplami, "TL", 2) : "—"}
                </output>
              ) : (
                <div className="flex w-48 flex-col gap-1">
                  <label htmlFor={`${id}-tutar`} className="text-xs text-muted-foreground">
                    Toplam tutar (TL)
                  </label>
                  <Girdi id={`${id}-tutar`} inputMode="decimal" aria-invalid={!!errors.toplam_tutar} {...register("toplam_tutar")} />
                </div>
              )}
            </div>
            {hataMetni(errors.taban_tutar?.message ?? errors.toplam_tutar?.message ?? carpanHatasi)}
            {!tabanModu && carpanlar.length > 0 && (
              <p className="text-xs text-muted-foreground">Çarpanlar yalnız taban tutar doluyken uygulanır.</p>
            )}
          </fieldset>

          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-neden`} className="text-sm font-medium">
              Neden
            </label>
            <Girdi id={`${id}-neden`} placeholder="Değişiklik nedeni" {...register("neden")} />
            {hataMetni(errors.neden?.message)}
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-medium">Alt kalemler</legend>
            <div className="flex flex-wrap items-center justify-end gap-2">
              <div role="radiogroup" aria-label="Giriş biçimi" className="inline-flex rounded-lg bg-muted p-0.5 text-xs">
                {(["tutar", "yuzde"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    role="radio"
                    aria-checked={mod === m}
                    disabled={!bolunebilir}
                    title={bolunebilir ? undefined : "Giriş biçimi değiştirmek için geçerli bir Gider Toplamı gerekir"}
                    onClick={() => modDegistir(m)}
                    className={cn("rounded-md px-2.5 py-1", mod === m ? "bg-background font-medium shadow-sm" : "text-muted-foreground")}
                  >
                    {m === "tutar" ? "Tutarla" : "Yüzdeyle"}
                  </button>
                ))}
              </div>
            </div>
            {fields.length > 0 && (
              <div className="grid grid-cols-[1fr_7rem_5rem_6rem_auto] gap-2 px-0.5 text-xs text-muted-foreground" aria-hidden>
                <span>Alt kalem</span>
                <span>{mod === "tutar" ? "Tutar (TL)" : "Pay (%)"}</span>
                <span className="text-right">Gider %</span>
                <span>{BAZ_ETIKETI[bazTipi]}</span>
                <span />
              </div>
            )}
            {fields.map((f, i) => {
              const e = errors.anahtarlar?.[i];
              const pay = anahtarlar[i] ? satirPayi(anahtarlar[i]) : null;
              const tutarKaydi = register(`anahtarlar.${i}.tutar`);
              const payKaydi = register(`anahtarlar.${i}.pay`);
              return (
                <div key={f.id} className="grid grid-cols-[1fr_7rem_5rem_6rem_auto] items-center gap-2">
                  <Girdi aria-label={`Alt kalem ${i + 1}`} aria-invalid={!!e?.alt_kalem} {...register(`anahtarlar.${i}.alt_kalem`)} />
                  {mod === "tutar" ? (
                    <Girdi
                      aria-label={`Tutar (TL) ${i + 1}`}
                      inputMode="decimal"
                      aria-invalid={!!e?.tutar}
                      {...tutarKaydi}
                      onChange={(ev) => {
                        elleIsaretle(f.id);
                        void tutarKaydi.onChange(ev);
                      }}
                    />
                  ) : (
                    <Girdi
                      aria-label={`Pay (%) ${i + 1}`}
                      inputMode="decimal"
                      aria-invalid={!!e?.pay}
                      {...payKaydi}
                      onChange={(ev) => {
                        elleIsaretle(f.id);
                        void payKaydi.onChange(ev);
                      }}
                    />
                  )}
                  <span data-testid={`form-pay-${i + 1}`} className="text-right text-sm tabular-nums text-muted-foreground">
                    {pay ? yuzdeBicimle(pay.div(100), 1) : "—"}
                  </span>
                  <Girdi aria-label={`Baz miktar ${i + 1}`} inputMode="decimal" aria-invalid={!!e?.baz_miktar} {...register(`anahtarlar.${i}.baz_miktar`)} />
                  <Button type="button" variant="ghost" size="sm" aria-label={`Alt kalemi sil ${i + 1}`} onClick={() => remove(i)}>
                    Sil
                  </Button>
                  {(e?.alt_kalem || e?.pay || e?.tutar || e?.baz_miktar) && (
                    <p role="alert" className="col-span-5 text-sm text-destructive">
                      {e?.alt_kalem?.message ?? e?.tutar?.message ?? e?.pay?.message ?? e?.baz_miktar?.message}
                    </p>
                  )}
                </div>
              );
            })}
            <div>
              <Button type="button" variant="outline" size="sm" onClick={() => append({ alt_kalem: "", pay: "", tutar: "", baz_miktar: "1", ozgun_pay: "" })}>
                Alt kalem ekle
              </Button>
            </div>
            <p className="text-sm">
              Pay toplamı:{" "}
              <strong data-testid="form-pay-toplam" className={cn("tabular-nums", tamMi ? "text-foreground" : "text-red-600 dark:text-red-400")}>
                {yuzdeBicimle(payToplam.div(100), 1)}
              </strong>
              {!tamMi && <span className="text-red-600 dark:text-red-400"> (%100 olmalı)</span>}
            </p>
          </fieldset>

          <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
            Özet: {havuz.kod} havuzu {giderToplami ? paraBicimle(giderToplami, "TL", 2) : "—"}
            {tabanModu && giderToplami ? ` (taban × ${carpanlar.length} çarpan)` : ""}
            {birimOran ? `, birim oran ${paraBicimle(birimOran, "TL", 4)} / ${bazTipi}` : ""}, pay toplamı {yuzdeBicimle(payToplam.div(100), 1)}.
          </p>
          {hataMetni(hata ?? undefined)}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onKapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={gonderiliyor}>
              {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
    {payOnayi && (
      <OnayDiyalogu
        baslik="Pay toplamı %100 değil"
        onayMetni="Yine de kaydet"
        bekliyor={gonderiliyor}
        onOnayla={() => {
          onGonder(payOnayi);
          setPayOnayi(null);
        }}
        onVazgec={() => setPayOnayi(null)}
      >
        <p>{`Alt kalem paylarının toplamı ${yuzdeBicimle(payToplam.div(100), 1)}; havuz tutarı tam dağıtılmayacak. Yine de kaydedilsin mi?`}</p>
      </OnayDiyalogu>
    )}
    </>
  );
}
