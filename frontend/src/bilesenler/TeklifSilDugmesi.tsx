import { useState } from "react";
import { Trash2 } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useTeklifSil } from "@/api/sorgular/hesaplar";
import { NedenAlani } from "@/bilesenler/NedenAlani";
import { nedenGecerli } from "@/yardimcilar/neden";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";

interface Props {
  teklifId: number;
  /** Erişilebilir ad ve onay metni için, ör. "03.004… Tur 2". */
  etiket: string;
  /** Teklif durumu; "kabul" ise silme kapalıdır (sunucu da 409 verir). */
  durum?: string;
}

export const KABUL_SILINEMEZ = "Kabul edilmiş teklif silinemez; önce durumunu değiştirin.";

/**
 * Teklif turunu onay sorarak siler. Diğer turların numarası değişmez; silinen tur Değişiklik Günlüğünde görünür. Kabul edilmiş teklif
 * silinemez: düğme pasif, nedeni ipucunda (pasif düğme fareyle ipucu göstermediği için ipucu sarmalayıcıdadır).
 */
export function TeklifSilDugmesi({ teklifId, etiket, durum }: Props) {
  const sil = useTeklifSil();
  const { kilitli } = useSenaryo();
  const [acik, setAcik] = useState(false);
  const [neden, setNeden] = useState("");
  const kabul = durum === "kabul";
  const ipucu = kilitli ? "Senaryo kilitli" : kabul ? KABUL_SILINEMEZ : "Teklifi sil";
  return (
    <>
      <span title={ipucu} className="inline-flex">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label={`Sil — ${etiket}`}
          title={ipucu}
          disabled={kilitli || kabul || sil.isPending}
          onClick={() => {
            sil.reset();
            setNeden("");
            setAcik(true);
          }}
          className="size-7 text-muted-foreground hover:text-destructive"
        >
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </span>
      {acik && (
        <OnayDiyalogu
          baslik="Teklifi sil"
          onayMetni="Sil"
          bekliyor={sil.isPending}
          onayPasif={!nedenGecerli(neden)}
          hata={sil.error ? hataMetni(sil.error) : null}
          onOnayla={() => sil.mutate({ teklifId, neden: neden.trim() }, { onSuccess: () => setAcik(false) })}
          onVazgec={() => setAcik(false)}
        >
          <p>{`${etiket} silinecek. Diğer turların numarası değişmez; silinen tur Değişiklik Günlüğünde kalır.`}</p>
          <NedenAlani deger={neden} onDegis={setNeden} autoFocus />
        </OnayDiyalogu>
      )}
    </>
  );
}
