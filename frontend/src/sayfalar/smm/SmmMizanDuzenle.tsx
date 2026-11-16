import { useId, useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { hataMetniVarsa, type ApiHatasi } from "@/api/istemci";
import { useSmmMizan, useSmmMizanEkle, useSmmMizanGuncelle, useSmmMizanSil, type SmmMizanTuru } from "@/api/sorgular/smm";
import type { SmmMizanSatiri } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";
import { D, paraBicimle } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { useSmmYazmaKilidi } from "./SmmDuzenlemeKilidi";

const ORNEK = { gider: "720", stok: "150.01.001" } as const;
const kutu = (x: string) => D(x).toFixed().replace(".", ",");

interface FormProps {
  donemId: number;
  tur: SmmMizanTuru;
  /** Düzenlenen satır; null ise yeni satır formu. */
  satir: SmmMizanSatiri | null;
  onKapat: () => void;
  onKaydedildi: (mesaj: string) => void;
}

/** Mizan satırı ekleme / düzenleme diyaloğu: hesap kodu (yalnız yeni satırda), hesap adı, bakiye ve zorunlu neden. */
function MizanSatirFormu({ donemId, tur, satir, onKapat, onKaydedildi }: FormProps) {
  const id = useId();
  const yeni = satir === null;
  const ekle = useSmmMizanEkle(donemId, tur);
  const guncelle = useSmmMizanGuncelle(donemId, tur);
  const yazma = useSmmYazmaKilidi();
  const ilk = { ad: satir?.ad ?? "", bakiye: satir ? kutu(satir.bakiye) : "" };
  const [hesap, setHesap] = useState("");
  const [ad, setAd] = useState(ilk.ad);
  const [bakiye, setBakiye] = useState(ilk.bakiye);
  const [neden, setNeden] = useState("");
  const gonderiliyor = ekle.isPending || guncelle.isPending;
  const bakiyeApi = sayiApi(bakiye, true);
  const hatalar: string[] = [];
  if (yeni && !hesap.trim()) hatalar.push("Hesap kodu zorunlu");
  if (bakiye.trim() === "") hatalar.push("Bakiye zorunlu");
  else if (bakiyeApi === null) hatalar.push("Bakiye geçerli bir sayı olmalı");
  const degisti = ad !== ilk.ad || bakiye !== ilk.bakiye;
  const kaydedilebilir = hatalar.length === 0 && neden.trim() !== "" && (yeni || degisti) && !gonderiliyor && !yazma.kilitli;
  const hata = hataMetniVarsa(ekle.error) ?? hataMetniVarsa(guncelle.error);

  function kaydet() {
    if (!kaydedilebilir || bakiyeApi === null) return;
    const onSuccess = () => {
      onKaydedildi(yeni ? `${hesap.trim()} eklendi.` : `${satir!.hesap} güncellendi.`);
      onKapat();
    };
    if (yeni) ekle.mutate({ hesap: hesap.trim(), ad: ad.trim() || null, bakiye: bakiyeApi, neden: neden.trim() }, { onSuccess });
    else
      guncelle.mutate(
        {
          hesap: satir!.hesap,
          ...(ad !== ilk.ad ? { ad: ad.trim() || null } : {}),
          ...(bakiye !== ilk.bakiye ? { bakiye: bakiyeApi } : {}),
          neden: neden.trim(),
        },
        { onSuccess },
      );
  }

  return (
    <Dialog open onOpenChange={(a) => !a && onKapat()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{yeni ? "Mizan satırı ekle" : `Mizan satırını düzenle: ${satir!.hesap}`}</DialogTitle>
          <DialogDescription>
            Bakiye TL olarak girilir: borç bakiyesi artı, alacak bakiyesi eksi. Değişiklik nedenle günlüğe düşer; SMM özeti ve fiş yeniden
            hesaplanır, satır "elle" işaretlenir.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            kaydet();
          }}
        >
          {yeni && (
            <div className="flex flex-col gap-1">
              <label htmlFor={`${id}-hesap`} className="text-sm font-medium">
                Hesap kodu *
              </label>
              <Input
                id={`${id}-hesap`}
                value={hesap}
                onChange={(e) => setHesap(e.target.value)}
                placeholder={`Örn. ${ORNEK[tur]}`}
                className="h-8 font-mono"
              />
            </div>
          )}
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-ad`} className="text-sm font-medium">
              Hesap adı
            </label>
            <Input id={`${id}-ad`} value={ad} onChange={(e) => setAd(e.target.value)} className="h-8" />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-bakiye`} className="text-sm font-medium">
              Bakiye (TL) *
            </label>
            <Input
              id={`${id}-bakiye`}
              inputMode="decimal"
              value={bakiye}
              onChange={(e) => setBakiye(e.target.value)}
              className="h-8 text-right tabular-nums"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${id}-neden`} className="text-sm font-medium">
              Neden *
            </label>
            <Input
              id={`${id}-neden`}
              value={neden}
              onChange={(e) => setNeden(e.target.value)}
              placeholder="Örn. kesin mizana göre düzeltme"
              className="h-8"
            />
          </div>
          {hatalar.map((h) => (
            <p key={h} className="text-xs text-destructive">
              {h}
            </p>
          ))}
          {hata && (
            <p role="alert" className="text-sm text-destructive">
              {hata}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onKapat}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={!kaydedilebilir} title={yazma.neden}>
              {gonderiliyor ? "Kaydediliyor…" : "Kaydet"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

interface Props {
  donemId: number;
  tur: SmmMizanTuru;
  kilitli: boolean;
}

/**
 * Bir mizanın (gider ya da stok) satırları: hesap kodu, ad, bakiye, "elle" rozeti ve toplam. Kilitli olmayan dönemde satır eklenir,
 * düzenlenir, silinir (neden zorunlu). Excel yeniden yüklenirse elle satırlar silinir; uyarı burada da görünür.
 */
export function SmmMizanBolumu({ donemId, tur, kilitli }: Props) {
  const q = useSmmMizan(donemId, tur);
  const sil = useSmmMizanSil(donemId, tur);
  // `kilitli`: dönem kapatıldı (işlem sütunu hiç görünmez). Düzenleme kilidi kapalıyken düğmeler görünür ama devre dışıdır.
  const { kilitli: yazmaKilitli, neden: kilitNedeni } = useSmmYazmaKilidi(kilitli);
  const [duzenlenen, setDuzenlenen] = useState<SmmMizanSatiri | "yeni" | null>(null);
  const [silinen, setSilinen] = useState<SmmMizanSatiri | null>(null);
  const [silNedeni, setSilNedeni] = useState("");
  const [mesaj, setMesaj] = useState<string | null>(null);
  const v = q.data;

  const sutunlar = useMemo<SutunTanimi<SmmMizanSatiri>[]>(
    () => [
      { accessorKey: "hesap", header: "Hesap kodu", cell: (c) => <span className="font-mono">{c.row.original.hesap}</span> },
      {
        accessorKey: "ad",
        header: "Hesap adı",
        meta: { hiza: "sol" },
        cell: (c) => (
          <span className="flex items-center gap-1.5">
            {c.row.original.ad ?? "—"}
            {c.row.original.elle && (
              <Badge variant="outline" title="Ekranda girildi ya da değiştirildi">
                elle
              </Badge>
            )}
          </span>
        ),
      },
      {
        id: "bakiye",
        accessorFn: (r) => Number(r.bakiye),
        header: "Bakiye",
        meta: { hiza: "sag" },
        cell: (c) => <ParaHucresi deger={c.row.original.bakiye} basamak={2} />,
      },
      ...(kilitli
        ? []
        : ([
            {
              id: "islem",
              header: "",
              enableSorting: false,
              meta: { hiza: "sag" },
              cell: (c) => (
                <span className="flex justify-end gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`${c.row.original.hesap} satırını düzenle`}
                    disabled={yazmaKilitli}
                    title={kilitNedeni}
                    onClick={() => setDuzenlenen(c.row.original)}
                  >
                    <Pencil className="size-3.5" />
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    aria-label={`${c.row.original.hesap} satırını sil`}
                    disabled={yazmaKilitli}
                    title={kilitNedeni}
                    onClick={() => {
                      sil.reset();
                      setSilNedeni("");
                      setSilinen(c.row.original);
                    }}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </span>
              ),
            },
          ] satisfies SutunTanimi<SmmMizanSatiri>[])),
    ],
    [kilitli, sil, yazmaKilitli, kilitNedeni],
  );

  return (
    <section aria-label={`${v?.ad ?? "Mizan"} satırları`} className="flex w-full flex-col gap-2 rounded-xl border bg-background p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-semibold">{v?.ad ?? "Mizan"} satırları</h3>
        {v && v.elle > 0 && <span className="text-xs text-muted-foreground">{v.elle} elle satır</span>}
        {!kilitli && (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="ml-auto"
            disabled={yazmaKilitli}
            title={kilitNedeni}
            onClick={() => setDuzenlenen("yeni")}
          >
            <Plus className="size-3.5" /> Satır ekle
          </Button>
        )}
      </div>
      {mesaj && (
        <p role="status" className="text-sm text-green-700 dark:text-green-400">
          {mesaj}
        </p>
      )}
      <VeriTablosu
        veri={v?.kayitlar ?? []}
        sutunlar={sutunlar}
        yukleniyor={q.isPending}
        hata={q.error as ApiHatasi | null}
        bosMetin="Mizan satırı yok"
        bosAciklama={kilitli ? undefined : "Excel yükleyin ya da Satır ekle ile elle girin."}
        toplamSatiri={() => ({
          ad: "Toplam",
          bakiye: <span className="font-semibold tabular-nums">{paraBicimle(v?.toplam ?? "0", "TL", 2)}</span>,
        })}
      />
      {duzenlenen && (
        <MizanSatirFormu
          donemId={donemId}
          tur={tur}
          satir={duzenlenen === "yeni" ? null : duzenlenen}
          onKapat={() => setDuzenlenen(null)}
          onKaydedildi={setMesaj}
        />
      )}
      {silinen && (
        <OnayDiyalogu
          baslik={`${silinen.hesap} satırı silinsin mi?`}
          onayMetni="Satırı sil"
          bekliyor={sil.isPending || silNedeni.trim() === "" || yazmaKilitli}
          hata={hataMetniVarsa(sil.error)}
          onOnayla={() =>
            sil.mutate(
              { hesap: silinen.hesap, neden: silNedeni.trim() },
              {
                onSuccess: () => {
                  setMesaj(`${silinen.hesap} silindi.`);
                  setSilinen(null);
                },
              },
            )
          }
          onVazgec={() => setSilinen(null)}
        >
          <p>
            <b>{silinen.ad ?? silinen.hesap}</b> ({paraBicimle(silinen.bakiye, "TL", 2)}) mizandan çıkarılır; SMM özeti yeniden hesaplanır.
            Eski değer günlükte kalır.
          </p>
          <label className="flex flex-col gap-1">
            <span className="font-medium">Neden *</span>
            <Input aria-label="Silme nedeni" value={silNedeni} onChange={(e) => setSilNedeni(e.target.value)} className="h-8" />
          </label>
        </OnayDiyalogu>
      )}
    </section>
  );
}
