import { useState } from "react";
import type { AktarimOnizleRecete, ReceteAktarimSayfasi } from "@/api/tipler";
import { Badge } from "@/bilesenler/ui/badge";
import { AktarimFormu } from "./AktarimFormu";
import { FarkTablosu } from "./FarkTablosu";

export const DURUM_ETIKETI: Record<ReceteAktarimSayfasi["durum"], string> = {
  yeni_urun: "Yeni ürün",
  yeni_recete: "Bu çalışmada reçetesi yok",
  degisti: "Değişti",
  ayni: "Aynı",
};

/** Kullanıcının seçimi: önizlemenin önerisi (`secili`) üzerine yazılan işaretler; önizleme yenilenince sıfırlanır. */
export function seciliSayfalar(o: AktarimOnizleRecete, isaret: Record<string, boolean>): string[] {
  return o.sayfalar.filter((x) => isaret[x.sayfa] ?? x.secili).map((x) => x.sayfa);
}

function FarkOzeti({ s }: { s: ReceteAktarimSayfasi }) {
  if (s.durum !== "degisti") return <span className="text-muted-foreground">—</span>;
  const parca = [
    s.eklenen.length ? `+${s.eklenen.length} eklenen` : null,
    s.cikan.length ? `−${s.cikan.length} çıkan` : null,
    s.degisen.length ? `${s.degisen.length} değişen` : null,
  ].filter(Boolean);
  return <span>{parca.join(" · ")}</span>;
}

/** Veri Aktar → Ürün reçetesi: Excel ürün sayfası düzenindeki dosyadan reçeteler (önizle → seç → neden → uygula). */
export function ReceteDosyaAktar() {
  const [isaret, setIsaret] = useState<Record<string, boolean>>({});

  return (
    <AktarimFormu
      tip="recete"
      sablon="urun_recetesi"
      ad="Dosyadan reçete aktar"
      aciklama="Fiyat çalışması Excel'inin ürün sayfası düzenindeki dosya: kitabın tamamı ya da bir/birkaç ürün sayfasının kopyası. Her sayfanın reçetesi seçili çalışmadaki aktif reçeteyle karşılaştırılır; seçtiğiniz ürünler için yeni reçete versiyonu açılır, eski versiyon geçmişte kalır. Var olan ürün kartı ve üretim bilgileri değişmez; sistemde olmayan ürün sayfadaki bilgilerle açılır."
      onSifirla={() => setIsaret({})}
      uygulaEk={(o) => ({ sayfalar: seciliSayfalar(o, isaret) })}
      onizlemeGoster={(o) => {
        const secili = new Set(seciliSayfalar(o, isaret));
        return (
          <>
            {o.sayfalar.length > 0 && (
              <section aria-label="Ürün sayfaları" className="flex flex-col gap-1">
                <h3 className="text-sm font-medium">
                  Ürün sayfaları ({o.sayfalar.length}) · seçili {secili.size}
                </h3>
                <div className="max-h-96 overflow-auto rounded-md border">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-muted text-left">
                      <tr>
                        <th className="w-8 px-2 py-1">
                          <span className="sr-only">Seç</span>
                        </th>
                        <th className="px-2 py-1 font-medium">Sayfa</th>
                        <th className="px-2 py-1 font-medium">Ürün</th>
                        <th className="px-2 py-1 font-medium">Durum</th>
                        <th className="px-2 py-1 text-right font-medium">Satır</th>
                        <th className="px-2 py-1 font-medium">Fark</th>
                      </tr>
                    </thead>
                    <tbody>
                      {o.sayfalar.map((s) => (
                        <tr key={s.sayfa} className="border-t align-top">
                          <td className="px-2 py-1.5">
                            <input
                              type="checkbox"
                              className="size-4"
                              aria-label={`Uygula: ${s.sayfa} ${s.ad}`}
                              checked={secili.has(s.sayfa)}
                              onChange={(e) => setIsaret((i) => ({ ...i, [s.sayfa]: e.target.checked }))}
                            />
                          </td>
                          <td className="px-2 py-1.5 tabular-nums">{s.sayfa}</td>
                          <td className="px-2 py-1.5">
                            <span className="font-medium">{s.ad}</span>
                            <span className="block text-xs text-muted-foreground tabular-nums">{s.kod}</span>
                            {s.uyarilar.map((u) => (
                              <span key={u} className="block text-xs text-chart-3">
                                {u}
                              </span>
                            ))}
                          </td>
                          <td className="px-2 py-1.5">
                            <Badge variant={s.durum === "ayni" ? "outline" : "secondary"}>{DURUM_ETIKETI[s.durum]}</Badge>
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums">{s.satir_sayisi}</td>
                          <td className="px-2 py-1.5">
                            <FarkOzeti s={s} />
                            {s.durum === "degisti" && (
                              <details className="mt-1 text-xs">
                                <summary className="cursor-pointer text-muted-foreground">Ayrıntı</summary>
                                <ul className="mt-1 flex flex-col gap-0.5">
                                  {s.eklenen.map((x, i) => (
                                    <li key={`e${i}`}>
                                      + {x.kod} {x.ad}
                                    </li>
                                  ))}
                                  {s.cikan.map((x, i) => (
                                    <li key={`c${i}`}>
                                      − {x.kod} {x.ad}
                                    </li>
                                  ))}
                                  {s.degisen.map((x, i) => (
                                    <li key={`d${i}`}>
                                      ~ {x.kod} {x.ad}: {x.alanlar.join(", ")}
                                    </li>
                                  ))}
                                </ul>
                              </details>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
            <FarkTablosu baslik="Okunamayan sayfalar" sutunlar={["Sayfa", "Neden"]} satirlar={o.hatali.map((h) => [h.sayfa, h.mesaj])} />
          </>
        );
      }}
      yazilacakVar={(o) => seciliSayfalar(o, isaret).length > 0}
      ozetKartlari={(u) => [
        { baslik: "Yeni reçete versiyonu", deger: u.uygulanan.length },
        { baslik: "Yeni açılan ürün", deger: u.yeni_urun },
      ]}
      uyarilar={(u) => u.uygulanan.map((x) => `${x.sayfa}: ${x.kod} → v${x.versiyon}`)}
    />
  );
}
