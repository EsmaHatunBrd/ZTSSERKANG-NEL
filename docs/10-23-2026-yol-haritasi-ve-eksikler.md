# Yol Haritası ve Eksikler — 23.10.2026 akşamı itibarıyla

Amaç: neyin bittiğini, neyin eksik olduğunu ve sıradakini tek sayfada görmek. Seçim kullanıcının; önerilen sıra en altta.

## 0. Durum özeti
- Serkan Bey'in ilk 17 maddesinden 13'ü tam, 2'si veri bekliyor (geçen yıl satışı, enflasyon kıyası), 1'i dosya bekliyor (gerçekleşen), 1'i kapsam dışı (SMM).
- Fazlar 1-5c kapandı; Excel ile birebir parite korunuyor (ilk bütçe fiyatlarıyla); revize fiyatlar canlıda.
- Testler: backend ~440, frontend 380, uçtan uca 25. Yavaşlık çözüldü (dashboard 0,26 sn, kayıt sonrası ısıtma).

## A. Muhasebeden bekleyenler (biz bir şey yapamayız, cevap gerek)
| # | Konu | Neden önemli | Cevap gelince iş |
|---|---|---|---|
| A1 | **Gerçekleşen Excel dosyası** | Faz 6'nın girdisi | Faz 6 (plan hazır): ayrı senaryo, Bütçe vs Gerçekleşen sayfası, sapma ayrıştırması — 1 gün |
| A2 | **299 fiyatsız malzeme** ara mamul mü eksik mi | Maliyeti aşağı çekiyor (0 TL) | Ara mamul işareti + fiyatsız listesinin daralması — yarım gün |
| A3 | **Üretim Adetleri kodları (02.*) ↔ ürün kodları (03.*)** | "Hedef adetle maliyet" sütunu boş | Ada göre ya da dönüşüm tablosuyla eşleme — yarım gün |
| A4 | **Geçen yıl satış verisi** nereden (ERP/liste), ürün mü müşteri mi | Karşılaştırma ve enflasyon eşiği boş | Şablon zaten var; ERP ise dışa aktarım biçimine okuyucu — yarım gün |
| A5 | Gider çarpanlarının adı/anlamı; elektrik %100,1 / doğalgaz %99,5 | Çarpanlar artık arayüzde; adlandırılacak | Veri girişi, kod yok |
| A6 | Z işaretli 2 dövizli malzeme (043/044): kur uygulansın mı | 2 üründe maliyet | Tek kural değişikliği |
| A7 | Yurtdışı pazar yüzde/finansman kuralı; "ihracat destekleri" notu | İhracat teklifinde doğrulanmamış hesap | Kural + test — yarım gün |
| A8 | 056-067 sayfalarına ERP kodu | Geçici SAYFA-0xx kodları | Tek tıkla yeniden adlandırma var |
| A9 | 4,15066 yan hesabı; Teklif Kapak 0,95 oran sütunu | Belirsiz alanlar | Gerekirse alan eklenir |

## B. Üründe açık küçük işler (bizde, kısa)
| # | İş | Süre |
|---|---|---|
| B1 | Hesap hatalarına kararlı kod (`hedef_yok`, `parametre_eksik`); arayüz metin yerine kodla tanısın | 1 saat |
| B2 | Boş çalışmada "parametreleri geçen sezondan al" kısayolu (yeni çalışma diyaloğu Boş sekmesi) | 1 saat |
| B3 | Excel gider yeniden yüklemesi taban × çarpanı okusun (şu an toplam yazıp çarpanı temizliyor) | 2 saat |
| B4 | Yeni çalışma diyaloğunda sekme değişince Boş sekmesi sıfırlanmasın | 30 dk |
| B5 | Senaryo silme yedeklerinin budanması (14 gün) | 30 dk |
| B6 | Aile görünen adı baş harf büyük (kozmetik) | 15 dk |
| B7 | Hedef adet ad-eşlemesi (A3 cevabı "ada göre" ise) | yarım gün |
| B8 | Kilit, senaryodan bağımsız yazımları (ürün/malzeme kartı, satış geçmişi) kapsasın mı — karar | 2 saat |
| B9 | Erişilebilirlik taraması (axe) ve düzeltmeler | yarım gün |

## C. Yayına alma (kullanıcıya açmadan önce şart)
| # | İş | Süre | Not |
|---|---|---|---|
| C1 | **Kullanıcı girişi ve roller** (muhasebe: tam; satın alma: fiyat girişi; yönetim: salt okunur) | 1-2 gün | Şu an yalnız ad seçimi; dışa açmadan önce şart |
| C2 | **Kurulum paketi**: tek komutla sunucuda çalışma (Windows servisi ya da zamanlanmış görev), `npm run build` + uvicorn, ortam değişkenleri, yedek klasörü | yarım gün | Backend artık arayüzü de sunuyor: tek adres |
| C3 | **Yedek stratejisi**: günlük otomatik yedek var (14 gün); ağ paylaşımına kopya + geri yükleme talimatı | 2 saat | |
| C4 | **Kullanım rehberi** son hali (Veri Girişi, Yeni çalışma, revize fiyat eklendi) + 30 dk tanıtım | 2 saat | `docs/ozel/10-22-2026-kullanim-rehberi.md` güncellenecek |
| C5 | Çok kullanıcılı yoğunlukta SQLite yeterli mi — izleme; gerekirse PostgreSQL | sonra | Şimdilik yeterli |

## D. Önerilen yeni özellikler (Excel'de olmayan; kullanıcı seçer)
| # | Özellik | Değer | Süre |
|---|---|---|---|
| D1 | **Etki önizlemesi**: Kaydet'ten önce "bu değişiklik N ürünü şu kadar etkiler" | Hata önler | 1 gün |
| D2 | **Kur / zam simülasyonu**: "USD 55 olursa", "kavanoz %10 zamlanırsa" toplu ne olur | Bütçe toplantısı | 1 gün |
| D3 | **Malzeme etki haritası**: bir malzemenin fiyatı hangi ürünleri ne kadar etkiler (satın alma pazarlığı) | Pazarlık | yarım gün |
| D4 | **Müşteriye teklif çıktısı** (PDF/Excel, kayıtlı hesaba bağlı, Zeytursan şablonu) | Dış görünüm | 1 gün |
| D5 | **Asgari kâr kırmızı çizgisi**: teklif turu eşiğin altına inerse onay | Kontrol | yarım gün |
| D6 | **Onay akışı**: hazırlayan → onaylayan (C1'e bağlı) | Kurumsal | 1 gün |
| D7 | **Tutarlılık paneli**: fiyatsız malzeme, %100 olmayan pay, reçetesiz ürün, 0 adetli hedef — tek ekran, çözüm bağlantılı (Uyarılar sayfasının genişletilmiş hali) | Hızlı temizlik | yarım gün |
| D8 | **Sezon kapanış raporu**: bütçe → gerçekleşen → sapma, PDF (Faz 6 sonrası) | Yönetim | 1 gün |

## E. Faz 6 — Gerçekleşen kıyası (plan hazır: `docs/10-22-2026-faz6-gerceklesen-kiyas-plani.md`)
Dosya gelince: gerçekleşen Excel ayrı senaryo (tür "gerçekleşen", enflasyon 0), Bütçe vs Gerçekleşen sayfası (ürün ürün maliyet, satış, kâr; toplamlar), ürün ekranında yan yana kıyas, sapma ayrıştırması (fiyat / miktar-fire / gider / kur), Excel çıktısı. Süre: 1 gün.

## Önerilen sıra
1. **Bu hafta:** C4 rehber + C2 kurulum paketi (uygulamayı sunucuya koyup Serkan Bey'e göstermek için), B1-B6 küçükler (toplu yarım gün).
2. **Muhasebe görüşmesi:** A1-A4 (en kritik dördü); cevaplara göre A-işleri ve B7.
3. **Dosya gelince:** Faz 6.
4. **Dışa açmadan önce:** C1 kullanıcı girişi + roller, C3 yedek.
5. **Sonra, seçime göre:** D1 etki önizlemesi ve D2 simülasyon (en çok istenecekler), D7 tutarlılık paneli, D4 teklif çıktısı.

## Bugün yapılanların özeti (23.10)
Faz 5b: muhasebe cevapları (Z/S, revize fiyat, elle giriş + çarpanlar, Veri Girişi, Üretim bilgileri kartı). Faz 5c: Yeni çalışma (boş / kopya / Excel), senaryo düzenle-sil, yeni ürün, reçetesiz ürün akışı, senaryo üyeliği. Performans: ısıtıcı, paylaşılan hesap bağlamı, tek adres. Raporlar: `10-23-2026-faz5b-kapanis-raporu.md`, `10-23-2026-faz5c-kapanis-raporu.md`.
