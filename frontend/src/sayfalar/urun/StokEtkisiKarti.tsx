import { useState, type ReactNode } from "react";
import { PackagePlus, Pencil, Trash2, TriangleAlert } from "lucide-react";
import { hataMetni, hataMetniVarsa } from "@/api/istemci";
import { useStokDevri, useStokDevriKaydet, useStokDevriSil } from "@/api/sorgular/stokDevri";
import type { StokDevri } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { Girdi } from "@/bilesenler/Girdi";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { stokDevriGovdesi, stokFormuDoldur, stokFormuHatalari, stokFormuOzeti, type StokDevriFormDegeri } from "./stokDevriFormu";
import { StokDevriAlanlari } from "./StokDevriAlanlari";

interface Props {
  kod: string;
  senaryoId: number | null;
  kilitli: boolean;
  /** Kayıt/silme sonrası çağrılır: ürün ekranı hesabı yeniden koşturur (satış fiyatı ortalama maliyetten olabilir). */
  onDegisti?: () => void;
}

const adet = (s: string | null) => (s === null ? "—" : paraBicimle(s, "", 0));
const tl = (s: string | null) => (s === null ? "—" : paraBicimle(s, "TL", 2));
const oran = (s: string | null) => (s === null ? "—" : yuzdeBicimle(s, 1));

/** Ekleme / düzenleme diyaloğu: formu doldurur, hataları kırmızıyla gösterir, gönderimden önce özet verir. */
export function StokDevriDiyalogu({
  kod,
  senaryoId,
  mevcut,
  onKapat,
  onKaydedildi,
}: {
  kod: string;
  senaryoId: number;
  mevcut: StokDevri | null | undefined;
  onKapat: () => void;
  onKaydedildi: () => void;
}) {
  const kaydet = useStokDevriKaydet();
  const [deger, setDeger] = useState<StokDevriFormDegeri>(() => stokFormuDoldur(mevcut));
  const [denendi, setDenendi] = useState(false);
  const hatalar = stokFormuHatalari(deger);
  const gecerli = Object.keys(hatalar).length === 0;
  const yeni = !mevcut || mevcut.adet === null;

  return (
    <Dialog open onOpenChange={(a) => !a && !kaydet.isPending && onKapat()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{yeni ? "Stokta kalan ekle" : "Stokta kalanı düzenle"}</DialogTitle>
          <DialogDescription>
            Geçen yıldan kalan stok. Güncel stok maliyeti = birim maliyet × (1 + enflasyon); ortalama maliyet stok ve bu yılın üretimine
            göre ağırlıklandırılır. Kayıt yalnız bu çalışmaya aittir.
          </DialogDescription>
        </DialogHeader>
        <form
          noValidate
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setDenendi(true);
            if (!gecerli || kaydet.isPending) return;
            kaydet.mutate({ kod, senaryo: senaryoId, govde: stokDevriGovdesi(deger) }, { onSuccess: onKaydedildi });
          }}
        >
          <StokDevriAlanlari deger={deger} onDegis={setDeger} hatalar={denendi ? hatalar : {}} devreDisi={kaydet.isPending} />
          <p aria-live="polite" className="rounded-md bg-muted p-2 text-sm">
            {stokFormuOzeti(deger)}
          </p>
          {kaydet.error && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetni(kaydet.error)}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onKapat} disabled={kaydet.isPending}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={kaydet.isPending}>
              {kaydet.isPending ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/** Kaldırma onayı: neden zorunlu. */
function KaldirOnayi({
  kod,
  senaryoId,
  onKapat,
  onKaldirildi,
}: {
  kod: string;
  senaryoId: number;
  onKapat: () => void;
  onKaldirildi: () => void;
}) {
  const sil = useStokDevriSil();
  const [neden, setNeden] = useState("");
  const [denendi, setDenendi] = useState(false);
  const eksik = denendi && !neden.trim();
  return (
    <OnayDiyalogu
      baslik="Stokta kalan kaldırılsın mı?"
      onayMetni={sil.isPending ? "Kaldırılıyor…" : "Kaldır"}
      bekliyor={sil.isPending}
      hata={hataMetniVarsa(sil.error)}
      onVazgec={onKapat}
      onOnayla={() => {
        setDenendi(true);
        if (!neden.trim()) return;
        sil.mutate({ kod, senaryo: senaryoId, neden: neden.trim() }, { onSuccess: onKaldirildi });
      }}
    >
      <p>Bu ürünün stokta kalan kaydı silinir; maliyet yalnız bu yılın üretimiyle hesaplanır.</p>
      <label htmlFor="stok-kaldir-neden" className="font-medium">
        Neden (zorunlu)
      </label>
      <Girdi id="stok-kaldir-neden" value={neden} aria-invalid={eksik} onChange={(e) => setNeden(e.target.value)} />
      {eksik && (
        <p role="alert" className="text-xs text-destructive">
          Neden zorunlu
        </p>
      )}
    </OnayDiyalogu>
  );
}

function Satir({ etiket, children, vurgu }: { etiket: string; children: ReactNode; vurgu?: boolean }) {
  return (
    <div className={`flex items-baseline justify-between gap-3 py-1 ${vurgu ? "border-t pt-2 font-semibold" : ""}`}>
      <dt className={vurgu ? "" : "text-muted-foreground"}>{etiket}</dt>
      <dd className="flex items-center gap-1.5 text-right tabular-nums">{children}</dd>
    </div>
  );
}

/**
 * Ürün ekranındaki "Stok etkisi" bölümü: ürün ekranının "hücreye yaz, tek Kaydet" akışından AYRIDIR, her işlem anında kaydedilir.
 * Kayıt yoksa yalnız sade bir "Stokta kalan ekle" düğmesi görünür (dikkat çekmez).
 */
export function StokEtkisiKarti({ kod, senaryoId, kilitli, onDegisti }: Props) {
  const sorgu = useStokDevri(kod, senaryoId);
  const [diyalog, setDiyalog] = useState<"duzenle" | "kaldir" | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const k = sorgu.data;
  const kayitVar = !!k && k.adet !== null;

  if (senaryoId === null || sorgu.isPending) return null;

  const bitti = (m: string) => {
    setDiyalog(null);
    setMesaj(m);
    onDegisti?.();
  };

  const diyaloglar = (
    <>
      {diyalog === "duzenle" && (
        <StokDevriDiyalogu
          kod={kod}
          senaryoId={senaryoId}
          mevcut={k}
          onKapat={() => setDiyalog(null)}
          onKaydedildi={() => bitti("Stokta kalan kaydedildi.")}
        />
      )}
      {diyalog === "kaldir" && (
        <KaldirOnayi
          kod={kod}
          senaryoId={senaryoId}
          onKapat={() => setDiyalog(null)}
          onKaldirildi={() => bitti("Stokta kalan kaldırıldı.")}
        />
      )}
    </>
  );

  if (sorgu.error) {
    return (
      <p role="alert" className="text-sm text-destructive">
        Stokta kalan bilgisi alınamadı: {hataMetni(sorgu.error)}
      </p>
    );
  }

  if (!kayitVar) {
    return (
      <div className="flex flex-wrap items-center gap-2" data-testid="stok-etkisi-bos">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground"
          disabled={kilitli}
          title={kilitli ? "Senaryo kilitli" : "Geçen yıldan kalan stok varsa ortalama maliyet için girin"}
          onClick={() => setDiyalog("duzenle")}
        >
          <PackagePlus aria-hidden />
          Stokta kalan ekle
        </Button>
        {mesaj && (
          <span role="status" className="text-sm text-muted-foreground">
            {mesaj}
          </span>
        )}
        {diyaloglar}
      </div>
    );
  }

  const enflasyonElle = k.enflasyon !== null;
  return (
    <section aria-labelledby="stok-etkisi-baslik" className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="stok-etkisi-baslik" className="text-base font-semibold">
            Stok etkisi
          </h2>
          <p className="text-xs text-muted-foreground">Geçen yıldan kalan stokla ağırlıklı ortalama maliyet · anında kaydedilir</p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={kilitli}
            title={kilitli ? "Senaryo kilitli" : undefined}
            onClick={() => setDiyalog("duzenle")}
          >
            <Pencil aria-hidden />
            Düzenle
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={kilitli}
            title={kilitli ? "Senaryo kilitli" : undefined}
            onClick={() => setDiyalog("kaldir")}
          >
            <Trash2 aria-hidden />
            Kaldır
          </Button>
        </div>
      </header>

      {k.aciklama && (
        <p
          role="note"
          className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
        >
          <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          {k.aciklama}
        </p>
      )}

      <div className="grid gap-x-8 sm:grid-cols-2">
        <dl className="text-sm">
          <Satir etiket="Stok adedi">{adet(k.adet)}</Satir>
          <Satir etiket="Stok birim maliyeti">{tl(k.birim_maliyet)}</Satir>
          <Satir etiket="Enflasyon">
            {oran(k.enflasyon_kullanilan)}
            <Badge variant={enflasyonElle ? "secondary" : "outline"}>{enflasyonElle ? "elle" : "parametre"}</Badge>
          </Satir>
          <Satir etiket="Güncel stok maliyeti">{tl(k.guncel_stok_maliyeti)}</Satir>
        </dl>
        <dl className="text-sm">
          <Satir etiket="Bu yıl üretim adedi">
            {adet(k.uretim_adedi_kullanilan)}
            {k.uretim_adedi_kaynagi && (
              <Badge variant={k.uretim_adedi_kaynagi === "elle" ? "secondary" : "outline"}>
                {k.uretim_adedi_kaynagi === "elle" ? "elle" : "geçen yıl satışı"}
              </Badge>
            )}
          </Satir>
          <Satir etiket="Bu yılın maliyeti">{tl(k.bu_yil_maliyet)}</Satir>
          <Satir etiket="Stok payı">{oran(k.stok_payi)}</Satir>
          <Satir etiket="Ortalama maliyet" vurgu>
            {tl(k.ortalama_maliyet)}
          </Satir>
        </dl>
      </div>
      {mesaj && (
        <p role="status" className="text-sm text-muted-foreground">
          {mesaj}
        </p>
      )}
      {diyaloglar}
    </section>
  );
}
