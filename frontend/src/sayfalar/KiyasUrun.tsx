import type { ReactNode } from "react";
import { ArrowLeft, TriangleAlert } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useKiyasUrun } from "@/api/sorgular/kiyas";
import type { BgAlanlar, BgAyristirma, BgDeger, BgReceteSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";
import { D, paraBicimle } from "@/yardimcilar/para";
import { degerMetni } from "./ayarlar/ParametreDiyalogu";
import { FarkYuzdesi } from "./kiyas/FarkYuzdesi";

const TOPLAM_ALANLARI: { alan: keyof BgAlanlar; etiket: string; pb?: string; basamak?: number }[] = [
  { alan: "recete_maliyeti", etiket: "Reçete maliyeti" },
  { alan: "gug", etiket: "Üretim giderleri (GÜG)" },
  { alan: "faaliyet", etiket: "Faaliyet giderleri" },
  { alan: "finans", etiket: "Finansman" },
  { alan: "maliyet_tl", etiket: "Birim maliyet TL (finansman dahil)" },
  { alan: "maliyet_usd", etiket: "Birim maliyet USD", pb: "USD", basamak: 3 },
  { alan: "satis_tl", etiket: "Satış fiyatı TL" },
  { alan: "satis_usd", etiket: "Satış fiyatı USD", pb: "USD", basamak: 3 },
];

function Bolum({ baslik, children, aciklama }: { baslik: string; children: ReactNode; aciklama?: string }) {
  return (
    <section aria-label={baslik} className="flex flex-col gap-2 rounded-xl border bg-card p-3 shadow-xs sm:p-4">
      <h2 className="text-base font-semibold">{baslik}</h2>
      {aciklama && <p className="text-sm text-muted-foreground">{aciklama}</p>}
      <div className="overflow-x-auto">{children}</div>
    </section>
  );
}

const sag = "text-right";

function DegerSatiri({
  etiket,
  v,
  pb = "TL",
  basamak = 2,
  kalin,
}: {
  etiket: string;
  v: BgDeger;
  pb?: string;
  basamak?: number;
  kalin?: boolean;
}) {
  return (
    <TableRow className={cn(kalin && "font-semibold")}>
      <TableCell>{etiket}</TableCell>
      <TableCell className={sag}>
        <ParaHucresi deger={v.a} paraBirimi={pb} basamak={basamak} />
      </TableCell>
      <TableCell className={sag}>
        <ParaHucresi deger={v.b} paraBirimi={pb} basamak={basamak} />
      </TableCell>
      <TableCell className={sag}>
        <ParaHucresi deger={v.fark} paraBirimi={pb} basamak={basamak} />
      </TableCell>
      <TableCell className={sag}>
        <FarkYuzdesi deger={v.fark_yuzde} />
      </TableCell>
    </TableRow>
  );
}

/** Sapma kaynağı: yatay çubuklar (sıfırdan sağa artış, sola azalış), değer metni her zaman yanında. */
function Ayristirma({ adimlar, toplam }: { adimlar: BgAyristirma[]; toplam: string | null }) {
  const enBuyuk = adimlar.reduce((m, x) => (D(x.fark).abs().greaterThan(m) ? D(x.fark).abs() : m), D(0));
  return (
    <div className="flex flex-col gap-1.5">
      <ul className="flex flex-col gap-1.5">
        {adimlar.map((x) => {
          const d = D(x.fark);
          const oran = enBuyuk.isZero() ? 0 : d.abs().div(enBuyuk).times(50).toNumber();
          return (
            <li key={x.kaynak} className="grid grid-cols-[minmax(10rem,16rem)_minmax(0,1fr)_7rem] items-center gap-3 text-sm">
              <span>{x.etiket}</span>
              <span className="relative h-4" aria-hidden>
                <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
                {oran > 0 && (
                  <span
                    className={cn("absolute inset-y-0.5 rounded-sm", d.isNegative() ? "right-1/2 bg-chart-2" : "left-1/2 bg-chart-1")}
                    style={{ width: `${oran}%` }}
                  />
                )}
              </span>
              <ParaHucresi deger={x.fark} />
            </li>
          );
        })}
      </ul>
      <div className="grid grid-cols-[minmax(10rem,16rem)_minmax(0,1fr)_7rem] gap-3 border-t pt-1.5 text-sm font-semibold">
        <span>Toplam fark</span>
        <span />
        <ParaHucresi deger={toplam} />
      </div>
    </div>
  );
}

const RECETE_ALANLARI = [
  { alan: "miktar", etiket: "Miktar", basamak: 4 },
  { alan: "fire", etiket: "Fire", basamak: 4 },
  { alan: "birim_fiyat", etiket: "Birim fiyat", basamak: 4 },
  { alan: "tutar", etiket: "Tutar", basamak: 4 },
] as const;

function ReceteHucresi({ s, alan, basamak }: { s: BgReceteSatiri; alan: (typeof RECETE_ALANLARI)[number]["alan"]; basamak: number }) {
  const a = s.a?.[alan] ?? null;
  const b = s.b?.[alan] ?? null;
  const degisti = s.degisen.includes(alan);
  return (
    <TableCell className={cn(sag, degisti && "bg-sari/60")}>
      <span className="flex flex-col items-end leading-tight">
        <ParaHucresi deger={b} paraBirimi="" basamak={basamak} />
        {degisti && (
          <span className="text-xs text-muted-foreground tabular-nums">bütçe {a === null ? "—" : paraBicimle(a, "", basamak)}</span>
        )}
      </span>
    </TableCell>
  );
}

const DURUM: Record<string, string> = { yalniz_a: "yalnız bütçede", yalniz_b: "yalnız gerçekleşende" };

export default function KiyasUrun() {
  const { kod = "" } = useParams();
  const [params] = useSearchParams();
  const a = Number(params.get("a")) || null;
  const b = Number(params.get("b")) || null;
  const q = useKiyasUrun(kod, a, b);
  const geri = `/butce-gerceklesen?${params.toString()}`;
  const d = q.data;

  return (
    <section className="flex flex-col gap-4 p-4">
      <Link to={geri} className="inline-flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" aria-hidden />
        Bütçe vs Gerçekleşen
      </Link>
      <SayfaBasligi
        baslik={d ? `${d.ad}` : kod}
        altBaslik={d ? `${d.kod} · A: ${d.a.ad} (${d.a.sezon}) · B: ${d.b.ad} (${d.b.sezon})` : undefined}
      />
      {q.error ? (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/40 px-3 py-2 text-sm text-destructive">
          <TriangleAlert className="size-4" aria-hidden />
          {hataMetni(q.error as ApiHatasi)}
        </div>
      ) : !d ? (
        <div role="status" className="text-sm text-muted-foreground">
          Yükleniyor…
        </div>
      ) : (
        <>
          <Bolum
            baslik="Sapmanın kaynağı"
            aciklama="Bütçeden başlanıp her adımda bir blok gerçekleşenle değiştirilir; adımın etkisi birim maliyet TL'deki değişimdir. Toplam, gerçek farka eşittir."
          >
            <Ayristirma adimlar={d.ayristirma} toplam={d.toplam_fark} />
          </Bolum>

          <Bolum baslik="Toplamlar">
            <Table className="text-[13px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Kalem</TableHead>
                  <TableHead className={sag}>Bütçe</TableHead>
                  <TableHead className={sag}>Gerçekleşen</TableHead>
                  <TableHead className={sag}>Fark</TableHead>
                  <TableHead className={sag}>Fark %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {TOPLAM_ALANLARI.map((t) => (
                  <DegerSatiri
                    key={t.alan}
                    etiket={t.etiket}
                    v={d.alanlar[t.alan]}
                    pb={t.pb}
                    basamak={t.basamak}
                    kalin={t.alan === "maliyet_tl"}
                  />
                ))}
              </TableBody>
            </Table>
          </Bolum>

          <Bolum baslik="Reçete" aciklama="Hücrede gerçekleşen değer; değişen hücre vurgulu ve altında bütçe değeri.">
            <Table className="text-[13px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Kod</TableHead>
                  <TableHead>Malzeme</TableHead>
                  {RECETE_ALANLARI.map((x) => (
                    <TableHead key={x.alan} className={sag}>
                      {x.etiket}
                    </TableHead>
                  ))}
                  <TableHead className={sag}>Tutar farkı</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.recete.map((s, i) => (
                  <TableRow key={`${s.kod}-${i}`} className={cn(s.durum !== "iki" && "bg-muted/50")}>
                    <TableCell className="text-xs whitespace-nowrap">{s.kod}</TableCell>
                    <TableCell className="min-w-48">
                      {s.kalem}
                      {s.durum !== "iki" && <span className="ml-2 text-xs font-medium text-muted-foreground">({DURUM[s.durum]})</span>}
                    </TableCell>
                    {RECETE_ALANLARI.map((x) => (
                      <ReceteHucresi key={x.alan} s={s} alan={x.alan} basamak={x.basamak} />
                    ))}
                    <TableCell className={sag}>
                      <ParaHucresi deger={s.fark_tutar} basamak={4} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Bolum>

          <Bolum baslik="Giderler">
            <Table className="text-[13px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Kalem</TableHead>
                  <TableHead className={sag}>Bütçe</TableHead>
                  <TableHead className={sag}>Gerçekleşen</TableHead>
                  <TableHead className={sag}>Fark</TableHead>
                  <TableHead className={sag}>Fark %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.giderler.map((g) => (
                  <DegerSatiri key={g.kod} etiket={g.kalem} v={g} basamak={4} />
                ))}
              </TableBody>
            </Table>
          </Bolum>

          <div className="grid gap-4 lg:grid-cols-2">
            <Bolum baslik="Üretim bilgileri">
              <KarsiTablo satirlar={d.uretim.map((u) => ({ anahtar: u.etiket, a: u.a, b: u.b, degisti: u.degisti }))} />
            </Bolum>
            <Bolum baslik="Parametreler">
              <KarsiTablo satirlar={d.parametreler} />
            </Bolum>
          </div>
        </>
      )}
    </section>
  );
}

function KarsiTablo({ satirlar }: { satirlar: { anahtar: string; a: string | null; b: string | null; degisti: boolean }[] }) {
  return (
    <Table className="text-[13px]">
      <TableHeader>
        <TableRow>
          <TableHead>Alan</TableHead>
          <TableHead className={sag}>Bütçe</TableHead>
          <TableHead className={sag}>Gerçekleşen</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {satirlar.map((s) => (
          <TableRow key={s.anahtar} className={cn(s.degisti && "bg-sari/60 font-medium")}>
            <TableCell>{s.anahtar}</TableCell>
            <TableCell className={cn(sag, "tabular-nums")}>{s.a === null ? "—" : degerMetni(s.a, null)}</TableCell>
            <TableCell className={cn(sag, "tabular-nums")}>{s.b === null ? "—" : degerMetni(s.b, null)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
