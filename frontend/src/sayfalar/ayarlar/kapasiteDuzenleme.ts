import { useState } from "react";
import { useKapasiteKaydet } from "@/api/sorgular/kapasite";
import type { KapasiteKaydi } from "@/api/tipler";
import { sayiApi, sayiGecerli } from "@/yardimcilar/sayi";

export type KapasiteAlani = "net_kapasite" | "net_sure" | "toplam_kapasite" | "toplam_sure" | "hedef_uretim" | "ortalama_isci";

/** Excel `Üretim Adetleri` sütunları (sıra Excel ile aynı). */
export const KAPASITE_ALANLARI: { anahtar: KapasiteAlani; etiket: string }[] = [
  { anahtar: "net_kapasite", etiket: "Net kapasite" },
  { anahtar: "net_sure", etiket: "Net süre" },
  { anahtar: "toplam_kapasite", etiket: "Toplam kapasite" },
  { anahtar: "toplam_sure", etiket: "Toplam süre" },
  { anahtar: "hedef_uretim", etiket: "Hedef üretim" },
  { anahtar: "ortalama_isci", etiket: "Ortalama işçi" },
];

/** Sayı gösterimi: en çok 2 ondalık (Intl'e metin verilir, Number() ile hassasiyet kaybı olmaz). */
export function kapasiteSayisi(metin: string): string {
  return new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 }).format(metin as unknown as number);
}

export interface KapasiteDuzenleme {
  urunKodu: string;
  degerler: Record<KapasiteAlani, string>;
  neden: string;
}

/**
 * Bir ürünün kapasite satırını düzenleme durumu ve kaydı: Üretim Adetleri (satır içi) ve Veri Girişi (kart) aynı mantığı kullanır.
 * Neden zorunlu; tüm alanlar sayı olmalı; kayıt `useKapasiteKaydet` ile gider.
 */
export function useKapasiteDuzenleme(senaryoId: number | null) {
  const kaydet = useKapasiteKaydet();
  const [duzenleme, setDuzenleme] = useState<KapasiteDuzenleme | null>(null);

  function basla(k: KapasiteKaydi) {
    kaydet.reset();
    setDuzenleme({
      urunKodu: k.urun_kodu,
      degerler: Object.fromEntries(KAPASITE_ALANLARI.map((a) => [a.anahtar, k[a.anahtar]])) as Record<KapasiteAlani, string>,
      neden: "",
    });
  }
  function alanDegistir(alan: KapasiteAlani, deger: string) {
    setDuzenleme((d) => (d ? { ...d, degerler: { ...d.degerler, [alan]: deger } } : d));
  }
  function nedenDegistir(neden: string) {
    setDuzenleme((d) => (d ? { ...d, neden } : d));
  }
  const hatalar = duzenleme
    ? KAPASITE_ALANLARI.filter((a) => !sayiGecerli(duzenleme.degerler[a.anahtar])).map((a) => `${a.etiket} sayı olmalı`)
    : [];
  const kaydedilebilir = !!duzenleme && senaryoId !== null && hatalar.length === 0 && duzenleme.neden.trim() !== "" && !kaydet.isPending;

  function gonder(onBasari: (urunKodu: string) => void) {
    if (!duzenleme || !kaydedilebilir || senaryoId === null) return;
    const govde = {
      ...(Object.fromEntries(KAPASITE_ALANLARI.map((a) => [a.anahtar, sayiApi(duzenleme.degerler[a.anahtar]) ?? "0"])) as Record<KapasiteAlani, string>),
      neden: duzenleme.neden.trim(),
    };
    const urunKodu = duzenleme.urunKodu;
    kaydet.mutate(
      { urunKodu, senaryo: senaryoId, govde },
      {
        onSuccess: () => {
          onBasari(urunKodu);
          setDuzenleme(null);
        },
      },
    );
  }

  return { duzenleme, basla, alanDegistir, nedenDegistir, iptal: () => setDuzenleme(null), hatalar, kaydedilebilir, gonder, kaydet };
}
