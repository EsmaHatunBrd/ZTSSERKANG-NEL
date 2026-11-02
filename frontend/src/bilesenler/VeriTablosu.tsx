import { useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Inbox } from "lucide-react";
import { flexRender } from "@tanstack/react-table";
import {
  getCoreRowModel,
  getSortedRowModel,
  useLegacyTable,
  type LegacyColumnDef,
  type LegacyRow,
} from "@tanstack/react-table/legacy";
import type { SortingState } from "@tanstack/react-table";
import Decimal from "decimal.js";
import { hataMetni, type ApiHatasi } from "@/api/istemci";
import { Input } from "@/bilesenler/ui/input";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/bilesenler/ui/table";
import { cn } from "@/lib/utils";

/** Sütun tanımı (TanStack Table). */
// oxlint-disable-next-line no-explicit-any
export type SutunTanimi<T> = LegacyColumnDef<T, any>;

export interface VeriTablosuProps<T> {
  veri: T[];
  sutunlar: SutunTanimi<T>[];
  /** Süzülmüş satırlardan sütun kimliği -> içerik üretir (toplamlar Decimal ile hesaplanmalıdır). */
  toplamSatiri?: (satirlar: T[]) => Record<string, ReactNode>;
  yukleniyor?: boolean;
  hata?: ApiHatasi | null;
  bosMetin?: string;
  /** Boş tabloda metnin altında görünen yönlendirme (örn. "Henüz kayıt yok — Veri Aktar ile yükleyin"). */
  bosAciklama?: string;
  /** Metin aramasının bakacağı alan. */
  aramaAlani?: keyof T;
  satirTikla?: (t: T) => void;
  className?: string;
}

const SAYI = /^-?\d+(\.\d+)?$/;

/** Sayısal metinleri Decimal ile, diğerlerini Türkçe sıralamayla karşılaştırır; boşlar sona. */
function karsilastir(a: unknown, b: unknown): number {
  const bosA = a === null || a === undefined || a === "";
  const bosB = b === null || b === undefined || b === "";
  if (bosA || bosB) return bosA === bosB ? 0 : bosA ? 1 : -1;
  const sa = String(a);
  const sb = String(b);
  if (SAYI.test(sa) && SAYI.test(sb)) return new Decimal(sa).comparedTo(new Decimal(sb));
  return sa.localeCompare(sb, "tr");
}

function sirala<T>(x: LegacyRow<T>, y: LegacyRow<T>, sutunId: string): number {
  return karsilastir(x.getValue(sutunId), y.getValue(sutunId));
}

export function VeriTablosu<T>({
  veri,
  sutunlar,
  toplamSatiri,
  yukleniyor,
  hata,
  bosMetin = "Kayıt yok",
  bosAciklama,
  aramaAlani,
  satirTikla,
  className,
}: VeriTablosuProps<T>) {
  const [arama, setArama] = useState("");
  const [siralama, setSiralama] = useState<SortingState>([]);
  const [odak, setOdak] = useState(0);
  const kapRef = useRef<HTMLDivElement>(null);

  const suzulmus = useMemo(() => {
    const q = arama.trim().toLocaleLowerCase("tr");
    if (!aramaAlani || !q) return veri;
    return veri.filter((s) =>
      String(s[aramaAlani] ?? "")
        .toLocaleLowerCase("tr")
        .includes(q),
    );
  }, [veri, arama, aramaAlani]);

  const sutunlarSiralamali = useMemo(
    () => sutunlar.map((s) => ({ sortFn: sirala, ...s }) as SutunTanimi<T>),
    [sutunlar],
  );

  const tablo = useLegacyTable<T>({
    data: suzulmus,
    columns: sutunlarSiralamali,
    state: { sorting: siralama },
    onSortingChange: setSiralama,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const satirlar = tablo.getRowModel().rows;
  const gorunenSutunlar = tablo.getVisibleLeafColumns();
  const toplam = toplamSatiri && satirlar.length > 0 ? toplamSatiri(suzulmus) : null;

  function tusa(e: KeyboardEvent<HTMLTableRowElement>, i: number, t: T) {
    if (e.target !== e.currentTarget) return; // satır içindeki düğme/girdi kendi tuşlarını yönetir
    const hedefSatir = (n: number) => {
      const el = kapRef.current?.querySelectorAll<HTMLTableRowElement>("tr[data-satir]")[n];
      if (el) {
        setOdak(n);
        el.focus();
      }
    };
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        hedefSatir(Math.min(i + 1, satirlar.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        hedefSatir(Math.max(i - 1, 0));
        break;
      case "Home":
        e.preventDefault();
        hedefSatir(0);
        break;
      case "End":
        e.preventDefault();
        hedefSatir(satirlar.length - 1);
        break;
      case "Enter":
        if (satirTikla) {
          e.preventDefault();
          satirTikla(t);
        }
        break;
    }
  }

  const sutunSayisi = Math.max(gorunenSutunlar.length, 1);

  return (
    <div ref={kapRef} className={cn("flex flex-col gap-2", className)}>
      {aramaAlani && (
        <Input
          type="search"
          aria-label="Tabloda ara"
          placeholder="Ara…"
          value={arama}
          onChange={(e) => setArama(e.target.value)}
          className="max-w-xs"
        />
      )}
      <Table>
        <TableHeader>
          {tablo.getHeaderGroups().map((grup) => (
            <TableRow key={grup.id}>
              {grup.headers.map((h) => {
                const siralanabilir = h.column.getCanSort();
                const yon = h.column.getIsSorted();
                return (
                  <TableHead
                    key={h.id}
                    colSpan={h.colSpan}
                    aria-sort={
                      siralanabilir ? (yon === "asc" ? "ascending" : yon === "desc" ? "descending" : "none") : undefined
                    }
                  >
                    {h.isPlaceholder ? null : siralanabilir ? (
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                        className="inline-flex items-center gap-1 rounded-sm font-medium hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none"
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {yon === "asc" ? (
                          <ArrowUp className="size-3.5" aria-hidden />
                        ) : yon === "desc" ? (
                          <ArrowDown className="size-3.5" aria-hidden />
                        ) : (
                          <ArrowUpDown className="size-3.5 opacity-40" aria-hidden />
                        )}
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {hata ? (
            <TableRow>
              <TableCell colSpan={sutunSayisi}>
                <div role="alert" className="py-6 text-center text-destructive">
                  {hataMetni(hata)}
                </div>
              </TableCell>
            </TableRow>
          ) : yukleniyor ? (
            <TableRow>
              <TableCell colSpan={sutunSayisi}>
                <div role="status" className="flex flex-col gap-2 py-3" aria-label="Yükleniyor">
                  <span className="sr-only">Yükleniyor…</span>
                  {[0, 1, 2, 3, 4].map((i) => (
                    <div key={i} aria-hidden className="h-6 animate-pulse rounded bg-muted" style={{ width: `${95 - i * 6}%` }} />
                  ))}
                </div>
              </TableCell>
            </TableRow>
          ) : satirlar.length === 0 ? (
            <TableRow>
              <TableCell colSpan={sutunSayisi}>
                <div className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
                  <Inbox className="size-8 text-marka" aria-hidden />
                  <span>{bosMetin}</span>
                  {bosAciklama && <span className="text-xs">{bosAciklama}</span>}
                </div>
              </TableCell>
            </TableRow>
          ) : (
            satirlar.map((satir, i) => (
              <TableRow
                key={satir.id}
                data-satir=""
                tabIndex={i === Math.min(odak, satirlar.length - 1) ? 0 : -1}
                onFocus={() => setOdak(i)}
                onKeyDown={(e) => tusa(e, i, satir.original)}
                onClick={
                  satirTikla
                    ? (e) => {
                        if ((e.target as HTMLElement).closest("button, a, input, select, textarea, [role=button]")) return;
                        satirTikla(satir.original);
                      }
                    : undefined
                }
                className={cn(
                  "focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:outline-none focus-visible:ring-inset",
                  satirTikla && "cursor-pointer",
                )}
              >
                {satir.getVisibleCells().map((c) => (
                  <TableCell key={c.id}>{flexRender(c.column.columnDef.cell, c.getContext())}</TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
        {toplam && !hata && !yukleniyor && (
          <TableFooter>
            <TableRow>
              {gorunenSutunlar.map((s) => (
                <TableCell key={s.id} className="font-medium tabular-nums">
                  {toplam[s.id] ?? null}
                </TableCell>
              ))}
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </div>
  );
}
