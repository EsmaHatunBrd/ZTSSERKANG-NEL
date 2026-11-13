<#
.SYNOPSIS
  Sunucunun bilgisayar açılışında kendiliğinden başlaması için Zamanlanmış Görev kaydeder (ya da kaldırır).

.DESCRIPTION
  YÖNETİCİ olarak çalıştırılır. Sistemde kalıcı değişiklik yapar:
    - "FiyatCalismasi-Sunucu" görevi: bilgisayar açılışında, verilen kullanıcıyla (oturum açık olmasa da)
      kurulum\11-12-2026-baslat.ps1 -Bekle çalıştırır; süreç düşerse 1 dakika arayla 3 kez yeniden dener.
    - -GunlukYedek verilirse "FiyatCalismasi-GunlukYedek" görevi: her gün -YedekSaati'nde yedekle.ps1 çalıştırır.
      (Uygulamanın kendi otomatik yedeği yalnız sunucu sürecinin İLK isteğinde alınır; haftalarca açık kalan sunucuda
      günlük yedek için bu görev gerekir.)
    - -GuvenlikDuvari verilirse ayar dosyasındaki PORT için gelen bağlantı kuralı eklenir (Etki alanı + Özel ağ profilleri).
  -Kaldir: bu betiğin eklediği görevleri ve güvenlik duvarı kuralını kaldırır (veriye, dosyalara dokunmaz).

  Kullanıcı hesabı: proje klasörüne ve veri\ klasörüne yazma yetkisi olmalı; "Toplu iş olarak oturum açma"
  (Log on as a batch job) hakkı gerekir. Ağ paylaşımına yedek alınacaksa paylaşım yetkisi de bu hesapta olmalı.
  Şifre yalnız kayıt anında sorulur; hiçbir dosyaya yazılmaz (Windows Görev Zamanlayıcı kendi kasasında saklar).

.PARAMETER Kullanici
  Görevin çalışacağı hesap, örn. SIRKET\fiyatsvc ya da .\fiyatsvc. (-Kaldir dışında zorunlu.)

.PARAMETER AyarDosyasi
  Ayar dosyası yolu. Verilmezse kurulum\ayarlar.env.

.PARAMETER GunlukYedek
  Günlük yedek görevini de kaydeder.

.PARAMETER YedekSaati
  Günlük yedek saati (SS:DD). Varsayılan 02:00.

.PARAMETER GuvenlikDuvari
  PORT için Windows Güvenlik Duvarı gelen kuralı ekler.

.PARAMETER Kaldir
  Kayıtları kaldırır.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-servis-kaydet.ps1 -Kullanici SIRKET\fiyatsvc -GunlukYedek -GuvenlikDuvari

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-servis-kaydet.ps1 -Kaldir
#>
param(
    [string]$Kullanici = '',
    [string]$AyarDosyasi = '',
    [switch]$GunlukYedek,
    [string]$YedekSaati = '02:00',
    [switch]$GuvenlikDuvari,
    [switch]$Kaldir
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

$SunucuGorevi = 'FiyatCalismasi-Sunucu'
$YedekGorevi = 'FiyatCalismasi-GunlukYedek'
$KuralAdi = 'Fiyat Calismasi (HTTP)'

try {
    if (-not (Yonetici-Mi)) { throw 'Bu betik yönetici yetkisi ister: PowerShell''i "Yönetici olarak çalıştır" ile açın.' }
    if ($AyarDosyasi -eq '') { $AyarDosyasi = $VarsayilanAyarDosyasi }
    $AyarDosyasi = [System.IO.Path]::GetFullPath($AyarDosyasi)

    # ---------- Kaldırma ----------
    if ($Kaldir) {
        foreach ($ad in @($SunucuGorevi, $YedekGorevi)) {
            if (Get-ScheduledTask -TaskName $ad -ErrorAction SilentlyContinue) {
                Stop-ScheduledTask -TaskName $ad -ErrorAction SilentlyContinue
                Unregister-ScheduledTask -TaskName $ad -Confirm:$false
                Yaz-Bilgi "Görev kaldırıldı: $ad"
            } else {
                Yaz-Bilgi "Görev zaten yok: $ad"
            }
        }
        if (Get-NetFirewallRule -DisplayName $KuralAdi -ErrorAction SilentlyContinue) {
            Remove-NetFirewallRule -DisplayName $KuralAdi
            Yaz-Bilgi "Güvenlik duvarı kuralı kaldırıldı: $KuralAdi"
        }
        Yaz-Bilgi 'Çalışan sunucu varsa kurulum\11-12-2026-durdur.ps1 ile durdurabilirsiniz.'
        exit 0
    }

    # ---------- Kayıt ----------
    if ($Kullanici -eq '') { throw '-Kullanici zorunlu (örn. SIRKET\fiyatsvc).' }
    if (-not (Test-Path -LiteralPath $AyarDosyasi)) { throw "Ayar dosyası yok: $AyarDosyasi. Önce kur.ps1 çalıştırın." }
    if (-not (Test-Path -LiteralPath (Python-Yolu))) { throw 'Sanal ortam yok. Önce kur.ps1 çalıştırın.' }
    $saat = [datetime]::MinValue
    if (-not [datetime]::TryParseExact($YedekSaati, 'HH:mm', [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::None, [ref]$saat)) {
        throw '-YedekSaati SS:DD biçiminde olmalı (örn. 02:00).'
    }
    $ayarlar = Ayarlari-Oku $AyarDosyasi
    $port = [int](Ayar $ayarlar 'PORT' '8000')

    $guvenliSifre = Read-Host -AsSecureString "$Kullanici hesabının şifresi (dosyaya yazılmaz)"
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($guvenliSifre)
    try {
        $sifre = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }

    $ps = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $baslat = Join-Path $KurulumDizini '11-12-2026-baslat.ps1'
    $yedekle = Join-Path $KurulumDizini '11-12-2026-yedekle.ps1'

    # Sunucu görevi: açılışta, süre sınırı yok, düşerse yeniden dene.
    $eylem = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $ProjeKoku `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$baslat`" -Bekle -AyarDosyasi `"$AyarDosyasi`""
    $tetik = New-ScheduledTaskTrigger -AtStartup
    $ayar = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $SunucuGorevi -Action $eylem -Trigger $tetik -Settings $ayar -User $Kullanici -Password $sifre `
        -RunLevel Limited -Description 'Fiyat Çalışması sunucusu (uvicorn, tek adres). kurulum\11-12-2026-servis-kaydet.ps1 ile kaydedildi.' -Force | Out-Null
    Yaz-Bilgi "Görev kaydedildi: $SunucuGorevi (açılışta, kullanıcı $Kullanici)"

    if ($GunlukYedek) {
        $eylemY = New-ScheduledTaskAction -Execute $ps -WorkingDirectory $ProjeKoku `
            -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$yedekle`" -AyarDosyasi `"$AyarDosyasi`""
        $tetikY = New-ScheduledTaskTrigger -Daily -At $saat
        $ayarY = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 1) -StartWhenAvailable -AllowStartIfOnBatteries
        Register-ScheduledTask -TaskName $YedekGorevi -Action $eylemY -Trigger $tetikY -Settings $ayarY -User $Kullanici -Password $sifre `
            -RunLevel Limited -Description 'Fiyat Çalışması günlük veritabanı yedeği (yedekle.ps1).' -Force | Out-Null
        Yaz-Bilgi "Görev kaydedildi: $YedekGorevi (her gün $YedekSaati)"
    }
    $sifre = $null

    if ($GuvenlikDuvari) {
        if (Get-NetFirewallRule -DisplayName $KuralAdi -ErrorAction SilentlyContinue) { Remove-NetFirewallRule -DisplayName $KuralAdi }
        New-NetFirewallRule -DisplayName $KuralAdi -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -Profile Domain, Private | Out-Null
        Yaz-Bilgi "Güvenlik duvarı kuralı eklendi: TCP $port (Etki alanı + Özel ağ)"
    }

    Write-Host ''
    Write-Host "  Şimdi başlatmak için : Start-ScheduledTask -TaskName $SunucuGorevi"
    Write-Host "  Durum                : Get-ScheduledTask -TaskName $SunucuGorevi | Get-ScheduledTaskInfo"
    Write-Host '  Kaldırmak için       : kurulum\11-12-2026-servis-kaydet.ps1 -Kaldir'
    Write-Host '  Not: sunucu elle (baslat.ps1) açıksa önce durdur.ps1 ile kapatın; aynı portta iki sunucu çalışmaz.'
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
