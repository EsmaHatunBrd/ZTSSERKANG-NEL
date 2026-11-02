import { Badge } from "@/bilesenler/ui/badge";

export type KaynakTuru =
  | "fire"
  | "elle"
  | "liste"
  | "satir"
  | "malzeme"
  | "yok"
  | "import"
  | "import-revize"
  | "-"
  | `grup:${string}`
  | `tip:${string}`;

const SABIT: Record<string, string> = {
  fire: "Fire",
  elle: "Elle",
  liste: "Liste",
  satir: "Satır",
  malzeme: "Malzeme",
  yok: "Yok",
  import: "İçe aktarma",
  "import-revize": "İçe aktarma (revize)",
};

/** Malzeme Z/S bayrağı (muhasebe, 23.10.2026): Z = Ziraat'ten (kendi tarımından) gelen, enflasyon uygulanmaz;
 * S = satın alma, TL fiyata enflasyon, dövize kur. Hesap motoru zaten böyle çalışır; bu yalnız etiket. */
export const ZS_ACIKLAMA = "Ziraat: enflasyon uygulanmaz · Satın alma: TL fiyata enflasyon, dövize kur";

export function zsEtiketi(zs: string | null | undefined): string {
  const v = (zs ?? "").trim().toUpperCase();
  if (v === "Z") return "Ziraat";
  if (v === "S") return "Satın alma";
  return v || "—";
}

export function kaynakMetni(tur: string): string | null {
  if (tur === "-" || tur === "") return null;
  if (tur.startsWith("grup:")) return `Grup: ${tur.slice(5)}`;
  if (tur.startsWith("tip:")) return `Tip: ${tur.slice(4)}`;
  return SABIT[tur] ?? tur;
}

/** Miktar/fiyat/fire kaynağını gösteren küçük rozet. "-" (gider satırı) için boş döner. */
export function KaynakRozeti({ tur }: { tur: KaynakTuru | (string & {}) | null | undefined }) {
  const metin = tur ? kaynakMetni(tur) : null;
  if (!metin) return null;
  const vurgulu = tur === "elle" || tur === "yok";
  return <Badge variant={tur === "yok" ? "destructive" : vurgulu ? "default" : "secondary"}>{metin}</Badge>;
}
