import { useId, useMemo, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { CartesianGrid, Label, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { DashboardSatiri } from "@/api/tipler";
import { BOLGE_ADI, FIYAT_KAYNAGI_ADI, gecenYilVar, karlilikHaritasi, type FiyatKaynagi, type KarlilikNoktasi } from "./karlilik";

// Tek seri: marka paletinin ilk adımı (açık/koyu temada ayrı token değeri). Bölge bir durumdur; renkle değil konumla ve tabloyla anlatılır.
const NOKTA_RENGI = "var(--chart-1)";
const OLCU = { width: 640, height: 320 };
const EKSEN = { fontSize: 12, fill: "var(--muted-foreground)" };
const SELECT =
  "h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50";
const tamSayi = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 });
const adetEkseni = (v: number) => tamSayi.format(v);
const yuzdeEkseni = (v: number) => `%${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 0 }).format(v)}`;

function Ipucu({ active, payload }: { active?: boolean; payload?: { payload: KarlilikNoktasi }[] }) {
  const n = payload?.[0]?.payload;
  if (!active || !n) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md">
      <div className="font-medium">{n.ad}</div>
      <div className="font-mono text-xs text-muted-foreground">{n.kod}</div>
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-xs">
        <dt className="text-muted-foreground">Üretim adedi</dt>
        <dd className="text-right tabular-nums">{n.adetMetni}</dd>
        <dt className="text-muted-foreground">Kâr oranı</dt>
        <dd className="text-right tabular-nums">{n.karMetni}</dd>
        <dt className="text-muted-foreground">Satış</dt>
        <dd className="text-right tabular-nums">{n.satisMetni}</dd>
        <dt className="text-muted-foreground">Maliyet</dt>
        <dd className="text-right tabular-nums">{n.maliyetMetni}</dd>
      </dl>
      <div className="mt-1 text-xs">{BOLGE_ADI[n.bolge]}</div>
    </div>
  );
}

interface Props {
  satirlar: DashboardSatiri[];
  /** `satis_kar` parametresi (0,2 gibi oran); yoksa eşik medyan. */
  hedefKarOrani: string | null | undefined;
  senaryoId: number;
}

/**
 * Kârlılık haritası: x = üretim adedi (log ölçek; 400 ile 1.000.000 aynı eksende okunur), y = kâr oranı %.
 * Eşik çizgileri dört bölge kurar; "çok satan, marjı zayıf" bölgesi altta tablo olarak da listelenir (fiyat kararı oradan çıkar).
 * Satış fiyatı kaynağı seçilebilir: Satış Geçmişi yüklüyse varsayılan geçen yılın gerçek fiyatıdır; bütçe satışı maliyet × hedef kâr
 * olduğundan o kaynakta tüm ürünler eşiktedir (düz harita; not gösterilir).
 */
export function KarlilikHaritasi({ satirlar, hedefKarOrani, senaryoId }: Props) {
  const id = useId();
  const gecenYil = gecenYilVar(satirlar);
  const [kaynak, setKaynak] = useState<FiyatKaynagi>(gecenYil ? "gecen_yil" : "hesap");
  const v = useMemo(() => karlilikHaritasi(satirlar, hedefKarOrani, kaynak), [satirlar, hedefKarOrani, kaynak]);
  const risk = v.noktalar.filter((n) => n.bolge === "risk").sort((a, b) => b.adet - a.adet);
  const ozet =
    `${v.noktalar.length} ürün; eşikler: üretim adedi ${tamSayi.format(v.adetEsigi)}, kâr oranı %${v.karEsigi}. ` +
    `Çok satan kârlı ${v.sayilar.guclu}, çok satan marjı zayıf ${v.sayilar.risk}, az satan kârlı ${v.sayilar.nis}, az satan marjı zayıf ${v.sayilar.zayif}.`;
  const kenar = { left: 8, right: 24, top: 16, bottom: 8 };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor={`${id}-kaynak`} className="font-medium">
          Kâr hangi satış fiyatıyla ölçülsün
        </label>
        <select id={`${id}-kaynak`} className={SELECT} value={kaynak} onChange={(e) => setKaynak(e.target.value as FiyatKaynagi)}>
          <option value="gecen_yil" disabled={!gecenYil}>
            {FIYAT_KAYNAGI_ADI.gecen_yil}
            {gecenYil ? "" : " (Satış Geçmişi yok)"}
          </option>
          <option value="hesap">{FIYAT_KAYNAGI_ADI.hesap}</option>
        </select>
      </div>
      {v.duz && (
        <p
          role="note"
          data-testid="duz-notu"
          className="rounded-lg border border-marka/40 bg-accent/40 px-3 py-2 text-sm text-muted-foreground"
        >
          Bu kaynakta tüm ürünler aynı kâr oranında: fiyat çalışmasının satış fiyatı maliyet × (1 + hedef kâr) olduğundan harita dikeyde
          ayrışmaz. Gerçek kârlılık için{" "}
          <Link to={`/satis-gecmisi?senaryo=${senaryoId}`} className="text-primary underline-offset-4 hover:underline">
            Satış Geçmişi
          </Link>{" "}
          yükleyip &quot;Geçen yıl gerçek satış fiyatı&quot; kaynağını seçin.
        </p>
      )}
      {v.noktalar.length === 0 ? (
        <p role="note" className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          Haritaya girecek ürün yok: hesabı, seçili satış fiyatı ve üretim adedi olan ürün gerekir.
        </p>
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4" aria-label="Bölge sayıları">
            {(["guclu", "risk", "nis", "zayif"] as const).map((b) => (
              <div key={b} className="rounded-lg border bg-card px-3 py-2">
                <dt className="text-xs text-muted-foreground">{BOLGE_ADI[b]}</dt>
                <dd className="text-lg font-semibold tabular-nums" data-testid={`bolge-${b}`}>
                  {v.sayilar[b]}
                </dd>
              </div>
            ))}
          </dl>
          <figure className="flex flex-col gap-1" data-grafik="karlilik">
            <figcaption className="text-sm font-medium">
              <span className="mr-2 inline-block size-2.5 rounded-full align-middle" style={{ background: NOKTA_RENGI }} aria-hidden />
              Ürünler: üretim adedi (yatay, logaritmik) × kâr oranı (dikey). Kesikli çizgiler eşikler.
            </figcaption>
            <div style={{ height: OLCU.height }} role="img" aria-label={`Kârlılık haritası. ${ozet}`}>
              <ResponsiveContainer width="100%" height="100%" initialDimension={OLCU}>
                <ScatterChart margin={kenar}>
                  <CartesianGrid stroke="var(--border)" />
                  <XAxis
                    type="number"
                    dataKey="adet"
                    name="Üretim adedi"
                    scale="log"
                    domain={["auto", "auto"]}
                    tick={EKSEN}
                    tickLine={false}
                    axisLine={{ stroke: "var(--border)" }}
                    tickFormatter={adetEkseni}
                  >
                    <Label value="Üretim adedi (yıllık)" position="insideBottom" offset={-4} style={EKSEN} />
                  </XAxis>
                  <YAxis
                    type="number"
                    dataKey="kar"
                    name="Kâr oranı"
                    tick={EKSEN}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                    tickFormatter={yuzdeEkseni}
                    tickCount={6}
                    domain={[(min: number) => Math.min(0, Math.floor((min - 5) / 5) * 5), (max: number) => Math.ceil((max + 5) / 5) * 5]}
                  />
                  <Tooltip content={<Ipucu />} cursor={{ stroke: "var(--border)", strokeDasharray: "4 4" }} />
                  <ReferenceLine x={v.adetEsigi} stroke="var(--muted-foreground)" strokeDasharray="4 4">
                    <Label value={`Adet eşiği ${tamSayi.format(v.adetEsigi)}`} position="insideBottomLeft" style={EKSEN} />
                  </ReferenceLine>
                  <ReferenceLine y={v.karEsigi} stroke="var(--muted-foreground)" strokeDasharray="4 4">
                    <Label
                      value={`${v.karEsigiKaynagi === "hedef" ? "Hedef kâr" : "Medyan kâr"} %${v.karEsigi}`}
                      position="insideBottomRight"
                      style={EKSEN}
                    />
                  </ReferenceLine>
                  <Scatter
                    data={v.noktalar}
                    name="Ürün"
                    fill={NOKTA_RENGI}
                    stroke="var(--card)"
                    strokeWidth={2}
                    r={5}
                    isAnimationActive={false}
                  />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </figure>
          <p className="text-xs text-muted-foreground">
            Eşikler: üretim adedi medyanı {tamSayi.format(v.adetEsigi)} ve{" "}
            {v.karEsigiKaynagi === "hedef" ? "hedef kâr oranı" : "kâr oranı medyanı"} %{v.karEsigi}
            {v.karEsigiKaynagi === "hedef" && (
              <>
                {" "}
                (Parametreler&apos;deki <span className="font-mono">satis_kar</span>)
              </>
            )}
            . Kâr oranı = (satış − maliyet) / maliyet; satış = {FIYAT_KAYNAGI_ADI[kaynak].toLocaleLowerCase("tr")}.
            {v.disarida > 0 && ` ${v.disarida} ürün hesabı, seçili satış fiyatı ya da üretim adedi olmadığı için haritada yok.`}
          </p>
          <section aria-labelledby={`${id}-risk`} className="flex flex-col gap-2">
            <h3 id={`${id}-risk`} className="flex items-center gap-2 text-sm font-semibold">
              <TriangleAlert className="size-4 text-amber-600 dark:text-amber-400" aria-hidden />
              {BOLGE_ADI.risk} ({risk.length})
            </h3>
            {risk.length === 0 ? (
              <p className="text-sm text-muted-foreground">Çok satan ürünlerin hepsi kâr eşiğinin üstünde.</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border bg-card">
                <table className="w-full text-sm" aria-label="Çok satan, marjı zayıf ürünler">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="px-3 py-1.5 font-medium">Kod</th>
                      <th className="px-3 py-1.5 font-medium">Ürün</th>
                      <th className="px-3 py-1.5 font-medium">Hat</th>
                      <th className="px-3 py-1.5 text-right font-medium">Üretim adedi</th>
                      <th className="px-3 py-1.5 text-right font-medium">Maliyet</th>
                      <th className="px-3 py-1.5 text-right font-medium">Satış</th>
                      <th className="px-3 py-1.5 text-right font-medium">Kâr oranı</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risk.map((n) => (
                      <tr key={n.kod} className="border-b last:border-0 odd:bg-muted/40">
                        <td className="px-3 py-1.5 font-mono text-xs">
                          <Link
                            to={`/urunler/${encodeURIComponent(n.kod)}?senaryo=${senaryoId}`}
                            className="text-primary underline-offset-4 hover:underline"
                          >
                            {n.kod}
                          </Link>
                        </td>
                        <td className="px-3 py-1.5">{n.ad}</td>
                        <td className="px-3 py-1.5 text-muted-foreground">{n.hat}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{n.adetMetni}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{n.maliyetMetni}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{n.satisMetni}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{n.karMetni}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
