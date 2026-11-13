<#
.SYNOPSIS
  Fiyat Çalışması sunucusunu durdurur.

.DESCRIPTION
  Ayar dosyasındaki PORT'u dinleyen süreç BİZİM sunucumuzsa (komut satırında "backend.uygulama:app" geçiyorsa) kapatır.
  Portu başka bir program kullanıyorsa dokunmaz, yalnız bildirir. Veri kaybı olmaz: veritabanı (SQLite WAL) ani kapanmaya dayanıklıdır,
  ancak o anda süren bir kayıt işlemi tamamlanmamış sayılır; mümkünse kullanıcılar çalışmıyorken durdurun.

.PARAMETER AyarDosyasi
  Ayar dosyası yolu. Verilmezse kurulum\ayarlar.env.

.NOTES
  Çıkış kodları: 0 durduruldu ya da zaten çalışmıyordu, 1 hata, 2 port başka bir sürece ait (dokunulmadı).
  Sunucu Zamanlanmış Görev ile (başka kullanıcıyla) çalışıyorsa bu betiği yönetici olarak çalıştırın.
#>
param(
    [string]$AyarDosyasi = ''
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

try {
    if ($AyarDosyasi -eq '') { $AyarDosyasi = $VarsayilanAyarDosyasi }
    $ayarlar = Ayarlari-Oku $AyarDosyasi
    $port = [int](Ayar $ayarlar 'PORT' '8000')
    $pidDosyasi = Join-Path $GunlukDizini "sunucu-$port.pid"

    $hedefler = @()
    foreach ($no in @(Port-Dinleyenler $port)) {
        if (Bizim-Sunucu-Mu $no) {
            $hedefler += $no
        } else {
            Yaz-Uyari "Port $port, bu uygulamaya ait olduğu doğrulanamayan bir süreçte (süreç $no, $(Surec-Adi $no)). Dokunulmadı."
            Yaz-Uyari 'Sunucu başka bir kullanıcıyla çalışıyorsa bu betiği yönetici olarak çalıştırın.'
            exit 2
        }
    }
    # Başlatan (üst) süreç: sanal ortamın python.exe'si asıl Python'u alt süreç olarak açar; ikisi de kapatılır.
    if (Test-Path -LiteralPath $pidDosyasi) {
        $kayitli = 0
        if ([int]::TryParse(("$(Get-Content -LiteralPath $pidDosyasi -TotalCount 1)").Trim(), [ref]$kayitli)) {
            if ($kayitli -gt 0 -and (Bizim-Sunucu-Mu $kayitli) -and ($hedefler -notcontains $kayitli)) { $hedefler += $kayitli }
        }
    }

    if ($hedefler.Count -eq 0) {
        Yaz-Bilgi "Sunucu çalışmıyor (port $port boş)."
        Remove-Item -LiteralPath $pidDosyasi -Force -ErrorAction SilentlyContinue
        exit 0
    }

    foreach ($no in $hedefler) {
        if (Get-Process -Id $no -ErrorAction SilentlyContinue) {
            Yaz-Bilgi "Süreç kapatılıyor: $no"
            $eski = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
            & taskkill.exe /PID $no /T /F 2>&1 | Out-Null
            $ErrorActionPreference = $eski
        }
    }
    for ($i = 0; $i -lt 20; $i++) {
        if (@(Port-Dinleyenler $port).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    if (@(Port-Dinleyenler $port).Count -gt 0) { throw "Sunucu kapatılamadı; port $port hâlâ dinleniyor." }
    Remove-Item -LiteralPath $pidDosyasi -Force -ErrorAction SilentlyContinue
    Yaz-Bilgi "Sunucu durduruldu (port $port)."
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
