import { useRef, useState, type ReactNode } from "react";
import { ApiHatasi } from "@/api/istemci";
import { useFiyatEkle } from "@/api/sorgular/malzemeler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { D, paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";

type FiyatEkle = ReturnType<typeof useFiyatEkle>;
type Degiskenler = Parameters<FiyatEkle["mutate"]>[0];
type Secenekler = Parameters<FiyatEkle["mutate"]>[1];

/** Sunucunun "fiyat eşikten fazla değişiyor" yanıtı (422, kod=fiyat_sapma) mı? */
export function sapmaMi(e: unknown): e is ApiHatasi {
  return e instanceof ApiHatasi && e.kod === "fiyat_sapma";
}

interface Sapma {
  eski_fiyat: string;
  yeni_fiyat: string;
  para_birimi: string;
  oran: string;
  esik: string;
}

/**
 * useFiyatEkle + eşik onayı: yeni fiyat öncekinden eşikten (TL %15 / döviz %10, Parametreler'den değişir) fazla farklıysa sunucu
 * kaydetmez; kullanıcıya önceki ve yeni fiyat gösterilir, onaylarsa aynı istek `onay: true` ile ve aynı onSuccess ile yeniden gider.
 * Kullanan yer `onayDiyalogu`'nu çizer; `error` sapma yanıtını içermez (form kendi hatası gibi göstermesin).
 */
export function useOnayliFiyatEkle() {
  const ekle = useFiyatEkle();
  const son = useRef<{ v: Degiskenler; o: Secenekler } | null>(null);
  const [kapali, setKapali] = useState(false);

  function mutate(v: Degiskenler, o?: Secenekler) {
    son.current = { v, o };
    setKapali(false);
    ekle.mutate(v, o);
  }

  const sapma = sapmaMi(ekle.error) && !kapali && son.current ? (ekle.error.alanlar as unknown as Sapma) : null;
  let onayDiyalogu: ReactNode = null;
  if (sapma && son.current) {
    const { v, o } = son.current;
    const pb = sapma.para_birimi;
    onayDiyalogu = (
      <OnayDiyalogu
        baslik="Fiyat büyük ölçüde değişiyor"
        onayMetni="Yine de kaydet"
        bekliyor={ekle.isPending}
        onOnayla={() => ekle.mutate({ ...v, govde: { ...v.govde, onay: true } }, o)}
        onVazgec={() => setKapali(true)}
      >
        <p>
          {v.kod}: {paraBicimle(sapma.eski_fiyat, pb, 4)} → {paraBicimle(sapma.yeni_fiyat, pb, 4)} ({D(sapma.oran).isNegative() ? "" : "+"}
          {yuzdeBicimle(sapma.oran)}).
        </p>
        <p className="text-muted-foreground">
          Bu çalışmada {pb === "TL" ? "TL" : "dövizli"} fiyatlar için uyarı eşiği {yuzdeBicimle(sapma.esik, 0)}. Yanlış yazılmadıysa
          kaydedin.
        </p>
      </OnayDiyalogu>
    );
  }

  return {
    mutate,
    isPending: ekle.isPending,
    error: sapmaMi(ekle.error) ? null : ekle.error,
    reset: () => {
      setKapali(false);
      ekle.reset();
    },
    onayDiyalogu,
  };
}
