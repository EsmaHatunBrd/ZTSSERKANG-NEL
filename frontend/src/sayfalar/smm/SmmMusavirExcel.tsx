import { useRef, useState } from "react";
import { CircleCheck, FileSpreadsheet, Info } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { smmMusavirExcelAdresi, useSmmMusavirDurum, useSmmMusavirSablonOnizle, useSmmMusavirSablonSakla } from "@/api/sorgular/smm";
import type { SmmDonem, SmmMusavirExcelDurumu } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { goster } from "@/yardimcilar/tarih";
import { useSmmYazmaKilidi } from "./SmmDuzenlemeKilidi";

export const SABLON_YOK_NEDENI = "Şablon yok: Dönemler › SMM Excel'inden yükle ile bir ayın Excel'ini yükleyin";

/** "Şablon: <dosya>, <tarih>" (+ önceki ayın dosyasıysa hangi ay). */
export function sablonMetni(d: SmmMusavirExcelDurumu): string | null {
  if (!d.sablon) return null;
  const tarih = d.sablon.zaman ? `, ${goster(d.sablon.zaman)}` : "";
  const onceki = !d.kendi && d.kaynak_donem ? ` (${d.kaynak_donem} dosyası; bu ayın Excel'i yüklenmedi)` : "";
  return `Şablon: ${d.sablon.dosya_adi}${tarih}${onceki}`;
}

/**
 * SMM Özeti başlığında "Müşavir Excel'i": müşavire giden SMM Excel'inin aynısı (kendi Excel'iniz şablon), rakamlar uygulamadan.
 * Şablon yoksa pasif düğme; nedeni başlık ipucunda ve sayfadaki bilgi satırında.
 */
export function MusavirExcelDugmesi({ donemId }: { donemId: number }) {
  const q = useSmmMusavirDurum(donemId);
  const d = q.data;
  const sinif = "inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm font-medium";
  if (!d?.sablon) {
    return (
      <button
        type="button"
        disabled
        className={`${sinif} cursor-not-allowed opacity-50`}
        title={q.isPending ? "Şablon denetleniyor…" : q.error ? hataMetni(q.error) : SABLON_YOK_NEDENI}
      >
        <FileSpreadsheet className="size-3.5" /> Müşavir Excel'i
      </button>
    );
  }
  return (
    <a
      href={smmMusavirExcelAdresi(donemId)}
      download
      className={`${sinif} hover:bg-accent`}
      title={`${sablonMetni(d)}. Excel açıldığında toplamlar yeniden hesaplanır.`}
    >
      <FileSpreadsheet className="size-3.5" /> Müşavir Excel'i
    </a>
  );
}

/** SMM Özeti'nde düğmenin açıklaması: hangi şablon, taslak mı, şablon yoksa ne yapılmalı. */
export function MusavirExcelBilgisi({ donemId }: { donemId: number }) {
  const q = useSmmMusavirDurum(donemId);
  const d = q.data;
  if (!d) return null;
  return (
    <p role="note" aria-label="Müşavir Excel'i" className="flex items-start gap-2 text-xs text-muted-foreground">
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      {d.sablon ? (
        <span>
          Müşavir Excel'i: {sablonMetni(d)}. Formüller ve biçim sizin dosyanızdaki gibi kalır, rakamlar uygulamadan; Excel açıldığında
          toplamlar yeniden hesaplanır.
          {d.taslak && <b className="text-foreground"> TASLAK — dönem kapatılmadı.</b>}
        </span>
      ) : (
        <span>Müşavir Excel'i indirilemez. {SABLON_YOK_NEDENI} (ya da Dönemler'de "Müşavir şablonu olarak yalnız sakla").</span>
      )}
    </p>
  );
}

/**
 * Dönemler: SMM Excel'ini dönem verisine dokunmadan yalnız müşavir şablonu olarak saklama (Excel'i zaten yüklemiş, ya da dönemi
 * aylık kaynaklardan kurmuş kullanıcı için). Önce önizleme (sayfa adları); SMM Excel'i değilse sunucu reddeder.
 */
export function MusavirSablonKarti({ liste }: { liste: SmmDonem[] }) {
  const [secili, setSecili] = useState<number | null>(null);
  const donemId = secili ?? liste[0]?.id ?? null;
  const durum = useSmmMusavirDurum(donemId);
  const onizle = useSmmMusavirSablonOnizle();
  const sakla = useSmmMusavirSablonSakla();
  const { kilitli, neden } = useSmmYazmaKilidi();
  const dosyaRef = useRef<HTMLInputElement>(null);
  const [dosya, setDosya] = useState<File | null>(null);
  const on = onizle.data;
  if (donemId === null) return null;
  const d = durum.data;
  return (
    <section aria-label="Müşavir Excel'i şablonu" className="flex flex-col gap-3 rounded-2xl border bg-card p-5 shadow-xs">
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-kart-yesil text-primary" aria-hidden>
          <FileSpreadsheet className="size-5" />
        </span>
        <div>
          <h2 className="text-base font-semibold">Müşavir Excel'i şablonu</h2>
          <p className="text-sm text-muted-foreground">
            Müşavire giden SMM Excel'i sizin dosyanızın düzeninde üretilir: SMM Excel'inden yüklediğiniz dosya şablon olarak saklanır,
            rakamlar uygulamadan yazılır. Excel'i zaten yüklediyseniz ya da dönemi aylık kaynaklardan kurduysanız, dosyayı burada dönem
            verisine dokunmadan yalnız şablon olarak saklayabilirsiniz. Şablonu olmayan ay, en yakın önceki ayın şablonunu kullanır.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Dönem</span>
          <select
            aria-label="Şablon dönemi"
            className="h-8 rounded-lg border border-input bg-background px-2 text-sm"
            value={donemId}
            onChange={(e) => {
              setSecili(Number(e.target.value));
              onizle.reset();
              sakla.reset();
            }}
          >
            {liste.map((x) => (
              <option key={x.id} value={x.id}>
                {x.ad}
              </option>
            ))}
          </select>
        </label>
        <label className="flex min-w-56 flex-1 flex-col gap-1 text-sm">
          <span className="text-muted-foreground">SMM Excel'i (.xlsx)</span>
          <Input
            ref={dosyaRef}
            type="file"
            accept=".xlsx"
            aria-label="Müşavir şablonu dosyası"
            onChange={(e) => {
              setDosya(e.target.files?.[0] ?? null);
              onizle.reset();
              sakla.reset();
            }}
          />
        </label>
        <Button
          type="button"
          variant="outline"
          disabled={!dosya || onizle.isPending}
          onClick={() => dosya && onizle.mutate({ donemId, dosya })}
        >
          {onizle.isPending ? "Okunuyor…" : "Şablonu önizle"}
        </Button>
      </div>
      {d && (
        <p className="text-sm text-muted-foreground">
          {d.sablon ? sablonMetni(d) : "Bu dönem için şablon yok; Müşavir Excel'i indirilemez."}
        </p>
      )}
      {(onizle.error || sakla.error) && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(onizle.error ?? sakla.error)}
        </p>
      )}
      {on && dosya && !sakla.data && (
        <div role="region" aria-label="Şablon önizlemesi" className="flex flex-col gap-2 rounded-xl border bg-muted/40 px-4 py-3 text-sm">
          <p>
            <b>{on.dosya_adi}</b> {on.donem} için müşavir şablonu olarak saklanacak; dönemin verileri değişmez.
            {on.mevcut ? ` Mevcut şablonun (${on.mevcut.dosya_adi}) yerine geçer.` : ""}
          </p>
          <p className="text-xs text-muted-foreground">Sayfalar: {on.sayfalar.join(", ")}</p>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              disabled={kilitli || sakla.isPending}
              title={neden}
              onClick={() =>
                sakla.mutate(
                  { donemId, dosya },
                  {
                    onSuccess: () => {
                      setDosya(null);
                      if (dosyaRef.current) dosyaRef.current.value = "";
                    },
                  },
                )
              }
            >
              {sakla.isPending ? "Saklanıyor…" : "Yalnız şablon olarak sakla"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => onizle.reset()}>
              Vazgeç
            </Button>
          </div>
        </div>
      )}
      {sakla.data && (
        <p role="status" className="flex items-center gap-2 rounded-xl bg-kart-yesil px-4 py-3 text-sm">
          <CircleCheck className="size-4 text-green-700 dark:text-green-400" aria-hidden />
          Şablon saklandı. {sablonMetni(sakla.data)}.
        </p>
      )}
    </section>
  );
}
