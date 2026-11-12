import type { ReactNode } from "react";
import { Download } from "lucide-react";
import type { StokDevriAktarimSatiri } from "@/api/tipler";
import { buttonVariants } from "@/bilesenler/ui/button";
import { cn } from "@/lib/utils";
import { paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { AktarimFormu } from "./AktarimFormu";
import { FarkTablosu, Sayac } from "./FarkTablosu";

const SABLON_ADRESI = "/api/v1/aktarim/stok-devri/sablon.xlsx";

type Alan = "adet" | "birim_maliyet" | "enflasyon" | "uretim_adedi";
const BOS: Record<Alan, string> = { adet: "—", birim_maliyet: "—", enflasyon: "parametre", uretim_adedi: "geçen yıl satışı" };
const BICIM: Record<Alan, (v: string) => string> = {
  adet: (v) => paraBicimle(v, "", 0),
  birim_maliyet: (v) => paraBicimle(v, "", 2),
  enflasyon: (v) => yuzdeBicimle(v, 1),
  uretim_adedi: (v) => paraBicimle(v, "", 0),
};
const ALANLAR: Alan[] = ["adet", "birim_maliyet", "enflasyon", "uretim_adedi"];
const SUTUNLAR = ["Satır", "Ürün kodu", "Ürün adı", "Stok adedi", "Birim maliyet (TL)", "Enflasyon", "Üretim adedi"];

const goster = (a: Alan, v: string | null | undefined) => (v == null || v === "" ? BOS[a] : BICIM[a](v));

/** Hücre: değişen satırda eski değer farklıysa "eski → yeni". */
function hucre(s: StokDevriAktarimSatiri, a: Alan): ReactNode {
  const yeni = goster(a, s[a]);
  const eski = s.eski;
  if (!eski || !(a in eski) || (eski[a] ?? null) === (s[a] ?? null)) return yeni;
  return (
    <span className="whitespace-nowrap">
      <span className="text-muted-foreground line-through">{goster(a, eski[a])}</span> → <span className="font-medium">{yeni}</span>
    </span>
  );
}

const satirHucreleri = (s: StokDevriAktarimSatiri): ReactNode[] => [
  s.satir_no,
  s.urun_kodu,
  s.ad ?? "—",
  ...ALANLAR.map((a) => hucre(s, a)),
];

/** Veri Aktar → Stokta kalan: şablonu indir, doldur, önizle, nedenle uygula. Kayıtlar seçili çalışmaya yazılır. */
export function StokDevriAktar() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <a href={SABLON_ADRESI} download className={cn(buttonVariants({ variant: "outline" }))}>
          <Download aria-hidden />
          Şablonu indir
        </a>
      </div>
      <AktarimFormu
        tip="stok-devri"
        ad="Stokta kalanı içe aktar"
        aciklama="Şablon sütunları: ürün kodu, stok adedi, stok birim maliyeti; isteğe bağlı enflasyon (boşsa parametre) ve bu yıl üretim adedi (boşsa geçen yıl satışı). Seçili çalışmadaki kayıtlarla karşılaştırılır; yalnız yeni ve değişen ürünler yazılır, her değişiklik geçmişe kaydedilir."
        onizlemeGoster={(o) => {
          const eksik = Object.entries(o.sutunlar).filter(([, bulunan]) => bulunan === null);
          return (
            <>
              {eksik.length > 0 && (
                <p className="text-sm text-amber-700 dark:text-amber-400">
                  Dosyada bulunamayan sütunlar: {eksik.map(([s]) => s).join(", ")}
                </p>
              )}
              <div className="flex flex-wrap gap-x-6">
                <Sayac etiket="Yeni" deger={o.yeni} />
                <Sayac etiket="Değişen" deger={o.degisen} />
                <Sayac etiket="Aynı" deger={o.ayni} />
                <Sayac etiket="Hatalı" deger={o.hatalar.length} />
              </div>
              <FarkTablosu baslik="Hatalı satırlar" sutunlar={["Satır", "Hata"]} satirlar={o.hatalar.map((h) => [h.satir_no, h.mesaj])} />
              <FarkTablosu
                baslik="Yeni kayıtlar"
                sutunlar={SUTUNLAR}
                satirlar={o.satirlar.filter((s) => s.durum === "yeni").map(satirHucreleri)}
                sagda={[3, 4, 5, 6]}
              />
              <FarkTablosu
                baslik="Değişen kayıtlar"
                sutunlar={SUTUNLAR}
                satirlar={o.satirlar.filter((s) => s.durum === "degisen").map(satirHucreleri)}
                sagda={[3, 4, 5, 6]}
              />
            </>
          );
        }}
        hatalar={(o) => o.hatalar.map((h) => String(h.satir_no))}
        yazilacakVar={(o) => o.yeni + o.degisen > 0}
        ozetKartlari={(u) => [
          { baslik: "Eklenen", deger: u.eklenen },
          { baslik: "Güncellenen", deger: u.guncellenen },
          { baslik: "Aynı", deger: u.ayni },
        ]}
      />
    </div>
  );
}
