import type { ReactNode } from "react";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";

interface Props {
  baslik: string;
  /** Diyalogun gövdesi (ne değişecek). */
  children: ReactNode;
  onayMetni?: string;
  bekliyor?: boolean;
  hata?: string | null;
  onOnayla: () => void;
  onVazgec: () => void;
}

/** Geri alınması zor yazma işlemleri için ortak onay penceresi; hata olursa açık kalır ve role=alert gösterir. */
export function OnayDiyalogu({ baslik, children, onayMetni = "Onayla", bekliyor = false, hata = null, onOnayla, onVazgec }: Props) {
  return (
    <Dialog open onOpenChange={(a) => !a && onVazgec()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{baslik}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-2 text-sm">{children}</div>
        {hata && (
          <p role="alert" className="text-sm text-destructive">
            {hata}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onVazgec}>
            Vazgeç
          </Button>
          <Button type="button" disabled={bekliyor} onClick={onOnayla}>
            {onayMetni}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
