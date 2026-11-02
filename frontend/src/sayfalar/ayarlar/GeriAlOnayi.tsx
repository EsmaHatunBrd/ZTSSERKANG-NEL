import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";

interface Props {
  metin: string;
  hata: string | null;
  bekliyor: boolean;
  onOnayla: () => void;
  onVazgec: () => void;
}

/** "Geri al" için tek satırlık onay; hata olursa açık kalır ve role=alert gösterir. */
export function GeriAlOnayi({ metin, hata, bekliyor, onOnayla, onVazgec }: Props) {
  return (
    <Dialog open onOpenChange={(a) => !a && onVazgec()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Geri almayı onayla</DialogTitle>
        </DialogHeader>
        <p className="text-sm">{metin}</p>
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
            {bekliyor ? "Kaydediliyor…" : "Onayla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
