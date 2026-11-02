import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { useState } from "react";
import { hataMetni } from "@/api/istemci";
import { useKapasite } from "@/api/sorgular/kapasite";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { useSenaryoSayfasi } from "@/yardimcilar/sayfalama";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KAPASITE_ALANLARI as ALANLAR, kapasiteSayisi as sayiBicimle, useKapasiteDuzenleme } from "./ayarlar/kapasiteDuzenleme";

const BOYUT = 50;

/** Excel `Üretim Adetleri` sayfası: ürün başına kapasite, süre, hedef üretim ve ortalama işçi; satır içi düzenleme (neden zorunlu). */
export default function UretimAdetleri() {
  const { senaryoId, kilitli } = useSenaryo();
  const [sayfa, setSayfa] = useSenaryoSayfasi(senaryoId);
  const liste = useKapasite(senaryoId, { sayfa, boyut: BOYUT });
  // Düzenleme durumu/doğrulama/kayıt Veri Girişi sayfasıyla ortak (ayarlar/kapasiteDuzenleme).
  const { duzenleme, basla, alanDegistir, nedenDegistir, iptal, hatalar, kaydedilebilir, gonder, kaydet } = useKapasiteDuzenleme(senaryoId);
  const [durum, setDurum] = useState<string | null>(null);

  if (senaryoId === null) {
    return (
      <section className="p-4">
        <SayfaBasligi baslik="Üretim Adetleri" />
        <p className="mt-2 text-muted-foreground">Başlamak için yukarıdan bir senaryo seçin.</p>
      </section>
    );
  }

  const kayitlar = liste.data?.kayitlar ?? [];
  const toplam = liste.data?.toplam ?? null;
  const sayfaSayisi = Math.max(1, Math.ceil((toplam ?? 0) / BOYUT));

  function kaydetTikla() {
    gonder((kod) => setDurum(`${kod} için üretim adetleri kaydedildi.`));
  }

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaBasligi baslik="Üretim Adetleri" altBaslik="Ürün başına kapasite ve hedef üretim. Her değişiklik bir nedenle kaydedilir ve geçmişte tutulur." />
      <KilitSeridi />

      <div aria-live="polite">
        {durum && (
          <p
            role="status"
            aria-label="Kayıt durumu"
            className="rounded-md bg-green-50 px-3 py-2 text-sm text-green-900 dark:bg-green-950/40 dark:text-green-200"
          >
            {durum}
          </p>
        )}
      </div>
      {liste.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(liste.error)}
        </p>
      )}

      <Table aria-label="Üretim adetleri tablosu">
        <TableHeader>
          <TableRow>
            <TableHead>Ürün kodu</TableHead>
            <TableHead>Ürün</TableHead>
            {ALANLAR.map((a) => (
              <TableHead key={a.anahtar} className="text-right">
                {a.etiket}
              </TableHead>
            ))}
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {liste.isPending ? (
            <TableRow>
              <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                Yükleniyor…
              </TableCell>
            </TableRow>
          ) : kayitlar.length === 0 ? (
            <TableRow>
              <TableCell colSpan={9} className="py-6 text-center text-muted-foreground">
                Kayıt yok
              </TableCell>
            </TableRow>
          ) : (
            kayitlar.map((k) => {
              const acik = duzenleme?.urunKodu === k.urun_kodu;
              return (
                <TableRow key={k.urun_kodu}>
                  <TableCell className="text-muted-foreground">{k.urun_kodu}</TableCell>
                  <TableCell>{k.urun_ad ?? "—"}</TableCell>
                  {ALANLAR.map((a) => (
                    <TableCell key={a.anahtar} className="text-right tabular-nums">
                      {acik && duzenleme ? (
                        <Input
                          aria-label={a.etiket}
                          inputMode="decimal"
                          value={duzenleme.degerler[a.anahtar]}
                          onChange={(e) => alanDegistir(a.anahtar, e.target.value)}
                          className="h-7 w-24 px-1.5 text-right tabular-nums"
                        />
                      ) : (
                        sayiBicimle(k[a.anahtar])
                      )}
                    </TableCell>
                  ))}
                  <TableCell>
                    {acik && duzenleme ? (
                      <div className="flex flex-col gap-2">
                        <Input
                          aria-label="Neden"
                          placeholder="Neden (zorunlu)"
                          value={duzenleme.neden}
                          onChange={(e) => nedenDegistir(e.target.value)}
                          className="h-7 w-48"
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
                          <Button type="button" size="sm" disabled={!kaydedilebilir} onClick={kaydetTikla}>
                            Kaydet
                          </Button>
                          <Button type="button" size="sm" variant="outline" onClick={iptal}>
                            Vazgeç
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        aria-label={`Düzenle — ${k.urun_kodu}`}
                        disabled={kilitli}
                        onClick={() => {
                          setDurum(null);
                          basla(k);
                        }}
                      >
                        Düzenle
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>

      <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
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
    </section>
  );
}
