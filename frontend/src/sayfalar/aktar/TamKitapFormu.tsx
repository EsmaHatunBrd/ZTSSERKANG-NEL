import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useImportExcelTam } from "@/api/sorgular/aktar";
import { useSenaryolar } from "@/api/sorgular/senaryolar";
import type { Senaryo } from "@/api/tipler";
import { useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { Button } from "@/bilesenler/ui/button";
import { Girdi as Input } from "@/bilesenler/Girdi";
import { YuklemeYardimi } from "@/bilesenler/SablonIndir";
import { SonYuklemeSeridi } from "@/bilesenler/SonYuklemeSeridi";
import { ImportOzetiKartlari } from "./ImportOzetiKartlari";
import { MusavirSablonuSakla } from "./MusavirSablonuSakla";

const AZAMI_BOYUT = 25 * 1024 * 1024;

/** Dosya, react-hook-form'un derin kopyalamasında bozulacağı için formdan ayrı tutulur ve ayrıca doğrulanır. */
export const dosyaSemasi = z
  .custom<File>((v) => typeof File !== "undefined" && v instanceof File, "Excel dosyası seçin")
  .refine((f) => f.name.toLowerCase().endsWith(".xlsx"), "Yalnızca .xlsx dosyası yüklenebilir")
  .refine((f) => f.size <= AZAMI_BOYUT, "Dosya 25 MB'tan büyük olamaz");

export const tamKitapSemasi = z.object({
  sezon_ad: z.string().regex(/^\d{4}-\d{4}$/, "Sezon YYYY-YYYY biçiminde olmalı"),
  senaryo_ad: z.string().trim().min(1, "Senaryo adı zorunlu"),
  tur: z.enum(["fiyat_calismasi", "gerceklesen"]),
  kartlari_guncelle: z.boolean(),
});

type FormDegerleri = z.infer<typeof tamKitapSemasi>;

const SELECT_SINIFI =
  "h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

function HataMetni({ id, mesaj }: { id: string; mesaj?: string }) {
  if (!mesaj) return null;
  return (
    <p id={id} className="text-sm text-destructive">
      {mesaj}
    </p>
  );
}

export function TamKitapFormu() {
  const aktar = useImportExcelTam();
  const senaryolar = useSenaryolar();
  const { senaryoId, senaryo: seciliSenaryo, kilitli } = useSenaryo();
  // Yeni çalışma açan mod senaryo kilidinden etkilenmez; düzenleme kilidi iki modu da kapatır.
  const { duzenlemeKilitli } = useYazmaKilidi();
  // Mod bilinçli seçilir (varsayılan yok): yanlışlıkla ikinci bir senaryo açılmasın ya da mevcut senaryoya yazılmasın.
  const [mod, setMod] = useState<"yeni" | "tamamla" | null>(null);
  const [bekleyen, setBekleyen] = useState<{
    d: FormDegerleri;
    dosya: File;
    ayni: Senaryo;
  } | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormDegerleri>({
    resolver: zodResolver(tamKitapSemasi),
    defaultValues: {
      sezon_ad: "2026-2027",
      senaryo_ad: "Fiyat Çalışması",
      tur: "fiyat_calismasi",
      kartlari_guncelle: false,
    },
  });

  const [dosya, setDosya] = useState<File | undefined>(undefined);
  const [dosyaHata, setDosyaHata] = useState<string | undefined>(undefined);

  function dosyaDogrula(f: File | undefined): File | null {
    const s = dosyaSemasi.safeParse(f);
    setDosyaHata(s.success ? undefined : s.error.issues[0]?.message);
    return s.success ? s.data : null;
  }

  const hata = (aktar.error as ApiHatasi | null) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <form
        noValidate
        onSubmit={(e) => {
          // Dosya doğrulaması her zaman çalışır; geçersizse diğer alanlar da doğrulanıp hata gösterilir, ağ isteği yapılmaz.
          if (mod === null) {
            e.preventDefault();
            return;
          }
          const f = dosyaDogrula(dosya);
          if (mod === "tamamla") {
            // Tamamla modunda sezon/senaryo/tür alanları yoktur: yalnız dosya ve seçili senaryo gönderilir.
            e.preventDefault();
            if (f && senaryoId !== null) aktar.mutate({ dosya: f, senaryo_id: senaryoId });
            return;
          }
          void handleSubmit((d) => {
            if (!f) return;
            // Aynı sezon ve adda senaryo varsa ikinci bir kopya açmadan önce kullanıcıya sorulur.
            const ayni = (senaryolar.data ?? []).find((s) => s.sezon_ad === d.sezon_ad && s.ad === d.senaryo_ad.trim());
            if (ayni) setBekleyen({ d, dosya: f, ayni });
            else aktar.mutate({ ...d, dosya: f });
          })(e);
        }}
        className="grid max-w-2xl gap-4"
        aria-label="Tüm çalışma kitabını içe aktar"
      >
        <p className="text-sm text-muted-foreground">
          Fiyat çalışması Excel dosyasının tamamı (malzeme, fiyat, havuz, ambalaj, ürün, reçete, parametre) tek seferde yüklenir. En fazla
          25 MB, yalnızca .xlsx. Sayfa adları (S.ALMA BF, Gider Dağıtım, Üretim Adetleri, ürün sayfaları) büyük/küçük harf fark etmez; eksik
          sayfa varsa hangisi olduğu söylenir.
        </p>
        <YuklemeYardimi />
        {mod === "tamamla" && senaryoId !== null && (
          <SonYuklemeSeridi
            yol="/api/v1/import/excel-tam"
            sorgu={{ senaryo: senaryoId }}
            kilitli={duzenlemeKilitli || kilitli}
            kilitNedeni={duzenlemeKilitli ? "Düzenleme kilitli" : kilitli ? "Senaryo kilitli" : undefined}
          />
        )}

        <fieldset className="flex flex-col gap-1">
          <legend className="text-sm font-medium">Aktarım modu</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="aktar-mod" className="size-4" checked={mod === "yeni"} onChange={() => setMod("yeni")} />
            Yeni senaryo oluştur
          </label>
          <p className="ml-6 text-xs text-muted-foreground">
            Excel'deki her şey yeni, ayrı bir çalışma olarak açılır. Var olan çalışmalara dokunulmaz.
          </p>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name="aktar-mod" className="size-4" checked={mod === "tamamla"} onChange={() => setMod("tamamla")} />
            Mevcut senaryoyu tamamla (seçili senaryo)
          </label>
          <p className="ml-6 text-xs text-muted-foreground">
            Seçili çalışmaya yalnız eksik olanlar eklenir; var olan hiçbir kayıt değişmez.
          </p>
          {mod === "tamamla" && (
            <p className="text-sm text-muted-foreground">
              {senaryoId === null
                ? "Önce üst çubuktan bir senaryo seçin."
                : `Seçili senaryo: ${seciliSenaryo?.ad ?? `#${senaryoId}`}. Yeni senaryo açılmaz; yalnızca eksik olanlar (üretim adetleri, kurlar, satış fiyatı notu, eksik reçete/fiyat) eklenir, var olan hiçbir kayıt değişmez.`}
            </p>
          )}
        </fieldset>

        <div className="flex flex-col gap-1">
          <label htmlFor="aktar-dosya" className="text-sm font-medium">
            Excel dosyası
          </label>
          <Input
            id="aktar-dosya"
            type="file"
            accept=".xlsx"
            aria-invalid={!!dosyaHata}
            aria-describedby={dosyaHata ? "aktar-dosya-hata" : undefined}
            onChange={(e) => {
              const f = e.target.files?.[0];
              setDosya(f);
              if (f || dosyaHata) dosyaDogrula(f);
            }}
          />
          <HataMetni id="aktar-dosya-hata" mesaj={dosyaHata} />
        </div>

        {mod === "yeni" && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <label htmlFor="aktar-sezon" className="text-sm font-medium">
                  Sezon adı
                </label>
                <Input
                  id="aktar-sezon"
                  placeholder="2026-2027"
                  aria-invalid={!!errors.sezon_ad}
                  aria-describedby={errors.sezon_ad ? "aktar-sezon-hata" : undefined}
                  {...register("sezon_ad")}
                />
                <HataMetni id="aktar-sezon-hata" mesaj={errors.sezon_ad?.message} />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="aktar-senaryo" className="text-sm font-medium">
                  Senaryo adı
                </label>
                <Input
                  id="aktar-senaryo"
                  aria-invalid={!!errors.senaryo_ad}
                  aria-describedby={errors.senaryo_ad ? "aktar-senaryo-hata" : undefined}
                  {...register("senaryo_ad")}
                />
                <HataMetni id="aktar-senaryo-hata" mesaj={errors.senaryo_ad?.message} />
              </div>
            </div>

            <div className="flex flex-wrap items-end gap-6">
              <div className="flex flex-col gap-1">
                <label htmlFor="aktar-tur" className="text-sm font-medium">
                  Tür
                </label>
                <select id="aktar-tur" className={SELECT_SINIFI} {...register("tur")}>
                  <option value="fiyat_calismasi">Fiyat çalışması</option>
                  <option value="gerceklesen">Gerçekleşen</option>
                </select>
              </div>
              <div className="flex max-w-sm flex-col gap-0.5 pb-1">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" className="size-4" aria-describedby="kartlar-aciklama" {...register("kartlari_guncelle")} />
                  Kartları güncelle
                </label>
                <p id="kartlar-aciklama" className="ml-6 text-xs text-muted-foreground">
                  İşaretlerseniz sistemdeki ürün ve malzeme kartlarının bilgileri (ad, birim, hat, ambalaj…) Excel'dekiyle değiştirilir.
                  İşaretlemezseniz yalnız yeni kartlar açılır, farklar özette listelenir.
                </p>
              </div>
            </div>
          </>
        )}

        <div>
          <Button
            type="submit"
            disabled={aktar.isPending || mod === null || duzenlemeKilitli || (mod === "tamamla" && (senaryoId === null || kilitli))}
            title={duzenlemeKilitli ? "Düzenleme kilitli" : undefined}
          >
            {aktar.isPending ? "Aktarılıyor…" : "İçe aktar"}
          </Button>
          {mod === null && <p className="mt-1 text-xs text-muted-foreground">Önce aktarım modunu seçin.</p>}
        </div>
      </form>

      {bekleyen && (
        <OnayDiyalogu
          baslik="Aynı adda senaryo var"
          onayMetni="Yine de oluştur"
          onOnayla={() => {
            aktar.mutate({ ...bekleyen.d, dosya: bekleyen.dosya });
            setBekleyen(null);
          }}
          onVazgec={() => setBekleyen(null)}
        >
          <p>{`Aynı adda senaryo var (#${bekleyen.ayni.id}). Yine de yeni senaryo oluşturulsun mu?`}</p>
        </OnayDiyalogu>
      )}

      {aktar.isPending && (
        <div role="status" className="flex max-w-2xl flex-col gap-2 text-sm text-muted-foreground">
          <span>Dosya yükleniyor ve işleniyor, bu işlem birkaç dakika sürebilir…</span>
          <progress className="h-2 w-full" aria-label="İçe aktarma ilerlemesi" />
        </div>
      )}

      {hata && (
        <div role="alert" className="max-w-2xl rounded-md border border-destructive/40 p-3 text-sm text-destructive">
          <p className="font-medium">{hataMetni(hata)}</p>
        </div>
      )}

      {aktar.data?.musavir_sablonu_saklandi && (
        <p className="max-w-2xl text-sm text-muted-foreground" data-testid="musavir-sablon-saklandi">
          Kitap, bu çalışmanın Müşavir Excel&apos;i şablonu olarak da saklandı (İndir › Müşavir Excel&apos;i).
        </p>
      )}
      {aktar.data && <ImportOzetiKartlari ozet={aktar.data} />}

      <MusavirSablonuSakla />
    </div>
  );
}
