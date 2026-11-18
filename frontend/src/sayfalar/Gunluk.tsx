import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { hataMetniVarsa } from "@/api/istemci";
import { gunlukXlsxAdresi, useGunluk, useGunlukGeriAl, useGunlukOzeti, type GunlukSatiri, type GunlukSuzgeci } from "@/api/sorgular/gunluk";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button, buttonVariants } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";
import { GeriAlOnayi } from "./ayarlar/GeriAlOnayi";

const BOYUT = 50;
const ARAMA_GECIKME_MS = 300;

export const TUR_ETIKETI: Record<GunlukSatiri["tur"], string> = {
  parametre: "Parametre",
  fiyat: "Fiyat",
  fire: "Fire",
  metin: "Metin",
  recete: "Reçete",
  hesap: "Hesap",
  teklif: "Teklif",
  urun: "Ürün kartı",
  hedef: "Hedef",
  havuz: "Havuz",
  ambalaj: "Ambalaj",
  kapasite: "Kapasite",
  satis: "Satış",
  diger: "Diğer",
};
const TURLER = Object.keys(TUR_ETIKETI) as GunlukSatiri["tur"][];

const GIRDI_SINIFI =
  "h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** "2026-10-22T08:00:00+00:00" -> "22.10.2026 11:00" (yerel saat). */
function zamanGoster(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Başlık ve değerler sunucuda okunur Türkçe biçimlenir (parametre adı, yüzde, TL); burada olduğu gibi gösterilir. */
export function baslikGoster(s: GunlukSatiri): string {
  return s.baslik;
}

function degerGoster(_s: GunlukSatiri, v: string | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  return v;
}

function OzetKartlari({ senaryo, hazir }: { senaryo: number | null; hazir: boolean }) {
  const ozet = useGunlukOzeti(senaryo, 7, hazir);
  const d = ozet.data;
  return (
    <section aria-label="Son 7 gün" className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border bg-card p-3">
        <div className="text-xs text-muted-foreground">Son 7 gün · toplam değişiklik</div>
        <div className="text-2xl font-semibold tabular-nums" data-testid="ozet-toplam">
          {ozet.isLoading ? "…" : (d?.toplam ?? "—")}
        </div>
      </div>
      <div className="rounded-lg border bg-card p-3">
        <div className="text-xs text-muted-foreground">Kullanıcı bazında</div>
        <ul className="mt-1 flex flex-col gap-0.5 text-sm">
          {(d?.kullanici_bazinda ?? []).slice(0, 5).map((k) => (
            <li key={k.kullanici} className="flex justify-between gap-2">
              <span className="truncate">{k.kullanici}</span>
              <span className="tabular-nums">{k.adet}</span>
            </li>
          ))}
          {d && d.kullanici_bazinda.length === 0 && <li className="text-muted-foreground">Kayıt yok</li>}
        </ul>
      </div>
      <div className="rounded-lg border bg-card p-3">
        <div className="text-xs text-muted-foreground">Tür bazında</div>
        <ul className="mt-1 flex flex-wrap gap-1.5 text-sm">
          {(d?.tur_bazinda ?? []).map((t) => (
            <li key={t.tur}>
              <Badge variant="secondary">
                {TUR_ETIKETI[t.tur]} · {t.adet}
              </Badge>
            </li>
          ))}
          {d && d.tur_bazinda.length === 0 && <li className="text-muted-foreground">Kayıt yok</li>}
        </ul>
      </div>
    </section>
  );
}

export default function Gunluk() {
  const { senaryoId, yukleniyor } = useSenaryo();
  const [tumSenaryolar, setTumSenaryolar] = useState(false);
  const [bas, setBas] = useState("");
  const [son, setSon] = useState("");
  const [kullanici, setKullanici] = useState("");
  const [turler, setTurler] = useState<string[]>([]);
  const [urunGirdi, setUrunGirdi] = useState("");
  const [urun, setUrun] = useState("");
  const [aramaGirdi, setAramaGirdi] = useState("");
  const [arama, setArama] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const [bekleyen, setBekleyen] = useState<GunlukSatiri | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const geriAl = useGunlukGeriAl();

  // Metin süzgeçlerinde her tuş vuruşunda istek atmamak için kısa gecikme.
  useEffect(() => {
    const z = setTimeout(() => {
      setUrun(urunGirdi.trim());
      setArama(aramaGirdi.trim());
    }, ARAMA_GECIKME_MS);
    return () => clearTimeout(z);
  }, [urunGirdi, aramaGirdi]);

  const senaryo = tumSenaryolar ? null : senaryoId;
  const suzgec = useMemo<GunlukSuzgeci>(
    () => ({ senaryo, bas, son, kullanici: kullanici.trim(), tur: turler, urun_kodu: urun, q: arama, sayfa, boyut: BOYUT }),
    [senaryo, bas, son, kullanici, turler, urun, arama, sayfa],
  );
  const hazir = tumSenaryolar || !yukleniyor; // senaryo listesi gelmeden süzgeçsiz istek atılmaz
  const sorgu = useGunluk(suzgec, hazir);
  const satirlar = sorgu.data?.kayitlar ?? [];
  const toplam = sorgu.data?.toplam ?? 0;
  const sayfaSayisi = Math.max(1, Math.ceil(toplam / BOYUT));

  const suz = (yaz: () => void) => {
    yaz();
    setSayfa(1);
  };
  const turSec = (t: string, secili: boolean) => suz(() => setTurler((o) => (secili ? [...o, t] : o.filter((x) => x !== t))));

  function onayla() {
    if (!bekleyen?.geri_al) return;
    const baslik = baslikGoster(bekleyen);
    geriAl.mutate(bekleyen.geri_al, {
      onSuccess: () => {
        setMesaj(`${baslik} geri alındı (yeni kayıt olarak eklendi).`);
        setBekleyen(null);
      },
    });
  }

  return (
    <section className="flex flex-col gap-4">
      <SayfaBasligi
        baslik="Değişiklik Günlüğü"
        altBaslik="Parametre, fiyat, fire, reçete, hesap ve teklif değişikliklerinin tek akışı. Kayıtlar silinmez; geri alma yeni kayıt olarak eklenir."
        eylemler={
          <a href={gunlukXlsxAdresi({ ...suzgec })} download className={cn(buttonVariants({ variant: "outline" }))}>
            <Download aria-hidden />
            Excel'e aktar
          </a>
        }
      />

      <OzetKartlari senaryo={senaryo ?? null} hazir={hazir} />

      {mesaj && (
        <p role="status" className="rounded-md bg-muted p-2 text-sm">
          {mesaj}
        </p>
      )}

      <form
        role="search"
        aria-label="Günlük süzgeçleri"
        className="flex flex-col gap-3 rounded-lg border p-3"
        onSubmit={(e) => e.preventDefault()}
      >
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Başlangıç
            <input type="date" value={bas} onChange={(e) => suz(() => setBas(e.target.value))} className={GIRDI_SINIFI} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Bitiş
            <input type="date" value={son} onChange={(e) => suz(() => setSon(e.target.value))} className={GIRDI_SINIFI} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Kullanıcı
            <Input
              value={kullanici}
              onChange={(e) => suz(() => setKullanici(e.target.value))}
              className="w-40"
              placeholder="Kullanıcı adı"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Ürün kodu
            <Input
              value={urunGirdi}
              onChange={(e) => {
                setUrunGirdi(e.target.value);
                setSayfa(1);
              }}
              className="w-40"
              placeholder="Ürün kodu"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Ara
            <Input
              type="search"
              value={aramaGirdi}
              onChange={(e) => {
                setAramaGirdi(e.target.value);
                setSayfa(1);
              }}
              className="w-56"
              placeholder="Başlık, neden, değer…"
            />
          </label>
          <label className="flex items-center gap-2 pb-1 text-sm">
            <input type="checkbox" checked={tumSenaryolar} onChange={(e) => suz(() => setTumSenaryolar(e.target.checked))} />
            Tüm senaryolar
          </label>
        </div>
        <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <legend className="mb-1 text-sm">Tür</legend>
          {TURLER.map((t) => (
            <label key={t} className="flex items-center gap-1.5 text-sm">
              <input type="checkbox" checked={turler.includes(t)} onChange={(e) => turSec(t, e.target.checked)} />
              {TUR_ETIKETI[t]}
            </label>
          ))}
        </fieldset>
      </form>

      {sorgu.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetniVarsa(sorgu.error)}
        </p>
      )}

      <section aria-label="Değişiklik akışı">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Zaman</TableHead>
              <TableHead>Kullanıcı</TableHead>
              <TableHead>Tür</TableHead>
              <TableHead>Başlık</TableHead>
              <TableHead>Ürün</TableHead>
              <TableHead>Eski → Yeni</TableHead>
              <TableHead>Neden</TableHead>
              <TableHead>İşlem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorgu.isLoading && (
              <TableRow>
                <TableCell colSpan={8} role="status" className="text-muted-foreground">
                  Yükleniyor…
                </TableCell>
              </TableRow>
            )}
            {!sorgu.isLoading && satirlar.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} className="text-muted-foreground">
                  Bu süzgeçle kayıt yok
                </TableCell>
              </TableRow>
            )}
            {satirlar.map((s) => (
              <TableRow key={s.id} data-testid={`gunluk-${s.id}`}>
                <TableCell className="whitespace-nowrap tabular-nums">{zamanGoster(s.zaman)}</TableCell>
                <TableCell>{s.kullanici}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{TUR_ETIKETI[s.tur]}</Badge>
                </TableCell>
                <TableCell>{baslikGoster(s)}</TableCell>
                <TableCell className="font-mono text-xs">{s.urun_kodu ?? "—"}</TableCell>
                <TableCell className="max-w-72 text-xs">
                  {s.eski == null && s.yeni == null ? (
                    "—"
                  ) : (
                    <>
                      <span className="text-muted-foreground">{degerGoster(s, s.eski)}</span>
                      {" → "}
                      <span className="font-medium">{degerGoster(s, s.yeni)}</span>
                    </>
                  )}
                </TableCell>
                <TableCell className="max-w-56 text-xs">{s.neden ?? "—"}</TableCell>
                <TableCell>
                  {s.geri_alinabilir && s.geri_al ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Geri al ${s.id}`}
                      onClick={() => {
                        geriAl.reset();
                        setBekleyen(s);
                      }}
                    >
                      Geri al
                    </Button>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
        <span className="mr-auto text-muted-foreground">{toplam} kayıt</span>
        <Button variant="outline" size="sm" disabled={sayfa <= 1} onClick={() => setSayfa((s) => s - 1)}>
          Önceki
        </Button>
        <span>
          Sayfa {sayfa} / {sayfaSayisi}
        </span>
        <Button variant="outline" size="sm" disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa((s) => s + 1)}>
          Sonraki
        </Button>
      </nav>

      {bekleyen && (
        <GeriAlOnayi
          metin={`${baslikGoster(bekleyen)}: ${degerGoster(bekleyen, bekleyen.eski)} değeri bugünden itibaren yeniden geçerli olacak (yeni kayıt olarak eklenir).`}
          hata={hataMetniVarsa(geriAl.error)}
          bekliyor={geriAl.isPending}
          onOnayla={onayla}
          onVazgec={() => {
            geriAl.reset();
            setBekleyen(null);
          }}
        />
      )}
    </section>
  );
}
