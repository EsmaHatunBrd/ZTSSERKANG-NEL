import { Lock } from "lucide-react";
import { useSenaryo } from "./SenaryoSecici";

export const KILIT_METNI = "Bu senaryo kilitli; değişiklik yapılamaz";
/** Kilidin kapsamı: yalnız senaryoya bağlı kayıtlar korunur (Arşiv kilit diyaloğunda da aynı cümle kullanılır). */
export const KILIT_KAPSAM_NOTU =
  "Kilit senaryoya bağlı kayıtları korur; ürün/malzeme kartı gibi senaryodan bağımsız veriler değişebilir, kayıtlı hesaplar ve Arşiv etkilenmez.";

/** Seçili senaryo kilitliyse sayfanın üstünde sarı uyarı şeridi; değilse hiçbir şey çizmez. */
export function KilitSeridi() {
  const { kilitli } = useSenaryo();
  if (!kilitli) return null;
  return (
    <p
      role="status"
      data-testid="kilit-seridi"
      className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
    >
      <Lock className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>
        {KILIT_METNI}
        <span className="block text-xs opacity-90">{KILIT_KAPSAM_NOTU}</span>
      </span>
    </p>
  );
}
