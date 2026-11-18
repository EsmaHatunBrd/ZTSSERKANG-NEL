import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Trash2 } from "lucide-react";
import { useFieldArray, useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { api, cagir, hataMetni, type ApiHatasi } from "@/api/istemci";
import { anahtar } from "@/api/sorgular/anahtarlar";
import type { Sema } from "@/api/tipler";
import { useRecete, useReceteKaydet } from "@/api/sorgular/urunler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import type { ReceteSatiri } from "@/api/tipler";
import { sayiApi, sayiGecerli } from "@/yardimcilar/sayi";
import { FIRE_ARALIK_MESAJI, fireOraniMetni, fireYuzdeHatasi, fireYuzdeMetni } from "../urun/yardimci";
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
  // Mevcut reçeteden getirilen satırın formda görünmeyen alanları: yeni sürümde aynen korunur.
  seviye: z.number().int().nullable().optional(),
  zs_elle: z.string().nullable().optional(),
  para_birimi_elle: z.string().nullable().optional(),
});

export const receteSemasi = z.object({
  urun_kodu: z.string().trim().min(1, "Ürün kodu zorunlu"),
  satirlar: z.array(satirSemasi).min(1, "En az bir satır girin"),
  neden: z.string().trim().min(1, "Neden zorunlu: değişikliğin nedenini yazın").max(300, "Neden en çok 300 karakter olabilir"),
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
/** API sayısı -> formda gösterilen Türkçe metin (virgüllü). */
const virgul = (v: string | null | undefined) => (v == null ? "" : v.replace(".", ","));

/**
 * Mevcut reçete satırı -> form satırı. Fire yalnız satıra elle yazılmışsa (fire_override) gelir; kuraldan gelen fire boş kalır,
 * böylece yeni sürümde de kurala bağlı kalır.
 */
function formSatiri(r: ReceteSatiri): SatirDegeri {
  return {
    malzeme_kodu: r.malzeme_kodu,
    ad: r.ad ?? "",
    miktar: virgul(r.miktar),
    birim: r.birim ?? "",
    fire_override: r.fire_override != null ? virgul(fireYuzdeMetni(r.fire_override)) : "",
    brut_miktar_elle: virgul(r.brut_miktar_elle),
    birim_fiyat_elle: virgul(r.birim_fiyat_elle),
    dugum_tipi: r.dugum_tipi,
    seviye: r.seviye ?? null,
    zs_elle: r.zs_elle ?? null,
    para_birimi_elle: r.para_birimi_elle ?? null,
  };
}

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
  if (s.seviye != null) g.seviye = s.seviye;
  if (s.zs_elle) g.zs_elle = s.zs_elle as Sema["ReceteSatirGiris"]["zs_elle"];
  if (s.para_birimi_elle) g.para_birimi_elle = s.para_birimi_elle;
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
  neden,
  bekliyor,
  onOnayla,
  onVazgec,
}: {
  kod: string;
  senaryoId: number | null;
  yeniSatir: number;
  neden: string;
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
      <p className="text-sm">
        <span className="text-muted-foreground">Neden: </span>
        {neden}
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
    getValues,
    formState: { errors },
  } = useForm<FormDegerleri>({
    resolver: zodResolver(receteSemasi),
    defaultValues: { urun_kodu: urunKodu ?? "", satirlar: [BOS_SATIR], neden: "" },
  });
  const { fields, append, remove, replace } = useFieldArray({ control, name: "satirlar" });

  const hata = (ekle.error as ApiHatasi | null) ?? null;
  const [bekleyen, setBekleyen] = useState<{ kod: string; satirlar: Sema["ReceteSatirGiris"][]; neden: string } | null>(null);

  // "Mevcut reçeteyi getir": seçili çalışmadaki aktif reçetenin satırları forma dolar (düzenleyip yeni sürüm olarak kaydedilir).
  const qc = useQueryClient();
  const [getirOnayi, setGetirOnayi] = useState<string | null>(null);
  const [getirMesaji, setGetirMesaji] = useState<string | null>(null);
  const [getirHatasi, setGetirHatasi] = useState<string | null>(null);
  const [getiriliyor, setGetiriliyor] = useState(false);

  async function getirUygula(kod: string) {
    if (senaryoId == null) {
      setSenaryoYok(true);
      return;
    }
    setGetiriliyor(true);
    try {
      const recete = await qc.fetchQuery({
        queryKey: [...anahtar.recete(kod, senaryoId), null],
        queryFn: () => cagir(api.GET("/api/v1/urunler/{kod}/recete", { params: { path: { kod }, query: { senaryo: senaryoId } } })),
        staleTime: 0,
      });
      if (recete.satirlar.length === 0) {
        setGetirMesaji(`${kod} ürününün bu çalışmada reçetesi yok; satırları elle girin.`);
        return;
      }
      replace(recete.satirlar.map(formSatiri));
      setGetirMesaji(`Mevcut reçete getirildi: Versiyon ${recete.versiyon}, ${recete.satirlar.length} satır. Düzenleyip kaydedin.`);
    } catch (e) {
      setGetirHatasi(hataMetni(e as ApiHatasi));
    } finally {
      setGetiriliyor(false);
    }
  }

  function mevcutuGetir() {
    const kod = getValues("urun_kodu").trim();
    setGetirMesaji(null);
    setGetirHatasi(null);
    if (!kod) {
      setGetirMesaji("Önce ürün kodunu yazın.");
      return;
    }
    // Formda yazılmış satır varsa üzerine yazmadan önce sorulur.
    if (getValues("satirlar").some((x) => x.malzeme_kodu.trim() !== "")) setGetirOnayi(kod);
    else void getirUygula(kod);
  }

  function gonder(d: FormDegerleri) {
    if (senaryoId == null) {
      setSenaryoYok(true);
      return;
    }
    setSenaryoYok(false);
    // Reçete yazımı tüm satırları değiştirir: önce mevcut/yeni satır sayısıyla onay istenir.
    setBekleyen({ kod: d.urun_kodu, satirlar: d.satirlar.map(apiSatiri), neden: d.neden.trim() });
  }

  function onayla() {
    if (!bekleyen || senaryoId == null) return;
    ekle.mutate(
      { kod: bekleyen.kod, senaryo: senaryoId, satirlar: bekleyen.satirlar, neden: bekleyen.neden },
      { onSettled: () => setBekleyen(null) },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="max-w-3xl text-sm text-amber-700 dark:text-amber-400">
        {gomulu
          ? "Reçetenin tüm satırlarını girin; kaydedince ilk reçete versiyonu açılır ve hesap gelir."
          : "Bu işlem ürün için yeni bir reçete versiyonu oluşturur; reçetenin tüm satırlarını girin ya da mevcut reçeteyi getirip düzenleyin."}
      </p>

      <form noValidate onSubmit={handleSubmit(gonder)} className="flex flex-col gap-4" aria-label="Elle reçete girişi">
        {urunKodu === undefined && (
          <div className="flex flex-col gap-1">
            <label htmlFor="recete-urun" className="text-sm font-medium">
              Ürün kodu
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <Input id="recete-urun" className="max-w-xs" aria-invalid={!!errors.urun_kodu} {...register("urun_kodu")} />
              <Button type="button" variant="outline" size="sm" onClick={mevcutuGetir} disabled={getiriliyor}>
                <Download aria-hidden />
                {getiriliyor ? "Getiriliyor…" : "Mevcut reçeteyi getir"}
              </Button>
            </div>
            {errors.urun_kodu && <p className="text-sm text-destructive">{errors.urun_kodu.message}</p>}
            {getirMesaji && (
              <p role="status" className="text-sm text-muted-foreground">
                {getirMesaji}
              </p>
            )}
            {getirHatasi && (
              <p role="alert" className="text-sm text-destructive">
                {getirHatasi}
              </p>
            )}
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

        <div className="flex max-w-3xl flex-col gap-1">
          <label htmlFor="recete-neden" className="text-sm font-medium">
            Neden (zorunlu)
          </label>
          <Input
            id="recete-neden"
            placeholder="Ör. Kapak tedarikçisi değişti"
            aria-invalid={!!errors.neden}
            aria-describedby={errors.neden ? "recete-neden-hata" : undefined}
            {...register("neden")}
          />
          {errors.neden ? (
            <p id="recete-neden-hata" className="text-sm text-destructive">
              {errors.neden.message}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">Değişiklik Günlüğünde reçete sürümüyle birlikte görünür.</p>
          )}
        </div>

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
          neden={bekleyen.neden}
          bekliyor={ekle.isPending}
          onOnayla={onayla}
          onVazgec={() => setBekleyen(null)}
        />
      )}

      {getirOnayi && (
        <OnayDiyalogu
          baslik="Formdaki satırlar değişecek"
          onayMetni="Mevcut reçeteyi getir"
          onOnayla={() => {
            const kod = getirOnayi;
            setGetirOnayi(null);
            void getirUygula(kod);
          }}
          onVazgec={() => setGetirOnayi(null)}
        >
          <p>{`Formdaki satırlar silinip ${getirOnayi} ürününün bu çalışmadaki mevcut reçetesi yüklenecek.`}</p>
        </OnayDiyalogu>
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
