/**
 * Dashboard ilk yükleme beklemesi (ms). Soğuk hesap boş makinede ~2 sn; e2e kurulumu, Vite ve tarayıcı aynı anda
 * başlarken 15 sn aşılabiliyor (23.10 ölçümü), bu yüzden 30 sn. Dashboard'a bağlı her bekleme bu tek sabiti kullanır.
 */
export const DASHBOARD_BEKLEME_MS = 30_000;

/**
 * Dashboard'a girmeden ürün ekranını doğrudan açan testler için gerçek kitaptaki ilk ürünün kodu
 * (e2e/kurulum.py kitabı her koşuda yeniden yükler; kod kitapla birlikte sabittir).
 */
export const E2E_URUN_KODU = "03.004.001.002.00010";
