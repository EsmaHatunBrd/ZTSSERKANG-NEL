import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PackagePlus } from "lucide-react";
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

/** Menüdeki "Ürün Maliyeti" girişi: ürün seçilir, satır `/urunler/:kod?senaryo=` ekranına gider. */
export default function Urunler() {
  const { senaryoId } = useSenaryo();
  const gezin = useNavigate();
  const [arama, setArama] = useState("");
  const [params] = useSearchParams();
  const [tum, setTum] = useState(() => params.get("tum") === "1"); // Veri Kontrolü "Reçetesi olmayan ürün" bağlantısından

  const [sayfa, setSayfa] = useSenaryoSayfasi(senaryoId);

  const urunler = useUrunler(senaryoId, { sayfa, boyut: BOYUT, tum: tum || undefined });
  const sutunlar = useMemo(() => (tum ? [...SUTUNLAR, DURUM_SUTUNU] : SUTUNLAR), [tum]);
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
          satirTikla={(s) => gezin(`/urunler/${encodeURIComponent(s.kod)}?senaryo=${senaryoId}`)}
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
