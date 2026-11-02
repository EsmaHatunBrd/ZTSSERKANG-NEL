# Faz 6 — Gerçekleşen Excel ile Kıyas (Bütçe vs Gerçekleşen) Planı

Tarih: 22.10.2026 · Durum: **öneri, kullanıcı onayı bekliyor** · Önceki: Faz 5 (`docs/10-22-2026-faz5-karsilastirma-ve-performans-plani.md`)

## 1. Durum
- Fiyat çalışması Excel'i eksiksiz aktarıldı (kullanıcı teyidi 22.10): reçete, fire, gider dağıtımı, finansman, kurlar, satış fiyatı, teklifler, Teklif Kapak, Üretim Adetleri, Ambalaj Özeti.
- "Gerçekleşen" Excel'i aynı düzenin kopyası; farkı gerçekleşen miktar/fiyat/giderler ve **enflasyon 0** (sistemde zaten kural: `tur=gerceklesen` senaryoda enflasyon yazılmaz).
- Yükleme yolu hazır: Veri Aktar → Tüm çalışma kitabı → tür **Gerçekleşen**, aynı sezon. Yani ikinci Excel sisteme **ayrı bir senaryo** olarak girer; kıyas = iki senaryonun karşılaştırılması.

## 2. Kullanıcıya görünen
1. **Bütçe vs Gerçekleşen sayfası** (menü "Çalışma"): üstte iki senaryo seçici (A = fiyat çalışması, B = gerçekleşen; aynı sezon varsayılan). Tablo: ürün başına Reçete maliyeti · GÜG · Faaliyet · Finans · Toplam birim maliyet TL/USD · Satış fiyatı TL/USD — her biri **A | B | Fark | Fark %**; sapma eşiği (varsayılan ±%5) üstündekiler renkli; sıralama fark %'ye göre; "yalnız sapanlar" süzgeci; Excel'e aktar.
2. **Ürün kıyas ekranı** (satıra tıklayınca): yan yana reçete (satır eşlemesi malzeme koduna göre; miktar, fire, brüt, birim fiyat, tutar — A | B | fark, değişen hücre vurgulu; yalnız bir tarafta olan satırlar işaretli), gider kalemleri aynı düzende, üretim bilgileri ve parametreler (kur, faiz, stok, enflasyon) farkları, satış fiyatı/teklif farkı.
3. **Dashboard'a** "Gerçekleşen sapma %" sütunu (B seçiliyse) ve üst kart: "±%5'i aşan ürün sayısı".
4. **Sapma kaynağı özeti** (ürün başına): toplam farkın ne kadarı malzeme fiyatından, ne kadarı miktar/fireden, ne kadarı gider oranlarından, ne kadarı kurdan — basit ayrıştırma: her blok için A girdileriyle B'nin yalnız o bloğunu değiştirip hesap (motor zaten override destekliyor). Muhasebenin "neden saptı" sorusuna cevap.

## 3. Teknik
- Backend `karsilastirma_servisi.senaryo_farki(urun, a, b, tarih)` (tasarımda imzası ayrılmıştı) + `GET /karsilastirma/senaryo?a=&b=&esik=` (liste, önbellekli) + `GET /karsilastirma/senaryo/{kod}?a=&b=` (ürün detayı + sapma ayrıştırması) + `GET /disa-aktar/butce-gerceklesen.xlsx`.
- Reçete eşleme: malzeme kodu + sıra; aynı kod birden çoksa sırayla. Yalnız A'da / yalnız B'de satırlar ayrı listelenir.
- Sapma ayrıştırması: 4 ek hesap/ürün (fiyat, miktar+fire, gider oranları, kur) → önbellekli.
- Frontend: `Kiyas.tsx` (liste), `KiyasUrun.tsx` (detay), dashboard sütunu, Recharts "sapma dağılımı" çubuk grafiği.
- Testler: sentetik iki senaryo ile fark/yüzde/ayrıştırma toplamının toplam farka eşitliği (1e-9); gerçek gerçekleşen Excel geldiğinde parite (B senaryosunun Excel hücreleriyle birebir, mevcut parite altyapısı).

## 4. Gereken
- Gerçekleşen Excel dosyası (e-posta ekiyle gönderilebilir; adı "Gerçekleşen" ya da benzer; aynı düzen). Dosya gelmeden backend/frontend sentetik verilerle yazılır, dosya gelince parite + canlı yükleme.

## 5. Kararlar / riskler
1. Gerçekleşen senaryoda enflasyon 0, finansman parametreleri Excel'den (aynı mı farklı mı bilinmiyor; neyse o).
2. Eşik ±%5 parametre (`sapma_esigi`), kullanıcı değiştirebilir.
3. Sapma ayrıştırması sıralıdır (önce fiyat, sonra miktar, gider, kur); etkileşim terimi "diğer" olarak gösterilir.
