import { useState, type FormEvent } from "react";
import { Copy, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { hataMetniVarsa } from "@/api/istemci";
import { useSmmMalzemeAra, useSmmRecete, useSmmReceteDuzenle, useSmmAlternatif } from "@/api/sorgular/smm";
import type { SmmReceteDetayi } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/bilesenler/ui/sheet";
import { cn } from "@/lib/utils";
import { D } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { useGecikmeli } from "./ortak";

export const ASAMA_ADI: Record<string, string> = { "20": "20 · Sebze kabul", "40": "40 · Üretim hattı", "50": "50 · Etiketleme" };
type Satir = SmmReceteDetayi["alternatifler"][number]["satirlar"][number];

/** API sayısı -> kutu metni ("0.05" -> "0,05"). */
const kutu = (x: string) => D(x).toFixed().replace(".", ",");
/** Fire oranı -> yüzde kutusu ("0.3333" -> "33,33"). */
const yuzdeKutu = (x: string) => D(x).times(100).toDecimalPlaces(4).toFixed().replace(".", ",");
const yuzde = (x: string) => (D(x).isZero() ? "—" : `%${yuzdeKutu(x)}`);
/** Yüzde kutusu -> oran ("5" -> "0.05"); geçersizse null. */
const orana = (x: string) => {
  const a = sayiApi(x.trim() === "" ? "0" : x);
  return a === null ? null : D(a).dividedBy(100).toFixed();
};

/** Kod ya da adla malzeme arayıp seçme (reçetelerde geçenler ve son dönemin stok kartları). */
function MalzemeSecici({ onSec }: { onSec: (m: { kod: string; ad: string | null; birim: string | null }) => void }) {
  const [metin, setMetin] = useState("");
  const q = useGecikmeli(metin, 250);
  const ara = useSmmMalzemeAra(q);
  const guncel = q === metin.trim() && !ara.isPlaceholderData;
  return (
    <div className="flex min-w-0 flex-1 flex-col gap-1">
      <Input aria-label="Malzeme ara" placeholder="Malzeme kodu ya da adı" value={metin} onChange={(e) => setMetin(e.target.value)} />
      {metin.trim().length >= 2 && (
        <ul aria-label="Malzeme seçenekleri" className="flex max-h-48 flex-col overflow-y-auto rounded-lg border text-sm">
          {!guncel || ara.isPending ? (
            <li className="px-3 py-1.5 text-muted-foreground">Aranıyor…</li>
          ) : (ara.data ?? []).length === 0 ? (
            <li className="px-3 py-1.5 text-muted-foreground">Eşleşen yok; kodu tam yazıp "Bu kodu kullan" deyin.</li>
          ) : (
            (ara.data ?? []).map((m) => (
              <li key={m.kod}>
                <button
                  type="button"
                  className="flex w-full items-baseline justify-between gap-3 px-3 py-1.5 text-left hover:bg-accent/60"
                  onClick={() => {
                    onSec(m);
                    setMetin("");
                  }}
                >
                  <span className="min-w-0 truncate">{m.ad ?? m.kod}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {m.kod}
                    {m.birim ? ` · ${m.birim}` : ""}
                  </span>
                </button>
              </li>
            ))
          )}
          {guncel && metin.trim().length >= 3 && !(ara.data ?? []).some((m) => m.kod === metin.trim()) && (
            <li>
              <button
                type="button"
                className="w-full px-3 py-1.5 text-left text-primary hover:bg-accent/60"
                onClick={() => {
                  onSec({ kod: metin.trim(), ad: null, birim: null });
                  setMetin("");
                }}
              >
                Bu kodu kullan: {metin.trim()}
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/** Reçeteye satır ekleme formu. */
function SatirEkle({ kod, alternatif, onBitti }: { kod: string; alternatif: string; onBitti: () => void }) {
  const { ekle } = useSmmReceteDuzenle();
  const [mal, setMal] = useState<{ kod: string; ad: string | null } | null>(null);
  const [miktar, setMiktar] = useState("");
  const [birim, setBirim] = useState("");
  const [fire, setFire] = useState("");
  const miktarApi = sayiApi(miktar);
  const fireOran = orana(fire);
  const gecerli = mal !== null && miktarApi !== null && D(miktarApi).gt(0) && birim.trim() !== "" && fireOran !== null;
  function gonder(e: FormEvent) {
    e.preventDefault();
    if (!gecerli || !mal) return;
    ekle.mutate(
      {
        kod,
        satir: {
          alternatif,
          malzeme_kod: mal.kod,
          malzeme_ad: mal.ad,
          miktar: miktarApi as string,
          birim: birim.trim(),
          fire_orani: fireOran as string,
        },
      },
      { onSuccess: onBitti },
    );
  }
  return (
    <form
      onSubmit={gonder}
      aria-label={`Satır ekle — alternatif ${alternatif}`}
      className="flex flex-col gap-2 border-t bg-muted/40 px-4 py-3"
    >
      {mal ? (
        <p className="text-sm">
          Malzeme: <b>{mal.ad ?? mal.kod}</b> <span className="text-muted-foreground">({mal.kod})</span>{" "}
          <button type="button" className="text-primary hover:underline" onClick={() => setMal(null)}>
            değiştir
          </button>
        </p>
      ) : (
        <MalzemeSecici
          onSec={(m) => {
            setMal({ kod: m.kod, ad: m.ad });
            if (m.birim && !birim) setBirim(m.birim);
          }}
        />
      )}
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Miktar (1 birim ürün için)
          <Input
            aria-label="Yeni satır miktarı"
            inputMode="decimal"
            className="w-32"
            value={miktar}
            onChange={(e) => setMiktar(e.target.value)}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Birim
          <Input aria-label="Yeni satır birimi" className="w-20" value={birim} onChange={(e) => setBirim(e.target.value.toUpperCase())} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Fire %
          <Input
            aria-label="Yeni satır fire yüzdesi"
            inputMode="decimal"
            className="w-20"
            value={fire}
            onChange={(e) => setFire(e.target.value)}
          />
        </label>
        <Button type="submit" size="sm" disabled={!gecerli || ekle.isPending}>
          {ekle.isPending ? "Ekleniyor…" : "Satırı ekle"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onBitti}>
          Vazgeç
        </Button>
      </div>
      {hataMetniVarsa(ekle.error) && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetniVarsa(ekle.error)}
        </p>
      )}
    </form>
  );
}

/** Tek reçete satırı: miktar, birim ve fire düzenlenir; değişince Kaydet görünür. */
function SatirDuzenle({ s }: { s: Satir }) {
  const { guncelle, sil } = useSmmReceteDuzenle();
  const [duzenle, setDuzenle] = useState(false);
  const [miktar, setMiktar] = useState(kutu(s.miktar));
  const [birim, setBirim] = useState(s.birim ?? "");
  const [fire, setFire] = useState(yuzdeKutu(s.fire_orani));
  const miktarApi = sayiApi(miktar);
  const fireOran = orana(fire);
  const gecerli = miktarApi !== null && D(miktarApi).gt(0) && birim.trim() !== "" && fireOran !== null;
  const hata = hataMetniVarsa(guncelle.error) ?? hataMetniVarsa(sil.error);
  return (
    <tr className="align-top">
      <td className="px-4 py-1.5">
        <span className="block">{s.malzeme_ad ?? s.malzeme_kod}</span>
        <span className="block text-xs text-muted-foreground">
          {s.malzeme_kod}
          {s.kalem_tipi !== null && ` · kalem tipi ${s.kalem_tipi}`}
        </span>
        {hata && (
          <span role="alert" className="block text-xs text-destructive">
            {hata}
          </span>
        )}
      </td>
      {duzenle ? (
        <>
          <td className="py-1.5">
            <span className="flex justify-end gap-1">
              <Input
                aria-label={`Miktar — ${s.malzeme_kod}`}
                inputMode="decimal"
                className="h-7 w-24 text-right"
                value={miktar}
                onChange={(e) => setMiktar(e.target.value)}
              />
              <Input
                aria-label={`Birim — ${s.malzeme_kod}`}
                className="h-7 w-14"
                value={birim}
                onChange={(e) => setBirim(e.target.value.toUpperCase())}
              />
            </span>
          </td>
          <td className="py-1.5">
            <Input
              aria-label={`Fire % — ${s.malzeme_kod}`}
              inputMode="decimal"
              className="ml-auto h-7 w-16 text-right"
              value={fire}
              onChange={(e) => setFire(e.target.value)}
            />
          </td>
          <td className="py-1.5 pr-3">
            <span className="flex justify-end gap-1">
              <Button
                type="button"
                size="sm"
                disabled={!gecerli || guncelle.isPending}
                onClick={() =>
                  guncelle.mutate(
                    { id: s.id, alanlar: { miktar: miktarApi as string, birim: birim.trim(), fire_orani: fireOran as string } },
                    { onSuccess: () => setDuzenle(false) },
                  )
                }
              >
                Kaydet
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setDuzenle(false)}>
                Vazgeç
              </Button>
            </span>
          </td>
        </>
      ) : (
        <>
          <td className="py-1.5 text-right tabular-nums">
            {kutu(s.miktar)} <span className="text-xs text-muted-foreground">{s.birim}</span>
          </td>
          <td className="py-1.5 text-right tabular-nums">{yuzde(s.fire_orani)}</td>
          <td className="py-1.5 pr-3">
            <span className="flex justify-end gap-0.5">
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={`Düzenle — ${s.malzeme_kod}`}
                onClick={() => setDuzenle(true)}
              >
                <Pencil className="size-3.5" />
              </Button>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={`Sil — ${s.malzeme_kod}`}
                disabled={sil.isPending}
                onClick={() => sil.mutate(s.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </span>
          </td>
        </>
      )}
    </tr>
  );
}

/** Ürünün reçetesi: alternatifler, hesapta kullanılacak alternatif, elle düzenleme. */
export function ReceteCekmecesi({ kod, onKapat }: { kod: string | null; onKapat: () => void }) {
  const q = useSmmRecete(kod);
  const sec = useSmmAlternatif();
  const { kopyala, caniasaDon, asama: asamaDegistir } = useSmmReceteDuzenle();
  const [ekleAlt, setEkleAlt] = useState<string | null>(null);
  const [donOnayi, setDonOnayi] = useState(false);
  const r = q.data;
  const yeniAlt = r ? String(Math.max(...r.alternatifler.map((a) => Number(a.alternatif) || 0)) + 1).padStart(2, "0") : "01";
  const hata = hataMetniVarsa(sec.error) ?? hataMetniVarsa(kopyala.error);
  return (
    <Sheet
      open={kod !== null}
      onOpenChange={(a) => {
        if (!a) {
          setEkleAlt(null);
          onKapat();
        }
      }}
    >
      <SheetContent side="right" className="data-[side=right]:sm:max-w-3xl">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {r?.ana_ad ?? kod}
            {r?.elle && <span className="rounded-full bg-kart-sari px-2 py-0.5 text-xs font-medium">Elle değiştirildi</span>}
          </SheetTitle>
          <SheetDescription>
            {kod} {r && `· ${ASAMA_ADI[String(r.asama)] ?? r.asama}`}
            {r?.elle && r.elle_degistiren && ` · son değiştiren ${r.elle_degistiren}`}
          </SheetDescription>
        </SheetHeader>
        <div className="flex flex-col gap-4 overflow-y-auto px-4 pb-4">
          {q.isPending && <p className="text-sm text-muted-foreground">Yükleniyor…</p>}
          {r && (
            <label className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted-foreground">Aşama</span>
              <select
                aria-label="Ürünün aşaması"
                className="h-8 rounded-lg border border-input bg-background px-2 text-sm"
                value={r.asama}
                disabled={asamaDegistir.isPending}
                onChange={(e) => asamaDegistir.mutate({ kod: r.ana_kod, asama: Number(e.target.value) })}
              >
                {Object.entries(ASAMA_ADI).map(([a, ad]) => (
                  <option key={a} value={a}>
                    {ad}
                  </option>
                ))}
              </select>
              {r.asama !== r.kod_asamasi && (
                <span className="text-xs text-amber-700 dark:text-amber-400">Koda göre {ASAMA_ADI[String(r.kod_asamasi)]} olurdu</span>
              )}
              {hataMetniVarsa(asamaDegistir.error) && (
                <span className="text-xs text-destructive">{hataMetniVarsa(asamaDegistir.error)}</span>
              )}
            </label>
          )}
          {r?.elle && (
            <p className="flex flex-wrap items-center gap-2 rounded-lg bg-kart-sari px-3 py-2 text-sm">
              Bu reçete elle değiştirildi; Canias dökümü yeniden yüklenince korunur.
              {r.canias_var && (
                <Button type="button" size="sm" variant="outline" className="ml-auto" onClick={() => setDonOnayi(true)}>
                  <RotateCcw className="size-3.5" /> Canias'a döndür
                </Button>
              )}
            </p>
          )}
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
          {r?.alternatifler.map((a) => (
            <section key={a.alternatif} aria-label={`Alternatif ${a.alternatif}`} className="overflow-hidden rounded-xl border">
              <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2">
                <span className="font-medium">Alternatif {a.alternatif}</span>
                {r.secili_alternatif === a.alternatif ? (
                  <span className="rounded-full bg-kart-yesil px-2 py-0.5 text-xs font-medium">Hesapta kullanılıyor</span>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={sec.isPending}
                    onClick={() => sec.mutate({ kod: r.ana_kod, alternatif: a.alternatif })}
                  >
                    Bunu kullan
                  </Button>
                )}
                <span className="ml-auto flex gap-1">
                  <Button type="button" size="sm" variant="ghost" onClick={() => setEkleAlt(a.alternatif)}>
                    <Plus className="size-3.5" /> Satır ekle
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={kopyala.isPending}
                    onClick={() => kopyala.mutate({ kod: r.ana_kod, kaynak: a.alternatif, yeni: yeniAlt })}
                  >
                    <Copy className="size-3.5" /> {yeniAlt} olarak kopyala
                  </Button>
                </span>
              </div>
              <table className="w-full text-sm">
                <caption className="sr-only">Alternatif {a.alternatif} satırları</caption>
                <thead>
                  <tr className="text-left text-xs text-muted-foreground uppercase">
                    <th className="px-4 py-1.5 font-medium">Malzeme</th>
                    <th className="py-1.5 text-right font-medium">Miktar</th>
                    <th className="py-1.5 text-right font-medium">Fire</th>
                    <th className="w-24 py-1.5 pr-3">
                      <span className="sr-only">İşlem</span>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {a.satirlar.map((s) => (
                    <SatirDuzenle key={`${s.id}-${s.miktar}-${s.birim}-${s.fire_orani}`} s={s} />
                  ))}
                </tbody>
              </table>
              {ekleAlt === a.alternatif && <SatirEkle kod={r.ana_kod} alternatif={a.alternatif} onBitti={() => setEkleAlt(null)} />}
            </section>
          ))}
        </div>
        {donOnayi && r && (
          <OnayDiyalogu
            baslik="Canias reçetesine dönülsün mü?"
            onayMetni="Canias'a döndür"
            bekliyor={caniasaDon.isPending}
            hata={hataMetniVarsa(caniasaDon.error)}
            onOnayla={() => caniasaDon.mutate(r.ana_kod, { onSuccess: () => setDonOnayi(false) })}
            onVazgec={() => setDonOnayi(false)}
          >
            <p>{r.ana_ad ?? r.ana_kod} reçetesindeki elle değişiklikler silinir; son yüklenen Canias dökümündeki hâline döner.</p>
          </OnayDiyalogu>
        )}
      </SheetContent>
    </Sheet>
  );
}

/** Canias'ta henüz olmayan ürün için elle reçete (ilk satırıyla). */
export function YeniReceteDiyalogu({ acik, onKapat, onAcildi }: { acik: boolean; onKapat: () => void; onAcildi: (kod: string) => void }) {
  const { yeniUrun } = useSmmReceteDuzenle();
  const [kod, setKod] = useState("");
  const [ad, setAd] = useState("");
  const [mal, setMal] = useState<{ kod: string; ad: string | null } | null>(null);
  const [miktar, setMiktar] = useState("");
  const [birim, setBirim] = useState("");
  const [fire, setFire] = useState("");
  const miktarApi = sayiApi(miktar);
  const fireOran = orana(fire);
  const gecerli = kod.trim() !== "" && mal !== null && miktarApi !== null && D(miktarApi).gt(0) && birim.trim() !== "" && fireOran !== null;
  return (
    <Dialog open={acik} onOpenChange={(a) => !a && onKapat()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Yeni reçete</DialogTitle>
          <DialogDescription>
            Canias'ta henüz olmayan bir ürün için. Aşama koddan anlaşılır (02 → 40, 03 → 50, diğerleri → 20). Diğer satırları sonra
            eklersiniz.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!gecerli || !mal) return;
            yeniUrun.mutate(
              {
                ana_kod: kod.trim(),
                ana_ad: ad.trim() || null,
                alternatif: "00",
                malzeme_kod: mal.kod,
                malzeme_ad: mal.ad,
                miktar: miktarApi as string,
                birim: birim.trim(),
                fire_orani: fireOran as string,
              },
              {
                onSuccess: (d) => {
                  onAcildi(d.ana_kod);
                  onKapat();
                },
              },
            );
          }}
        >
          <div className="grid grid-cols-[10rem_1fr] gap-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Ürün kodu</span>
              <Input aria-label="Ürün kodu" value={kod} onChange={(e) => setKod(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Ürün adı</span>
              <Input aria-label="Ürün adı" value={ad} onChange={(e) => setAd(e.target.value)} />
            </label>
          </div>
          <div className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">İlk satır</span>
            {mal ? (
              <p>
                <b>{mal.ad ?? mal.kod}</b> <span className="text-muted-foreground">({mal.kod})</span>{" "}
                <button type="button" className="text-primary hover:underline" onClick={() => setMal(null)}>
                  değiştir
                </button>
              </p>
            ) : (
              <MalzemeSecici
                onSec={(m) => {
                  setMal({ kod: m.kod, ad: m.ad });
                  if (m.birim && !birim) setBirim(m.birim);
                }}
              />
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Input
              aria-label="İlk satır miktarı"
              placeholder="Miktar"
              inputMode="decimal"
              className="w-32"
              value={miktar}
              onChange={(e) => setMiktar(e.target.value)}
            />
            <Input
              aria-label="İlk satır birimi"
              placeholder="Birim"
              className="w-20"
              value={birim}
              onChange={(e) => setBirim(e.target.value.toUpperCase())}
            />
            <Input
              aria-label="İlk satır fire yüzdesi"
              placeholder="Fire %"
              inputMode="decimal"
              className="w-20"
              value={fire}
              onChange={(e) => setFire(e.target.value)}
            />
          </div>
          {hataMetniVarsa(yeniUrun.error) && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetniVarsa(yeniUrun.error)}
            </p>
          )}
          <div className={cn("flex justify-end gap-2")}>
            <Button type="button" variant="outline" onClick={onKapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={!gecerli || yeniUrun.isPending}>
              {yeniUrun.isPending ? "Oluşturuluyor…" : "Reçeteyi oluştur"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
