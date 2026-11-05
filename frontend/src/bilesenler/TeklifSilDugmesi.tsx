import { useState } from "react";
import { Trash2 } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useTeklifSil } from "@/api/sorgular/hesaplar";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";

interface Props {
  teklifId: number;
  /** Erişilebilir ad ve onay metni için, ör. "03.004… Tur 2". */
  etiket: string;
}

/** Teklif turunu onay sorarak siler. Diğer turların numarası değişmez; silinen tur Değişiklik Günlüğünde görünür. */
export function TeklifSilDugmesi({ teklifId, etiket }: Props) {
  const sil = useTeklifSil();
  const { kilitli } = useSenaryo();
  const [acik, setAcik] = useState(false);
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={`Sil — ${etiket}`}
        title={kilitli ? "Senaryo kilitli" : "Teklifi sil"}
        disabled={kilitli || sil.isPending}
        onClick={() => {
          sil.reset();
          setAcik(true);
        }}
        className="size-7 text-muted-foreground hover:text-destructive"
      >
        <Trash2 className="size-4" aria-hidden />
      </Button>
      {acik && (
        <OnayDiyalogu
          baslik="Teklifi sil"
          onayMetni="Sil"
          bekliyor={sil.isPending}
          hata={sil.error ? hataMetni(sil.error) : null}
          onOnayla={() => sil.mutate(teklifId, { onSuccess: () => setAcik(false) })}
          onVazgec={() => setAcik(false)}
        >
          <p>{`${etiket} silinecek. Diğer turların numarası değişmez; silinen tur Değişiklik Günlüğünde kalır.`}</p>
        </OnayDiyalogu>
      )}
    </>
  );
}
