import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { hataMetniVarsa } from "@/api/istemci";
import { useSmmSureDuzenle, useSmmSureler, type SureGirdisi } from "@/api/sorgular/smm";
import type { SmmSure } from "@/api/tipler";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { D } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { DonemSecici, DonemYok, useGecikmeli, useSmmDonemSecimi } from "./ortak";
import { SmmDuzenlemeKilidi, useSmmYazmaKilidi, type SmmYazmaKilidi } from "./SmmDuzenlemeKilidi";

const SAYI_ALANLARI = [
  ["vardiya_uretim", "Vardiya üretim"],
  ["dolum_isci", "Dolum işçi"],
  ["etiket_isci", "Etiket işçi"],
  ["dolum_sn", "Dolum sn"],
  ["dolum_adam_sn", "Dolum adam-sn"],
  ["etiket_sn", "Etiket sn"],
  ["etiket_adam_sn", "Etiket adam-sn"],
] as const;
type SayiAlani = (typeof SAYI_ALANLARI)[number][0];
const METIN_ALANLARI = [
  ["mamul_kod", "Mamul kodu (50)"],
  ["yari_mamul_kod", "Yarı mamul kodu (40)"],
  ["ad", "Ad"],
] as const;

const kutu = (x: string | null | undefined) => (x === null || x === undefined ? "" : D(x).toFixed().replace(".", ","));
const goster = (x: string) => (D(x).isZero() ? "—" : new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 4 }).format(D(x).toNumber()));

type Taslak = Record<string, string>;

function taslakOlustur(s?: SmmSure): Taslak {
  const t: Taslak = {};
  for (const [a] of METIN_ALANLARI) t[a] = (s?.[a] as string | null) ?? "";
  for (const [a] of SAYI_ALANLARI) t[a] = s ? kutu(s[a]) : "";
  return t;
}

/** Taslak -> API gövdesi; sayı geçersizse null döner. */
function govde(t: Taslak): SureGirdisi | null {
  const g: SureGirdisi = {};
  for (const [a] of METIN_ALANLARI) g[a] = t[a].trim() || null;
  for (const [a] of SAYI_ALANLARI) {
    if (t[a].trim() === "") continue;
    const v = sayiApi(t[a]);
    if (v === null) return null;
    g[a as SayiAlani] = v;
  }
  return g;
}

function Alanlar({ t, set, onek }: { t: Taslak; set: (t: Taslak) => void; onek: string }) {
  return (
    <>
      {METIN_ALANLARI.map(([a, ad]) => (
        <td key={a} className="px-1 py-1">
          <Input
            aria-label={`${ad}${onek}`}
            className={a === "ad" ? "h-7 min-w-48" : "h-7 w-40"}
            value={t[a]}
            onChange={(e) => set({ ...t, [a]: e.target.value })}
          />
        </td>
      ))}
      {SAYI_ALANLARI.map(([a, ad]) => (
        <td key={a} className="px-1 py-1">
          <Input
            aria-label={`${ad}${onek}`}
            inputMode="decimal"
            className="h-7 w-24 text-right"
            value={t[a]}
            onChange={(e) => set({ ...t, [a]: e.target.value })}
          />
        </td>
      ))}
    </>
  );
}

function Satir({ s, donemId, yazma }: { s: SmmSure; donemId: number; yazma: SmmYazmaKilidi }) {
  const { guncelle, sil } = useSmmSureDuzenle(donemId);
  const [duzenle, setDuzenle] = useState(false);
  const [t, setT] = useState<Taslak>(() => taslakOlustur(s));
  const g = govde(t);
  const hata = hataMetniVarsa(guncelle.error) ?? hataMetniVarsa(sil.error);
  return (
    <tr className="border-b align-middle">
      {duzenle ? (
        <Alanlar t={t} set={setT} onek={` — ${s.kod}`} />
      ) : (
        <>
          <td className="px-2 py-1.5 tabular-nums">{s.mamul_kod ?? "—"}</td>
          <td className="px-2 py-1.5 tabular-nums">{s.yari_mamul_kod ?? "—"}</td>
          <td className="max-w-80 px-2 py-1.5">{s.ad}</td>
          {SAYI_ALANLARI.map(([a]) => (
            <td key={a} className="px-2 py-1.5 text-right tabular-nums">
              {goster(s[a])}
            </td>
          ))}
        </>
      )}
      <td className="px-2 py-1">
        <span className="flex justify-end gap-1">
          {duzenle ? (
            <>
              <Button
                type="button"
                size="sm"
                disabled={yazma.kilitli || g === null || guncelle.isPending}
                title={yazma.neden}
                onClick={() => g && guncelle.mutate({ id: s.id, g }, { onSuccess: () => setDuzenle(false) })}
              >
                Kaydet
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => (setT(taslakOlustur(s)), setDuzenle(false))}>
                Vazgeç
              </Button>
            </>
          ) : (
            <>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={`Düzenle — ${s.kod}`}
                disabled={yazma.kilitli}
                title={yazma.neden}
                onClick={() => setDuzenle(true)}
              >
                <Pencil className="size-3.5" />
              </Button>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label={`Sil — ${s.kod}`}
                disabled={yazma.kilitli || sil.isPending}
                title={yazma.neden}
                onClick={() => sil.mutate(s.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </>
          )}
        </span>
        {hata && (
          <span role="alert" className="block text-xs text-destructive">
            {hata}
          </span>
        )}
      </td>
    </tr>
  );
}

/**
 * Üretim süreleri (Excel '51' sayfası): dönem başına; işçilik ve genel gider dağıtımında kullanılır. Yeni dönem önceki dönemden kopyalar.
 */
export default function SmmSureler() {
  const secim = useSmmDonemSecimi();
  const [arama, setArama] = useState("");
  const gecikmeli = useGecikmeli(arama);
  const q = useSmmSureler(secim.donemId, gecikmeli);
  const { ekle } = useSmmSureDuzenle(secim.donemId);
  const [yeni, setYeni] = useState<Taslak | null>(null);
  const donemKilitli = Boolean(secim.secili?.kilitli);
  const yazma = useSmmYazmaKilidi(donemKilitli);
  const yg = yeni ? govde(yeni) : null;
  if (secim.bos) {
    return (
      <section className="flex flex-col gap-5">
        <SayfaBasligi baslik="Üretim Süreleri" />
        <DonemYok />
      </section>
    );
  }
  const kayitlar = q.data?.kayitlar ?? [];
  return (
    <section className="flex flex-col gap-5">
      <SayfaBasligi
        baslik="Üretim Süreleri"
        altBaslik="Ürün başına dolum ve etiket süreleri (Excel '51' sayfası). İşçilik ve genel gider, süre × üretim miktarı oranında dağıtılır."
        eylemler={<DonemSecici secim={secim} />}
      />
      <SmmDuzenlemeKilidi donemKilitli={donemKilitli} />
      <div className="flex flex-wrap items-center gap-3">
        <Input
          aria-label="Süre ara"
          placeholder="Kod ya da ad ara"
          className="max-w-xs"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
        />
        <span className="text-sm text-muted-foreground">{q.data ? `${kayitlar.length} satır` : ""}</span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="ml-auto"
          onClick={() => setYeni(taslakOlustur())}
          disabled={yazma.kilitli || yeni !== null}
          title={yazma.neden}
        >
          <Plus className="size-3.5" /> Satır ekle
        </Button>
      </div>
      <div className="overflow-x-auto rounded-2xl border bg-card shadow-xs">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground uppercase">
              {METIN_ALANLARI.map(([a, ad]) => (
                <th key={a} className="px-2 py-2 font-medium">
                  {ad}
                </th>
              ))}
              {SAYI_ALANLARI.map(([a, ad]) => (
                <th key={a} className="px-2 py-2 text-right font-medium whitespace-nowrap">
                  {ad}
                </th>
              ))}
              <th className="px-2 py-2">
                <span className="sr-only">İşlem</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {yeni && (
              <tr className="border-b bg-kart-yesil/40">
                <Alanlar t={yeni} set={setYeni} onek=" (yeni)" />
                <td className="px-2 py-1">
                  <span className="flex justify-end gap-1">
                    <Button
                      type="button"
                      size="sm"
                      disabled={yazma.kilitli || yg === null || !(yeni.mamul_kod.trim() || yeni.yari_mamul_kod.trim()) || ekle.isPending}
                      title={yazma.neden}
                      onClick={() => yg && ekle.mutate(yg, { onSuccess: () => setYeni(null) })}
                    >
                      Ekle
                    </Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setYeni(null)}>
                      Vazgeç
                    </Button>
                  </span>
                  {hataMetniVarsa(ekle.error) && (
                    <span role="alert" className="block text-xs text-destructive">
                      {hataMetniVarsa(ekle.error)}
                    </span>
                  )}
                </td>
              </tr>
            )}
            {q.isPending && (
              <tr>
                <td colSpan={11} className="px-2 py-6 text-center text-muted-foreground">
                  Yükleniyor…
                </td>
              </tr>
            )}
            {!q.isPending && kayitlar.length === 0 && !yeni && (
              <tr>
                <td colSpan={11} className="px-2 py-6 text-center text-muted-foreground">
                  Süre yok
                </td>
              </tr>
            )}
            {secim.donemId !== null &&
              kayitlar.map((s) => (
                <Satir key={`${s.id}-${s.dolum_sn}-${s.etiket_adam_sn}-${s.ad}`} s={s} donemId={secim.donemId as number} yazma={yazma} />
              ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
