import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { Senaryo, SenaryoGuncelleGiris } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Girdi } from "@/bilesenler/Girdi";
import { senaryoEtiketi } from "@/yardimcilar/senaryo";
import { SEZON_BICIM_MESAJI, SEZON_BICIMI } from "./YeniCalismaDiyalogu";

const sema = z.object({
  sezon_ad: z.string().trim().min(1, "Sezon adı zorunlu").regex(SEZON_BICIMI, SEZON_BICIM_MESAJI),
  ad: z.string().trim().min(1, "Çalışma adı zorunlu"),
  aciklama: z.string().trim(),
  neden: z.string().trim().min(1, "Neden zorunlu"),
});
type Form = z.infer<typeof sema>;

interface Props {
  senaryo: Senaryo;
  gonderiliyor: boolean;
  hata: string | null;
  onGonder: (govde: SenaryoGuncelleGiris) => void;
  onKapat: () => void;
}

/** Senaryo adı / sezon / açıklama düzenleme; yalnız değişen alanlar nedenle gönderilir (günlüğe düşer). */
export function SenaryoDuzenleDiyalogu({ senaryo, gonderiliyor, hata, onGonder, onKapat }: Props) {
  const id = useId();
  const [degisiklikYok, setDegisiklikYok] = useState(false);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Form>({
    resolver: zodResolver(sema),
    defaultValues: { sezon_ad: senaryo.sezon_ad, ad: senaryo.ad, aciklama: senaryo.aciklama ?? "", neden: "" },
  });

  function gonder(v: Form) {
    const govde: SenaryoGuncelleGiris = { neden: v.neden };
    if (v.sezon_ad !== senaryo.sezon_ad) govde.sezon_ad = v.sezon_ad;
    if (v.ad !== senaryo.ad) govde.ad = v.ad;
    // Boşaltılan açıklama null gider (şemada `string | null`).
    if (v.aciklama !== (senaryo.aciklama ?? "")) govde.aciklama = v.aciklama === "" ? null : v.aciklama;
    if (govde.sezon_ad === undefined && govde.ad === undefined && govde.aciklama === undefined) {
      setDegisiklikYok(true);
      return;
    }
    setDegisiklikYok(false);
    onGonder(govde);
  }

  const hataSatiri = (m?: string | null) =>
    m ? (
      <p role="alert" className="text-sm text-destructive">
        {m}
      </p>
    ) : null;

  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Çalışmayı düzenle</DialogTitle>
          <DialogDescription>{senaryoEtiketi(senaryo)}</DialogDescription>
        </DialogHeader>
        <form noValidate className="flex flex-col gap-3" onSubmit={handleSubmit(gonder)}>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-sezon`} className="text-sm font-medium">
              Sezon adı
            </label>
            <Girdi id={`${id}-sezon`} aria-invalid={!!errors.sezon_ad} {...register("sezon_ad")} />
            {hataSatiri(errors.sezon_ad?.message)}
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-ad`} className="text-sm font-medium">
              Çalışma adı
            </label>
            <Girdi id={`${id}-ad`} aria-invalid={!!errors.ad} {...register("ad")} />
            {hataSatiri(errors.ad?.message)}
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-aciklama`} className="text-sm font-medium">
              Açıklama <span className="font-normal text-muted-foreground">(isteğe bağlı)</span>
            </label>
            <Girdi id={`${id}-aciklama`} {...register("aciklama")} />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-neden`} className="text-sm font-medium">
              Neden
            </label>
            <Girdi id={`${id}-neden`} aria-invalid={!!errors.neden} {...register("neden")} />
            {hataSatiri(errors.neden?.message)}
          </div>
          {degisiklikYok && <p className="text-sm text-muted-foreground">Değişiklik yok: ad, sezon ya da açıklamadan birini değiştirin.</p>}
          {hataSatiri(hata)}
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
