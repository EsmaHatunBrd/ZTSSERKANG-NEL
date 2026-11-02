import { useState } from "react";
import { Badge } from "@/bilesenler/ui/badge";
import { Button } from "@/bilesenler/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/bilesenler/ui/dialog";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import type { DegisiklikSatiri, Kapsam } from "./Taslak";

export interface KaydetSecimi {
  neden: string;
  hesabiKaydet: boolean;
  /** parametre anahtarı -> seçilen kapsam (yalnız senaryo geneli satırlarda "Yalnız bu ürün için yaz" işaretlenenler). */
  kapsamSecimi: Record<string, Kapsam>;
}

interface Props {
  acik: boolean;
  satirlar: DegisiklikSatiri[];
  /** Elle brüt olduğu için fire taslağı düşecek satırlar. */
  dusenFire: { sira: number }[];
  gonderiliyor: boolean;
  /** Sunucu hatası (Türkçe); diyalog açık kalır, taslak korunur. */
  hata: string | null;
  /** Senaryodaki ürün sayısı (rozet "N ürünü etkiler"); yüklenmediyse "tüm ürünleri etkiler". */
  urunSayisi?: number | null;
  onGonder: (secim: KaydetSecimi) => void;
  onKapat: () => void;
}

/** Tek "Kaydet" onayı: ne değişiyor, kimi etkiliyor, neden. Gönderince POST /urunler/{kod}/kaydet çağrılır. */
export function KaydetDiyalogu({ acik, ...diger }: Props) {
  return (
    // Gönderim sürerken kapatma istekleri (Escape, dış tıklama, Vazgeç) yok sayılır: yanıt geri çağrısı kaybolmasın.
    <Dialog open={acik} onOpenChange={(a) => !a && !diger.gonderiliyor && diger.onKapat()}>
      <DialogContent className="sm:max-w-3xl" aria-label="Değişiklikleri kaydet" showCloseButton={!diger.gonderiliyor}>
        {acik && <Icerik {...diger} />}
      </DialogContent>
    </Dialog>
  );
}

function Icerik({ satirlar, dusenFire, gonderiliyor, hata, urunSayisi, onGonder, onKapat }: Omit<Props, "acik">) {
  const [neden, setNeden] = useState("");
  const [hesabiKaydet, setHesabiKaydet] = useState(true);
  const [yalnizUrun, setYalnizUrun] = useState<Record<string, boolean>>({});

  const gonderilebilir = neden.trim() !== "" && !gonderiliyor;

  function gonder() {
    const kapsamSecimi: Record<string, Kapsam> = {};
    for (const s of satirlar) {
      if (s.parametre && yalnizUrun[s.parametre]) kapsamSecimi[s.parametre] = "urun";
    }
    onGonder({ neden: neden.trim(), hesabiKaydet, kapsamSecimi });
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Değişiklikleri kaydet</DialogTitle>
        <DialogDescription>Aşağıdakiler tek işlemde yazılır; biri başarısız olursa hiçbiri yazılmaz.</DialogDescription>
      </DialogHeader>

      <div className="max-h-[50vh] overflow-auto">
        <Table aria-label="Değişiklik listesi">
          <TableHeader>
            <TableRow>
              <TableHead>Alan</TableHead>
              <TableHead className="text-right">Eski → Yeni</TableHead>
              <TableHead>Etki</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {satirlar.map((s) => (
              <TableRow key={s.alan} data-alan={s.alan}>
                <TableCell>
                  {s.etiket}
                  {s.ek && <span className="block text-xs text-muted-foreground">{s.ek}</span>}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  <span className="text-muted-foreground">{s.eski}</span>
                  <span aria-hidden> → </span>
                  <span className="sr-only"> yeni: </span>
                  <span className="font-medium">{s.yeni}</span>
                </TableCell>
                <TableCell>
                  <div className="flex flex-col items-start gap-1">
                    {!s.kalici ? (
                      <>
                        <Badge variant="outline">Yalnız bu hesapta</Badge>
                        {s.not && <span className="text-xs text-muted-foreground">{s.not}</span>}
                      </>
                    ) : s.etki === "senaryo" && !yalnizUrun[s.parametre ?? ""] ? (
                      <Badge variant="destructive">
                        Senaryo geneli — {urunSayisi != null ? `${urunSayisi} ürünü etkiler` : "tüm ürünleri etkiler"}
                      </Badge>
                    ) : (
                      <Badge variant="secondary">Bu ürün</Badge>
                    )}
                    {s.kalici && s.etki === "senaryo" && s.parametre && (
                      <label className="flex items-center gap-1.5 text-xs">
                        <input
                          type="checkbox"
                          aria-label={`Yalnız bu ürün için yaz — ${s.etiket}`}
                          checked={!!yalnizUrun[s.parametre]}
                          onChange={(e) => {
                            const p = s.parametre as string;
                            setYalnizUrun((y) => ({
                              ...y,
                              [p]: e.target.checked,
                            }));
                          }}
                        />
                        Yalnız bu ürün için yaz
                      </label>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {dusenFire.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm text-destructive">
          {dusenFire.map((r) => (
            <li key={r.sira}>{`Satır ${r.sira}: fire düşer (elle brüt)`}</li>
          ))}
        </ul>
      )}

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">Neden (zorunlu)</span>
        <Input
          aria-label="Neden"
          aria-required
          value={neden}
          onChange={(e) => setNeden(e.target.value)}
          placeholder="Örn. Ekim ayı fiyat güncellemesi"
          autoFocus
        />
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" aria-label="Hesabı da kaydet" checked={hesabiKaydet} onChange={(e) => setHesabiKaydet(e.target.checked)} />
        Hesabı da kaydet
      </label>

      {hata && (
        <p role="alert" className="text-sm text-destructive">
          {hata}
        </p>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onKapat} disabled={gonderiliyor}>
          Vazgeç
        </Button>
        <Button type="button" onClick={gonder} disabled={!gonderilebilir}>
          Onayla ve kaydet
        </Button>
      </DialogFooter>
    </>
  );
}
