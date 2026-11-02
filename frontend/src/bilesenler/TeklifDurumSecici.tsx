import { useState } from "react";
import { hataMetni } from "@/api/istemci";
import { useTeklifDurum } from "@/api/sorgular/hesaplar";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { ONAY_GEREKEN_DURUMLAR, TEKLIF_DURUMLARI, teklifDurumAdi } from "@/yardimcilar/teklif";

interface Props {
  teklifId: number;
  durum: string;
  etiket: string;
}

/**
 * Teklif durumu seçimi: güncellenirken kapalıdır, kabul/red için onay ister, hata satırda role=alert ile gösterilir.
 * Her seçici kendi mutation'ını taşır (bir satırın beklemesi diğerlerini kilitlemez).
 */
export function TeklifDurumSecici({ teklifId, durum, etiket }: Props) {
  const degistir = useTeklifDurum();
  const { kilitli } = useSenaryo();
  const [bekleyen, setBekleyen] = useState<string | null>(null);

  function uygula(yeni: string) {
    setBekleyen(null);
    degistir.mutate({ teklifId, durum: yeni });
  }

  return (
    <span className="inline-flex flex-col gap-1">
      <select
        aria-label={etiket}
        value={durum}
        disabled={degistir.isPending || kilitli}
        title={kilitli ? "Senaryo kilitli" : undefined}
        onChange={(e) => {
          const yeni = e.target.value;
          if (ONAY_GEREKEN_DURUMLAR.has(yeni)) setBekleyen(yeni);
          else uygula(yeni);
        }}
        className="h-7 rounded-lg border border-input bg-background px-2 text-sm"
      >
        {!TEKLIF_DURUMLARI.some(([v]) => v === durum) && <option value={durum}>{durum}</option>}
        {TEKLIF_DURUMLARI.map(([v, ad]) => (
          <option key={v} value={v}>
            {ad}
          </option>
        ))}
      </select>
      {degistir.error && (
        <span role="alert" className="text-xs text-destructive">
          {hataMetni(degistir.error)}
        </span>
      )}
      {bekleyen && (
        <OnayDiyalogu
          baslik="Teklif durumunu onayla"
          onayMetni="Onayla"
          onOnayla={() => uygula(bekleyen)}
          onVazgec={() => setBekleyen(null)}
        >
          <p>{`Teklif durumu ${teklifDurumAdi(bekleyen)} olarak değiştirilecek.`}</p>
        </OnayDiyalogu>
      )}
    </span>
  );
}
