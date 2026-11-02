import { yuzdeBicimle } from "@/yardimcilar/para";

/** Parametre anahtarı (faiz.TL, kur.USD...) -> ekranda gösterilecek Türkçe etiket; bilinmeyen anahtar olduğu gibi döner. */
export function parametreEtiketi(anahtar: string): string {
  if (anahtar.startsWith("faiz.")) return `Faiz ${anahtar.slice(5)} (%)`;
  if (anahtar.startsWith("stok_ay.")) return `Stok süresi ${anahtar.slice(8)} (ay)`;
  if (anahtar.startsWith("kur.")) return `${anahtar.slice(4)} kuru`;
  if (anahtar.startsWith("teklif_kar.")) return `Teklif ${anahtar.slice(11)} kârı (%)`;
  switch (anahtar) {
    case "enflasyon":
      return "Enflasyon (%)";
    case "maliyet_sapma":
      return "Maliyet sapma (%)";
    case "vardiya_saati":
      return "Vardiya saati";
    case "satis_kar":
      return "Satış kârı (%)";
    default:
      return anahtar;
  }
}

const ORAN = /^(faiz\.|teklif_kar\.)|^(enflasyon|maliyet_sapma|satis_kar)$/;

/** Oran parametreleri yüzde olarak, ay/saat/kur düz sayı olarak gösterilir. */
export function parametreDegerGoster(anahtar: string, deger: string): string {
  return ORAN.test(anahtar) ? yuzdeBicimle(deger) : deger.replace(".", ",");
}
