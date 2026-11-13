import { useEffect, useId, useMemo, useState, type ReactNode } from "react";
import { hataMetniVarsa } from "@/api/istemci";
import {
  useAktarimOnizle,
  useAktarimUygula,
  type AktarimTipi,
  type AktarimUygulaDegiskenleri,
  type TipHaritasi,
} from "@/api/sorgular/aktarim";
import { useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Girdi } from "@/bilesenler/Girdi";
import { Button } from "@/bilesenler/ui/button";
import { bugunIso } from "@/yardimcilar/tarih";
import { dosyaSemasi } from "./TamKitapFormu";

export interface OzetKarti {
  baslik: string;
  deger: number;
}

interface Props<T extends AktarimTipi> {
  tip: T;
  /** Formun erişilebilir adı. */
  ad: string;
  aciklama: string;
  /** Satın alma: geçerlilik tarihi ve "Kartları güncelle" alanları. */
  satinAlma?: boolean;
  /** Önizleme gövdesi: yeni / değişen / aynı / hatalı tabloları. */
  onizlemeGoster: (o: TipHaritasi[T]["onizle"]) => ReactNode;
  /** Önizlemedeki hatalı satır kodları; doluysa uygulanamaz. */
  hatalar?: (o: TipHaritasi[T]["onizle"]) => string[];
  /** Yazılacak bir şey var mı (yoksa Uygula pasif). */
  yazilacakVar: (o: TipHaritasi[T]["onizle"]) => boolean;
  ozetKartlari: (u: TipHaritasi[T]["uygula"]) => OzetKarti[];
  uyarilar?: (u: TipHaritasi[T]["uygula"]) => string[];
  /** Uygula isteğine eklenecek alanlar; son önizlemeyle çağrılır (ör. reçetede seçilen sayfalar). */
  uygulaEk?: (o: TipHaritasi[T]["onizle"]) => Partial<AktarimUygulaDegiskenleri>;
  /** Dosya ya da senaryo değişince (önizleme geçersizleşince) çağrılır: tipe özel seçimler sıfırlansın. */
  onSifirla?: () => void;
}

/** Ortak akış: dosya seç -> Önizle -> fark tablosu -> neden -> Uygula -> özet. Dosya, tarih veya senaryo değişince önizleme geçersiz olur. */
export function AktarimFormu<T extends AktarimTipi>({
  tip,
  ad,
  aciklama,
  satinAlma,
  onizlemeGoster,
  hatalar,
  yazilacakVar,
  ozetKartlari,
  uyarilar,
  uygulaEk,
  onSifirla,
}: Props<T>) {
  const id = useId();
  const { senaryoId } = useSenaryo();
  const { kilitli, neden: kilitNedeni } = useYazmaKilidi();
  const bugun = useMemo(() => bugunIso(), []);
  const [dosya, setDosya] = useState<File | null>(null);
  const [dosyaHata, setDosyaHata] = useState<string | undefined>(undefined);
  const [tarih, setTarih] = useState(bugun);
  const [kartlariGuncelle, setKartlariGuncelle] = useState(false);
  const [neden, setNeden] = useState("");
  const onizle = useAktarimOnizle(tip);
  const uygula = useAktarimUygula(tip);

  const onizleme = onizle.data;
  const hataKodlari = onizleme && hatalar ? hatalar(onizleme) : [];
  const nedenVar = neden.trim() !== "";
  const tarihVar = !satinAlma || /^\d{4}-\d{2}-\d{2}$/.test(tarih);
  const uygulanabilir =
    !!onizleme && yazilacakVar(onizleme) && hataKodlari.length === 0 && nedenVar && tarihVar && !uygula.isPending && !kilitli;

  // Önizleme belirli bir senaryo için hesaplandı: üst çubukta senaryo değişirse eskimiş önizleme/özet atılır.
  useEffect(() => {
    onizle.reset();
    uygula.reset();
    onSifirla?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [senaryoId]);

  function sifirla() {
    onizle.reset();
    uygula.reset();
    onSifirla?.();
  }

  function onizleBaslat() {
    if (!dosya || senaryoId === null) return;
    uygula.reset();
    onizle.mutate({ dosya, senaryo: senaryoId, ...(satinAlma ? { gecerlilik_basi: tarih } : {}) });
  }

  function uygulaBaslat() {
    if (!dosya || senaryoId === null || !uygulanabilir) return;
    uygula.mutate({
      dosya,
      senaryo: senaryoId,
      neden: neden.trim(),
      ...(satinAlma ? { gecerlilik_basi: tarih, kartlari_guncelle: kartlariGuncelle } : {}),
      ...(uygulaEk && onizleme ? uygulaEk(onizleme) : {}),
    });
  }

  const hata = hataMetniVarsa(onizle.error) ?? hataMetniVarsa(uygula.error);
  const sonuc = uygula.data;

  return (
    <div className="flex flex-col gap-6">
      <form
        noValidate
        aria-label={ad}
        className="grid max-w-3xl gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          uygulaBaslat();
        }}
      >
        <p className="text-sm text-muted-foreground">{aciklama}</p>
        {senaryoId === null && <p className="text-sm text-muted-foreground">Önce üst çubuktan bir senaryo seçin.</p>}

        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-dosya`} className="text-sm font-medium">
            Excel dosyası
          </label>
          <Girdi
            id={`${id}-dosya`}
            type="file"
            accept=".xlsx"
            aria-invalid={!!dosyaHata}
            onChange={(e) => {
              const f = e.target.files?.[0];
              const s = dosyaSemasi.safeParse(f);
              setDosyaHata(s.success ? undefined : s.error.issues[0]?.message);
              setDosya(s.success ? s.data : null);
              sifirla();
            }}
          />
          {dosyaHata && <p className="text-sm text-destructive">{dosyaHata}</p>}
        </div>

        {satinAlma && (
          <div className="flex flex-wrap items-end gap-6">
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-tarih`} className="text-sm font-medium">
                Geçerlilik tarihi
              </label>
              <Girdi
                id={`${id}-tarih`}
                type="date"
                value={tarih}
                onChange={(e) => {
                  setTarih(e.target.value);
                  sifirla(); // önizleme seçili tarihe göre hesaplandı
                }}
              />
            </div>
            <label className="flex items-center gap-2 pb-1 text-sm">
              <input
                type="checkbox"
                className="size-4"
                checked={kartlariGuncelle}
                onChange={(e) => setKartlariGuncelle(e.target.checked)}
              />
              Kartları güncelle
            </label>
          </div>
        )}

        <div>
          <Button
            type="button"
            variant="outline"
            disabled={!dosya || senaryoId === null || !tarihVar || onizle.isPending}
            onClick={onizleBaslat}
          >
            {onizle.isPending ? "Önizleniyor…" : "Önizle"}
          </Button>
        </div>

        {onizleme && (
          <section aria-label="Önizleme" className="flex flex-col gap-3">
            {onizlemeGoster(onizleme)}
            {hataKodlari.length > 0 && (
              <p role="alert" className="rounded-md border border-destructive/40 p-2 text-sm text-destructive">
                Hatalı satırlar düzeltilmeden uygulanamaz.
              </p>
            )}
            {!yazilacakVar(onizleme) && hataKodlari.length === 0 && (
              <p className="text-sm text-muted-foreground">Yazılacak değişiklik yok.</p>
            )}
            <div className="flex max-w-xl flex-col gap-1">
              <label htmlFor={`${id}-neden`} className="text-sm font-medium">
                Neden
              </label>
              <Girdi id={`${id}-neden`} value={neden} onChange={(e) => setNeden(e.target.value)} />
            </div>
            <div>
              <Button type="submit" disabled={!uygulanabilir} title={kilitNedeni}>
                {uygula.isPending ? "Uygulanıyor…" : "Uygula"}
              </Button>
            </div>
          </section>
        )}
      </form>

      {hata && (
        <div role="alert" className="max-w-3xl rounded-md border border-destructive/40 p-3 text-sm text-destructive">
          <p className="font-medium">{hata}</p>
        </div>
      )}

      {sonuc && (
        <section aria-label="Aktarım özeti" className="flex flex-col gap-3">
          <h2 className="text-lg font-semibold">Aktarım tamamlandı</h2>
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {ozetKartlari(sonuc).map((k) => (
              <div key={k.baslik} className="rounded-lg border p-3">
                <div data-kart-baslik className="text-sm text-muted-foreground">
                  {k.baslik}
                </div>
                <div className="text-2xl font-semibold tabular-nums">{k.deger}</div>
              </div>
            ))}
          </div>
          {uyarilar && uyarilar(sonuc).length > 0 && (
            <details className="rounded-lg border px-3 py-2" open>
              <summary className="cursor-pointer text-sm font-medium">Uyarılar ({uyarilar(sonuc).length})</summary>
              <ul className="mt-2 list-disc pl-5 text-sm">
                {uyarilar(sonuc).map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}
    </div>
  );
}
