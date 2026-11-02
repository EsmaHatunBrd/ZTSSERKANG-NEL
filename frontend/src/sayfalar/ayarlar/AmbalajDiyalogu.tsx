import { useId, useMemo } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { Ambalaj, AmbalajKaydiGiris } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Girdi } from "@/bilesenler/Girdi";
import { sayiApi, sayiHatasi, sayiKurali, sayiPozitif } from "./ortak";

const sayi = z.string().trim().superRefine(sayiKurali());
const pozitif = z.string().trim().superRefine((x, ctx) => {
  const m = sayiHatasi(x);
  if (m === "Sayı olmalı") ctx.addIssue({ code: "custom", message: m });
  else if (!sayiPozitif(x)) ctx.addIssue({ code: "custom", message: "Katsayı sıfırdan büyük olmalı" });
});
const sema = z.object({
  neden: z.string().trim().min(1, "Neden zorunlu"),
  siniflar: z.array(
    z.object({ ad: z.string().trim().min(1, "Ad zorunlu"), hacim: sayi, uretim_adedi: sayi, katsayi: pozitif }),
  ),
});
type Form = z.infer<typeof sema>;

interface Props {
  siniflar: Ambalaj[];
  gonderiliyor: boolean;
  hata: string | null;
  onGonder: (v: AmbalajKaydiGiris) => void;
  onKapat: () => void;
}

/** Ambalaj sınıfları: PUT tüm listeyi değiştirir, bu yüzden form mevcut listeyle açılır. */
export function AmbalajDiyalogu({ siniflar, gonderiliyor, hata, onGonder, onKapat }: Props) {
  const id = useId();
  const varsayilan = useMemo<Form>(() => ({ neden: "", siniflar: siniflar.map((s) => ({ ...s })) }), [siniflar]);
  const {
    register,
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<Form>({ resolver: zodResolver(sema), defaultValues: varsayilan });
  const { fields, append, remove } = useFieldArray({ control, name: "siniflar" });
  const adet = (watch("siniflar") ?? []).length;

  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Ambalaj sınıflarını düzenle</DialogTitle>
          <DialogDescription>Kaydedince mevcut liste bu listeyle tamamen değiştirilir.</DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          noValidate
          onSubmit={handleSubmit((v) =>
            onGonder({
              neden: v.neden.trim(),
              siniflar: v.siniflar.map((s) => ({
                ad: s.ad.trim(),
                hacim: sayiApi(s.hacim) ?? "",
                uretim_adedi: sayiApi(s.uretim_adedi) ?? "",
                katsayi: sayiApi(s.katsayi) ?? "",
              })),
            }),
          )}
        >
          {fields.map((f, i) => {
            const e = errors.siniflar?.[i];
            return (
              <div key={f.id} className="grid grid-cols-[1fr_5rem_6rem_5rem_auto] items-start gap-2">
                <Girdi aria-label={`Ad ${i + 1}`} aria-invalid={!!e?.ad} {...register(`siniflar.${i}.ad`)} />
                <Girdi aria-label={`Hacim ${i + 1}`} inputMode="decimal" aria-invalid={!!e?.hacim} {...register(`siniflar.${i}.hacim`)} />
                <Girdi aria-label={`Üretim adedi ${i + 1}`} inputMode="decimal" aria-invalid={!!e?.uretim_adedi} {...register(`siniflar.${i}.uretim_adedi`)} />
                <Girdi aria-label={`Katsayı ${i + 1}`} inputMode="decimal" aria-invalid={!!e?.katsayi} {...register(`siniflar.${i}.katsayi`)} />
                <Button type="button" variant="ghost" size="sm" aria-label={`Satırı sil ${i + 1}`} onClick={() => remove(i)}>
                  Sil
                </Button>
                {e && (
                  <p role="alert" className="col-span-5 text-sm text-destructive">
                    {e.ad?.message ?? e.hacim?.message ?? e.uretim_adedi?.message ?? e.katsayi?.message}
                  </p>
                )}
              </div>
            );
          })}
          <div>
            <Button type="button" variant="outline" size="sm" onClick={() => append({ ad: "", hacim: "", uretim_adedi: "", katsayi: "" })}>
              Satır ekle
            </Button>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-neden`} className="text-sm font-medium">
              Neden
            </label>
            <Girdi id={`${id}-neden`} placeholder="Değişiklik nedeni" {...register("neden")} />
            {errors.neden && (
              <p role="alert" className="text-sm text-destructive">
                {errors.neden.message}
              </p>
            )}
          </div>
          <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
            Özet: {adet} sınıf kaydedilecek; mevcut liste değiştirilir.
          </p>
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
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
  );
}
