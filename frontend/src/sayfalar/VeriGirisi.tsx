import { useId, useMemo, useState } from "react";
import { Coins, Factory, Settings2, Wallet } from "lucide-react";
import { hataMetni, hataMetniVarsa } from "@/api/istemci";
import { useGiderHavuzlari, useHavuzKaydet } from "@/api/sorgular/gider";
import { useKapasite } from "@/api/sorgular/kapasite";
import { useFiyatEkle, useMalzemeler } from "@/api/sorgular/malzemeler";
import {
  useParametreEkle,
  useParametreler,
  useParametreTanimlari,
} from "@/api/sorgular/parametreler";
import type { GiderHavuzu, Malzeme, ParametreTanimi } from "@/api/tipler";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { paraBicimle, type ParaBirimi } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { DegerDiyalogu } from "./ayarlar/DegerDiyalogu";
import { HavuzDiyalogu, havuzGovdesi } from "./ayarlar/HavuzDiyalogu";
import {
  KAPASITE_ALANLARI,
  kapasiteSayisi,
  useKapasiteDuzenleme,
} from "./ayarlar/kapasiteDuzenleme";
import { degerMetni, ParametreDiyalogu } from "./ayarlar/ParametreDiyalogu";
import { Alan, Kart, SELECT } from "./girdi/ortak";
import { UretimBilgileriKarti } from "./girdi/UretimBilgileriKarti";
import { YeniUrunKarti } from "./girdi/YeniUrunKarti";

/** Tek sayfada arama/seçim için üst sınır (API `boyut` en çok 500). */
const LISTE_BOYUTU = 500;
/** Salt okunur parametreler (Parametreler sayfasında da düzenlenmez). */
const SALT_OKUNUR = (anahtar: string) => anahtar.startsWith("dagitim_carpani.");

const malzemeBirimi = (m: Malzeme): ParaBirimi => m.para_birimi?.trim() || "TL";

/* ------------------------------------------------------------------ Gider havuzu */

function HavuzGirisKarti({
  senaryoId,
  kilitli,
  onMesaj,
}: {
  senaryoId: number;
  kilitli: boolean;
  onMesaj: (m: string) => void;
}) {
  const id = useId();
  const havuzlar = useGiderHavuzlari(senaryoId);
  const kaydet = useHavuzKaydet();
  const [kod, setKod] = useState("");
  const [duzenlenen, setDuzenlenen] = useState<GiderHavuzu | null>(null);
  const kayitlar = havuzlar.data?.kayitlar ?? [];
  const secili = kayitlar.find((h) => h.kod === kod) ?? null;
  const payKontrol = havuzlar.data?.pay_kontrol.find((p) => p.havuz === kod);

  return (
    <Kart
      baslik="Gider havuzu"
      tumu={{ yol: "/gider", etiket: "Gider Dağıtım" }}
      aciklama="Havuzu seçin; taban × çarpanlar, alt kalem tutarları ve bazı aynı diyalogdan girilir."
      simge={<Wallet />}
    >
      <Alan etiket="Havuz" htmlFor={`${id}-havuz`}>
        <select
          id={`${id}-havuz`}
          className={SELECT}
          value={kod}
          disabled={kilitli || havuzlar.isLoading}
          onChange={(e) => setKod(e.target.value)}
        >
          <option value="">Seçin…</option>
          {kayitlar.map((h) => (
            <option key={h.kod} value={h.kod}>
              {h.ad} ({h.kod})
            </option>
          ))}
        </select>
      </Alan>
      {havuzlar.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(havuzlar.error)}
        </p>
      )}
      {secili && (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Gider Toplamı</dt>
          <dd className="tabular-nums">
            {paraBicimle(secili.toplam_tutar, "TL", 2)}
            {secili.taban_tutar && secili.carpanlar.length > 0 && (
              <span className="block text-xs text-muted-foreground">
                {paraBicimle(secili.taban_tutar, "", 2)}
                {secili.carpanlar
                  .map((c) => ` × ${c.deger.replace(".", ",")}`)
                  .join("")}
              </span>
            )}
          </dd>
          <dt className="text-muted-foreground">Baz</dt>
          <dd>
            {secili.baz_tipi}
            {secili.baz_miktar
              ? ` · ${paraBicimle(secili.baz_miktar, "", 0)}`
              : ""}
          </dd>
          <dt className="text-muted-foreground">Alt kalem</dt>
          <dd>
            {secili.anahtarlar.length}
            {payKontrol && (
              <Badge variant="destructive" className="ml-2">
                pay toplamı {paraBicimle(payKontrol.toplam, "", 3)}
              </Badge>
            )}
          </dd>
        </dl>
      )}
      <div>
        <Button
          type="button"
          size="sm"
          disabled={!secili || kilitli}
          onClick={() => {
            kaydet.reset();
            setDuzenlenen(secili);
          }}
        >
          Havuzu düzenle
        </Button>
      </div>
      {duzenlenen && (
        <HavuzDiyalogu
          havuz={duzenlenen}
          gonderiliyor={kaydet.isPending}
          hata={hataMetniVarsa(kaydet.error)}
          onKapat={() => setDuzenlenen(null)}
          onGonder={(v) =>
            kaydet.mutate(
              {
                kod: duzenlenen.kod,
                senaryo: senaryoId,
                govde: havuzGovdesi(v),
              },
              {
                onSuccess: () => {
                  onMesaj(`${v.ad} kaydedildi.`);
                  setDuzenlenen(null);
                },
              },
            )
          }
        />
      )}
    </Kart>
  );
}

/* ------------------------------------------------------------------ Malzeme fiyatı */

function FiyatKarti({
  senaryoId,
  kilitli,
  onMesaj,
}: {
  senaryoId: number;
  kilitli: boolean;
  onMesaj: (m: string) => void;
}) {
  const id = useId();
  const sorgu = useMalzemeler(senaryoId, { boyut: LISTE_BOYUTU });
  const ekle = useFiyatEkle();
  const [arama, setArama] = useState("");
  const [duzenlenen, setDuzenlenen] = useState<Malzeme | null>(null);
  const eslesen = useMemo(() => {
    const q = arama.trim().toLocaleLowerCase("tr");
    if (!q) return [];
    return (sorgu.data?.kayitlar ?? [])
      .filter((m) => !m.kart_yok) // kartı olmayan malzemeye fiyat yazılamaz (Malzeme Fiyatları da engeller)
      .filter(
        (m) =>
          m.kod.toLocaleLowerCase("tr").includes(q) ||
          (m.ad ?? "").toLocaleLowerCase("tr").includes(q),
      )
      .slice(0, 8);
  }, [sorgu.data, arama]);
  const eksik = (sorgu.data?.toplam ?? 0) > (sorgu.data?.kayitlar.length ?? 0);

  return (
    <Kart
      baslik="Malzeme fiyatı"
      tumu={{ yol: "/fiyatlar", etiket: "Malzeme Fiyatları" }}
      aciklama="Kod ya da ada göre arayın; yeni fiyat geçerlilik tarihi ve nedenle fiyat geçmişine eklenir."
      simge={<Coins />}
    >
      <Alan etiket="Malzeme ara" htmlFor={`${id}-ara`}>
        <Input
          id={`${id}-ara`}
          type="search"
          placeholder="kod veya ad"
          value={arama}
          disabled={kilitli}
          onChange={(e) => setArama(e.target.value)}
        />
      </Alan>
      {sorgu.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(sorgu.error)}
        </p>
      )}
      {eksik && (
        <p className="text-xs text-muted-foreground">
          Arama ilk {LISTE_BOYUTU} malzemede yapılır; bulamazsanız Malzeme
          Fiyatları sayfasını kullanın.
        </p>
      )}
      {arama.trim() && eslesen.length === 0 && !sorgu.isLoading && (
        <p className="text-sm text-muted-foreground">Eşleşen malzeme yok.</p>
      )}
      {eslesen.length > 0 && (
        <ul className="divide-y rounded-md border text-sm">
          {eslesen.map((m) => (
            <li
              key={m.kod}
              className="flex items-center justify-between gap-2 px-2 py-1.5"
            >
              <span className="min-w-0">
                <span className="font-mono text-xs">{m.kod}</span>
                <span className="ml-2 truncate">{m.ad ?? "—"}</span>
                <span className="block text-xs text-muted-foreground tabular-nums">
                  {m.fiyatsiz
                    ? "Fiyatsız"
                    : paraBicimle(m.fiyat ?? "0", malzemeBirimi(m), 4)}
                  {m.gecerlilik_basi ? ` · ${goster(m.gecerlilik_basi)}` : ""}
                </span>
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                aria-label={`Fiyat gir ${m.kod}`}
                disabled={kilitli}
                onClick={() => {
                  ekle.reset();
                  setDuzenlenen(m);
                }}
              >
                Fiyat gir
              </Button>
            </li>
          ))}
        </ul>
      )}
      {duzenlenen && (
        <DegerDiyalogu
          baslik={`Fiyat değiştir: ${duzenlenen.kod}`}
          aciklama={duzenlenen.ad ?? undefined}
          degerEtiketi="Yeni fiyat"
          mevcut={duzenlenen.fiyat ?? ""}
          ozet={(d, t) =>
            `Özet: ${duzenlenen.kod} için ${paraBicimle(d, malzemeBirimi(duzenlenen), 4)} fiyatı ${goster(t)} tarihinden itibaren geçerli olacak.`
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
                  para_birimi: malzemeBirimi(duzenlenen),
                },
              },
              {
                onSuccess: () => {
                  onMesaj(`${duzenlenen.kod} fiyatı kaydedildi.`);
                  setDuzenlenen(null);
                },
              },
            )
          }
        />
      )}
    </Kart>
  );
}

/* ------------------------------------------------------------------ Parametre */

function ParametreKarti({
  senaryoId,
  kilitli,
  onMesaj,
}: {
  senaryoId: number;
  kilitli: boolean;
  onMesaj: (m: string) => void;
}) {
  const id = useId();
  const { senaryo } = useSenaryo();
  const tanimlar = useParametreTanimlari();
  const degerler = useParametreler(senaryoId);
  const ekle = useParametreEkle();
  const [anahtar, setAnahtar] = useState("");
  const [duzenlenen, setDuzenlenen] = useState<ParametreTanimi | null>(null);
  const liste = useMemo(() => {
    const t: ParametreTanimi[] = (tanimlar.data?.kayitlar ?? []).filter(
      (x) => !SALT_OKUNUR(x.anahtar),
    );
    const bilinen = new Set(t.map((x) => x.anahtar));
    for (const a of Object.keys(degerler.data ?? {}))
      if (!bilinen.has(a) && !SALT_OKUNUR(a))
        t.push({ anahtar: a, aciklama: null, birim: null });
    return t;
  }, [tanimlar.data, degerler.data]);
  const secili = liste.find((t) => t.anahtar === anahtar) ?? null;
  const deger = secili ? degerler.data?.[secili.anahtar] : undefined;
  // Parametreler sayfasıyla aynı kural: gerçekleşen senaryoda enflasyon kilitlidir.
  const enflasyonKilidi =
    senaryo?.tur === "gerceklesen" && anahtar === "enflasyon";
  const hata = tanimlar.error ?? degerler.error;

  return (
    <Kart
      baslik="Parametre"
      tumu={{ yol: "/parametreler", etiket: "Parametreler" }}
      aciklama="Anahtarı seçin; yeni değer geçerlilik tarihi ve nedenle parametre geçmişine eklenir."
      simge={<Settings2 />}
    >
      <Alan etiket="Parametre" htmlFor={`${id}-p`}>
        <select
          id={`${id}-p`}
          className={SELECT}
          value={anahtar}
          disabled={kilitli || tanimlar.isLoading}
          onChange={(e) => setAnahtar(e.target.value)}
        >
          <option value="">Seçin…</option>
          {liste.map((t) => (
            <option key={t.anahtar} value={t.anahtar}>
              {t.anahtar}
              {t.aciklama ? ` — ${t.aciklama}` : ""}
            </option>
          ))}
        </select>
      </Alan>
      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </p>
      )}
      {secili && (
        <p className="text-sm">
          Geçerli değer:{" "}
          <strong className="tabular-nums">
            {deger === undefined ? "—" : degerMetni(deger, secili.birim)}
          </strong>
          {enflasyonKilidi && (
            <span className="block text-xs text-muted-foreground">
              Gerçekleşen senaryoda enflasyon kilitlidir.
            </span>
          )}
        </p>
      )}
      <div>
        <Button
          type="button"
          size="sm"
          disabled={!secili || kilitli || enflasyonKilidi}
          onClick={() => {
            ekle.reset();
            setDuzenlenen(secili);
          }}
        >
          Değeri değiştir
        </Button>
      </div>
      {duzenlenen && (
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
                  ...(v.kapsam_tipi === "urun"
                    ? { kapsam_id: v.kapsam_id }
                    : {}),
                },
              },
              {
                onSuccess: () => {
                  onMesaj(`${duzenlenen.anahtar} değeri kaydedildi.`);
                  setDuzenlenen(null);
                },
              },
            )
          }
        />
      )}
    </Kart>
  );
}

/* ------------------------------------------------------------------ Hat kapasitesi (Üretim Adetleri sayfası) */

function KapasiteKarti({
  senaryoId,
  kilitli,
  onMesaj,
}: {
  senaryoId: number;
  kilitli: boolean;
  onMesaj: (m: string) => void;
}) {
  const id = useId();
  const liste = useKapasite(senaryoId, { boyut: LISTE_BOYUTU });
  const {
    duzenleme,
    basla,
    alanDegistir,
    nedenDegistir,
    iptal,
    hatalar,
    kaydedilebilir,
    gonder,
    kaydet,
  } = useKapasiteDuzenleme(senaryoId);
  const kayitlar = liste.data?.kayitlar ?? [];

  return (
    <Kart
      baslik="Hat kapasitesi (Üretim Adetleri)"
      tumu={{ yol: "/uretim-adetleri", etiket: "Üretim Adetleri" }}
      aciklama="Excel'in Üretim Adetleri sayfasındaki kayıtlar (hedef üretim, net/toplam kapasite, işçi); kayıt kodu o sayfadan gelir. Ürün bazlı üretim adedi için Üretim bilgileri kartını kullanın."
      simge={<Factory />}
    >
      <Alan etiket="Kayıt" htmlFor={`${id}-u`}>
        <select
          id={`${id}-u`}
          className={SELECT}
          value={duzenleme?.urunKodu ?? ""}
          disabled={kilitli || liste.isLoading}
          onChange={(e) => {
            const k = kayitlar.find((x) => x.urun_kodu === e.target.value);
            if (k) basla(k);
            else iptal();
          }}
        >
          <option value="">Seçin…</option>
          {kayitlar.map((k) => (
            <option key={k.urun_kodu} value={k.urun_kodu}>
              {k.urun_kodu}
              {k.urun_ad ? ` — ${k.urun_ad}` : ""}
            </option>
          ))}
        </select>
      </Alan>
      {liste.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(liste.error)}
        </p>
      )}
      {duzenleme && (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {KAPASITE_ALANLARI.map((a) => {
              const mevcut = kayitlar.find(
                (k) => k.urun_kodu === duzenleme.urunKodu,
              )?.[a.anahtar];
              return (
                <div key={a.anahtar} className="flex flex-col gap-1">
                  <label
                    htmlFor={`${id}-${a.anahtar}`}
                    className="text-xs text-muted-foreground"
                  >
                    {a.etiket}
                    {mevcut !== undefined && (
                      <span className="ml-1 tabular-nums">
                        (şu an {kapasiteSayisi(mevcut)})
                      </span>
                    )}
                  </label>
                  <Input
                    id={`${id}-${a.anahtar}`}
                    aria-label={a.etiket}
                    inputMode="decimal"
                    value={duzenleme.degerler[a.anahtar]}
                    disabled={kilitli}
                    onChange={(e) => alanDegistir(a.anahtar, e.target.value)}
                    className="h-8 text-right tabular-nums"
                  />
                </div>
              );
            })}
          </div>
          <Input
            aria-label="Neden"
            placeholder="Neden (zorunlu)"
            value={duzenleme.neden}
            disabled={kilitli}
            onChange={(e) => nedenDegistir(e.target.value)}
            className="h-8"
          />
          {hatalar.map((h) => (
            <p key={h} className="text-xs text-destructive">
              {h}
            </p>
          ))}
          {kaydet.error && (
            <p role="alert" className="text-xs text-destructive">
              {hataMetni(kaydet.error)}
            </p>
          )}
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              disabled={!kaydedilebilir || kilitli}
              onClick={() =>
                gonder((kod) =>
                  onMesaj(`${kod} için üretim adetleri kaydedildi.`),
                )
              }
            >
              Kaydet
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={iptal}>
              Vazgeç
            </Button>
          </div>
        </div>
      )}
    </Kart>
  );
}

/* ------------------------------------------------------------------ Sayfa */

/**
 * Tek sayfada elle veri girişi (muhasebe isteği): gider havuzu, malzeme fiyatı, parametre ve üretim hedefi kartları.
 * Her kart ilgili sayfanın mevcut diyalog/mutasyonunu kullanır; kayıt sonrası sorgular o mutasyonlarca tazelenir.
 */
export default function VeriGirisi() {
  const { senaryoId, kilitli } = useSenaryo();
  const [mesaj, setMesaj] = useState<string | null>(null);

  return (
    <section className="flex flex-col gap-4">
      <SayfaBasligi
        baslik="Veri Girişi"
        altBaslik="Yeni ürün kartı, gider havuzu, malzeme fiyatı, parametre, ürün üretim bilgileri ve hat kapasitesini Excel'e dönmeden tek yerden girin. Her kayıt nedenle günlüğe düşer."
      />
      <KilitSeridi />
      {mesaj && (
        <p role="status" className="rounded-md bg-muted p-2 text-sm">
          {mesaj}
        </p>
      )}
      {senaryoId == null ? (
        <p className="text-muted-foreground">
          Başlamak için yukarıdan bir senaryo seçin.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <YeniUrunKarti senaryoId={senaryoId} onMesaj={setMesaj} />
          <HavuzGirisKarti
            senaryoId={senaryoId}
            kilitli={kilitli}
            onMesaj={setMesaj}
          />
          <FiyatKarti
            senaryoId={senaryoId}
            kilitli={kilitli}
            onMesaj={setMesaj}
          />
          <ParametreKarti
            senaryoId={senaryoId}
            kilitli={kilitli}
            onMesaj={setMesaj}
          />
          <UretimBilgileriKarti
            senaryoId={senaryoId}
            kilitli={kilitli}
            onMesaj={setMesaj}
          />
          <KapasiteKarti
            senaryoId={senaryoId}
            kilitli={kilitli}
            onMesaj={setMesaj}
          />
        </div>
      )}
    </section>
  );
}
