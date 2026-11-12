import { useMemo } from "react";
import { useGiderHavuzlari } from "@/api/sorgular/gider";
import type { UretimBilgisi } from "@/api/tipler";
import { Input } from "@/bilesenler/ui/input";
import { cn } from "@/lib/utils";
import { goster } from "@/yardimcilar/tarih";
import { sayiApi } from "@/yardimcilar/sayi";
import { hatListesi, PAZARLAR, SINIFLAR } from "@/yardimcilar/urunKarti";
import { GirdiHucresi } from "./GirdiHucresi";
import { ParametreGirdisi } from "./ParametreGirdisi";
import type { HedefAlani, Taslak, TaslakYamasi, UrunAlani } from "./Taslak";
import { fireYuzdeMetni, yuzdeOranMetni } from "./yardimci";

type HedefAnahtari = HedefAlani;
type UrunAnahtari = UrunAlani;

const HEDEF_ALANLARI: {
  anahtar: HedefAnahtari;
  etiket: string;
  ad: string;
  yuzde?: boolean;
}[] = [
  {
    anahtar: "vardiya_uretim_adedi",
    etiket: "Vardiya üretim adedi",
    ad: "Vardiya üretim adedi",
  },
  { anahtar: "dolum_personel", etiket: "Dolum personel", ad: "Dolum personel" },
  {
    anahtar: "etiketleme_adedi",
    etiket: "Etiketleme adedi",
    ad: "Etiketleme adedi",
  },
  {
    anahtar: "etiket_personel",
    etiket: "Etiket personel",
    ad: "Etiket personel",
  },
  {
    anahtar: "mal_kabul_miktar_kg",
    etiket: "Mal kabul miktarı (kg)",
    ad: "Mal kabul miktarı (kg)",
  },
  {
    anahtar: "mal_kabul_fire",
    etiket: "Mal kabul fire (%)",
    ad: "Mal kabul fire",
    yuzde: true,
  },
];

const SECIM_SINIFI =
  "h-7 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

interface Props {
  senaryoId: number;
  senaryoAdi: string | null;
  hesapTarihi: string;
  /** Hesabın (taslak uygulanmış) üretim bilgisi. */
  uretim: UretimBilgisi;
  /** Tek taslak; bu blok `urun`, `hedef` ve `parametreler.vardiya_saati` dilimlerini okur/yazar. */
  taslak: Taslak;
  onTaslak: (yama: TaslakYamasi) => void;
  /** Sunucu tabanı parametreleri (anahtar -> API değeri): "Eski değer" ipucu için. */
  taban?: Record<string, string>;
  /** Kayıtlı ürün kartının markası (boşsa sunucu addan türetir). */
  marka?: string | null;
}

function Alan({ etiket, children }: { etiket: string; children: React.ReactNode }) {
  return (
    <label className="flex items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground">{etiket}</span>
      {children}
    </label>
  );
}

/** Ürünün üretim girdileri: her alan hücreye yazılır, hesaba hemen girer ve tek "Kaydet" ile kalıcı yazılır. */
export function UretimBilgileri({ senaryoId, senaryoAdi, hesapTarihi, uretim, taslak, onTaslak, taban, marka }: Props) {
  const havuzlar = useGiderHavuzlari(senaryoId);
  const seciliHat = taslak.urun.hat ?? uretim.hat;

  const hatlar = useMemo(() => hatListesi(havuzlar.data?.kayitlar, seciliHat), [havuzlar.data, seciliHat]);

  const ov = taslak.hedef;
  const etkinHedef = (a: HedefAnahtari): string => ov[a] ?? uretim[a];
  const etkinPazarlama = ov.pazarlama_yonetim_uygula ?? uretim.pazarlama_yonetim_uygula;
  const etkinUrun = (a: Exclude<UrunAnahtari, "marka">): string => taslak.urun[a] ?? uretim[a];
  const urunTaslagi = (a: UrunAnahtari, deger: string | null) => onTaslak({ urun: { [a]: deger ?? undefined } });
  const hedefKaldir = (a: HedefAnahtari | "pazarlama_yonetim_uygula") => onTaslak({ hedef: { [a]: undefined } });

  const vurgu = (var_: boolean) => (var_ ? "border-primary" : undefined);

  return (
    <section aria-label="Üretim bilgileri" className="flex flex-col gap-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-base font-semibold">Üretim bilgileri</h2>
          <p className="text-xs text-muted-foreground">{`Hesap tarihi ${goster(hesapTarihi)}${senaryoAdi ? ` · ${senaryoAdi}` : ""}`}</p>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Yazdığınız değer hesaba hemen girer; kalıcı olması için üstteki &quot;Kaydet&quot; düğmesini kullanın.
      </p>

      <div className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
        <Alan etiket="Süzme miktar (kg)">
          <GirdiHucresi
            etiket="Süzme miktar (kg)"
            deger={etkinUrun("suzme_kg")}
            className={vurgu(taslak.urun.suzme_kg !== undefined)}
            onMetin={(m) => urunTaslagi("suzme_kg", m.trim() === "" ? null : sayiApi(m))}
          />
        </Alan>
        <Alan etiket="Net miktar (kg)">
          {/* Excel E137 "-": hesaplamalarda kullanılmaz; yalnızca Excel düzenini korumak için salt okunur gösterilir. */}
          <span
            title="Excel'de kullanılmıyor"
            aria-label="Net miktar (kg): Excel'de kullanılmıyor"
            className="inline-block min-w-16 px-2 text-right text-muted-foreground"
          >
            —
          </span>
        </Alan>
        <Alan etiket="Ambalaj (ml)">
          <GirdiHucresi
            etiket="Ambalaj (ml)"
            deger={etkinUrun("ambalaj_hacmi")}
            className={vurgu(taslak.urun.ambalaj_hacmi !== undefined)}
            onMetin={(m) => urunTaslagi("ambalaj_hacmi", m.trim() === "" ? null : sayiApi(m))}
          />
        </Alan>
        <Alan etiket="Üretim hattı">
          <select
            aria-label="Üretim hattı"
            value={etkinUrun("hat")}
            onChange={(e) => urunTaslagi("hat", e.target.value)}
            className={cn(SECIM_SINIFI, taslak.urun.hat !== undefined && "border-primary")}
          >
            {hatlar.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </Alan>
        <Alan etiket="Taze/Turşu sınıfı">
          <select
            aria-label="Taze/Turşu sınıfı"
            value={etkinUrun("taze_tursu_sinifi")}
            onChange={(e) => urunTaslagi("taze_tursu_sinifi", e.target.value)}
            className={cn(SECIM_SINIFI, taslak.urun.taze_tursu_sinifi !== undefined && "border-primary")}
          >
            {[...new Set([...SINIFLAR, etkinUrun("taze_tursu_sinifi")])].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Alan>
        <Alan etiket="Pazar">
          <select
            aria-label="Pazar"
            value={etkinUrun("pazar")}
            onChange={(e) => urunTaslagi("pazar", e.target.value)}
            className={cn(SECIM_SINIFI, taslak.urun.pazar !== undefined && "border-primary")}
          >
            {[...new Set([...PAZARLAR, etkinUrun("pazar")])].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </Alan>
        <Alan etiket="Marka">
          <Input
            aria-label="Marka"
            aria-description="Boş bırakılırsa ürün adından türetilir (ör. adında Berrak geçiyorsa Berrak)."
            title={
              taslak.urun.marka !== undefined
                ? `Eski değer: ${marka || "—"}`
                : "Boş bırakılırsa ürün adından türetilir. Liste fiyatı yalnız Berrak ürünlerinde hesaplanır."
            }
            placeholder="addan türetilir"
            value={taslak.urun.marka ?? marka ?? ""}
            onChange={(e) => onTaslak({ urun: { marka: e.target.value } })}
            className={cn("h-7 w-36 text-sm", taslak.urun.marka !== undefined && "border-primary")}
          />
        </Alan>
        <Alan etiket="Vardiya saati">
          <ParametreGirdisi
            etiket="Vardiya saati"
            deger={uretim.vardiya_saati}
            eskiDeger={taban ? (taban.vardiya_saati ?? null) : undefined}
            taslak={taslak.parametreler.vardiya_saati}
            onDegis={(d) => onTaslak({ parametreler: { vardiya_saati: d ?? undefined } })}
          />
        </Alan>
        {HEDEF_ALANLARI.map((f) => (
          <Alan key={f.anahtar} etiket={f.etiket}>
            <GirdiHucresi
              etiket={f.etiket}
              deger={f.yuzde ? fireYuzdeMetni(etkinHedef(f.anahtar)) : etkinHedef(f.anahtar)}
              className={vurgu(ov[f.anahtar] !== undefined)}
              onMetin={(m) => {
                if (m.trim() === "") return hedefKaldir(f.anahtar);
                const v = f.yuzde ? yuzdeOranMetni(m) : sayiApi(m);
                if (v !== null) onTaslak({ hedef: { [f.anahtar]: v } });
              }}
            />
          </Alan>
        ))}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            aria-label="Pazarlama/yönetim payı uygula"
            checked={etkinPazarlama}
            onChange={(e) => {
              onTaslak({
                hedef: { pazarlama_yonetim_uygula: e.target.checked },
              });
            }}
          />
          <span className="text-muted-foreground">Pazarlama/yönetim payı uygula</span>
        </label>
      </div>
    </section>
  );
}
