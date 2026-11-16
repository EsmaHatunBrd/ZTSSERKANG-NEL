import { useState } from "react";
import { Link } from "react-router-dom";
import { CircleCheck, CircleDashed, Lock, TriangleAlert, Upload } from "lucide-react";
import { hataMetniVarsa } from "@/api/istemci";
import { useSmmAyarlar, useSmmVeriDurumu, useSmmVeriOnizle, useSmmVeriYukle } from "@/api/sorgular/smm";
import type { SmmVeriDurumu } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { satirKaybi, useSatirKaybiOnayi } from "@/bilesenler/SatirKaybiOnayi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { SonYuklemeSeridi } from "@/bilesenler/SonYuklemeSeridi";
import { YuklemeOzetiKutusu, type YuklemeOzetiT } from "@/bilesenler/YuklemeOzetiKutusu";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { DonemSecici, DonemYok, useSmmDonemSecimi } from "./ortak";
import { DevirBolumu, KapanisBolumu, kilitTarihi } from "./SmmDevirKilit";
import { SmmMizanBolumu } from "./SmmMizanDuzenle";
import { SmmDuzenlemeKilidi, useSmmYazmaKilidi } from "./SmmDuzenlemeKilidi";
import { KAYNAK_SABLONU, SmmOnizlemeKutusu, SmmYuklemeYardimi } from "./SmmYukleme";

type Kaynak = SmmVeriDurumu["kaynaklar"][number];
const kutu = (x: string) => D(x).toFixed().replace(".", ",");

/** Bir veri kaynağı satırı: durum, son yükleme, dosya seçimi → önizleme → uygula; son yüklemeyi geri al. */
function KaynakSatiri({ k, donemId, kilitli }: { k: Kaynak; donemId: number; kilitli: boolean }) {
  const yukle = useSmmVeriYukle(donemId);
  const onizle = useSmmVeriOnizle(donemId);
  const kayip = useSatirKaybiOnayi();
  const [dosya, setDosya] = useState<File | null>(null);
  const [anahtar, setAnahtar] = useState(0);
  const [mizanAcik, setMizanAcik] = useState(false);
  const [yuklemeOnayi, setYuklemeOnayi] = useState(false);
  const [sonuc, setSonuc] = useState<YuklemeOzetiT | null>(null);
  const { kilitli: yazmaKilitli, neden: kilitNedeni } = useSmmYazmaKilidi(kilitli);
  const son = k.son;
  const mizanTur = k.kaynak === "gider_mizan" ? "gider" : k.kaynak === "stok_mizan" ? "stok" : null;
  const elle = k.elle ?? 0;
  const on = onizle.data;
  const gonder = (onay = false) =>
    dosya &&
    yukle.mutate(
      { kaynak: k.kaynak, dosya, onay },
      {
        onSuccess: (v) => {
          setSonuc(v.yukleme ?? null);
          setDosya(null);
          setAnahtar((x) => x + 1);
          setYuklemeOnayi(false);
          onizle.reset();
        },
        onError: (e) => {
          setYuklemeOnayi(false);
          kayip.yakala(e, () => gonder(true));
        },
      },
    );
  const uygula = () => ((on?.elle_silinecek ?? elle) > 0 ? setYuklemeOnayi(true) : gonder());
  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      {k.yuklendi ? (
        <CircleCheck className="size-5 shrink-0 text-green-700 dark:text-green-400" aria-label="Yüklendi" />
      ) : (
        <CircleDashed className={cn("size-5 shrink-0", k.zorunlu ? "text-amber-600" : "text-muted-foreground")} aria-label="Eksik" />
      )}
      <span className="flex min-w-56 flex-1 flex-col">
        <span className="font-medium">
          {k.ad}
          {k.zorunlu && !k.yuklendi && <span className="ml-2 rounded-full bg-kart-sari px-2 py-0.5 text-xs font-medium">Gerekli</span>}
        </span>
        <span className="text-xs text-muted-foreground">
          {k.yuklendi ? `${k.dolu} kayıt` : "Henüz yok"}
          {son && ` · ${son.excel ? "SMM Excel'inden" : (son.dosya ?? "elle")} · ${son.kullanici ?? ""}`}
          {son?.zaman && ` · ${new Date(son.zaman).toLocaleString("tr-TR")}`}
          {elle > 0 && ` · ${elle} elle satır`}
        </span>
      </span>
      {mizanTur && (
        <Button type="button" size="sm" variant="ghost" aria-expanded={mizanAcik} onClick={() => setMizanAcik((x) => !x)}>
          {mizanAcik ? "Satırları gizle" : kilitli ? "Satırları gör" : "Satırları gör / düzenle"}
        </Button>
      )}
      {!kilitli && (
        <span className="flex flex-wrap items-center gap-2">
          <Input
            key={anahtar}
            type="file"
            accept=".xlsx"
            aria-label={`${k.ad} dosyası`}
            className="w-64"
            disabled={yazmaKilitli}
            title={kilitNedeni}
            onChange={(e) => {
              setDosya(e.target.files?.[0] ?? null);
              yukle.reset();
              onizle.reset();
              setSonuc(null);
            }}
          />
          <Button
            type="button"
            size="sm"
            variant={k.yuklendi ? "outline" : "default"}
            aria-label={`Önizle — ${k.ad}`}
            disabled={yazmaKilitli || !dosya || onizle.isPending}
            title={kilitNedeni}
            onClick={() => dosya && onizle.mutate({ kaynak: k.kaynak, dosya })}
          >
            <Upload className="size-3.5" /> {onizle.isPending ? "Okunuyor…" : k.yuklendi ? "Yeniden yükle: önizle" : "Önizle"}
          </Button>
        </span>
      )}
      {!kilitli && (
        <span className="w-full pl-8">
          <SmmYuklemeYardimi kimlik={KAYNAK_SABLONU[k.kaynak]} />
        </span>
      )}
      {(hataMetniVarsa(onizle.error) || (hataMetniVarsa(yukle.error) && !satirKaybi(yukle.error))) && (
        <p role="alert" className="w-full pl-8 text-sm text-destructive">
          {hataMetniVarsa(onizle.error) ?? hataMetniVarsa(yukle.error)}
        </p>
      )}
      {on && dosya && !kilitli && (
        <div className="w-full pl-8">
          <SmmOnizlemeKutusu
            ozet={on}
            baslik={`${k.ad} — sorunlu satırlar`}
            uygulaMetni={k.yuklendi ? "Uygula (eskisinin yerine geçer)" : "Uygula"}
            uygulanamaz={yazmaKilitli || on.dosyadaki === 0}
            bekliyor={yukle.isPending}
            kilitNedeni={kilitNedeni}
            onUygula={uygula}
            onVazgec={() => onizle.reset()}
          >
            <p className="text-xs text-muted-foreground">
              Dosyada {on.dosyadaki} {mizanTur ? "hesap" : "kalem"}; dönemde şu an {on.mevcut}.
            </p>
          </SmmOnizlemeKutusu>
        </div>
      )}
      {sonuc && sonuc.sorunlu.length > 0 && (
        <div className="w-full pl-8">
          <p role="status" className="mb-2 text-sm">
            Yüklendi; <b>{sonuc.sorunlu.length} sorunlu satır yazılmadı.</b> Dosyayı düzeltip yeniden yükleyebilirsiniz.
          </p>
          <YuklemeOzetiKutusu ozet={sonuc} baslik={`${k.ad} — yazılmayan satırlar`} />
        </div>
      )}
      {!kilitli && (
        <div className="w-full pl-8">
          <SonYuklemeSeridi
            yol={`/api/v1/smm/donemler/${donemId}/veri/${k.kaynak}`}
            sorgu={{}}
            kilitli={yazmaKilitli}
            kilitNedeni={kilitNedeni}
            gecersiz={["smm"]}
          />
        </div>
      )}
      {mizanTur && mizanAcik && <SmmMizanBolumu donemId={donemId} tur={mizanTur} kilitli={kilitli} />}
      {yuklemeOnayi && !yazmaKilitli && (
        <OnayDiyalogu
          baslik={`${k.ad} yeniden yüklensin mi?`}
          onayMetni="Yükle ve elle satırları sil"
          bekliyor={yukle.isPending}
          hata={satirKaybi(yukle.error) ? null : hataMetniVarsa(yukle.error)}
          onOnayla={() => gonder()}
          onVazgec={() => setYuklemeOnayi(false)}
        >
          <p>
            <b>{k.elle_uyari ?? `${on?.elle_silinecek ?? elle} elle satır var, yükleme bunları siler`}.</b> Yükleme bu mizanı dosyadakilerle
            baştan yazar; elle girdiğiniz ya da düzelttiğiniz satırlar kaybolur (eski değerler günlükte kalır).
          </p>
        </OnayDiyalogu>
      )}
      {kayip.diyalog}
    </li>
  );
}

/** Finansman (alımlara dağıtılır) ve 720 / 730 gider tutarları. */
function AyarKarti({ v, donemId, kilitli }: { v: SmmVeriDurumu; donemId: number; kilitli: boolean }) {
  const kaydet = useSmmAyarlar(donemId);
  const { kilitli: yazmaKilitli, neden: kilitNedeni } = useSmmYazmaKilidi(kilitli);
  const ilk = { finansman: kutu(v.ayarlar.finansman), gider_720: kutu(v.ayarlar.gider_720), gider_730: kutu(v.ayarlar.gider_730) };
  const [t, setT] = useState(ilk);
  const degisen = (Object.keys(t) as (keyof typeof t)[]).filter((a) => t[a] !== ilk[a]);
  const gecersiz = degisen.some((a) => sayiApi(t[a]) === null);
  const ADLAR = {
    finansman: "Finansman gideri (alımlara dağıtılır)",
    gider_720: "720 Direkt işçilik",
    gider_730: "730 Genel üretim gideri",
  };
  return (
    <section aria-label="Gider tutarları" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <h2 className="text-base font-semibold">Gider tutarları</h2>
      <p className="text-sm text-muted-foreground">Gider mizanı yüklenince 720 / 730 oradan gelir; burada elle de düzeltebilirsiniz.</p>
      <div className="grid gap-3 sm:grid-cols-3">
        {(Object.keys(ADLAR) as (keyof typeof ADLAR)[]).map((a) => (
          <label key={a} className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">{ADLAR[a]}</span>
            <Input
              inputMode="decimal"
              aria-label={ADLAR[a]}
              disabled={yazmaKilitli}
              title={kilitNedeni}
              value={t[a]}
              onChange={(e) => setT({ ...t, [a]: e.target.value })}
            />
          </label>
        ))}
      </div>
      {hataMetniVarsa(kaydet.error) && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetniVarsa(kaydet.error)}
        </p>
      )}
      {!kilitli && (
        <div className="flex justify-end">
          <Button
            type="button"
            size="sm"
            disabled={yazmaKilitli || degisen.length === 0 || gecersiz || kaydet.isPending}
            title={kilitNedeni}
            onClick={() => kaydet.mutate(Object.fromEntries(degisen.map((a) => [a, sayiApi(t[a])])))}
          >
            Kaydet
          </Button>
        </div>
      )}
    </section>
  );
}

/**
 * Aylık veri girişi: dönemin veri kaynakları (alım-satış, iade, üretim, sayım, şahit, gider ve stok mizanı) ayrı ayrı yüklenir; kontrol
 * listesi neyin eksik olduğunu gösterir. Açılış stoku önceki ayın kapanışıyla uyuşmuyorsa uyarır (devri yenile). Dönem kapatılınca
 * (kilit) değişiklik yapılamaz; SMM fişi Excel olarak indirilir.
 */
export default function SmmVeri() {
  const secim = useSmmDonemSecimi();
  const q = useSmmVeriDurumu(secim.donemId);
  const v = q.data;
  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Veri Girişi" />
        <DonemYok />
      </section>
    );
  }
  const kilitli = Boolean(v?.donem.kilitli);
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Veri Girişi"
        altBaslik="Dönemin aylık verileri: her kaynağı ayrı yükleyin; eksikler aşağıda işaretli. Kalemleri tek tek düzeltmek için Stok ve Envanter'de satıra tıklayın."
        eylemler={<DonemSecici secim={secim} />}
      />
      <SmmDuzenlemeKilidi donemKilitli={kilitli} />
      {v && (
        <>
          {kilitli ? (
            <p className="flex flex-wrap items-center gap-2 rounded-xl bg-muted px-4 py-3 text-sm">
              <Lock className="size-4" aria-hidden />
              <b>{v.donem.ad}</b> kapatıldı
              {v.donem.kilitleyen ? ` (${[v.donem.kilitleyen, kilitTarihi(v.donem.kilit_zamani)].filter(Boolean).join(" · ")})` : ""};
              veriler değiştirilemez.
            </p>
          ) : v.eksik.length > 0 ? (
            <p className="flex flex-wrap items-center gap-2 rounded-xl bg-kart-sari px-4 py-3 text-sm">
              <TriangleAlert className="size-4 text-amber-700" aria-hidden />
              Eksik: <b>{v.eksik.join(", ")}</b>. Bunlar olmadan SMM hesabı eksik çıkar.
            </p>
          ) : (
            <p className="flex items-center gap-2 rounded-xl bg-kart-yesil px-4 py-3 text-sm">
              <CircleCheck className="size-4 text-green-700" aria-hidden />
              Gerekli veriler tamam.{" "}
              <Link to={`/smm/ozet?donem=${v.donem.id}`} className="font-semibold text-primary hover:underline">
                SMM Özeti'ne git
              </Link>
            </p>
          )}

          <DevirBolumu key={v.donem.id} v={v} />

          {v.grupsuz && v.grupsuz.kalem > 0 && (
            <p className="flex flex-wrap items-center gap-2 rounded-xl bg-kart-sari px-4 py-3 text-sm">
              <TriangleAlert className="size-4 text-amber-700" aria-hidden />
              <span>
                <b>{v.grupsuz.kalem} kalemin türü / mizan kodu boş</b>; bunlar SMM tablosuna girmiyor (alım{" "}
                {paraBicimle(v.grupsuz.alim_tutar, "TL", 0)}, dönem başı {paraBicimle(v.grupsuz.dbs_tutar, "TL", 0)}). Örnek:{" "}
                {v.grupsuz.ornek.join(", ")}.{" "}
                <Link to={`/smm/stok?donem=${v.donem.id}`} className="font-semibold text-primary hover:underline">
                  Stok ve Envanter'de türünü girin
                </Link>
              </span>
            </p>
          )}

          <section aria-label="Veri kaynakları" className="rounded-2xl border bg-card px-5 py-2 shadow-xs">
            <ul className="flex flex-col divide-y">
              <li className="flex items-center gap-3 py-3">
                {v.donem_basi.hazir ? (
                  <CircleCheck className="size-5 shrink-0 text-green-700 dark:text-green-400" aria-label="Hazır" />
                ) : (
                  <CircleDashed className="size-5 shrink-0 text-amber-600" aria-label="Eksik" />
                )}
                <span className="flex flex-col">
                  <span className="font-medium">Dönem başı stok</span>
                  <span className="text-xs text-muted-foreground">
                    {v.donem_basi.kaynak === "devir"
                      ? "Önceki dönemin sayımından devredildi"
                      : v.donem_basi.kaynak === "excel"
                        ? "SMM Excel'inden (DBS)"
                        : "Yok — ilk dönemse kalemlere elle girin"}{" "}
                    · {v.donem_basi.dolu} kalem · {paraBicimle(v.donem_basi.tutar, "TL", 0)}
                  </span>
                </span>
              </li>
              {v.kaynaklar.map((k) => (
                <KaynakSatiri key={k.kaynak} k={k} donemId={v.donem.id} kilitli={kilitli} />
              ))}
            </ul>
          </section>
          <p className="-mt-2 text-xs text-muted-foreground">
            Dosya, bugünkü SMM Excel'inin ilgili sayfası (HM-YM ALIŞ SATIŞ, İADELER, ÜRETİM, DSS, ŞAHİT, GİDER MİZAN, STOK MİZAN), şablon ya
            da tek sayfalık bir Canias raporu olabilir. Önce önizleme gösterilir; "Uygula" o kaynağın eski verisinin yerine geçer, boş ya da
            yanlış dosya veriyi değiştirmez. Son yükleme "Geri al" ile geri alınabilir. Gider ve stok mizanı satırları "Satırları gör /
            düzenle" ile elle de girilebilir.
          </p>

          <AyarKarti
            key={`${v.donem.id}-${v.ayarlar.finansman}-${v.ayarlar.gider_720}-${v.ayarlar.gider_730}`}
            v={v}
            donemId={v.donem.id}
            kilitli={kilitli}
          />

          <KapanisBolumu key={v.donem.id} v={v} liste={secim.liste} />
        </>
      )}
    </section>
  );
}
