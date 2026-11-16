import { useId, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useImportFiyatOnizle, useImportFiyatUygula } from "@/api/sorgular/aktar";
import type { FiyatOnizleme } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Girdi } from "@/bilesenler/Girdi";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/bilesenler/ui/tabs";
import { paraBicimle } from "@/yardimcilar/para";
import { bugunIso } from "@/yardimcilar/tarih";
import { hataMetniVarsa } from "@/api/istemci";
import { SablonIndir, YuklemeYardimi } from "@/bilesenler/SablonIndir";
import { SonYuklemeSeridi } from "@/bilesenler/SonYuklemeSeridi";
import { YuklemeOzetiKutusu } from "@/bilesenler/YuklemeOzetiKutusu";
import { useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";

/** Fiyat listesi okuyucusunun gerçekten desteklediği uzantılar (.xls / .csv okunamaz). */
const DESTEKLENEN = [".xlsx", ".xlsm"];

const sema = z.object({
  tarih: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Geçerlilik tarihi zorunlu"),
  neden: z.string().trim().min(1, "Neden zorunlu"),
});

interface Props {
  senaryo: number;
  onKapat: () => void;
  onBasari: (mesaj: string) => void;
}

/** Fiyat listesi (Excel) yükleme: dosya -> önizleme -> uygula (geçerlilik tarihi + neden). */
export function FiyatListesiYukle({ senaryo, onKapat, onBasari }: Props) {
  const id = useId();
  const bugun = useMemo(() => bugunIso(), []);
  const [dosya, setDosya] = useState<File | null>(null);
  const [onizleme, setOnizleme] = useState<FiyatOnizleme | null>(null);
  const [dosyaHata, setDosyaHata] = useState<string | null>(null);
  /** Elle girilmiş fiyatlar: varsayılan korunur; kullanıcı "üzerine yaz" seçerse önizleme yenilenir. */
  const [elleUstuneYaz, setElleUstuneYaz] = useState(false);
  const onizle = useImportFiyatOnizle();
  const uygula = useImportFiyatUygula();
  const { kilitli, neden: kilitNedeni } = useYazmaKilidi();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<z.infer<typeof sema>>({ resolver: zodResolver(sema), defaultValues: { tarih: bugun, neden: "" } });

  function onizleBaslat(elle = elleUstuneYaz) {
    if (!dosya) return;
    onizle.mutate({ dosya, senaryo, gecerlilik_basi: getValues("tarih"), elle_ustune_yaz: elle }, { onSuccess: (v) => setOnizleme(v) });
  }

  function uygulaBaslat(v: z.infer<typeof sema>) {
    if (!dosya) return;
    uygula.mutate(
      { dosya, senaryo, gecerlilik_basi: v.tarih, neden: v.neden.trim(), elle_ustune_yaz: elleUstuneYaz },
      {
        onSuccess: (s) => {
          const korunan = s.korunan_elle ? ` Elle girilmiş ${s.korunan_elle} fiyat korundu.` : "";
          onBasari(`${s.yazilan} fiyat yazıldı.${korunan}`);
          onKapat();
        },
      },
    );
  }

  const hata = hataMetniVarsa(onizle.error) ?? hataMetniVarsa(uygula.error);

  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Fiyat listesi yükle</DialogTitle>
          <DialogDescription>Excel dosyasını seçin, değişiklikleri önizleyin, sonra uygulayın.</DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-3" noValidate onSubmit={handleSubmit(uygulaBaslat)}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <YuklemeYardimi />
            <SablonIndir kimlik="malzeme_fiyat_listesi" />
          </div>
          <SonYuklemeSeridi
            yol="/api/v1/import/fiyat-listesi"
            sorgu={{ senaryo }}
            kilitli={kilitli}
            kilitNedeni={kilitNedeni}
            gecersiz={["malzemeler", "fiyat-gecmisi", "urunler", "uyarilar"]}
          />
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-dosya`} className="text-sm font-medium">
              Fiyat listesi dosyası
            </label>
            <Girdi
              id={`${id}-dosya`}
              type="file"
              accept={DESTEKLENEN.join(",")}
              aria-invalid={!!dosyaHata}
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                const uygun = !f || DESTEKLENEN.some((u) => f.name.toLowerCase().endsWith(u));
                setDosyaHata(
                  uygun ? null : "Yalnız .xlsx dosyası yüklenebilir (.xls ve .csv desteklenmez; Excel'de .xlsx olarak kaydedin).",
                );
                setDosya(uygun ? f : null);
                setOnizleme(null);
              }}
            />
            {dosyaHata && (
              <p role="alert" className="text-sm text-destructive">
                {dosyaHata}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-tarih`} className="text-sm font-medium">
              Geçerlilik tarihi
            </label>
            <Girdi
              id={`${id}-tarih`}
              type="date"
              {...register("tarih", {
                // Önizleme seçili tarihe göre hesaplandı: tarih değişince eskimiş önizleme uygulanamasın.
                onChange: () => setOnizleme(null),
              })}
            />
            {errors.tarih && (
              <p role="alert" className="text-sm text-destructive">
                {errors.tarih.message}
              </p>
            )}
          </div>
          <div>
            <Button type="button" variant="outline" disabled={!dosya || onizle.isPending} onClick={() => onizleBaslat()}>
              {onizle.isPending ? "Önizleniyor…" : "Önizle"}
            </Button>
          </div>

          {onizleme && (
            <>
              {onizleme.ozet && <YuklemeOzetiKutusu ozet={onizleme.ozet} baslik="Fiyat listesi — sorunlu satırlar" />}
              {(onizleme.elle?.length ?? 0) > 0 && (
                <fieldset className="flex flex-col gap-1 rounded-md border p-2 text-sm" aria-label="Elle girilmiş fiyatlar">
                  <legend className="px-1 font-medium">
                    Elle girilmiş {onizleme.elle?.length} fiyat — korunsun mu, üzerine yazılsın mı?
                  </legend>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={`${id}-elle`}
                      className="size-4"
                      checked={!elleUstuneYaz}
                      onChange={() => {
                        setElleUstuneYaz(false);
                        onizleBaslat(false);
                      }}
                    />
                    Korunsun (önerilen)
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={`${id}-elle`}
                      className="size-4"
                      checked={elleUstuneYaz}
                      onChange={() => {
                        setElleUstuneYaz(true);
                        onizleBaslat(true);
                      }}
                    />
                    Üzerine yazılsın
                  </label>
                  <ul className="max-h-32 overflow-auto pl-1 text-xs text-muted-foreground tabular-nums">
                    {onizleme.elle?.map((x) => (
                      <li key={x.kod}>
                        {x.kod}: {paraBicimle(x.eski, "", 4)} (elle) → {paraBicimle(x.yeni, "", 4)}
                      </li>
                    ))}
                  </ul>
                </fieldset>
              )}
              <Tabs defaultValue="degisen">
                <TabsList>
                  <TabsTrigger value="degisen">Değişen ({onizleme.degisen.length})</TabsTrigger>
                  <TabsTrigger value="yeni">Yeni ({onizleme.yeni.length})</TabsTrigger>
                  <TabsTrigger value="ayni">Aynı ({onizleme.ayni})</TabsTrigger>
                  <TabsTrigger value="hatali">Hatalı ({onizleme.hatali.length})</TabsTrigger>
                </TabsList>
                <TabsContent value="degisen">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left">
                        <th>Kod</th>
                        <th className="text-right">Eski</th>
                        <th className="text-right">Yeni</th>
                      </tr>
                    </thead>
                    <tbody>
                      {onizleme.degisen.map((d) => (
                        <tr key={d.kod}>
                          <td>{d.kod}</td>
                          <td>
                            <span className="block text-right tabular-nums">{paraBicimle(d.eski, "", 4)}</span>
                          </td>
                          <td>
                            <span className="block text-right tabular-nums">{paraBicimle(d.yeni, "", 4)}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {onizleme.degisen.length === 0 && <p className="text-sm text-muted-foreground">Değişen fiyat yok.</p>}
                </TabsContent>
                <TabsContent value="yeni">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left">
                        <th>Kod</th>
                        <th className="text-right">Fiyat</th>
                      </tr>
                    </thead>
                    <tbody>
                      {onizleme.yeni.map((d) => (
                        <tr key={d.kod}>
                          <td>{d.kod}</td>
                          <td>
                            <span className="block text-right tabular-nums">{paraBicimle(d.yeni, "", 4)}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {onizleme.yeni.length === 0 && <p className="text-sm text-muted-foreground">Yeni kalem yok.</p>}
                </TabsContent>
                <TabsContent value="ayni">
                  <p className="text-sm">{onizleme.ayni} kalemin fiyatı değişmemiş; yazılmayacak.</p>
                </TabsContent>
                <TabsContent value="hatali">
                  {onizleme.hatali.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Hatalı satır yok.</p>
                  ) : (
                    <ul className="list-disc pl-5 text-sm text-destructive">
                      {onizleme.hatali.map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ul>
                  )}
                </TabsContent>
              </Tabs>
              {(onizleme.revize?.length ?? 0) > 0 && (
                <section
                  role="region"
                  aria-labelledby={`${id}-revize-baslik`}
                  className="rounded-md border border-amber-300/60 bg-amber-50 p-2 text-sm dark:border-amber-700/60 dark:bg-amber-950/30"
                >
                  <h3 id={`${id}-revize-baslik`} className="font-medium">
                    Revize fiyatlar
                  </h3>
                  <p className="text-muted-foreground">Revize fiyat (S.ALMA BF I): {onizleme.revize.length}</p>
                  <p className="text-xs text-muted-foreground">
                    Bu kalemlerde I sütunundaki revize fiyat geçerli olacak (ilk bütçe → revize).
                  </p>
                  <ul className="mt-1 max-h-40 list-none overflow-auto pl-0 tabular-nums">
                    {onizleme.revize.map((r, i) => (
                      <li key={`${r.kod}-${i}`}>
                        {r.kod} · {r.ilk == null ? "—" : paraBicimle(r.ilk, "", 4)} → {paraBicimle(r.revize, "", 4)}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              <div className="flex flex-col gap-1">
                <label htmlFor={`${id}-neden`} className="text-sm font-medium">
                  Neden
                </label>
                <Girdi id={`${id}-neden`} aria-invalid={!!errors.neden} {...register("neden")} />
                {errors.neden && (
                  <p role="alert" className="text-sm text-destructive">
                    {errors.neden.message}
                  </p>
                )}
              </div>
              <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
                Özet: {onizleme.degisen.length} değişen fiyat yazılacak.
                {onizleme.yeni.length > 0 &&
                  ` Sistemde fiyatı olmayan ${onizleme.yeni.length} kod yazılmaz (Veri Aktar › Satın alma fiyat listesi).`}
              </p>
            </>
          )}

          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onKapat}>
              Vazgeç
            </Button>
            {onizleme && (
              <Button type="submit" disabled={uygula.isPending || kilitli} title={kilitNedeni}>
                {uygula.isPending ? "Uygulanıyor…" : "Uygula"}
              </Button>
            )}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
