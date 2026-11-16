# Fiyat Çalışması — Kurulum ve İşletim Rehberi (BT sorumlusu için)

Uygulama tek bir Windows bilgisayarda çalışır ve ağdaki kullanıcılara tarayıcıdan **tek adresle** hizmet verir:
`http://<sunucu-adı>:8000`. Aynı süreç hem ekranları hem API'yi sunar; ayrı web sunucusu ya da veritabanı sunucusu gerekmez
(veritabanı tek dosyadır: `veri\fiyat.db`).

Bütün betikler `kurulum\` klasöründedir ve PowerShell 5.1 ile çalışır. Komutlar proje klasöründe, şu kalıpla çalıştırılır:

```
powershell -ExecutionPolicy Bypass -File kurulum\<betik>.ps1
```

| Betik | Ne yapar |
|---|---|
| `11-12-2026-kur.ps1` | İlk kurulum: Python ortamı, bağımlılıklar, arayüz derlemesi, klasörler, ayar dosyası. Tekrar çalıştırılabilir. |
| `11-12-2026-baslat.ps1` | Sunucuyu başlatır. Zaten çalışıyorsa ya da port doluysa uyarır, ikinci kopya açmaz. |
| `11-12-2026-durdur.ps1` | Sunucuyu durdurur (yalnız bu uygulamanın sürecini). |
| `11-12-2026-servis-kaydet.ps1` | Açılışta otomatik başlatma (Zamanlanmış Görev), isteğe bağlı günlük yedek görevi ve güvenlik duvarı kuralı; `-Kaldir` ile geri alır. Yönetici ister. |
| `11-12-2026-yedekle.ps1` | Veritabanını tarihli adla yedekler (yerel + isteğe bağlı ağ paylaşımı), 14 günden eski kendi yedeklerini siler. |
| `11-12-2026-geri-yukle.ps1` | Seçilen yedeği geri yükler; önce mevcut veritabanını yedekler ve onay ister. |
| `11-12-2026-guncelle.ps1` | Yeni sürüm kopyalandıktan sonra: yedek → durdur → bağımlılık + derleme → başlat. |

## 1. Gereksinimler

- Windows 10/11 ya da Windows Server 2016+ (PowerShell 5.1 hazır gelir).
- **Python 3.11 veya üstü** (64 bit; geliştirme 3.12 ile yapıldı). Kurulumda "py launcher" ya da "Add to PATH" seçili olsun.
- **Node.js 22 LTS (22.12+)** ya da 20.19+ — yalnız arayüzü derlemek için (kurulum ve güncelleme sırasında) gerekir.
- Kurulum ve güncelleme sırasında internet (PyPI ve npm paket depoları). Çalışırken internet gerekmez.
- Disk: uygulama ~1 GB (bağımlılıklarla); veri küçük (veritabanı birkaç MB, yedekler için birkaç yüz MB ayırın).
- Sunucuyu çalıştıracak bir Windows hesabı (proje klasörüne yazma yetkili). Otomatik başlatma için bu hesabın şifresi gerekir.
- Onay çıktısı PDF'i (16.11.2026) `fpdf2` ile sunucuda üretilir (`pyproject.toml` bağımlılığı; `kur.ps1` kurar, tarayıcı gerekmez). Türkçe
  karakterler için Windows'un Arial yazı tipini (`C:\Windows\Fonts\arial.ttf`, `arialbd.ttf`) kullanır; başka bir TrueType yazı tipi
  istenirse `PDF_YAZI_TIPI` / `PDF_YAZI_TIPI_KALIN` ortam değişkenleriyle tam yolu verilir.

## 2. Kurulum

1. Proje klasörünü sunucuya kopyalayın (örn. `C:\FiyatCalismasi`). Şunları **kopyalamayın**: `.venv`, `frontend\node_modules`,
   `frontend\dist`, `.git` (sunucuda yeniden üretilir; `.venv` başka bilgisayara taşınınca çalışmaz).
   Klasör yolunda `& | < > ^ %` karakterleri olmasın.
2. Mevcut veriyle devam edilecekse `fiyat.db` dosyasını `veri\fiyat.db` olarak koyun (kopyalarken eski bilgisayardaki uygulama kapalı olsun;
   yanında `fiyat.db-wal` / `fiyat.db-shm` varsa onları da birlikte kopyalayın). Sıfırdan başlanacaksa bir şey koymayın; ilk açılışta boş veritabanı oluşur.
3. Kurulumu çalıştırın:
   ```
   powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-kur.ps1
   ```
   Birkaç dakika sürer. Sonunda "Kurulum tamam" yazmalı. Hata verirse mesajı okuyup düzeltin ve aynı komutu yeniden çalıştırın (zararsızdır).
4. `kurulum\ayarlar.env` dosyasını açıp gözden geçirin (aşağıdaki tablo). Varsayılanlar çoğu kurulum için yeterlidir.
5. Sunucuyu başlatın:
   ```
   powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1
   ```
   "API yanıt veriyor" ve "Arayüz yanıt veriyor" satırlarını ve adresi görmelisiniz.
6. Başka bilgisayarlardan erişim için Windows Güvenlik Duvarı'nda 8000 portuna izin verin
   (`servis-kaydet.ps1 -GuvenlikDuvari` bunu yapar; bkz. bölüm 5).

### Ayarlar (`kurulum\ayarlar.env`)

| Ayar | Varsayılan | Açıklama |
|---|---|---|
| `HOST` | `0.0.0.0` | `0.0.0.0`: ağdan erişilir. `127.0.0.1`: yalnız sunucunun kendisinden. |
| `PORT` | `8000` | Adresin port numarası. |
| `VERITABANI_URL` | boş → `veri\fiyat.db` | Veritabanı başka diskte tutulacaksa `sqlite:///D:/FiyatVeri/fiyat.db`. |
| `GIRIS_ZORUNLU` | `1` | Sunucuda **1 kalmalı**. 0 olursa uygulama şifresiz açılır. |
| `ONBELLEK_ISITMA` | `1` | Kayıt sonrası ana sayfa hesaplarını arka planda hazırlar. |
| `ARAYUZ_DIZINI` | boş → `frontend\dist` | Derlenmiş arayüz klasörü. Değiştirmeye gerek yok. |
| `CORS_ORIGINS` | boş | Tek adres kurulumunda gerekmez. |
| `EXCEL_YOLU` | boş | Excel içe aktarmanın varsayılan dosyası. |
| `YEDEK_AG_KLASORU` | boş | Doluysa `yedekle.ps1` yedeği buraya da kopyalar (örn. `\\dosyasunucu\yedek\fiyat`). |
| `YEDEK_TUT_GUN` | `14` | `yedekle.ps1` yedeklerinin saklanma süresi (gün). |
| `GUNLUK_TUT_GUN` | `30` | Sunucu günlük dosyalarının saklanma süresi (gün). |

Ayar değişikliği sunucu yeniden başlatılınca geçerli olur (`durdur` → `baslat`). Bu dosyada şifre tutulmaz.

## 3. Adres

- Kullanıcılar: `http://<sunucu-adı>:8000` (örn. `http://FIYATSRV:8000`). Sunucunun IP adresi de kullanılabilir.
- Bağlantı şifresizdir (HTTP). Uygulama **yalnız şirket iç ağında** kullanılmalı; internete açılmamalıdır.

## 4. İlk kullanıcı (Genel Direktör)

Yalnız ilk kurulumda, sunucu **bir kez başlatıldıktan sonra** (veritabanı dosyası o zaman oluşur):

```
.venv\Scripts\python.exe scripts\11-04-2026-ilk-genel-direktor.py
```

- Ekrana kullanıcı adı (`direktor`) ve **geçici şifre** yazılır. Şifre başka hiçbir yerde saklanmaz; not edip ilgili kişiye güvenli yoldan iletin.
- İlk girişte uygulama yeni şifre belirletir. Diğer kullanıcıları Genel Direktör uygulamanın içinden açar.
- Veritabanı başka yerdeyse `--db "D:\FiyatVeri\fiyat.db"` ekleyin. Farklı kullanıcı adı için `--kullanici`.
- Veritabanında zaten etkin bir Genel Direktör varsa betik hiçbir şey yapmaz (eski veritabanı taşındıysa mevcut hesaplar geçerlidir).

## 5. Açılışta otomatik başlatma

Yönetici PowerShell penceresinde:

```
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-servis-kaydet.ps1 -Kullanici SIRKET\fiyatsvc -GunlukYedek -GuvenlikDuvari
```

- Hesabın şifresi sorulur (dosyaya yazılmaz). Hesapta "Toplu iş olarak oturum açma" (Log on as a batch job) hakkı olmalıdır.
- `FiyatCalismasi-Sunucu` görevi: bilgisayar açılınca sunucuyu başlatır; süreç düşerse 1 dakika arayla 3 kez yeniden dener.
- `-GunlukYedek`: her gün 02:00'de `yedekle.ps1` çalışır (saat için `-YedekSaati 23:30`). **Önerilir** — bkz. bölüm 6.
- `-GuvenlikDuvari`: `PORT` için gelen bağlantı kuralı ekler (Etki alanı + Özel ağ).
- Sunucu elle açıksa önce `durdur.ps1` ile kapatın, sonra `Start-ScheduledTask -TaskName FiyatCalismasi-Sunucu`.
- Geri almak için: `kurulum\11-12-2026-servis-kaydet.ps1 -Kaldir`.
- Hesabın şifresi değişirse görevi aynı komutla yeniden kaydedin.

## 6. Yedek ve geri yükleme

Yedekler veritabanının yanındaki `yedek` klasöründedir (varsayılan `veri\yedek\`). Üç tür dosya bulunur:

| Dosya adı | Kim alır | Saklama |
|---|---|---|
| `AA-GG-YYYY-otomatik-fiyat.db` | Uygulama, sunucu sürecinin **ilk isteğinde**, günde en çok bir kez | Son 14 dosya |
| `AA-GG-YYYY-SSDDSS-yedek-fiyat.db` | `yedekle.ps1` | `YEDEK_TUT_GUN` gün (en yenisi hep kalır) |
| `…-guncelleme-oncesi-…`, `…-geri-yukleme-oncesi-…`, `…-silme-oncesi-…` | Güncelleme / geri yükleme / senaryo silme öncesi | İlk ikisi silinmez (ara sıra elle temizleyin); silme öncesi 14 gün |

Önemli: uygulamanın kendi otomatik yedeği yalnız sunucu **yeniden başladığında** alınır. Haftalarca açık kalan sunucuda
günlük yedek için bölüm 5'teki `-GunlukYedek` görevini kurun. Disk arızasına karşı `YEDEK_AG_KLASORU` ile ağ paylaşımına da kopyalatın
(görev hesabının paylaşıma yazma yetkisi olmalı).

Elle yedek (sunucu çalışırken de alınabilir):

```
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-yedekle.ps1
```

Çıkış kodu 0: tamam. 3: yerel yedek alındı ama ağ kopyası başarısız. 1: yedek alınamadı.

Geri yükleme:

```
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-durdur.ps1
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-geri-yukle.ps1
powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1
```

- Betik yedekleri listeler, numara sorar, ne yapacağını gösterir ve **EVET** yazılmasını ister.
- Önce mevcut veritabanını `…-geri-yukleme-oncesi-…` adıyla yedekler; yanlış yedek seçildiyse aynı betikle o dosya geri yüklenir.
- Seçilen yedekten sonra girilen veriler uygulamada görünmez olur; kullanıcılara haber verin.
- Belirli dosya için: `-Yedek 11-12-2026-020000-yedek-fiyat.db`. Ağ paylaşımındaki yedek için tam yol verin.
- Sunucu görevle çalışıyorsa `durdur`/`baslat` yerine `Stop-ScheduledTask` / `Start-ScheduledTask -TaskName FiyatCalismasi-Sunucu` kullanın.

Veritabanı dosyasını sunucu çalışırken Explorer'dan kopyalayarak yedeklemeyin (eksik kopya oluşabilir); `yedekle.ps1` kullanın.

## 7. Güncelleme

1. Yeni sürümün dosyalarını proje klasörünün üzerine kopyalayın. `veri\` klasörüne ve `kurulum\ayarlar.env` dosyasına dokunmayın.
2. Çalıştırın (görev kayıtlıysa yönetici olarak):
   ```
   powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-guncelle.ps1
   ```
   Sırayla: yedek alır → sunucuyu durdurur → bağımlılıkları kurar ve arayüzü derler → sunucuyu başlatır. Birkaç dakika kesinti olur;
   kullanıcılar çalışmıyorken yapın. Veritabanı yapısı gerekiyorsa ilk açılışta kendiliğinden güncellenir.
3. Kullanıcılar tarayıcıda sayfayı yenilesin (Ctrl+F5).

Sorun çıkarsa: eski sürüm dosyalarını geri kopyalayın, `guncelle.ps1`'i yeniden çalıştırın; veri için gerekirse
`…-guncelleme-oncesi-…` yedeğini geri yükleyin.

## 8. Günlük dosyaları

- Yer: `veri\gunluk\AA-GG-YYYY-sunucu-<port>.log` (sunucunun başlatıldığı günün adıyla; aynı gün yeniden başlatılırsa sonuna eklenir).
- İçerik: açılış/kapanış satırları, her isteğin adresi (sorgu parametreleriyle) ve sonuç kodu, hata izleri. Şifreler yazılmaz; yine de günlükleri `veri\` gibi koruyun, dışarıya gönderirken gözden geçirin.
- `GUNLUK_TUT_GUN` günden eski günlükler her başlatmada silinir.
- `veri\gunluk\sunucu-<port>.pid`: çalışan sürecin numarası (betikler kullanır; elle değiştirmeyin).
- Kimin neyi değiştirdiği bu dosyalarda değil, uygulamanın içindeki değişiklik günlüğündedir.

## 9. Sorun giderme

| Belirti | Neden / çözüm |
|---|---|
| `baslat`: "Port 8000 başka bir süreç tarafından kullanılıyor" | Mesajdaki süreç portu tutuyor. O programı kapatın ya da `ayarlar.env` içinde `PORT` değiştirin (adres ve güvenlik duvarı kuralı da değişir). |
| `baslat`: "Sunucu zaten çalışıyor" | Normal. Yeniden başlatmak için önce `durdur.ps1`. |
| `baslat`: "Sunucu açılamadı" | Ekrana günlüğün son satırları yazılır; tamamı `veri\gunluk\` altında. En sık neden: bağımlılık eksik → `kur.ps1`'i yeniden çalıştırın. |
| Sunucuda açılıyor, başka bilgisayardan açılmıyor | `HOST=0.0.0.0` mı? Güvenlik duvarında port açık mı (`-GuvenlikDuvari`)? Sunucu adı çözülüyor mu (IP ile deneyin)? |
| Sayfa açılıyor ama boş / "uç yok" | Arayüz derlemesi eksik: `kur.ps1` çalıştırın, `frontend\dist\index.html` oluşmalı; sonra sunucuyu yeniden başlatın. |
| Giriş ekranı kimseyi kabul etmiyor (ilk kurulum) | İlk Genel Direktör açılmamış: bölüm 4. Art arda 5 hatalı denemede hesap 15 dakika kilitlenir. |
| "betik çalıştırma devre dışı" (execution policy) | Komutu `powershell -ExecutionPolicy Bypass -File …` kalıbıyla çalıştırın. |
| `kur`: pip / npm ci hata veriyor | İnternet ya da vekil sunucu (proxy) erişimi. Kurumsal vekil varsa pip ve npm için vekil ayarı yapın, sonra `kur.ps1`'i yineleyin. |
| `kur`: "Node … uygun değil" / "Python … en az 3.11" | Bölüm 1'deki sürümleri kurun. Eski `.venv` yanlış Python ile oluştuysa klasörü silip `kur.ps1`'i yeniden çalıştırın. |
| Python açılırken "DLL load failed" ya da "Uygulama Denetimi ilkesi bu dosyayı engelledi" | Bilgisayarda Uygulama Denetimi (WDAC/AppLocker) `.venv` içindeki derlenmiş kitaplıkları (`.pyd`/`.dll`; SQLAlchemy, pydantic) engelliyor olabilir. Proje klasörü için ilke istisnası tanımlanmalıdır. (Bu projede henüz karşılaşılmadı; görülürse günlükteki dosya adını BT güvenliğe iletin.) |
| Görev "Çalışıyor" ama adres açılmıyor | `veri\gunluk\` son günlüğe bakın. Görev hesabının proje klasörüne yazma yetkisi ve "Toplu iş olarak oturum açma" hakkı var mı? |
| `durdur`: "doğrulanamayan bir süreçte" | Sunucu başka bir hesapla (görevle) çalışıyor: yönetici PowerShell'de çalıştırın ya da `Stop-ScheduledTask` kullanın. |
| "database is locked" hataları | Aynı veritabanını açan ikinci bir sunucu ya da yedek/antivirüs taraması olabilir. Tek sunucu çalıştığından emin olun; `veri\` klasörünü antivirüsün anlık taramasından hariç tutmayı değerlendirin. |

## 10. Bilinmesi gerekenler

- Uygulama **tek süreç** olarak çalışacak biçimde yazılmıştır: aynı veritabanı için ikinci bir sunucu başlatmayın.
- `durdur.ps1` süreci anında kapatır. Veritabanı buna dayanıklıdır, ancak o saniyede süren bir kayıt tamamlanmamış olur; mümkünse mesai dışında durdurun.
- Kullanıcı oturumları veritabanında tutulur; sunucu yeniden başlayınca kullanıcıların yeniden giriş yapması gerekmez.
- `veri\` klasörü şirket verisidir (maliyet, fiyat, kullanıcı hesapları): klasör yetkilerini yalnız sunucu hesabı ve BT ile sınırlayın;
  ağ paylaşımındaki yedekler için de aynı kısıt geçerlidir.
