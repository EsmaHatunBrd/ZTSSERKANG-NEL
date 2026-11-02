---
name: muhasebe-otomasyon-kurallari
description: Muhasebe otomasyonu projesinde orkestrator, arayuz ve backend ajanlarının ortak kullandığı kurallar - Türkçe terimler, Tekdüzen Hesap Planı, tutar/tarih formatı, KVKK hassasiyeti. Muhasebe ekranı, API veya hesaplama yazarken kullan.
---

# Muhasebe Otomasyonu - Ortak Kurallar

## Dil ve terimler
- Arayüz metinleri, hata mesajları ve raporlar **Türkçe** olur.
- Muhasebe terimleri Türk uygulamasına uygun kullanılır: mizan, yevmiye, cari hesap, mutabakat, tahakkuk, KDV, Ba-Bs, e-fatura, e-arşiv, e-defter.
- Hesap kodları **Tekdüzen Hesap Planı** yapısındadır (örn. 120 Alıcılar, 320 Satıcılar, 100 Kasa, 102 Bankalar, 191 İndirilecek KDV, 391 Hesaplanan KDV).

## Sayı, para ve tarih
- Tutar gösterimi: `1.234.567,89` (binlik nokta, ondalık virgül), yanında para birimi (TL, USD, EUR).
- Tarih gösterimi: `GG.AA.YYYY`. Depolama ve API: ISO 8601 (`YYYY-MM-DD`).
- Para tutarları **asla float ile tutulmaz**: tam sayı kuruş veya Decimal kullanılır. Yuvarlama kuralı açıkça belirtilir.
- Borç = Alacak dengesi her kayıtta doğrulanır; dengesiz fiş kaydedilmez.

## Veri güvenliği (KVKK)
- Kişisel veri (ad, TC kimlik, IBAN, telefon) log'a yazılmaz, hata mesajında gösterilmez.
- Kurum/firma adları da korunan veri sayılır; örnek veri üretirken uydurma isimler kullan.
- Gerçek veri içeren dosyaları (Excel/CSV) işlemeden önce kullanıcıdan hangi sütunların gerektiğini sor.

## Çalışma ilkeleri
- Emin olunmayan muhasebe/vergi kuralı için **tahmin etme, sor** veya "doğrulanmalı" diye işaretle.
- Hesaplamalar izlenebilir olmalı: her rakamın hangi kayıttan geldiği görülebilsin.
- Silme ve geri alınamayan işlemlerde kullanıcıdan onay iste.
- Hazır kaynaklar: `muhasebe-operasyonlari` ve `prompt-iyilestirici` skill'lerine başvur, içeriklerini kopyalama.
