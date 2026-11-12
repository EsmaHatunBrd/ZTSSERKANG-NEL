import { useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type Decimal from "decimal.js";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useHesap, useHesaplar } from "@/api/sorgular/hesaplar";
import type { KayitliHesapOzeti } from "@/api/tipler";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { cn } from "@/lib/utils";
import { paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { teklifDurumAdi } from "@/yardimcilar/teklif";
import { hesaplariSirala, kiyasla, receteKiyasla, type ReceteKiyasDurumu } from "./hesapKiyas";

interface Props {
  kod: string;
  senaryoId: number | null;
}

export const ILK_SATIR = 10;
export const EN_COK_SECIM = 2;
export const BOS_METNI = "Bu ürün için kayıtlı hesap yok. Hesabı kaydet ile ilk kaydı oluşturun.";
export const SECIM_IPUCU = "En çok iki hesap kıyaslanır; yeni bir hesap seçmek için önce birinin işaretini kaldırın.";

/** Ürün ekranının "Geçmiş hesaplar" bölümü: kayıtlı hesapların zaman çizgisi ve iki hesabın kıyası. */
export function HesapGecmisi({ kod, senaryoId }: Props) {
  const gezin = useNavigate();
  const hesaplar = useHesaplar(kod, senaryoId);
  const [tumu, setTumu] = useState(false);
  const [secili, setSecili] = useState<number[]>([]);

  const sirali = useMemo(() => hesaplariSirala(hesaplar.data?.kayitlar ?? []), [hesaplar.data]);
  const gorunen = tumu ? sirali : sirali.slice(0, ILK_SATIR);
  const gizli = sirali.length - gorunen.length;
  const seciliSet = useMemo(() => new Set(secili), [secili]);
  // Sütun tanımı seçime bağlı olursa her tıklamada hücre bileşeni yeniden mount olur (odak kaybı). Sütun sabit kalır;
  // hücre güncel seçimi ref'ten okur (bölüm her seçim değişiminde yeniden çizildiği için hücre de yeniden çizilir).
  const seciliRef = useRef(secili);
  seciliRef.current = secili;

  function secimDegistir(id: number, isaretli: boolean) {
    setSecili((s) => (isaretli ? (s.includes(id) || s.length >= EN_COK_SECIM ? s : [...s, id]) : s.filter((x) => x !== id)));
  }

  const sutunlar = useMemo<SutunTanimi<KayitliHesapOzeti>[]>(
    () => [
      {
        id: "kiyas",
        header: "Kıyasla",
        enableSorting: false,
        meta: { hiza: "sol", sinif: "w-16" },
        cell: ({ row }) => {
          const h = row.original;
          const isaretli = seciliRef.current.includes(h.id);
          const kapali = seciliRef.current.length >= EN_COK_SECIM && !isaretli;
          return (
            <input
              type="checkbox"
              className="size-4 accent-primary disabled:cursor-not-allowed disabled:opacity-50"
              aria-label={`Kıyas için seç: ${goster(h.hesap_tarihi)} #${h.id}`}
              checked={isaretli}
              disabled={kapali}
              title={kapali ? SECIM_IPUCU : undefined}
              onChange={(e) => secimDegistir(h.id, e.target.checked)}
            />
          );
        },
      },
      { accessorKey: "hesap_tarihi", header: "Tarih", meta: { hiza: "sol" }, cell: ({ getValue }) => goster(getValue<string>()) },
      {
        accessorKey: "id",
        header: "No",
        meta: { hiza: "sol" },
        cell: ({ row }) => (
          <Link
            to={`/hesaplar/${row.original.id}?senaryo=${senaryoId ?? ""}`}
            className="font-medium text-primary underline-offset-4 hover:underline"
          >
            #{row.original.id}
          </Link>
        ),
      },
      {
        accessorKey: "maliyet_tl",
        header: "Birim maliyet (TL)",
        meta: { hiza: "sag" },
        cell: ({ getValue }) => <span className="tabular-nums">{paraDolu(getValue<string | null>())}</span>,
      },
      {
        accessorKey: "satis_tl",
        header: "Satış fiyatı (TL)",
        meta: { hiza: "sag" },
        cell: ({ getValue }) => <span className="tabular-nums">{paraDolu(getValue<string | null>())}</span>,
      },
      {
        id: "son_tur",
        header: "Son tur",
        accessorFn: (h) => h.son_tur_no ?? null,
        meta: { hiza: "sol" },
        cell: ({ row }) => sonTurMetni(row.original),
      },
      { accessorKey: "olusturan", header: "Kaydeden", meta: { hiza: "sol" } },
    ],
    [senaryoId],
  );

  // Kıyas: A eski, B yeni (zaman çizgisindeki sıraya göre; seçim sırasından bağımsız).
  const kiyasIdleri = useMemo(() => {
    if (secili.length !== EN_COK_SECIM) return null;
    const [yeni, eski] = sirali.filter((h) => seciliSet.has(h.id));
    return yeni && eski ? { a: eski, b: yeni } : null;
  }, [secili, seciliSet, sirali]);

  return (
    <section aria-label="Geçmiş hesaplar" className="flex flex-col gap-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Geçmiş hesaplar</h2>
        {sirali.length > 0 && (
          <p className="text-xs text-muted-foreground">
            {secili.length === 0
              ? "Kıyaslamak için iki hesap işaretleyin."
              : secili.length === 1
                ? "Bir hesap daha işaretleyin."
                : "İki hesap seçildi; kıyas aşağıda."}
          </p>
        )}
      </div>

      <VeriTablosu<KayitliHesapOzeti>
        veri={gorunen}
        sutunlar={sutunlar}
        yukleniyor={hesaplar.isPending && senaryoId !== null}
        hata={(hesaplar.error as ApiHatasi | null) ?? null}
        bosMetin={BOS_METNI}
        satirTikla={(h) => gezin(`/hesaplar/${h.id}?senaryo=${senaryoId ?? ""}`)}
      />

      {gizli > 0 && (
        <Button type="button" variant="outline" size="sm" className="w-fit" onClick={() => setTumu(true)}>
          Tümünü göster ({sirali.length})
        </Button>
      )}

      {kiyasIdleri && <KiyasPaneli a={kiyasIdleri.a} b={kiyasIdleri.b} senaryoId={senaryoId} />}
    </section>
  );
}

const paraDolu = (x: string | null | undefined) => (x === null || x === undefined || x === "" ? "—" : paraBicimle(x, ""));

function sonTurMetni(h: KayitliHesapOzeti): string {
  if (h.son_tur_no == null) return "—";
  const parcalar = [`Tur ${h.son_tur_no}`];
  if (h.son_kar_orani != null) parcalar.push(yuzdeBicimle(h.son_kar_orani, 1));
  if (h.son_durum) parcalar.push(teklifDurumAdi(h.son_durum));
  return parcalar.join(" · ");
}

interface KiyasProps {
  a: KayitliHesapOzeti;
  b: KayitliHesapOzeti;
  senaryoId: number | null;
}

const SAG = "text-right tabular-nums";

/** Artış kırmızı, azalış yeşil, değişmeyen sönük. */
function farkSinifi(fark: Decimal | null): string {
  if (fark === null || fark.isZero()) return "text-muted-foreground";
  return fark.gt(0) ? "text-destructive" : "text-primary";
}

const farkMetni = (fark: Decimal | null, birim: string) => (fark === null ? "—" : `${fark.gt(0) ? "+" : ""}${paraBicimle(fark, birim)}`);
const yuzdeMetni = (y: Decimal | null) => (y === null ? "—" : `${y.gt(0) ? "+" : ""}${yuzdeBicimle(y, 1)}`);

const DURUM_ROZETI: Partial<Record<ReceteKiyasDurumu, string>> = { yalniz_a: "yalnız A", yalniz_b: "yalnız B" };

function KiyasPaneli({ a, b, senaryoId }: KiyasProps) {
  const hesapA = useHesap(a.id);
  const hesapB = useHesap(b.id);
  const [yalnizDegisen, setYalnizDegisen] = useState(true);

  const ozet = useMemo(
    () => (hesapA.data && hesapB.data ? kiyasla(hesapA.data.gorunum, hesapB.data.gorunum) : []),
    [hesapA.data, hesapB.data],
  );
  const recete = useMemo(
    () => (hesapA.data && hesapB.data ? receteKiyasla(hesapA.data.gorunum.satirlar, hesapB.data.gorunum.satirlar) : []),
    [hesapA.data, hesapB.data],
  );
  const receteGorunen = yalnizDegisen ? recete.filter((s) => s.durum !== "ayni") : recete;
  const hata = hesapA.error ?? hesapB.error;

  return (
    <section role="region" aria-label="Hesap kıyası" className="flex flex-col gap-3 rounded-lg border border-primary/30 bg-primary/5 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          Kıyas: A {goster(a.hesap_tarihi)} #{a.id} → B {goster(b.hesap_tarihi)} #{b.id}
        </h3>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link to={`/hesaplar/${a.id}`} className="text-primary underline-offset-4 hover:underline">
            Kayıtlı hesabı aç (A #{a.id})
          </Link>
          <Link to={`/hesaplar/${b.id}`} className="text-primary underline-offset-4 hover:underline">
            Kayıtlı hesabı aç (B #{b.id})
          </Link>
          <Link to={`/butce-gerceklesen?senaryo=${senaryoId ?? ""}`} className="text-primary underline-offset-4 hover:underline">
            Kıyasla modülü
          </Link>
        </div>
      </div>

      {hata ? (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </p>
      ) : hesapA.isPending || hesapB.isPending ? (
        <p role="status" className="text-sm text-muted-foreground">
          Kıyas hazırlanıyor…
        </p>
      ) : (
        <>
          <Table aria-label="Kıyas özeti" className="text-[13px]">
            <TableHeader>
              <TableRow>
                <TableHead>Kalem</TableHead>
                <TableHead className={SAG}>A (eski)</TableHead>
                <TableHead className={SAG}>B (yeni)</TableHead>
                <TableHead className={SAG}>Fark</TableHead>
                <TableHead className={SAG}>Fark %</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ozet.map((s) => (
                <TableRow key={s.etiket}>
                  <TableCell>{s.etiket}</TableCell>
                  <TableCell className={SAG}>{s.a === null ? "—" : paraBicimle(s.a, s.birim)}</TableCell>
                  <TableCell className={SAG}>{s.b === null ? "—" : paraBicimle(s.b, s.birim)}</TableCell>
                  <TableCell className={cn(SAG, farkSinifi(s.fark))}>{farkMetni(s.fark, s.birim)}</TableCell>
                  <TableCell className={cn(SAG, farkSinifi(s.fark))}>{yuzdeMetni(s.farkYuzde)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-sm font-medium">Reçete satırları</h4>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                role="switch"
                className="size-4 accent-primary"
                aria-checked={yalnizDegisen}
                checked={yalnizDegisen}
                onChange={(e) => setYalnizDegisen(e.target.checked)}
              />
              Yalnız değişenleri göster
            </label>
          </div>
          {receteGorunen.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {recete.length === 0 ? "Kodlu reçete satırı yok." : "Reçete satırlarında değişiklik yok."}
            </p>
          ) : (
            <Table aria-label="Reçete kıyası" className="text-[13px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Kod</TableHead>
                  <TableHead>Cinsi</TableHead>
                  <TableHead className={SAG}>A tutar (TL)</TableHead>
                  <TableHead className={SAG}>B tutar (TL)</TableHead>
                  <TableHead className={SAG}>Fark (TL)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {receteGorunen.map((s) => (
                  <TableRow key={s.anahtar} data-durum={s.durum} className={cn(s.durum === "ayni" && "text-muted-foreground")}>
                    <TableCell className="font-medium">{s.kod}</TableCell>
                    <TableCell>
                      <span className="flex flex-wrap items-center gap-2">
                        {s.kalem}
                        {DURUM_ROZETI[s.durum] && <Badge variant="outline">{DURUM_ROZETI[s.durum]}</Badge>}
                      </span>
                    </TableCell>
                    <TableCell className={SAG}>{s.a === null ? "—" : paraBicimle(s.a, "")}</TableCell>
                    <TableCell className={SAG}>{s.b === null ? "—" : paraBicimle(s.b, "")}</TableCell>
                    <TableCell className={cn(SAG, farkSinifi(s.fark))}>{farkMetni(s.fark, "")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </section>
  );
}
