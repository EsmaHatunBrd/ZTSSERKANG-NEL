import { useId, useMemo, useState } from "react";
import { FileCheck2, Loader2 } from "lucide-react";
import type { OnayCiktisiEkleri, OnayCiktisiFiyatGiris, OnayCiktisiImzalari, OnayCiktisiSmmGiris } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Girdi } from "@/bilesenler/Girdi";
import { cn } from "@/lib/utils";
import { dosyaIndir } from "@/yardimcilar/indir";
import * as kullanici from "@/yardimcilar/kullanici";

/** Diyalogun kapsamı: Fiyat Çalışması (çalışma + ürün seçimi) ya da maliyet muhasebesi (dönem). */
export type OnayKapsami =
  | {
      modul: "fiyat";
      senaryoId: number;
      senaryoAdi: string;
      kilitli: boolean;
      /** Çalışmanın ürünleri (çoklu seçim için); yüklenirken boş dizi. */
      urunler: { kod: string; ad: string }[];
      urunlerYukleniyor?: boolean;
    }
  | { modul: "smm"; donemler: { id: number; ad: string; kilitli: boolean }[]; donemId: number };

export type OnayTuru = "excel" | "pdf";

const TURLER: { deger: OnayTuru | "formullu"; etiket: string; ipucu?: string }[] = [
  { deger: "excel", etiket: "Excel (rakamlar)" },
  { deger: "pdf", etiket: "PDF (yazdırmaya ve imzaya hazır)" },
  { deger: "formullu", etiket: "Excel (formüllü)", ipucu: "Yakında" },
];

const IMZALAR: { alan: keyof OnayCiktisiImzalari; etiket: string }[] = [
  { alan: "hazirlayan", etiket: "Hazırlayan" },
  { alan: "kontrol_eden", etiket: "Kontrol eden" },
  { alan: "onaylayan", etiket: "Onaylayan" },
];

type Ekler = Required<OnayCiktisiEkleri>;

/** Diyalogun gönderdiği gövde (test ve çağıranlar için dışa açık). */
export function onayGovdesi(
  kapsam: OnayKapsami,
  secim: { tur: OnayTuru; tumUrunler: boolean; secili: string[]; donemId: number; ekler: Ekler; imzalar: Record<string, string> },
): OnayCiktisiFiyatGiris | OnayCiktisiSmmGiris {
  const imzalar: OnayCiktisiImzalari = {};
  for (const { alan } of IMZALAR) {
    const v = (secim.imzalar[alan] ?? "").trim();
    if (v) imzalar[alan] = v;
  }
  if (kapsam.modul === "fiyat") {
    // mutabakat yalnız SMM'de kullanılır; Fiyat'ta sunucu yok sayar
    const govde: OnayCiktisiFiyatGiris = { senaryo_id: kapsam.senaryoId, tur: secim.tur, ekler: secim.ekler, imzalar };
    if (!secim.tumUrunler) govde.urunler = secim.secili;
    return govde;
  }
  return { donem_id: secim.donemId, tur: secim.tur, ekler: secim.ekler, imzalar };
}

const SECIM_SINIFI = "h-8 rounded-lg border bg-background px-2 text-sm";

/**
 * Yeminli mali müşavire verilecek onay çıktısı: tür (Excel rakamlar / PDF; formüllü Excel yakında), kapsam, ekler ve imza adları.
 * Çalışma ya da dönem kapatılmadıysa çıktı TASLAK damgalıdır; diyalog bunu açıkça yazar. Dosya sunucuda hazırlanırken
 * "Hazırlanıyor…" görünür; hata `role=alert` ile gösterilir. Veri yazmaz (izleyici de indirebilir).
 */
export function OnayCiktisiDiyalogu({ kapsam, onKapat }: { kapsam: OnayKapsami; onKapat: () => void }) {
  const id = useId();
  const [tur, setTur] = useState<OnayTuru>("excel");
  const [tumUrunler, setTumUrunler] = useState(true);
  const [secili, setSecili] = useState<string[]>([]);
  const [arama, setArama] = useState("");
  const [donemId, setDonemId] = useState(kapsam.modul === "smm" ? kapsam.donemId : 0);
  const [ekler, setEkler] = useState<Ekler>({ kapak: true, mutabakat: true, elle_degisiklikler: true, gunluk_ozeti: true });
  const [imzalar, setImzalar] = useState<Record<string, string>>({});
  const [hazirlaniyor, setHazirlaniyor] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  const kesin = kapsam.modul === "fiyat" ? kapsam.kilitli : (kapsam.donemler.find((d) => d.id === donemId)?.kilitli ?? false);
  const nesne = kapsam.modul === "fiyat" ? "çalışma" : "dönem";
  const gorunenUrunler = useMemo(() => {
    if (kapsam.modul !== "fiyat") return [];
    const q = arama.trim().toLocaleLowerCase("tr");
    return q ? kapsam.urunler.filter((u) => `${u.kod} ${u.ad}`.toLocaleLowerCase("tr").includes(q)) : kapsam.urunler;
  }, [kapsam, arama]);
  const secimEksik = kapsam.modul === "fiyat" && !tumUrunler && secili.length === 0;

  const ekListesi: { alan: keyof Ekler; etiket: string }[] = [
    { alan: "kapak", etiket: "Kapak sayfası" },
    ...(kapsam.modul === "smm" ? [{ alan: "mutabakat" as const, etiket: "Mutabakat" }] : []),
    { alan: "elle_degisiklikler", etiket: "Elle yapılan değişiklikler" },
    {
      alan: "gunluk_ozeti",
      etiket: kapsam.modul === "fiyat" ? "Değişiklik günlüğü özeti (son 90 gün)" : "Değişiklik günlüğü özeti (dönem içi)",
    },
  ];

  function urunDegistir(kod: string, acik: boolean) {
    setSecili((o) => (acik ? [...o, kod] : o.filter((k) => k !== kod)));
  }

  async function indir() {
    if (secimEksik) return;
    setHazirlaniyor(true);
    setHata(null);
    const govde = onayGovdesi(kapsam, { tur, tumUrunler, secili, donemId, ekler, imzalar });
    const basliklar: Record<string, string> = { "Content-Type": "application/json" };
    const ad = kullanici.al();
    if (kullanici.adGecerli(ad)) basliklar["X-Kullanici"] = encodeURIComponent(ad);
    try {
      await dosyaIndir(`/api/v1/onay-ciktisi/${kapsam.modul}`, `onay-ciktisi.${tur === "pdf" ? "pdf" : "xlsx"}`, {
        method: "POST",
        headers: basliklar,
        body: JSON.stringify(govde),
      });
    } catch (e) {
      setHata(e instanceof Error ? e.message : "Dosya hazırlanamadı");
    } finally {
      setHazirlaniyor(false);
    }
  }

  return (
    <Dialog open onOpenChange={(a) => !a && !hazirlaniyor && onKapat()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Onay çıktısı</DialogTitle>
          <DialogDescription>
            {kapsam.modul === "fiyat" ? `Fiyat Çalışması · ${kapsam.senaryoAdi}` : "Maliyet muhasebesi"} — yeminli mali müşavir için yalnız
            rakamlar (formül yok).
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 text-sm">
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 font-medium">Kapsam</legend>
            {kapsam.modul === "fiyat" ? (
              <>
                <label className="flex items-center gap-2">
                  <input type="radio" name={`${id}-kapsam`} checked={tumUrunler} onChange={() => setTumUrunler(true)} />
                  Seçili çalışmanın tüm ürünleri
                </label>
                <label className="flex items-center gap-2">
                  <input type="radio" name={`${id}-kapsam`} checked={!tumUrunler} onChange={() => setTumUrunler(false)} />
                  Yalnız seçtiğim ürünler{!tumUrunler && ` (${secili.length} seçili)`}
                </label>
                {!tumUrunler && (
                  <div className="flex flex-col gap-2 rounded-lg border p-2">
                    <Girdi aria-label="Ürün ara" placeholder="Kod ya da ad ara" value={arama} onChange={(e) => setArama(e.target.value)} />
                    {kapsam.urunlerYukleniyor ? (
                      <p className="text-muted-foreground">Ürünler yükleniyor…</p>
                    ) : (
                      <ul aria-label="Ürünler" className="max-h-48 overflow-y-auto">
                        {gorunenUrunler.map((u) => (
                          <li key={u.kod}>
                            <label className="flex items-center gap-2 py-0.5">
                              <input
                                type="checkbox"
                                checked={secili.includes(u.kod)}
                                onChange={(e) => urunDegistir(u.kod, e.target.checked)}
                              />
                              <span className="font-mono text-xs">{u.kod}</span>
                              <span className="truncate">{u.ad}</span>
                            </label>
                          </li>
                        ))}
                      </ul>
                    )}
                    {secimEksik && <p className="text-xs text-destructive">En az bir ürün seçin.</p>}
                  </div>
                )}
              </>
            ) : (
              <label className="flex items-center gap-2">
                <span className="text-muted-foreground">Dönem</span>
                <select aria-label="Dönem" className={SECIM_SINIFI} value={donemId} onChange={(e) => setDonemId(Number(e.target.value))}>
                  {kapsam.donemler.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.ad}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </fieldset>

          <p
            data-testid="onay-durumu"
            className={cn("rounded-lg px-3 py-2", kesin ? "bg-muted" : "border border-destructive/40 bg-destructive/5 text-destructive")}
          >
            {kesin ? `Bu ${nesne} kapatıldı: çıktı KESİN olarak işaretlenir.` : `Bu ${nesne} kapatılmadığı için çıktı TASLAK damgalı olur.`}
          </p>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1 font-medium">Tür</legend>
            {TURLER.map((t) => (
              <label key={t.deger} className={cn("flex items-center gap-2", t.ipucu && "text-muted-foreground")} title={t.ipucu}>
                <input
                  type="radio"
                  name={`${id}-tur`}
                  value={t.deger}
                  disabled={t.deger === "formullu"}
                  checked={tur === t.deger}
                  onChange={() => t.deger !== "formullu" && setTur(t.deger)}
                />
                {t.etiket}
                {t.ipucu && <span className="rounded bg-muted px-1.5 text-xs">{t.ipucu}</span>}
              </label>
            ))}
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1 font-medium">Ekler</legend>
            {ekListesi.map((e) => (
              <label key={e.alan} className="flex items-center gap-2">
                <input type="checkbox" checked={ekler[e.alan]} onChange={(x) => setEkler((o) => ({ ...o, [e.alan]: x.target.checked }))} />
                {e.etiket}
              </label>
            ))}
          </fieldset>

          <fieldset className="grid gap-2 sm:grid-cols-3">
            <legend className="mb-1 font-medium">
              İmza alanları <span className="font-normal text-muted-foreground">(isteğe bağlı; boşsa çizgi boş kalır)</span>
            </legend>
            {IMZALAR.map((i) => (
              <label key={i.alan} className="flex flex-col gap-1">
                <span className="text-xs text-muted-foreground">{i.etiket}</span>
                <Girdi
                  aria-label={i.etiket}
                  maxLength={120}
                  value={imzalar[i.alan] ?? ""}
                  onChange={(e) => setImzalar((o) => ({ ...o, [i.alan]: e.target.value }))}
                />
              </label>
            ))}
          </fieldset>

          {hata && (
            <p role="alert" className="text-destructive">
              {hata}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onKapat} disabled={hazirlaniyor}>
            Kapat
          </Button>
          <Button type="button" onClick={indir} disabled={hazirlaniyor || secimEksik} aria-busy={hazirlaniyor}>
            {hazirlaniyor ? <Loader2 className="animate-spin" aria-hidden /> : <FileCheck2 aria-hidden />}
            {hazirlaniyor ? "Hazırlanıyor…" : "İndir"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** "Onay çıktısı" düğmesi: tıklanınca diyalogu açar. `kapsam` diyalog açıkken hesaplanır (ürün listesi gibi yükler için). */
export function OnayCiktisiDugmesi({ kapsam, onAc }: { kapsam: OnayKapsami | null; onAc?: (acik: boolean) => void }) {
  const [acik, setAcik] = useState(false);
  function degistir(a: boolean) {
    setAcik(a);
    onAc?.(a);
  }
  return (
    <>
      <Button type="button" variant="outline" onClick={() => degistir(true)} title="Yeminli mali müşavir için Excel ya da PDF">
        <FileCheck2 aria-hidden />
        Onay çıktısı
      </Button>
      {acik && kapsam && <OnayCiktisiDiyalogu kapsam={kapsam} onKapat={() => degistir(false)} />}
    </>
  );
}
