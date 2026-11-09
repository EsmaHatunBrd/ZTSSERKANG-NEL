import { Link } from "react-router-dom";
import { ArrowRight, Check } from "lucide-react";
import { useSmmDonemleri, useSmmVeriDurumu } from "@/api/sorgular/smm";
import { cn } from "@/lib/utils";

const AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

interface Adim {
  ad: string;
  durum: "tamam" | "simdi" | "sonra";
}

/**
 * Maliyet muhasebesinde "bu ay sıradaki adım": son döneme bakar ve tek bir yönlendirme verir. Aylık akış:
 * dönem aç -> verileri gir -> kontrol et (üretim maliyeti, sarf farkı, SMM özeti) -> kapat. Kullanıcı neye tıklayacağını düşünmesin.
 */
export function SiradakiAdim() {
  const donemler = useSmmDonemleri();
  const son = donemler.data?.kayitlar[0] ?? null;
  const veri = useSmmVeriDurumu(son && !son.kilitli ? son.id : null);
  if (donemler.isPending || (son && !son.kilitli && veri.isPending)) {
    return <div className="h-40 animate-pulse rounded-2xl bg-muted" aria-hidden />;
  }

  const sonraki = son ? (son.ay === 12 ? `${AYLAR[0]} ${son.yil + 1}` : `${AYLAR[son.ay]} ${son.yil}`) : null;
  const eksik = veri.data?.eksik ?? [];
  let baslik: string;
  let aciklama: string;
  let hedef: string;
  let dugme: string;
  let adimlar: Adim[];
  let ikincil: { ad: string; yol: string }[] = [];

  if (!son) {
    baslik = "İlk dönemi başlatın";
    aciklama = "Bugünkü SMM Excel'ini yükleyin; dönem başı stok, alımlar, sayım ve reçeteler oradan gelir.";
    hedef = "/smm";
    dugme = "Dönemler'e git";
    adimlar = [
      { ad: "Dönemi aç", durum: "simdi" },
      { ad: "Verileri gir", durum: "sonra" },
      { ad: "Kontrol et", durum: "sonra" },
      { ad: "Kapat", durum: "sonra" },
    ];
  } else if (son.kilitli) {
    baslik = `${son.ad} kapatıldı · sırada ${sonraki}`;
    aciklama = `${sonraki} dönemini açın: dönem başı stok ${son.ad} sayımından otomatik gelir.`;
    hedef = "/smm";
    dugme = `${sonraki} dönemini aç`;
    adimlar = [
      { ad: "Dönemi aç", durum: "simdi" },
      { ad: "Verileri gir", durum: "sonra" },
      { ad: "Kontrol et", durum: "sonra" },
      { ad: "Kapat", durum: "sonra" },
    ];
    ikincil = [{ ad: `${son.ad} SMM özeti`, yol: `/smm/ozet?donem=${son.id}` }];
  } else if (eksik.length > 0) {
    baslik = `${son.ad} · veriler eksik`;
    aciklama = `Eksik: ${eksik.join(", ")}. Veri Girişi'nden her birini ayrı yükleyin.`;
    hedef = `/smm/veri?donem=${son.id}`;
    dugme = "Veri Girişi'ne git";
    adimlar = [
      { ad: "Dönemi aç", durum: "tamam" },
      { ad: "Verileri gir", durum: "simdi" },
      { ad: "Kontrol et", durum: "sonra" },
      { ad: "Kapat", durum: "sonra" },
    ];
  } else {
    baslik = `${son.ad} · veriler tamam, kontrol edin`;
    aciklama = "Üretim maliyetine ve sarf farkına göz atın; SMM Özeti uygunsa fişi indirip dönemi Veri Girişi'nden kapatın.";
    hedef = `/smm/ozet?donem=${son.id}`;
    dugme = "SMM Özeti'ne git";
    adimlar = [
      { ad: "Dönemi aç", durum: "tamam" },
      { ad: "Verileri gir", durum: "tamam" },
      { ad: "Kontrol et", durum: "simdi" },
      { ad: "Kapat", durum: "sonra" },
    ];
    ikincil = [
      { ad: "Üretim maliyeti", yol: `/smm/uretim?donem=${son.id}` },
      { ad: "Sarf farkı", yol: `/smm/sarf-farki?donem=${son.id}` },
      { ad: "Dönemi kapat", yol: `/smm/veri?donem=${son.id}` },
    ];
  }

  return (
    <section aria-label="Bu ay sıradaki adım" className="flex flex-col gap-4 rounded-2xl border-2 border-marka bg-card p-6 shadow-xs">
      <ol className="flex flex-wrap items-center gap-2 text-sm" aria-label="Aylık akış">
        {adimlar.map((a, i) => (
          <li key={a.ad} className="flex items-center gap-2">
            <span
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1 font-medium",
                a.durum === "tamam" && "bg-kart-yesil text-primary",
                a.durum === "simdi" && "bg-primary text-primary-foreground",
                a.durum === "sonra" && "bg-muted text-muted-foreground",
              )}
              aria-current={a.durum === "simdi" ? "step" : undefined}
            >
              {a.durum === "tamam" ? <Check className="size-3.5" aria-hidden /> : <span className="tabular-nums">{i + 1}</span>}
              {a.ad}
            </span>
            {i < adimlar.length - 1 && <ArrowRight className="size-3.5 text-muted-foreground" aria-hidden />}
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <h2 className="text-xl font-semibold">{baslik}</h2>
          <p className="text-sm text-muted-foreground">{aciklama}</p>
          {ikincil.length > 0 && (
            <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {ikincil.map((x) => (
                <Link key={x.yol} to={x.yol} className="text-primary underline-offset-4 hover:underline">
                  {x.ad}
                </Link>
              ))}
            </p>
          )}
        </div>
        <Link
          to={hedef}
          className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
        >
          {dugme} <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
    </section>
  );
}
