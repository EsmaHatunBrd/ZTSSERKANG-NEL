import { useId, useMemo, useState } from "react";
import { PackageOpen } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useStokDevri, useStokDevriKaydet, useStokDevriListesi } from "@/api/sorgular/stokDevri";
import { useUrunler } from "@/api/sorgular/urunler";
import type { StokDevri } from "@/api/tipler";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { paraBicimle } from "@/yardimcilar/para";
import { stokDevriGovdesi, stokFormuDoldur, stokFormuHatalari, stokFormuOzeti, type StokDevriFormDegeri } from "../urun/stokDevriFormu";
import { StokDevriAlanlari } from "../urun/StokDevriAlanlari";
import { Alan, Kart, SELECT } from "./ortak";

/** Tek sayfada arama/seçim için üst sınır (API `boyut` en çok 500). */
const LISTE_BOYUTU = 500;
/** Kartın altındaki kısa listede gösterilen kayıt sayısı; fazlası "Tüm liste" ile açılır. */
const KISA_LISTE = 5;

const tr = (s: string) => s.toLocaleLowerCase("tr");

function Form({
  kod,
  senaryoId,
  kilitli,
  mevcut,
  onMesaj,
  onVazgec,
}: {
  kod: string;
  senaryoId: number;
  kilitli: boolean;
  mevcut: StokDevri | undefined;
  onMesaj: (m: string) => void;
  onVazgec: () => void;
}) {
  const kaydet = useStokDevriKaydet();
  const [deger, setDeger] = useState<StokDevriFormDegeri>(() => stokFormuDoldur(mevcut));
  const [denendi, setDenendi] = useState(false);
  const hatalar = stokFormuHatalari(deger);
  const kayitVar = !!mevcut && mevcut.adet !== null;

  return (
    <form
      noValidate
      aria-label="Stokta kalan formu"
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        setDenendi(true);
        if (Object.keys(hatalar).length > 0 || kaydet.isPending || kilitli) return;
        kaydet.mutate(
          { kod, senaryo: senaryoId, govde: stokDevriGovdesi(deger) },
          {
            onSuccess: () => {
              onMesaj(`${kod} için stokta kalan kaydedildi.`);
              setDeger((d) => ({ ...d, neden: "" }));
              setDenendi(false);
            },
          },
        );
      }}
    >
      <p className="text-xs text-muted-foreground">
        {kayitVar
          ? "Bu ürünün kayıtlı stokta kalanı aşağıda; değiştirip kaydedin."
          : "Bu ürün için henüz stokta kalan yok; girilen değerler ilk kayıt olur."}
      </p>
      <StokDevriAlanlari deger={deger} onDegis={setDeger} hatalar={denendi ? hatalar : {}} devreDisi={kilitli || kaydet.isPending} />
      <p aria-live="polite" className="rounded-md bg-muted p-2 text-xs">
        {stokFormuOzeti(deger)}
      </p>
      {kaydet.error && (
        <p role="alert" className="text-xs text-destructive">
          {hataMetni(kaydet.error)}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={kilitli || kaydet.isPending}>
          {kaydet.isPending ? "Kaydediliyor…" : "Kaydet"}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onVazgec}>
          Vazgeç
        </Button>
      </div>
    </form>
  );
}

/** Veri Girişi → "Stokta kalan": ürünü bulun, geçen yıldan kalan stoku girin. Altta bu çalışmada kaydı olan ürünler. */
export function StokDevriKarti({ senaryoId, kilitli, onMesaj }: { senaryoId: number; kilitli: boolean; onMesaj: (m: string) => void }) {
  const id = useId();
  const urunler = useUrunler(senaryoId, { boyut: LISTE_BOYUTU });
  const liste = useStokDevriListesi(senaryoId);
  const [arama, setArama] = useState("");
  const [kod, setKod] = useState("");
  const [tumu, setTumu] = useState(false);
  const kayit = useStokDevri(kod, senaryoId);

  const secenekler = useMemo(() => {
    const q = tr(arama.trim());
    const hepsi = urunler.data?.kayitlar ?? [];
    return q ? hepsi.filter((u) => tr(u.kod).includes(q) || tr(u.ad).includes(q)) : hepsi;
  }, [urunler.data, arama]);

  const kayitlar = liste.data?.kayitlar ?? [];
  const gorunen = tumu ? kayitlar : kayitlar.slice(0, KISA_LISTE);

  return (
    <Kart
      baslik="Stokta kalan"
      aciklama="Geçen yıldan kalan stok varsa ürünü seçip adet ve birim maliyetini girin; ortalama maliyet buna göre hesaplanır. Kayıt yalnız bu çalışmaya aittir."
      simge={<PackageOpen />}
    >
      <div className="grid gap-2 sm:grid-cols-2">
        <Alan etiket="Ürün ara" htmlFor={`${id}-ara`}>
          <Input
            id={`${id}-ara`}
            type="search"
            placeholder="Kod ya da ad"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
            className="h-8"
          />
        </Alan>
        <Alan etiket="Ürün" htmlFor={`${id}-urun`}>
          <select id={`${id}-urun`} className={SELECT} value={kod} disabled={urunler.isLoading} onChange={(e) => setKod(e.target.value)}>
            <option value="">{urunler.isLoading ? "Yükleniyor…" : `Seçin… (${secenekler.length})`}</option>
            {secenekler.map((u) => (
              <option key={u.kod} value={u.kod}>
                {u.kod} — {u.ad}
              </option>
            ))}
          </select>
        </Alan>
      </div>
      {urunler.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(urunler.error)}
        </p>
      )}

      {kod && kayit.isPending && <p className="text-sm text-muted-foreground">Yükleniyor…</p>}
      {kod && kayit.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(kayit.error)}
        </p>
      )}
      {kod && kayit.isSuccess && (
        <Form
          key={kod}
          kod={kod}
          senaryoId={senaryoId}
          kilitli={kilitli}
          mevcut={kayit.data}
          onMesaj={onMesaj}
          onVazgec={() => setKod("")}
        />
      )}

      <div className="flex flex-col gap-1 border-t pt-2">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-medium">Kaydı olan ürünler{liste.data ? ` (${kayitlar.length})` : ""}</h3>
          {kayitlar.length > KISA_LISTE && (
            <button
              type="button"
              className="text-xs font-medium text-primary underline-offset-4 hover:underline"
              onClick={() => setTumu((t) => !t)}
            >
              {tumu ? "Kısa liste" : `Tüm liste (${kayitlar.length}) →`}
            </button>
          )}
        </div>
        {liste.isPending && <p className="text-xs text-muted-foreground">Yükleniyor…</p>}
        {liste.error && (
          <p role="alert" className="text-xs text-destructive">
            {hataMetni(liste.error)}
          </p>
        )}
        {liste.isSuccess && kayitlar.length === 0 && (
          <p className="text-xs text-muted-foreground">Bu çalışmada stokta kalan girilmiş ürün yok.</p>
        )}
        {gorunen.length > 0 && (
          <table aria-label="Stokta kalanı olan ürünler" className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">Ürün</th>
                <th className="py-1 text-right font-medium">Stok adedi</th>
                <th className="py-1 text-right font-medium">Ortalama maliyet</th>
              </tr>
            </thead>
            <tbody>
              {gorunen.map((k) => (
                <tr key={k.urun_kodu} className="border-t">
                  <td className="py-1">
                    <button
                      type="button"
                      className="text-left hover:underline"
                      title="Formda aç"
                      onClick={() => {
                        setArama("");
                        setKod(k.urun_kodu);
                      }}
                    >
                      <span className="text-xs text-muted-foreground tabular-nums">{k.urun_kodu}</span> {k.ad}
                    </button>
                  </td>
                  <td className="py-1 text-right tabular-nums">{k.adet === null ? "—" : paraBicimle(k.adet, "", 0)}</td>
                  <td className="py-1 text-right tabular-nums">
                    {k.ortalama_maliyet === null ? "—" : paraBicimle(k.ortalama_maliyet, "TL", 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Kart>
  );
}
