import { useState } from "react";
import type { HesapSatiri, ReceteSatiri } from "@/api/tipler";
import { KaynakRozeti, ZS_ACIKLAMA, zsEtiketi } from "@/bilesenler/KaynakRozeti";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Badge } from "@/bilesenler/ui/badge";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { D, topla } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { GirdiHucresi } from "./GirdiHucresi";
import {
  eslestir,
  etkinBrutElle,
  etkinFiyatElle,
  fireOraniMetni,
  fireYuzdeHatasi,
  fireYuzdeMetni,
  fiyatsizMi,
  sayiGoster,
  MALZEME,
} from "./yardimci";
import type { SatirTaslagi, TaslakYamasi } from "./Taslak";

interface Props {
  satirlar: HesapSatiri[] | undefined;
  recete: ReceteSatiri[];
  uyarilar: string[];
  yukleniyor: boolean;
  hata: string | null;
  /** `Taslak.satirlar` dilimi (reçete sırası -> satır taslağı). */
  taslak: Record<number, SatirTaslagi>;
  /** Tek yazma kapısı: `{ satirlar: { [sira]: yama } }`. */
  onTaslak: (yama: TaslakYamasi) => void;
  /** Kayıtlı hesap görünümü: hücreler düzenlenemez, değerler kaydedilmiş değerlerdir. */
  saltOkunur?: boolean;
  /** Ürünün kodu: kodu buna eşit olan ara mamul satırı "Ürün" rozeti alır. */
  urunKodu?: string;
}

/** Girdi hücresinin gösterdiği metin (API sayısı -> virgüllü Türkçe metin; boşsa ""). */
const girdiMetni = (x: string | null | undefined) => (x === null || x === undefined ? "" : sayiGoster(x, 6));

/** Kaynak rozetini, tıklanınca elle -> kural geçişi yapan bir düğmeye sarar. */
function GecisDugmesi({
  etiket,
  eylem,
  onClick,
  children,
}: {
  etiket: string;
  eylem: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`${etiket}. ${eylem}`}
      title={eylem}
      className="rounded-4xl focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {children}
    </button>
  );
}

export function ReceteTablosu({ satirlar, recete, uyarilar, yukleniyor, hata, taslak, onTaslak, saltOkunur = false, urunKodu }: Props) {
  const [fireHata, setFireHata] = useState<{
    sira: number;
    mesaj: string;
  } | null>(null);
  const tum = satirlar ?? [];
  const eslesme = eslestir(tum, recete);
  // Seviye yoksa (eski anlık görüntüler) ağaç hissi: ara mamul satırından sonraki yaprak satırlar bir kademe girintilidir.
  const malzeme = tum
    .map((s, i) => ({ s, r: eslesme[i] }))
    .filter(({ s }) => s.grup === MALZEME)
    .map(({ s, r }, i, tumu) => {
      const ara = s.dugum_tipi === "ara_mamul";
      const oncesindeAra = tumu.slice(0, i + 1).some((x) => x.s.dugum_tipi === "ara_mamul" && !(x.s.kod && x.s.kod === urunKodu));
      return { s, r, ara, girinti: oncesindeAra && !ara ? 1 : 0 };
    });

  const firesizToplam = topla(malzeme.map(({ s }) => s.tutar_firesiz ?? "0"));
  const fireliToplam = topla(malzeme.map(({ s }) => s.tutar));
  const sutunSayisi = 15;

  return (
    // 16 sütun dar ekranda sığsın: sıkı hücre boşluğu, başlıklar ve malzeme adı iki satıra inebilir (sütun kaldırılmaz).
    <Table aria-label="Reçete tablosu" className="text-[13px] [&_td]:px-1.5 [&_th]:px-1.5 [&_th]:leading-tight [&_th]:whitespace-normal">
      <TableHeader>
        <TableRow>
          <TableHead>Satır</TableHead>
          <TableHead>Kod</TableHead>
          <TableHead>Cinsi</TableHead>
          <TableHead className="text-right">Miktar</TableHead>
          <TableHead className="text-right">Fire %</TableHead>
          <TableHead className="text-right">Brüt</TableHead>
          <TableHead>Birim</TableHead>
          <TableHead className="text-right">Birim fiyat</TableHead>
          <TableHead title={ZS_ACIKLAMA}>Kaynak</TableHead>
          <TableHead>Döviz</TableHead>
          <TableHead className="text-right">Tutar (firesiz)</TableHead>
          <TableHead className="text-right">Tutar (fireli)</TableHead>
          <TableHead className="text-right">Maliyet %</TableHead>
          <TableHead className="text-right">Satış %</TableHead>
          <TableHead title="Üstte miktar (fire kuralı / elle brüt), altta fiyat (liste / elle) kaynağı">Kaynak (miktar / fiyat)</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {hata ? (
          <TableRow>
            <TableCell colSpan={sutunSayisi}>
              <div className="py-6 text-center text-destructive">{hata}</div>
            </TableCell>
          </TableRow>
        ) : yukleniyor ? (
          <TableRow>
            <TableCell colSpan={sutunSayisi}>
              <div role="status" className="py-6 text-center text-muted-foreground">
                Hesaplanıyor…
              </div>
            </TableCell>
          </TableRow>
        ) : malzeme.length === 0 ? (
          <TableRow>
            <TableCell colSpan={sutunSayisi}>
              <div className="py-6 text-center text-muted-foreground">Bu ürünün reçetesinde malzeme satırı yok</div>
            </TableCell>
          </TableRow>
        ) : (
          malzeme.map(({ s, r, ara, girinti }, i) => {
            const t = r ? taslak[r.sira] : undefined;
            // Ürün satırı ve ara mamul satırları düzenlenmez; kayıtlı hesap görünümü tümüyle salt okunurdur.
            const duzenlenir = !!r && !ara && !saltOkunur;
            const urunSatiri = ara && !!s.kod && s.kod === urunKodu;
            const brutElle = r ? etkinBrutElle(r, t) : s.brut_miktar_elle;
            const fiyatElle = r ? etkinFiyatElle(r, t) : s.birim_fiyat_elle;
            // Sunucudaki satır elle brüt ise, taslakta fire'e dönülse bile fire girilemez (backend 422).
            const sunucuElle = r ? r.brut_miktar_elle !== null : false;
            const fiyatsiz = fiyatsizMi(s, uyarilar);
            // Tutarı 0 olan satır (ara mamul / fiyatı bilerek 0) soluk yazılır: göz tutarı olan satırlara gitsin.
            const sifirTutar = s.tutar == null || D(s.tutar).isZero();
            const miktarTuru = brutElle !== null ? "elle" : "fire";
            const fiyatTuru = fiyatElle !== null ? "elle" : s.fiyat_kaynagi === "elle" ? "liste" : s.fiyat_kaynagi;
            const yaz = (yama: NonNullable<TaslakYamasi["satirlar"]>[number]) => r && onTaslak({ satirlar: { [r.sira]: yama } });
            const seviyeli = s.seviye !== null && s.seviye !== undefined;
            return (
              <TableRow
                key={`${s.kod ?? s.kalem}-${i}`}
                data-uyari={fiyatsiz ? "true" : undefined}
                data-girinti={girinti}
                data-seviye={seviyeli ? s.seviye : undefined}
                className={cn(
                  ara && "bg-muted/50 odd:bg-muted/50",
                  sifirTutar && !urunSatiri && "text-muted-foreground",
                  urunSatiri && "font-semibold",
                )}
              >
                <TableCell className="tabular-nums">{r?.sira ?? s.sira ?? "—"}</TableCell>
                <TableCell className="text-xs whitespace-nowrap text-muted-foreground tabular-nums">{s.kod ?? "—"}</TableCell>
                <TableCell
                  className={cn("min-w-36 whitespace-normal", !seviyeli && girinti > 0 && "pl-8")}
                  style={seviyeli ? { paddingLeft: 8 + (s.seviye as number) * 14 } : undefined}
                >
                  {seviyeli && (s.seviye as number) > 0 && (
                    <span aria-hidden className="mr-1 text-muted-foreground">
                      └
                    </span>
                  )}
                  {s.kalem}
                  {ara && (
                    <Badge variant="outline" className="ml-2">
                      {urunSatiri ? "Ürün" : "Ara mamul"}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {duzenlenir && r ? (
                    <GirdiHucresi
                      etiket={`Miktar — ${s.kalem}`}
                      deger={girdiMetni(s.miktar)}
                      degisti={t?.miktar !== undefined}
                      eski={girdiMetni(r.miktar)}
                      onMetin={(m) => {
                        const v = m.trim() === "" ? undefined : sayiApi(m);
                        // Geçersiz metinde önceki değer kalır; boşaltmak taslağı siler.
                        if (m.trim() === "" || v !== null) yaz({ miktar: v ?? undefined });
                      }}
                    />
                  ) : (
                    sayiGoster(s.miktar)
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {duzenlenir && r ? (
                    <>
                      <GirdiHucresi
                        etiket={`Fire % — ${s.kalem}`}
                        deger={fireYuzdeMetni(s.fire_orani)}
                        disabled={brutElle !== null || sunucuElle}
                        degisti={t?.fire !== undefined}
                        eski={
                          r.fire_override != null ? `${fireYuzdeMetni(r.fire_override)} %` : `${fireYuzdeMetni(r.fire_orani)} % (kural)`
                        }
                        title={
                          sunucuElle && brutElle === null
                            ? "Reçeteyi kaydedince fire girilebilir"
                            : brutElle !== null
                              ? "elle brüt: fire uygulanmaz"
                              : undefined
                        }
                        aciklama={sunucuElle && brutElle === null ? "Reçeteyi kaydedince fire girilebilir" : undefined}
                        onMetin={(m) => {
                          if (m.trim() === "") {
                            setFireHata(null);
                            yaz({ fire: undefined });
                            return;
                          }
                          // Sunucuya gitmeden: sayı değilse ya da 0 ≤ x < 100 dışındaysa taslak verilmez.
                          const h = fireYuzdeHatasi(m);
                          setFireHata(h ? { sira: r.sira, mesaj: h } : null);
                          // Geçersiz girdide önceki geçerli değer de kalkar (görünmeyen eski değer hesapta kalmasın).
                          yaz({
                            fire: h ? undefined : (fireOraniMetni(m) ?? undefined),
                          });
                        }}
                        onCik={() => setFireHata(null)}
                      />
                      {fireHata?.sira === r.sira && (
                        <p role="alert" className="mt-1 text-xs text-destructive">
                          {fireHata.mesaj}
                        </p>
                      )}
                    </>
                  ) : (
                    <YuzdeHucresi deger={s.fire_orani} />
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {duzenlenir && r ? (
                    <GirdiHucresi
                      etiket={`Brüt — ${s.kalem}`}
                      deger={girdiMetni(s.brut_miktar)}
                      degisti={t?.brut_miktar_elle !== undefined}
                      eski={r.brut_miktar_elle != null ? girdiMetni(r.brut_miktar_elle) : "kurala bağlı (fire oranı)"}
                      title={t?.brut_miktar_elle === undefined ? "Boşaltırsanız fire oranı kuralına döner" : undefined}
                      onMetin={(m) => {
                        // Boş = kurala bırak (null); geçersiz metinde önceki değer kalır.
                        if (m.trim() === "") return yaz({ brut_miktar_elle: null });
                        const v = sayiApi(m);
                        if (v !== null) yaz({ brut_miktar_elle: v });
                      }}
                    />
                  ) : (
                    sayiGoster(s.brut_miktar)
                  )}
                </TableCell>
                <TableCell>{r?.birim ?? s.birim ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">
                  <div className="flex items-center justify-end gap-1.5">
                    {fiyatsiz && !urunSatiri && (
                      <span
                        className="size-2 shrink-0 rounded-full bg-chart-3"
                        title="Fiyat listesinde bu malzemenin fiyatı yok"
                        role="img"
                        aria-label="fiyat yok"
                      />
                    )}
                    {duzenlenir && r ? (
                      <GirdiHucresi
                        etiket={`Birim fiyat${s.doviz ? ` (${s.doviz})` : ""} — ${s.kalem}`}
                        deger={girdiMetni(s.birim_fiyat)}
                        className="w-20"
                        degisti={t?.birim_fiyat_elle !== undefined}
                        eski={r.birim_fiyat_elle != null ? girdiMetni(r.birim_fiyat_elle) : "liste fiyatı"}
                        title={t?.birim_fiyat_elle === undefined ? "Boşaltırsanız liste fiyatına döner" : undefined}
                        onMetin={(m) => {
                          // Boş = listeye dön (null); geçersiz metinde önceki değer kalır.
                          if (m.trim() === "") return yaz({ birim_fiyat_elle: null });
                          const v = sayiApi(m);
                          if (v !== null) yaz({ birim_fiyat_elle: v });
                        }}
                      />
                    ) : (
                      <ParaHucresi deger={s.birim_fiyat} paraBirimi={s.doviz ?? ""} basamak={4} />
                    )}
                  </div>
                </TableCell>
                <TableCell title={ZS_ACIKLAMA}>{zsEtiketi(s.zs)}</TableCell>
                <TableCell className="text-muted-foreground">{s.doviz ?? "—"}</TableCell>
                <TableCell>
                  <ParaHucresi deger={s.tutar_firesiz} />
                </TableCell>
                <TableCell>
                  <ParaHucresi deger={s.tutar} />
                </TableCell>
                <TableCell>
                  <YuzdeHucresi deger={s.maliyet_yuzdesi} />
                </TableCell>
                <TableCell>
                  <YuzdeHucresi deger={s.fiyat_yuzdesi} />
                </TableCell>
                <TableCell>
                  {/* Miktar ve fiyat kaynağı tek hücrede alt alta: dar ekranda iki ayrı sütun yer kaplamasın. */}
                  <div className="flex flex-col items-start gap-0.5">
                    {duzenlenir && brutElle !== null ? (
                      <GecisDugmesi
                        etiket={`Miktar kaynağı — ${s.kalem}: Elle`}
                        eylem="Fire oranı uygula"
                        onClick={() => yaz({ brut_miktar_elle: null })}
                      >
                        <KaynakRozeti tur="elle" />
                      </GecisDugmesi>
                    ) : (
                      <KaynakRozeti tur={duzenlenir ? miktarTuru : s.miktar_kaynagi} />
                    )}
                    {duzenlenir && fiyatElle !== null ? (
                      <GecisDugmesi
                        etiket={`Fiyat kaynağı — ${s.kalem}: Elle`}
                        eylem="Listeye dön"
                        onClick={() => yaz({ birim_fiyat_elle: null })}
                      >
                        <KaynakRozeti tur="elle" />
                      </GecisDugmesi>
                    ) : (
                      <KaynakRozeti tur={duzenlenir ? fiyatTuru : s.fiyat_kaynagi} />
                    )}
                  </div>
                </TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
      {!hata && !yukleniyor && malzeme.length > 0 && (
        <TableFooter>
          <TableRow>
            <TableCell colSpan={10} className="text-right font-medium">
              Malzeme toplamı (firesiz)
            </TableCell>
            <TableCell>
              <ParaHucresi deger={firesizToplam.toFixed(6)} className="font-medium" />
            </TableCell>
            <TableCell colSpan={4} />
          </TableRow>
          <TableRow>
            <TableCell colSpan={11} className="text-right font-medium">
              Malzeme toplamı (fireli)
            </TableCell>
            <TableCell>
              <ParaHucresi deger={fireliToplam.toFixed(6)} className="font-medium" />
            </TableCell>
            <TableCell colSpan={3} />
          </TableRow>
        </TableFooter>
      )}
    </Table>
  );
}
