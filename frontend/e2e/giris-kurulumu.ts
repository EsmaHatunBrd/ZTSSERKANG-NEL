import { request, type FullConfig } from "@playwright/test";

/** e2e/kurulum.py'nin açtığı test yöneticisi (yalnız her koşuda sıfırlanan e2e.db'de). */
export const E2E_KULLANICI = "e2e.yonetici";
export const E2E_SIFRE = "e2e-sifre-1";
/** Giriş yapılmış oturumun (çerez) kaydı; testler bununla başlar. Depoya girmez (.gitignore). */
export const OTURUM_DOSYASI = "e2e/.oturum.json";

/** Sunucular kalktıktan sonra bir kez giriş yapar ve çerezi kaydeder: testler giriş ekranını her seferinde geçmez. */
export default async function girisKurulumu(config: FullConfig): Promise<void> {
  const baseURL = config.projects[0].use.baseURL;
  const r = await request.newContext({ baseURL });
  const y = await r.post("/api/v1/kimlik/giris", { data: { kullanici_adi: E2E_KULLANICI, sifre: E2E_SIFRE } });
  if (!y.ok()) throw new Error(`e2e girişi başarısız: ${y.status()} ${await y.text()}`);
  await r.storageState({ path: OTURUM_DOSYASI });
  await r.dispose();
}
