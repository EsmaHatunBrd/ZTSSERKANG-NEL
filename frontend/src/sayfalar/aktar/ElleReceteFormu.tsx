import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { useFieldArray, useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import type { Sema } from "@/api/tipler";
import { useRecete, useReceteKaydet } from "@/api/sorgular/urunler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { sayiApi, sayiGecerli } from "@/yardimcilar/sayi";
import { FIRE_ARALIK_MESAJI, fireOraniMetni, fireYuzdeHatasi } from "../urun/yardimci";
import { Girdi as Input } from "@/bilesenler/Girdi";

const sayiOpsiyonel = z
  .string()
  .trim()
  .refine((v) => v === "" || sayiGecerli(v), "Sayı olmalı");

const satirSemasi = z.object({
  malzeme_kodu: z.string().trim().min(1, "Malzeme kodu zorunlu"),
  ad: z.string().trim(),
  miktar: z
    .string()
    .trim()
    .min(1, "Miktar zorunlu")
    .refine((v) => v === "" || sayiGecerli(v), "Miktar sayı olmalı"),
  birim: z.string().trim(),
  // Ürün ekranındaki gibi yüzde (0-100); API'ye oran olarak gider.
  fire_override: sayiOpsiyonel.refine((v) => v === "" || fireYuzdeHatasi(v) === null, FIRE_ARALIK_MESAJI),
  brut_miktar_elle: sayiOpsiyonel,
  birim_fiyat_elle: sayiOpsiyonel,
  dugum_tipi: z.enum(["yaprak", "ara_mamul"]),
});

export const receteSemasi = z.object({
  urun_kodu: z.string().trim().min(1, "Ürün kodu zorunlu"),
  satirlar: z.array(satirSemasi).min(1, "En az bir satır girin"),
});

type FormDegerleri = z.infer<typeof receteSemasi>;
type SatirDegeri = FormDegerleri["satirlar"][number];

const BOS_SATIR: SatirDegeri = {
  malzeme_kodu: "",
  ad: "",
  miktar: "",
  birim: "",
  fire_override: "",
  brut_miktar_elle: "",
  birim_fiyat_elle: "",
  dugum_tipi: "yaprak",
};

const nokta = (v: string) => sayiApi(v) ?? v;

/** Form satırı -> API gövdesi; boş isteğe bağlı alanlar gönderilmez. */
function apiSatiri(s: SatirDegeri): Sema["ReceteSatirGiris"] {
  const g: Sema["ReceteSatirGiris"] = {
    malzeme_kodu: s.malzeme_kodu,
    ad: s.ad,
    miktar: nokta(s.miktar),
    dugum_tipi: s.dugum_tipi,
  };
  if (s.birim) g.birim = s.birim;
  if (s.fire_override) g.fire_override = fireOraniMetni(s.fire_override) ?? undefined;
  if (s.brut_miktar_elle) g.brut_miktar_elle = nokta(s.brut_miktar_elle);
  if (s.birim_fiyat_elle) g.birim_fiyat_elle = nokta(s.birim_fiyat_elle);
  return g;
}

const SELECT_SINIFI =
  "h-8 w-full rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

function Alan({ etiket, hata, children }: { etiket: string; hata?: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-xs text-muted-foreground" aria-hidden>
        {etiket}
      </span>
      {children}
      {hata && <p className="text-xs text-destructive">{hata}</p>}
    </div>
  );
}

function ReceteDegisimOnayi({
  kod,
  senaryoId,
  yeniSatir,
  bekliyor,
  onOnayla,
  onVazgec,
}: {
  kod: string;
  senaryoId: number | null;
  yeniSatir: number;
  bekliyor: boolean;
  onOnayla: () => void;
  onVazgec: () => void;
}) {
  const mevcut = useRecete(kod, senaryoId);
  // Reçetesi olmayan (ya da bulunamayan) ürün için 0 satır kabul edilir.
  const mevcutSatir = mevcut.isPending ? null : (mevcut.data?.satirlar.length ?? 0);
  return (
    <OnayDiyalogu
      baslik={mevcutSatir === 0 ? "İlk reçete kaydedilecek" : "Reçete değiştirilecek"}
      onayMetni="Onayla ve kaydet"
      bekliyor={bekliyor || mevcut.isPending}
      onOnayla={onOnayla}
      onVazgec={onVazgec}
    >
      <p>
        {mevcutSatir === 0
          ? `${kod} ürünü için bu çalışmada ilk reçete versiyonu açılır.`
          : `${kod} ürünü için yeni bir reçete versiyonu açılır; önceki versiyon geçmişte kalır.`}
      </p>
      <p className="font-medium">
        {mevcutSatir === null
          ? "Mevcut reçete okunuyor…"
          : mevcutSatir === 0
            ? `Bu çalışmada reçetesi yok: ilk reçete versiyonu ${yeniSatir} satırla açılır ve ürün çalışmaya dahil olur`
            : `Mevcut reçete ${mevcutSatir} satır → yeni ${yeniSatir} satır; tüm reçete değiştirilecek`}
      </p>
    </OnayDiyalogu>
  );
}

interface Props {
  /** Doluysa ürün kodu sabittir (alan gizlenir): ürün ekranındaki reçetesiz ürün akışı. */
  urunKodu?: string;
  /** Ürün ekranına gömülü kullanım: Veri Aktar'a özgü açıklama ve "Ürün ekranına git" bağlantısı gösterilmez. */
  gomulu?: boolean;
}

export function ElleReceteFormu({ urunKodu, gomulu = false }: Props = {}) {
  const { senaryoId } = useSenaryo();
  const { kilitli, neden: kilitNedeni } = useYazmaKilidi();
  const ekle = useReceteKaydet();
  const [senaryoYok, setSenaryoYok] = useState(false);
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<FormDegerleri>({
    resolver: zodResolver(receteSemasi),
    defaultValues: { urun_kodu: urunKodu ?? "", satirlar: [BOS_SATIR] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "satirlar" });

  const hata = (ekle.error as ApiHatasi | null) ?? null;
  const [bekleyen, setBekleyen] = useState<{ kod: string; satirlar: Sema["ReceteSatirGiris"][] } | null>(null);

  function gonder(d: FormDegerleri) {
    if (senaryoId == null) {
      setSenaryoYok(true);
      return;
    }
    setSenaryoYok(false);
    // Reçete yazımı tüm satırları değiştirir: önce mevcut/yeni satır sayısıyla onay istenir.
    setBekleyen({ kod: d.urun_kodu, satirlar: d.satirlar.map(apiSatiri) });
  }

  function onayla() {
    if (!bekleyen || senaryoId == null) return;
    ekle.mutate({ kod: bekleyen.kod, senaryo: senaryoId, satirlar: bekleyen.satirlar }, { onSettled: () => setBekleyen(null) });
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-sm text-amber-700 dark:text-amber-400">
        {gomulu
          ? "Reçetenin tüm satırlarını girin; kaydedince ilk reçete versiyonu açılır ve hesap gelir."
          : "Bu işlem ürün için yeni bir reçete versiyonu oluşturur; reçetenin tüm satırlarını girin."}
      </p>

      <form noValidate onSubmit={handleSubmit(gonder)} className="flex flex-col gap-4" aria-label="Elle reçete girişi">
        {urunKodu === undefined && (
          <div className="flex max-w-xs flex-col gap-1">
            <label htmlFor="recete-urun" className="text-sm font-medium">
              Ürün kodu
            </label>
            <Input id="recete-urun" aria-invalid={!!errors.urun_kodu} {...register("urun_kodu")} />
            {errors.urun_kodu && <p className="text-sm text-destructive">{errors.urun_kodu.message}</p>}
          </div>
        )}

        <ol className="flex flex-col gap-3">
          {fields.map((f, i) => {
            const e = errors.satirlar?.[i];
            const n = i + 1;
            return (
              <li key={f.id} className="rounded-lg border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">Satır {n}</span>
                  {fields.length > 1 && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => remove(i)} aria-label={`Satır ${n} sil`}>
                      <Trash2 aria-hidden />
                      Sil
                    </Button>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Alan etiket="Malzeme kodu" hata={e?.malzeme_kodu?.message}>
                    <Input aria-label={`Malzeme kodu ${n}`} aria-invalid={!!e?.malzeme_kodu} {...register(`satirlar.${i}.malzeme_kodu`)} />
                  </Alan>
                  <Alan etiket="Ad" hata={e?.ad?.message}>
                    <Input aria-label={`Ad ${n}`} {...register(`satirlar.${i}.ad`)} />
                  </Alan>
                  <Alan etiket="Miktar" hata={e?.miktar?.message}>
                    <Input
                      aria-label={`Miktar ${n}`}
                      inputMode="decimal"
                      aria-invalid={!!e?.miktar}
                      {...register(`satirlar.${i}.miktar`)}
                    />
                  </Alan>
                  <Alan etiket="Birim" hata={e?.birim?.message}>
                    <Input aria-label={`Birim ${n}`} {...register(`satirlar.${i}.birim`)} />
                  </Alan>
                  <Alan etiket="Fire % (0-100)" hata={e?.fire_override?.message}>
                    <Input aria-label={`Fire % ${n}`} inputMode="decimal" {...register(`satirlar.${i}.fire_override`)} />
                  </Alan>
                  <Alan etiket="Brüt miktar (elle)" hata={e?.brut_miktar_elle?.message}>
                    <Input aria-label={`Elle brüt miktar ${n}`} inputMode="decimal" {...register(`satirlar.${i}.brut_miktar_elle`)} />
                  </Alan>
                  <Alan etiket="Birim fiyat (elle; boşsa liste)" hata={e?.birim_fiyat_elle?.message}>
                    <Input aria-label={`Elle birim fiyat ${n}`} inputMode="decimal" {...register(`satirlar.${i}.birim_fiyat_elle`)} />
                  </Alan>
                  <Alan etiket="Düğüm tipi">
                    <select aria-label={`Düğüm tipi ${n}`} className={SELECT_SINIFI} {...register(`satirlar.${i}.dugum_tipi`)}>
                      <option value="yaprak">Yaprak (malzeme)</option>
                      <option value="ara_mamul">Ara mamul</option>
                    </select>
                  </Alan>
                </div>
              </li>
            );
          })}
        </ol>
        {errors.satirlar?.message && <p className="text-sm text-destructive">{errors.satirlar.message}</p>}

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => append(BOS_SATIR)}>
            <Plus aria-hidden />
            Satır ekle
          </Button>
          <Button type="submit" disabled={ekle.isPending || kilitli} title={kilitNedeni}>
            {ekle.isPending ? "Kaydediliyor…" : "Reçeteyi kaydet"}
          </Button>
        </div>
      </form>

      {bekleyen && (
        <ReceteDegisimOnayi
          kod={bekleyen.kod}
          senaryoId={senaryoId}
          yeniSatir={bekleyen.satirlar.length}
          bekliyor={ekle.isPending}
          onOnayla={onayla}
          onVazgec={() => setBekleyen(null)}
        />
      )}

      {senaryoYok && (
        <div role="alert" className="text-sm text-destructive">
          Senaryo henüz yüklenmedi, biraz sonra tekrar deneyin.
        </div>
      )}
      {hata && (
        <div role="alert" className="max-w-3xl rounded-md border border-destructive/40 p-3 text-sm text-destructive">
          {hataMetni(hata)}
        </div>
      )}
      {ekle.data && (
        <p role="status" className="max-w-3xl rounded-md border p-3 text-sm">
          {`Reçete kaydedildi: Versiyon ${ekle.data.versiyon}, ${ekle.data.satir_sayisi} satır. `}
          {!gomulu && (
            <Link
              to={`/urunler/${encodeURIComponent(ekle.variables?.kod ?? "")}?senaryo=${senaryoId}`}
              className="text-primary underline-offset-4 hover:underline"
            >
              Ürün ekranına git
            </Link>
          )}
        </p>
      )}
    </div>
  );
}
