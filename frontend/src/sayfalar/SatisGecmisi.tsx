import { useMemo, useRef, useState, type FormEvent } from "react";
import { Download } from "lucide-react";
import { ApiHatasi, hataMetni, hataMetniVarsa } from "@/api/istemci";
import { useSatisEkle, useSatisGecmisi, useSatisSil, useSatisYukle } from "@/api/sorgular/satis";
import type { SatisKaydi, SatisYuklemeOzeti } from "@/api/tipler";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { VeriTablosu, type SutunTanimi } from "@/bilesenler/VeriTablosu";
import { sayiApi } from "@/yardimcilar/sayi";
import { goster } from "@/yardimcilar/tarih";

const BOYUT = 50;
const PARA_BIRIMLERI = ["TL", "USD", "EUR", "GBP", "CHF", "RUB", "ZAR"] as const;
const SABLON_ADRESI = "/api/v1/satis-gecmisi/sablon.xlsx";
const SELECT_SINIFI =
  "h-8 w-full rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

interface YuklemeHatasi {
  satir_no: number;
  mesaj: string;
}

/** 422 gövdesindeki `alanlar.hatalar` ([{satir_no, mesaj}]) listesini okur; yoksa boş. */
function yuklemeHatalari(e: unknown): YuklemeHatasi[] {
  if (!(e instanceof ApiHatasi) || !Array.isArray(e.alanlar.hatalar)) return [];
  return (e.alanlar.hatalar as YuklemeHatasi[]).filter((h) => typeof h?.satir_no === "number");
}

const BOS_FORM = { urun_kodu: "", musteri: "", tarih: "", fiyat: "", para_birimi: "TL", adet: "" };

function Alan({ etiket, children }: { etiket: string; children: React.ReactNode }) {
  return (
    <label className="flex min-w-32 flex-1 flex-col gap-1 text-sm">
      <span className="text-muted-foreground">{etiket}</span>
      {children}
    </label>
  );
}

/** Satış geçmişi: "geçen yıl kaça sattım" karşılaştırması için ürün başına satış satırları (CSV/xlsx yükleme veya elle satır). */
export default function SatisGecmisi() {
  const [urunKodu, setUrunKodu] = useState("");
  const [musteri, setMusteri] = useState("");
  const [bas, setBas] = useState("");
  const [son, setSon] = useState("");
  const [sayfa, setSayfa] = useState(1);
  const liste = useSatisGecmisi({ urun_kodu: urunKodu.trim(), musteri: musteri.trim(), bas, son, sayfa, boyut: BOYUT });
  const ekle = useSatisEkle();
  const yukle = useSatisYukle();
  const sil = useSatisSil();

  const dosyaRef = useRef<HTMLInputElement>(null);
  const [dosya, setDosya] = useState<File | null>(null);
  const [yuklemeOzeti, setYuklemeOzeti] = useState<SatisYuklemeOzeti | null>(null);
  const [form, setForm] = useState(BOS_FORM);
  const [formHatasi, setFormHatasi] = useState<string | null>(null);
  const [eklendi, setEklendi] = useState(false);
  const [silinecek, setSilinecek] = useState<SatisKaydi | null>(null);

  const kayitlar = liste.data?.kayitlar ?? [];
  const toplam = liste.data?.toplam ?? 0;
  const sayfaSayisi = Math.max(1, Math.ceil(toplam / BOYUT));

  function suzgec(yaz: (v: string) => void) {
    return (v: string) => {
      yaz(v);
      setSayfa(1);
    };
  }

  function yukleTikla() {
    if (!dosya) return;
    setYuklemeOzeti(null);
    yukle.mutate(dosya, {
      onSuccess: (ozet) => {
        setYuklemeOzeti(ozet);
        setDosya(null);
        if (dosyaRef.current) dosyaRef.current.value = "";
      },
    });
  }

  function satirEkle(e: FormEvent) {
    e.preventDefault();
    setEklendi(false);
    const fiyat = sayiApi(form.fiyat);
    const adet = sayiApi(form.adet);
    if (!form.urun_kodu.trim() || !form.musteri.trim() || !form.tarih) return setFormHatasi("Ürün kodu, müşteri ve tarih zorunlu");
    if (fiyat === null) return setFormHatasi("Fiyat sayı olmalı (0 veya büyük)");
    if (adet === null || Number(adet) <= 0) return setFormHatasi("Adet 0'dan büyük bir sayı olmalı");
    setFormHatasi(null);
    ekle.mutate(
      {
        urun_kodu: form.urun_kodu.trim(),
        musteri: form.musteri.trim(),
        tarih: form.tarih,
        fiyat,
        para_birimi: form.para_birimi as (typeof PARA_BIRIMLERI)[number],
        adet,
      },
      {
        onSuccess: () => {
          setEklendi(true);
          setForm({ ...BOS_FORM, para_birimi: form.para_birimi });
        },
      },
    );
  }

  const sutunlar = useMemo<SutunTanimi<SatisKaydi>[]>(
    () => [
      { accessorKey: "urun_kodu", header: "Ürün kodu", cell: (c) => <span className="text-muted-foreground">{c.getValue() as string}</span> },
      { accessorKey: "urun_ad", header: "Ürün" },
      { accessorKey: "musteri", header: "Müşteri" },
      { accessorKey: "tarih", header: "Tarih", cell: (c) => goster(c.getValue() as string) },
      {
        accessorKey: "fiyat",
        header: "Fiyat",
        cell: (c) => <ParaHucresi deger={c.row.original.fiyat} paraBirimi={c.row.original.para_birimi} />,
      },
      {
        accessorKey: "adet",
        header: "Adet",
        cell: (c) => (
          <span className="block text-right tabular-nums">
            {new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 }).format(c.row.original.adet as unknown as number)}
          </span>
        ),
      },
      {
        id: "sil",
        header: () => <span className="sr-only">Sil</span>,
        enableSorting: false,
        cell: (c) => (
          <Button
            type="button"
            size="sm"
            variant="outline"
            aria-label={`Sil — ${c.row.original.urun_kodu} ${goster(c.row.original.tarih)}`}
            onClick={() => {
              sil.reset();
              setSilinecek(c.row.original);
            }}
          >
            Sil
          </Button>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const hatalar = yuklemeHatalari(yukle.error);

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaBasligi
        baslik="Satış Geçmişi"
        altBaslik="Geçen yılın satış fiyatları: şablonla yükleyin veya satırı elle ekleyin. Fiyat karşılaştırmaları bu veriyi kullanır."
        eylemler={
          <a
            href={SABLON_ADRESI}
            download
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-input bg-background px-2.5 text-sm font-medium hover:bg-muted"
          >
            <Download className="size-4" aria-hidden />
            Şablonu indir
          </a>
        }
      />

      <div className="flex flex-wrap items-end gap-2" aria-label="Dosya yükleme">
        <Alan etiket="Dosya (CSV veya xlsx)">
          <Input
            ref={dosyaRef}
            type="file"
            accept=".csv,.xlsx"
            aria-label="Dosya seç"
            onChange={(e) => {
              setDosya(e.target.files?.[0] ?? null);
              setYuklemeOzeti(null);
              yukle.reset();
            }}
          />
        </Alan>
        <Button type="button" disabled={!dosya || yukle.isPending} onClick={yukleTikla}>
          Yükle
        </Button>
      </div>
      <p className="-mt-2 text-xs text-muted-foreground">
        Sayı biçimi: 1234.56 veya 1.234,56; &quot;2.000&quot; (virgülsüz, noktadan sonra 3 hane) belirsiz sayılıp reddedilir. En fazla 20.000 satır.
      </p>
      <div aria-live="polite">
        {yuklemeOzeti && (
          <p role="status" aria-label="Yükleme sonucu" className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-900 dark:bg-green-950/40 dark:text-green-200">
            {yuklemeOzeti.eklenen} satır eklendi.
          </p>
        )}
        {yukle.error && (
          <div role="alert" aria-label="Yükleme hataları" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-900 dark:bg-red-950/40 dark:text-red-200">
            {hatalar.length > 0 ? (
              <>
                <p className="font-medium">Dosyada hatalı satırlar var; hiçbir satır eklenmedi.</p>
                <ul className="mt-1 list-disc pl-5">
                  {hatalar.map((h) => (
                    <li key={h.satir_no}>
                      Satır {h.satir_no}: {h.mesaj}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              hataMetni(yukle.error)
            )}
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-2" role="search" aria-label="Süzgeç">
        <Alan etiket="Ürün kodu">
          <Input value={urunKodu} onChange={(e) => suzgec(setUrunKodu)(e.target.value)} />
        </Alan>
        <Alan etiket="Müşteri">
          <Input value={musteri} onChange={(e) => suzgec(setMusteri)(e.target.value)} />
        </Alan>
        <Alan etiket="Başlangıç tarihi">
          <Input type="date" value={bas} onChange={(e) => suzgec(setBas)(e.target.value)} />
        </Alan>
        <Alan etiket="Bitiş tarihi">
          <Input type="date" value={son} onChange={(e) => suzgec(setSon)(e.target.value)} />
        </Alan>
      </div>

      <VeriTablosu veri={kayitlar} sutunlar={sutunlar} yukleniyor={liste.isPending} hata={liste.error as ApiHatasi | null} bosMetin="Satış kaydı yok" />

      <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
        <span className="mr-auto text-muted-foreground">{toplam} kayıt</span>
        <Button variant="outline" size="sm" disabled={sayfa <= 1} onClick={() => setSayfa(sayfa - 1)}>
          Önceki
        </Button>
        <span aria-live="polite">
          Sayfa {sayfa} / {sayfaSayisi}
        </span>
        <Button variant="outline" size="sm" disabled={sayfa >= sayfaSayisi} onClick={() => setSayfa(sayfa + 1)}>
          Sonraki
        </Button>
      </nav>

      <form onSubmit={satirEkle} aria-label="Satır ekle" className="flex flex-col gap-2 rounded-lg border p-3">
        <h2 className="text-base font-semibold">Satır ekle</h2>
        <div className="flex flex-wrap items-end gap-2">
          <Alan etiket="Ürün kodu *">
            <Input value={form.urun_kodu} onChange={(e) => setForm({ ...form, urun_kodu: e.target.value })} />
          </Alan>
          <Alan etiket="Müşteri *">
            <Input value={form.musteri} onChange={(e) => setForm({ ...form, musteri: e.target.value })} />
          </Alan>
          <Alan etiket="Tarih *">
            <Input type="date" value={form.tarih} onChange={(e) => setForm({ ...form, tarih: e.target.value })} />
          </Alan>
          <Alan etiket="Fiyat *">
            <Input inputMode="decimal" value={form.fiyat} onChange={(e) => setForm({ ...form, fiyat: e.target.value })} />
          </Alan>
          <Alan etiket="Para birimi">
            <select className={SELECT_SINIFI} value={form.para_birimi} onChange={(e) => setForm({ ...form, para_birimi: e.target.value })}>
              {PARA_BIRIMLERI.map((p) => (
                <option key={p}>{p}</option>
              ))}
            </select>
          </Alan>
          <Alan etiket="Adet *">
            <Input inputMode="decimal" value={form.adet} onChange={(e) => setForm({ ...form, adet: e.target.value })} />
          </Alan>
          <Button type="submit" disabled={ekle.isPending}>
            Ekle
          </Button>
        </div>
        {(formHatasi || ekle.error) && (
          <p role="alert" className="text-sm text-destructive">
            {formHatasi ?? hataMetni(ekle.error)}
          </p>
        )}
        {eklendi && (
          <p role="status" aria-label="Ekleme durumu" className="text-sm text-green-800 dark:text-green-300">
            Satır eklendi.
          </p>
        )}
      </form>

      {silinecek && (
        <OnayDiyalogu
          baslik="Satış kaydı silinsin mi?"
          onayMetni="Sil"
          bekliyor={sil.isPending}
          hata={hataMetniVarsa(sil.error)}
          onOnayla={() => sil.mutate(silinecek.id, { onSuccess: () => setSilinecek(null) })}
          onVazgec={() => setSilinecek(null)}
        >
          <p>
            {silinecek.urun_kodu} · {silinecek.musteri} · {goster(silinecek.tarih)} kaydı silinecek. Silinen içerik değişiklik geçmişinde saklanır.
          </p>
        </OnayDiyalogu>
      )}
    </section>
  );
}
