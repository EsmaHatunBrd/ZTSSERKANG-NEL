import { useState } from "react";
import { UserRound } from "lucide-react";
import { Button } from "@/bilesenler/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";
import { adGecerli, al, kaydet } from "@/yardimcilar/kullanici";

/**
 * Denetim izi için yazan kişinin adı. İlk açılışta kayıtlı ad yoksa, geçerli bir ad girilene kadar
 * kapanmayan bir diyalog açılır (yazma istekleri "sistem" adıyla engellenir, bkz. api/istemci).
 */
export function KullaniciAyari() {
  const [ad, setAd] = useState(() => al());
  const [duzenle, setDuzenle] = useState(false);
  const [zorunlu, setZorunlu] = useState(() => !adGecerli(al()));
  const [taslak, setTaslak] = useState(() => (adGecerli(al()) ? al() : ""));
  const [hata, setHata] = useState<string | null>(null);

  const kaydetVeKapat = () => {
    const temiz = taslak.trim();
    if (!adGecerli(temiz)) {
      setHata(temiz === "" ? "Ad boş olamaz" : "Kendi adınızı girin (\"sistem\" geçerli değil)");
      return;
    }
    kaydet(temiz);
    setAd(temiz);
    setHata(null);
    setDuzenle(false);
    setZorunlu(false);
  };

  const form = (
    <form
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        kaydetVeKapat();
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span>Adınız</span>
        <Input
          autoFocus
          value={taslak}
          onChange={(e) => setTaslak(e.target.value)}
          aria-label="Adınız"
          aria-invalid={!!hata}
          className="h-8"
        />
      </label>
      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hata}
        </p>
      )}
      <DialogFooter>
        {!zorunlu && (
          <Button type="button" variant="outline" size="sm" onClick={() => setDuzenle(false)}>
            Vazgeç
          </Button>
        )}
        <Button type="submit" size="sm">
          Kaydet
        </Button>
      </DialogFooter>
    </form>
  );

  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          setTaslak(adGecerli(ad) ? ad : "");
          setHata(null);
          setDuzenle(true);
        }}
        title="Kullanıcı adını değiştir"
        className="max-w-48 truncate"
      >
        <UserRound aria-hidden />
        Kullanıcı: {ad}
      </Button>
      <Dialog
        open={zorunlu || duzenle}
        // Zorunlu ilk girişte kapatma (Esc, dış tık) yok sayılır.
        onOpenChange={(a) => {
          if (!a && !zorunlu) setDuzenle(false);
        }}
      >
        <DialogContent showCloseButton={!zorunlu}>
          <DialogHeader>
            <DialogTitle>{zorunlu ? "Adınızı girin" : "Kullanıcı adını değiştir"}</DialogTitle>
            <DialogDescription>
              {zorunlu
                ? "Yapılan değişiklikler bu adla kaydedilir. Devam etmek için adınızı girin."
                : "Yeni değişiklikler bu adla kaydedilir."}
            </DialogDescription>
          </DialogHeader>
          {form}
        </DialogContent>
      </Dialog>
    </>
  );
}
