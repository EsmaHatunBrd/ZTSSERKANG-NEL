# Faz 4: Frontend (React) - Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Muhasebe ekibinin kullanacağı, Faz 2 API'sine bağlanan modern ve sade bir web arayüzü: Dashboard (Teklif Kapak), Ürün Maliyeti (tek tabloda firesiz/fireli), Reçete Aktar, Malzeme Fiyatları, Parametreler, Gider Dağıtım, Teklif; Türkçe, açık/koyu tema, klavyeyle kullanılabilir.

**Architecture:** `frontend/` ayrı bir Vite + React 18 + TypeScript projesi. API tipleri backend'in `/openapi.json` çıktısından **üretilir** (`openapi-typescript`), elle yazılmaz; böylece sözleşme değişince derleme hatası verir. Sunucu durumu TanStack Query, tablolar TanStack Table, formlar react-hook-form + zod, bileşenler shadcn/ui + Tailwind, grafikler Recharts. Para değerleri API'den string gelir, ekranda `decimal.js` ile toplanır ve `Intl.NumberFormat("tr-TR")` ile biçimlenir. Geliştirmede Vite proxy `/api` → `http://127.0.0.1:8000` (CORS'a gerek kalmaz).

**Tech Stack:** Node 20+, Vite 5, React 18, TypeScript 5, Tailwind 3, shadcn/ui, TanStack Query 5, TanStack Table 8, react-hook-form 7, zod 3, decimal.js 10, Recharts 2, openapi-typescript 7 + openapi-fetch, Vitest + Testing Library + MSW (API sahteleme), Playwright (1 duman testi).

**Spec:** `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` (§4 API, §5 ekranlar), `docs/10-21-2026-faz2b-firesiz-fireli-elle-deger-plani.md` (T4-T5: yanıt alanları ve Ürün Maliyeti ekranı).

## Global Constraints

- Tip kaynağı `frontend/src/api/sema.d.ts` = `openapi-typescript` çıktısı; alan adları koddan değil bu dosyadan gelir. Üretim komutu `npm run api:tipler` (backend çalışırken `http://127.0.0.1:8000/openapi.json`); üretilen dosya depoda tutulur.
- Para: API string → ekranda `Decimal` (decimal.js); `number`a çevrilerek toplama **yapılmaz**. Gösterim `1.234.567,89` (tr-TR), sağa hizalı.
- Tarih gösterimi `GG.AA.YYYY`, API'ye ISO.
- Tüm metinler Türkçe; `X-Kullanici` başlığı `encodeURIComponent` ile gönderilir (backend `unquote` eder); kullanıcı adı ayarlar panelinden girilir, `localStorage`'da tutulur.
- Yazma işlemleri: "neden" alanı zorunlu olanlarda (fiyat, parametre, fire kuralı) form doğrulamasıyla; silme yok, pasifleştirme var; kaydetmeden önce özet onayı.
- Her tablo: sıralama, filtre/arama, boş/yükleniyor/hata durumu, toplam satırı; klavye gezinmesi.
- Düzen: 1280px masaüstü öncelikli, 768px'e kadar bozulmaz; açık/koyu tema (`prefers-color-scheme` + anahtar).
- Dosya adlandırma: TS/TSX modülleri import kuralına uyar; yeni belgeler `MM-DD-YYYY-açıklama`. Git yok (kullanıcı istemedi).
- Faz 4'te kimlik doğrulama yok; `X-Kullanici` yalnız kayıt amaçlı.
- Testler: her sayfa için MSW ile en az bir render + bir etkileşim testi; para biçimleme ve `Decimal` toplama birim testleri; bir Playwright duman testi (backend + frontend gerçek).

---

## Dosya Yapısı

```
frontend/
├── package.json  vite.config.ts  tsconfig.json  tailwind.config.ts  index.html  .env.example
├── src/
│   ├── main.tsx  App.tsx  yonlendirme.tsx            # React Router: /, /urunler/:kod, /recete-aktar, /fiyatlar, /parametreler, /gider, /teklifler
│   ├── api/
│   │   ├── sema.d.ts                                 # ÜRETİLEN (openapi-typescript)
│   │   ├── istemci.ts                                # openapi-fetch client, X-Kullanici, hata gövdesi -> ApiHatasi
│   │   └── sorgular/                                 # TanStack Query hook'ları (urunler.ts, hesap.ts, malzemeler.ts, parametreler.ts, gider.ts, teklifler.ts, import.ts, senaryolar.ts)
│   ├── yardimcilar/
│   │   ├── para.ts                                   # D(), paraBicimle(), yuzdeBicimle(), topla()
│   │   ├── tarih.ts
│   │   └── kullanici.ts                              # localStorage kullanıcı adı
│   ├── bilesenler/
│   │   ├── ui/                                       # shadcn üretimleri (button, input, table, dialog, select, badge, tabs, toast, sheet, tooltip)
│   │   ├── VeriTablosu.tsx                           # TanStack Table sarmalayıcı: sıralama, filtre, toplam satırı, boş/yükleniyor/hata
│   │   ├── ParaHucresi.tsx  YuzdeHucresi.tsx  UyariRozeti.tsx  KaynakRozeti.tsx
│   │   ├── SenaryoSecici.tsx  KullaniciAyari.tsx  TemaAnahtari.tsx  Kabuk.tsx (yan menü + üst bar)
│   │   └── GecmisCekmecesi.tsx                       # parametre/fiyat geçmişi + "geri al" (eski değeri yeni kayıt olarak ekle)
│   ├── sayfalar/
│   │   ├── Dashboard.tsx
│   │   ├── UrunMaliyeti.tsx  (+ ReceteTablosu.tsx, GiderKalemleri.tsx, YuzdeGrafigi.tsx, TeklifPaneli.tsx, NeOlurPaneli.tsx)
│   │   ├── ReceteAktar.tsx
│   │   ├── MalzemeFiyatlari.tsx
│   │   ├── Parametreler.tsx
│   │   ├── GiderDagitim.tsx
│   │   └── Teklifler.tsx
│   └── test/ (kurulum, msw/ sunucu + işleyiciler, fikstürler)
├── e2e/duman.spec.ts
└── 10-21-2026-frontend-okubeni.md                    # kurulum ve çalıştırma
```

---

### Task 1: Proje iskeleti, tema, kabuk ve para yardımcıları

**Files:** Create `frontend/` (Vite React-TS şablonu), Tailwind + shadcn kurulumu (`button input table dialog select badge tabs toast sheet tooltip`), `src/yardimcilar/para.ts`, `src/yardimcilar/tarih.ts`, `src/yardimcilar/kullanici.ts`, `src/bilesenler/Kabuk.tsx`, `TemaAnahtari.tsx`, `KullaniciAyari.tsx`, `src/yonlendirme.tsx`, `src/test/kurulum.ts`, `src/yardimcilar/para.test.ts`

**Interfaces:**
- `para.D(x: string | number | Decimal | null | undefined): Decimal` (null → 0; string virgüllü girişleri `"1.234,56"` → `1234.56` çevirir)
- `para.paraBicimle(x, paraBirimi?: "TL"|"USD"|"EUR", basamak = 2): string` → `"1.234,56 TL"`; `para.yuzdeBicimle(oran, basamak = 1)` → `"19,7 %"`; `para.topla(xs: (string|Decimal)[]): Decimal`; `para.apiMetni(d: Decimal): string` (API'ye gönderilecek düz string, nokta ondalık)
- `tarih.goster(iso: string): "GG.AA.YYYY"`, `tarih.bugunIso()`
- `kullanici.al(): string` (yoksa `"sistem"`), `kullanici.kaydet(ad)`

- [ ] **Step 1: Test** (`para.test.ts`)
```ts
import { describe, expect, it } from "vitest";
import { D, paraBicimle, topla, yuzdeBicimle, apiMetni } from "./para";
describe("para", () => {
  it("string ondalığı kaybetmez", () => { expect(topla(["0.1", "0.2"]).toString()).toBe("0.3"); });
  it("tr-TR biçimler", () => { expect(paraBicimle("38.130789", "TL")).toBe("38,13 TL"); expect(paraBicimle("1234567.891", "USD", 3)).toBe("1.234.567,891 USD"); });
  it("virgüllü girişi okur", () => { expect(D("1.234,56").toString()).toBe("1234.56"); expect(apiMetni(D("1.234,56"))).toBe("1234.56"); });
  it("yüzde", () => { expect(yuzdeBicimle("0.19736")).toBe("19,7 %"); });
  it("boş değer sıfır", () => { expect(D(null).toString()).toBe("0"); });
});
```
- [ ] **Step 2:** `npm create vite@latest frontend -- --template react-ts`, bağımlılıklar (`npm i @tanstack/react-query @tanstack/react-table react-hook-form zod @hookform/resolvers decimal.js recharts react-router-dom openapi-fetch` ve dev: `openapi-typescript vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom msw @playwright/test tailwindcss postcss autoprefixer`), `npx shadcn@latest init` + bileşenler; `vite.config.ts` içinde `server.proxy["/api"] = "http://127.0.0.1:8000"` ve vitest ayarı (`environment: "jsdom"`, `setupFiles: ["src/test/kurulum.ts"]`).
- [ ] **Step 3:** test kırmızı → `para.ts` vb. uygula → yeşil. `Kabuk`: sol menü (7 sayfa), üst bar (SenaryoSecici yer tutucu, KullaniciAyari, TemaAnahtari). Tema: Tailwind `darkMode: "class"`, `html` sınıfı `localStorage` + `prefers-color-scheme`.
- [ ] **Step 4:** `npm run build` hatasız; `npm test` yeşil.

---

### Task 2: API istemcisi, üretilen tipler, sorgu hook'ları, MSW

**Files:** Create `src/api/sema.d.ts` (üretilen), `src/api/istemci.ts`, `src/api/sorgular/*.ts`, `src/test/msw/{sunucu,isleyiciler}.ts`, `src/test/fikstur/{hesapYaniti,urunler,parametreler}.ts`, `src/api/istemci.test.ts`; Modify `package.json` (`"api:tipler": "openapi-typescript http://127.0.0.1:8000/openapi.json -o src/api/sema.d.ts"`)

**Interfaces:**
- `istemci.ts`: `export const api = createClient<paths>({ baseUrl: "/api/v1", headers: () => ({ "X-Kullanici": encodeURIComponent(kullanici.al()) }) })`; `export class ApiHatasi extends Error { hata: string; mesaj: string; alanlar: Record<string, unknown>; durum: number }`; `export async function cagir<T>(p: Promise<{data?: T; error?: unknown; response: Response}>): Promise<T>` — `error` varsa gövdeyi `ApiHatasi`'ye çevirir (backend gövdesi `{hata, mesaj, alanlar}`), ağ hatasında `ApiHatasi("ag", "Sunucuya ulaşılamadı")`.
- Hook'lar (her biri `queryKey` sözleşmesi ile): `useSenaryolar()`, `useUrunler(senaryo, {sayfa, boyut, gecici?})`, `useUrun(kod, senaryo)`, `useRecete(kod, senaryo)`, `useHesapla()` (mutation: `POST /urunler/{kod}/hesapla`, kaydetmez), `useHesapKaydet()`, `useHesaplar(kod, senaryo)`, `useHesap(id)`, `useTeklifler(hesapId)`, `useTeklifEkle()`, `useMalzemeler(senaryo, {fiyatsiz, sayfa, boyut, arama})`, `useFiyatGecmisi(kod, senaryo)`, `useFiyatEkle()`, `useParametreler(senaryo, tarih?)`, `useParametreTanimlari()`, `useParametreGecmisi(anahtar, senaryo)`, `useParametreEkle()`, `useGiderHavuzlari(senaryo)`, `useHavuzKaydet()`, `useAmbalajlar(senaryo)`, `useFireKurallari(senaryo)`, `useFireKuraliEkle()`, `useMalzemeGruplari()`, `useGrupOlustur()`, `useImportFiyatOnizle()`, `useImportFiyatUygula()`, `useImportExcelTam()`, `useUyarilar(senaryo)`. Mutation'lar ilgili `queryKey`'leri `invalidateQueries` eder.
- MSW işleyicileri: Dashboard listesi (3 ürün, biri `hata` dolu), `/hesapla` yanıtı (fikstür = tasarım §4 örneği + `toplamlar_firesiz`/`fiyatlar_firesiz` + satırlarda `tutar_firesiz`, `miktar_kaynagi`, `fiyat_kaynagi`), parametreler, malzemeler (biri fiyatsız, biri `kart_yok`), geçmişler, 404/422 örnekleri.

- [ ] **Step 1:** Backend'i başlat (`.\.venv\Scripts\python -m uvicorn backend.uygulama:app`), `npm run api:tipler` çalıştır; `sema.d.ts` üretilsin (yoksa görev duraklar, NEEDS_CONTEXT).
- [ ] **Step 2: Test** (`istemci.test.ts`, MSW): 200 → veri döner; 404 gövdesi → `ApiHatasi.hata === "bulunamadi"`, `.mesaj` Türkçe; ağ hatası → `hata === "ag"`; `X-Kullanici` başlığı yüzde kodlanmış (`"Eşma"` → `"E%C5%9Fma"`).
- [ ] **Step 3-4:** uygula, yeşil.

---

### Task 3: VeriTablosu ve ortak hücreler

**Files:** Create `src/bilesenler/VeriTablosu.tsx`, `ParaHucresi.tsx`, `YuzdeHucresi.tsx`, `UyariRozeti.tsx`, `KaynakRozeti.tsx`, `SenaryoSecici.tsx`, `GecmisCekmecesi.tsx`, testler.

**Interfaces:**
- `VeriTablosu<T>({ veri, sutunlar: ColumnDef<T>[], toplamSatiri?: (satirlar: T[]) => Record<string, ReactNode>, yukleniyor?, hata?: ApiHatasi | null, bosMetin?, aramaAlani?: keyof T, satirTikla?: (t: T) => void })` — sıralama, metin arama, klavye (ok tuşları + Enter), `aria-sort`, boş/yükleniyor/hata durumları.
- `ParaHucresi({ deger: string | null, paraBirimi?, basamak? })` sağa hizalı tabular-nums; negatif kırmızı; `null` → "—".
- `KaynakRozeti({ tur: "fire" | "elle" | "liste" | "satir" | "grup:..." | "malzeme" | "tip:..." | "yok" | "-" })`: metin "Fire", "Elle", "Liste", "Satır", "Grup: X", "Malzeme", "Tip: X", "Yok".
- `SenaryoSecici`: `useSenaryolar`, seçim URL query `?senaryo=` ve `localStorage`; sayfalar `useSenaryo()` hook'undan okur (Context).
- `GecmisCekmecesi({ baslik, kayitlar: {deger, gecerlilik_basi, neden, olusturan, olusturma_zamani}[], geriAl?: (kayit) => void })`: "Geri al" eski değeri **yeni kayıt** olarak ekler (neden otomatik: `"Geri alındı: <tarih> değeri"`).

- [ ] Testler: tablo sıralama tıklaması sırayı değiştirir; toplam satırı `Decimal` ile toplar (`"0.1"+"0.2"` → `"0,30 TL"`); hata durumunda `ApiHatasi.mesaj` görünür; `KaynakRozeti("grup:Hassas")` → "Grup: Hassas".

---

### Task 4: Dashboard (Teklif Kapak)

**Files:** Create `src/sayfalar/Dashboard.tsx`, `Dashboard.test.tsx`

Sütunlar: Kod, Ürün, Ambalaj (ml), Hat, Reçete Maliyeti, GÜG, Faaliyet, Finans, Gider %, Maliyet TL (fireli), Maliyet TL (firesiz), Maliyet USD, Maliyet EUR, Satış TL, Üretim Adedi, Uyarı (sayı rozeti, tıklayınca liste), Durum (`hata` varsa kırmızı rozet + mesaj). Üst kartlar: ürün sayısı, hata sayısı, fiyatsız malzeme sayısı (`useMalzemeler(fiyatsiz)` toplam), pay toplamı uyarısı (`useGiderHavuzlari().pay_kontrol` boş değilse). Filtreler: geçici kodlu ürünler (`gecici=true`), hat, metin arama. "Excel'e aktar" düğmesi → `GET /disa-aktar/urunler.xlsx?senaryo=` (indirme). Satıra tıkla → `/urunler/:kod`.

- [ ] Testler (MSW): 3 satır render; `hata` satırı rozetli; "Excel'e aktar" `href` doğru; arama filtreler; toplam satırı maliyet sütunlarında görünmez (anlamsız), üretim adedinde toplam var.

---

### Task 5: Ürün Maliyeti ekranı (tek tablo, firesiz/fireli, ne olur, kaydet, teklif)

**Files:** Create `src/sayfalar/UrunMaliyeti.tsx`, `ReceteTablosu.tsx`, `GiderKalemleri.tsx`, `YuzdeGrafigi.tsx`, `NeOlurPaneli.tsx`, `TeklifPaneli.tsx`, testler.

Davranış:
- Sayfa açılınca `useRecete` + `useHesapla` (kaydetmeden) çalışır; başlıkta ürün adı/kodu, senaryo, hesap tarihi (değiştirilebilir, ISO'ya çevrilir).
- **ReceteTablosu** sütunları: Sıra, Kod, Malzeme, Miktar, Fire % (satır içi düzenlenebilir; elle brüt doluysa pasif), Brüt Miktar, Miktar kaynağı (KaynakRozeti: Fire / Elle; tıklayınca "Elle brüt gir" ↔ "Fire oranı uygula" geçişi), Birim Fiyat, Fiyat kaynağı (Liste / Elle; tıklayınca elle fiyat gir / listeye dön), Döviz, **Tutar (firesiz)**, **Tutar (fireli)**, Maliyet %, Satış %. Altta iki toplam: "Malzeme toplamı (firesiz) / (fireli)". Düzenlemeler **önce** `NeOlur` durumuna yazılır (override: `fire`, satır elle değerleri ise yeni reçete versiyonu gerektirir → "Reçeteyi kaydet" düğmesi `POST /urunler/{kod}/recete` ile yeni versiyon açar; onay diyaloğu özetle).
- **GiderKalemleri**: işçilik, GÜG, pazarlama/yönetim, finansman satırları; finansman bloğunda faiz ve stok süresi inline override (`parametreler` override'ı).
- **Toplamlar kartı**: Toplam birim maliyet, Giydirilmiş, Finansman, **Maliyet TL (fireli | firesiz)**, USD, EUR, **Satış TL (fireli | firesiz)**, Süzme kg fiyatı, Teklifler USD (1/2/3).
- **YuzdeGrafigi** (Recharts yatay çubuk): kalemlerin maliyet % ve satış % payı; `dataviz` kurallarına uygun tek renk ailesi, tooltip'te tam değer.
- **NeOlurPaneli**: aktif override'ların listesi (parametre, fire, üretim), "Sıfırla"; her değişiklikte `useHesapla` yeniden koşar (debounce 300 ms). "Hesabı kaydet" → `POST /hesaplar` (override dahil), başarı toast'ı + hesap id.
- **TeklifPaneli**: kayıtlı hesap seçimi (`useHesaplar`), tur listesi, "Yeni tur" (kâr %, müşteri, not) → `useTeklifEkle`; durum değiştirme (taslak/gönderildi/kabul/red).
- Uyarılar: sağ üstte `UyariRozeti` + açılır liste (`uyarilar`), "fiyat listesinde yok" satırları tabloda sarı vurgu.
- Yurtdışı ürünlerde sarı bant: "Yurtdışı yüzde kuralı doğrulanmadı".

- [ ] Testler (MSW): fikstür hesapla yanıtıyla tablo iki tutar sütununu ve iki toplamı gösterir; fire hücresini değiştirince `POST /hesapla` override `{fire:{sira:oran}}` ile çağrılır (MSW isteği yakalar); "Kaydet" `POST /hesaplar` çağırır ve toast gösterir; elle brüt moduna geçince fire hücresi pasifleşir; kaynak rozetleri doğru metin.

---

### Task 6: Malzeme Fiyatları, Parametreler, Gider Dağıtım

**Files:** `src/sayfalar/MalzemeFiyatlari.tsx`, `Parametreler.tsx`, `GiderDagitim.tsx`, testler.

- **MalzemeFiyatları**: tablo (kod, ad, tip, birim, para, Z/S, geçerli fiyat, geçerlilik, kaynak), filtre "fiyatsız" (kart yok olanlar "Kart yok" rozetiyle), satır içi fiyat düzenleme → diyalog (fiyat, geçerlilik tarihi varsayılan bugün, neden zorunlu) → `useFiyatEkle`; geçmiş simgesi → `GecmisCekmecesi` (+ geri al); "Fiyat listesi yükle" → dosya seç → önizleme tablosu (değişen/yeni/aynı/hatalı sekmeleri) → "Uygula" (geçerlilik tarihi + neden) → sonuç.
- **Parametreler**: `useParametreTanimlari` + `useParametreler`; gruplu form (Genel: enflasyon, satış kârı, vardiya saati; Kurlar; Faiz; Stok süresi; Teklif kâr oranları; Dağıtım çarpanları (salt okunur, "Faz 3")); her alanda geçerli değer, "Değiştir" → diyalog (değer, geçerlilik, neden, kapsam: genel / ürün seç) → `useParametreEkle`; geçmiş çekmecesi + geri al; gerçekleşen senaryoda enflasyon alanı kilitli ve açıklamalı.
- **GiderDagıtım**: havuz kartları (toplam, baz tipi, baz miktar, birim oran), anahtar tabloları (alt kalem, pay %, baz; pay toplamı göstergesi %100 değilse kırmızı), ambalaj sınıfları tablosu (ad, hacim, adet, katsayı); düzenleme → `useHavuzKaydet` / ambalaj PUT; onay özeti.

- [ ] Testler: fiyat ekleme diyaloğu "neden" boşsa gönderilmez; fiyatsız filtresi `kart_yok` satırını gösterir; parametre geçmişi "Geri al" eski değeri `POST` eder; pay toplamı 0,567 kırmızı gösterilir.

---

### Task 7: Reçete Aktar, Teklifler, dosya yükleme ve uyarılar sayfası

**Files:** `src/sayfalar/ReceteAktar.tsx`, `Teklifler.tsx`, `Uyarilar.tsx` (menüde "Uyarılar"), testler.

- **ReceteAktar**: iki mod: (a) "Tüm çalışma kitabı" (`POST /import/excel-tam`: dosya, sezon adı, senaryo adı, tür, kartları güncelle) → özet kartları (malzeme, fiyat, ürün, atlanan, uyarılar, kart farkları, yeniden adlandırılan); (b) ürün reçetesi (Faz 5: şimdilik "yakında" kartı ve `POST /urunler/{kod}/recete` ile elle satır girişi formu: kod, ad, miktar, birim, fire/elle brüt, fiyat liste/elle).
- **Teklifler**: tüm senaryo için kayıtlı hesaplar + turlar listesi (ürün, tur, kâr, TL/USD/EUR, müşteri, durum, tarih); filtre durum/müşteri; satırdan ürün ekranına geçiş; yazdırma görünümü (CSS print) "Teklif özeti".
- **Uyarılar**: `useUyarilar(senaryo)` — ürün başına uyarı listesi, türüne göre gruplama (metin ön ekine göre: "fiyat listesinde yok", "kur", "hat", "sınıf", "Yurtdışı", "vardiya"), ürün bağlantıları.

- [ ] Testler: excel-tam formu dosyasız gönderilmez; özet kartları fikstürle render; uyarılar gruplanır.

---

### Task 8: Uçtan uca duman testi, okubeni, tasarım temizliği

**Files:** `frontend/e2e/duman.spec.ts`, `frontend/10-21-2026-frontend-okubeni.md`; Modify `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` ("Faz 4 sonucu").

- Playwright: backend'i gerçek Excel import'uyla başlat (test öncesi `POST /import/excel-tam` ile `veri/test.db`), frontend `npm run dev`; akış: Dashboard açılır → 67 satır → bir ürüne tıkla → iki toplam görünür → fire hücresini değiştir → toplam değişir → "Hesabı kaydet" → teklif turu ekle → Teklifler sayfasında görünür.
- Okubeni: Node/npm kurulumu, `npm i`, `npm run api:tipler`, `npm run dev`, `npm test`, `npm run e2e`, backend başlatma komutu, `VITE_API_URL` (proxy yerine doğrudan adres isteniyorsa).
- Tasarım temizliği: tüm sayfalarda 768px düzen kontrolü (Playwright viewport), koyu tema kontrast kontrolü, klavye odak halkaları.

## Self-review
- Kapsam: tasarım §5'teki 7 sayfa → T4-T7 (Karşılaştırma Faz 5, planda yok); Faz 2b ekranı (tek tablo, iki tutar, satır bazlı kaynak seçimi) → T5; geçmiş + geri al → T3/T6; import → T7; firesiz dashboard sütunu → T4.
- Tip tutarlılığı: alan adları üretilen `sema.d.ts`'ten gelir; planda geçen adlar (`tutar_firesiz`, `miktar_kaynagi`, `fiyat_kaynagi`, `toplamlar_firesiz`, `fiyatlar_firesiz`, `gecici_kod`, `kart_yok`, `pay_kontrol`) Faz 2/2b sözleşmesindeki adlardır; farklıysa derleme hatası görevin içinde düzeltilir ve raporlanır.
- Risk: shadcn/Tailwind kurulumu çevrimdışı ortamda paket indiremezse T1 duraklar (NEEDS_CONTEXT).
