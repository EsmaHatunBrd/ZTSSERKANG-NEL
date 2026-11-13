import { useState } from "react";
import { Pencil } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useAileDegistir } from "@/api/sorgular/karsilastirma";
import { useDuzenlemeKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";

const ENCOK = 120;

function AileDiyalogu({ kod, mevcut, onKapat }: { kod: string; mevcut: string; onKapat: () => void }) {
  const [metin, setMetin] = useState(mevcut);
  const degistir = useAileDegistir();
  const kaydet = (aile: string | null) => degistir.mutate({ kod, aile }, { onSuccess: onKapat });
  return (
    <Dialog open onOpenChange={(a) => !a && !degistir.isPending && onKapat()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ürün ailesi</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            kaydet(metin.trim() || null);
          }}
        >
          <label className="flex flex-col gap-1 text-sm">
            Aile adı
            <Input value={metin} maxLength={ENCOK} onChange={(e) => setMetin(e.target.value)} autoFocus />
          </label>
          <p className="text-xs text-muted-foreground">
            Aynı aileye yazılan ürünler Karşılaştırma sayfasında ambalaj hacmine göre yan yana gösterilir. Yazdığınız ad olduğu gibi
            görünür; eşleştirmede büyük/küçük harf farkı gözetilmez. &ldquo;Yeniden türet&rdquo; adı üründen otomatik üretir.
          </p>
          {degistir.error && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetni(degistir.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={degistir.isPending} onClick={onKapat}>
              Vazgeç
            </Button>
            <Button type="button" variant="outline" disabled={degistir.isPending} onClick={() => kaydet(null)}>
              Yeniden türet
            </Button>
            <Button type="submit" disabled={degistir.isPending}>
              Kaydet
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Ürün başlığının altında "Aile: ..." rozeti ve düzenleme düğmesi. Görünen ad (`aile_ad`) gösterilir ve düzenlenir;
 *  gruplama anahtarı (`aile`) sunucuda türetilir, kullanıcıya gösterilmez. */
export function AileRozeti({ kod, aile, aileAd }: { kod: string; aile: string | null | undefined; aileAd?: string | null }) {
  const [acik, setAcik] = useState(false);
  const kilitli = !useDuzenlemeKilidi().acik;
  const gorunen = aileAd ?? aile ?? "";
  return (
    <span className="inline-flex items-center gap-1">
      <Badge variant="secondary">Aile: {gorunen || "—"}</Badge>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Ürün ailesini düzenle"
        disabled={kilitli}
        title={kilitli ? "Düzenleme kilitli" : undefined}
        onClick={() => setAcik(true)}
      >
        <Pencil aria-hidden />
      </Button>
      {acik && <AileDiyalogu key={kod} kod={kod} mevcut={gorunen} onKapat={() => setAcik(false)} />}
    </span>
  );
}
