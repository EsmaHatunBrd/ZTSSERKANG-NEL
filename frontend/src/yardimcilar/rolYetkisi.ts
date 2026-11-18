import type { Rol } from "@/api/sorgular/kimlik";

/**
 * Rol yetkisinin TEK kaynağı (arayüz tarafı; sunucudaki kimlik_servisi.yazabilir_mi ile aynı kural).
 *
 * Yazma alanları:
 * - `genel`: Fiyat Çalışması ve Maliyet Muhasebesi'nin geri kalanı (reçete, parametre, gider, satış, liste, teklif, senaryo…).
 * - `malzeme`: malzeme kartı ve fiyatı. Bu alanı kullanan ekranlar (sayfa `YazmaAlaniSaglayici alan="malzeme"` ile işaretlenir):
 *   Malzeme Fiyatları · Veri Aktar › Satın alma fiyat listesi sekmesi · Veri Girişi › Yeni malzeme ve Malzeme fiyatı kartları.
 *
 * Giriş zorunlu değilse (tek kullanıcılı kurulum) her alana yazılır.
 */
export type YazmaAlani = "genel" | "malzeme";

const ROL_YAZMA_ALANLARI: Record<Rol, readonly YazmaAlani[]> = {
  genel_direktor: ["genel", "malzeme"],
  muhasebe: ["genel", "malzeme"],
  satin_alma: ["malzeme"],
  izleyici: [],
};

/** Rol bu alanda değişiklik yapabilir mi (düzenleme kilidi açılabilir mi). */
export function alanaYazabilir(girisZorunlu: boolean, rol: Rol | null, alan: YazmaAlani): boolean {
  if (!girisZorunlu) return true;
  return rol !== null && (ROL_YAZMA_ALANLARI[rol]?.includes(alan) ?? false);
}

/** "Yeni çalışma" ve senaryo işlemleri (Düzenle… / Sil…) menüsü: yalnız genel alana yazabilen roller. */
export function senaryoYonetebilir(girisZorunlu: boolean, rol: Rol | null): boolean {
  return alanaYazabilir(girisZorunlu, rol, "genel");
}

/** Rol bu alana yazamıyorsa düzenleme kilidi şeridinde görünen metin. */
export function saltOkunurMetni(rol: Rol | null): string {
  if (rol === "izleyici") return "Salt okunur: izleyici rolü değişiklik yapamaz";
  if (rol === "satin_alma") return "Salt okunur: satın alma rolü bu sayfada değişiklik yapamaz";
  return "Salt okunur: bu rol bu sayfada değişiklik yapamaz";
}
