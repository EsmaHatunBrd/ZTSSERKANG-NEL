/** Ctrl+K hızlı arama: istemci tarafı süzme (Türkçe küçük harf, kod ve ad içinde geçen). */
export interface AramaOgesi {
  tur: "urun" | "malzeme";
  kod: string;
  ad: string;
}

export interface AramaSonucu extends AramaOgesi {
  yol: string;
}

function normalize(s: string): string {
  return s.trim().toLocaleLowerCase("tr");
}

/** Sorgu boşsa boş liste; önce kodu sorguyla BAŞLAYANLAR, sonra içerenler; her türden en çok `sinir` sonuç. */
export function aramaSuz(sorgu: string, ogeler: AramaOgesi[], senaryoId: number | null, sinir = 8): AramaSonucu[] {
  const q = normalize(sorgu);
  if (q.length < 2) return [];
  const puanla = (o: AramaOgesi): number => {
    const kod = normalize(o.kod);
    const ad = normalize(o.ad);
    if (kod.startsWith(q)) return 0;
    if (kod.includes(q)) return 1;
    if (ad.startsWith(q)) return 2;
    if (ad.includes(q)) return 3;
    return -1;
  };
  const yol = (o: AramaOgesi): string => {
    const sen = senaryoId === null ? "" : `senaryo=${senaryoId}`;
    if (o.tur === "urun") return `/urunler/${encodeURIComponent(o.kod)}${sen ? `?${sen}` : ""}`;
    return `/fiyatlar?${sen ? `${sen}&` : ""}arama=${encodeURIComponent(o.kod)}`;
  };
  const sonuc: AramaSonucu[] = [];
  for (const tur of ["urun", "malzeme"] as const) {
    const adaylar = ogeler
      .filter((o) => o.tur === tur)
      .map((o) => ({ o, p: puanla(o) }))
      .filter((x) => x.p >= 0)
      .sort((a, b) => a.p - b.p || a.o.kod.localeCompare(b.o.kod, "tr"))
      .slice(0, sinir);
    for (const { o } of adaylar) sonuc.push({ ...o, yol: yol(o) });
  }
  return sonuc;
}
