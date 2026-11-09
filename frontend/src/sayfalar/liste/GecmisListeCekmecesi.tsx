import { useState, type FormEvent } from "react";
import { hataMetni } from "@/api/istemci";
import { useListeFiyatiKaydet, useListeFiyatiSil } from "@/api/sorgular/liste";
import type { ListeCalismaSatiri } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/bilesenler/ui/sheet";
import { D, paraBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";

/** API sayı metni -> giriş kutusu metni ("54.9" -> "54,9"); boş -> "". */
function kutuMetni(x: string | null | undefined): string {
  return x ? D(x).toFixed().replace(".", ",") : "";
}

interface SatirProps {
  kod: string;
  yil: number;
  liste: string;
  maliyet: string | null;
  ornek: boolean;
}

/** Tek yılın satırı: liste fiyatı ve birim maliyet düzenlenir; Kaydet yalnız değişince açılır. */
function YilSatiri({ kod, yil, liste, maliyet, ornek }: SatirProps) {
  const kaydet = useListeFiyatiKaydet();
  const sil = useListeFiyatiSil();
  const [l, setL] = useState(kutuMetni(liste));
  const [mal, setMal] = useState(kutuMetni(maliyet));
  const degisti = l !== kutuMetni(liste) || mal !== kutuMetni(maliyet);
  const lApi = sayiApi(l);
  const malApi = mal.trim() === "" ? null : sayiApi(mal);
  const gecerli = lApi !== null && D(lApi).gt(0) && (mal.trim() === "" || (malApi !== null && D(malApi).gt(0)));
  const hata = kaydet.error ?? sil.error;
  return (
    <li className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold tabular-nums">{yil}</span>
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
      <div className="flex justify-end gap-2">
        <Button type="button" size="sm" variant="outline" disabled={sil.isPending} onClick={() => sil.mutate({ urun_kodu: kod, yil })}>
          Sil
        </Button>
        <Button
          type="button"
          size="sm"
          disabled={(!degisti && !ornek) || !gecerli || kaydet.isPending}
          onClick={() => kaydet.mutate({ urun_kodu: kod, yil, liste_fiyati: lApi as string, birim_maliyet: malApi })}
        >
          {ornek && !degisti ? "Gerçek olarak kaydet" : "Kaydet"}
        </Button>
      </div>
      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </p>
      )}
    </li>
  );
}

/** Yeni yıl ekleme formu (varsayılan yıl: listedeki en eski yılın bir öncesi ya da çalışma yılının bir öncesi). */
function YilEkle({ kod, varsayilanYil }: { kod: string; varsayilanYil: number }) {
  const kaydet = useListeFiyatiKaydet();
  const [yil, setYil] = useState(String(varsayilanYil));
  const [l, setL] = useState("");
  const [mal, setMal] = useState("");
  const [uyari, setUyari] = useState<string | null>(null);

  function gonder(e: FormEvent) {
    e.preventDefault();
    const y = Number(yil);
    const lApi = sayiApi(l);
    const malApi = mal.trim() === "" ? null : sayiApi(mal);
    if (!Number.isInteger(y) || y < 2000 || y > 2100) return setUyari("Yıl 2000–2100 arasında olmalı");
    if (lApi === null || !D(lApi).gt(0)) return setUyari("Liste fiyatı 0'dan büyük bir sayı olmalı");
    if (mal.trim() !== "" && (malApi === null || !D(malApi).gt(0))) return setUyari("Birim maliyet 0'dan büyük bir sayı olmalı");
    setUyari(null);
    kaydet.mutate(
      { urun_kodu: kod, yil: y, liste_fiyati: lApi, birim_maliyet: malApi },
      {
        onSuccess: () => {
          setL("");
          setMal("");
          setYil(String(y - 1));
        },
      },
    );
  }

  return (
    <form onSubmit={gonder} aria-label="Yıl ekle" className="flex flex-col gap-2 rounded-lg border border-dashed p-3">
      <span className="text-sm font-medium">Yıl ekle</span>
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
      <div className="flex justify-end">
        <Button type="submit" size="sm" disabled={kaydet.isPending}>
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
  bolen: string;
  onKapat: () => void;
}

/** Bir ürünün geçmiş yıllardaki liste fiyatları ve birim maliyetleri: elle girme, düzeltme, silme. */
export function GecmisListeCekmecesi({ satir, yil, bolen, onKapat }: Props) {
  const enEski = satir?.gecmis.length ? Math.min(...satir.gecmis.map((g) => g.yil)) : yil;
  return (
    <Sheet open={satir !== null} onOpenChange={(a) => !a && onKapat()}>
      <SheetContent side="right" className="sm:max-w-md">
        {satir && (
          <>
            <SheetHeader>
              <SheetTitle>{satir.ad}</SheetTitle>
              <SheetDescription>
                {satir.kod} · {yil} liste fiyatı{" "}
                {satir.yeni_liste ? `${paraBicimle(satir.yeni_liste)} (satış ÷ ${kutuMetni(bolen)})` : "hesaplanamadı"}. Önceki yılların
                liste fiyatını ve isterseniz o yılın birim maliyetini girin; artışlar buna göre hesaplanır.
              </SheetDescription>
            </SheetHeader>
            <div className="flex flex-col gap-3 overflow-y-auto px-4 pb-4">
              <YilEkle key={`${satir.kod}-${enEski}`} kod={satir.kod} varsayilanYil={satir.gecmis.length ? enEski - 1 : yil - 1} />
              <ul className="flex flex-col gap-2" aria-label="Geçmiş liste fiyatları">
                {satir.gecmis.length === 0 && <li className="text-sm text-muted-foreground">Bu ürün için geçmiş liste fiyatı yok.</li>}
                {satir.gecmis.map((g) => (
                  <YilSatiri
                    key={`${g.yil}-${g.liste_fiyati}-${g.birim_maliyet}-${g.ornek}`}
                    kod={satir.kod}
                    yil={g.yil}
                    liste={g.liste_fiyati}
                    maliyet={g.birim_maliyet}
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
