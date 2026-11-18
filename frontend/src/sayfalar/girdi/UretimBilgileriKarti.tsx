import { useEffect, useId, useMemo, useState } from "react";
import { Boxes } from "lucide-react";
import { hataMetni } from "@/api/istemci";
import { useUretimHedefiKaydet, useUrun, useUrunler } from "@/api/sorgular/urunler";
import { Button } from "@/bilesenler/ui/button";
import { Input } from "@/bilesenler/ui/input";
import { sayiApi } from "@/yardimcilar/sayi";
import { kapasiteSayisi } from "../ayarlar/kapasiteDuzenleme";
import { fireYuzdeMetni, yuzdeOranMetni } from "../urun/yardimci";
import { Alan, Kart, SELECT } from "./ortak";

/** Tek sayfada arama/seçim için üst sınır (API `boyut` en çok 500). */
const LISTE_BOYUTU = 500;

type HedefAlanAnahtari =
  "vardiya_uretim_adedi" | "dolum_personel" | "etiketleme_adedi" | "etiket_personel" | "mal_kabul_miktar_kg" | "mal_kabul_fire";
/** Ürün ekranındaki "Üretim bilgileri" bloğuyla aynı alanlar (fire yüzde olarak girilir, API'ye oran gider). */
const HEDEF_ALANLARI: {
  anahtar: HedefAlanAnahtari;
  etiket: string;
  yuzde?: boolean;
}[] = [
  { anahtar: "vardiya_uretim_adedi", etiket: "Vardiya üretim adedi" },
  { anahtar: "dolum_personel", etiket: "Dolum personel" },
  { anahtar: "etiketleme_adedi", etiket: "Etiketleme adedi" },
  { anahtar: "etiket_personel", etiket: "Etiket personel" },
  { anahtar: "mal_kabul_miktar_kg", etiket: "Mal kabul miktarı (kg)" },
  { anahtar: "mal_kabul_fire", etiket: "Mal kabul fire (%)", yuzde: true },
];
type HedefDegerleri = Record<HedefAlanAnahtari, string>;
const BOS_HEDEF: HedefDegerleri = {
  vardiya_uretim_adedi: "",
  dolum_personel: "",
  etiketleme_adedi: "",
  etiket_personel: "",
  mal_kabul_miktar_kg: "",
  mal_kabul_fire: "",
};

interface Props {
  senaryoId: number;
  kilitli: boolean;
  onMesaj: (m: string) => void;
  /** Doluysa ürün seçici gizlenir ve bu ürün için girilir (ürün ekranı: "hesap için üretim bilgisi gerekli" durumu). */
  sabitKod?: string;
  /** Başarılı kayıttan sonra çağrılır (ürün ekranı hesabı yeniden koşturur). */
  onKaydedildi?: () => void;
}

/** Ürünün üretim bilgileri (vardiya üretim adedi, personel, mal kabul) nedenle kaydedilir; Genel Bakış'taki Üretim Adedi buradan gelir. */
export function UretimBilgileriKarti({ senaryoId, kilitli, onMesaj, sabitKod, onKaydedildi }: Props) {
  const id = useId();
  const liste = useUrunler(sabitKod ? null : senaryoId, { boyut: LISTE_BOYUTU });
  const [kod, setKod] = useState(sabitKod ?? "");
  const urun = useUrun(kod, senaryoId);
  const kaydet = useUretimHedefiKaydet();
  const [degerler, setDegerler] = useState<HedefDegerleri>(BOS_HEDEF);
  const [pazarlama, setPazarlama] = useState(true);
  const [neden, setNeden] = useState("");
  /** Kullanıcı bir alana dokunmadan boş formun altı hata satırı gösterilmez. */
  const [dokunuldu, setDokunuldu] = useState(false);
  const hedef = urun.data?.uretim_hedefi ?? null;
  const { reset: kaydetSifirla } = kaydet;

  // Ürün (ya da sunucudaki hedef) değişince form sunucu değerleriyle dolar; henüz hedefi olmayan üründe boş kalır.
  useEffect(() => {
    setDegerler(
      hedef
        ? {
            vardiya_uretim_adedi: hedef.vardiya_uretim_adedi,
            dolum_personel: hedef.dolum_personel,
            etiketleme_adedi: hedef.etiketleme_adedi,
            etiket_personel: hedef.etiket_personel,
            mal_kabul_miktar_kg: hedef.mal_kabul_miktar_kg,
            mal_kabul_fire: fireYuzdeMetni(hedef.mal_kabul_fire),
          }
        : BOS_HEDEF,
    );
    setPazarlama(hedef?.pazarlama_yonetim_uygula ?? true);
    setNeden("");
    setDokunuldu(false);
  }, [kod, hedef]);

  // Önceki ürünün hata/sonuç durumu yalnız ürün değişince temizlenir. Kayıt sonrası `hedef` yenilenirken reset çağrılmaz:
  // reset gözlemciyi mutasyondan ayırır ve `mutate(..., { onSuccess })` geri çağrısı (mesaj, hesabı yeniden koşturma) düşer.
  useEffect(() => kaydetSifirla(), [kod, kaydetSifirla]);

  const hatalar = useMemo(() => {
    if (!kod) return [];
    const h: string[] = [];
    for (const a of HEDEF_ALANLARI) {
      const v = degerler[a.anahtar];
      const ok = a.yuzde ? yuzdeOranMetni(v) !== null : sayiApi(v) !== null;
      if (!ok) h.push(`${a.etiket} geçerli bir sayı olmalı`);
    }
    return h;
  }, [kod, degerler]);
  const kaydedilebilir = !!kod && hatalar.length === 0 && neden.trim() !== "" && !kaydet.isPending && !kilitli;

  function gonder() {
    if (!kaydedilebilir) return;
    kaydet.mutate(
      {
        kod,
        senaryo: senaryoId,
        govde: {
          vardiya_uretim_adedi: sayiApi(degerler.vardiya_uretim_adedi) as string,
          dolum_personel: sayiApi(degerler.dolum_personel) as string,
          etiketleme_adedi: sayiApi(degerler.etiketleme_adedi) as string,
          etiket_personel: sayiApi(degerler.etiket_personel) as string,
          mal_kabul_miktar_kg: sayiApi(degerler.mal_kabul_miktar_kg) as string,
          mal_kabul_fire: yuzdeOranMetni(degerler.mal_kabul_fire) as string,
          pazarlama_yonetim_uygula: pazarlama,
          neden: neden.trim(),
        },
      },
      {
        onSuccess: () => {
          onMesaj(`${kod} için üretim bilgileri kaydedildi.`);
          onKaydedildi?.();
        },
      },
    );
  }

  return (
    <Kart
      baslik="Üretim bilgileri (ürün)"
      aciklama={
        sabitKod
          ? "Hesap için gerekli: vardiya üretim adedi, personel ve mal kabul bilgileri. Kaydedince hesap yeniden koşar."
          : "Ürünü seçin; vardiya üretim adedi, personel ve mal kabul bilgileri ürün ekranındaki Üretim bilgileri bloğuyla aynıdır. Genel Bakış'taki Üretim Adedi buradan gelir."
      }
      simge={<Boxes />}
    >
      {!sabitKod && (
        <Alan etiket="Ürün" htmlFor={`${id}-urun`}>
          <select
            id={`${id}-urun`}
            className={SELECT}
            value={kod}
            disabled={kilitli || liste.isLoading}
            onChange={(e) => setKod(e.target.value)}
          >
            <option value="">Seçin…</option>
            {(liste.data?.kayitlar ?? []).map((u) => (
              <option key={u.kod} value={u.kod}>
                {u.kod} — {u.ad}
              </option>
            ))}
          </select>
        </Alan>
      )}
      {liste.error && (
        <p role="alert" className="text-sm text-destructive">
          {hataMetni(liste.error)}
        </p>
      )}
      {kod && urun.isLoading && <p className="text-sm text-muted-foreground">Yükleniyor…</p>}
      {kod && urun.data && (
        <div className="flex flex-col gap-2">
          {!hedef && (
            <p className="text-xs text-muted-foreground">Bu ürün için henüz üretim bilgisi yok; girilen değerler ilk kayıt olur.</p>
          )}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {HEDEF_ALANLARI.map((a) => {
              const mevcut = hedef ? (a.yuzde ? fireYuzdeMetni(hedef[a.anahtar]) : hedef[a.anahtar]) : undefined;
              return (
                <div key={a.anahtar} className="flex flex-col gap-1">
                  <label htmlFor={`${id}-${a.anahtar}`} className="text-xs text-muted-foreground">
                    {a.etiket}
                    {mevcut !== undefined && <span className="ml-1 tabular-nums">(şu an {kapasiteSayisi(mevcut)})</span>}
                  </label>
                  <Input
                    id={`${id}-${a.anahtar}`}
                    aria-label={a.etiket}
                    inputMode="decimal"
                    value={degerler[a.anahtar]}
                    disabled={kilitli}
                    onChange={(e) => {
                      setDokunuldu(true);
                      setDegerler((d) => ({ ...d, [a.anahtar]: e.target.value }));
                    }}
                    className="h-8 text-right tabular-nums"
                  />
                </div>
              );
            })}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={pazarlama} disabled={kilitli} onChange={(e) => setPazarlama(e.target.checked)} />
            Pazarlama ve yönetim gideri uygulansın
          </label>
          <Input
            aria-label="Neden"
            placeholder="Neden (zorunlu)"
            value={neden}
            disabled={kilitli}
            onChange={(e) => setNeden(e.target.value)}
            className="h-8"
          />
          {dokunuldu &&
            hatalar.map((h) => (
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
            <Button type="button" size="sm" disabled={!kaydedilebilir} onClick={gonder}>
              Kaydet
            </Button>
            {!sabitKod && (
              <Button type="button" size="sm" variant="outline" onClick={() => setKod("")}>
                Vazgeç
              </Button>
            )}
          </div>
        </div>
      )}
    </Kart>
  );
}
