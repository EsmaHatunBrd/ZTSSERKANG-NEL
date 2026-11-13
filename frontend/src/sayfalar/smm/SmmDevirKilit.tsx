import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { CircleCheck, Download, Lock, LockOpen, RefreshCw, TriangleAlert } from "lucide-react";
import { ApiHatasi, hataMetniVarsa } from "@/api/istemci";
import { SMM_KAPANIS_EKSIK, smmFisAdresi, useSmmDevirDurumu, useSmmDevirYenile, useSmmKilit } from "@/api/sorgular/smm";
import type { SmmDevirYenileSonucu, SmmDonem, SmmVeriDurumu } from "@/api/tipler";
import { useOturum } from "@/bilesenler/GirisKapisi";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";
import { D, paraBicimle } from "@/yardimcilar/para";
import { miktar } from "./ortak";

/** Kapanış anı: "13.11.2026". */
export const kilitTarihi = (z: string | null | undefined) => (z ? new Date(z).toLocaleDateString("tr-TR") : null);

/** Açılışını bu dönemden devralmış dönem (varsa). */
export const sonrakiDonem = (liste: SmmDonem[], donemId: number) => liste.find((x) => x.devir_donem_id === donemId) ?? null;

/** Açılış – önceki kapanış farkları: TL farkı en büyük ilk 20 kalem. */
function DevirFarklari({ donemId }: { donemId: number }) {
  const q = useSmmDevirDurumu(donemId);
  const d = q.data;
  if (q.isPending) return <p className="text-sm text-muted-foreground">Farklar yükleniyor…</p>;
  if (q.error) return <p className="text-sm text-destructive">{hataMetniVarsa(q.error)}</p>;
  if (!d || d.ornek.length === 0) return <p className="text-sm text-muted-foreground">Fark yok.</p>;
  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto rounded-xl border bg-card">
        <table aria-label="Devir farkları" className="w-full text-sm">
          <thead className="bg-muted/60 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Kod</th>
              <th className="px-3 py-2 text-left font-medium">Ad</th>
              <th className="px-3 py-2 text-right font-medium">Açılış miktar</th>
              <th className="px-3 py-2 text-right font-medium">Kapanış miktar</th>
              <th className="px-3 py-2 text-right font-medium">Açılış tutar</th>
              <th className="px-3 py-2 text-right font-medium">Kapanış tutar</th>
              <th className="px-3 py-2 text-right font-medium">Fark (TL)</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {d.ornek.map((x) => (
              <tr key={x.kod}>
                <td className="px-3 py-1.5 font-medium whitespace-nowrap">
                  {x.kod}
                  {x.elle && (
                    <Badge variant="outline" className="ml-2" title="Açılış değeri ekranda elle girildi; devir yenilenince korunur">
                      elle
                    </Badge>
                  )}
                </td>
                <td className="px-3 py-1.5">{x.ad ?? "—"}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{miktar(x.acilis_miktar)}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{miktar(x.kapanis_miktar)}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{paraBicimle(x.acilis_tutar, "", 2)}</td>
                <td className="px-3 py-1.5 text-right tabular-nums">{paraBicimle(x.kapanis_tutar, "", 2)}</td>
                <td className="px-3 py-1.5 text-right font-medium tabular-nums">
                  {paraBicimle(D(x.acilis_tutar).minus(x.kapanis_tutar), "", 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        Açılış: bu dönemin dönem başı stoku. Kapanış: {d.onceki?.ad} sayımı ve dönem sonu stok tutarı (şu anki hâli).
        {d.fark_kalem > d.ornek.length && ` TL farkı en büyük ${d.ornek.length} kalem gösteriliyor (toplam ${d.fark_kalem}).`}
        {d.elle_kalem > 0 && ` ${d.elle_kalem} kalemin açılışı elle girilmiş.`}
      </p>
    </div>
  );
}

/** "Devri yenile": neden zorunlu; elle girilmiş açılış değerleri korunur (isteğe bağlı ezilir). */
function DevirYenileDiyalogu({
  v,
  onBitti,
  onVazgec,
}: {
  v: SmmVeriDurumu;
  onBitti: (s: SmmDevirYenileSonucu) => void;
  onVazgec: () => void;
}) {
  const yenile = useSmmDevirYenile();
  const durum = useSmmDevirDurumu(v.donem.id);
  const [neden, setNeden] = useState("");
  const [elleEz, setElleEz] = useState(false);
  const nedenId = useId();
  const elle = durum.data?.elle_kalem ?? 0;
  return (
    <Dialog open onOpenChange={(a) => !a && onVazgec()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Devir yenilensin mi?</DialogTitle>
          <DialogDescription>
            {v.donem.ad} açılış stoku, {v.devir?.onceki_ad} döneminin güncel kapanışından (sayım miktarı ve dönem sonu stok tutarı) yeniden
            yazılır. Eski değerler günlükte kalır.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3 text-sm">
          <p>
            <b>Elle girdiğiniz açılış değerleri korunur.</b>
            {elle > 0 && ` Bu dönemde önceki kapanıştan farklı ${elle} elle açılış değeri var.`}
          </p>
          {elle > 0 && (
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={elleEz} onChange={(e) => setElleEz(e.target.checked)} />
              Elle girilmiş {elle} açılış değerini de önceki kapanışla değiştir
            </label>
          )}
          <label htmlFor={nedenId} className="flex flex-col gap-1">
            <span className="text-muted-foreground">Neden (zorunlu)</span>
            <Input id={nedenId} value={neden} maxLength={300} onChange={(e) => setNeden(e.target.value)} />
          </label>
        </div>
        {hataMetniVarsa(yenile.error) && (
          <p role="alert" className="text-sm text-destructive">
            {hataMetniVarsa(yenile.error)}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onVazgec}>
            Vazgeç
          </Button>
          <Button
            type="button"
            disabled={!neden.trim() || yenile.isPending}
            onClick={() => yenile.mutate({ donemId: v.donem.id, neden: neden.trim(), elleEz }, { onSuccess: onBitti })}
          >
            Devri yenile
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Açılış stoku önceki ayın kapanışıyla uyuşmuyorsa sarı uyarı şeridi: farkları gör, devri yenile. */
export function DevirBolumu({ v }: { v: SmmVeriDurumu }) {
  const [farklarAcik, setFarklarAcik] = useState(false);
  const [yenileAcik, setYenileAcik] = useState(false);
  const [sonuc, setSonuc] = useState<SmmDevirYenileSonucu | null>(null);
  const dv = v.devir;
  if (!dv) return null;
  return (
    <>
      {sonuc && (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-xl bg-kart-yesil px-4 py-3 text-sm">
          <CircleCheck className="size-4 text-green-700 dark:text-green-400" aria-hidden />
          Devir yenilendi: {sonuc.guncellenen} kalem güncellendi, {sonuc.eklenen} kalem eklendi.
          {sonuc.elle_kalem > 0 &&
            (sonuc.elle_korundu
              ? ` ${sonuc.elle_kalem} elle açılış değeri korundu.`
              : ` ${sonuc.elle_kalem} elle açılış değeri de değiştirildi.`)}
        </p>
      )}
      {!dv.uyumlu && (
        <section aria-label="Devir uyarısı" className="flex flex-col gap-3 rounded-xl bg-kart-sari px-4 py-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <TriangleAlert className="size-4 shrink-0 text-amber-700" aria-hidden />
            <span className="min-w-56 flex-1">
              <b>
                Açılış stoku {dv.onceki_ad} kapanışıyla uyuşmuyor ({dv.fark_kalem} kalem, fark {paraBicimle(dv.fark_tutar, "TL", 2)})
              </b>
              .{!dv.onceki_kilitli && ` ${dv.onceki_ad} henüz kapatılmadı; kapanışı değişmeye devam edebilir.`}
            </span>
            <Button type="button" size="sm" variant="outline" aria-expanded={farklarAcik} onClick={() => setFarklarAcik((x) => !x)}>
              {farklarAcik ? "Farkları gizle" : "Farkları gör"}
            </Button>
            {!v.donem.kilitli && (
              <Button type="button" size="sm" onClick={() => setYenileAcik(true)}>
                <RefreshCw className="size-3.5" /> Devri yenile
              </Button>
            )}
          </div>
          {farklarAcik && <DevirFarklari donemId={v.donem.id} />}
        </section>
      )}
      {yenileAcik && (
        <DevirYenileDiyalogu
          v={v}
          onVazgec={() => setYenileAcik(false)}
          onBitti={(s) => {
            setSonuc(s);
            setYenileAcik(false);
          }}
        />
      )}
    </>
  );
}

/** Dönem kapanışı: fiş indirme, kapatma (eksik ön kontrolü, "yine de kapat") ve kilit açma (yalnız Genel Direktör; zincir uyarısı). */
export function KapanisBolumu({ v, liste }: { v: SmmVeriDurumu; liste: SmmDonem[] }) {
  const { yonetici } = useOturum();
  const kilit = useSmmKilit();
  const [kapatOnayi, setKapatOnayi] = useState(false);
  const [eksikler, setEksikler] = useState<string[] | null>(null);
  const [acOnayi, setAcOnayi] = useState(false);
  const [acUyari, setAcUyari] = useState<string | null>(null);
  const kilitli = Boolean(v.donem.kilitli);
  const sonraki = sonrakiDonem(liste, v.donem.id);
  const eksikHatasi = kilit.error instanceof ApiHatasi && kilit.error.kod === SMM_KAPANIS_EKSIK;
  const vazgec = () => {
    setKapatOnayi(false);
    setAcOnayi(false);
    setEksikler(null);
    kilit.reset();
  };
  const kapat = (zorla: boolean) =>
    kilit.mutate(
      { donemId: v.donem.id, kilitli: true, zorla },
      {
        onSuccess: vazgec,
        onError: (e) => {
          if (e instanceof ApiHatasi && e.kod === SMM_KAPANIS_EKSIK) {
            const x = e.alanlar.eksikler;
            setEksikler(Array.isArray(x) ? x.map(String) : []);
          }
        },
      },
    );
  return (
    <>
      <section aria-label="Dönem kapanışı" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
        <h2 className="text-base font-semibold">Dönem kapanışı</h2>
        <p className="text-sm text-muted-foreground">
          Veriler tamamlanıp SMM Özeti kontrol edilince dönem kapatılır: kilitli dönemde veri, reçete kaynağı, dağıtım ve elle değerler
          değiştirilemez. Kapanış bir sonraki ayın açılışı olur. SMM fişi Canias'a aktarım için Excel olarak indirilir.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <a
            href={smmFisAdresi(v.donem.id)}
            download
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium hover:bg-accent"
          >
            <Download className="size-3.5" /> SMM fişini Excel olarak indir
          </a>
          {kilitli ? (
            <>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={!yonetici || kilit.isPending}
                title={yonetici ? undefined : "Dönem kilidini yalnız Genel Direktör açabilir"}
                onClick={() => {
                  kilit.reset();
                  setAcOnayi(true);
                }}
              >
                <LockOpen className="size-3.5" /> Kilidi aç
              </Button>
              {!yonetici && <span className="text-xs text-muted-foreground">Dönem kilidini yalnız Genel Direktör açabilir.</span>}
            </>
          ) : (
            <Button
              type="button"
              size="sm"
              onClick={() => {
                kilit.reset();
                setAcUyari(null);
                setKapatOnayi(true);
              }}
            >
              <Lock className="size-3.5" /> Dönemi kapat (kilitle)
            </Button>
          )}
        </div>
        {acUyari && !kilitli && (
          <p role="status" className="flex flex-wrap items-center gap-2 rounded-xl bg-kart-sari px-4 py-3 text-sm">
            <TriangleAlert className="size-4 shrink-0 text-amber-700" aria-hidden />
            <span>Kilit açıldı. {acUyari}.</span>
            {sonraki && (
              <Link to={`/smm/veri?donem=${sonraki.id}`} className="font-semibold text-primary hover:underline">
                {sonraki.ad} veri girişine git
              </Link>
            )}
          </p>
        )}
      </section>

      {kapatOnayi && eksikler === null && (
        <OnayDiyalogu
          baslik={`${v.donem.ad} kapatılsın mı?`}
          onayMetni="Kapat ve kilitle"
          bekliyor={kilit.isPending}
          hata={eksikHatasi ? null : hataMetniVarsa(kilit.error)}
          onOnayla={() => kapat(false)}
          onVazgec={vazgec}
        >
          <p>
            Dönem kilitlenince veriler ve hesap ayarları değiştirilemez.{" "}
            {v.eksik.length > 0 && <b>Eksik veri var: {v.eksik.join(", ")}.</b>} Kilidi sonradan yalnız Genel Direktör açabilir.
          </p>
        </OnayDiyalogu>
      )}
      {kapatOnayi && eksikler !== null && (
        <OnayDiyalogu
          baslik={`${v.donem.ad} eksiklerle kapatılsın mı?`}
          onayMetni="Yine de kapat"
          bekliyor={kilit.isPending}
          hata={eksikHatasi ? null : hataMetniVarsa(kilit.error)}
          onOnayla={() => kapat(true)}
          onVazgec={vazgec}
        >
          <p>Dönem kapatılmadan önce şunlar eksik görünüyor:</p>
          <ul aria-label="Kapanış eksikleri" className="list-disc pl-5">
            {eksikler.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <p>Yine de kapatırsanız bu eksikler günlüğe yazılır.</p>
        </OnayDiyalogu>
      )}
      {acOnayi && (
        <OnayDiyalogu
          baslik={`${v.donem.ad} kilidi açılsın mı?`}
          onayMetni="Kilidi aç"
          bekliyor={kilit.isPending}
          hata={hataMetniVarsa(kilit.error)}
          onOnayla={() =>
            kilit.mutate(
              { donemId: v.donem.id, kilitli: false },
              {
                onSuccess: (d) => {
                  setAcUyari(d.uyari ?? null);
                  setAcOnayi(false);
                },
              },
            )
          }
          onVazgec={vazgec}
        >
          <p>Kilit açılınca dönemin verileri ve hesap ayarları yeniden değiştirilebilir.</p>
          {sonraki &&
            (sonraki.kilitli ? (
              <p>
                <b>Önce {sonraki.ad} kilidini açın:</b> açılışı bu dönemden devralındı ve o dönem kapalı.
              </p>
            ) : (
              <p>
                <b>{sonraki.ad} açılışı bu dönemden devralındı;</b> değişiklik sonrası {sonraki.ad} döneminde devri yenileyin.
              </p>
            ))}
        </OnayDiyalogu>
      )}
    </>
  );
}
