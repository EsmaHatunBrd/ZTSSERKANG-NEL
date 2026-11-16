import { useId, useRef, useState } from "react";
import { FolderOpen, Upload } from "lucide-react";
import { ApiHatasi, hataMetni } from "@/api/istemci";
import { useSatisOnizle, useSatisYukle } from "@/api/sorgular/satis";
import type { SatisYuklemeOzeti } from "@/api/tipler";
import { useDuzenlemeKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { YuklemeYardimi } from "@/bilesenler/SablonIndir";
import { SonYuklemeSeridi } from "@/bilesenler/SonYuklemeSeridi";
import { YuklemeOzetiKutusu } from "@/bilesenler/YuklemeOzetiKutusu";
import { Button } from "@/bilesenler/ui/button";

interface YuklemeHatasi {
  satir_no: number;
  mesaj: string;
}

/** 422 gövdesindeki `alanlar.hatalar` ([{satir_no, mesaj}]) listesini okur; yoksa boş. */
function yuklemeHatalari(e: unknown): YuklemeHatasi[] {
  if (!(e instanceof ApiHatasi) || !Array.isArray(e.alanlar.hatalar)) return [];
  return (e.alanlar.hatalar as YuklemeHatasi[]).filter((h) => typeof h?.satir_no === "number");
}

/**
 * Satış geçmişi dosya yükleme kartı (CSV/xlsx): Satış Geçmişi sayfasında ve Veri Aktar → Satış geçmişi sekmesinde aynı bileşen.
 * Yükleme senaryodan bağımsızdır (satış geçmişi ürün bazlı tutulur); başarıda liste sorguları mutasyon tarafından tazelenir.
 * Önizle: kaç satır eklenecek, kaçı zaten kayıtlı (atlanır, ikilenmez). Son yükleme "Geri al" ile kaldırılabilir.
 */
export function SatisYuklemeKarti({ baslik = "Dosyadan yükle" }: { baslik?: string }) {
  const kilitli = !useDuzenlemeKilidi().acik;
  const id = useId();
  const yukle = useSatisYukle();
  const onizle = useSatisOnizle();
  const dosyaRef = useRef<HTMLInputElement>(null);
  const [dosya, setDosya] = useState<File | null>(null);
  const [ozet, setOzet] = useState<SatisYuklemeOzeti | null>(null);
  const hatalar = yuklemeHatalari(yukle.error);

  function yukleTikla() {
    if (!dosya) return;
    setOzet(null);
    yukle.mutate(dosya, {
      onSuccess: (o) => {
        setOzet(o);
        setDosya(null);
        onizle.reset();
        if (dosyaRef.current) dosyaRef.current.value = "";
      },
    });
  }

  return (
    <section aria-labelledby={`${id}-baslik`} className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-sm">
      <h2 id={`${id}-baslik`} className="flex items-center gap-2 text-base font-semibold">
        <Upload className="size-4 text-marka" aria-hidden />
        {baslik}
      </h2>
      <p className="text-sm text-muted-foreground">
        Şablonu indirip doldurun, CSV ya da xlsx olarak yükleyin. Sütunlar: ürün kodu, müşteri, tarih, fiyat, para birimi, adet. Yüklenen
        satırlar listeye eklenir; sistemde aynısı (ürün, müşteri, tarih, fiyat, adet) olan satırlar atlanır. Hatalı satır varsa hiçbir satır
        eklenmez ve hatalar aşağıda listelenir.
      </p>
      <YuklemeYardimi />
      <SonYuklemeSeridi
        yol="/api/v1/satis-gecmisi"
        sorgu={{}}
        kilitli={kilitli}
        kilitNedeni="Düzenleme kilitli"
        gecersiz={["satis-gecmisi"]}
      />
      <div className="flex flex-wrap items-center gap-2">
        <label
          htmlFor={id}
          className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-lg border border-input bg-background px-3 text-sm font-medium hover:bg-muted focus-within:ring-2 focus-within:ring-ring/50"
        >
          <FolderOpen className="size-4" aria-hidden />
          Dosya seç
        </label>
        <input
          id={id}
          ref={dosyaRef}
          type="file"
          accept=".csv,.xlsx"
          className="sr-only"
          onChange={(e) => {
            setDosya(e.target.files?.[0] ?? null);
            setOzet(null);
            yukle.reset();
            onizle.reset();
          }}
        />
        <span className={dosya ? "text-sm" : "text-sm text-muted-foreground"} data-testid="secili-dosya">
          {dosya ? dosya.name : "Henüz dosya seçilmedi"}
        </span>
        <Button type="button" variant="outline" disabled={!dosya || onizle.isPending} onClick={() => dosya && onizle.mutate(dosya)}>
          {onizle.isPending ? "Önizleniyor…" : "Önizle"}
        </Button>
        <Button
          type="button"
          disabled={!dosya || yukle.isPending || kilitli}
          title={kilitli ? "Düzenleme kilitli" : undefined}
          onClick={yukleTikla}
        >
          {yukle.isPending ? "Yükleniyor…" : "Yükle"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Sayı biçimi: 1234.56 veya 1.234,56; &quot;2.000&quot; (virgülsüz, noktadan sonra 3 hane) belirsiz sayılıp reddedilir. En fazla
        20.000 satır.
      </p>
      {onizle.data && (
        <section aria-label="Önizleme" className="flex flex-col gap-1 rounded-md border p-3">
          <p className="text-sm">
            {onizle.data.eklenecek} satır eklenecek
            {onizle.data.kayitli > 0 ? `, ${onizle.data.kayitli} satır zaten kayıtlı (atlanacak)` : ""}.
          </p>
          <YuklemeOzetiKutusu ozet={onizle.data.ozet} baslik="Satış geçmişi — sorunlu satırlar" />
        </section>
      )}
      {onizle.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(onizle.error)}
        </p>
      )}
      <div aria-live="polite">
        {ozet && (
          <p
            role="status"
            aria-label="Yükleme sonucu"
            className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-900 dark:bg-green-950/40 dark:text-green-200"
          >
            {ozet.eklenen} satır eklendi.
            {(ozet.atlanan_kayitli ?? 0) > 0 && ` ${ozet.atlanan_kayitli} satır zaten kayıtlı olduğu için atlandı.`}
          </p>
        )}
        {yukle.error && (
          <div
            role="alert"
            aria-label="Yükleme hataları"
            className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-900 dark:bg-red-950/40 dark:text-red-200"
          >
            {hatalar.length > 0 ? (
              <>
                <p className="font-medium">Dosyada hatalı satırlar var; hiçbir satır eklenmedi.</p>
                <ul className="mt-1 list-disc pl-5">
                  {hatalar.map((h) => (
                    <li key={h.satir_no}>
                      Satır {h.satir_no}: {h.mesaj}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              hataMetni(yukle.error)
            )}
          </div>
        )}
      </div>
    </section>
  );
}
