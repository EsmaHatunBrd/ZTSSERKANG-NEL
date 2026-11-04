import { createContext, useContext, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, LogIn } from "lucide-react";
import { ApiHatasi, girisModunuAyarla, hataMetni } from "@/api/istemci";
import { useBen, useCikis, useGiris, useSifreDegistir, type GirisKullanicisi, type Rol } from "@/api/sorgular/kimlik";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Logo } from "./Logo";

interface Oturum {
  /** Sunucu girişi zorunlu tutuyor mu (false: eski tek kullanıcılı kurulum, ad diyaloğu). */
  girisZorunlu: boolean;
  kullanici: GirisKullanicisi | null;
}

const OturumBaglami = createContext<Oturum>({ girisZorunlu: false, kullanici: null });

/** Oturumdaki kullanıcı ve rol (giriş zorunlu değilse kullanici null; her şeye izin var sayılır). */
export function useOturum(): Oturum & { rol: Rol | null; yonetici: boolean; yazabilir: boolean } {
  const o = useContext(OturumBaglami);
  const rol = o.kullanici?.rol ?? null;
  return { ...o, rol, yonetici: !o.girisZorunlu || rol === "genel_direktor", yazabilir: !o.girisZorunlu || rol !== "izleyici" };
}

/** Testlerde ve hikâyelerde kapıyı atlayıp rol vermek için. */
export function OturumSaglayici({ deger, children }: { deger: Oturum; children: ReactNode }) {
  return <OturumBaglami.Provider value={deger}>{children}</OturumBaglami.Provider>;
}

function Kart({ baslik, aciklama, children }: { baslik: string; aciklama?: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 text-foreground">
      <div className="flex w-full max-w-sm flex-col gap-5 rounded-2xl border bg-card p-6 shadow-sm">
        <div className="flex flex-col items-center gap-2 text-center">
          <Logo />
          <h1 className="text-lg font-semibold">{baslik}</h1>
          {aciklama && <p className="text-sm text-muted-foreground">{aciklama}</p>}
        </div>
        {children}
      </div>
    </main>
  );
}

function Alan({ etiket, ...p }: { etiket: string } & React.ComponentProps<typeof Input>) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{etiket}</span>
      <Input aria-label={etiket} className="h-9" {...p} />
    </label>
  );
}

export function GirisEkrani() {
  const giris = useGiris();
  const [ad, setAd] = useState("");
  const [sifre, setSifre] = useState("");
  return (
    <Kart baslik="Fiyat Çalışması" aciklama="Devam etmek için giriş yapın.">
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (ad.trim() && sifre) giris.mutate({ kullanici_adi: ad.trim(), sifre });
        }}
      >
        <Alan etiket="Kullanıcı adı" autoFocus autoComplete="username" value={ad} onChange={(e) => setAd(e.target.value)} />
        <Alan etiket="Şifre" type="password" autoComplete="current-password" value={sifre} onChange={(e) => setSifre(e.target.value)} />
        {giris.error && (
          <p role="alert" className="text-sm text-destructive">
            {hataMetni(giris.error)}
          </p>
        )}
        <Button type="submit" disabled={giris.isPending || !ad.trim() || !sifre}>
          <LogIn aria-hidden /> {giris.isPending ? "Giriş yapılıyor…" : "Giriş yap"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">Şifrenizi unuttuysanız Genel Direktör sıfırlayabilir.</p>
      </form>
    </Kart>
  );
}

/** Şifre belirleme/değiştirme formu: geçici şifreyle ilk girişte (zorunlu) ve Hesabım penceresinde kullanılır. */
export function SifreFormu({ eskiEtiket = "Mevcut şifre", onBitti }: { eskiEtiket?: string; onBitti?: () => void }) {
  const degistir = useSifreDegistir();
  const [eski, setEski] = useState("");
  const [yeni, setYeni] = useState("");
  const [tekrar, setTekrar] = useState("");
  const yerelHata =
    yeni && yeni.length < 8 ? "Yeni şifre en az 8 karakter olmalı" : tekrar && yeni !== tekrar ? "Yeni şifreler aynı değil" : null;
  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (yerelHata || !eski || !yeni) return;
        degistir.mutate({ eski_sifre: eski, yeni_sifre: yeni }, { onSuccess: () => onBitti?.() });
      }}
    >
      <Alan etiket={eskiEtiket} type="password" autoComplete="current-password" value={eski} onChange={(e) => setEski(e.target.value)} />
      <Alan etiket="Yeni şifre" type="password" autoComplete="new-password" value={yeni} onChange={(e) => setYeni(e.target.value)} />
      <Alan
        etiket="Yeni şifre (tekrar)"
        type="password"
        autoComplete="new-password"
        value={tekrar}
        onChange={(e) => setTekrar(e.target.value)}
      />
      {(yerelHata || degistir.error) && (
        <p role="alert" className="text-sm text-destructive">
          {yerelHata ?? hataMetni(degistir.error)}
        </p>
      )}
      <Button type="submit" disabled={degistir.isPending || !!yerelHata || !eski || !yeni || yeni !== tekrar}>
        <KeyRound aria-hidden /> Şifreyi kaydet
      </Button>
    </form>
  );
}

function SifreBelirleEkrani({ kullanici }: { kullanici: GirisKullanicisi }) {
  const cikis = useCikis();
  return (
    <Kart
      baslik={`Hoş geldiniz, ${kullanici.ad}`}
      aciklama="Size verilen geçici şifreyle giriş yaptınız. Devam etmek için kendi şifrenizi belirleyin."
    >
      <SifreFormu eskiEtiket="Geçici şifre" />
      <Button type="button" variant="ghost" size="sm" onClick={() => cikis.mutate()}>
        Çıkış yap
      </Button>
    </Kart>
  );
}

/**
 * Uygulamanın en dış katmanı. Sunucu girişi zorunlu tutuyorsa: oturum yoksa giriş ekranı, geçici şifreyle girilmişse şifre
 * belirleme ekranı, aksi halde uygulama (oturumdaki kullanıcı bağlamıyla). Girişi zorunlu tutmayan (ya da kimlik ucu olmayan
 * eski) sunucuda uygulama eskisi gibi açılır.
 */
export function GirisKapisi({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const ben = useBen();
  // Veri yokken yeniden sorgu durumu "bekliyor"a çeker: giriş ekranındayken bu olursa ekran sökülmesin (yazılan ad/şifre silinmesin).
  const girisEkraninda = useRef(false);
  const girissiz =
    (ben.error instanceof ApiHatasi && ben.error.durum === 401) ||
    (ben.isPending && ben.fetchStatus === "fetching" && girisEkraninda.current);
  girisEkraninda.current = girissiz;
  const girisZorunlu = girissiz || ben.data?.giris_zorunlu === true;
  // Çocuklar ilk isteklerini atmadan önce istemci doğru modda olmalı: render sırasında (idempotent) ayarlanır.
  girisModunuAyarla(girisZorunlu, () => void qc.invalidateQueries({ queryKey: ["kimlik", "ben"] }));

  if (ben.isPending && !girissiz) {
    return (
      <div role="status" className="flex min-h-screen items-center justify-center bg-background text-muted-foreground">
        Yükleniyor…
      </div>
    );
  }
  if (girissiz) return <GirisEkrani />;
  const kullanici = ben.data?.kullanici ?? null;
  if (girisZorunlu && kullanici?.sifre_degismeli) return <SifreBelirleEkrani kullanici={kullanici} />;
  return <OturumBaglami.Provider value={{ girisZorunlu, kullanici }}>{children}</OturumBaglami.Provider>;
}
