import { useId, useState, type ChangeEvent, type FormEvent } from "react";
import { Boxes } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useFiyatEkle } from "@/api/sorgular/malzemeler";
import { useMalzemeKartiOlustur } from "@/api/sorgular/malzemeKarti";
import { Button } from "@/bilesenler/ui/button";
import { Girdi } from "@/bilesenler/Girdi";
import { sayiApi } from "@/yardimcilar/sayi";
import { bugunIso } from "@/yardimcilar/tarih";
import { Alan, Kart, SELECT } from "./ortak";

/** Malzeme tipleri (Canias stok kartı türleri; fire varsayılanları ve gider/maliyet grupları bu adlara bağlıdır). */
const TIPLER = [
  "0001-Hammadde",
  "0008-Ambalaj Malzeme",
  "0017-Yardımcı Malzeme",
  "0018-Sarf Malzemesi",
  "0004-Ticari Malzeme",
  "0002-Üretim Yarı Mamul",
  "0003-Ürün",
  "0015-Yarı Mamül",
];
const BIRIMLER = ["AD", "KG", "LT", "GR", "MT", "KUTU"];
const PARA_BIRIMLERI = ["TL", "USD", "EUR", "GBP", "CHF", "RUB", "ZAR"];

const bos = () => ({ kod: "", ad: "", tip: TIPLER[1], birim: "AD", para_birimi: "TL", zs: "S", fiyat: "", tarih: bugunIso(), neden: "" });
type Form = ReturnType<typeof bos>;

/**
 * Yeni malzeme kartı (sıfırdan kullanım): kart açılır, istenirse aynı adımda ilk fiyat bu çalışmaya yazılır. Excel'den yükleme
 * yapılmayan kurulumda malzeme açmanın tek ekranı burasıdır; sonraki fiyat güncellemeleri "Malzeme fiyatı" kartından yapılır.
 */
export function YeniMalzemeKarti({
  senaryoId,
  kilitli = false,
  onMesaj,
}: {
  senaryoId: number;
  kilitli?: boolean;
  onMesaj: (m: string) => void;
}) {
  const id = useId();
  const olustur = useMalzemeKartiOlustur();
  const fiyatEkle = useFiyatEkle();
  const [f, setF] = useState<Form>(bos);
  const [hata, setHata] = useState<string | null>(null);
  const alan = (k: keyof Form) => ({
    value: f[k],
    onChange: (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((o) => ({ ...o, [k]: e.target.value })),
  });
  const fiyatVar = f.fiyat.trim() !== "";
  const yukleniyor = olustur.isPending || fiyatEkle.isPending;

  function gonder(e: FormEvent) {
    e.preventDefault();
    setHata(null);
    const kod = f.kod.trim();
    if (!kod || /[\s/?#]/.test(kod)) return setHata("Kod zorunlu; boşluk ya da / ? # içeremez");
    if (!f.ad.trim()) return setHata("Ad zorunlu");
    const fiyat = fiyatVar ? sayiApi(f.fiyat) : null;
    if (fiyatVar && fiyat === null) return setHata("Fiyat geçerli bir sayı olmalı");
    if (fiyatVar && !f.neden.trim()) return setHata("Fiyat girildiyse neden zorunlu");
    olustur.mutate(
      { senaryo: senaryoId, govde: { kod, ad: f.ad.trim(), tip: f.tip, birim: f.birim, para_birimi: f.para_birimi, zs: f.zs } },
      {
        onSuccess: () => {
          if (fiyat === null) {
            onMesaj(`${kod} malzeme kartı açıldı; fiyatı girilene kadar 0 TL sayılır.`);
            setF(bos());
            return;
          }
          fiyatEkle.mutate(
            {
              kod,
              senaryo: senaryoId,
              govde: { fiyat, gecerlilik_basi: f.tarih, neden: f.neden.trim(), para_birimi: f.para_birimi, onay: false },
            },
            {
              onSuccess: () => {
                onMesaj(`${kod} malzeme kartı açıldı ve ilk fiyatı girildi.`);
                setF(bos());
              },
              onError: (er) => setHata(`Kart açıldı ama fiyat yazılamadı: ${hataMetni(er)}. Fiyatı "Malzeme fiyatı" kartından girin.`),
            },
          );
        },
        onError: (er) => setHata(hataMetni(er)),
      },
    );
  }

  return (
    <Kart
      baslik="Yeni malzeme"
      aciklama="Malzeme kartını açın; isterseniz ilk fiyatı da girin. Fiyatı olmayan malzeme 0 TL sayılır ve Veri Kontrolü'nde uyarı verir."
      simge={<Boxes />}
    >
      <form noValidate className="flex flex-col gap-3" aria-label="Yeni malzeme" onSubmit={gonder}>
        <div className="grid grid-cols-2 gap-3">
          <Alan etiket="Malzeme kodu" htmlFor={`${id}-kod`}>
            <Girdi id={`${id}-kod`} placeholder="Canias stok kodu" disabled={kilitli} {...alan("kod")} />
          </Alan>
          <Alan etiket="Ad" htmlFor={`${id}-ad`}>
            <Girdi id={`${id}-ad`} placeholder="örn. Kavanoz 720 ml" disabled={kilitli} {...alan("ad")} />
          </Alan>
          <Alan etiket="Tip" htmlFor={`${id}-tip`}>
            <select id={`${id}-tip`} className={SELECT} disabled={kilitli} {...alan("tip")}>
              {TIPLER.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </Alan>
          <Alan etiket="Birim" htmlFor={`${id}-birim`}>
            <select id={`${id}-birim`} className={SELECT} disabled={kilitli} {...alan("birim")}>
              {BIRIMLER.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </Alan>
          <Alan etiket="Para birimi" htmlFor={`${id}-para`}>
            <select id={`${id}-para`} className={SELECT} disabled={kilitli} {...alan("para_birimi")}>
              {PARA_BIRIMLERI.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </Alan>
          <Alan etiket="Kaynak" htmlFor={`${id}-zs`}>
            <select id={`${id}-zs`} className={SELECT} disabled={kilitli} {...alan("zs")}>
              <option value="S">Satın alma (TL'ye enflasyon, dövize kur)</option>
              <option value="Z">Ziraat (enflasyon ve kur yok)</option>
            </select>
          </Alan>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Alan etiket="İlk fiyat (isteğe bağlı)" htmlFor={`${id}-fiyat`}>
            <Girdi id={`${id}-fiyat`} inputMode="decimal" className="text-right tabular-nums" disabled={kilitli} {...alan("fiyat")} />
          </Alan>
          <Alan etiket="Geçerlilik tarihi" htmlFor={`${id}-tarih`}>
            <Girdi id={`${id}-tarih`} type="date" disabled={kilitli || !fiyatVar} {...alan("tarih")} />
          </Alan>
          <Alan etiket="Neden" htmlFor={`${id}-neden`}>
            <Girdi id={`${id}-neden`} placeholder="fiyat girildiyse zorunlu" disabled={kilitli || !fiyatVar} {...alan("neden")} />
          </Alan>
        </div>
        {hata && (
          <p role="alert" className="text-sm text-destructive">
            {hata}
          </p>
        )}
        <div>
          <Button type="submit" size="sm" disabled={kilitli || yukleniyor}>
            {yukleniyor ? "Kaydediliyor…" : "Malzemeyi aç"}
          </Button>
        </div>
      </form>
    </Kart>
  );
}
