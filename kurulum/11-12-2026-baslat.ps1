<#
.SYNOPSIS
  Fiyat Çalışması sunucusunu tek adresten başlatır (arayüz + API aynı portta).

.DESCRIPTION
  kurulum\ayarlar.env dosyasını okur, ortam değişkenlerini ayarlar ve uvicorn'u arka planda başlatır.
  Çıktı veri\gunluk\ altındaki günlük dosyalarına yazılır. Port zaten dinleniyorsa başlatmaz, uyarır.
  Uygulama tek süreç varsayımıyla yazılmıştır: aynı veritabanı için ikinci bir sunucu BAŞLATMAYIN.

.PARAMETER AyarDosyasi
  Ayar dosyası yolu. Verilmezse kurulum\ayarlar.env.

.PARAMETER Bekle
  Sunucu süreci kapanana kadar bu betik de açık kalır (Zamanlanmış Görev bunu kullanır).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1

.NOTES
  Çıkış kodları: 0 başladı, 1 hata, 2 zaten çalışıyor / port dolu.
#>
param(
    [string]$AyarDosyasi = '',
    [switch]$Bekle
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

try {
    if ($AyarDosyasi -eq '') { $AyarDosyasi = $VarsayilanAyarDosyasi }
    if (-not (Test-Path -LiteralPath $AyarDosyasi)) {
        Yaz-Uyari "Ayar dosyası yok ($AyarDosyasi); varsayılanlarla başlatılıyor (127.0.0.1:8000). Önce kur.ps1 çalıştırılması önerilir."
    }
    $ayarlar = Ayarlari-Oku $AyarDosyasi
    $sunucuHost = Ayar $ayarlar 'HOST' '127.0.0.1'
    $port = [int](Ayar $ayarlar 'PORT' '8000')
    $python = Python-Yolu
    if (-not (Test-Path -LiteralPath $python)) { throw "Sanal ortam yok: $python. Önce kurulum\11-12-2026-kur.ps1 çalıştırın." }

    # ---------- Zaten çalışıyor mu? ----------
    $dinleyenler = @(Port-Dinleyenler $port)
    if ($dinleyenler.Count -gt 0) {
        $no = $dinleyenler[0]
        if (Bizim-Sunucu-Mu $no) {
            Yaz-Uyari "Sunucu zaten çalışıyor (port $port, süreç $no). Yeniden başlatmak için önce kurulum\11-12-2026-durdur.ps1."
        } else {
            Yaz-Uyari "Port $port başka bir süreç tarafından kullanılıyor (süreç $no, $(Surec-Adi $no)). ayarlar.env içinde PORT değiştirin ya da o süreci kapatın."
        }
        exit 2
    }

    # ---------- Arayüz derlemesi var mı? ----------
    $arayuz = Ayar $ayarlar 'ARAYUZ_DIZINI' (Join-Path $ProjeKoku 'frontend\dist')
    if (-not (Test-Path -LiteralPath (Join-Path $arayuz 'index.html'))) {
        Yaz-Uyari "Derlenmiş arayüz bulunamadı ($arayuz). Sunucu yalnız API olarak açılır; arayüz için kur.ps1 çalıştırın."
    }

    # ---------- Ortam değişkenleri (yalnız dolu olanlar; boşlar uygulamanın varsayılanını kullanır) ----------
    foreach ($ad in @('VERITABANI_URL', 'GIRIS_ZORUNLU', 'ONBELLEK_ISITMA', 'ONBELLEK_ISITMA_GECIKME_SN', 'CORS_ORIGINS', 'ARAYUZ_DIZINI', 'EXCEL_YOLU')) {
        $deger = Ayar $ayarlar $ad ''
        if ($deger -ne '') { Set-Item -Path "Env:$ad" -Value $deger } else { Remove-Item -Path "Env:$ad" -ErrorAction SilentlyContinue }
    }
    $env:PYTHONUTF8 = '1'
    $env:PYTHONUNBUFFERED = '1'   # günlük satırları bekletilmeden dosyaya yazılsın
    if ((Ayar $ayarlar 'GIRIS_ZORUNLU' '1') -in @('0', 'false', 'hayir')) {
        Yaz-Uyari 'GIRIS_ZORUNLU kapalı: uygulama şifresiz açılır. Sunucuda 1 olmalıdır.'
    }

    # ---------- Günlük dosyaları ----------
    if (-not (Test-Path -LiteralPath $GunlukDizini)) { New-Item -ItemType Directory -Path $GunlukDizini -Force | Out-Null }
    $tutGun = [int](Ayar $ayarlar 'GUNLUK_TUT_GUN' '30')
    $sinir = (Get-Date).AddDays(-$tutGun)
    # Yalnız bu betiğin ürettiği günlükler (AA-GG-YYYY-sunucu-<port>.log) budanır.
    Get-ChildItem -LiteralPath $GunlukDizini -Filter '*-sunucu-*.log' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $sinir } |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
    $gunlukDosyasi = Join-Path $GunlukDizini "$(Get-Date -Format 'MM-dd-yyyy')-sunucu-$port.log"   # aynı gün yeniden başlatılırsa sonuna eklenir
    $pidDosyasi = Join-Path $GunlukDizini "sunucu-$port.pid"

    # ---------- Başlat ----------
    # cmd.exe üzerinden başlatılır: çıktı (stdout + stderr) tek günlük dosyasına eklenir ve sunucu, bu betiği çağıranın
    # çıktı kanalını devralmaz (betik bir boruya/başka programa bağlıyken de takılmadan döner).
    if ($sunucuHost -notmatch '^[0-9A-Za-z\.\-:]+$') { throw "HOST geçersiz: $sunucuHost" }
    foreach ($yol in @($python, $gunlukDosyasi)) {
        if ($yol -match '[&|<>^%"]') { throw "Klasör yolunda desteklenmeyen karakter var (& | < > ^ % `"): $yol" }
    }
    $komut = '/d /c ""' + $python + '" -m uvicorn ' + $SunucuImzasi + ' --host ' + $sunucuHost + ' --port ' + $port + ' >> "' + $gunlukDosyasi + '" 2>&1"'
    Add-Content -LiteralPath $gunlukDosyasi -Encoding UTF8 -Value "=== $(Get-Date -Format 'dd.MM.yyyy HH:mm:ss') sunucu başlatılıyor ($sunucuHost`:$port) ==="
    Yaz-Bilgi "Sunucu başlatılıyor: $sunucuHost`:$port"
    $surec = Start-Process -FilePath $env:ComSpec -ArgumentList $komut -WorkingDirectory $ProjeKoku -WindowStyle Hidden -PassThru
    Set-Content -LiteralPath $pidDosyasi -Value $surec.Id -Encoding ASCII

    # ---------- Açıldı mı? (en çok 60 sn) ----------
    $yoklamaHost = $sunucuHost
    if ($sunucuHost -eq '0.0.0.0') { $yoklamaHost = '127.0.0.1' }
    $taban = "http://$yoklamaHost`:$port"
    $acildi = $false
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Seconds 1
        if ($surec.HasExited) { break }
        if (@(Port-Dinleyenler $port).Count -gt 0) { $acildi = $true; break }
    }
    if (-not $acildi) {
        Yaz-Hata "Sunucu açılamadı. Günlük: $gunlukDosyasi"
        if (Test-Path -LiteralPath $gunlukDosyasi) { Get-Content -LiteralPath $gunlukDosyasi -Tail 20 -Encoding UTF8 | ForEach-Object { Write-Host "    $_" } }
        if (-not $surec.HasExited) { & taskkill.exe /PID $surec.Id /T /F | Out-Null }
        Remove-Item -LiteralPath $pidDosyasi -Force -ErrorAction SilentlyContinue
        exit 1
    }

    # İlk istek: veritabanı dosyası yoksa oluşur, şema güncellenir, günün otomatik yedeği alınır (backend/depo/veritabani.py).
    $kod = Http-Durum "$taban/api/v1/kimlik/ben" 120
    if ($kod -eq 200 -or $kod -eq 401) {
        Yaz-Bilgi "API yanıt veriyor (HTTP $kod)."
    } else {
        Yaz-Uyari "API beklenen yanıtı vermedi (HTTP $kod). Günlük: $gunlukDosyasi"
    }
    $kod = Http-Durum "$taban/" 30
    if ($kod -eq 200) { Yaz-Bilgi 'Arayüz yanıt veriyor.' } else { Yaz-Uyari "Arayüz sunulmuyor (HTTP $kod): derleme eksik olabilir." }

    Write-Host ''
    if ($sunucuHost -eq '0.0.0.0') {
        Write-Host "  Adres (ağdan)        : http://$($env:COMPUTERNAME):$port"
        Write-Host "  Adres (bu bilgisayar): http://127.0.0.1:$port"
    } else {
        Write-Host "  Adres : http://$sunucuHost`:$port"
    }
    Write-Host "  Günlük: $gunlukDosyasi"
    Write-Host "  Durdur: powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-durdur.ps1"
    Write-Host ''

    if ($Bekle) {
        Yaz-Bilgi 'Sunucu kapanana kadar bekleniyor (-Bekle) ...'
        $surec.WaitForExit()
        Remove-Item -LiteralPath $pidDosyasi -Force -ErrorAction SilentlyContinue
        exit $surec.ExitCode
    }
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
