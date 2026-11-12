import { Link } from "react-router-dom";
import { CircleAlert, CircleCheck, Info, TriangleAlert } from "lucide-react";
import type { YonetimOzeti } from "@/api/tipler";
import { Badge } from "@/bilesenler/ui/badge";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";
import { YonetimKarti } from "./YonetimKarti";

const sayi = (n: number | string) => new Intl.NumberFormat("tr-TR").format(Number(n));

interface KartProps {
  ozet: YonetimOzeti;
  sorgu: string;
}

const DURUM_SINIFI: Record<string, string> = {
  hata: "text-destructive",
  dikkat: "text-amber-700 dark:text-amber-300",
  bilgi: "text-sky-700 dark:text-sky-300",
};

/** Veri Kontrolü: hata / dikkat / bilgi sayıları ve ilgi bekleyen konular; tamamı Veri Kontrolü sayfasında. */
export function VeriKontroluKarti({ ozet, sorgu }: KartProps) {
  const v = ozet.veri_kontrolu;
  const sorunlar = v.sorunlar.filter((s) => s.durum !== "tamam");
  return (
    <YonetimKarti
      baslik="Veri Kontrolü"
      aciklama="Eksik ya da çelişkili veriler"
      bagla={`/veri-kontrolu${sorgu}`}
      baglaMetni="Veri Kontrolü"
    >
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm tabular-nums">
        <span className={cn("flex items-center gap-1.5 font-medium", v.hata > 0 ? "text-destructive" : "text-muted-foreground")}>
          <CircleAlert className="size-4" aria-hidden />
          {v.hata} hata
        </span>
        <span className={cn("flex items-center gap-1.5 font-medium", v.dikkat > 0 ? DURUM_SINIFI.dikkat : "text-muted-foreground")}>
          <TriangleAlert className="size-4" aria-hidden />
          {v.dikkat} dikkat
        </span>
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Info className="size-4" aria-hidden />
          {v.bilgi} bilgi
        </span>
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <CircleCheck className="size-4" aria-hidden />
          {v.tamam} tamam
        </span>
      </div>
      {sorunlar.length === 0 ? (
        <p className="text-sm text-muted-foreground">İlgi bekleyen konu yok.</p>
      ) : (
        <ul className="flex flex-col gap-1 text-sm">
          {sorunlar.map((s) => (
            <li key={s.kod} className="flex items-baseline justify-between gap-3">
              <Link to={`/veri-kontrolu${sorgu}`} className={cn("underline-offset-4 hover:underline", DURUM_SINIFI[s.durum])}>
                {s.baslik}
              </Link>
              <span className="font-medium tabular-nums">{sayi(s.sayi)}</span>
            </li>
          ))}
        </ul>
      )}
    </YonetimKarti>
  );
}

/** Stok etkisi: yalnız stok devri kaydı olan çalışmada (stok_etkisi null değilse) çizilir. */
export function StokEtkisiKarti({ ozet, sorgu }: KartProps) {
  const s = ozet.stok_etkisi;
  if (!s) return null;
  const etki = D(s.toplam_etki_tl);
  return (
    <YonetimKarti
      baslik="Stok etkisi"
      aciklama="Stoktan gelen birimlerin bu yılın maliyetine göre farkı (negatif: stok daha ucuz)"
      bagla={`/genel-bakis${sorgu}`}
      baglaMetni="Genel Bakış"
    >
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
        <div className="flex flex-col">
          <dt className="text-xs text-muted-foreground">Kayıt</dt>
          <dd className="font-semibold tabular-nums">{sayi(s.kayit_sayisi)}</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-xs text-muted-foreground">Etkilenen ürün</dt>
          <dd className="font-semibold tabular-nums">{sayi(s.etkili_urun)}</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-xs text-muted-foreground">Stok adedi</dt>
          <dd className="font-semibold tabular-nums">{paraBicimle(s.stok_adedi, "", 0)}</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-xs text-muted-foreground">Toplam etki</dt>
          <dd className={cn("font-semibold tabular-nums", etki.isNegative() && "text-destructive")}>{paraBicimle(etki, "TL", 0)}</dd>
        </div>
      </dl>
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        Satış ortalama maliyetten:
        <Badge variant={s.satis_ortalama_maliyetten ? "default" : "outline"}>{s.satis_ortalama_maliyetten ? "Açık" : "Kapalı"}</Badge>
      </p>
    </YonetimKarti>
  );
}

/** Hesaplanamayan ürünler: uyarı listesi; boşsa çizilmez. */
export function UyarilarKarti({ ozet, sorgu }: KartProps) {
  if (ozet.uyarilar.length === 0) return null;
  return (
    <YonetimKarti
      baslik="Hesaplanamayan ürünler"
      aciklama={`${ozet.uyarilar.length} ürünün maliyeti hesaplanamadı`}
      bagla={`/uyarilar${sorgu}`}
      baglaMetni="Ürün uyarıları"
    >
      <ul className="flex flex-col gap-1 text-sm">
        {ozet.uyarilar.map((u) => (
          <li key={u.kod} className="flex flex-wrap items-baseline gap-x-2">
            <Link to={`/urunler/${encodeURIComponent(u.kod)}${sorgu}`} className="font-medium underline-offset-4 hover:underline">
              {u.ad}
            </Link>
            <span className="font-mono text-xs text-muted-foreground">{u.kod}</span>
            <span className="text-destructive">{u.mesaj}</span>
          </li>
        ))}
      </ul>
    </YonetimKarti>
  );
}
