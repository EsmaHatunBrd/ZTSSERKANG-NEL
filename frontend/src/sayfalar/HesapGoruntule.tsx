import { Link, useParams } from "react-router-dom";
import { hataMetni } from "@/api/istemci";
import { useHesap } from "@/api/sorgular/hesaplar";
import { Badge } from "@/bilesenler/ui/badge";
import { goster } from "@/yardimcilar/tarih";
import { GiderKalemleri } from "./urun/GiderKalemleri";
import { ReceteTablosu } from "./urun/ReceteTablosu";
import { ToplamlarKarti } from "./urun/ToplamlarKarti";
import { kayitliOverrideListesi } from "./urun/Taslak";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";

const BOS_TASLAK = {};
const YAPMA = () => undefined;

/** Kayıtlı bir hesabın salt okunur görünümü (GET /hesaplar/:id -> `gorunum`): giriş alanı yok. */
export default function HesapGoruntule() {
  const { id } = useParams();
  const sayi = Number(id);
  const hesapNo = Number.isInteger(sayi) && sayi > 0 ? sayi : null;
  const sorgu = useHesap(hesapNo);

  if (hesapNo === null) {
    return (
      <section className="p-4">
        <SayfaBasligi baslik="Kayıtlı hesap" />
        <p role="alert" className="mt-2 text-destructive">Geçersiz hesap numarası</p>
      </section>
    );
  }
  if (sorgu.isPending) {
    return (
      <p role="status" className="p-4 text-muted-foreground">
        Hesap yükleniyor…
      </p>
    );
  }
  if (sorgu.error) {
    return (
      <section className="p-4">
        <SayfaBasligi baslik={`Kayıtlı hesap #${hesapNo}`} />
        <p role="alert" className="mt-2 text-destructive">
          {hataMetni(sorgu.error)}
        </p>
      </section>
    );
  }

  const h = sorgu.data;
  const g = h.gorunum;
  const degisiklikler = kayitliOverrideListesi((h.girdi_snapshot as { override?: unknown }).override);
  const urunBaglantisi = `/urunler/${encodeURIComponent(g.urun_kodu)}?senaryo=${h.senaryo_id}`;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <SayfaBasligi baslik={`Kayıtlı hesap #${h.id} · ${goster(h.hesap_tarihi)} · ${h.olusturan}`} />
        <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant="outline">{g.urun_kodu}</Badge>
          <span>Bu hesap kaydedildiği andaki değerleri gösterir; salt okunurdur.</span>
          <Link to={urunBaglantisi} className="text-primary underline-offset-4 hover:underline">
            Ürün ekranına dön
          </Link>
        </p>
      </header>

      {g.uyarilar.length > 0 && (
        <ul aria-label="Hesap uyarıları" className="flex flex-col gap-1 rounded-lg border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900 dark:border-yellow-700 dark:bg-yellow-950/40 dark:text-yellow-200">
          {g.uyarilar.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}

      {degisiklikler.length > 0 && (
        <section aria-label="Kayıt anındaki değişiklikler" className="flex flex-col gap-2 rounded-lg border border-primary/40 bg-primary/5 p-3 text-sm">
          <h2 className="font-medium">Kayıt anındaki değişiklikler</h2>
          <p className="text-xs text-muted-foreground">Bu hesap, aşağıdaki değerlerle (kalıcı olarak yazılmadan) hesaplanmıştır.</p>
          <ul className="flex flex-col gap-1">
            {degisiklikler.map((d, i) => (
              <li key={`${d.etiket}-${i}`} className="flex flex-wrap gap-x-2">
                <span className="text-muted-foreground">{d.etiket}</span>
                <span className="font-medium tabular-nums">{d.deger}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-label="Reçete" className="flex flex-col gap-3">
        <h2 className="text-base font-semibold">Reçete</h2>
        <ReceteTablosu
          satirlar={g.satirlar}
          recete={[]}
          uyarilar={g.uyarilar}
          yukleniyor={false}
          hata={null}
          taslak={BOS_TASLAK}
          onTaslak={YAPMA}
          saltOkunur
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <GiderKalemleri
          satirlar={g.satirlar}
          toplamlar={g.toplamlar}
          parametreler={g.kullanilan_parametreler}
          uretim={g.uretim}
        />
        <ToplamlarKarti
          toplamlar={g.toplamlar}
          toplamlarFiresiz={g.toplamlar_firesiz ?? null}
          fiyatlar={g.fiyatlar}
          fiyatlarFiresiz={g.fiyatlar_firesiz ?? null}
          notlar={g.notlar}
          kurlar={g.parametreler?.kurlar ?? null}
        />
      </div>
    </div>
  );
}
