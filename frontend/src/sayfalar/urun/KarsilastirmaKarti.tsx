import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useSatisGecmisi } from "@/api/sorgular/satis";
import { useUrunKarsilastirma } from "@/api/sorgular/karsilastirma";
import type { EnflasyonPb, GecenYil, UretimEtkisi } from "@/api/tipler";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { paraBicimle, yuzdeBicimle, D } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { EnflasyonRozeti } from "../karsilastirma/EnflasyonRozeti";

interface Props {
  kod: string;
  senaryoId: number | null;
  /** Hesap tarihi (boşsa sunucu varsayılanı). Taslak değişikliği karta yansımaz: kart yalnız sunucu değerleriyle çalışır. */
  tarih: string;
}

const adet = (s: string) => paraBicimle(s, "", 0);
const basamakOf = (pb: string) => (pb === "TL" ? 2 : 3);

function Bolum({ baslik, children }: { baslik: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <h3 className="text-sm font-semibold">{baslik}</h3>
      {children}
    </div>
  );
}

function Bos({ children }: { children: ReactNode }) {
  return <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm text-muted-foreground">{children}</p>;
}

function GecenYilBolumu({ veri, senaryoId }: { veri: GecenYil | null; senaryoId: number | null }) {
  if (!veri) {
    return (
      <Bos>
        Satış geçmişi yok —{" "}
        <Link to={`/satis-gecmisi${senaryoId ? `?senaryo=${senaryoId}` : ""}`} className="text-primary underline-offset-4 hover:underline">
          Satış Geçmişi sayfasından yükleyin
        </Link>
      </Bos>
    );
  }
  return (
    <>
      <p className="text-xs text-muted-foreground">
        {goster(veri.donem_basi)} – {goster(veri.donem_sonu)} · {veri.kayit_sayisi} kayıt · {veri.musteri_sayisi} müşteri
      </p>
      <Table aria-label="Geçen yıl ortalama fiyat">
        <TableHeader>
          <TableRow>
            <TableHead>Para birimi</TableHead>
            <TableHead className="text-right">Ort. fiyat</TableHead>
            <TableHead className="text-right">Adet</TableHead>
            <TableHead className="text-right">Müşteri</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Object.entries(veri.para_birimleri).map(([pb, v]) => (
            <TableRow key={pb}>
              <TableCell>{pb}</TableCell>
              <TableCell>
                <ParaHucresi deger={v.fiyat} paraBirimi={pb} basamak={basamakOf(pb)} />
              </TableCell>
              <TableCell className="text-right tabular-nums">{adet(v.adet)}</TableCell>
              <TableCell className="text-right tabular-nums">{v.musteri_sayisi}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

function EnflasyonBolumu({ veri, hata }: { veri: Record<string, EnflasyonPb> | null; hata: string | null | undefined }) {
  if (!veri || Object.keys(veri).length === 0) {
    return (
      <Bos>{hata ? `Hesap yapılamadı: ${hata}` : "Enflasyon karşılaştırması için geçen yılın satışı ve güncel satış fiyatı gerekir."}</Bos>
    );
  }
  return (
    <Table aria-label="Enflasyon eşiği">
      <TableHeader>
        <TableRow>
          <TableHead>Para birimi</TableHead>
          <TableHead className="text-right">Geçen yıl</TableHead>
          <TableHead className="text-right">Yeni</TableHead>
          <TableHead className="text-right">Oran</TableHead>
          <TableHead className="text-right">Fark</TableHead>
          <TableHead>Durum</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {Object.entries(veri).map(([pb, v]) => (
          <TableRow key={pb}>
            <TableCell>{pb}</TableCell>
            <TableCell>
              <ParaHucresi deger={v.gecen_yil} paraBirimi={pb} basamak={basamakOf(pb)} />
            </TableCell>
            <TableCell>
              <ParaHucresi deger={v.yeni} paraBirimi={pb} basamak={basamakOf(pb)} />
            </TableCell>
            <TableCell className="text-right tabular-nums">{paraBicimle(v.oran, "×", 3)}</TableCell>
            <TableCell className="text-right tabular-nums">{yuzdeBicimle(D(v.fark_yuzde).div(100), 1)}</TableCell>
            <TableCell>
              <EnflasyonRozeti durum={v.durum} />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function HedefBolumu({ veri, senaryoId }: { veri: UretimEtkisi | null; senaryoId: number | null }) {
  if (!veri) {
    return (
      <Bos>
        Hedef adet tanımlı değil —{" "}
        <Link
          to={`/uretim-adetleri${senaryoId ? `?senaryo=${senaryoId}` : ""}`}
          className="text-primary underline-offset-4 hover:underline"
        >
          Üretim Adetleri sayfasından girin
        </Link>
      </Bos>
    );
  }
  const satirlar: {
    etiket: string;
    tl: string | null;
    usd: string | null;
    eur: string | null;
  }[] = [
    {
      etiket: "Maliyet (bütçe adedi)",
      tl: veri.maliyet_tl_butce,
      usd: veri.maliyet_usd_butce,
      eur: veri.maliyet_eur_butce,
    },
    {
      etiket: "Maliyet (hedef adedi)",
      tl: veri.maliyet_tl_hedef,
      usd: veri.maliyet_usd_hedef,
      eur: veri.maliyet_eur_hedef,
    },
    {
      etiket: "Satış (bütçe adedi)",
      tl: veri.satis_tl_butce,
      usd: veri.satis_usd_butce,
      eur: veri.satis_eur_butce,
    },
    {
      etiket: "Satış (hedef adedi)",
      tl: veri.satis_tl_hedef,
      usd: veri.satis_usd_hedef,
      eur: veri.satis_eur_hedef,
    },
  ];
  return (
    <>
      <p className="text-sm">
        Bütçe adedi <strong className="tabular-nums">{adet(veri.butce_adedi)}</strong> · Hedef adedi{" "}
        <strong className="tabular-nums">{adet(veri.hedef_adedi)}</strong>
        {veri.oran != null && (
          <>
            {" "}
            · Oran <strong className="tabular-nums">{paraBicimle(veri.oran, "×", 2)}</strong>
          </>
        )}
      </p>
      <Table aria-label="Hedef adetle maliyet ve satış">
        <TableHeader>
          <TableRow>
            <TableHead>Kalem</TableHead>
            <TableHead className="text-right">TL</TableHead>
            <TableHead className="text-right">USD</TableHead>
            <TableHead className="text-right">EUR</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {satirlar.map((s) => (
            <TableRow key={s.etiket}>
              <TableCell>{s.etiket}</TableCell>
              <TableCell>
                <ParaHucresi deger={s.tl} />
              </TableCell>
              <TableCell>
                <ParaHucresi deger={s.usd} paraBirimi="USD" basamak={3} />
              </TableCell>
              <TableCell>
                <ParaHucresi deger={s.eur} paraBirimi="EUR" basamak={3} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

/** Ürün ekranı karşılaştırma kartı: geçen yıl, enflasyon eşiği, hedef adetle (yalnız sunucu değerleri). */
export function KarsilastirmaKarti({ kod, senaryoId, tarih }: Props) {
  const [musteri, setMusteri] = useState("");
  const sorgu = useUrunKarsilastirma(kod, senaryoId, tarih, musteri);
  // Müşteri listesi ürünün satış geçmişinden türetilir (süzgeçten bağımsız, seçim yapılınca liste daralmaz).
  const satislar = useSatisGecmisi({ urun_kodu: kod, boyut: 500 });
  const musteriler = useMemo(
    () => [...new Set((satislar.data?.kayitlar ?? []).map((s) => s.musteri))].sort((a, b) => a.localeCompare(b, "tr")),
    [satislar.data],
  );
  const hata = sorgu.error as ApiHatasi | null;
  const veri = sorgu.data;

  return (
    <section aria-label="Karşılaştırma" className="flex flex-col gap-4 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Karşılaştırma</h2>
        {(musteriler.length > 0 || musteri) && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Müşteri süzgeci</span>
            <select
              aria-label="Müşteri süzgeci"
              value={musteri}
              onChange={(e) => setMusteri(e.target.value)}
              className="h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">Tüm müşteriler</option>
              {musteriler.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {hata ? (
        <div role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </div>
      ) : sorgu.isPending ? (
        <div role="status" aria-label="Yükleniyor" className="flex flex-col gap-2">
          {[0, 1, 2].map((i) => (
            <div key={i} aria-hidden className="h-6 animate-pulse rounded bg-muted" style={{ width: `${90 - i * 10}%` }} />
          ))}
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <Bolum baslik="Geçen yıl">
            <GecenYilBolumu veri={veri?.gecen_yil ?? null} senaryoId={senaryoId} />
          </Bolum>
          <Bolum baslik="Enflasyon eşiği">
            <EnflasyonBolumu veri={veri?.enflasyon_esigi ?? null} hata={veri?.hesap_hatasi} />
          </Bolum>
          <Bolum baslik="Hedef adetle">
            <HedefBolumu veri={veri?.uretim_adedi_etkisi ?? null} senaryoId={senaryoId} />
          </Bolum>
        </div>
      )}
    </section>
  );
}
