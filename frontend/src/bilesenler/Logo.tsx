import { cn } from "@/lib/utils";

/**
 * Zeytursan logosu (public/zeytursan-logo.png, 500x104, şeffaf zemin). Koyu temada yazı koyu yeşil olduğu için
 * logo küçük beyaz bir rozetin içinde gösterilir; böylece iki temada da okunur.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-md dark:bg-white dark:px-2 dark:py-1", className)}>
      <img src="/zeytursan-logo.png" alt="Zeytursan" width={500} height={104} className="h-7 w-auto" />
    </span>
  );
}
