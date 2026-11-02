import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search } from "lucide-react";
import { useMalzemeler } from "@/api/sorgular/malzemeler";
import { useUrunler } from "@/api/sorgular/urunler";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/bilesenler/ui/dialog";
import { aramaSuz, type AramaOgesi } from "./aramaSuz";
import { useSenaryo } from "./SenaryoSecici";

/** Sağ üstte büyüteç + Ctrl+K: ürün kodu/adı → ürün ekranı; malzeme kodu/adı → Malzeme Fiyatları (arama dolu). */
export function HizliArama() {
  const [acik, setAcik] = useState(false);
  const [sorgu, setSorgu] = useState("");
  const [secili, setSecili] = useState(0);
  const girdi = useRef<HTMLInputElement>(null);
  const { senaryoId } = useSenaryo();
  const navigate = useNavigate();

  useEffect(() => {
    const dinle = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setAcik((a) => !a);
      }
    };
    window.addEventListener("keydown", dinle);
    return () => window.removeEventListener("keydown", dinle);
  }, []);

  // Listeler yalnız diyalog açıkken çekilir; ürün listesi sunucu önbelleğinden gelir, malzemeler iki sayfa (≤1000).
  const urunler = useUrunler(acik ? senaryoId : null, { boyut: 500 });
  const malzeme1 = useMalzemeler(acik ? senaryoId : null, { boyut: 500, sayfa: 1 });
  const malzeme2 = useMalzemeler(acik && (malzeme1.data?.toplam ?? 0) > 500 ? senaryoId : null, { boyut: 500, sayfa: 2 });

  const ogeler = useMemo<AramaOgesi[]>(() => {
    const u = (urunler.data?.kayitlar ?? []).map((k) => ({ tur: "urun" as const, kod: k.kod, ad: k.ad }));
    const m = [...(malzeme1.data?.kayitlar ?? []), ...(malzeme2.data?.kayitlar ?? [])].map((k) => ({
      tur: "malzeme" as const,
      kod: k.kod,
      ad: k.ad,
    }));
    return [...u, ...m];
  }, [urunler.data, malzeme1.data, malzeme2.data]);

  const sonuclar = useMemo(() => aramaSuz(sorgu, ogeler, senaryoId), [sorgu, ogeler, senaryoId]);
  const yukleniyor = acik && (urunler.isLoading || malzeme1.isLoading);

  useEffect(() => {
    setSecili(0);
  }, [sorgu]);

  function git(yol: string) {
    setAcik(false);
    setSorgu("");
    navigate(yol);
  }

  function tusa(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSecili((i) => Math.min(i + 1, Math.max(sonuclar.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSecili((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && sonuclar[secili]) {
      e.preventDefault();
      git(sonuclar[secili].yol);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setAcik(true)}
        aria-label="Hızlı arama (Ctrl+K)"
        title="Hızlı arama (Ctrl+K)"
        className="inline-flex size-9 items-center justify-center rounded-full border text-muted-foreground hover:bg-accent/70 hover:text-foreground"
      >
        <Search className="size-4" aria-hidden="true" />
      </button>
      <Dialog open={acik} onOpenChange={setAcik}>
        <DialogContent className="top-24 translate-y-0 sm:max-w-lg" showCloseButton={false} initialFocus={girdi}>
          <DialogTitle className="sr-only">Hızlı arama</DialogTitle>
          <DialogDescription className="sr-only">Ürün veya malzeme kodu ya da adı yazın; ok tuşlarıyla seçip Enter ile açın.</DialogDescription>
          <div className="flex items-center gap-2 border-b pb-2">
            <Search className="size-4 text-muted-foreground" aria-hidden="true" />
            <input
              ref={girdi}
              value={sorgu}
              onChange={(e) => setSorgu(e.target.value)}
              onKeyDown={tusa}
              placeholder="Ürün veya malzeme: kod ya da ad…"
              aria-label="Arama"
              className="w-full bg-transparent text-base outline-none placeholder:text-muted-foreground"
              autoComplete="off"
            />
            <kbd className="rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground">Esc</kbd>
          </div>
          <div role="listbox" aria-label="Arama sonuçları" className="max-h-80 overflow-auto">
            {yukleniyor && <p className="px-2 py-3 text-sm text-muted-foreground">Yükleniyor…</p>}
            {!yukleniyor && sorgu.trim().length >= 2 && sonuclar.length === 0 && (
              <p className="px-2 py-3 text-sm text-muted-foreground">Sonuç yok.</p>
            )}
            {!yukleniyor && sorgu.trim().length < 2 && (
              <p className="px-2 py-3 text-sm text-muted-foreground">En az iki karakter yazın. Ürünler ürün ekranına, malzemeler Malzeme Fiyatları'na gider.</p>
            )}
            {sonuclar.map((s, i) => (
              <button
                key={`${s.tur}-${s.kod}`}
                type="button"
                role="option"
                aria-selected={i === secili}
                onMouseEnter={() => setSecili(i)}
                onClick={() => git(s.yol)}
                className={`flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm ${i === secili ? "bg-accent/70" : "hover:bg-muted/60"}`}
              >
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${s.tur === "urun" ? "bg-marka/20 text-primary" : "bg-muted text-muted-foreground"}`}>
                  {s.tur === "urun" ? "Ürün" : "Malzeme"}
                </span>
                <span className="font-mono text-xs text-muted-foreground">{s.kod}</span>
                <span className="truncate">{s.ad}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
