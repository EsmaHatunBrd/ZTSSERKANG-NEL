import { paraBicimle } from "@/yardimcilar/para";

/** Sunucudan yüzde metni gelir ("35.00" = %35): "35,0 %". null ise "—". */
export const puanMetni = (p: string | null | undefined, basamak = 1) =>
  p === null || p === undefined ? "—" : `${paraBicimle(p, "", basamak)} %`;
