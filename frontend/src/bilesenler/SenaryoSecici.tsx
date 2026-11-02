import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { Ellipsis, Plus } from "lucide-react";
import { useSenaryoGuncelle, useSenaryolar, useSenaryoSil } from "@/api/sorgular/senaryolar";
import { hataMetni, hataMetniVarsa, type ApiHatasi } from "@/api/istemci";
import type { Senaryo } from "@/api/tipler";
import { OnayDiyalogu } from "./OnayDiyalogu";
import { SenaryoDuzenleDiyalogu } from "./SenaryoDuzenleDiyalogu";
import { Button, buttonVariants } from "./ui/button";
import { YeniCalismaDiyalogu, type YeniCalismaSekmesi } from "./YeniCalismaDiyalogu";
import { cn } from "@/lib/utils";
import { senaryoEtiketi } from "@/yardimcilar/senaryo";

const ANAHTAR = "fiyat-calismasi.senaryo";

interface SenaryoBaglami {
  /** Seçili senaryo; liste yüklenene kadar null. */
  senaryoId: number | null;
  senaryo: Senaryo | null;
  senaryolar: Senaryo[];
  /** Seçili senaryo kilitli mi (yazma uçları 409 verir); yazma düğmeleri buna bakarak pasifleşir. */
  kilitli: boolean;
  yukleniyor: boolean;
  hata: ApiHatasi | null;
  sec: (id: number) => void;
  /** "Yeni çalışma" diyaloğunu açar (varsayılan sekme: Boş). Dashboard boş durumu kopya sekmesiyle açar. */
  yeniCalismaAc: (sekme?: YeniCalismaSekmesi) => void;
}

const Baglam = createContext<SenaryoBaglami | null>(null);

function sakliOku(): number | null {
  try {
    const v = Number(localStorage.getItem(ANAHTAR));
    return Number.isInteger(v) && v > 0 ? v : null;
  } catch {
    return null;
  }
}

function sakliYaz(id: number): void {
  try {
    localStorage.setItem(ANAHTAR, String(id));
  } catch {
    /* localStorage kullanılamıyor */
  }
}

/** Seçim sırası: URL ?senaryo= -> localStorage -> ilk senaryo. Geçersiz kimlikler yok sayılır. */
export function SenaryoSaglayici({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams();
  const sorgu = useSenaryolar();
  const senaryolar = useMemo(() => sorgu.data ?? [], [sorgu.data]);
  const [yeniCalisma, setYeniCalisma] = useState<YeniCalismaSekmesi | null>(null);

  const urlId = Number(params.get("senaryo"));
  const secili = useMemo(() => {
    if (senaryolar.length === 0) return null;
    const adaylar = [urlId, sakliOku()];
    for (const a of adaylar) {
      const bulunan = senaryolar.find((s) => s.id === a);
      if (bulunan) return bulunan;
    }
    return senaryolar[0];
  }, [senaryolar, urlId]);

  const seciliId = secili?.id ?? null;

  // URL ve saklanan değer her zaman seçimle eşit kalsın.
  useEffect(() => {
    if (seciliId === null) return;
    sakliYaz(seciliId);
    if (params.get("senaryo") !== String(seciliId)) {
      setParams(
        (onceki) => {
          const yeni = new URLSearchParams(onceki);
          yeni.set("senaryo", String(seciliId));
          return yeni;
        },
        { replace: true },
      );
    }
  }, [seciliId, params, setParams]);

  const sec = useCallback(
    (id: number) => {
      sakliYaz(id);
      setParams((onceki) => {
        const yeni = new URLSearchParams(onceki);
        yeni.set("senaryo", String(id));
        return yeni;
      });
    },
    [setParams],
  );

  const yeniCalismaAc = useCallback((sekme: YeniCalismaSekmesi = "bos") => setYeniCalisma(sekme), []);

  const deger = useMemo<SenaryoBaglami>(
    () => ({
      senaryoId: seciliId,
      senaryo: secili,
      senaryolar,
      kilitli: secili?.kilitli ?? false,
      yukleniyor: sorgu.isPending,
      hata: (sorgu.error as ApiHatasi | null) ?? null,
      sec,
      yeniCalismaAc,
    }),
    [seciliId, secili, senaryolar, sorgu.isPending, sorgu.error, sec, yeniCalismaAc],
  );

  return (
    <Baglam.Provider value={deger}>
      {children}
      {yeniCalisma && (
        <YeniCalismaDiyalogu
          sekme={yeniCalisma}
          senaryolar={senaryolar}
          seciliId={seciliId}
          onKapat={() => setYeniCalisma(null)}
          onOlusturuldu={sec}
        />
      )}
    </Baglam.Provider>
  );
}

/** Sayfalar seçili senaryoyu buradan okur. */
export function useSenaryo(): SenaryoBaglami {
  const b = useContext(Baglam);
  if (!b) throw new Error("useSenaryo, SenaryoSaglayici içinde kullanılmalıdır");
  return b;
}

const MENU_OGESI =
  "w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted focus-visible:bg-muted focus-visible:outline-none aria-disabled:cursor-not-allowed aria-disabled:opacity-50 aria-disabled:hover:bg-transparent";

/**
 * Seçili senaryo için "⋯" menüsü: Düzenle… / Sil…. Kilitli senaryoda ikisi de pasiftir (sunucu da 409 verir); pasif öğe
 * `aria-disabled` ile odaklanabilir kalır ki "Senaryo kilitli" ipucu klavye/okuyucu kullanıcısına da ulaşsın.
 * Klavye: açılınca odak ilk öğeye; Ok yukarı/aşağı, Home/End dolaşır; Escape kapatır ve odağı düğmeye döndürür.
 */
function SenaryoMenusu({ senaryo, onDuzenle, onSil }: { senaryo: Senaryo; onDuzenle: () => void; onSil: () => void }) {
  const [acik, setAcik] = useState(false);
  const kok = useRef<HTMLDivElement>(null);
  const tetik = useRef<HTMLButtonElement>(null);
  const ogeler = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!acik) return;
    ogeler.current[0]?.focus();
    const disariTikla = (e: MouseEvent) => {
      if (kok.current && !kok.current.contains(e.target as Node)) setAcik(false);
    };
    document.addEventListener("mousedown", disariTikla);
    return () => document.removeEventListener("mousedown", disariTikla);
  }, [acik]);

  function kapat(odakDon = true) {
    setAcik(false);
    if (odakDon) tetik.current?.focus();
  }

  function tusa(e: React.KeyboardEvent<HTMLDivElement>) {
    const liste = ogeler.current.filter((o): o is HTMLButtonElement => !!o);
    const i = liste.findIndex((o) => o === document.activeElement);
    let hedef = -1;
    if (e.key === "Escape") return kapat();
    if (e.key === "ArrowDown") hedef = (i + 1) % liste.length;
    else if (e.key === "ArrowUp") hedef = (i - 1 + liste.length) % liste.length;
    else if (e.key === "Home") hedef = 0;
    else if (e.key === "End") hedef = liste.length - 1;
    if (hedef < 0) return;
    e.preventDefault();
    liste[hedef]?.focus();
  }

  const kilitli = senaryo.kilitli;
  const kilitNotu = kilitli ? "Senaryo kilitli" : undefined;
  const oge = (i: number, etiket: string, eylem: () => void, ekSinif = "") => (
    <button
      type="button"
      role="menuitem"
      ref={(el) => {
        ogeler.current[i] = el;
      }}
      className={`${MENU_OGESI} ${ekSinif}`}
      aria-disabled={kilitli || undefined}
      title={kilitNotu}
      onClick={() => {
        if (kilitli) return;
        kapat(false);
        eylem();
      }}
    >
      {etiket}
    </button>
  );

  return (
    <div ref={kok} className="relative" onKeyDown={tusa}>
      {/* Düz <button>: ui/button ref iletmez; Escape sonrası odağı geri vermek için DOM düğümü gerekir. */}
      <button
        ref={tetik}
        type="button"
        className={cn(buttonVariants({ variant: "ghost", size: "icon-sm" }))}
        aria-label="Senaryo işlemleri"
        title="Senaryo işlemleri"
        aria-haspopup="menu"
        aria-expanded={acik}
        onClick={() => setAcik((a) => !a)}
      >
        <Ellipsis aria-hidden />
      </button>
      {acik && (
        <div
          role="menu"
          aria-label="Senaryo işlemleri"
          className="absolute right-0 z-30 mt-1 flex w-44 flex-col gap-0.5 rounded-xl border bg-popover p-1 text-popover-foreground shadow-lg"
        >
          {oge(0, "Düzenle…", onDuzenle)}
          {oge(1, "Sil…", onSil, "text-destructive")}
        </div>
      )}
    </div>
  );
}

export function SenaryoSecici() {
  const { senaryolar, senaryo, senaryoId, yukleniyor, hata, sec, yeniCalismaAc } = useSenaryo();
  // Hedef senaryo state'te tutulur: silme/yenileme sırasında seçim değişse de diyalog başlığı ve kimlik sabit kalır.
  const [duzenlenen, setDuzenlenen] = useState<Senaryo | null>(null);
  const [silinecek, setSilinecek] = useState<Senaryo | null>(null);
  const guncelle = useSenaryoGuncelle();
  const silme = useSenaryoSil();

  if (hata) return <span className="text-sm text-destructive">{hataMetni(hata)}</span>;
  if (yukleniyor) return <span className="text-sm text-muted-foreground">Senaryolar yükleniyor…</span>;

  const yeniDugmesi = (
    <Button type="button" variant="outline" size="sm" onClick={() => yeniCalismaAc("bos")}>
      <Plus aria-hidden />
      Yeni çalışma
    </Button>
  );

  if (senaryolar.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Senaryo yok</span>
        {yeniDugmesi}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="senaryo-secici" className="text-muted-foreground">
        Senaryo
      </label>
      <select
        id="senaryo-secici"
        value={senaryoId ?? ""}
        onChange={(e) => sec(Number(e.target.value))}
        className="h-9 max-w-[40vw] rounded-lg border border-input bg-card px-3 text-sm font-medium shadow-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        {senaryolar.map((s) => (
          <option key={s.id} value={s.id}>
            {senaryoEtiketi(s)}
          </option>
        ))}
      </select>
      {yeniDugmesi}
      {senaryo && (
        <SenaryoMenusu
          senaryo={senaryo}
          onDuzenle={() => {
            guncelle.reset();
            setDuzenlenen(senaryo);
          }}
          onSil={() => {
            silme.reset();
            setSilinecek(senaryo);
          }}
        />
      )}
      {duzenlenen && (
        <SenaryoDuzenleDiyalogu
          senaryo={duzenlenen}
          gonderiliyor={guncelle.isPending}
          hata={hataMetniVarsa(guncelle.error)}
          onKapat={() => setDuzenlenen(null)}
          onGonder={(govde) => guncelle.mutate({ id: duzenlenen.id, govde }, { onSuccess: () => setDuzenlenen(null) })}
        />
      )}
      {silinecek && (
        <OnayDiyalogu
          baslik={`Çalışmayı sil: ${silinecek.sezon_ad} · ${silinecek.ad}`}
          onayMetni="Sil"
          bekliyor={silme.isPending}
          hata={hataMetniVarsa(silme.error)}
          onOnayla={() => silme.mutate(silinecek.id, { onSuccess: () => setSilinecek(null) })}
          onVazgec={() => setSilinecek(null)}
        >
          <p>Bu işlem geri alınamaz; silmeden önce otomatik yedek alınır.</p>
          <p className="text-muted-foreground">
            Çalışmaya bağlı reçeteler, fiyatlar, parametre değerleri, gider dağıtımı ve üretim bilgileri de silinir. Kayıtlı hesabı olan
            ya da kilitli çalışma silinemez; ürün ve malzeme kartları etkilenmez.
          </p>
        </OnayDiyalogu>
      )}
    </div>
  );
}
