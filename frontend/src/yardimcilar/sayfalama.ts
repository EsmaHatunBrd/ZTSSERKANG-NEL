import { useCallback, useState } from "react";

/**
 * Senaryoya bağlı sayfa numarası: senaryo değişince sayfa kendiliğinden 1'e döner
 * (efekt beklenmeden, böylece eski sayfa numarasıyla yeni senaryoya istek atılmaz).
 */
export function useSenaryoSayfasi(senaryoId: number | null): [number, (s: number | ((onceki: number) => number)) => void] {
  const [durum, setDurum] = useState({ senaryo: senaryoId, sayfa: 1 });
  const sayfa = durum.senaryo === senaryoId ? durum.sayfa : 1;
  const sayfaYaz = useCallback(
    (s: number | ((onceki: number) => number)) =>
      setDurum((d) => {
        const onceki = d.senaryo === senaryoId ? d.sayfa : 1;
        return { senaryo: senaryoId, sayfa: typeof s === "function" ? s(onceki) : s };
      }),
    [senaryoId],
  );
  return [sayfa, sayfaYaz];
}
