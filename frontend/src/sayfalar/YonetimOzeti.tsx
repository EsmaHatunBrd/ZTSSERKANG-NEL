import { useState } from "react";
import { Printer, RefreshCw } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useYonetimOzeti } from "@/api/sorgular/yonetim";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { goster } from "@/yardimcilar/tarih";
import { StokEtkisiKarti, UyarilarKarti, VeriKontroluKarti } from "./yonetim/DurumKartlari";
import { MaliyetYapisiKarti } from "./yonetim/MaliyetYapisiKarti";
import { OzetKutulari } from "./yonetim/OzetKutulari";
import { AcikTekliflerKarti, EnPahaliKarti, HedefAltiKarti, KurRiskiKarti } from "./yonetim/Tablolar";

/** "2026-11-12T09:00:00+00:00" -> "12.11.2026 12:00" (yerel saat). Tarihsiz metin olduğu gibi döner. */
function zamanGoster(iso: string | undefined): string | null {
  if (!iso) return null;
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(t.getDate())}.${p(t.getMonth() + 1)}.${t.getFullYear()} ${p(t.getHours())}:${p(t.getMinutes())}`;
}

/**
 * Yönetim Özeti (analiz önerisi 15): seçili çalışmanın marj, maliyet yapısı, hedef altı, kur riski, teklif, veri kontrolü ve stok
 * etkisi durumu tek yazdırılabilir sayfada. Hiçbir şey kaydedilmez; "Yenile" sunucu önbelleğini atlayıp yeniden hesaplatır.
 */
export default function YonetimOzeti() {
  const { senaryoId } = useSenaryo();
  const [surum, setSurum] = useState(0);
  const q = useYonetimOzeti(senaryoId, surum);
  const o = q.data;
  const sorgu = senaryoId === null ? "" : `?senaryo=${senaryoId}`;
  const uretim = zamanGoster(o?.baslik.uretim_zamani);

  return (
    <div data-yazdir="yonetim" className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Yönetim Özeti"
        altBaslik={
          o
            ? `${o.baslik.sezon_ad} · ${o.baslik.ad} · hesap tarihi ${goster(o.baslik.hesap_tarihi)}`
            : "Marj, risk, teklif ve veri durumu tek sayfada"
        }
        eylemler={
          <>
            <Button
              type="button"
              variant="outline"
              size="sm"
              title="Tarayıcının yazdırma penceresi açılır; PDF için yazıcı olarak 'PDF olarak kaydet' seçin."
              disabled={!o}
              onClick={() => window.print()}
            >
              <Printer aria-hidden />
              Yazdır / PDF
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              title="Sunucudaki özeti yeniden hesaplatır (birkaç saniye sürebilir)."
              disabled={senaryoId === null || q.isFetching}
              onClick={() => setSurum((s) => s + 1)}
            >
              <RefreshCw aria-hidden className={q.isFetching ? "animate-spin" : undefined} />
              Yenile
            </Button>
          </>
        }
      />

      {o && (
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {o.baslik.kilitli && <Badge variant="outline">Kilitli çalışma</Badge>}
          {uretim && <span>Özet {uretim} itibarıyla hesaplandı.</span>}
          <span>Tutarlar TL, oranlar yüzde; kur riski tüm kurların %10 artışı varsayımıyla.</span>
        </p>
      )}

      {senaryoId === null && !q.isPending && (
        <p role="status" className="text-sm text-muted-foreground">
          Önce üst bardan bir çalışma seçin.
        </p>
      )}
      {q.isPending && senaryoId !== null && (
        <div role="status" className="flex flex-col gap-3" aria-label="Yükleniyor">
          <span className="sr-only">Özet yükleniyor…</span>
          <div aria-hidden className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-24 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
          <div aria-hidden className="h-48 animate-pulse rounded-xl bg-muted" />
        </div>
      )}
      {q.error && (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}

      {o && (
        <>
          <OzetKutulari ozet={o} />
          <div className="grid gap-4 xl:grid-cols-2">
            <MaliyetYapisiKarti yapi={o.maliyet_yapisi} />
            <HedefAltiKarti ozet={o} sorgu={sorgu} />
            <KurRiskiKarti ozet={o} sorgu={sorgu} />
            <AcikTekliflerKarti ozet={o} sorgu={sorgu} />
            <VeriKontroluKarti ozet={o} sorgu={sorgu} />
            <EnPahaliKarti ozet={o} sorgu={sorgu} />
            <StokEtkisiKarti ozet={o} sorgu={sorgu} />
            <UyarilarKarti ozet={o} sorgu={sorgu} />
          </div>
        </>
      )}
    </div>
  );
}
