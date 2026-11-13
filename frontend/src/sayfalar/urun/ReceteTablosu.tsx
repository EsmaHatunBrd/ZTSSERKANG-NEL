import { useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import type { HesapSatiri, ReceteSatiri } from "@/api/tipler";
import { useDuzenlemeKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { KaynakRozeti, ZS_ACIKLAMA, zsEtiketi } from "@/bilesenler/KaynakRozeti";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { D, topla } from "@/yardimcilar/para";
import { sayiApi } from "@/yardimcilar/sayi";
import { FormulIpucu } from "./FormulIpucu";
import { formulIpucu } from "./formulMetni";
import { GirdiHucresi } from "./GirdiHucresi";
import { gezinmeYonu, sonrakiHucre, TASLAK_ALANI, type GezinmeSatiri, type GirdiAlani } from "./receteKlavye";
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

/** Tablo yoğunluğu tercihi ("siki" | "rahat"; yoksa rahat). */
export const YOGUNLUK_ANAHTARI = "fiyat-calismasi.tablo-yogunluk";
type Yogunluk = "siki" | "rahat";

function kayitliYogunluk(): Yogunluk {
  try {
    return localStorage.getItem(YOGUNLUK_ANAHTARI) === "siki" ? "siki" : "rahat";
  } catch {
    return "rahat";
  }
}

/** Girdi hücresinin gösterdiği metin (API sayısı -> virgüllü Türkçe metin; boşsa ""). */
const girdiMetni = (x: string | null | undefined) => (x === null || x === undefined ? "" : sayiGoster(x, 6));

/** Solda sabit kalan ilk üç sütunun genişlik/konum sınıfları (Satır 3.5rem, Kod 10rem; Cinsi ondan sonra başlar). */
const SABIT_SATIR = "hucre-sabit left-0 w-14 min-w-14";
const SABIT_KOD = "hucre-sabit left-14 w-40 min-w-40";
const SABIT_CINSI = "hucre-sabit left-54 border-r";

/**
 * Kısa görünür başlık + tam ad: tam ad ekran okuyucuya ve `title` ipucuna gider; görünen kısa metin CSS ile çizilir
 * (`.kisa-baslik::before`), böylece başlığın metin içeriği tam ad olarak kalır (testler ve e2e tam adı arar).
 */
function KisaBaslik({ tam, kisa }: { tam: string; kisa: string }) {
  return (
    <>
      <span className="sr-only">{tam}</span>
      <span aria-hidden className="kisa-baslik" data-kisa={kisa} />
    </>
  );
}

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
  const kilitli = !useDuzenlemeKilidi().acik;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={kilitli}
      aria-label={`${etiket}. ${eylem}`}
      title={kilitli ? "Düzenleme kilitli" : eylem}
      className="rounded-4xl focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {children}
    </button>
  );
}

const GRUP_BASLIGI = "h-7 border-b text-center text-[11px] font-semibold tracking-wider text-muted-foreground uppercase";

export function ReceteTablosu({ satirlar, recete, uyarilar, yukleniyor, hata, taslak, onTaslak, saltOkunur = false, urunKodu }: Props) {
  const [fireHata, setFireHata] = useState<{
    sira: number;
    mesaj: string;
  } | null>(null);
  const [yogunluk, setYogunluk] = useState<Yogunluk>(kayitliYogunluk);
  function yogunlukAyarla(y: Yogunluk) {
    setYogunluk(y);
    try {
      localStorage.setItem(YOGUNLUK_ANAHTARI, y);
    } catch {
      /* depolama kapalı */
    }
  }
  const siki = yogunluk === "siki";
  // Katlanmış ara mamuller (satır anahtarı). Bileşen içi durum: sayfa yenilenince hepsi açık.
  const [kapali, setKapali] = useState<Set<string>>(() => new Set());
  // Odaklanılan girdinin odaklanma anındaki taslak değeri: Escape buna geri döner.
  const odak = useRef<{ sira: number; alan: GirdiAlani; deger: string | null | undefined } | null>(null);
  const tum = satirlar ?? [];
  const eslesme = eslestir(tum, recete);
  // Seviye yoksa (eski anlık görüntüler) ağaç hissi: ara mamul satırından sonraki yaprak satırlar bir kademe girintilidir.
  const malzemeHam = tum
    .map((s, i) => ({ s, r: eslesme[i] }))
    .filter(({ s }) => s.grup === MALZEME)
    .map(({ s, r }, i, tumu) => {
      const ara = s.dugum_tipi === "ara_mamul";
      const oncesindeAra = tumu.slice(0, i + 1).some((x) => x.s.dugum_tipi === "ara_mamul" && !(x.s.kod && x.s.kod === urunKodu));
      const girinti = oncesindeAra && !ara ? 1 : 0;
      const seviyeli = s.seviye !== null && s.seviye !== undefined;
      // Katlama için derinlik: sunucu seviyesi varsa o; yoksa ara mamul 0, altındaki yaprak 1.
      const derinlik = seviyeli ? (s.seviye as number) : ara ? 0 : girinti;
      const urunSatiri = ara && !!s.kod && s.kod === urunKodu;
      return { s, r, ara, girinti, seviyeli, derinlik, urunSatiri, anahtar: `${s.kod ?? s.kalem}-${i}` };
    });
  // Görünürlük: katlanmış bir üst satırın altındaki (daha derin) satırlar, aynı veya daha sığ ilk satıra kadar gizlenir.
  // Üst satır = kendisinden sonra daha derin satır gelen satır (sunucu `ara_mamul` demese de: Excel'den gelen reçetelerde
  // yarı mamuller `yaprak` + seviye ile gelir). Ürün satırı (satır 1) katlanmaz.
  let kapaliDerinlik: number | null = null;
  const malzeme = malzemeHam.map((m, i) => {
    if (kapaliDerinlik !== null && m.derinlik <= kapaliDerinlik) kapaliDerinlik = null;
    const gizli = kapaliDerinlik !== null;
    const altVar = !m.urunSatiri && i + 1 < malzemeHam.length && malzemeHam[i + 1].derinlik > m.derinlik;
    const kapaliMi = altVar && kapali.has(m.anahtar);
    if (kapaliMi && !gizli) kapaliDerinlik = m.derinlik;
    // Ürün satırı ve ara mamul satırları düzenlenmez; kayıtlı hesap görünümü tümüyle salt okunurdur.
    const duzenlenir = !!m.r && !m.ara && !saltOkunur;
    const t = m.r ? taslak[m.r.sira] : undefined;
    const brutElle = m.r ? etkinBrutElle(m.r, t) : m.s.brut_miktar_elle;
    // Sunucudaki satır elle brüt ise, taslakta fire'e dönülse bile fire girilemez (backend 422).
    const sunucuElle = m.r ? m.r.brut_miktar_elle !== null : false;
    const fireKapali = brutElle !== null || sunucuElle;
    return { ...m, t, gizli, altVar, kapaliMi, duzenlenir, brutElle, sunucuElle, fireKapali };
  });
  const gezinme: GezinmeSatiri[] = malzeme.map((m) => ({
    gorunur: !m.gizli,
    girdiler: m.duzenlenir ? { miktar: true, fire: !m.fireKapali, brut: true, fiyat: true } : {},
  }));

  function katla(anahtar: string) {
    setKapali((eski) => {
      const yeni = new Set(eski);
      if (yeni.has(anahtar)) yeni.delete(anahtar);
      else yeni.add(anahtar);
      return yeni;
    });
  }

  /** Olayın hedefi düzenlenebilir bir girdiyse sütun/satır bilgisini verir. */
  function girdiKonumu(hedef: EventTarget | null) {
    const el = hedef as HTMLElement | null;
    if (!el || el.tagName !== "INPUT") return null;
    const kap = el.closest<HTMLElement>("[data-alan]");
    if (!kap) return null;
    const i = Number(kap.dataset.satirIndeks);
    const sira = malzeme[i]?.r?.sira;
    if (sira === undefined) return null;
    return { girdi: el as HTMLInputElement, alan: kap.dataset.alan as GirdiAlani, i, sira };
  }

  function odaklandi(e: React.FocusEvent<HTMLTableSectionElement>) {
    const k = girdiKonumu(e.target);
    if (!k) return;
    odak.current = { sira: k.sira, alan: k.alan, deger: taslak[k.sira]?.[TASLAK_ALANI[k.alan]] };
  }

  function tusaBasildi(e: React.KeyboardEvent<HTMLTableSectionElement>) {
    const k = girdiKonumu(e.target);
    if (!k) return;
    if (e.key === "Escape") {
      // Hücredeki taslak değişikliğini odaklanmadan önceki haline döndür; odak hücrede kalır.
      const o = odak.current;
      if (o && o.sira === k.sira && o.alan === k.alan) {
        e.preventDefault();
        onTaslak({ satirlar: { [k.sira]: { [TASLAK_ALANI[k.alan]]: o.deger } } });
        if (k.alan === "fire") setFireHata(null);
        k.girdi.blur();
        k.girdi.focus();
      }
      return;
    }
    const yon = gezinmeYonu(e);
    if (yon === null) return;
    e.preventDefault();
    const hedefIndeks = sonrakiHucre(k.i, k.alan, yon, gezinme);
    if (hedefIndeks === null) return;
    const hedef = e.currentTarget.querySelector<HTMLInputElement>(`[data-alan="${k.alan}"][data-satir-indeks="${hedefIndeks}"] input`);
    hedef?.focus();
    hedef?.select();
  }

  const firesizToplam = topla(malzeme.map(({ s }) => s.tutar_firesiz ?? "0"));
  const fireliToplam = topla(malzeme.map(({ s }) => s.tutar));
  const sutunSayisi = 15;

  return (
    <div className="flex flex-col gap-2">
      <div role="group" aria-label="Tablo yoğunluğu" className="flex items-center justify-end gap-1 text-xs text-muted-foreground">
        <span className="mr-1">Görünüm</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-pressed={siki}
          className="aria-pressed:bg-accent aria-pressed:text-accent-foreground"
          onClick={() => yogunlukAyarla("siki")}
        >
          Sıkı
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-pressed={!siki}
          className="aria-pressed:bg-accent aria-pressed:text-accent-foreground"
          onClick={() => yogunlukAyarla("rahat")}
        >
          Rahat
        </Button>
      </div>
      {/* Yatay kaydırma kapsayıcısı: ilk üç sütun solda, başlık üstte, toplamlar altta sabit (Excel "bölmeleri dondur"). */}
      <div data-slot="table-container" className="relative max-h-[75vh] w-full overflow-auto rounded-xl border bg-card shadow-sm">
        <table
          aria-label="Reçete tablosu"
          data-yogunluk={yogunluk}
          className={cn(
            "w-full caption-bottom [&_td]:px-1.5 [&_th]:px-1.5 [&_th]:leading-tight",
            siki ? "text-xs [&_input]:h-6 [&_input]:w-16 [&_td]:py-1 [&_th]:py-1" : "text-[13px]",
          )}
        >
          <TableHeader>
            {/* Grup satırı yalnız görsel: erişilebilirlik ağacında sütun başlığı sayılmaz (alt satır tam adları taşır). */}
            <TableRow aria-hidden="true" className="odd:bg-transparent hover:bg-transparent">
              <th colSpan={3} className={cn(GRUP_BASLIGI, "hucre-sabit left-0 border-r")}>
                Malzeme
              </th>
              <th colSpan={4} className={GRUP_BASLIGI}>
                Miktar
              </th>
              <th colSpan={3} className={GRUP_BASLIGI}>
                Fiyat
              </th>
              <th colSpan={2} className={GRUP_BASLIGI}>
                Tutar
              </th>
              <th colSpan={2} className={GRUP_BASLIGI}>
                Pay
              </th>
              <th className={GRUP_BASLIGI}>Kaynak</th>
            </TableRow>
            <TableRow>
              <TableHead className={SABIT_SATIR}>Satır</TableHead>
              <TableHead className={SABIT_KOD}>Kod</TableHead>
              <TableHead className={SABIT_CINSI}>Cinsi</TableHead>
              <TableHead className="text-right">Miktar</TableHead>
              <TableHead className="text-right">Fire %</TableHead>
              <TableHead className="text-right">Brüt</TableHead>
              <TableHead>Birim</TableHead>
              <TableHead className="text-right">Birim fiyat</TableHead>
              <TableHead title={ZS_ACIKLAMA}>Kaynak</TableHead>
              <TableHead>Döviz</TableHead>
              <TableHead className="text-right" title="Tutar (firesiz)">
                <KisaBaslik tam="Tutar (firesiz)" kisa="Firesiz" />
              </TableHead>
              <TableHead className="text-right" title="Tutar (fireli)">
                <KisaBaslik tam="Tutar (fireli)" kisa="Fireli" />
              </TableHead>
              <TableHead className="text-right">Maliyet %</TableHead>
              <TableHead className="text-right">Satış %</TableHead>
              <TableHead title="Miktar kaynağı (fire kuralı / elle brüt) · fiyat kaynağı (liste / elle)">
                <KisaBaslik tam="Kaynak (miktar / fiyat)" kisa="Miktar · Fiyat" />
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody onKeyDown={tusaBasildi} onFocus={odaklandi}>
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
              malzeme.map((m, i) => {
                const { s, r, ara, girinti, seviyeli, urunSatiri, anahtar, t, gizli, altVar, kapaliMi, duzenlenir, brutElle, sunucuElle } =
                  m;
                // Katlanmış ara mamulün altı: toplamlar ve hesap değişmez, yalnız satır çizilmez.
                if (gizli) return null;
                const fiyatElle = r ? etkinFiyatElle(r, t) : s.birim_fiyat_elle;
                const fiyatsiz = fiyatsizMi(s, uyarilar);
                // Tutarı 0 olan satır (ara mamul / fiyatı bilerek 0) soluk yazılır: göz tutarı olan satırlara gitsin.
                const sifirTutar = s.tutar == null || D(s.tutar).isZero();
                const miktarTuru = brutElle !== null ? "elle" : "fire";
                const fiyatTuru = fiyatElle !== null ? "elle" : s.fiyat_kaynagi === "elle" ? "liste" : s.fiyat_kaynagi;
                const yaz = (yama: NonNullable<TaslakYamasi["satirlar"]>[number]) => r && onTaslak({ satirlar: { [r.sira]: yama } });
                const ipucu = formulIpucu(s);
                /** Girdiyi klavye gezinmesi için sütun/satır etiketiyle sarar (düzen değişmez: `contents`). */
                const girdiKabi = (alan: GirdiAlani, cocuk: React.ReactNode) => (
                  <span className="contents" data-alan={alan} data-satir-indeks={i}>
                    {cocuk}
                  </span>
                );
                return (
                  <TableRow
                    key={anahtar}
                    data-uyari={fiyatsiz ? "true" : undefined}
                    data-girinti={girinti}
                    data-seviye={seviyeli ? s.seviye : undefined}
                    data-ara={ara ? "true" : undefined}
                    data-kapali={kapaliMi ? "true" : undefined}
                    className={cn(
                      ara && "bg-muted/50 odd:bg-muted/50",
                      sifirTutar && !urunSatiri && "text-muted-foreground",
                      urunSatiri && "font-semibold",
                    )}
                  >
                    <TableCell className={cn(SABIT_SATIR, "tabular-nums")}>{r?.sira ?? s.sira ?? "—"}</TableCell>
                    <TableCell className={cn(SABIT_KOD, "text-xs whitespace-nowrap text-muted-foreground tabular-nums")}>
                      {s.kod ?? "—"}
                    </TableCell>
                    <TableCell
                      className={cn(SABIT_CINSI, !seviyeli && girinti > 0 && "pl-8")}
                      style={seviyeli ? { paddingLeft: 8 + (s.seviye as number) * 14 } : undefined}
                    >
                      <div className="flex min-w-0 items-center gap-1.5">
                        {altVar && (
                          <button
                            type="button"
                            aria-expanded={!kapaliMi}
                            aria-label={kapaliMi ? "Alt satırları göster" : "Alt satırları gizle"}
                            onClick={() => katla(anahtar)}
                            className="-ml-1 flex size-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                          >
                            <ChevronRight aria-hidden className={cn("size-3.5 transition-transform", !kapaliMi && "rotate-90")} />
                          </button>
                        )}
                        {seviyeli && (s.seviye as number) > 0 && (
                          <span aria-hidden className="shrink-0 text-muted-foreground">
                            └
                          </span>
                        )}
                        <span className="block max-w-[14rem] truncate" title={s.kalem}>
                          {s.kalem}
                        </span>
                        {ara && (
                          <Badge variant="outline" className="shrink-0">
                            {urunSatiri ? "Ürün" : "Ara mamul"}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {duzenlenir && r
                        ? girdiKabi(
                            "miktar",
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
                            />,
                          )
                        : sayiGoster(s.miktar)}
                    </TableCell>
                    <TableCell className="text-right">
                      {duzenlenir && r ? (
                        <>
                          {girdiKabi(
                            "fire",
                            <GirdiHucresi
                              etiket={`Fire % — ${s.kalem}`}
                              deger={fireYuzdeMetni(s.fire_orani)}
                              disabled={brutElle !== null || sunucuElle}
                              degisti={t?.fire !== undefined}
                              eski={
                                r.fire_override != null
                                  ? `${fireYuzdeMetni(r.fire_override)} %`
                                  : `${fireYuzdeMetni(r.fire_orani)} % (kural)`
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
                            />,
                          )}
                          {fireHata?.sira === r.sira && (
                            <p role="alert" className="mt-1 text-xs whitespace-normal text-destructive">
                              {fireHata.mesaj}
                            </p>
                          )}
                        </>
                      ) : (
                        <YuzdeHucresi deger={s.fire_orani} />
                      )}
                    </TableCell>
                    {/* Brüt: girdinin kendi title'ı (boşaltma ipucu) kalır; formül açıklaması hücrede. */}
                    <TableCell className="text-right tabular-nums" title={ipucu.brut}>
                      {duzenlenir && r
                        ? girdiKabi(
                            "brut",
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
                            />,
                          )
                        : sayiGoster(s.brut_miktar)}
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
                          girdiKabi(
                            "fiyat",
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
                            />,
                          )
                        ) : (
                          <ParaHucresi deger={s.birim_fiyat} paraBirimi={s.doviz ?? ""} basamak={4} />
                        )}
                      </div>
                    </TableCell>
                    <TableCell title={ZS_ACIKLAMA}>{zsEtiketi(s.zs)}</TableCell>
                    <TableCell className="text-muted-foreground">{s.doviz ?? "—"}</TableCell>
                    {/* "Bu sayı nereden geldi": fareye title, klavye odağına popover (formül satırın kendi alanlarından). */}
                    <TableCell className="text-right tabular-nums">
                      {ipucu.firesiz ? (
                        <FormulIpucu metin={ipucu.firesiz}>
                          <ParaHucresi deger={s.tutar_firesiz} />
                        </FormulIpucu>
                      ) : (
                        <ParaHucresi deger={s.tutar_firesiz} />
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {ipucu.fireli ? (
                        <FormulIpucu metin={ipucu.fireli}>
                          <ParaHucresi deger={s.tutar} />
                        </FormulIpucu>
                      ) : (
                        <ParaHucresi deger={s.tutar} />
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <YuzdeHucresi deger={s.maliyet_yuzdesi} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      <YuzdeHucresi deger={s.fiyat_yuzdesi} />
                    </TableCell>
                    <TableCell>
                      {/* Miktar ve fiyat kaynağı tek hücrede yan yana (sıra: miktar · fiyat). */}
                      <div data-kaynaklar className="flex flex-row flex-nowrap items-center gap-1">
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
            <TableFooter className="altbilgi-sabit">
              <TableRow>
                <TableCell colSpan={3} className={cn(SABIT_CINSI, "left-0 font-medium")}>
                  Malzeme toplamı (firesiz)
                </TableCell>
                <TableCell colSpan={7} />
                <TableCell className="text-right">
                  <ParaHucresi deger={firesizToplam.toFixed(6)} className="font-medium" />
                </TableCell>
                <TableCell colSpan={4} />
              </TableRow>
              <TableRow>
                <TableCell colSpan={3} className={cn(SABIT_CINSI, "left-0 font-medium")}>
                  Malzeme toplamı (fireli)
                </TableCell>
                <TableCell colSpan={8} />
                <TableCell className="text-right">
                  <ParaHucresi deger={fireliToplam.toFixed(6)} className="font-medium" />
                </TableCell>
                <TableCell colSpan={3} />
              </TableRow>
            </TableFooter>
          )}
        </table>
      </div>
    </div>
  );
}
