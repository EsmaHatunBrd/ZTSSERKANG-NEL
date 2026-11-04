import { expect, test } from "@playwright/test";
import { E2E_KULLANICI, E2E_SIFRE } from "./giris-kurulumu";

// Oturumsuz bağlam: kayıtlı çerez kullanılmaz.
test.use({ storageState: { cookies: [], origins: [] } });

test("giriş: oturumsuz açılış giriş ekranı → yanlış şifre mesajı → giriş → Ana Sayfa kartları → Genel Bakış → çıkış", async ({ page }) => {
  await page.goto("/genel-bakis");
  await expect(page.getByRole("heading", { name: "Fiyat Çalışması" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Ana menü" })).toHaveCount(0);

  await page.getByLabel("Kullanıcı adı").fill(E2E_KULLANICI);
  await page.getByLabel("Şifre").fill("yanlis-sifre");
  await page.getByRole("button", { name: /Giriş yap/ }).click();
  await expect(page.getByRole("alert")).toContainText("kullanıcı adı ya da şifre yanlış");

  await page.getByLabel("Şifre").fill(E2E_SIFRE);
  await page.getByRole("button", { name: /Giriş yap/ }).click();
  // Giriş öncesi istenen adres korunur (Genel Bakış); kök adres Ana Sayfa kartlarını gösterir.
  await expect(page.getByRole("button", { name: /Hesabım: E2E Yönetici/ })).toBeVisible();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Hoş geldiniz" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Yönetim" }).getByRole("link", { name: /Kullanıcılar/ })).toBeVisible();
  await page
    .getByRole("region", { name: "Çalışma" })
    .getByRole("link", { name: /Genel Bakış/ })
    .click();
  await expect(page).toHaveURL(/\/genel-bakis/);
  await expect(page.getByText("Ürün sayısı", { exact: true })).toBeVisible();

  // Sayfa yenilense de oturum açık kalır (çerez tarayıcıda kalıcı).
  await page.reload();
  await expect(page.getByRole("button", { name: /Hesabım: E2E Yönetici/ })).toBeVisible();

  await page.getByRole("button", { name: "Çıkış yap" }).click();
  await expect(page.getByLabel("Kullanıcı adı")).toBeVisible();
});
