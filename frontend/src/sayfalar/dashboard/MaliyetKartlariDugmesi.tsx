import { useState } from "react";
import { FileSpreadsheet, Loader2 } from "lucide-react";
import { maliyetKartlariXlsxAdresi } from "@/api/sorgular/onemliMalzemeler";
import { Button } from "@/bilesenler/ui/button";
import { dosyaIndir } from "@/yardimcilar/indir";

/**
 * Tüm ürünlerin maliyet kartlarını tek Excel dosyasında indirir (Özet + ürün başına sayfa). Dosya sunucuda hazırlanırken düğme
 * "Hazırlanıyor…" gösterir ve yeniden tıklanamaz; hata olursa düğmenin altında mesaj çıkar.
 */
export function MaliyetKartlariDugmesi({ senaryoId }: { senaryoId: number }) {
  const [hazirlaniyor, setHazirlaniyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  async function indir() {
    setHazirlaniyor(true);
    setHata(null);
    try {
      await dosyaIndir(maliyetKartlariXlsxAdresi(senaryoId), "maliyet-kartlari.xlsx");
    } catch (e) {
      setHata(e instanceof Error ? e.message : "Dosya hazırlanamadı");
    } finally {
      setHazirlaniyor(false);
    }
  }

  return (
    <span className="flex flex-col items-end gap-1">
      <Button
        type="button"
        variant="outline"
        onClick={indir}
        disabled={hazirlaniyor}
        aria-busy={hazirlaniyor}
        title="Her ürün ayrı sayfada, tek Excel dosyası"
      >
        {hazirlaniyor ? <Loader2 className="animate-spin" aria-hidden /> : <FileSpreadsheet aria-hidden />}
        {hazirlaniyor ? "Hazırlanıyor…" : "Tüm maliyet kartları (ürün başına sayfa)"}
      </Button>
      {hata && (
        <span role="alert" className="text-xs text-destructive">
          {hata}
        </span>
      )}
    </span>
  );
}
