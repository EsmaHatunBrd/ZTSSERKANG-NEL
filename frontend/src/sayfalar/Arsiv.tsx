import { useState } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet, Lock, LockOpen } from "lucide-react";
import { hataMetniVarsa } from "@/api/istemci";
import { useArsiv, useArsivKayitlari, useArsivKiyas, useSenaryoKilidi, type ArsivKiyasi, type ArsivSenaryosu } from "@/api/sorgular/arsiv";
import { KILIT_KAPSAM_NOTU } from "@/bilesenler/KilitSeridi";
import { OnayDiyalogu } from "@/bilesenler/OnayDiyalogu";
import { ParaHucresi } from "@/bilesenler/ParaHucresi";
import { SayfaBasligi } from "@/bilesenler/SayfaBasligi";
import { KIYAS_SEKMELERI, SayfaSekmeleri } from "@/bilesenler/SayfaSekmeleri";
import { useSenaryo } from "@/bilesenler/SenaryoSecici";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";
import { goster } from "@/yardimcilar/tarih";

const BOYUT = 50;
const TUR_ADI: Record<string, string> = { fiyat_calismasi: "Fiyat çalışması", gerceklesen: "Gerçekleşen" };

function KiyasTablosu({ baslik, satirlar }: { baslik: string; satirlar: ArsivKiyasi["toplamlar"] }) {
  return (
    <section aria-label={baslik} className="flex flex-col gap-1">
      <h3 className="text-sm font-medium">{baslik}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Alan</TableHead>
            <TableHead className="text-right">A</TableHead>
            <TableHead className="text-right">B</TableHead>
            <TableHead className="text-right">Fark (B − A)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {satirlar.map((s) => (
            <TableRow key={s.alan}>
              <TableCell>{s.etiket}</TableCell>
              <TableCell>
                <ParaHucresi deger={s.a} basamak={4} />
              </TableCell>
              <TableCell>
                <ParaHucresi deger={s.b} basamak={4} />
              </TableCell>
              <TableCell>
                <ParaHucresi deger={s.fark} basamak={4} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </section>
  );
}

const DURUM_ADI = { ortak: "Her ikisinde", sadece_a: "Yalnız A", sadece_b: "Yalnız B" } as const;

function KiyasKarti({ a, b, onKapat }: { a: number; b: number; onKapat: () => void }) {
  const kiyas = useArsivKiyas(a, b);
  const k = kiyas.data;
  return (
    <section aria-label="Kıyas" className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <header className="flex items-center justify-between gap-2">
        <h2 className="text-lg font-medium">Kayıt kıyası</h2>
        <Button type="button" variant="outline" size="sm" onClick={onKapat}>
          Kıyası kapat
        </Button>
      </header>
      {kiyas.isLoading && (
        <p role="status" className="text-muted-foreground">
          Yükleniyor…
        </p>
      )}
      {kiyas.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetniVarsa(kiyas.error)}
        </p>
      )}
      {k && (
        <>
          {k.uyari && (
            <p
              role="status"
              className="rounded-md border border-amber-300 bg-amber-100 px-3 py-2 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-100"
            >
              {k.uyari}
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                ["A", k.a],
                ["B", k.b],
              ] as const
            ).map(([e, h]) => (
              <div key={e} className="rounded-md border p-3 text-sm">
                <div className="font-medium">
                  {e}: {h.urun_kodu} · {h.urun_ad}
                </div>
                <div className="text-muted-foreground">
                  Hesap tarihi {goster(h.hesap_tarihi)} · {h.olusturan} · kayıt #{h.id}
                </div>
              </div>
            ))}
          </div>
          <KiyasTablosu baslik="Toplamlar" satirlar={k.toplamlar} />
          <KiyasTablosu baslik="Fiyatlar" satirlar={k.fiyatlar} />
          <section aria-label="Malzeme satırları" className="flex flex-col gap-1">
            <h3 className="text-sm font-medium">Reçete satırları (malzeme koduna göre)</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Malzeme</TableHead>
                  <TableHead>Durum</TableHead>
                  <TableHead className="text-right">A tutar</TableHead>
                  <TableHead className="text-right">B tutar</TableHead>
                  <TableHead className="text-right">Fark (B − A)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {k.satirlar.map((s) => (
                  <TableRow key={s.malzeme_kodu}>
                    <TableCell>
                      <div>{s.ad ?? s.malzeme_kodu}</div>
                      <div className="font-mono text-xs text-muted-foreground">{s.malzeme_kodu}</div>
                    </TableCell>
                    <TableCell>{DURUM_ADI[s.durum]}</TableCell>
                    <TableCell>
                      <ParaHucresi deger={s.a_tutar} basamak={4} />
                    </TableCell>
                    <TableCell>
                      <ParaHucresi deger={s.b_tutar} basamak={4} />
                    </TableCell>
                    <TableCell>
                      <ParaHucresi deger={s.fark} basamak={4} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        </>
      )}
    </section>
  );
}

function KilitDiyalogu({ senaryo, onKapat }: { senaryo: ArsivSenaryosu; onKapat: () => void }) {
  const kilit = useSenaryoKilidi();
  const [neden, setNeden] = useState("");
  const [yerelHata, setYerelHata] = useState<string | null>(null);
  const kilitle = !senaryo.kilitli;
  function onayla() {
    if (!neden.trim()) {
      setYerelHata("Neden zorunlu");
      return;
    }
    setYerelHata(null);
    kilit.mutate({ senaryo: senaryo.id, kilitle, neden: neden.trim() }, { onSuccess: onKapat });
  }
  return (
    <OnayDiyalogu
      baslik={kilitle ? "Senaryoyu kilitle" : "Senaryonun kilidini aç"}
      onayMetni={kilitle ? "Kilitle" : "Kilidi aç"}
      bekliyor={kilit.isPending}
      hata={yerelHata ?? hataMetniVarsa(kilit.error)}
      onOnayla={onayla}
      onVazgec={onKapat}
    >
      <p>
        {kilitle
          ? `"${senaryo.ad}" kilitlenince parametre, fiyat, reçete, hesap ve teklif değişiklikleri yapılamaz. Okuma ve hesaplama serbesttir.`
          : `"${senaryo.ad}" yeniden değiştirilebilir olacak.`}
      </p>
      {kilitle && <p className="text-sm text-muted-foreground">{KILIT_KAPSAM_NOTU}</p>}
      <label className="flex flex-col gap-1">
        Neden
        <Input value={neden} onChange={(e) => setNeden(e.target.value)} placeholder="Örn. Teklif müşteriye gönderildi" />
      </label>
    </OnayDiyalogu>
  );
}

export default function Arsiv() {
  const { senaryoId, sec } = useSenaryo();
  const arsiv = useArsiv();
  const [sayfa, setSayfa] = useState({ senaryo: senaryoId, no: 1 });
  const sayfaNo = sayfa.senaryo === senaryoId ? sayfa.no : 1; // senaryo değişince 1. sayfa
  const [urunGirdi, setUrunGirdi] = useState("");
  const kayitlar = useArsivKayitlari(senaryoId, sayfaNo, BOYUT, urunGirdi.trim());
  const [secili, setSecili] = useState<{ senaryo: number | null; idler: number[] }>({ senaryo: senaryoId, idler: [] });
  const idler = secili.senaryo === senaryoId ? secili.idler : [];
  const [kiyasAcik, setKiyasAcik] = useState(false);
  const [kilitHedefi, setKilitHedefi] = useState<ArsivSenaryosu | null>(null);

  const sezonlar = arsiv.data ?? [];
  const aktifSenaryo = sezonlar.flatMap((z) => z.senaryolar).find((s) => s.id === senaryoId) ?? null;
  const satirlar = kayitlar.data?.kayitlar ?? [];
  const toplam = kayitlar.data?.toplam ?? 0;
  const sayfaSayisi = Math.max(1, Math.ceil(toplam / BOYUT));

  const isaretle = (id: number, acik: boolean) => {
    setKiyasAcik(false);
    setSecili({ senaryo: senaryoId, idler: acik ? [...idler, id].slice(0, 2) : idler.filter((x) => x !== id) });
  };

  return (
    <section className="flex flex-col gap-4 p-4">
      <SayfaSekmeleri etiket="Kıyas türü" sekmeler={KIYAS_SEKMELERI} />
      <SayfaBasligi baslik="Arşiv" altBaslik="Sezon, senaryo ve tarihli kayıtlı hesaplar. Her yeni kayıt kendi tarihiyle ayrı tutulur." />
      {arsiv.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetniVarsa(arsiv.error)}
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <nav aria-label="Arşiv ağacı" className="flex flex-col gap-3">
          {arsiv.isLoading && (
            <p role="status" className="text-muted-foreground">
              Yükleniyor…
            </p>
          )}
          {sezonlar.map((z) => (
            <div key={z.id} role="group" aria-label={`Sezon ${z.ad}`} className="flex flex-col gap-1">
              <div className="px-1 text-sm font-semibold">
                {z.ad}{" "}
                <span className="text-xs font-normal text-muted-foreground">
                  {goster(z.baslangic)} – {goster(z.bitis)}
                </span>
              </div>
              {z.senaryolar.length === 0 && <p className="px-1 text-xs text-muted-foreground">Senaryo yok</p>}
              {z.senaryolar.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  aria-pressed={s.id === senaryoId}
                  aria-label={`Senaryo ${s.ad}`}
                  onClick={() => sec(s.id)}
                  className={cn(
                    "flex flex-col gap-0.5 rounded-lg border px-3 py-2 text-left text-sm transition-colors hover:bg-muted",
                    s.id === senaryoId && "border-marka bg-accent",
                  )}
                >
                  <span className="flex items-center gap-1.5 font-medium">
                    {s.kilitli && <Lock className="size-3.5 shrink-0" aria-label="Kilitli" />}
                    <span className="truncate">{s.ad}</span>
                    <Badge variant="secondary">{TUR_ADI[s.tur] ?? s.tur}</Badge>
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {s.olusturma_zamani ? goster(s.olusturma_zamani) : "—"} · {s.olusturan}
                  </span>
                  {s.kaynak_dosya && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <FileSpreadsheet className="size-3 shrink-0" aria-hidden />
                      <span className="truncate">{s.kaynak_dosya}</span>
                    </span>
                  )}
                  <span className="text-xs text-muted-foreground">
                    {s.urun_sayisi} ürün · {s.hesap_sayisi} hesap · {s.teklif_sayisi} teklif
                  </span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="flex min-w-0 flex-col gap-3">
          {aktifSenaryo ? (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 text-lg font-medium">
                  {aktifSenaryo.kilitli && <Lock className="size-4" aria-hidden />}
                  {aktifSenaryo.ad}
                  {aktifSenaryo.kilitli && <Badge variant="outline">Kilitli</Badge>}
                </h2>
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    type="search"
                    aria-label="Ürün kodu ara"
                    placeholder="Ürün kodu ara"
                    value={urunGirdi}
                    onChange={(e) => {
                      setUrunGirdi(e.target.value);
                      setSayfa({ senaryo: senaryoId, no: 1 });
                    }}
                    className="w-44"
                  />
                  <Button type="button" variant="outline" disabled={idler.length !== 2} onClick={() => setKiyasAcik(true)}>
                    Kıyasla
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setKilitHedefi(aktifSenaryo)}>
                    {aktifSenaryo.kilitli ? (
                      <>
                        <LockOpen aria-hidden /> Kilidi aç
                      </>
                    ) : (
                      <>
                        <Lock aria-hidden /> Kilitle
                      </>
                    )}
                  </Button>
                </div>
              </div>
              {idler.length === 1 && <p className="text-xs text-muted-foreground">Kıyaslamak için bir kayıt daha seçin.</p>}

              {kiyasAcik && idler.length === 2 && <KiyasKarti a={idler[0]} b={idler[1]} onKapat={() => setKiyasAcik(false)} />}

              {kayitlar.error && (
                <p role="alert" className="text-sm text-destructive">
                  {hataMetniVarsa(kayitlar.error)}
                </p>
              )}
              <section aria-label="Kayıtlı hesaplar">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8">
                        <span className="sr-only">Seç</span>
                      </TableHead>
                      <TableHead>Hesap tarihi</TableHead>
                      <TableHead>Ürün</TableHead>
                      <TableHead>Neden</TableHead>
                      <TableHead className="text-right">Maliyet (TL)</TableHead>
                      <TableHead className="text-right">Satış (TL)</TableHead>
                      <TableHead className="text-right">Teklif</TableHead>
                      <TableHead>Kaydeden</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {kayitlar.isLoading && (
                      <TableRow>
                        <TableCell colSpan={8} role="status" className="text-muted-foreground">
                          Yükleniyor…
                        </TableCell>
                      </TableRow>
                    )}
                    {!kayitlar.isLoading && satirlar.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={8} className="text-muted-foreground">
                          Bu senaryoda kayıtlı hesap yok
                        </TableCell>
                      </TableRow>
                    )}
                    {satirlar.map((r) => {
                      const isaretli = idler.includes(r.id);
                      return (
                        <TableRow key={r.id}>
                          <TableCell>
                            <input
                              type="checkbox"
                              aria-label={`Kıyas için seç ${r.urun_kodu} ${r.hesap_tarihi}`}
                              checked={isaretli}
                              disabled={!isaretli && idler.length >= 2}
                              onChange={(e) => isaretle(r.id, e.target.checked)}
                            />
                          </TableCell>
                          <TableCell className="whitespace-nowrap">{goster(r.hesap_tarihi)}</TableCell>
                          <TableCell>
                            <Link to={`/hesaplar/${r.id}`} className="text-primary underline-offset-2 hover:underline">
                              {r.urun_ad}
                            </Link>
                            <div className="font-mono text-xs text-muted-foreground">{r.urun_kodu}</div>
                          </TableCell>
                          <TableCell className="max-w-56 text-xs">{r.neden ?? "—"}</TableCell>
                          <TableCell>
                            <ParaHucresi deger={r.maliyet_tl} />
                          </TableCell>
                          <TableCell>
                            <ParaHucresi deger={r.satis_tl} />
                          </TableCell>
                          <TableCell className="text-right tabular-nums">{r.teklif_sayisi}</TableCell>
                          <TableCell className="text-xs">{r.olusturan}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </section>

              <nav aria-label="Sayfalama" className="flex items-center justify-end gap-2 text-sm">
                <span className="mr-auto text-muted-foreground">{toplam} kayıt</span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={sayfaNo <= 1}
                  onClick={() => setSayfa({ senaryo: senaryoId, no: sayfaNo - 1 })}
                >
                  Önceki
                </Button>
                <span>
                  Sayfa {sayfaNo} / {sayfaSayisi}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={sayfaNo >= sayfaSayisi}
                  onClick={() => setSayfa({ senaryo: senaryoId, no: sayfaNo + 1 })}
                >
                  Sonraki
                </Button>
              </nav>
            </>
          ) : (
            !arsiv.isLoading && <p className="text-muted-foreground">Soldaki ağaçtan bir senaryo seçin.</p>
          )}
        </div>
      </div>
      {kilitHedefi && <KilitDiyalogu senaryo={kilitHedefi} onKapat={() => setKilitHedefi(null)} />}
    </section>
  );
}
