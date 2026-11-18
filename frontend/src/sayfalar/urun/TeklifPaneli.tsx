import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { useHesapKaydet, useHesaplar, useTeklifEkle, useTeklifler } from "@/api/sorgular/hesaplar";
import { TeklifDurumSecici } from "@/bilesenler/TeklifDurumSecici";
import { TeklifSilDugmesi } from "@/bilesenler/TeklifSilDugmesi";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { apiMetni, D, yuzdeBicimle } from "@/yardimcilar/para";
import { goster } from "@/yardimcilar/tarih";
import { sayiGecerli } from "@/yardimcilar/sayi";
import { teklifDurumAdi } from "@/yardimcilar/teklif";

interface Props {
  kod: string;
  senaryoId: number | null;
  /** Az önce kaydedilen hesap; seçimi buna çeker. */
  sonKayitId: number | null;
}

/** Kayıtlı bir hesap için teklif turları: tur ekleme ve durum değiştirme. */
export function TeklifPaneli({ kod, senaryoId, sonKayitId }: Props) {
  const hesaplar = useHesaplar(kod, senaryoId);
  const [secim, setSecim] = useState<number | null>(null);
  const [kar, setKar] = useState("");
  const [musteri, setMusteri] = useState("");
  const [not, setNot] = useState("");

  useEffect(() => {
    if (sonKayitId !== null) setSecim(sonKayitId);
  }, [sonKayitId]);

  const kayitlar = hesaplar.data?.kayitlar ?? [];
  const hesapId = secim ?? kayitlar[0]?.id ?? null;
  const teklifler = useTeklifler(hesapId);
  const ekle = useTeklifEkle();
  const hesapKaydet = useHesapKaydet();
  const hata = (ekle.error ?? hesapKaydet.error ?? teklifler.error) as ApiHatasi | null;
  // "%17", "17", "17,5" kabul edilir: yüzde işareti ve boşluklar atılır.
  const karSayi = kar.replace(/%/g, "").trim();
  const karGecerli = sayiGecerli(karSayi);
  const pasifNedeni =
    hesapId === null
      ? "Önce güncel hesabı kaydedin"
      : !karSayi
        ? "Kâr oranını yazın (ör. 17)"
        : !karGecerli
          ? "Kâr oranı sayı olmalı (ör. 17 ya da 17,5)"
          : null;

  function hesabiKaydet() {
    if (senaryoId === null) return;
    hesapKaydet.mutate({ kod, govde: { senaryo_id: senaryoId } }, { onSuccess: (y) => setSecim(y.id) });
  }

  function turEkle() {
    if (hesapId === null || !karGecerli) return;
    ekle.mutate(
      {
        hesapId,
        govde: {
          kar_orani: apiMetni(D(karSayi.replace(",", ".")).div(100)),
          musteri: musteri.trim() || null,
          notu: not.trim() || null,
        },
      },
      {
        onSuccess: () => {
          setMusteri("");
          setNot("");
        },
      },
    );
  }

  return (
    <section aria-label="Teklif turları" className="flex flex-col gap-3 rounded-xl border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">Teklif turları</h2>
        <Link
          to={`/teklifler?senaryo=${senaryoId ?? ""}&urun=${encodeURIComponent(kod)}`}
          className="text-sm text-primary underline underline-offset-4"
        >
          Bu ürünün tüm teklifleri
        </Link>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Kayıtlı hesap</span>
          <select
            aria-label="Kayıtlı hesap"
            value={hesapId ?? ""}
            onChange={(e) => setSecim(Number(e.target.value))}
            disabled={kayitlar.length === 0}
            className="h-8 rounded-lg border border-input bg-background px-2 text-sm"
          >
            {kayitlar.length === 0 && <option value="">Kayıtlı hesap yok</option>}
            {kayitlar.map((h) => (
              <option key={h.id} value={h.id}>
                #{h.id} · {goster(h.hesap_tarihi)} · {h.olusturan}
                {h.son_tur_no != null &&
                  ` · Tur ${h.son_tur_no}${h.son_kar_orani != null ? ` · ${yuzdeBicimle(h.son_kar_orani, 1)}` : ""}${h.son_durum ? ` · ${teklifDurumAdi(h.son_durum)}` : ""}`}
              </option>
            ))}
          </select>
        </label>
      </div>

      {hesapId !== null && (
        <Link to={`/hesaplar/${hesapId}`} className="w-fit text-sm text-primary underline-offset-4 hover:underline">
          Kayıtlı hesabı görüntüle
        </Link>
      )}

      {!hesaplar.isPending && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {kayitlar.length === 0 && (
            <span className="text-muted-foreground">Teklif, kaydedilmiş bir hesaba bağlanır. Önce güncel hesabı kaydedin.</span>
          )}
          <Button
            type="button"
            size="sm"
            variant={kayitlar.length === 0 ? "default" : "outline"}
            onClick={hesabiKaydet}
            disabled={senaryoId === null || hesapKaydet.isPending}
            title="Ürünün şu anki maliyetini numaralı bir hesap olarak saklar; teklif turları bu hesaba bağlanır"
          >
            {hesapKaydet.isPending
              ? "Kaydediliyor…"
              : kayitlar.length === 0
                ? "Güncel hesabı kaydet"
                : "Güncel hesabı yeni kayıt olarak kaydet"}
          </Button>
        </div>
      )}

      <form
        className="flex flex-wrap items-end gap-3 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          turEkle();
        }}
      >
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Kâr %</span>
          <Input
            aria-label="Kâr %"
            inputMode="decimal"
            placeholder="ör. 17"
            value={kar}
            onChange={(e) => setKar(e.target.value)}
            className="w-24"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Müşteri</span>
          <Input aria-label="Müşteri" value={musteri} onChange={(e) => setMusteri(e.target.value)} className="w-48" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-muted-foreground">Not</span>
          <Input aria-label="Not" value={not} onChange={(e) => setNot(e.target.value)} className="w-56" />
        </label>
        <Button type="submit" size="sm" disabled={pasifNedeni !== null || ekle.isPending} title={pasifNedeni ?? undefined}>
          Yeni tur
        </Button>
        {pasifNedeni && <span className="pb-1.5 text-xs text-muted-foreground">{pasifNedeni}</span>}
      </form>

      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(hata)}
        </p>
      )}

      <Table aria-label="Teklif turları tablosu">
        <TableHeader>
          <TableRow>
            <TableHead>Tur</TableHead>
            <TableHead className="text-right">Kâr</TableHead>
            <TableHead className="text-right">Fiyat TL</TableHead>
            <TableHead className="text-right">Fiyat USD</TableHead>
            <TableHead>Müşteri</TableHead>
            <TableHead>Durum</TableHead>
            <TableHead className="w-10">
              <span className="sr-only">İşlem</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(teklifler.data?.kayitlar ?? []).length === 0 ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground">
                Henüz teklif turu yok
              </TableCell>
            </TableRow>
          ) : (
            (teklifler.data?.kayitlar ?? []).map((t) => (
              <TableRow key={t.id}>
                <TableCell>Tur {t.tur_no}</TableCell>
                <TableCell className="text-right tabular-nums">{yuzdeBicimle(t.kar_orani, 1)}</TableCell>
                <TableCell>
                  <ParaHucresi deger={t.fiyat_tl} />
                </TableCell>
                <TableCell>
                  <ParaHucresi deger={t.fiyat_usd} paraBirimi="USD" />
                </TableCell>
                <TableCell>{t.musteri ?? "—"}</TableCell>
                <TableCell>
                  <TeklifDurumSecici teklifId={t.id} durum={t.durum} etiket={`Durum — Tur ${t.tur_no}`} />
                </TableCell>
                <TableCell>
                  <TeklifSilDugmesi teklifId={t.id} etiket={`Tur ${t.tur_no}`} durum={t.durum} />
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </section>
  );
}
