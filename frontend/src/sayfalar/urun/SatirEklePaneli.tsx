import { useEffect, useId, useState } from "react";
import { Plus } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { malzemelerSorgusu, useMalzemeler } from "@/api/sorgular/malzemeler";
import { Girdi as Input } from "@/bilesenler/Girdi";
import { Button } from "@/bilesenler/ui/button";
import { sayiApi } from "@/yardimcilar/sayi";
import type { YeniSatir } from "./Taslak";
import { fireOraniMetni, fireYuzdeHatasi } from "./yardimci";

interface Props {
  senaryoId: number | null;
  /** Yeni satırın reçete seviyesi (reçetede seviye yoksa null). */
  seviye: number | null;
  onEkle: (satir: YeniSatir) => void;
}

interface Hatalar {
  kod?: string;
  miktar?: string;
  fire?: string;
}

const ARAMA_GECIKMESI_MS = 250;
const ONERI_BOYUTU = 8;
export const MALZEME_YOK_MESAJI = "Bu kodda malzeme yok; önce Veri Girişi › Yeni malzeme ile açın.";

/** Kod karşılaştırması: büyük/küçük harf ve baştaki/sondaki boşluk önemsiz (Türkçe kurallarıyla). */
function ayniKod(a: string, b: string) {
  return a.trim().toLocaleUpperCase("tr") === b.trim().toLocaleUpperCase("tr");
}

/**
 * Reçete tablosunun altındaki "Satır ekle" alanı: malzeme kodu ya da adıyla arayıp seçer, miktar/birim/fire girer.
 * Eklenen satır taslağa girer (kaydedilmez); canlı hesapta hemen görünür, Kaydet ile yeni reçete sürümüne yazılır.
 */
export function SatirEklePaneli(props: Props) {
  const [acik, setAcik] = useState(false);
  // Form (ve malzeme araması) yalnız açıkken bağlanır: kapalıyken sorgu istemcisi gerekmez.
  if (!acik)
    return (
      <div>
        <Button type="button" variant="outline" size="sm" onClick={() => setAcik(true)}>
          <Plus aria-hidden />
          Satır ekle
        </Button>
      </div>
    );
  return <SatirEkleFormu {...props} onKapat={() => setAcik(false)} />;
}

function SatirEkleFormu({ senaryoId, seviye, onEkle, onKapat }: Props & { onKapat: () => void }) {
  const [kod, setKod] = useState("");
  const [ad, setAd] = useState("");
  const [miktar, setMiktar] = useState("");
  const [birim, setBirim] = useState("");
  const [fire, setFire] = useState("");
  const [hatalar, setHatalar] = useState<Hatalar>({});
  const [arama, setArama] = useState("");
  const [secildi, setSecildi] = useState(false);
  const [denetleniyor, setDenetleniyor] = useState(false);
  const kimlik = useId();
  const istemci = useQueryClient();

  // Kod alanına yazılan metin kısa bir beklemeden sonra aranır (her tuşta istek gitmesin).
  useEffect(() => {
    const z = setTimeout(() => setArama(kod.trim()), ARAMA_GECIKMESI_MS);
    return () => clearTimeout(z);
  }, [kod]);
  const aramaAcik = !secildi && arama.length >= 2;
  const sonuclar = useMalzemeler(aramaAcik ? senaryoId : null, { arama, boyut: ONERI_BOYUTU });
  const adaylar = aramaAcik ? (sonuclar.data?.kayitlar ?? []) : [];

  function sec(m: { kod: string; ad?: string | null; birim?: string | null }) {
    setKod(m.kod);
    setAd(m.ad ?? "");
    if (m.birim) setBirim(m.birim);
    setSecildi(true);
    setHatalar((h) => ({ ...h, kod: undefined }));
  }

  /**
   * Öneriden seçilmemiş kodu sistemde arar: tam kod eşleşmesi varsa seçilmiş sayılır (ad/birim boşsa doldurulur),
   * yoksa satır eklenmez. Var olmayan kod 0 TL'lik sahte bir satır olarak reçeteye girmesin.
   */
  async function kodDogrula(): Promise<{ kod: string; ad: string; birim: string } | string> {
    if (senaryoId == null) return "Öneri listesinden bir malzeme seçin.";
    try {
      const sonuc = await istemci.fetchQuery(malzemelerSorgusu(senaryoId, { arama: kod.trim(), boyut: ONERI_BOYUTU }));
      const m = sonuc.kayitlar.find((k) => ayniKod(k.kod, kod));
      if (!m) return MALZEME_YOK_MESAJI;
      return { kod: m.kod, ad: ad.trim() || (m.ad ?? ""), birim: birim.trim() || (m.birim ?? "") };
    } catch {
      return "Malzeme denetlenemedi; bağlantıyı kontrol edip tekrar deneyin.";
    }
  }

  async function ekle(e: React.FormEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (denetleniyor) return;
    const h: Hatalar = {};
    if (!kod.trim()) h.kod = "Malzeme kodu zorunlu";
    const m = miktar.trim() === "" ? null : sayiApi(miktar);
    if (miktar.trim() === "") h.miktar = "Miktar zorunlu";
    else if (m === null) h.miktar = "Miktar sayı olmalı (0 ya da büyük)";
    if (fire.trim() !== "") {
      const fh = fireYuzdeHatasi(fire);
      if (fh) h.fire = fh;
    }
    let malzeme = { kod: kod.trim(), ad: ad.trim(), birim: birim.trim() };
    if (!h.kod && !secildi) {
      setDenetleniyor(true);
      const d = await kodDogrula();
      setDenetleniyor(false);
      if (typeof d === "string") h.kod = d;
      else {
        malzeme = d;
        sec(d);
      }
    }
    setHatalar(h);
    if (h.kod || h.miktar || h.fire || m === null) return;
    const satir: YeniSatir = { malzeme_kodu: malzeme.kod, ad: malzeme.ad, miktar: m, birim: malzeme.birim || null, seviye };
    const oran = fire.trim() === "" ? null : fireOraniMetni(fire);
    if (oran !== null) satir.fire = oran;
    onEkle(satir);
    onKapat();
  }

  const hataId = (alan: string) => `${kimlik}-${alan}-hata`;
  return (
    <form
      noValidate
      onSubmit={ekle}
      aria-label="Reçeteye satır ekle"
      className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-sm"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onKapat();
        }
      }}
    >
      <p className="text-sm text-muted-foreground">
        Yeni satır reçetenin sonuna eklenir; hesap hemen güncellenir, <span className="font-medium text-foreground">Kaydet</span> ile yeni
        reçete sürümü açılır.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(12rem,1.2fr)_minmax(12rem,1.5fr)_8rem_6rem_7rem]">
        <div className="relative flex min-w-0 flex-col gap-1">
          <label htmlFor={`${kimlik}-kod`} className="text-xs text-muted-foreground">
            Malzeme kodu ya da adı
          </label>
          <Input
            id={`${kimlik}-kod`}
            autoFocus
            autoComplete="off"
            value={kod}
            aria-invalid={!!hatalar.kod}
            aria-describedby={hatalar.kod ? hataId("kod") : undefined}
            onChange={(e) => {
              setKod(e.target.value);
              setSecildi(false);
              if (hatalar.kod) setHatalar((h) => ({ ...h, kod: undefined }));
            }}
          />
          {hatalar.kod && (
            <p id={hataId("kod")} className="text-xs text-destructive">
              {hatalar.kod}
            </p>
          )}
          {aramaAcik && (
            <ul
              aria-label="Malzeme önerileri"
              className="absolute top-full right-0 left-0 z-30 mt-1 max-h-64 overflow-auto rounded-lg border bg-popover p-1 text-sm text-popover-foreground shadow-lg"
            >
              {sonuclar.isPending ? (
                <li role="status" className="px-2 py-1.5 text-muted-foreground">
                  Aranıyor…
                </li>
              ) : sonuclar.isError ? (
                <li role="alert" className="px-2 py-1.5 text-destructive">
                  Malzemeler getirilemedi; biraz sonra tekrar deneyin.
                </li>
              ) : adaylar.length === 0 ? (
                <li className="px-2 py-1.5 text-muted-foreground">Eşleşen malzeme yok; önce Veri Girişi › Yeni malzeme ile açın.</li>
              ) : (
                adaylar.map((m) => (
                  <li key={m.kod}>
                    <button
                      type="button"
                      onClick={() => sec(m)}
                      className="flex w-full items-baseline gap-2 rounded-md px-2 py-1.5 text-left hover:bg-accent focus-visible:bg-accent focus-visible:outline-none"
                    >
                      <span className="shrink-0 text-xs text-muted-foreground tabular-nums">{m.kod}</span>
                      <span className="truncate">{m.ad ?? "—"}</span>
                      {m.birim && <span className="ml-auto shrink-0 text-xs text-muted-foreground">{m.birim}</span>}
                    </button>
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <label htmlFor={`${kimlik}-ad`} className="text-xs text-muted-foreground">
            Cinsi (ad)
          </label>
          <Input id={`${kimlik}-ad`} value={ad} onChange={(e) => setAd(e.target.value)} />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <label htmlFor={`${kimlik}-miktar`} className="text-xs text-muted-foreground">
            Miktar
          </label>
          <Input
            id={`${kimlik}-miktar`}
            inputMode="decimal"
            className="text-right tabular-nums"
            value={miktar}
            aria-invalid={!!hatalar.miktar}
            aria-describedby={hatalar.miktar ? hataId("miktar") : undefined}
            onChange={(e) => setMiktar(e.target.value)}
          />
          {hatalar.miktar && (
            <p id={hataId("miktar")} className="text-xs text-destructive">
              {hatalar.miktar}
            </p>
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <label htmlFor={`${kimlik}-birim`} className="text-xs text-muted-foreground">
            Birim
          </label>
          <Input id={`${kimlik}-birim`} value={birim} onChange={(e) => setBirim(e.target.value)} />
        </div>
        <div className="flex min-w-0 flex-col gap-1">
          <label htmlFor={`${kimlik}-fire`} className="text-xs text-muted-foreground">
            Fire % (boşsa kural)
          </label>
          <Input
            id={`${kimlik}-fire`}
            inputMode="decimal"
            className="text-right tabular-nums"
            value={fire}
            aria-invalid={!!hatalar.fire}
            aria-describedby={hatalar.fire ? hataId("fire") : undefined}
            onChange={(e) => setFire(e.target.value)}
          />
          {hatalar.fire && (
            <p id={hataId("fire")} className="text-xs text-destructive">
              {hatalar.fire}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={denetleniyor}>
          {denetleniyor ? "Denetleniyor…" : "Satırı ekle"}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onKapat}>
          Vazgeç
        </Button>
      </div>
    </form>
  );
}
