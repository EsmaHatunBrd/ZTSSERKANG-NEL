import { useState } from "react";
import { useUrunler } from "@/api/sorgular/urunler";
import type { Senaryo } from "@/api/tipler";
import { OnayCiktisiDugmesi, type OnayKapsami } from "@/bilesenler/OnayCiktisiDiyalogu";

/** Genel Bakış'taki "Onay çıktısı" düğmesi: seçili çalışma; ürün listesi (çoklu seçim için) yalnız diyalog açıkken yüklenir. */
export function OnayCiktisiFiyatDugmesi({ senaryo }: { senaryo: Senaryo }) {
  const [acik, setAcik] = useState(false);
  const urunler = useUrunler(acik ? senaryo.id : null, { boyut: 500 });
  const kapsam: OnayKapsami = {
    modul: "fiyat",
    senaryoId: senaryo.id,
    senaryoAdi: `${senaryo.sezon_ad} · ${senaryo.ad}`,
    kilitli: Boolean(senaryo.kilitli),
    urunler: (urunler.data?.kayitlar ?? []).map((u) => ({ kod: u.kod, ad: u.ad })),
    urunlerYukleniyor: acik && urunler.isPending,
  };
  return <OnayCiktisiDugmesi kapsam={kapsam} onAc={setAcik} />;
}
