import { CircleCheck, Download, Factory, Lock, PackageCheck, Sigma, TriangleAlert, Wheat } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { smmFisAdresi, useSmmOzet } from "@/api/sorgular/smm";
import type { SmmOzeti } from "@/api/tipler";
import { OnayCiktisiDugmesi } from "@/bilesenler/OnayCiktisiDiyalogu";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { cn } from "@/lib/utils";
import { Kart } from "@/sayfalar/dashboard/UstKartlar";
import { D, paraBicimle } from "@/yardimcilar/para";
import { DonemSecici, DonemYok, milyon, useSmmDonemSecimi } from "./ortak";
import { MusavirExcelBilgisi, MusavirExcelDugmesi } from "./SmmMusavirExcel";

const tl = (x: string | null | undefined) => (x === null || x === undefined ? "—" : paraBicimle(x, "TL", 2));

/** SMM tablosu: Excel SMM sayfasının düzeni; her blok bir stok hesabının hareketi ve sonucu. */
function Tablo({ v }: { v: SmmOzeti }) {
  return (
    <section aria-label="SMM tablosu" className="grid gap-4 lg:grid-cols-2">
      {v.tablo.map((b) => (
        <div key={b.hesap} className="flex flex-col rounded-2xl border bg-card shadow-xs">
          <h2 className="flex items-baseline gap-2 border-b px-5 py-3 text-base font-semibold">
            <span className="text-muted-foreground tabular-nums">{b.hesap}</span>
            {b.ad}
            {b.kalem > 0 && <span className="ml-auto text-xs font-normal text-muted-foreground">{b.kalem} kalem</span>}
          </h2>
          <table className="w-full text-sm">
            <tbody className="divide-y">
              {b.satirlar.map((s) => (
                <tr key={s.ad}>
                  <td className="w-8 py-1.5 pl-5 text-center text-muted-foreground">{s.isaret}</td>
                  <td className="py-1.5">{s.ad}</td>
                  <td className={cn("py-1.5 pr-5 text-right tabular-nums", D(s.tutar).isZero() && "text-muted-foreground")}>
                    {tl(s.tutar)}
                  </td>
                </tr>
              ))}
              <tr className="bg-kart-yesil font-semibold">
                <td className="py-2 pl-5 text-center">=</td>
                <td className="py-2">{b.sonuc_ad}</td>
                <td className="py-2 pr-5 text-right tabular-nums">{tl(b.sonuc)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}

/**
 * SMM özeti (3. adım): dönem sonu stok değerlemesi (Excel DSS), SMM tablosu, Excel'deki stok mizanıyla karşılaştırma ve SMM fişi taslağı.
 */
export default function SmmOzet() {
  const secim = useSmmDonemSecimi();
  const q = useSmmOzet(secim.donemId);
  const v = q.data;

  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="SMM Özeti" />
        <DonemYok />
      </section>
    );
  }

  const dk = v?.dss_kiyas;
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="SMM Özeti"
        altBaslik="Dönem sonu stok değerlemesi, satılan mamul maliyeti tablosu, stok mizanıyla karşılaştırma ve SMM fişi taslağı."
        eylemler={
          <span className="flex flex-wrap items-center gap-2">
            {secim.donemId !== null && (
              <OnayCiktisiDugmesi
                kapsam={{
                  modul: "smm",
                  donemId: secim.donemId,
                  donemler: secim.liste.map((d) => ({ id: d.id, ad: d.ad, kilitli: Boolean(d.kilitli) })),
                }}
              />
            )}
            {secim.donemId !== null && (
              <a
                href={smmFisAdresi(secim.donemId)}
                download
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium hover:bg-accent"
              >
                <Download className="size-3.5" /> Fişi indir (.xlsx)
              </a>
            )}
            {secim.donemId !== null && <MusavirExcelDugmesi donemId={secim.donemId} />}
            <DonemSecici secim={secim} />
          </span>
        }
      />
      {q.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(q.error)}
        </p>
      )}
      {secim.donemId !== null && <MusavirExcelBilgisi donemId={secim.donemId} />}
      {q.isPending && secim.donemId !== null && <p className="text-sm text-muted-foreground">Hesaplanıyor…</p>}

      {v?.donem.kilitli && (
        <p className="flex items-center gap-2 rounded-xl bg-muted px-4 py-2 text-sm">
          <Lock className="size-4" aria-hidden /> Bu dönem kapatıldı{v.donem.kilitleyen ? ` (${v.donem.kilitleyen})` : ""}.
        </p>
      )}
      {v && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Kart baslik="Satılan mamul maliyeti (620)" deger={milyon(v.smm)} simge={Sigma} renk="acik" />
            <Kart baslik="Üretim maliyeti" deger={milyon(v.uretim_maliyeti)} simge={Factory} renk="acik" />
            <Kart baslik="İlk madde ve malzeme gideri (710)" deger={milyon(v.ilk_madde)} simge={Wheat} renk="acik" />
            <Kart baslik="Dönem sonu stok (sayım)" deger={milyon(v.donem_sonu_stok)} simge={PackageCheck} renk="acik" />
          </div>

          {dk && dk.karsilastirilan > 0 && (
            <p role="status" className="flex items-start gap-2 text-sm">
              {dk.farkli === 0 ? (
                <CircleCheck className="mt-0.5 size-4 shrink-0 text-green-700 dark:text-green-400" aria-hidden />
              ) : (
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
              )}
              <span>
                Dönem sonu stok tutarları Excel'in DSS sayfasıyla karşılaştırıldı: {dk.karsilastirilan} kalemin <b>{dk.esit}</b>'i aynı
                {dk.farkli > 0 ? `, ${dk.farkli} kalem farklı` : ""} (Excel {paraBicimle(dk.excel_toplam, "TL", 2)}, uygulama{" "}
                {paraBicimle(dk.bizim_toplam, "TL", 2)}).
              </span>
            </p>
          )}

          <Tablo v={v} />
          <p className="-mt-2 text-xs text-muted-foreground">
            720 ve 730 gider mizanının dönem bakiyesi (tamamı) alındı. Mizanda şimdiye kadar yansıtılan: 721 {tl(v.yansitilan["721"])}, 731{" "}
            {tl(v.yansitilan["731"])}. Dönem içi satılan hammadde ve yarı mamul: {tl(v.satilan_hm_ym)}.
          </p>

          <section aria-label="Stok mizanı karşılaştırması" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
            <h2 className="text-base font-semibold">Stok mizanı ile sayım</h2>
            {v.mizan_kiyas.length === 0 ? (
              <p className="text-sm text-muted-foreground">Excel'de stok mizanı (STOK MİZAN sayfası) yok.</p>
            ) : (
              <>
                {v.mizan_tarihi && (
                  <p className="flex items-start gap-2 text-sm">
                    <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
                    <span>
                      Excel'deki stok mizanının tarihi <b>{v.mizan_tarihi}</b> görünüyor; dönemle aynı değilse farklar mizanın eski
                      olmasından gelir. Excel'in kendi karşılaştırması da çalışmıyor: sayım hesap kodları eski planda (150.03.001), mizan
                      yenisinde (150.003.031).
                    </span>
                  </p>
                )}
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-muted-foreground uppercase">
                        <th className="py-1.5 font-medium">Hesap</th>
                        <th className="py-1.5 text-right font-medium">Mizan bakiyesi</th>
                        <th className="py-1.5 text-right font-medium">Sayım tutarı</th>
                        <th className="py-1.5 text-right font-medium">Fark</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {v.mizan_kiyas.map((m) => (
                        <tr key={m.hesap}>
                          <td className="py-1.5">
                            <span className="mr-2 text-muted-foreground tabular-nums">{m.hesap}</span>
                            {m.ad}
                          </td>
                          <td className="py-1.5 text-right tabular-nums">{tl(m.mizan)}</td>
                          <td className="py-1.5 text-right tabular-nums">{tl(m.sayim)}</td>
                          <td className="py-1.5 text-right font-semibold tabular-nums">{tl(m.fark)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>

          <section aria-label="SMM fişi taslağı" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              SMM fişi taslağı
              <span className="rounded-full bg-kart-sari px-2 py-0.5 text-xs font-medium">Taslak · muhasebe kontrol etmeli</span>
            </h2>
            <p className="text-sm text-muted-foreground">
              Excel'deki kurallarla: 710-B / 150-A, 151-B / 711-A, 151-B / 721-A ve 731-A, 152-B / 151-A, 620-B / 152-A. Mizanda zaten
              yapılmış yansıtmalar varsa o satırlar çıkarılmalı.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-muted-foreground uppercase">
                    <th className="py-1.5 font-medium">Hesap</th>
                    <th className="py-1.5 font-medium">Açıklama</th>
                    <th className="py-1.5 text-right font-medium">Borç</th>
                    <th className="py-1.5 text-right font-medium">Alacak</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {v.fis.map((f, i) => (
                    <tr key={`${f.hesap}-${i}`}>
                      <td className={cn("py-1.5", D(f.alacak).gt(0) && "pl-6")}>
                        <span className="mr-2 font-medium tabular-nums">{f.hesap}</span>
                        <span className="text-muted-foreground">{f.ad}</span>
                      </td>
                      <td className="py-1.5 text-muted-foreground">{f.aciklama}</td>
                      <td className="py-1.5 text-right tabular-nums">{D(f.borc).isZero() ? "" : tl(f.borc)}</td>
                      <td className="py-1.5 text-right tabular-nums">{D(f.alacak).isZero() ? "" : tl(f.alacak)}</td>
                    </tr>
                  ))}
                  <tr className="font-semibold">
                    <td className="py-2" colSpan={2}>
                      Toplam
                    </td>
                    <td className="py-2 text-right tabular-nums">{tl(v.fis_borc)}</td>
                    <td className="py-2 text-right tabular-nums">{tl(v.fis_alacak)}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </section>
  );
}
