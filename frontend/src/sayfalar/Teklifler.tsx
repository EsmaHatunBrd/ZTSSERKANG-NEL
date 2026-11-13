import { useEffect, useMemo, useState } from "react";
import { Download, Printer } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import type { ApiHatasi } from "@/api/istemci";
import { useSenaryoTeklifleri } from "@/api/sorgular/hesaplar";
import type { SenaryoTeklifSatiri } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { TeklifDurumSecici } from "@/bilesenler/TeklifDurumSecici";
import { TeklifSilDugmesi } from "@/bilesenler/TeklifSilDugmesi";
import { Button, buttonVariants } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { YuzdeHucresi } from "@/bilesenler/YuzdeHucresi";
import { cn } from "@/lib/utils";
import { useSenaryoSayfasi } from "@/yardimcilar/sayfalama";
import { bugunIso, goster } from "@/yardimcilar/tarih";
import { paraBicimle, yuzdeBicimle } from "@/yardimcilar/para";
import { TEKLIF_DURUMLARI, teklifDurumAdi } from "@/yardimcilar/teklif";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";

/** Süzme ve sayfalama sunucuda yapılır (GET /teklifler); ekranda yalnızca geçerli sayfa bulunur. */
const BOYUT = 50;
const MUSTERI_GECIKME_MS = 300;

const YAZDIRMA_CSS = `
@media print {
  aside, header, .yazdirma-disi { display: none !important; }
  main { padding: 0 !important; }
  .yazdirma-alani { display: block !important; }
}`;

export default function Teklifler() {
  const { senaryoId, senaryo } = useSenaryo();
  const gezin = useNavigate();
  const [durum, setDurum] = useState("");
  const [musteriGirdi, setMusteriGirdi] = useState("");
  const [musteri, setMusteri] = useState("");
  // Ürün süzgeci (kod ya da ad); ?urun= ile gelen değer kutuya dolar (ürün ekranından bağlantı için).
  const [urunGirdi, setUrunGirdi] = useState(() => new URLSearchParams(window.location.search).get("urun") ?? "");
  const [urun, setUrun] = useState(urunGirdi.trim());
  useEffect(() => {
    const yeni = urunGirdi.trim();
    if (yeni === urun) return;
    const z = setTimeout(() => {
      setUrun(yeni);
      setSayfa(1);
    }, MUSTERI_GECIKME_MS);
    return () => clearTimeout(z);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urunGirdi, urun]);

  // Müşteri aramasında her tuş vuruşunda istek atmamak için kısa gecikme.
  useEffect(() => {
    const yeni = musteriGirdi.trim();
    if (yeni === musteri) return;
    const z = setTimeout(() => {
      setMusteri(yeni);
      setSayfa(1);
    }, MUSTERI_GECIKME_MS);
    return () => clearTimeout(z);
  }, [musteriGirdi, musteri]);

  const [sayfa, setSayfa] = useSenaryoSayfasi(senaryoId);

  const sorgu = useSenaryoTeklifleri(senaryoId, { durum, musteri, urun, sayfa, boyut: BOYUT });
  const satirlar = useMemo(() => sorgu.data?.kayitlar ?? [], [sorgu.data]);
  const toplam = sorgu.data?.toplam ?? 0;
  const sayfaSayisi = Math.max(1, Math.ceil(toplam / BOYUT));
  const hata = (sorgu.error as ApiHatasi | null) ?? null;

  const sutunlar = useMemo<SutunTanimi<SenaryoTeklifSatiri>[]>(
    () => [
      {
        id: "urun",
        header: "Ürün",
        accessorFn: (s: SenaryoTeklifSatiri) => s.urun_ad,
        cell: ({ row }: { row: { original: SenaryoTeklifSatiri } }) => (
          <div>
            <div>{row.original.urun_ad}</div>
            <div className="text-xs text-muted-foreground">{row.original.urun_kodu}</div>
          </div>
        ),
      },
      {
        id: "hesapTarihi",
        header: "Hesap tarihi",
        accessorFn: (s: SenaryoTeklifSatiri) => s.hesap_tarihi,
        cell: ({ getValue }: { getValue: () => unknown }) => goster(String(getValue())),
      },
      {
        id: "tur",
        header: "Tur",
        accessorFn: (s: SenaryoTeklifSatiri) => s.tur_no,
        cell: ({ getValue }: { getValue: () => unknown }) => `Tur ${getValue() as number}`,
      },
      {
        id: "kar",
        header: "Kâr %",
        accessorFn: (s: SenaryoTeklifSatiri) => s.kar_orani,
        cell: ({ getValue }: { getValue: () => unknown }) => <YuzdeHucresi deger={getValue() as string | null} />,
      },
      {
        id: "tl",
        header: "TL",
        accessorFn: (s: SenaryoTeklifSatiri) => s.fiyat_tl,
        cell: ({ getValue }: { getValue: () => unknown }) => <ParaHucresi deger={getValue() as string | null} />,
      },
      {
        id: "usd",
        header: "USD",
        accessorFn: (s: SenaryoTeklifSatiri) => s.fiyat_usd,
        cell: ({ getValue }: { getValue: () => unknown }) => <ParaHucresi deger={getValue() as string | null} paraBirimi="USD" />,
      },
      {
        id: "eur",
        header: "EUR",
        accessorFn: (s: SenaryoTeklifSatiri) => s.fiyat_eur,
        cell: ({ getValue }: { getValue: () => unknown }) => <ParaHucresi deger={getValue() as string | null} paraBirimi="EUR" />,
      },
      {
        id: "musteri",
        header: "Müşteri",
        accessorFn: (s: SenaryoTeklifSatiri) => s.musteri,
        cell: ({ getValue }: { getValue: () => unknown }) => (getValue() as string | null) ?? "—",
      },
      {
        id: "durum",
        header: "Durum",
        accessorFn: (s: SenaryoTeklifSatiri) => s.durum,
        cell: ({ row }: { row: { original: SenaryoTeklifSatiri } }) => {
          const s = row.original;
          // Satır tıklaması hesap görünümüne götürür; durum seçimi bunu tetiklememeli.
          return (
            <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
              <TeklifDurumSecici teklifId={s.teklif_id} durum={s.durum} etiket={`Durum — ${s.urun_kodu} Tur ${s.tur_no}`} />
            </span>
          );
        },
      },
      { id: "olusturan", header: "Oluşturan", accessorFn: (s: SenaryoTeklifSatiri) => s.olusturan },
      {
        id: "sil",
        header: () => <span className="sr-only">İşlem</span>,
        enableSorting: false,
        cell: ({ row }: { row: { original: SenaryoTeklifSatiri } }) => {
          const s = row.original;
          return (
            <span onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
              <TeklifSilDugmesi teklifId={s.teklif_id} etiket={`${s.urun_kodu} Tur ${s.tur_no}`} />
            </span>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const git = (s: SenaryoTeklifSatiri) => gezin(`/hesaplar/${s.hesap_id}`);

  return (
    <div className="flex flex-col gap-4">
      <style>{YAZDIRMA_CSS}</style>
      <div className="yazdirma-disi flex flex-col gap-4">
        <SayfaBasligi
          baslik="Teklifler"
          altBaslik="Seçili senaryodaki teklif turları. Satıra tıklayınca kayıtlı hesap açılır."
          eylemler={
            <>
              {senaryoId === null ? (
                <Button type="button" variant="outline" disabled>
                  <Download aria-hidden />
                  Teklif Kapak indir
                </Button>
              ) : (
                <a
                  href={`/api/v1/disa-aktar/teklif-kapak.xlsx?senaryo=${senaryoId}`}
                  download
                  className={cn(buttonVariants({ variant: "outline" }))}
                >
                  <Download aria-hidden />
                  Teklif Kapak indir
                </a>
              )}
              <Button type="button" variant="outline" onClick={() => window.print()} disabled={satirlar.length === 0}>
                <Printer aria-hidden />
                Yazdır
              </Button>
            </>
          }
        />

        <KilitSeridi />

        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Durum
            <select
              value={durum}
              onChange={(e) => {
                setDurum(e.target.value);
                setSayfa(1);
              }}
              className="h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">Tümü</option>
              {TEKLIF_DURUMLARI.map(([v, ad]) => (
                <option key={v} value={v}>
                  {ad}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Ürün ara
            <Input
              type="search"
              value={urunGirdi}
              onChange={(e) => setUrunGirdi(e.target.value)}
              className="w-64"
              placeholder="Ürün kodu ya da adı…"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Müşteri ara
            <Input
              type="search"
              value={musteriGirdi}
              onChange={(e) => setMusteriGirdi(e.target.value)}
              className="w-56"
              placeholder="Müşteri adı…"
            />
          </label>
        </div>

        <section aria-label="Teklif listesi">
          <VeriTablosu
            veri={satirlar}
            sutunlar={sutunlar}
            yukleniyor={sorgu.isLoading}
            hata={hata}
            bosMetin="Bu senaryoda teklif yok"
            bosAciklama="Teklif ürün ekranından açılır: Ürün Maliyeti'nde ürünü açın, Kaydet ile hesabı kaydedin, ardından sayfanın altındaki Teklif turları bölümünden kâr oranını seçip teklifi oluşturun."
            bosEylem={
              <Link
                to={senaryoId === null ? "/urunler" : `/urunler?senaryo=${senaryoId}`}
                className={cn(buttonVariants({ variant: "default", size: "sm" }))}
              >
                Ürün seç
              </Link>
            }
            satirTikla={git}
          />
        </section>

        <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
          <Button variant="outline" size="sm" disabled={sayfa <= 1} onClick={() => setSayfa((s) => s - 1)}>
            Önceki
          </Button>
          <span>
            Sayfa {sayfa} / {sayfaSayisi}
          </span>
          <Button variant="outline" size="sm" disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa((s) => s + 1)}>
            Sonraki
          </Button>
        </nav>
      </div>

      <section aria-label="Teklif özeti" role="region" className="yazdirma-alani hidden print:block">
        <h2 className="text-lg font-semibold">Teklif özeti</h2>
        <p className="text-xs">Not: Bu özet yalnızca bu sayfadaki teklifleri kapsar.</p>
        <p className="mb-2 text-sm">
          {senaryo ? `${senaryo.sezon_ad} · ${senaryo.ad}` : ""} — {goster(bugunIso())}
        </p>
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {["Ürün", "Hesap tarihi", "Tur", "Kâr", "TL", "USD", "EUR", "Müşteri", "Durum"].map((b) => (
                <th key={b} className="border-b px-1 py-1 text-left">
                  {b}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {satirlar.map((s) => (
              <tr key={s.teklif_id}>
                <td className="border-b px-1 py-1">{`${s.urun_kodu} ${s.urun_ad}`}</td>
                <td className="border-b px-1 py-1">{goster(s.hesap_tarihi)}</td>
                <td className="border-b px-1 py-1">{`Tur ${s.tur_no}`}</td>
                <td className="border-b px-1 py-1">{yuzdeBicimle(s.kar_orani)}</td>
                <td className="border-b px-1 py-1 text-right">{paraBicimle(s.fiyat_tl)}</td>
                <td className="border-b px-1 py-1 text-right">{s.fiyat_usd === null ? "—" : paraBicimle(s.fiyat_usd, "USD")}</td>
                <td className="border-b px-1 py-1 text-right">{s.fiyat_eur === null ? "—" : paraBicimle(s.fiyat_eur, "EUR")}</td>
                <td className="border-b px-1 py-1">{s.musteri ?? "—"}</td>
                <td className="border-b px-1 py-1">{teklifDurumAdi(s.durum)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
