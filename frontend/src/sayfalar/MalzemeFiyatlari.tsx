import { useDeferredValue, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { History, Pencil, Upload } from "lucide-react";
import { useFiyatGecmisi, useMalzemeler } from "@/api/sorgular/malzemeler";
import type { Malzeme } from "@/api/tipler";
import { useOnayliFiyatEkle } from "@/bilesenler/FiyatSapmaOnayi";
import { GecmisCekmecesi } from "@/bilesenler/GecmisCekmecesi";
import { KaynakRozeti, ZS_ACIKLAMA, zsEtiketi } from "@/bilesenler/KaynakRozeti";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { paraBicimle, type ParaBirimi } from "@/yardimcilar/para";
import { useSenaryoSayfasi } from "@/yardimcilar/sayfalama";
import { bugunIso, goster } from "@/yardimcilar/tarih";
import { DegerDiyalogu } from "./ayarlar/DegerDiyalogu";
import { FiyatListesiYukle } from "./ayarlar/FiyatListesiYukle";
import { GeriAlOnayi } from "./ayarlar/GeriAlOnayi";
import { hataMetniVarsa, type ApiHatasi } from "@/api/istemci";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";

const BOYUT = 100;
/** Süzgeç onay kutuları: basılabilir rozet görünümü (işaretliyse vurgulu zemin). */
const SUZGEC_ROZETI =
  "inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 text-sm whitespace-nowrap select-none hover:bg-muted has-checked:border-primary/40 has-checked:bg-accent";

function birim(m: Malzeme): ParaBirimi {
  return m.para_birimi?.trim() || "TL";
}

/** Tip adını kısaltır: "0001-Hammadde" -> "Hammadde" (kod öneki ipucunda kalır). */
export function tipKisa(tip: string | null | undefined): string {
  const t = (tip ?? "").trim();
  return t.replace(/^\d+\s*-\s*/, "") || t;
}

/** Geçmiş çekmecesi: fiyat geçmişini çeker; geri al = eski fiyatı bugünden geçerli YENİ kayıt olarak ekler. */
function FiyatGecmisiPaneli({
  malzeme,
  senaryo,
  kilitli,
  onKapat,
  onBasari,
}: {
  malzeme: Malzeme;
  senaryo: number;
  kilitli: boolean;
  onKapat: () => void;
  onBasari: (m: string) => void;
}) {
  const gecmis = useFiyatGecmisi(malzeme.kod, senaryo);
  const ekle = useOnayliFiyatEkle();
  const kayitlar = useMemo(
    () =>
      (gecmis.data?.kayitlar ?? []).map((k) => ({
        deger: k.fiyat,
        gecerlilik_basi: k.gecerlilik_basi,
        neden: k.neden,
        olusturan: k.olusturan,
        olusturma_zamani: k.olusturma_zamani ?? "",
        para_birimi: k.para_birimi,
      })),
    [gecmis.data],
  );
  const [bekleyen, setBekleyen] = useState<{ k: (typeof kayitlar)[number]; neden: string } | null>(null);

  function onayla() {
    if (!bekleyen) return;
    const { k, neden } = bekleyen;
    ekle.mutate(
      {
        kod: malzeme.kod,
        senaryo,
        govde: {
          fiyat: k.deger,
          gecerlilik_basi: bugunIso(),
          neden,
          para_birimi: k.para_birimi ?? malzeme.para_birimi ?? "TL",
          onay: false,
        },
      },
      {
        onSuccess: () => {
          onBasari(`${malzeme.kod} fiyatı geri alındı (yeni kayıt olarak eklendi).`);
          setBekleyen(null);
          onKapat();
        },
      },
    );
  }

  return (
    <>
      <GecmisCekmecesi
        acik
        onAcikDegisti={(a) => !a && onKapat()}
        baslik={`Fiyat geçmişi: ${malzeme.kod}`}
        kayitlar={kayitlar}
        degerGoster={(d) => paraBicimle(d, birim(malzeme))}
        geriAl={
          kilitli
            ? undefined
            : (k, neden) => {
                ekle.reset();
                setBekleyen({ k: k as (typeof kayitlar)[number], neden });
              }
        }
      />
      {bekleyen && (
        <GeriAlOnayi
          metin={`${goster(bekleyen.k.gecerlilik_basi)} tarihli ${paraBicimle(bekleyen.k.deger, birim(malzeme), 4)} değeri bugünden itibaren geçerli olacak.`}
          hata={hataMetniVarsa(ekle.error)}
          bekliyor={ekle.isPending}
          onOnayla={onayla}
          onVazgec={() => {
            ekle.reset();
            setBekleyen(null);
          }}
        />
      )}
      {ekle.onayDiyalogu}
    </>
  );
}

export default function MalzemeFiyatlari() {
  const { senaryoId, kilitli } = useSenaryo();
  const [params, setParams] = useSearchParams();
  const [fiyatsiz, setFiyatsiz] = useState(() => params.get("fiyatsiz") === "1"); // Genel Bakış'taki "Fiyatsız malzeme" kartından
  const [duzenlenen, setDuzenlenen] = useState<Malzeme | null>(null);
  const [gecmisMalzeme, setGecmisMalzeme] = useState<Malzeme | null>(null);
  const [yukle, setYukle] = useState(false);
  const [mesaj, setMesaj] = useState<string | null>(null);

  const [sayfa, setSayfa] = useSenaryoSayfasi(senaryoId);
  const revize = params.get("revize") === "1"; // URL'de taşınır: ?revize=1 paylaşılabilir / geri tuşuyla korunur
  const [arama, setArama] = useState(() => params.get("arama") ?? ""); // Ctrl+K hızlı arama ya da Veri Kontrolü'nden gelen malzeme kodu
  // Arama sunucuda, sayfalamadan önce süzülür (aranan malzeme 2. sayfada olsa da bulunur); yazarken her tuşta istek beklemesin.
  const sunucuArama = useDeferredValue(arama.trim());
  const sorgu = useMalzemeler(senaryoId, {
    fiyatsiz: fiyatsiz || undefined,
    revize: revize || undefined,
    arama: sunucuArama || undefined,
    sayfa,
    boyut: BOYUT,
  });
  const ekle = useOnayliFiyatEkle();

  function revizeAyarla(acik: boolean) {
    setParams(
      (onceki) => {
        const p = new URLSearchParams(onceki);
        if (acik) p.set("revize", "1");
        else p.delete("revize");
        return p;
      },
      { replace: true },
    );
    setSayfa(1);
  }
  const gorunen = useMemo(() => {
    const q = arama.trim().toLocaleLowerCase("tr");
    const kayitlar = sorgu.data?.kayitlar ?? [];
    return q
      ? kayitlar.filter((m) => m.kod.toLocaleLowerCase("tr").includes(q) || (m.ad ?? "").toLocaleLowerCase("tr").includes(q))
      : kayitlar;
  }, [sorgu.data, arama]);
  const toplam = sorgu.data?.toplam ?? 0;
  const sayfaSayisi = Math.max(1, Math.ceil(toplam / BOYUT));

  const sutunlar = useMemo<SutunTanimi<Malzeme>[]>(
    () => [
      // Kod ve Ad yatay kaydırmada solda sabit kalır (hucre-sabit); genişlikleri sabit ki ikinci sütunun sol kenarı tutsun.
      {
        accessorKey: "kod",
        header: "Kod",
        meta: { sinif: "hucre-sabit left-0 w-44 min-w-44 font-mono text-xs" },
      },
      {
        accessorKey: "ad",
        header: "Ad",
        meta: { sinif: "hucre-sabit left-44 min-w-56 border-r" },
        cell: ({ row }) =>
          row.original.kart_yok ? (
            <Badge variant="destructive">Kart yok</Badge>
          ) : (
            <span className="block max-w-[20rem] truncate" title={row.original.ad ?? undefined}>
              {row.original.ad ?? "—"}
            </span>
          ),
      },
      {
        accessorKey: "tip",
        header: "Tip",
        cell: ({ row }) =>
          row.original.tip ? (
            <span title={row.original.tip}>{tipKisa(row.original.tip)}</span>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      { accessorKey: "birim", header: "Birim", meta: { sinif: "w-16" } },
      { accessorKey: "para_birimi", header: "Para", meta: { sinif: "w-16" } },
      {
        accessorKey: "zs",
        header: () => <span title={ZS_ACIKLAMA}>Kaynak</span>,
        cell: ({ row }) =>
          row.original.kart_yok ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <span title={ZS_ACIKLAMA}>{zsEtiketi(row.original.zs)}</span>
          ),
      },
      {
        accessorKey: "ilk_fiyat",
        header: "İlk bütçe",
        cell: ({ row }) =>
          row.original.kart_yok || !row.original.ilk_fiyat ? (
            <span className="block text-right text-muted-foreground">—</span>
          ) : (
            <ParaHucresi deger={row.original.ilk_fiyat} paraBirimi={birim(row.original)} basamak={4} />
          ),
      },
      {
        accessorKey: "revize",
        header: "Revize",
        cell: ({ row }) =>
          row.original.revize ? (
            <Badge variant="outline" title="Geçerli fiyat ilk bütçeden farklı (S.ALMA BF I ya da sonraki değişiklik)">
              Revize
            </Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
      {
        accessorKey: "fiyat",
        header: "Geçerli fiyat",
        cell: ({ row }) =>
          row.original.kart_yok ? (
            <span className="block text-right text-muted-foreground">—</span>
          ) : (
            // Fiyatsız satırda "0,0000" yazılmaz; yalnız rozet.
            <span className="flex items-center justify-end gap-2">
              {row.original.fiyatsiz ? (
                <Badge variant="outline">Fiyatsız</Badge>
              ) : (
                <ParaHucresi deger={row.original.fiyat ?? null} paraBirimi={birim(row.original)} basamak={4} />
              )}
            </span>
          ),
      },
      {
        accessorKey: "gecerlilik_basi",
        header: "Geçerlilik",
        cell: ({ row }) =>
          row.original.gecerlilik_basi ? goster(row.original.gecerlilik_basi) : <span className="text-muted-foreground">—</span>,
      },
      {
        accessorKey: "kaynak",
        header: "Kayıt kaynağı",
        cell: ({ row }) => {
          const k = row.original.kaynak;
          if (!k) return <span className="text-muted-foreground">—</span>;
          return <KaynakRozeti tur={k} />;
        },
      },
      {
        id: "islem",
        header: "İşlem",
        enableSorting: false,
        cell: ({ row }) => (
          <span className="flex gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={`Fiyat değiştir ${row.original.kod}`}
              title={row.original.kart_yok ? "Önce malzeme kartı açılmalı" : "Fiyat değiştir"}
              disabled={!!row.original.kart_yok || kilitli}
              onClick={() => setDuzenlenen(row.original)}
            >
              <Pencil />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={`Geçmiş ${row.original.kod}`}
              title="Fiyat geçmişi"
              disabled={!!row.original.kart_yok}
              onClick={() => setGecmisMalzeme(row.original)}
            >
              <History />
            </Button>
          </span>
        ),
      },
    ],
    [kilitli],
  );

  return (
    <section className="flex flex-col gap-4">
      <SayfaBasligi
        baslik="Malzeme Fiyatları"
        eylemler={
          <Button type="button" variant="outline" disabled={senaryoId == null || kilitli} onClick={() => setYukle(true)}>
            <Upload /> Fiyat listesi yükle
          </Button>
        }
      />
      <KilitSeridi />

      {/* Tek satır: arama solda, iki süzgeç basılabilir rozet görünümünde, sağda kayıt sayacı. Dar ekranda sarar. */}
      <div role="group" aria-label="Süzgeçler" className="flex flex-wrap items-center gap-2">
        <Input
          type="search"
          aria-label="Malzeme ara (kod ya da ad)"
          placeholder="Malzeme ara (kod ya da ad)"
          value={arama}
          onChange={(e) => {
            setArama(e.target.value);
            setSayfa(1);
          }}
          className="max-w-sm"
        />
        <label className={SUZGEC_ROZETI} title="Yalnızca fiyatsız malzemeler (kartı olmayanlar dahil)">
          <input
            type="checkbox"
            className="accent-primary"
            checked={fiyatsiz}
            onChange={(e) => {
              setFiyatsiz(e.target.checked);
              setSayfa(1);
            }}
          />
          Yalnız fiyatsız
        </label>
        <label className={SUZGEC_ROZETI} title="Geçerli fiyat ilk bütçeden farklı olanlar">
          <input type="checkbox" className="accent-primary" checked={revize} onChange={(e) => revizeAyarla(e.target.checked)} />
          Yalnız revize edilenler
        </label>
        {/* Sayaç: sayfadaki yüklü verinin toplamı (API'de ayrı fiyatsız sayısı yok; süzgeç açıkken toplam zaten fiyatsız sayısıdır). */}
        <span className="ml-auto text-sm text-muted-foreground tabular-nums">
          {sorgu.data ? (fiyatsiz ? `${toplam} fiyatsız malzeme` : `${toplam} malzeme`) : ""}
        </span>
      </div>

      {mesaj && (
        <p role="status" className="rounded-md bg-muted p-2 text-sm">
          {mesaj}
        </p>
      )}

      <VeriTablosu
        veri={gorunen}
        sutunlar={sutunlar}
        yukleniyor={sorgu.isLoading}
        hata={(sorgu.error as ApiHatasi | null) ?? null}
        bosMetin="Malzeme bulunamadı"
      />

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

      {duzenlenen && senaryoId != null && (
        <DegerDiyalogu
          baslik={`Fiyat değiştir: ${duzenlenen.kod}`}
          aciklama={duzenlenen.ad ?? undefined}
          degerEtiketi="Yeni fiyat"
          mevcut={duzenlenen.fiyat ?? ""}
          ozet={(d, t) =>
            `Özet: ${duzenlenen.kod} için ${paraBicimle(d, birim(duzenlenen), 4)} fiyatı ${t.split("-").reverse().join(".")} tarihinden itibaren geçerli olacak.`
          }
          gonderiliyor={ekle.isPending}
          hata={hataMetniVarsa(ekle.error)}
          onKapat={() => {
            ekle.reset();
            setDuzenlenen(null);
          }}
          onGonder={(v) =>
            ekle.mutate(
              {
                kod: duzenlenen.kod,
                senaryo: senaryoId,
                govde: {
                  fiyat: v.deger,
                  gecerlilik_basi: v.tarih,
                  neden: v.neden,
                  para_birimi: duzenlenen.para_birimi ?? "TL",
                  onay: false,
                },
              },
              {
                onSuccess: () => {
                  setMesaj(`${duzenlenen.kod} fiyatı kaydedildi.`);
                  setDuzenlenen(null);
                },
              },
            )
          }
        />
      )}
      {ekle.onayDiyalogu}

      {gecmisMalzeme && senaryoId != null && (
        <FiyatGecmisiPaneli
          malzeme={gecmisMalzeme}
          senaryo={senaryoId}
          kilitli={kilitli}
          onKapat={() => setGecmisMalzeme(null)}
          onBasari={setMesaj}
        />
      )}

      {yukle && senaryoId != null && <FiyatListesiYukle senaryo={senaryoId} onKapat={() => setYukle(false)} onBasari={setMesaj} />}
    </section>
  );
}
