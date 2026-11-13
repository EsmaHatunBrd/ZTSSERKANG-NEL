<#
.SYNOPSIS
  Yeni sürüm dosyaları kopyalandıktan sonra çalıştırılır: yedek al -> durdur -> bağımlılık + derleme -> yeniden başlat.

.DESCRIPTION
  Önce: yeni sürümün dosyalarını proje klasörünün üzerine kopyalayın. veri\ klasörüne ve kurulum\ayarlar.env'e DOKUNMAYIN
  (yeni sürüm paketinde bunlar bulunmaz).
  Sıra:
    1. Veritabanı "…-guncelleme-oncesi-…" adıyla yedeklenir (yedek alınamazsa güncelleme durur).
    2. Sunucu durdurulur (Zamanlanmış Görev kayıtlıysa görev durdurulur).
    3. kur.ps1 çalışır: Python bağımlılıkları, npm ci, arayüz derlemesi.
    4. Sunucu yeniden başlatılır (görev kayıtlıysa görev, değilse baslat.ps1).
  Veritabanı şeması, sunucunun ilk isteğinde uygulama tarafından kendiliğinden güncellenir (eksik tablo/kolon eklenir).
  3. adım başarısız olursa sunucu yine de başlatılmaya çalışılır ve betik hata koduyla biter.

.PARAMETER AyarDosyasi
  Ayar dosyası yolu. Verilmezse kurulum\ayarlar.env.

.PARAMETER BagimlilikAtla
  pip / npm ci adımlarını atlar (yalnız kod değiştiyse, bağımlılıklar aynıysa).

.PARAMETER GorevAdi
  Zamanlanmış Görev adı (servis-kaydet.ps1 ile aynı). Varsayılan "FiyatCalismasi-Sunucu".

.NOTES
  Görev kayıtlıysa yönetici olarak çalıştırın. Çıkış kodları: 0 başarılı, 1 hata.
#>
param(
    [string]$AyarDosyasi = '',
    [switch]$BagimlilikAtla,
    [string]$GorevAdi = 'FiyatCalismasi-Sunucu'
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

try {
    if ($AyarDosyasi -eq '') { $AyarDosyasi = $VarsayilanAyarDosyasi }
    $ayarlar = Ayarlari-Oku $AyarDosyasi
    $db = Veritabani-Yolu $ayarlar
    $gorev = Get-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue
    if ($null -ne $gorev -and -not (Yonetici-Mi)) { throw "Zamanlanmış Görev ($GorevAdi) kayıtlı: bu betiği yönetici olarak çalıştırın." }

    # ---------- 1. Yedek ----------
    Write-Host ''
    Write-Host '=== 1/4 Yedek ==='
    if (Test-Path -LiteralPath $db) {
        $kod = Betik-Calistir '11-12-2026-yedekle.ps1' @{ AyarDosyasi = $AyarDosyasi; Etiket = 'guncelleme-oncesi' }
        if ($kod -eq 3) { Yaz-Uyari 'Ağ kopyası alınamadı; yerel yedekle devam ediliyor.' }
        elseif ($kod -ne 0) { throw 'Yedek alınamadı; güncelleme BAŞLATILMADI.' }
    } else {
        Yaz-Bilgi "Veritabanı yok ($db); yedek adımı atlandı."
    }

    # ---------- 2. Durdur ----------
    Write-Host ''
    Write-Host '=== 2/4 Sunucuyu durdur ==='
    if ($null -ne $gorev) {
        Stop-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    $kod = Betik-Calistir '11-12-2026-durdur.ps1' @{ AyarDosyasi = $AyarDosyasi }
    if ($kod -ne 0) { throw 'Sunucu durdurulamadı; güncelleme yapılmadı.' }

    # ---------- 3. Bağımlılık + derleme ----------
    Write-Host ''
    Write-Host '=== 3/4 Bağımlılıklar ve arayüz derlemesi ==='
    $kurParam = @{ OzetYok = $true }
    if ($BagimlilikAtla) { $kurParam['BagimlilikAtla'] = $true }
    $arayuz = Ayar $ayarlar 'ARAYUZ_DIZINI' ''
    if ($arayuz -ne '') { $kurParam['ArayuzCikti'] = $arayuz }
    $kurKod = Betik-Calistir '11-12-2026-kur.ps1' $kurParam
    if ($kurKod -ne 0) { Yaz-Hata 'Kurulum adımı başarısız. Sunucu yine de başlatılacak; yukarıdaki hatayı giderip guncelle.ps1''i yeniden çalıştırın.' }

    # ---------- 4. Başlat ----------
    Write-Host ''
    Write-Host '=== 4/4 Sunucuyu başlat ==='
    if ($null -ne $gorev) {
        Start-ScheduledTask -TaskName $GorevAdi
        $port = [int](Ayar $ayarlar 'PORT' '8000')
        $acildi = $false
        for ($i = 0; $i -lt 60; $i++) {
            Start-Sleep -Seconds 1
            if (@(Port-Dinleyenler $port).Count -gt 0) { $acildi = $true; break }
        }
        if (-not $acildi) { throw "Görev başlatıldı ama port $port 60 sn içinde açılmadı. veri\gunluk altındaki son günlüğe bakın." }
        Yaz-Bilgi "Sunucu görevle başlatıldı (port $port)."
    } else {
        $kod = Betik-Calistir '11-12-2026-baslat.ps1' @{ AyarDosyasi = $AyarDosyasi }
        if ($kod -ne 0) { throw 'Sunucu başlatılamadı.' }
    }

    if ($kurKod -ne 0) { exit 1 }
    Yaz-Bilgi 'Güncelleme tamam.'
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
