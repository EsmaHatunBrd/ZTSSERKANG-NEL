import { Fragment } from "react";
import type { HesapSatiri, Toplamlar, UretimBilgisi } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { apiMetni, D } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { GirdiHucresi } from "./GirdiHucresi";
import { parametreDegerGoster, parametreEtiketi } from "./parametreEtiketleri";
import { giderAnahtari, giderKaliciMi, GIDER_KALICI_DEGIL_NOTU, type TaslakYamasi } from "./Taslak";
import { MALZEME, sayiGoster } from "./yardimci";

const FINANSMAN = /^(faiz|stok_ay)\./;
const SENARYO_GENELI = "Senaryo geneli oran — tüm ürünleri etkiler";

interface GrupTanimi {
  ad: string;
  /** Bu başlık altında toplanan hesap grupları. */
  gruplar: string[];
  toplam: (t: Toplamlar) => string;
  not?: string;
}

// Excel I102-P119: Direkt işçilik, Genel üretim giderleri (GÜG), Gider toplamı, Toplam birim maliyet, Diğer giderler.
const GRUPLAR: GrupTanimi[] = [
  {
    ad: "Direkt işçilik",
    gruplar: ["direkt_iscilik"],
    toplam: (t) => t.direkt_iscilik,
  },
  {
    ad: "Genel üretim giderleri",
    gruplar: ["gug", "uretim_gideri"],
    toplam: (t) => t.gug,
  },
  {
    ad: "Diğer giderler",
    gruplar: ["diger", "pazarlama_yonetim"],
    toplam: (t) => t.diger,
    not: "Pazarlama ve yönetim giderleri dolum yapılan toplam adede göre dağıtılmıştır.",
  },
];

interface Props {
  satirlar: HesapSatiri[];
  toplamlar: Toplamlar;
  /** Verilirse (kayıtlı hesap görünümü) finansman parametreleri satır altında gösterilir; ekranda FinansmanTablosu kullanılır. */
  parametreler?: Record<string, string>;
  /** Hesabın üretim bilgisi: mal kabul (sınıf) ve elektrik (hat) oran anahtarını belirler. */
  uretim?: UretimBilgisi | null;
  /** `Taslak.giderOranlari` dilimi. */
  taslak?: Record<string, string>;
  /** Sunucudaki (kayıtlı) oranlar: değişen hücrenin eski değeri için. */
  sunucuOranlari?: Record<string, string>;
  /** Verilirse birim fiyat hücreleri düzenlenebilir; verilmezse (kayıtlı hesap) salt okunur. */
  onTaslak?: (yama: TaslakYamasi) => void;
}

interface SatirProps {
  s: HesapSatiri;
  anahtar: string | null;
  taslak?: Record<string, string>;
  sunucuOranlari?: Record<string, string>;
  onTaslak?: (yama: TaslakYamasi) => void;
}

function BirimFiyat({ s, anahtar, taslak, sunucuOranlari, onTaslak }: SatirProps) {
  if (!anahtar || !onTaslak) return <ParaHucresi deger={s.birim_fiyat} paraBirimi={s.doviz ?? ""} basamak={4} />;
  const yazildi = taslak?.[anahtar];
  const eski = sunucuOranlari?.[anahtar];
  const not = giderKaliciMi(anahtar) ? SENARYO_GENELI : `${SENARYO_GENELI} — ${GIDER_KALICI_DEGIL_NOTU}`;
  return (
    <GirdiHucresi
      etiket={`Birim fiyat — ${s.kalem}`}
      deger={yazildi !== undefined ? sayiGoster(yazildi, 6) : sayiGoster(s.birim_fiyat, 6)}
      className="w-28"
      degisti={yazildi !== undefined}
      title={yazildi !== undefined && eski !== undefined ? `${not}. Eski değer: ${sayiGoster(eski, 6)}` : not}
      onMetin={(m) => {
        const v = m.trim() === "" ? null : sayiApi(m);
        onTaslak({ giderOranlari: { [anahtar]: v ?? undefined } });
      }}
    />
  );
}

function Satir({ s, ...diger }: SatirProps) {
  return (
    <TableRow>
      <TableCell>{s.kalem}</TableCell>
      <TableCell className="text-right tabular-nums">{sayiGoster(s.miktar)}</TableCell>
      <TableCell>
        <YuzdeHucresi deger={s.fire_orani} />
      </TableCell>
      <TableCell className="text-right tabular-nums">{sayiGoster(s.brut_miktar)}</TableCell>
      <TableCell className="text-muted-foreground">{s.birim ?? "—"}</TableCell>
      <TableCell className="text-right">
        <BirimFiyat s={s} {...diger} />
      </TableCell>
      <TableCell className="text-muted-foreground">{s.doviz ?? "—"}</TableCell>
      <TableCell>
        <ParaHucresi deger={s.tutar} />
      </TableCell>
      <TableCell>
        <YuzdeHucresi deger={s.maliyet_yuzdesi} />
      </TableCell>
      <TableCell>
        <YuzdeHucresi deger={s.fiyat_yuzdesi} />
      </TableCell>
    </TableRow>
  );
}

function ToplamSatiri({ etiket, deger, vurgulu = false }: { etiket: string; deger: string | null; vurgulu?: boolean }) {
  return (
    <TableRow className={vurgulu ? "bg-muted/50 font-medium" : undefined}>
      <TableCell colSpan={7} className="text-right">
        {etiket}
      </TableCell>
      <TableCell>
        <ParaHucresi deger={deger} className={vurgulu ? "font-medium" : undefined} />
      </TableCell>
      <TableCell colSpan={2} />
    </TableRow>
  );
}

/** Malzeme dışı kalemler Excel'deki gibi üç grupta: ara toplamlar, gider toplamı, toplam birim maliyet. */
export function GiderKalemleri({ satirlar, toplamlar, parametreler, uretim, taslak, sunucuOranlari, onTaslak }: Props) {
  // Finansman satırı Toplamlar kartında ve finansman tablosunda gösterilir; gider gruplarına girmez.
  const giderler = satirlar.filter((s) => s.grup !== MALZEME && s.grup !== "finansman");
  const bilinen = new Set(GRUPLAR.flatMap((g) => g.gruplar));
  const grupSatirlari = (g: GrupTanimi, i: number) =>
    giderler.filter((s) => g.gruplar.includes(s.grup) || (i === GRUPLAR.length - 1 && !bilinen.has(s.grup)));
  const toplamBirimMaliyet = apiMetni(D(toplamlar.malzeme).plus(D(toplamlar.uretim_gideri)));
  const finansmanAnahtarlari = Object.keys(parametreler ?? {}).filter((a) => FINANSMAN.test(a));

  const grupGoster = (g: GrupTanimi, i: number) => {
    const satir = grupSatirlari(g, i);
    return (
      <Fragment key={g.ad}>
        <TableRow data-grup-basligi={g.ad}>
          <TableCell colSpan={10} className="bg-muted/30 font-medium">
            {g.ad}
          </TableCell>
        </TableRow>
        {satir.length === 0 ? (
          <TableRow>
            <TableCell colSpan={10} className="text-muted-foreground">
              Kalem yok
            </TableCell>
          </TableRow>
        ) : (
          satir.map((s, k) => (
            <Satir
              key={`${s.kalem}-${k}`}
              s={s}
              anahtar={giderAnahtari(s.kod, uretim)}
              taslak={taslak}
              sunucuOranlari={sunucuOranlari}
              onTaslak={onTaslak}
            />
          ))
        )}
        <ToplamSatiri etiket={`${g.ad} toplamı`} deger={g.toplam(toplamlar)} />
        {g.not && (
          <TableRow>
            <TableCell colSpan={10} className="text-xs text-muted-foreground">
              {g.not}
            </TableCell>
          </TableRow>
        )}
      </Fragment>
    );
  };

  return (
    <section aria-label="Gider kalemleri" className="flex flex-col gap-3">
      <h2 className="text-base font-semibold">Gider kalemleri</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Kalem</TableHead>
            <TableHead className="text-right">Miktar</TableHead>
            <TableHead className="text-right">Fire %</TableHead>
            <TableHead className="text-right">Brüt</TableHead>
            <TableHead>Birim</TableHead>
            <TableHead className="text-right">Birim fiyat</TableHead>
            <TableHead>Döviz</TableHead>
            <TableHead className="text-right">Tutar</TableHead>
            <TableHead className="text-right">Maliyet %</TableHead>
            <TableHead className="text-right">Satış %</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {giderler.length === 0 ? (
            <TableRow>
              <TableCell colSpan={10} className="text-center text-muted-foreground">
                Gider kalemi yok
              </TableCell>
            </TableRow>
          ) : (
            <>
              {grupGoster(GRUPLAR[0], 0)}
              {grupGoster(GRUPLAR[1], 1)}
              <ToplamSatiri etiket="Gider toplamı" deger={toplamlar.uretim_gideri} vurgulu />
              <ToplamSatiri etiket="Toplam birim maliyet" deger={toplamBirimMaliyet} vurgulu />
              {grupGoster(GRUPLAR[2], 2)}
            </>
          )}
        </TableBody>
      </Table>
      {parametreler && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border p-3" role="group" aria-label="Finansman">
          <span className="text-sm font-medium">Finansman</span>
          <ParaHucresi deger={toplamlar.finansman_tl} className="w-auto" />
          {finansmanAnahtarlari.map((a) => (
            <span key={a} className="text-sm text-muted-foreground">
              {parametreEtiketi(a)}: <span className="tabular-nums text-foreground">{parametreDegerGoster(a, parametreler[a])}</span>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
