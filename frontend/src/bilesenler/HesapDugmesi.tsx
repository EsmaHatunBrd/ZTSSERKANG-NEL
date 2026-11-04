import { useState } from "react";
import { LogOut, UserRound } from "lucide-react";
import { useCikis } from "@/api/sorgular/kimlik";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { SifreFormu, useOturum } from "./GirisKapisi";
import { KullaniciAyari } from "./KullaniciAyari";

/**
 * Sağ üstte oturumdaki kullanıcı: ad + rol; tıklayınca Hesabım (şifre değiştir, çıkış). Yanında tek tıkla çıkış.
 * Giriş zorunlu olmayan kurulumda eski ad seçimi (KullaniciAyari) gösterilir.
 */
export function HesapDugmesi() {
  const { girisZorunlu, kullanici } = useOturum();
  const cikis = useCikis();
  const [acik, setAcik] = useState(false);
  const [sifreKaydedildi, setSifreKaydedildi] = useState(false);
  if (!girisZorunlu || !kullanici) return <KullaniciAyari />;
  return (
    <div className="flex items-center gap-1">
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          setSifreKaydedildi(false);
          setAcik(true);
        }}
        aria-label={`Hesabım: ${kullanici.ad} (${kullanici.rol_ad})`}
      >
        <UserRound aria-hidden />
        <span className="max-w-40 truncate">{kullanici.ad}</span>
        <span className="hidden text-muted-foreground sm:inline">· {kullanici.rol_ad}</span>
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label="Çıkış yap"
        title="Çıkış yap"
        onClick={() => cikis.mutate()}
        disabled={cikis.isPending}
      >
        <LogOut aria-hidden />
      </Button>
      <Dialog open={acik} onOpenChange={setAcik}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hesabım</DialogTitle>
            <DialogDescription>
              {kullanici.ad} · <span className="font-mono">{kullanici.kullanici_adi}</span> · {kullanici.rol_ad}
            </DialogDescription>
          </DialogHeader>
          <h3 className="text-sm font-medium">Şifre değiştir</h3>
          {sifreKaydedildi ? (
            <p role="status" className="text-sm">
              Şifreniz değişti. Diğer cihazlardaki oturumlarınız kapatıldı.
            </p>
          ) : (
            <SifreFormu onBitti={() => setSifreKaydedildi(true)} />
          )}
          <Button type="button" variant="outline" onClick={() => cikis.mutate()} disabled={cikis.isPending}>
            <LogOut aria-hidden /> Çıkış yap
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
