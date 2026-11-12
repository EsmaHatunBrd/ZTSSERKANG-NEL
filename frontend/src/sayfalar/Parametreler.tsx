import { useMemo, useState } from "react";
import { History, Lock, Pencil, ToggleLeft, ToggleRight } from "lucide-react";
import { useParametreEkle, useParametreGecmisi, useParametreler, useParametreTanimlari } from "@/api/sorgular/parametreler";
import type { ParametreTanimi } from "@/api/tipler";
import { GecmisCekmecesi } from "@/bilesenler/GecmisCekmecesi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { bugunIso, goster } from "@/yardimcilar/tarih";
import { GeriAlOnayi } from "./ayarlar/GeriAlOnayi";
import { hataMetniVarsa } from "@/api/istemci";
import { degerMetni, ParametreDiyalogu } from "./ayarlar/ParametreDiyalogu";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { Girdi } from "@/bilesenler/Girdi";
import { acikMi, EVET_HAYIR_BIRIMI } from "./ayarlar/ortak";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";

interface Grup {
  baslik: string;
  eslesir: (anahtar: string) => boolean;
  saltOkunur?: boolean;
}

const GRUPLAR: Grup[] = [
  { baslik: "Genel", eslesir: (a) => ["enflasyon", "satis_kar", "vardiya_saati", "satis_ortalama_maliyetten"].includes(a) },
  { baslik: "Kurlar", eslesir: (a) => a.startsWith("kur.") },
  { baslik: "Faiz", eslesir: (a) => a.startsWith("faiz.") },
  { baslik: "Stok süresi", eslesir: (a) => a.startsWith("stok_ay.") },
  { baslik: "Teklif kâr oranları", eslesir: (a) => a.startsWith("teklif_kar.") },
  { baslik: "Dağıtım çarpanları", eslesir: (a) => a.startsWith("dagitim_carpani."), saltOkunur: true },
];
const DIGER: Grup = { baslik: "Diğer", eslesir: () => true };

/** Geçmiş çekmecesi; geri al = onaydan sonra eski değeri bugünden geçerli YENİ kayıt olarak ekler. Kilitliyse yalnız görüntülenir. */
function GecmisPaneli({
  anahtar,
  birim,
  senaryo,
  kilitli,
  onKapat,
  onBasari,
}: {
  anahtar: string;
  birim: string | null;
  senaryo: number;
  kilitli: boolean;
  onKapat: () => void;
  onBasari: (m: string) => void;
}) {
  const gecmis = useParametreGecmisi(anahtar, senaryo);
  const ekle = useParametreEkle();
  const kayitlar = useMemo(
    () => (gecmis.data?.kayitlar ?? []).map((k) => ({ ...k, olusturma_zamani: k.olusturma_zamani ?? "" })),
    [gecmis.data],
  );
  const [bekleyen, setBekleyen] = useState<{ k: (typeof kayitlar)[number]; neden: string } | null>(null);

  function onayla() {
    if (!bekleyen) return;
    const { k, neden } = bekleyen;
    ekle.mutate(
      {
        anahtar,
        senaryo,
        govde: {
          deger: k.deger,
          gecerlilik_basi: bugunIso(),
          neden,
          kapsam_tipi: k.kapsam_tipi === "urun" ? "urun" : "genel",
          kapsam_id: k.kapsam_id ?? null,
        },
      },
      {
        onSuccess: () => {
          onBasari(`${anahtar} değeri geri alındı (yeni kayıt olarak eklendi).`);
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
        baslik={`Parametre geçmişi: ${anahtar}${kilitli ? " (kilitli: gerçekleşen senaryoda geri alınamaz)" : ""}`}
        kayitlar={kayitlar}
        degerGoster={(d) => degerMetni(d, birim)}
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
          metin={`${goster(bekleyen.k.gecerlilik_basi)} tarihli ${degerMetni(bekleyen.k.deger, birim)} değeri bugünden itibaren geçerli olacak.`}
          hata={hataMetniVarsa(ekle.error)}
          bekliyor={ekle.isPending}
          onOnayla={onayla}
          onVazgec={() => {
            ekle.reset();
            setBekleyen(null);
          }}
        />
      )}
    </>
  );
}

/** Açık/kapalı parametreyi tersine çevirme onayı: bugünden geçerli, tüm ürünler; neden zorunlu. */
function AcKapaOnayi({
  tanim,
  yeniAcik,
  bekliyor,
  hata,
  onOnayla,
  onVazgec,
}: {
  tanim: ParametreTanimi;
  yeniAcik: boolean;
  bekliyor: boolean;
  hata: string | null;
  onOnayla: (neden: string) => void;
  onVazgec: () => void;
}) {
  const [neden, setNeden] = useState("");
  const [denendi, setDenendi] = useState(false);
  const eksik = denendi && !neden.trim();
  return (
    <OnayDiyalogu
      baslik={`${tanim.aciklama ?? tanim.anahtar}: ${yeniAcik ? "Aç" : "Kapat"}`}
      onayMetni={bekliyor ? "Kaydediliyor…" : yeniAcik ? "Aç" : "Kapat"}
      bekliyor={bekliyor}
      hata={hata}
      onVazgec={onVazgec}
      onOnayla={() => {
        setDenendi(true);
        if (neden.trim()) onOnayla(neden.trim());
      }}
    >
      <p>
        Özet: <strong>{tanim.anahtar}</strong> bugünden itibaren tüm ürünler için <strong>{yeniAcik ? "Açık" : "Kapalı"}</strong> olacak.
      </p>
      <label htmlFor="ac-kapa-neden" className="font-medium">
        Neden (zorunlu)
      </label>
      <Girdi id="ac-kapa-neden" value={neden} aria-invalid={eksik} onChange={(e) => setNeden(e.target.value)} />
      {eksik && (
        <p role="alert" className="text-xs text-destructive">
          Neden zorunlu
        </p>
      )}
    </OnayDiyalogu>
  );
}

export default function Parametreler() {
  const { senaryoId, senaryo, kilitli: senaryoKilitli } = useSenaryo();
  const tanimlar = useParametreTanimlari();
  const degerler = useParametreler(senaryoId);
  const ekle = useParametreEkle();
  const [duzenlenen, setDuzenlenen] = useState<ParametreTanimi | null>(null);
  const [gecmis, setGecmis] = useState<ParametreTanimi | null>(null);
  const [acKapa, setAcKapa] = useState<ParametreTanimi | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);

  const gerceklesen = senaryo?.tur === "gerceklesen";
  const yukleniyor = tanimlar.isLoading || degerler.isLoading;
  const hata = tanimlar.error ?? degerler.error;

  const gruplu = useMemo(() => {
    const tanimListesi: ParametreTanimi[] = [...(tanimlar.data?.kayitlar ?? [])];
    const bilinen = new Set(tanimListesi.map((t) => t.anahtar));
    for (const a of Object.keys(degerler.data ?? {})) {
      if (!bilinen.has(a)) tanimListesi.push({ anahtar: a, aciklama: null, birim: null });
    }
    const harita = new Map<Grup, ParametreTanimi[]>();
    for (const t of tanimListesi) {
      const g = GRUPLAR.find((x) => x.eslesir(t.anahtar)) ?? DIGER;
      harita.set(g, [...(harita.get(g) ?? []), t]);
    }
    return [...GRUPLAR, DIGER].filter((g) => harita.has(g)).map((g) => ({ grup: g, satirlar: harita.get(g) ?? [] }));
  }, [tanimlar.data, degerler.data]);

  return (
    <section className="flex flex-col gap-4">
      <SayfaBasligi baslik="Parametreler" />
      <KilitSeridi />

      {mesaj && (
        <p role="status" className="rounded-md bg-muted p-2 text-sm">
          {mesaj}
        </p>
      )}
      {hata && (
        <p role="alert" className="text-destructive">
          {hata.message}
        </p>
      )}
      {yukleniyor && (
        <p role="status" className="text-muted-foreground">
          Yükleniyor…
        </p>
      )}
      {!yukleniyor && !hata && gruplu.length === 0 && <p className="text-muted-foreground">Parametre bulunamadı.</p>}

      {gruplu.map(({ grup, satirlar }) => (
        <section key={grup.baslik} aria-labelledby={`g-${grup.baslik}`} className="flex flex-col gap-2">
          <h2 id={`g-${grup.baslik}`} className="flex items-center gap-2 text-lg font-medium">
            {grup.baslik}
            {grup.saltOkunur && <Badge variant="secondary">Faz 3</Badge>}
          </h2>
          {grup.saltOkunur && (
            <p className="text-sm text-muted-foreground">Salt okunur: dağıtım çarpanları Faz 3 kapsamında yönetilecek.</p>
          )}
          <Table className="table-fixed">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[55%]">Parametre</TableHead>
                <TableHead className="w-[20%] text-right">Geçerli değer</TableHead>
                <TableHead className="w-[25%]">İşlem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {satirlar.map((t) => {
                const deger = degerler.data?.[t.anahtar];
                const kilitli = gerceklesen && t.anahtar === "enflasyon";
                return (
                  <TableRow key={t.anahtar}>
                    <TableCell className="whitespace-normal">
                      <span className="block font-medium">{t.aciklama ?? t.anahtar}</span>
                      {/* Teknik ad: Excel/destek için küçük ve soluk */}
                      <span className="block font-mono text-xs text-muted-foreground">{t.anahtar}</span>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {t.birim === EVET_HAYIR_BIRIMI ? (
                        <Badge variant={acikMi(deger) ? "default" : "outline"}>{acikMi(deger) ? "Açık" : "Kapalı"}</Badge>
                      ) : deger === undefined ? (
                        "—"
                      ) : (
                        degerMetni(deger, t.birim)
                      )}
                    </TableCell>
                    <TableCell>
                      {grup.saltOkunur ? (
                        <span className="text-xs text-muted-foreground">Salt okunur</span>
                      ) : (
                        <span className="flex flex-wrap items-center gap-1">
                          {kilitli ? (
                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                              <Lock className="size-3" aria-hidden />
                              Gerçekleşen senaryoda enflasyon kilitlidir: gerçekleşen değerler sonradan değiştirilemez.
                            </span>
                          ) : t.birim === EVET_HAYIR_BIRIMI ? (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              role="switch"
                              aria-checked={acikMi(deger)}
                              aria-label={`Aç/Kapat ${t.anahtar}`}
                              disabled={senaryoKilitli}
                              onClick={() => {
                                ekle.reset();
                                setAcKapa(t);
                              }}
                            >
                              {acikMi(deger) ? <ToggleRight className="text-primary" /> : <ToggleLeft />}
                              {acikMi(deger) ? "Kapat" : "Aç"}
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              aria-label={`Değiştir ${t.anahtar}`}
                              disabled={senaryoKilitli}
                              onClick={() => {
                                ekle.reset();
                                setDuzenlenen(t);
                              }}
                            >
                              <Pencil /> Değiştir
                            </Button>
                          )}
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            aria-label={`Geçmiş ${t.anahtar}`}
                            title="Değişiklik geçmişi"
                            onClick={() => setGecmis(t)}
                          >
                            <History />
                          </Button>
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </section>
      ))}

      {duzenlenen && senaryoId != null && (
        <ParametreDiyalogu
          tanim={duzenlenen}
          mevcut={degerler.data?.[duzenlenen.anahtar] ?? ""}
          senaryo={senaryoId}
          gonderiliyor={ekle.isPending}
          hata={hataMetniVarsa(ekle.error)}
          onKapat={() => setDuzenlenen(null)}
          onGonder={(v) =>
            ekle.mutate(
              {
                anahtar: duzenlenen.anahtar,
                senaryo: senaryoId,
                govde: {
                  deger: v.deger,
                  gecerlilik_basi: v.tarih,
                  neden: v.neden,
                  kapsam_tipi: v.kapsam_tipi,
                  ...(v.kapsam_tipi === "urun" ? { kapsam_id: v.kapsam_id } : {}),
                },
              },
              {
                onSuccess: () => {
                  setMesaj(`${duzenlenen.anahtar} değeri kaydedildi.`);
                  setDuzenlenen(null);
                },
              },
            )
          }
        />
      )}

      {acKapa && senaryoId != null && (
        <AcKapaOnayi
          tanim={acKapa}
          yeniAcik={!acikMi(degerler.data?.[acKapa.anahtar])}
          bekliyor={ekle.isPending}
          hata={hataMetniVarsa(ekle.error)}
          onVazgec={() => setAcKapa(null)}
          onOnayla={(neden) => {
            const yeniAcik = !acikMi(degerler.data?.[acKapa.anahtar]);
            ekle.mutate(
              {
                anahtar: acKapa.anahtar,
                senaryo: senaryoId,
                govde: { deger: yeniAcik ? "1" : "0", gecerlilik_basi: bugunIso(), neden, kapsam_tipi: "genel" },
              },
              {
                onSuccess: () => {
                  setMesaj(`${acKapa.anahtar} ${yeniAcik ? "açıldı" : "kapatıldı"}.`);
                  setAcKapa(null);
                },
              },
            );
          }}
        />
      )}

      {gecmis && senaryoId != null && (
        <GecmisPaneli
          anahtar={gecmis.anahtar}
          birim={gecmis.birim}
          senaryo={senaryoId}
          kilitli={senaryoKilitli || (gerceklesen && gecmis.anahtar === "enflasyon")}
          onKapat={() => setGecmis(null)}
          onBasari={setMesaj}
        />
      )}
    </section>
  );
}
