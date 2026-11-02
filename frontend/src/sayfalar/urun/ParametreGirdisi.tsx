import { cn } from "@/lib/utils";
import { sayiApi } from "@/yardimcilar/sayi";
import { GirdiHucresi } from "./GirdiHucresi";
import { oranYuzdeMetni, yuzdeOranMetni } from "./yardimci";

interface Props {
  etiket: string;
  /** Sunucudaki (kayıtlı) değer (API metni). */
  deger: string | null;
  /** Sunucu tabanındaki değer ("Eski değer" ipucu): verilirse `deger` (yeniden hesaplanmış) yerine bu gösterilir; null = tabanda yok. */
  eskiDeger?: string | null;
  /** Taslakta bu parametre için yazılmış değer (API metni); yoksa undefined. */
  taslak: string | undefined;
  /** API metniyle çağrılır; girdi boşsa veya geçersizse null (taslak girdisi silinir). */
  onDegis: (deger: string | null) => void;
  /** yuzde: girdi yüzde ("25"), API oranı ("0.25"); sayi: olduğu gibi. */
  tur?: "yuzde" | "sayi";
  negatifIzin?: boolean;
  disabled?: boolean;
  className?: string;
}

/** Parametre hücresi: yazılan değer `taslak.parametreler`'e gider, hesaba hemen girer, "Kaydet" ile kalıcı olur. */
export function ParametreGirdisi({
  etiket,
  deger,
  eskiDeger,
  taslak,
  onDegis,
  tur = "sayi",
  negatifIzin = false,
  disabled,
  className,
}: Props) {
  const goster = (api: string | null | undefined) => (api === null || api === undefined ? "" : tur === "yuzde" ? oranYuzdeMetni(api) : api);
  return (
    <GirdiHucresi
      etiket={etiket}
      deger={goster(taslak ?? deger)}
      disabled={disabled}
      degisti={taslak !== undefined}
      eski={(() => {
        const e = eskiDeger === undefined ? deger : eskiDeger;
        return e === null ? "—" : `${goster(e)}${tur === "yuzde" ? " %" : ""}`;
      })()}
      className={cn(className)}
      onMetin={(m) => {
        if (m.trim() === "") return onDegis(null);
        onDegis(tur === "yuzde" ? yuzdeOranMetni(m, negatifIzin) : sayiApi(m, negatifIzin));
      }}
    />
  );
}
