import { useId, useMemo, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Girdi } from "@/bilesenler/Girdi";
import { bugunIso } from "@/yardimcilar/tarih";
import { sayiApi, sayiGecerli, sayiKurali } from "./ortak";

const semaYap = (negatifIzin: boolean) =>
  z.object({
  deger: z
    .string()
    .trim()
    .min(1, "Değer zorunlu")
    .superRefine(sayiKurali(negatifIzin)),
  tarih: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Geçerlilik tarihi zorunlu"),
  neden: z.string().trim().min(1, "Neden zorunlu"),
  });
type Form = z.infer<ReturnType<typeof semaYap>>;

export interface DegerGirdisi {
  /** API metni (nokta ondalık). */
  deger: string;
  tarih: string;
  neden: string;
}

interface Props {
  baslik: string;
  aciklama?: string;
  degerEtiketi: string;
  mevcut?: string;
  /** Gönderilmeden önce gösterilen özet cümlesi. */
  ozet: (deger: string, tarih: string) => string;
  gonderiliyor: boolean;
  hata: string | null;
  onGonder: (v: DegerGirdisi) => void;
  onKapat: () => void;
  /** Forma eklenecek alanlar (örn. kapsam seçimi). */
  children?: ReactNode;
  /** Doluysa gönderim engellenir ve metin gösterilir. */
  engel?: string | null;
  /** Parametre değerleri gibi eksi olabilen değerler için. Varsayılan: negatif reddedilir. */
  negatifIzin?: boolean;
}

/** Değer + geçerlilik tarihi + zorunlu neden alan diyalog; fiyat ve parametre yazımında ortak kullanılır. */
export function DegerDiyalogu({
  baslik,
  aciklama,
  degerEtiketi,
  mevcut,
  ozet,
  gonderiliyor,
  hata,
  onGonder,
  onKapat,
  children,
  engel,
  negatifIzin = false,
}: Props) {
  const id = useId();
  const bugun = useMemo(() => bugunIso(), []);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<Form>({
    resolver: zodResolver(semaYap(negatifIzin)),
    defaultValues: { deger: mevcut ?? "", tarih: bugun, neden: "" },
  });
  const [deger, tarih] = watch(["deger", "tarih"]);

  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{baslik}</DialogTitle>
          {aciklama && <DialogDescription>{aciklama}</DialogDescription>}
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          noValidate
          onSubmit={handleSubmit((v) => onGonder({ deger: sayiApi(v.deger, negatifIzin) ?? "", tarih: v.tarih, neden: v.neden.trim() }))}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-deger`} className="text-sm font-medium">
              {degerEtiketi}
            </label>
            <Girdi id={`${id}-deger`} inputMode="decimal" aria-invalid={!!errors.deger} {...register("deger")} />
            {errors.deger && (
              <p role="alert" className="text-sm text-destructive">
                {errors.deger.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-tarih`} className="text-sm font-medium">
              Geçerlilik tarihi
            </label>
            <Girdi id={`${id}-tarih`} type="date" aria-invalid={!!errors.tarih} {...register("tarih")} />
            {errors.tarih && (
              <p role="alert" className="text-sm text-destructive">
                {errors.tarih.message}
              </p>
            )}
          </div>
          {children}
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-neden`} className="text-sm font-medium">
              Neden
            </label>
            <Girdi id={`${id}-neden`} aria-invalid={!!errors.neden} {...register("neden")} />
            {errors.neden && (
              <p role="alert" className="text-sm text-destructive">
                {errors.neden.message}
              </p>
            )}
          </div>
          <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
            {sayiGecerli(deger ?? "", negatifIzin) ? ozet(sayiApi(deger, negatifIzin) ?? "", tarih) : "Özet: geçerli bir değer girin."}
          </p>
          {engel && <p className="text-sm text-muted-foreground">{engel}</p>}
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onKapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={gonderiliyor || !!engel}>
              {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
