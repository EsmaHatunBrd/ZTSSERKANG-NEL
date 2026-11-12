# Fiyat Çalışması - Frontend okubeni

## Önkoşullar
- Node.js 20 veya üstü (npm ile birlikte).
- Python sanal ortamı proje kökünde: `.venv` (bağımlılıklar kurulu; backend ve e2e kurulumu bunu kullanır).
- Excel çalışma kitabı proje kökünde: `Fiyat Çalışma - 2026-2027 - Berrak.xlsx` (yalnız e2e için).

## Kurulum
```
cd frontend
npm i
npx playwright install chromium   # yalnız ilk e2e öncesi
```

## Backend'i başlatma (proje kökünden)
```
.\.venv\Scripts\python -m uvicorn backend.uygulama:app --port 8000
```
Veritabanı varsayılan olarak `veri/fiyat.db`; başka dosya için `VERITABANI_URL=sqlite:///<mutlak yol>` ortam değişkeni. API belgeleri: http://127.0.0.1:8000/docs

## API tiplerini üretme
Backend çalışırken:
```
npm run api:tipler
```
`src/api/sema.d.ts` yeniden üretilir; alan adı farklarında `tsc` hata verir.

## Geliştirme sunucusu
```
npm run dev
```
Vite portu **5180**'dir (5173 bazı makinelerde başka süreçte kullanılıyor; doluysa Vite sonraki boş portu seçer). `/api` istekleri Vite proxy ile `http://127.0.0.1:8000` adresine gider.

**API adresi:** Arayüz her zaman aynı kökenli `/api` yolunu çağırır; Vite bunu `vite.config.ts` içindeki proxy ile `http://127.0.0.1:8000` adresine yönlendirir. Başka bir porttaki backend için `API_PORT` ortam değişkeni (ör. `API_PORT=8010 npm run dev`); başka bir adres için `vite.config.ts` içinde `server.proxy["/api"]` hedefini değiştirin (üretimde arayüzü ve API'yi aynı alan adı altında ters vekil/reverse proxy ile sunun). `VITE_API_URL` değişkeni kod tarafından **okunmaz** (`.env.example` içinde "henüz kullanılmıyor" notuyla durur).

## Testler
- Birim/bileşen: `npm test -- --run` (Vitest, jsdom, MSW).
- Uçtan uca: `npm run e2e` (Playwright, Chromium). Playwright iki sunucuyu kendisi başlatır:
  1. `e2e/kurulum.py`: `veri/e2e.db` silinir, gerçek Excel içe aktarılır (~15 sn, senaryo "E2E"), uvicorn **8010** portunda açılır (geliştirme backend'i 8000 ile çakışmaz; Vite proxy `API_PORT` ile yönlendirilir). 8010 doluysa `E2E_API_PORT=8012 npm run e2e` gibi başka bir port verilebilir; testlerde sabit port kullanılmaz (`request.get("/api/v1/…")` baseURL üzerinden vekillenir).
  2. Vite, 5190 portunda.
  Önce 8000 ve 5190 portları boş olmalıdır. Testler: `e2e/duman.spec.ts` (ana akış), `e2e/erisilebilirlik.spec.ts` (8 rota x 2 görünüm, koyu tema, odak halkası). İz için: `npx playwright show-trace`.

## Sorun giderme
- **Port kullanımda (8000/5190):** `Get-NetTCPConnection -LocalPort 8000 | Select OwningProcess` ile süreci bulup kapatın. e2e `reuseExistingServer: false` olduğundan çalışan bir sunucu varsa başlamaz.
- **Excel bulunamadı / açılamadı:** dosya proje kökünde `Fiyat Çalışma - 2026-2027 - Berrak.xlsx` adıyla olmalı ve Excel'de açık olmamalı (`~$...` kilit dosyası sorun çıkarmaz ama açık dosya okunamayabilir).
- **`veri/e2e.db` kilitli:** önceki backend süreci hâlâ çalışıyordur; kapatıp tekrar deneyin. Dosya her e2e öncesi silinip yeniden oluşturulur; elle silmek güvenlidir.
- **`npm run api:tipler` bağlanamıyor:** backend çalışmıyordur (8000).
- **Boş ekran / "Senaryo yok":** veritabanında senaryo yoktur; Excel'i "Reçete Aktar" sayfasından veya `POST /api/v1/import/excel-tam` ile içe aktarın.
- **Chromium bulunamadı:** `npx playwright install chromium`.
