import { useState } from "react";
import { KeyRound, UserPlus } from "lucide-react";
import { hataMetniVarsa } from "@/api/istemci";
import {
  useKullaniciEkle,
  useKullaniciGuncelle,
  useKullanicilar,
  useSifreSifirla,
  type GirisKullanicisi,
  type Rol,
} from "@/api/sorgular/kimlik";
import { useOturum } from "@/bilesenler/GirisKapisi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";

const ROL_ACIKLAMA: Record<Rol, string> = {
  genel_direktor: "Her şey; kullanıcı ekler, rol atar, şifre sıfırlar",
  muhasebe: "Her şeyi görür ve değiştirir (kullanıcı yönetimi hariç)",
  satin_alma: "Malzeme kartı ve fiyatlarını girer; diğer sayfaları görür",
  izleyici: "Her şeyi görür, hiçbir şeyi değiştiremez",
};
const ROL_SIRASI: Rol[] = ["genel_direktor", "muhasebe", "satin_alma", "izleyici"];
const ROL_AD: Record<Rol, string> = {
  genel_direktor: "Genel Direktör",
  muhasebe: "Muhasebe",
  satin_alma: "Satın alma",
  izleyici: "İzleyici",
};

const SECIM =
  "h-9 rounded-lg border border-input bg-card px-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** Okunabilir geçici şifre önerisi (karışan harfler yok): kullanıcı ilk girişte değiştirir. */
function sifreOner(): string {
  const harfler = "abcdefghjkmnpqrstuvwxyz23456789";
  const d = new Uint32Array(10);
  globalThis.crypto.getRandomValues(d);
  return Array.from(d, (x) => harfler[x % harfler.length]).join("");
}

function zaman(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function YeniKullanici({ onBilgi }: { onBilgi: (m: string) => void }) {
  const ekle = useKullaniciEkle();
  const [ad, setAd] = useState("");
  const [kadi, setKadi] = useState("");
  const [rol, setRol] = useState<Rol>("muhasebe");
  const [sifre, setSifre] = useState(sifreOner);
  return (
    <form
      aria-label="Yeni kullanıcı"
      className="flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs"
      onSubmit={(e) => {
        e.preventDefault();
        ekle.mutate(
          { ad: ad.trim(), kullanici_adi: kadi.trim().toLowerCase(), rol, gecici_sifre: sifre },
          {
            onSuccess: (k) => {
              onBilgi(
                `${k.ad} eklendi. Kullanıcı adı: ${k.kullanici_adi} · geçici şifre: ${sifre} — kişiye iletin; ilk girişte kendi şifresini belirleyecek.`,
              );
              setAd("");
              setKadi("");
              setSifre(sifreOner());
            },
          },
        );
      }}
    >
      <h2 className="flex items-center gap-2 font-medium">
        <UserPlus className="size-4" aria-hidden /> Yeni kullanıcı
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm">
          <span>Ad soyad</span>
          <Input aria-label="Ad soyad" value={ad} onChange={(e) => setAd(e.target.value)} className="h-9" />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Kullanıcı adı</span>
          <Input
            aria-label="Kullanıcı adı"
            value={kadi}
            onChange={(e) => setKadi(e.target.value)}
            placeholder="ör. ayse.yilmaz"
            autoComplete="off"
            className="h-9"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Rol</span>
          <select aria-label="Rol" value={rol} onChange={(e) => setRol(e.target.value as Rol)} className={SECIM}>
            {ROL_SIRASI.map((r) => (
              <option key={r} value={r}>
                {ROL_AD[r]}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Geçici şifre</span>
          <Input
            aria-label="Geçici şifre"
            value={sifre}
            onChange={(e) => setSifre(e.target.value)}
            autoComplete="off"
            className="h-9 font-mono"
          />
        </label>
      </div>
      <p className="text-xs text-muted-foreground">
        {ROL_ACIKLAMA[rol]}. Kullanıcı adı küçük harf, rakam, nokta ya da tire; en az 3 karakter.
      </p>
      {ekle.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetniVarsa(ekle.error)}
        </p>
      )}
      <div>
        <Button type="submit" disabled={ekle.isPending || !ad.trim() || kadi.trim().length < 3 || sifre.length < 8}>
          <UserPlus aria-hidden /> Kullanıcıyı ekle
        </Button>
      </div>
    </form>
  );
}

function Satir({ k, ben, onBilgi }: { k: GirisKullanicisi; ben: boolean; onBilgi: (m: string) => void }) {
  const guncelle = useKullaniciGuncelle();
  const sifirla = useSifreSifirla();
  const hata = hataMetniVarsa(guncelle.error) ?? hataMetniVarsa(sifirla.error);
  return (
    <TableRow data-pasif={k.aktif ? undefined : "true"} className={k.aktif ? undefined : "text-muted-foreground"}>
      <TableCell>
        <span className="block font-medium">
          {k.ad} {ben && <Badge variant="outline">siz</Badge>}
        </span>
        <span className="block font-mono text-xs text-muted-foreground">{k.kullanici_adi}</span>
        {hata && (
          <span role="alert" className="block text-xs text-destructive">
            {hata}
          </span>
        )}
      </TableCell>
      <TableCell>
        <select
          aria-label={`Rol — ${k.ad}`}
          value={k.rol}
          disabled={guncelle.isPending}
          onChange={(e) => guncelle.mutate({ id: k.id, govde: { rol: e.target.value as Rol } })}
          className={SECIM}
        >
          {ROL_SIRASI.map((r) => (
            <option key={r} value={r}>
              {ROL_AD[r]}
            </option>
          ))}
        </select>
      </TableCell>
      <TableCell>
        {!k.aktif ? (
          <Badge variant="secondary">Pasif</Badge>
        ) : k.sifre_degismeli ? (
          <Badge variant="outline">İlk giriş bekleniyor</Badge>
        ) : (
          "Aktif"
        )}
      </TableCell>
      <TableCell className="tabular-nums">{zaman(k.son_giris)}</TableCell>
      <TableCell>
        <span className="flex flex-wrap gap-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={sifirla.isPending}
            onClick={() => {
              const yeni = sifreOner();
              sifirla.mutate(
                { id: k.id, gecici_sifre: yeni },
                { onSuccess: () => onBilgi(`${k.ad} için yeni geçici şifre: ${yeni} — kişiye iletin; açık oturumları kapatıldı.`) },
              );
            }}
          >
            <KeyRound aria-hidden /> Şifre sıfırla
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={guncelle.isPending || ben}
            title={ben ? "Kendinizi pasifleştiremezsiniz" : undefined}
            onClick={() => guncelle.mutate({ id: k.id, govde: { aktif: !k.aktif } })}
          >
            {k.aktif ? "Pasifleştir" : "Etkinleştir"}
          </Button>
        </span>
      </TableCell>
    </TableRow>
  );
}

/** Yalnız Genel Direktör: kullanıcı ekleme, rol atama, şifre sıfırlama, pasifleştirme. */
export default function Kullanicilar() {
  const { girisZorunlu, yonetici, kullanici } = useOturum();
  const izinli = girisZorunlu && yonetici;
  const liste = useKullanicilar(izinli);
  const [bilgi, setBilgi] = useState<string | null>(null);

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaBasligi
        baslik="Kullanıcılar"
        altBaslik="Kimin giriş yapabileceği ve neleri değiştirebileceği. Değişiklikler günlüğe yazılır."
      />
      {!izinli ? (
        <p role="alert" className="rounded-md border p-3 text-sm text-muted-foreground">
          Bu sayfa yalnız Genel Direktör'e açıktır.
        </p>
      ) : (
        <>
          {bilgi && (
            <p role="status" className="rounded-md border border-marka/40 bg-accent/40 p-3 text-sm">
              {bilgi}
            </p>
          )}
          <YeniKullanici onBilgi={setBilgi} />
          {liste.error && (
            <p role="alert" className="text-sm text-destructive">
              {hataMetniVarsa(liste.error)}
            </p>
          )}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Kullanıcı</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Durum</TableHead>
                <TableHead>Son giriş</TableHead>
                <TableHead>İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(liste.data?.kayitlar ?? []).map((k) => (
                <Satir key={k.id} k={k} ben={k.id === kullanici?.id} onBilgi={setBilgi} />
              ))}
            </TableBody>
          </Table>
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            {ROL_SIRASI.map((r) => (
              <div key={r}>
                <dt className="inline font-medium">{ROL_AD[r]}: </dt>
                <dd className="inline text-muted-foreground">{ROL_ACIKLAMA[r]}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </section>
  );
}
