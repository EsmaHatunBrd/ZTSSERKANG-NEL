import { useState, type FormEvent } from "react";
import { hataMetni } from "@/api/istemci";
import { useListeFiyatiKaydet, useListeFiyatiSil } from "@/api/sorgular/liste";
import { useDuzenlemeKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { NedenAlani } from "@/bilesenler/NedenAlani";
import { NEDEN_IPUCU, nedenGecerli } from "@/yardimcilar/neden";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import type { ListeCalismaSatiri, ListePazari } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/bilesenler/ui/sheet";
import { D, paraBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { adimMetni, PAZAR_ADI } from "./listeYardimci";

/** API sayı metni -> giriş kutusu metni ("54.9" -> "54,9"); boş -> "". */
function kutuMetni(x: string | null | undefined): string {
  return x ? D(x).toFixed().replace(".", ",") : "";
}

interface SatirProps {
  kod: string;
  yil: number;
  pazar: ListePazari;
  liste: string;
  maliyet: string | null;
  bolen: string | null | undefined;
  ornek: boolean;
}

/** Tek yılın satırı: liste fiyatı ve birim maliyet düzenlenir; Kaydet yalnız değişince açılır. */
function YilSatiri({ kod, yil, pazar, liste, maliyet, bolen, ornek }: SatirProps) {
  const kaydet = useListeFiyatiKaydet(useSenaryo().senaryoId);
  const kilitli = !useDuzenlemeKilidi().acik;
  const kilitNotu = kilitli ? "Düzenleme kilitli" : undefined;
  const sil = useListeFiyatiSil();
  const [l, setL] = useState(kutuMetni(liste));
  const [mal, setMal] = useState(kutuMetni(maliyet));
  const [neden, setNeden] = useState("");
  const [silOnayi, setSilOnayi] = useState(false);
  const [silmeNedeni, setSilmeNedeni] = useState("");
  const degisti = l !== kutuMetni(liste) || mal !== kutuMetni(maliyet);
  const lApi = sayiApi(l);
  const malApi = mal.trim() === "" ? null : sayiApi(mal);
  const gecerli = lApi !== null && D(lApi).gt(0) && (mal.trim() === "" || (malApi !== null && D(malApi).gt(0)));
  const hata = kaydet.error;
  // Kaydedilecek bir şey varsa (değişiklik ya da örnek satırın gerçeğe çevrilmesi) neden sorulur.
  const kaydedilebilir = degisti || ornek;
  return (
    <li className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-baseline gap-2">
          <span className="font-semibold tabular-nums">{yil}</span>
          {bolen && <span className="text-xs text-muted-foreground">Bölen {kutuMetni(bolen)}</span>}
        </span>
        {ornek && <span className="rounded-full bg-sari px-2 py-0.5 text-xs font-medium text-foreground">Örnek veri</span>}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Liste fiyatı (TL)</span>
          <Input inputMode="decimal" aria-label={`Liste fiyatı ${yil}`} value={l} onChange={(e) => setL(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Birim maliyet (TL)</span>
          <Input
            inputMode="decimal"
            aria-label={`Birim maliyet ${yil}`}
            value={mal}
            placeholder="isteğe bağlı"
            onChange={(e) => setMal(e.target.value)}
          />
        </label>
      </div>
      {kaydedilebilir && <NedenAlani etiket={`Neden (zorunlu) — ${yil}`} deger={neden} onDegis={setNeden} disabled={kilitli} />}
      <div className="flex justify-end gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={sil.isPending || kilitli}
          title={kilitNotu}
          onClick={() => {
            sil.reset();
            setSilmeNedeni("");
            setSilOnayi(true);
          }}
        >
          Sil
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={!kaydedilebilir || !gecerli || !nedenGecerli(neden) || kaydet.isPending || kilitli}
          title={kilitNotu ?? (kaydedilebilir && !nedenGecerli(neden) ? NEDEN_IPUCU : undefined)}
          onClick={() =>
            kaydet.mutate({ urun_kodu: kod, yil, pazar, liste_fiyati: lApi as string, birim_maliyet: malApi, neden: neden.trim() })
          }
        >
          {ornek && !degisti ? "Gerçek olarak kaydet" : "Kaydet"}
        </Button>
      </div>
      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </p>
      )}
      {silOnayi && (
        <OnayDiyalogu
          baslik={`${yil} ${PAZAR_ADI[pazar].toLocaleLowerCase("tr")} liste fiyatı silinsin mi?`}
          onayMetni="Sil"
          bekliyor={sil.isPending}
          onayPasif={!nedenGecerli(silmeNedeni)}
          hata={sil.error ? hataMetni(sil.error) : null}
          onOnayla={() => sil.mutate({ urun_kodu: kod, yil, pazar, neden: silmeNedeni.trim() }, { onSuccess: () => setSilOnayi(false) })}
          onVazgec={() => setSilOnayi(false)}
        >
          <p>
            {kod} için {yil} yılının liste fiyatı ve birim maliyeti silinecek. Silinen değer Değişiklik Günlüğünde saklanır.
          </p>
          <NedenAlani deger={silmeNedeni} onDegis={setSilmeNedeni} autoFocus />
        </OnayDiyalogu>
      )}
    </li>
  );
}

/** Yeni yıl ekleme formu (varsayılan yıl: listedeki en eski yılın bir öncesi ya da çalışma yılının bir öncesi). */
function YilEkle({ kod, pazar, varsayilanYil }: { kod: string; pazar: ListePazari; varsayilanYil: number }) {
  const kaydet = useListeFiyatiKaydet(useSenaryo().senaryoId);
  const kilitli = !useDuzenlemeKilidi().acik;
  const kilitNotu = kilitli ? "Düzenleme kilitli" : undefined;
  const [yil, setYil] = useState(String(varsayilanYil));
  const [l, setL] = useState("");
  const [mal, setMal] = useState("");
  const [neden, setNeden] = useState("");
  const [uyari, setUyari] = useState<string | null>(null);

  function gonder(e: FormEvent) {
    e.preventDefault();
    const y = Number(yil);
    const lApi = sayiApi(l);
    const malApi = mal.trim() === "" ? null : sayiApi(mal);
    if (!Number.isInteger(y) || y < 2000 || y > 2100) return setUyari("Yıl 2000–2100 arasında olmalı");
    if (lApi === null || !D(lApi).gt(0)) return setUyari("Liste fiyatı 0'dan büyük bir sayı olmalı");
    if (mal.trim() !== "" && (malApi === null || !D(malApi).gt(0))) return setUyari("Birim maliyet 0'dan büyük bir sayı olmalı");
    if (!nedenGecerli(neden)) return setUyari(NEDEN_IPUCU);
    setUyari(null);
    kaydet.mutate(
      { urun_kodu: kod, yil: y, pazar, liste_fiyati: lApi, birim_maliyet: malApi, neden: neden.trim() },
      {
        onSuccess: () => {
          setL("");
          setMal("");
          setNeden("");
          setYil(String(y - 1));
        },
      },
    );
  }

  return (
    <form onSubmit={gonder} aria-label="Yıl ekle" className="flex flex-col gap-2 rounded-lg border border-dashed p-3">
      <span className="text-sm font-medium">Yıl ekle ({PAZAR_ADI[pazar].toLocaleLowerCase("tr")} liste fiyatı)</span>
      <div className="grid grid-cols-3 gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Yıl</span>
          <Input inputMode="numeric" aria-label="Yıl" value={yil} onChange={(e) => setYil(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Liste fiyatı</span>
          <Input inputMode="decimal" aria-label="Yeni liste fiyatı" value={l} onChange={(e) => setL(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Birim maliyet</span>
          <Input
            inputMode="decimal"
            aria-label="Yeni birim maliyet"
            value={mal}
            placeholder="isteğe bağlı"
            onChange={(e) => setMal(e.target.value)}
          />
        </label>
      </div>
      <NedenAlani deger={neden} onDegis={setNeden} disabled={kilitli} />
      <div className="flex justify-end">
        <Button
          type="submit"
          size="sm"
          disabled={kaydet.isPending || kilitli || !nedenGecerli(neden)}
          title={kilitNotu ?? (nedenGecerli(neden) ? undefined : NEDEN_IPUCU)}
        >
          Ekle
        </Button>
      </div>
      {(uyari || kaydet.error) && (
        <p role="alert" className="text-sm text-destructive">
          {uyari ?? hataMetni(kaydet.error)}
        </p>
      )}
    </form>
  );
}

interface Props {
  satir: ListeCalismaSatiri | null;
  yil: number;
  /** Seçili pazar: çekmece yalnız bu pazarın kayıtlarını gösterir ve yazar. */
  pazar: ListePazari;
  bolen: string;
  /** Yuvarlama adımı ("0.05"); yoksa gösterilmez. */
  yuvarlama?: string;
  onKapat: () => void;
}

/** Bir ürünün seçili pazardaki geçmiş liste fiyatları ve birim maliyetleri: elle girme, düzeltme, silme. */
export function GecmisListeCekmecesi({ satir, yil, pazar, bolen, yuvarlama, onKapat }: Props) {
  const gecmis = (satir?.gecmis ?? []).filter((g) => g.pazar === undefined || g.pazar === pazar);
  const enEski = gecmis.length ? Math.min(...gecmis.map((g) => g.yil)) : yil;
  const pazarAdi = PAZAR_ADI[pazar];
  return (
    <Sheet open={satir !== null} onOpenChange={(a) => !a && onKapat()}>
      <SheetContent side="right" className="sm:max-w-md">
        {satir && (
          <>
            <SheetHeader>
              <SheetTitle>{satir.ad}</SheetTitle>
              <SheetDescription>
                {satir.kod} · {yil} {pazarAdi.toLocaleLowerCase("tr")} liste fiyatı{" "}
                {satir.yeni_liste
                  ? `${paraBicimle(satir.yeni_liste)} (satış ÷ ${kutuMetni(bolen)}${yuvarlama ? `, en yakın ${adimMetni(yuvarlama)} TL` : ""})`
                  : "hesaplanamadı"}
                . Önceki yılların {pazarAdi.toLocaleLowerCase("tr")} liste fiyatını ve isterseniz o yılın birim maliyetini girin; artışlar
                buna göre hesaplanır.
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-3 overflow-y-auto px-4 pb-4">
              <YilEkle
                key={`${satir.kod}-${pazar}-${enEski}`}
                kod={satir.kod}
                pazar={pazar}
                varsayilanYil={gecmis.length ? enEski - 1 : yil - 1}
              />
              <ul className="flex flex-col gap-2" aria-label="Geçmiş liste fiyatları">
                {gecmis.length === 0 && (
                  <li className="text-sm text-muted-foreground">
                    Bu ürün için geçmiş {pazarAdi.toLocaleLowerCase("tr")} liste fiyatı yok.
                  </li>
                )}
                {gecmis.map((g) => (
                  <YilSatiri
                    key={`${pazar}-${g.yil}-${g.liste_fiyati}-${g.birim_maliyet}-${g.ornek}`}
                    kod={satir.kod}
                    yil={g.yil}
                    pazar={pazar}
                    liste={g.liste_fiyati}
                    maliyet={g.birim_maliyet}
                    bolen={g.bolen}
                    ornek={g.ornek}
                  />
                ))}
              </ul>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
