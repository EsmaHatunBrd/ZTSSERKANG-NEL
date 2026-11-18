import { useEffect, useState } from "react";
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
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
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

/** Özel ada Türkçe ilgi eki: "Bir" -> "Bir'in", "Ayşe" -> "Ayşe'nin", "Ali Kaya" -> "Ali Kaya'nın". */
function ilgiEki(ad: string): string {
  const a = ad.trim();
  const unluler = "aıoueiöüAIOUEİÖÜ";
  const son = [...a]
    .reverse()
    .find((h) => unluler.includes(h))
    ?.toLocaleLowerCase("tr");
  const ek = son === "a" || son === "ı" ? "ın" : son === "o" || son === "u" ? "un" : son === "ö" || son === "ü" ? "ün" : "in";
  const sonHarf = a.slice(-1);
  return `${a}'${sonHarf && unluler.includes(sonHarf) ? "n" : ""}${ek}`;
}

/** Satırdaki bekleyen onay: pasifleştir/etkinleştir, şifre sıfırla ya da rol değişikliği (seçilen yeni rolle). */
type Onay = { tur: "aktif" } | { tur: "sifre" } | { tur: "rol"; yeni: Rol };

function zaman(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Son başlatılan işlem: `no` her işlemde artar, `kimden` işlemi başlatan form/satır. */
interface Islem {
  no: number;
  kimden: string;
}

interface IslemProps {
  /** Yeni bir işlem başlayınca başka form/satırların eski hata mesajları temizlenir (başlatanın kendi isteği bozulmaz). */
  islem: Islem;
  /** Yeni işlem başlıyor: sayfadaki eski mesajlar temizlenir. */
  onIslem: (kimden: string) => void;
  onBilgi: (m: string) => void;
}

function YeniKullanici({ islem, onIslem, onBilgi }: IslemProps) {
  const ekle = useKullaniciEkle();
  const ekleSifirla = ekle.reset;
  useEffect(() => {
    if (islem.kimden !== "yeni") ekleSifirla();
  }, [islem, ekleSifirla]);
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
        onIslem("yeni");
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

function Satir({ k, ben, islem, onIslem, onBilgi }: IslemProps & { k: GirisKullanicisi; ben: boolean }) {
  const guncelle = useKullaniciGuncelle();
  const sifirla = useSifreSifirla();
  const [onay, setOnay] = useState<Onay | null>(null);
  const { reset: guncelleSifirla } = guncelle;
  const { reset: sifreSifirla } = sifirla;
  // Başka bir işlem başlayınca bu satırın eski hatası da silinir.
  useEffect(() => {
    if (islem.kimden === `satir-${k.id}`) return;
    guncelleSifirla();
    sifreSifirla();
  }, [islem, k.id, guncelleSifirla, sifreSifirla]);
  const bekliyor = guncelle.isPending || sifirla.isPending;
  const hata = hataMetniVarsa(guncelle.error) ?? hataMetniVarsa(sifirla.error);

  function onayla() {
    if (!onay) return;
    onIslem(`satir-${k.id}`);
    const kapat = (mesaj: string) => ({
      onSuccess: () => {
        setOnay(null);
        onBilgi(mesaj);
      },
    });
    if (onay.tur === "rol")
      guncelle.mutate({ id: k.id, govde: { rol: onay.yeni } }, kapat(`${ilgiEki(k.ad)} rolü ${ROL_AD[onay.yeni]} olarak değiştirildi.`));
    else if (onay.tur === "aktif")
      guncelle.mutate(
        { id: k.id, govde: { aktif: !k.aktif } },
        kapat(k.aktif ? `${k.ad} pasifleştirildi; açık oturumları kapatıldı.` : `${k.ad} etkinleştirildi.`),
      );
    else {
      const yeni = sifreOner();
      sifirla.mutate(
        { id: k.id, gecici_sifre: yeni },
        {
          onSuccess: () => {
            setOnay(null);
            onBilgi(`${k.ad} için yeni geçici şifre: ${yeni} — kişiye iletin; açık oturumları kapatıldı.`);
          },
        },
      );
    }
  }

  const baslik =
    onay?.tur === "rol"
      ? `${ilgiEki(k.ad)} rolü ${ROL_AD[k.rol]} → ${ROL_AD[onay.yeni]} olsun mu?`
      : onay?.tur === "sifre"
        ? `${k.ad} için şifre sıfırlansın mı?`
        : k.aktif
          ? `${k.ad} pasifleştirilsin mi?`
          : `${k.ad} etkinleştirilsin mi?`;
  const govde =
    onay?.tur === "rol"
      ? `Yeni rol: ${ROL_ACIKLAMA[onay.yeni]}.`
      : onay?.tur === "sifre"
        ? "Yeni geçici şifre üretilir, açık oturumları kapanır."
        : k.aktif
          ? "Açık oturumları hemen kapanır; bir daha giriş yapamaz. İstediğinizde yeniden etkinleştirebilirsiniz."
          : "Kullanıcı yeniden giriş yapabilir.";
  const onayMetni =
    onay?.tur === "rol" ? "Rolü değiştir" : onay?.tur === "sifre" ? "Şifreyi sıfırla" : k.aktif ? "Pasifleştir" : "Etkinleştir";

  return (
    <TableRow data-pasif={k.aktif ? undefined : "true"} className={k.aktif ? undefined : "text-muted-foreground"}>
      <TableCell>
        <span className="block font-medium">
          {k.ad} {ben && <Badge variant="outline">siz</Badge>}
        </span>
        <span className="block font-mono text-xs text-muted-foreground">{k.kullanici_adi}</span>
      </TableCell>
      <TableCell>
        <select
          aria-label={`Rol — ${k.ad}`}
          // Onay beklerken seçilen rol görünür; Vazgeç'te kayıtlı role döner.
          value={onay?.tur === "rol" ? onay.yeni : k.rol}
          disabled={bekliyor}
          onChange={(e) => {
            const yeni = e.target.value as Rol;
            if (yeni !== k.rol) setOnay({ tur: "rol", yeni });
          }}
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
          <Button type="button" variant="outline" size="sm" disabled={bekliyor} onClick={() => setOnay({ tur: "sifre" })}>
            <KeyRound aria-hidden /> Şifre sıfırla
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={bekliyor || ben}
            title={ben ? "Kendinizi pasifleştiremezsiniz" : undefined}
            onClick={() => setOnay({ tur: "aktif" })}
          >
            {k.aktif ? "Pasifleştir" : "Etkinleştir"}
          </Button>
        </span>
        {onay && (
          <OnayDiyalogu
            baslik={baslik}
            onayMetni={onayMetni}
            bekliyor={bekliyor}
            hata={hata}
            onOnayla={onayla}
            onVazgec={() => {
              guncelle.reset();
              sifirla.reset();
              setOnay(null);
            }}
          >
            <p>{govde}</p>
          </OnayDiyalogu>
        )}
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
  const [islem, setIslem] = useState<Islem>({ no: 0, kimden: "" });
  // Yeni işlem: önceki işlemlerin başarı ve hata mesajları birikmesin.
  const yeniIslem = (kimden: string) => {
    setBilgi(null);
    setIslem((i) => ({ no: i.no + 1, kimden }));
  };

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
          <YeniKullanici islem={islem} onIslem={yeniIslem} onBilgi={setBilgi} />
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
                <Satir key={k.id} k={k} ben={k.id === kullanici?.id} islem={islem} onIslem={yeniIslem} onBilgi={setBilgi} />
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
