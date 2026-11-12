import { useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { History, PackagePlus, Star } from "lucide-react";
import { useUrunler } from "@/api/sorgular/urunler";
import type { ApiHatasi } from "@/api/istemci";
import type { DashboardSatiri } from "@/api/tipler";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button, buttonVariants } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";
import { Input } from "@/bilesenler/ui/input";
import { useSenaryoSayfasi } from "@/yardimcilar/sayfalama";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { ambalajMetni } from "@/yardimcilar/ambalaj";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { FavoriDugmesi } from "@/bilesenler/FavoriDugmesi";
import { favoriDegistir, favorileriOku, sonAcilaniKaydet, sonAcilanlariOku } from "@/yardimcilar/sonAcilanlar";

const BOYUT = 50;
const tr = (s: string) => s.toLocaleLowerCase("tr");

const SUTUNLAR: SutunTanimi<DashboardSatiri>[] = [
  { accessorKey: "kod", header: "Kod" },
  { accessorKey: "ad", header: "Ürün" },
  {
    accessorKey: "ambalaj_hacmi",
    header: "Ambalaj",
    cell: ({ row }) => (
      <span className="block text-right tabular-nums">{ambalajMetni(row.original.ambalaj_etiket, row.original.ambalaj_hacmi)}</span>
    ),
  },
  { accessorKey: "hat", header: "Hat" },
];

/** "Çalışma dışı ürünleri göster" açıkken: üye olmayan (bu senaryoda reçetesi olmayan) ürünler hata metniyle gelir. */
const DURUM_SUTUNU: SutunTanimi<DashboardSatiri> = {
  id: "durum",
  header: "Durum",
  enableSorting: false,
  cell: ({ row }) =>
    row.original.hata ? (
      <Badge variant="outline" title={row.original.hata}>
        Çalışma dışı
      </Badge>
    ) : (
      <Badge variant="secondary">Dahil</Badge>
    ),
};

/** Favoriler / Son açılanlar bölümü: ürün adı + kod çipleri; ad listedeki satırdan, bulunamazsa yalnız kod. */
function UrunCipleri({
  baslik,
  simge,
  kodlar,
  satirlar,
  senaryoId,
}: {
  baslik: string;
  simge: ReactNode;
  kodlar: string[];
  satirlar: DashboardSatiri[];
  senaryoId: number;
}) {
  if (kodlar.length === 0) return null;
  const adlar = new Map(satirlar.map((s) => [s.kod, s.ad]));
  return (
    <section aria-label={baslik} className="flex flex-col gap-1.5">
      <h2 className="flex items-center gap-1.5 text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {simge}
        {baslik}
      </h2>
      <ul className="flex flex-wrap gap-1.5">
        {kodlar.map((kod) => {
          const ad = adlar.get(kod);
          return (
            <li key={kod}>
              <Link
                to={`/urunler/${encodeURIComponent(kod)}?senaryo=${senaryoId}`}
                className="inline-flex max-w-[28rem] items-center gap-1.5 rounded-full border bg-card px-3 py-1 text-sm transition-colors hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {ad && <span className="truncate">{ad}</span>}
                <span className={cn("tabular-nums", ad && "text-xs text-muted-foreground")}>{kod}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** Menüdeki "Ürün Maliyeti" girişi: ürün seçilir, satır `/urunler/:kod?senaryo=` ekranına gider. */
export default function Urunler() {
  const { senaryoId } = useSenaryo();
  const gezin = useNavigate();
  const [arama, setArama] = useState("");
  const [favoriler, setFavoriler] = useState<string[]>(() => favorileriOku());
  const [sonAcilanlar, setSonAcilanlar] = useState<string[]>(() => sonAcilanlariOku());
  const [params] = useSearchParams();
  const [tum, setTum] = useState(() => params.get("tum") === "1"); // Veri Kontrolü "Reçetesi olmayan ürün" bağlantısından

  const [sayfa, setSayfa] = useSenaryoSayfasi(senaryoId);

  const urunler = useUrunler(senaryoId, { sayfa, boyut: BOYUT, tum: tum || undefined });
  // Favori sütunu `favoriler`e bağlı olursa her tıklamada hücre bileşeni yeniden mount olur (odak kaybı). Sütun sabit kalır;
  // hücre güncel listeyi ref'ten okur (Urunler her favori değişiminde yeniden çizildiği için hücre de yeniden çizilir).
  const favorilerRef = useRef(favoriler);
  favorilerRef.current = favoriler;
  const sutunlar = useMemo<SutunTanimi<DashboardSatiri>[]>(() => {
    const favoriSutunu: SutunTanimi<DashboardSatiri> = {
      id: "favori",
      header: () => <span className="sr-only">Favori</span>,
      enableSorting: false,
      meta: { sinif: "w-10 pr-0" },
      cell: ({ row }) => (
        <FavoriDugmesi
          secili={favorilerRef.current.includes(row.original.kod)}
          onDegistir={() => setFavoriler(favoriDegistir(row.original.kod))}
        />
      ),
    };
    return tum ? [favoriSutunu, ...SUTUNLAR, DURUM_SUTUNU] : [favoriSutunu, ...SUTUNLAR];
  }, [tum]);
  const satirlar = useMemo(() => urunler.data?.kayitlar ?? [], [urunler.data]);
  const gorunen = useMemo(() => {
    const q = tr(arama.trim());
    return q ? satirlar.filter((s) => tr(s.kod).includes(q) || tr(s.ad).includes(q)) : satirlar;
  }, [satirlar, arama]);

  const toplam = urunler.data?.toplam ?? null;
  const sayfaSayisi = Math.max(1, Math.ceil((toplam ?? 0) / BOYUT));
  const sayfali = toplam !== null && toplam > BOYUT;

  if (senaryoId === null) {
    return (
      <section className="p-4">
        <SayfaBasligi baslik="Ürünler" />
        <p className="mt-2 text-muted-foreground">Başlamak için yukarıdan bir senaryo seçin.</p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaBasligi
        baslik="Ürünler"
        altBaslik="Maliyetini görmek istediğiniz ürünü seçin."
        eylemler={
          <Link to={`/veri-girisi?senaryo=${senaryoId}`} className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
            <PackagePlus aria-hidden />
            Yeni ürün
          </Link>
        }
      />
      {(favoriler.length > 0 || sonAcilanlar.length > 0) && (
        <div className="flex flex-col gap-3 rounded-xl border bg-muted/30 p-3">
          <UrunCipleri
            baslik="Favoriler"
            simge={<Star className="size-3.5" aria-hidden />}
            kodlar={favoriler}
            satirlar={satirlar}
            senaryoId={senaryoId}
          />
          <UrunCipleri
            baslik="Son açılanlar"
            simge={<History className="size-3.5" aria-hidden />}
            kodlar={sonAcilanlar}
            satirlar={satirlar}
            senaryoId={senaryoId}
          />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Input
          type="search"
          aria-label="Ürün ara"
          placeholder={sayfali ? "Bu sayfadaki ürünlerde ara" : "Kod veya ürün adı ara"}
          value={arama}
          onChange={(e) => setArama(e.target.value)}
          className="max-w-xs"
        />
        <label className="flex items-center gap-2 text-sm" title="Bu çalışmada reçetesi olmayan (üye olmayan) ürünleri de listeler">
          <input
            type="checkbox"
            checked={tum}
            onChange={(e) => {
              setTum(e.target.checked);
              setSayfa(1);
            }}
          />
          Çalışma dışı ürünleri göster
        </label>
        {sayfali && <span className="text-xs text-muted-foreground">Arama yalnızca bu sayfayı kapsar.</span>}
      </div>
      <div className="overflow-x-auto">
        <VeriTablosu
          veri={gorunen}
          sutunlar={sutunlar}
          yukleniyor={urunler.isPending}
          hata={(urunler.error as ApiHatasi | null) ?? null}
          bosMetin="Ürün bulunamadı"
          bosAciklama={
            tum
              ? "Hiç ürün kartı yok — Veri Girişi'nden yeni ürün açın"
              : "Bu çalışmada reçetesi olan ürün yok — yeni ürün açın ya da çalışma dışı ürünleri gösterin"
          }
          satirTikla={(s) => {
            setSonAcilanlar(sonAcilaniKaydet(s.kod));
            gezin(`/urunler/${encodeURIComponent(s.kod)}?senaryo=${senaryoId}`);
          }}
        />
      </div>
      {sayfali && (
        <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" size="sm" disabled={sayfa <= 1} onClick={() => setSayfa(sayfa - 1)}>
            Önceki
          </Button>
          <span aria-live="polite">
            Sayfa {sayfa} / {sayfaSayisi}
          </span>
          <Button variant="outline" size="sm" disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa(sayfa + 1)}>
            Sonraki
          </Button>
        </nav>
      )}
    </section>
  );
}
