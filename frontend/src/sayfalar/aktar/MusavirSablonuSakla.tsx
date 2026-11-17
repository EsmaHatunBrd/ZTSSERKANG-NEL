import { useState } from "react";
import { useMusavirSablonuOnizle, useMusavirSablonuSakla } from "@/api/sorgular/aktar";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { Button } from "@/bilesenler/ui/button";
import { Girdi as Input } from "@/bilesenler/Girdi";
import { useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { goster as tarihGoster } from "@/yardimcilar/tarih";
import { dosyaSemasi } from "./TamKitapFormu";

/**
 * Kitabı daha önce yüklemiş kullanıcılar için: Fiyat Çalışması kitabını aktarım yapmadan yalnız "Müşavir Excel'i" şablonu olarak saklar.
 * Önce denetlenir (sayfa adları, ürün sayfası sayısı); kitap değilse sunucunun anlaşılır reddi gösterilir. Senaryo verisi değişmez.
 */
export function MusavirSablonuSakla() {
  const { senaryoId, senaryo } = useSenaryo();
  const { duzenlemeKilitli } = useYazmaKilidi();
  const onizle = useMusavirSablonuOnizle();
  const sakla = useMusavirSablonuSakla();
  const [dosya, setDosya] = useState<File | undefined>(undefined);
  const [dosyaHata, setDosyaHata] = useState<string | undefined>(undefined);

  const hata = ((onizle.error ?? sakla.error) as ApiHatasi | null) ?? null;
  const on = onizle.data;

  function sec(f: File | undefined) {
    setDosya(f);
    onizle.reset();
    sakla.reset();
    const s = dosyaSemasi.safeParse(f);
    setDosyaHata(f && !s.success ? s.error.issues[0]?.message : undefined);
  }

  return (
    <section aria-labelledby="musavir-sablon-baslik" className="flex max-w-2xl flex-col gap-3 border-t pt-6">
      <h2 id="musavir-sablon-baslik" className="text-base font-semibold">
        Müşavir şablonu olarak yalnız sakla
      </h2>
      <p className="text-sm text-muted-foreground">
        Kitabınızı daha önce yüklediyseniz veriyi yeniden aktarmadan yalnız şablon olarak saklayın. İndir › &quot;Müşavir Excel&apos;i&quot;
        bu kitabın düzeninde, rakamları uygulamadan alarak üretilir. Çalışmanın verisi değişmez.
      </p>
      {senaryoId === null ? (
        <p className="text-sm text-muted-foreground">Önce üst çubuktan bir çalışma seçin.</p>
      ) : (
        <>
          <p className="text-sm">Çalışma: {senaryo?.ad ?? `#${senaryoId}`}</p>
          <div className="flex flex-col gap-1">
            <label htmlFor="musavir-sablon-dosya" className="text-sm font-medium">
              Fiyat Çalışması kitabı
            </label>
            <Input
              id="musavir-sablon-dosya"
              type="file"
              accept=".xlsx"
              aria-invalid={!!dosyaHata}
              aria-describedby={dosyaHata ? "musavir-sablon-dosya-hata" : undefined}
              onChange={(e) => sec(e.target.files?.[0])}
            />
            {dosyaHata && (
              <p id="musavir-sablon-dosya-hata" className="text-sm text-destructive">
                {dosyaHata}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              disabled={!dosya || !!dosyaHata || onizle.isPending}
              onClick={() => dosya && onizle.mutate({ dosya, senaryo: senaryoId })}
            >
              {onizle.isPending ? "Denetleniyor…" : "Denetle"}
            </Button>
            <Button
              type="button"
              disabled={!dosya || !on || sakla.isPending || duzenlemeKilitli}
              title={duzenlemeKilitli ? "Düzenleme kilitli" : undefined}
              onClick={() => dosya && sakla.mutate({ dosya, senaryo: senaryoId })}
            >
              {sakla.isPending ? "Saklanıyor…" : "Şablon olarak sakla"}
            </Button>
          </div>
          {on && !sakla.data && (
            <div data-testid="musavir-sablon-onizleme" className="rounded-md border p-3 text-sm">
              <p>
                {on.dosya_adi}: {on.sayfalar.length} sayfa, {on.urun_sayfasi} ürün sayfası.
              </p>
              <p className="text-xs text-muted-foreground">
                Sayfalar: {on.sayfalar.slice(0, 12).join(", ")}
                {on.sayfalar.length > 12 ? "…" : ""}
              </p>
              {on.mevcut && (
                <p className="mt-1 text-xs">
                  Şu anki şablon ({on.mevcut.dosya_adi}
                  {on.mevcut.zaman ? `, ${tarihGoster(on.mevcut.zaman)}` : ""}) bununla değiştirilecek.
                </p>
              )}
            </div>
          )}
          {sakla.data && (
            <p role="status" className="text-sm">
              Saklandı: {sakla.data.sablon.dosya_adi}. İndir › Müşavir Excel&apos;i artık bu kitabın düzeninde üretilir.
            </p>
          )}
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetni(hata)}
            </p>
          )}
        </>
      )}
    </section>
  );
}
