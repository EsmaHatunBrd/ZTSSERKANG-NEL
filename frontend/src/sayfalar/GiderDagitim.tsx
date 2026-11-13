import { useState } from "react";
import { useAmbalajKaydet, useAmbalajlar, useGiderHavuzlari, useHavuzKaydet } from "@/api/sorgular/gider";
import type { GiderHavuzu } from "@/api/tipler";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Button } from "@/bilesenler/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { AmbalajDiyalogu } from "./ayarlar/AmbalajDiyalogu";
import { HavuzDiyalogu, havuzGovdesi } from "./ayarlar/HavuzDiyalogu";
import { HavuzKarti } from "./ayarlar/HavuzKarti";
import { hataMetniVarsa } from "@/api/istemci";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KilitSeridi } from "@/bilesenler/KilitSeridi";
import { DuzenlemeKilidi, useYazmaKilidi } from "@/bilesenler/DuzenlemeKilidi";

export default function GiderDagitim() {
  const { senaryoId } = useSenaryo();
  const { kilitli, neden: kilitNedeni } = useYazmaKilidi();
  const havuzlar = useGiderHavuzlari(senaryoId);
  const ambalajlar = useAmbalajlar(senaryoId);
  const havuzKaydet = useHavuzKaydet();
  const ambalajKaydet = useAmbalajKaydet();
  const [duzenlenen, setDuzenlenen] = useState<GiderHavuzu | null>(null);
  const [ambalajAcik, setAmbalajAcik] = useState(false);
  const [mesaj, setMesaj] = useState<string | null>(null);

  const payKontrol = new Map((havuzlar.data?.pay_kontrol ?? []).map((p) => [p.havuz, p.toplam]));
  const siniflar = ambalajlar.data?.kayitlar ?? [];

  return (
    <section className="flex flex-col gap-6">
      <SayfaBasligi baslik="Gider Dağıtım" />
      <KilitSeridi />
      <DuzenlemeKilidi />

      {mesaj && (
        <p role="status" className="rounded-md bg-muted p-2 text-sm">
          {mesaj}
        </p>
      )}

      <div className="flex flex-col gap-4">
        <h2 className="text-lg font-medium">Gider havuzları</h2>
        {havuzlar.isLoading && (
          <p role="status" className="text-muted-foreground">
            Yükleniyor…
          </p>
        )}
        {havuzlar.error && (
          <p role="alert" className="text-destructive">
            {havuzlar.error.message}
          </p>
        )}
        {havuzlar.data && havuzlar.data.kayitlar.length === 0 && <p className="text-muted-foreground">Gider havuzu tanımlı değil.</p>}
        {havuzlar.data?.kayitlar.map((h) => (
          <HavuzKarti
            key={h.kod}
            havuz={h}
            payKontrolToplam={payKontrol.get(h.kod)}
            kilitli={kilitli}
            kilitNedeni={kilitNedeni}
            onDuzenle={() => {
              havuzKaydet.reset();
              setDuzenlenen(h);
            }}
          />
        ))}
      </div>

      <section aria-labelledby="ambalaj-baslik" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="ambalaj-baslik" className="text-lg font-medium">
            Ambalaj sınıfları
          </h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!ambalajlar.data || kilitli}
            title={kilitNedeni}
            onClick={() => {
              ambalajKaydet.reset();
              setAmbalajAcik(true);
            }}
          >
            Ambalaj sınıflarını düzenle
          </Button>
        </div>
        {ambalajlar.error && (
          <p role="alert" className="text-destructive">
            {ambalajlar.error.message}
          </p>
        )}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ad</TableHead>
              <TableHead className="text-right">Hacim (ml)</TableHead>
              <TableHead className="text-right">Üretim adedi</TableHead>
              <TableHead className="text-right">Katsayı</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ambalajlar.isLoading && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  Yükleniyor…
                </TableCell>
              </TableRow>
            )}
            {ambalajlar.data && siniflar.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  Ambalaj sınıfı tanımlı değil
                </TableCell>
              </TableRow>
            )}
            {siniflar.map((s) => (
              <TableRow key={s.ad}>
                <TableCell>{s.ad}</TableCell>
                <TableCell className="text-right tabular-nums">{s.hacim}</TableCell>
                <TableCell className="text-right tabular-nums">{s.uretim_adedi}</TableCell>
                <TableCell className="text-right tabular-nums">{s.katsayi}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </section>

      {duzenlenen && senaryoId != null && (
        <HavuzDiyalogu
          havuz={duzenlenen}
          gonderiliyor={havuzKaydet.isPending}
          hata={hataMetniVarsa(havuzKaydet.error)}
          onKapat={() => setDuzenlenen(null)}
          onGonder={(v) =>
            havuzKaydet.mutate(
              {
                kod: duzenlenen.kod,
                senaryo: senaryoId,
                govde: havuzGovdesi(v),
              },
              {
                onSuccess: () => {
                  setMesaj(`${v.ad} kaydedildi.`);
                  setDuzenlenen(null);
                },
              },
            )
          }
        />
      )}

      {ambalajAcik && senaryoId != null && (
        <AmbalajDiyalogu
          siniflar={siniflar}
          gonderiliyor={ambalajKaydet.isPending}
          hata={hataMetniVarsa(ambalajKaydet.error)}
          onKapat={() => setAmbalajAcik(false)}
          onGonder={(v) =>
            ambalajKaydet.mutate(
              { senaryo: senaryoId, govde: v },
              {
                onSuccess: () => {
                  setMesaj(`Ambalaj sınıfları kaydedildi (${v.siniflar.length} sınıf).`);
                  setAmbalajAcik(false);
                },
              },
            )
          }
        />
      )}
    </section>
  );
}
