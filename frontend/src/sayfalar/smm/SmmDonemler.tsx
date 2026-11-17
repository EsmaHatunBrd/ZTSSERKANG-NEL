import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarPlus, CalendarRange, CircleCheck, FileSpreadsheet, Lock, TriangleAlert, Upload } from "lucide-react";
import { ApiHatasi, hataMetni, hataMetniVarsa } from "@/api/istemci";
import { useSmmDonemleri, useSmmDonemOnizle, useSmmReceteKaynagi, useSmmSil, useSmmYeniDonem, useSmmYukle } from "@/api/sorgular/smm";
import type { SmmDonem } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { satirKaybi, useSatirKaybiOnayi } from "@/bilesenler/SatirKaybiOnayi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { SonYuklemeSeridi } from "@/bilesenler/SonYuklemeSeridi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { paraBicimle } from "@/yardimcilar/para";
import { kilitTarihi } from "./SmmDevirKilit";
import { SmmDuzenlemeKilidi, useSmmYazmaKilidi } from "./SmmDuzenlemeKilidi";
import { MusavirSablonKarti } from "./SmmMusavirExcel";
import { SmmOnizlemeKutusu, SmmYuklemeYardimi } from "./SmmYukleme";

const AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const SECIM_SINIFI = "h-8 rounded-lg border border-input bg-background px-2 text-sm";

/** '09-2026 SMM v1.xlsx' -> {ay: 9, yil: 2026}. */
export function dosyadanDonem(ad: string): { ay: number; yil: number } | null {
  const e = /(?<!\d)(\d{1,2})[-_. ](\d{4})(?!\d)/.exec(ad);
  if (!e) return null;
  const ay = Number(e[1]);
  return ay >= 1 && ay <= 12 ? { ay, yil: Number(e[2]) } : null;
}

/** Yüklenen Excel'in kendi hesabıyla karşılaştırma özeti. */
function ExcelKontrol({ d }: { d: SmmDonem }) {
  const k = d.excel_kontrol;
  if (!k) return null;
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      <li className="flex items-start gap-2">
        <CircleCheck className="mt-0.5 size-4 shrink-0 text-green-700 dark:text-green-400" aria-hidden />
        <span>
          {k.karsilastirilan} kalemin <b>{k.esit}</b>'i Excel'in kendi hesabıyla birebir aynı{k.farkli ? `; ${k.farkli} kalem farklı` : ""}.
        </span>
      </li>
      {k.excelde_sarf_bos > 0 && (
        <li className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
          <span>
            Excel'de <b>{k.excelde_sarf_bos}</b> kalemin sarf formülü boş bırakılmış; bu kalemlerin sarfı (
            {paraBicimle(k.excelde_sarf_bos_tutar, "TL", 0)}) Excel toplamlarına girmiyor. Uygulama bunları hesaplıyor.
          </span>
        </li>
      )}
      {(k.excelde_tekrar?.length ?? 0) > 0 && (
        <li className="flex items-start gap-2">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden />
          <span>
            Excel'in TABLO sayfasında <b>{k.excelde_tekrar.length}</b> kod iki kez yazılmış ({k.excelde_tekrar.slice(0, 3).join(", ")}
            {k.excelde_tekrar.length > 3 ? " …" : ""}); toplamlarda çift sayılıyor olabilir.
          </span>
        </li>
      )}
    </ul>
  );
}

/** Dönemin aşama hesabında kullandığı reçete: dönemle yüklenen Excel reçetesi ya da kalıcı Canias reçeteleri. */
function ReceteKaynagiSecici({ d }: { d: SmmDonem }) {
  const degistir = useSmmReceteKaynagi();
  const { kilitli, neden } = useSmmYazmaKilidi(Boolean(d.kilitli));
  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      Reçete
      <select
        aria-label={`Reçete kaynağı — ${d.ad}`}
        className={SECIM_SINIFI}
        value={d.recete_kaynagi ?? "excel"}
        disabled={kilitli || degistir.isPending}
        title={neden}
        onChange={(e) => degistir.mutate({ donemId: d.id, kaynak: e.target.value as "excel" | "ana" })}
      >
        {d.kaynak_dosya && <option value="excel">Excel'deki</option>}
        <option value="ana">Canias (kalıcı)</option>
      </select>
      {degistir.error && <span className="text-destructive">{hataMetni(degistir.error)}</span>}
    </label>
  );
}

/** Dönem satırının alt bilgisi: açılışın hangi ayın kapanışından geldiği (o ay kapalı değilse uyarı rozeti) ve kapanış (kim, ne zaman). */
function DonemDurumu({ d, liste }: { d: SmmDonem; liste: SmmDonem[] }) {
  const onceki = d.devir_donem_id ? liste.find((x) => x.id === d.devir_donem_id) : undefined;
  if (!onceki && !d.kilitli) return null;
  return (
    <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
      {onceki && <span>Açılış: {onceki.ad} kapanışından</span>}
      {onceki && !onceki.kilitli && (
        <span
          className="inline-flex items-center gap-1 rounded-full bg-kart-sari px-2 py-0.5 font-medium text-foreground"
          title={`${onceki.ad} kapatılmadı; devir sonradan değişebilir`}
        >
          <TriangleAlert className="size-3 text-amber-700" aria-hidden />
          {onceki.ad} kapalı değil
        </span>
      )}
      {d.kilitli && (
        <span className="inline-flex items-center gap-1 font-medium text-foreground">
          <Lock className="size-3" aria-hidden />
          {["Kapalı", d.kilitleyen, kilitTarihi(d.kilit_zamani)].filter(Boolean).join(" · ")}
        </span>
      )}
    </span>
  );
}

/** Excel'siz yeni dönem: dönem başı stok önceki dönemin sayımından devreder. */
function YeniDonemKarti({ liste }: { liste: SmmDonem[] }) {
  const yeni = useSmmYeniDonem();
  const { kilitli, neden } = useSmmYazmaKilidi();
  const son = liste[0];
  const sonraki = son ? (son.ay === 12 ? { ay: 1, yil: son.yil + 1 } : { ay: son.ay + 1, yil: son.yil }) : null;
  const [ay, setAy] = useState<number | null>(null);
  const [yil, setYil] = useState<number | null>(null);
  const a = ay ?? sonraki?.ay ?? new Date().getMonth() + 1;
  const y = yil ?? sonraki?.yil ?? new Date().getFullYear();
  return (
    <section aria-label="Yeni dönem aç" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-kart-yesil text-primary" aria-hidden>
          <CalendarPlus className="size-5" />
        </span>
        <div>
          <h2 className="text-base font-semibold">Yeni dönem aç</h2>
          <p className="text-sm text-muted-foreground">
            Dönem başı stok, önceki dönemin sayımla bulunan dönem sonu stokundan (miktar ve tutar) otomatik gelir. Stok kartları, üretim
            süreleri ve dağıtım tutarları kopyalanır; reçeteler Canias'tan yüklenen kalıcı reçetelerdir.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Yeni dönem ayı</span>
          <select aria-label="Yeni dönem ayı" className={SECIM_SINIFI} value={a} onChange={(e) => setAy(Number(e.target.value))}>
            {AYLAR.map((x, i) => (
              <option key={x} value={i + 1}>
                {x}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Yılı</span>
          <Input
            aria-label="Yeni dönem yılı"
            inputMode="numeric"
            className="w-24"
            value={y}
            onChange={(e) => setYil(Number(e.target.value) || y)}
          />
        </label>
        <Button type="button" disabled={kilitli || yeni.isPending} title={neden} onClick={() => yeni.mutate({ yil: y, ay: a })}>
          {yeni.isPending ? "Açılıyor…" : `${AYLAR[a - 1]} ${y} dönemini aç`}
        </Button>
        {son && <span className="text-sm text-muted-foreground">Devir: {son.ad}</span>}
      </div>
      {yeni.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(yeni.error)}
        </p>
      )}
      {yeni.data && (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-xl bg-kart-yesil px-4 py-3 text-sm">
          <CircleCheck className="size-4 text-green-700 dark:text-green-400" aria-hidden />
          {yeni.data.ad} açıldı.{" "}
          {yeni.data.devir.onceki
            ? `${yeni.data.devir.onceki} sayımından ${yeni.data.devir.kalem} kalem, ${paraBicimle(yeni.data.devir.tutar, "TL", 0)} dönem başı stok devredildi.`
            : "Önceki dönem yok; dönem başı stok boş."}{" "}
          Alım, üretim ve sayım verileri bu dönem için yüklenecek.
          <Link to={`/smm/stok?donem=${yeni.data.id}`} className="font-semibold text-primary underline-offset-4 hover:underline">
            Stok ve envantere git
          </Link>
        </p>
      )}
      {yeni.data?.devir.uyari && (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-xl bg-kart-sari px-4 py-3 text-sm">
          <TriangleAlert className="size-4 shrink-0 text-amber-700" aria-hidden />
          <span>
            <b>{yeni.data.devir.uyari}.</b> {yeni.data.devir.onceki} kapanışı değişirse Veri Girişi'nde "Devri yenile" ile açılışı
            güncelleyin.
          </span>
        </p>
      )}
    </section>
  );
}

/** Maliyet muhasebesi: aylık SMM Excel'ini dönem olarak yükleme ve yüklü dönemler. */
export default function SmmDonemler() {
  const donemler = useSmmDonemleri();
  const yukle = useSmmYukle();
  const onizle = useSmmDonemOnizle();
  const kayip = useSatirKaybiOnayi();
  const sil = useSmmSil();
  const { kilitli, neden } = useSmmYazmaKilidi();
  const dosyaRef = useRef<HTMLInputElement>(null);
  const [dosya, setDosya] = useState<File | null>(null);
  const [ay, setAy] = useState<number>(new Date().getMonth() + 1);
  const [yil, setYil] = useState<number>(new Date().getFullYear());
  const [ustuneYazOnayi, setUstuneYazOnayi] = useState(false);
  const [silinecek, setSilinecek] = useState<SmmDonem | null>(null);
  const [yuklenen, setYuklenen] = useState<SmmDonem | null>(null);

  function gonder(uzerineYaz = false, onay = false) {
    if (!dosya) return;
    setYuklenen(null);
    yukle.mutate(
      { dosya, yil, ay, uzerineYaz, onay },
      {
        onSuccess: (d) => {
          setYuklenen(d);
          setUstuneYazOnayi(false);
          setDosya(null);
          onizle.reset();
          if (dosyaRef.current) dosyaRef.current.value = "";
        },
        onError: (e) => {
          setUstuneYazOnayi(false);
          // önce "dönem zaten yüklü" (üzerine yaz), sonra "kalem yarıdan az" (satır kaybı) onayı
          if (kayip.yakala(e, () => gonder(true, true))) return;
          if (e instanceof ApiHatasi && e.durum === 409 && e.kod !== "donem_kilitli") setUstuneYazOnayi(true);
        },
      },
    );
  }

  const liste = donemler.data?.kayitlar ?? [];
  const cakisma = yukle.error instanceof ApiHatasi && yukle.error.durum === 409 && yukle.error.kod !== "donem_kilitli";
  const on = onizle.data;
  // seçili ay/yıl için var olan dönem: "Son yükleme — Geri al" şeridi onun için
  const seciliDonem = liste.find((d) => d.yil === yil && d.ay === ay) ?? null;
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi bant baslik="Maliyet Muhasebesi" altBaslik="Aylık SMM: dönem başı, alım, sayım, sarf ve ortalama maliyet" />
      <SmmDuzenlemeKilidi />

      <YeniDonemKarti liste={liste} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section aria-label="SMM Excel'i yükle" className="flex flex-col gap-4 rounded-2xl border bg-card p-5 shadow-xs">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-kart-yesil text-primary" aria-hidden>
              <Upload className="size-5" />
            </span>
            <div>
              <h2 className="text-base font-semibold">SMM Excel'inden yükle (isteğe bağlı)</h2>
              <p className="text-sm text-muted-foreground">
                Geçiş ve kontrol için: tüm verileri bugünkü SMM Excel'inden (DBS, HM-YM Alış Satış, DSS, TABLO, 20/40/50 KOD) alır ve
                uygulamanın hesabını Excel'inkiyle karşılaştırır. Ay dosya adından okunur.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex min-w-56 flex-1 flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Dosya (.xlsx)</span>
              <Input
                ref={dosyaRef}
                type="file"
                accept=".xlsx"
                aria-label="SMM dosyası"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setDosya(f);
                  yukle.reset();
                  onizle.reset();
                  setUstuneYazOnayi(false);
                  const dn = f ? dosyadanDonem(f.name) : null;
                  if (dn) {
                    setAy(dn.ay);
                    setYil(dn.yil);
                  }
                }}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Ay</span>
              <select
                aria-label="Ay"
                className={SECIM_SINIFI}
                value={ay}
                onChange={(e) => {
                  setAy(Number(e.target.value));
                  onizle.reset();
                }}
              >
                {AYLAR.map((a, i) => (
                  <option key={a} value={i + 1}>
                    {a}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Yıl</span>
              <Input
                aria-label="Yıl"
                inputMode="numeric"
                className="w-24"
                value={yil}
                onChange={(e) => {
                  setYil(Number(e.target.value) || yil);
                  onizle.reset();
                }}
              />
            </label>
            <Button
              type="button"
              variant="outline"
              disabled={!dosya || onizle.isPending}
              onClick={() => dosya && onizle.mutate({ dosya, yil, ay })}
            >
              {onizle.isPending ? "Okunuyor…" : "Önizle"}
            </Button>
          </div>
          <SmmYuklemeYardimi />
          {(onizle.error || (yukle.error && !cakisma && !satirKaybi(yukle.error))) && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetni(onizle.error ?? yukle.error)}
            </p>
          )}
          {on && dosya && (
            <SmmOnizlemeKutusu
              ozet={on}
              baslik="SMM Excel'i — sayı sütununda metin hücreler"
              uygulaMetni="Yükle"
              uygulanamaz={kilitli || on.kalem === 0 || on.kilitli}
              bekliyor={yukle.isPending}
              kilitNedeni={on.kilitli ? "Dönem kapatıldı" : neden}
              onUygula={() => gonder(false)}
              onVazgec={() => onizle.reset()}
            >
              <p className="text-sm">
                <b>{on.donem_ad}</b>: {on.kalem} stok kalemi, {on.recete_satiri} reçete satırı, {on.iscilik} üretim süresi.
                {on.mevcut_donem_id ? ` Dönem zaten var (${on.mevcut_kalem} kalem).` : " Yeni dönem açılacak."}
              </p>
              <p className="text-xs text-muted-foreground">Okunan sayfalar: {on.sayfalar.join(", ")}</p>
            </SmmOnizlemeKutusu>
          )}
          {seciliDonem && (
            <SonYuklemeSeridi
              yol={`/api/v1/smm/donemler/${seciliDonem.id}`}
              sorgu={{}}
              kilitli={kilitli || Boolean(seciliDonem.kilitli)}
              kilitNedeni={seciliDonem.kilitli ? "Dönem kapatıldı" : neden}
              gecersiz={["smm"]}
            />
          )}
          {yuklenen && (
            <div role="status" className="flex flex-col gap-2 rounded-xl bg-kart-yesil px-4 py-3 text-sm">
              <p className="font-medium">
                {yuklenen.ad} yüklendi: {yuklenen.kalem_sayisi} stok kalemi.{" "}
                <Link to={`/smm/stok?donem=${yuklenen.id}`} className="font-semibold text-primary underline-offset-4 hover:underline">
                  Stok ve envantere git
                </Link>
              </p>
              <ExcelKontrol d={yuklenen} />
            </div>
          )}
        </section>

        <section aria-label="Yüklü dönemler" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
          <h2 className="flex items-center gap-2 text-base font-semibold">
            <CalendarRange className="size-4 text-marka" aria-hidden />
            Yüklü dönemler
          </h2>
          {donemler.isPending ? (
            <p className="text-sm text-muted-foreground">Yükleniyor…</p>
          ) : liste.length === 0 ? (
            <p className="text-sm text-muted-foreground">Henüz dönem yok. Soldan bir SMM Excel'i yükleyin.</p>
          ) : (
            <ul className="flex flex-col divide-y">
              {liste.map((d) => (
                <li key={d.id} className="flex flex-wrap items-center gap-3 py-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground" aria-hidden>
                    <FileSpreadsheet className="size-4" />
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="font-medium">{d.ad}</span>
                    <span className="truncate text-xs text-muted-foreground">
                      {d.kalem_sayisi} kalem · {d.kaynak_dosya ?? (d.devir_donem_id ? "önceki dönemden devir" : "—")} · {d.olusturan}
                    </span>
                    <DonemDurumu d={d} liste={liste} />
                  </span>
                  <ReceteKaynagiSecici d={d} />
                  <Link
                    to={`/smm/stok?donem=${d.id}`}
                    className="rounded-full border px-3 py-1 text-sm font-medium hover:bg-accent"
                    aria-label={`Stok ve envanter — ${d.ad}`}
                  >
                    Stok ve envanter
                  </Link>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`Sil — ${d.ad}`}
                    disabled={kilitli}
                    title={neden}
                    onClick={() => {
                      sil.reset();
                      setSilinecek(d);
                    }}
                  >
                    Sil
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {liste.length > 0 && <MusavirSablonKarti liste={liste} />}

      {ustuneYazOnayi && dosya && !kilitli && (
        <OnayDiyalogu
          baslik="Dönem zaten yüklü"
          onayMetni="Üzerine yaz"
          bekliyor={yukle.isPending}
          onOnayla={() => gonder(true)}
          onVazgec={() => {
            setUstuneYazOnayi(false);
            yukle.reset();
          }}
        >
          <p>
            {AYLAR[ay - 1]} {yil} dönemi daha önce yüklenmiş. Üzerine yazarsanız bu dönemin verileri yeni dosyadakilerle değiştirilir.
            Yanlış olursa "Son yükleme — Geri al" ile önceki hâline dönebilirsiniz.
          </p>
        </OnayDiyalogu>
      )}
      {kayip.diyalog}
      {silinecek && !kilitli && (
        <OnayDiyalogu
          baslik="Dönem silinsin mi?"
          onayMetni="Sil"
          bekliyor={sil.isPending}
          hata={hataMetniVarsa(sil.error)}
          onOnayla={() => sil.mutate(silinecek.id, { onSuccess: () => setSilinecek(null) })}
          onVazgec={() => setSilinecek(null)}
        >
          <p>{silinecek.ad} dönemi ve yüklenen tüm verileri silinecek. Excel dosyanız etkilenmez; yeniden yükleyebilirsiniz.</p>
        </OnayDiyalogu>
      )}
    </section>
  );
}
