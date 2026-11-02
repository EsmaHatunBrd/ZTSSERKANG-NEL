# Faz 2b: Fireli/Firesiz Çift Hesap ve Elle Girilen Değerler - Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kullanıcı kararlarını (21.10.2026) uygulamak: (1) Excel'de elle yazılmış brüt miktar ve birim fiyat değerleri sistemde de elle değer olarak kalır; fire oranı yazılı satırda fire uygulanır; yeni üründe satır bazında "fire oranı / elle brüt" ve "liste fiyatı / elle fiyat" seçilebilir. (2) Sağ blok (Z-AO) = firesiz hesap; tek tabloda her satır ve toplam için hem firesiz hem fireli tutar gösterilir.

**Architecture:** Motorun reçete satırına iki isteğe bağlı alan eklenir (`brut_miktar_elle`, `birim_fiyat_elle`). Motor her satır için `tutar` (fireli/brüt) ve `tutar_firesiz` (net) üretir; `urun_maliyeti` aynı girdiyle tüm fireler 0 alınarak ikinci bir sonuç (`firesiz`) hesaplar ve ana sonuca iliştirir. Excel okuyucu elle yazılmış K/M hücrelerini bu alanlara aktarır; parite istisnaları küçülür. Veri modeli, import, servis ve API aynı alanları taşır; ekran tek tabloda iki tutar sütunu gösterir.

**Tech Stack:** mevcut (Python 3.12, Decimal, openpyxl, SQLAlchemy, FastAPI, pytest).

**Spec:** `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` (§2 formüller, §3 Excel sorunları, §8 kapanan sorular), `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md` (§2 veri modeli, §4 API, §5 ekranlar).

## Global Constraints

- Kullanıcı kararı: firesiz hesap **aynı üretim girdileriyle**, yalnızca tüm fireler (reçete satırları ve mal kabul) 0 alınarak üretilir.
- Geriye uyumluluk: yeni dataclass alanları varsayılanlı ve **son** alanlar; mevcut imzalar değişmez; mevcut testler (113+) yeşil kalır; parite toleransı ve beklenen değerler değişmez.
- Elle fiyat (`birim_fiyat_elle`) Excel'deki M hücresinin karşılığıdır: enflasyon/kur kuralı (Z/S, para birimi) elle fiyata da aynen uygulanır (Excel `P = f(M, N, O, K)` formülü M'nin kaynağına bakmaz).
- Elle brüt miktar (`brut_miktar_elle`) doluysa fire hesabı yapılmaz; `brut_miktar = brut_miktar_elle`. Firesiz tutar her zaman `miktar × fiyat_katsayısı` (net miktar) ile hesaplanır.
- Para `Decimal`; tanımlayıcılar Türkçe karakter kullanmadan; git yok; kurumsal veri raporlarda yalnızca sayfa/hücre/sayı.
- Append-only tablolar değişmez; `recete_satiri` yeni sütunları nullable `ParaTipi`.

---

## Dosya Yapısı

Değişen: `fiyat_motoru/modeller.py`, `malzeme.py`, `hesapla.py`, `excel_okuyucu.py`, `parite.py`; `backend/depo/modeller.py`, `backend/servisler/{recete_servisi,hesap_servisi,import_servisi}.py`, `backend/api/{semalar,urunler,disa_aktar}.py`; testler. Yeni: `tests/test_firesiz.py`, `tests/test_excel_firesiz_paritesi.py`, `tests/backend/test_firesiz_api.py`.

---

### Task 1: Motor — elle değerler ve firesiz tutar (`modeller.py`, `malzeme.py`, `hesapla.py`)

**Files:** Modify `fiyat_motoru/modeller.py`, `fiyat_motoru/malzeme.py`, `fiyat_motoru/hesapla.py`; Create `tests/test_firesiz.py`

**Interfaces:**
- `ReceteSatiri` sonuna: `brut_miktar_elle: Decimal | None = None`, `birim_fiyat_elle: Decimal | None = None`.
- `MaliyetSatiri` sonuna: `tutar_firesiz: Decimal = SIFIR`, `miktar_kaynagi: str = "fire"` (`"fire"` | `"elle"` | `"-"` gider satırları), `fiyat_kaynagi: str = "liste"` (`"liste"` | `"elle"` | `"-"`).
- `MaliyetSonucu` sonuna: `firesiz: "MaliyetSonucu | None" = None`.
- `malzeme.malzeme_tutari`: `brut = satir.brut_miktar_elle if satir.brut_miktar_elle is not None else brut_miktar(satir.miktar, satir.fire_orani)`; `fiyat = satir.birim_fiyat_elle if ... else malzeme.fiyat`; katsayı (kur / enflasyon / Z) aynen; `tutar = katsayi × brut`, `tutar_firesiz = katsayi × satir.miktar`. Uyarı mantığı değişmez (elle fiyat varsa "fiyat listesinde yok" uyarısı verilmez).
- `hesapla.urun_maliyeti(girdi, malzemeler, oranlar, p, firesiz_hesapla: bool = True)`: `firesiz_hesapla` True ise `girdi_firesiz = replace(girdi, recete=tuple(replace(r, fire_orani=SIFIR, brut_miktar_elle=None) for r in girdi.recete), uretim=replace(girdi.uretim, mal_kabul_fire=SIFIR))` ile `urun_maliyeti(..., firesiz_hesapla=False)` çağrılır ve `sonuc.firesiz`'e konur. Gider satırlarının `tutar_firesiz = tutar` (fire yok), finans satırı da.

- [ ] **Step 1: Test** (`tests/test_firesiz.py`; `tests/test_hesapla.py`'deki `GIRDI`, `MALZ`, `O`, `P` yeniden kullanılır)

```python
from dataclasses import replace
from decimal import Decimal as D_
from fiyat_motoru.hesapla import urun_maliyeti
from fiyat_motoru.malzeme import malzeme_tutari
from fiyat_motoru.modeller import ReceteSatiri
from fiyat_motoru.para import yakin, SIFIR
from tests.test_hesapla import GIRDI, MALZ, O, P
from tests.test_malzeme import P as PM, malz, satir


def test_satir_fireli_ve_firesiz_tutar():
    s, _ = malzeme_tutari(satir(1, "0.02"), malz("5.9", "TL", "S"), PM)       # 001!P13
    assert yakin(s.tutar, D_("7.525510204081633")) and yakin(s.tutar_firesiz, D_("7.375"))
    assert s.miktar_kaynagi == "fire" and s.fiyat_kaynagi == "liste"


def test_elle_brut_fire_hesaplanmaz():
    r = ReceteSatiri("k", "a", D_(1), D_("0.02"), "AD", brut_miktar_elle=D_("1.1"))
    s, _ = malzeme_tutari(r, malz("5.9", "TL", "S"), PM)
    assert yakin(s.tutar, D_("5.9") * D_("1.25") * D_("1.1")) and s.brut_miktar == D_("1.1") and s.miktar_kaynagi == "elle"
    assert yakin(s.tutar_firesiz, D_("7.375"))


def test_elle_fiyat_listeyi_ezer_katsayi_ayni():
    r = ReceteSatiri("k", "a", D_(1), SIFIR, "AD", birim_fiyat_elle=D_("6"))
    s, u = malzeme_tutari(r, malz("5.9", "TL", "S"), PM)
    assert yakin(s.tutar, D_("7.5")) and s.fiyat_kaynagi == "elle" and u is None
    s2, u2 = malzeme_tutari(r, None, PM)             # kartı olmayan malzeme + elle fiyat: Z/S bilinmiyor -> katsayı yok, uyarı yok
    assert yakin(s2.tutar, D_("6")) and u2 is None


def test_urun_firesiz_zinciri():
    r = urun_maliyeti(GIRDI, MALZ, O, P)
    f = r.firesiz
    assert f is not None and f.firesiz is None
    assert yakin(f.malzeme_toplami, D_("22.67374835")) and f.malzeme_toplami < r.malzeme_toplami
    assert f.direkt_iscilik_toplami == r.direkt_iscilik_toplami          # mal kabul firesi zaten 0'dı
    assert yakin(f.finansman_dahil_maliyet_tl, (f.toplam_birim_maliyet + f.diger_giderler_toplami) * D_("1.2"))
    assert all(s.tutar_firesiz == s.tutar for s in r.satirlar if s.grup != "malzeme")
    assert sum(s.tutar_firesiz for s in r.satirlar if s.grup == "malzeme") == f.malzeme_toplami


def test_mal_kabul_firesi_firesizde_sifir():
    g = replace(GIRDI, uretim=replace(GIRDI.uretim, mal_kabul_fire=D_("0.1")))
    r = urun_maliyeti(g, MALZ, O, P)
    assert r.firesiz.satir("mal_kabul_iscilik").brut_miktar == GIRDI.uretim.mal_kabul_miktar_kg
    assert r.satir("mal_kabul_iscilik").brut_miktar > r.firesiz.satir("mal_kabul_iscilik").brut_miktar
```

- [ ] **Step 2: Çalıştır, başarısız** (`TypeError: unexpected keyword 'brut_miktar_elle'`)
- [ ] **Step 3: Uygula** (Interfaces'e göre; `malzeme_tutari` içinde kartı olmayan malzeme + elle fiyat → katsayı 1, uyarı yok; elle fiyat varken `malzeme is None` uyarısı verilmez)
- [ ] **Step 4: Çalıştır, geçer**; tüm süit yeşil (`decimal_str` iç içe dataclass'ı zaten işler; Faz 2 snapshot'ı `firesiz`'i otomatik taşır).

---

### Task 2: Excel okuyucu — elle K/M aktarımı ve parite daralması (`excel_okuyucu.py`, `parite.py`)

**Files:** Modify `fiyat_motoru/excel_okuyucu.py`, `fiyat_motoru/parite.py`, `tests/test_excel_paritesi.py`, `tests/test_excel_okuyucu.py`; Create `tests/test_excel_firesiz_paritesi.py`

**Interfaces:**
- `urun_oku`: her reçete satırı için `ws_f` (formül) hücrelerine bakar: K hücresi formül değilse **veya** formülü `=I{r}/(1-J{r})` kalıbında değilse (boşluk/`+` farkları tolere) → `brut_miktar_elle = D(ws_v K)`; M hücresi formül değilse → `birim_fiyat_elle = D(ws_v M)`. (Kural: `scripts/excel_elle_hucre_tara.py` ile aynı sınıflandırma; o scriptteki yardımcıyı `excel_okuyucu`'ya taşı ve script oradan içe aksın.)
- `urun_oku` `bek` sözlüğüne sağ blok: `AL100`, `AL114`, `AL116`, `AL120`, `AL122`, `AL124`, `AL130`, `AL131`, `AL137` (satır konumları sol bloğun etiket satırlarıyla aynı; kolon AL).
- `parite.karsilastir`: mevcut karşılaştırma aynen; ek olarak `firesiz_farklari(...)`: `r.firesiz` alanlarını `AL*` ile karşılaştırır (`AL100`↔`firesiz.malzeme_toplami`, `AL130`↔`firesiz.finansman_dahil_maliyet_tl`, `AL131`↔USD, `AL137`↔satış TL). Sağ blok farklı üretim girdileri kullanabildiği (`AA138` vb.) için bu karşılaştırma **ayrı** bir sonuç listesidir; rapor dosyasına "Firesiz (sağ blok) karşılaştırması" bölümü eklenir.

- [ ] **Step 1: Testler**
  - `tests/test_excel_okuyucu.py`: sayfa `009` satır `K8` elle → `girdi.recete[?].brut_miktar_elle` dolu; sayfa `011` `K7` `=+I7/0.98` → elle (formül kalıp dışı); sayfa `001` `K8` → `None`; sayfa `012` `M10` elle → `birim_fiyat_elle` dolu.
  - `tests/test_excel_paritesi.py`: parite testi aynen çalışır; `BILINEN_ISTISNALAR` yeniden üretilir (Task 11 Step 3 yöntemiyle): artık eşleşen sayfaların istisnaları **silinir** (ölü istisna testi zorlar). Beklenti: kural paritesi birebir sayfa sayısı 32'den belirgin artar (hedef ≥ 55; gerçek sayıyı raporla), kalan istisnalar yalnızca K/M dışı elle hücreler (`I104` vb., `053` mutlak referanslar).
  - `tests/test_excel_firesiz_paritesi.py`: `FIRESIZ_ISTISNALARI` sözlüğüyle (gerekçe: hücre adresi; sağ blokta farklı `AA138`/`AG` sabitleri vb.) `firesiz_farklari` boş olmalı; ölü istisna testi.
- [ ] **Step 2-4:** uygula, koş, sayıları raporla (önce/sonra: birebir sayfa, istisna sayısı).

---

### Task 3: Veri modeli, servisler, import

**Files:** Modify `backend/depo/modeller.py` (`ReceteSatiri.brut_miktar_elle`, `birim_fiyat_elle` nullable `ParaTipi`), `backend/servisler/recete_servisi.py` (`yeni_versiyon` satır dict'inde `brut_miktar_elle`, `birim_fiyat_elle`; `fire_uygulanmis` bunları `MotorSatir`'a geçirir; `kaynaklar` için `"elle"` etiketi brüt elle ise), `backend/servisler/import_servisi.py` (okuyucudan geçir), `backend/servisler/hesap_servisi.py` (override `fire` elle brüt olan satıra uygulanırsa `DogrulamaHatasi("satır elle brüt miktarlı, önce elle değeri kaldırın")`; snapshot otomatik); testler: `test_recete_servisi.py` (elle alanlar versiyonla taşınır, kaynak "elle"), `test_import_servisi.py` (elle alan taşıyan satır sayısı > 0; `009` ürününde `K8` satırı), `test_uctan_uca_excel.py` (servis `firesiz.malzeme_toplami` == motor firesiz; yeniden üretilen `BILINEN_ISTISNALAR` ile 67 sayfa 0 fark).

- [ ] Adımlar: test → kırmızı → uygula → yeşil; tüm süit.

---

### Task 4: API ve dışa aktarma

**Files:** Modify `backend/api/semalar.py` (`ReceteSatirGiris` + `brut_miktar_elle: Decimal | None = Field(None, ge=0)`, `birim_fiyat_elle: Decimal | None = Field(None, ge=0)`), `backend/api/urunler.py` (`_hesap_yaniti`: satırda `tutar_firesiz`, `miktar_kaynagi`, `fiyat_kaynagi`, `brut_miktar_elle`, `birim_fiyat_elle`; `toplamlar_firesiz` ve `fiyatlar_firesiz` blokları `firesiz` sonucundan; dashboard satırına `maliyet_tl_firesiz`, `maliyet_usd_firesiz`; `GET recete` yeni alanları döner), `backend/api/disa_aktar.py` (iki sütun: Maliyet TL (fireli), Maliyet TL (firesiz)); Create `tests/backend/test_firesiz_api.py` (hesapla yanıtında iki toplam; elle brüt satır gönderip `miktar_kaynagi == "elle"`; dashboard yeni sütun; şema sınırları).

---

### Task 5: Dokümanlar
- `docs/10-21-2026-faz2-faz4-backend-frontend-tasarim.md`: §2 reçete satırı alanları; §4 `/hesapla` yanıt örneğine `tutar_firesiz`, `miktar_kaynagi`, `fiyat_kaynagi`, `toplamlar_firesiz`, `fiyatlar_firesiz`; §5 Ürün Maliyeti ekranı: tek tablo, "Tutar (firesiz) | Tutar (fireli)" sütunları, satır başında "Miktar: fire oranı / elle brüt" ve "Fiyat: liste / elle" seçimi, altta iki toplam ve iki satış fiyatı.
- `docs/10-21-2026-fiyat-calismasi-analiz-ve-mimari.md` §6: yeni parite sayıları; §3 madde 6 güncelle ("elle K/M değerleri artık veri olarak taşınır").

## Self-review
- Kapsam: kullanıcı kararı 1 (elle değerler + satır bazlı seçim) → T1, T2, T3, T4; karar 2 (firesiz/fireli tek tablo) → T1 (`firesiz`), T4, T5. Sağ blok paritesi → T2 ayrı liste (girdi farkları nedeniyle zorunlu birebir değil).
- Tip tutarlılığı: `brut_miktar_elle`/`birim_fiyat_elle` adları motor, ORM, servis dict, API şeması ve okuyucuda aynı; `miktar_kaynagi` değerleri `"fire" | "elle" | "-"`.
- Risk: T2 istisna listesinin yeniden üretimi zaman alır; ölü-istisna testi tutarlılığı zorlar.
