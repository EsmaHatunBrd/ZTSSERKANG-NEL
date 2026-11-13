# Kurulum betiklerinin ortak yardımcıları. Tek başına çalıştırılmaz; diğer betikler ". ortak.ps1" ile içine alır.
# PowerShell 5.1 uyumludur.

$ErrorActionPreference = 'Stop'

$KurulumDizini = $PSScriptRoot
$ProjeKoku = Split-Path -Parent $PSScriptRoot
$VarsayilanAyarDosyasi = Join-Path $KurulumDizini 'ayarlar.env'
$OrnekAyarDosyasi = Join-Path $KurulumDizini 'ayarlar.ornek.env'
$GunlukDizini = Join-Path $ProjeKoku 'veri\gunluk'
$SunucuImzasi = 'backend.uygulama:app'   # süreç komut satırında aranır: yalnız bizim sunucumuz durdurulur

function Yaz-Bilgi([string]$Mesaj) { Write-Host "[bilgi] $Mesaj" }
function Yaz-Uyari([string]$Mesaj) { Write-Host "[UYARI] $Mesaj" -ForegroundColor Yellow }
function Yaz-Hata([string]$Mesaj) { Write-Host "[HATA]  $Mesaj" -ForegroundColor Red }

function Ayarlari-Oku([string]$Dosya) {
    # ANAHTAR=DEGER satırları; "#" ile başlayan satırlar ve boş satırlar atlanır. Dosya yoksa boş tablo döner.
    $tablo = @{}
    if (-not $Dosya) { $Dosya = $VarsayilanAyarDosyasi }
    if (-not (Test-Path -LiteralPath $Dosya)) { return $tablo }
    foreach ($satir in (Get-Content -LiteralPath $Dosya -Encoding UTF8)) {
        $s = $satir.Trim()
        if ($s -eq '' -or $s.StartsWith('#')) { continue }
        $i = $s.IndexOf('=')
        if ($i -lt 1) { continue }
        $ad = $s.Substring(0, $i).Trim()
        $deger = $s.Substring($i + 1).Trim()
        if ($deger.Length -ge 2 -and (($deger.StartsWith('"') -and $deger.EndsWith('"')) -or ($deger.StartsWith("'") -and $deger.EndsWith("'")))) {
            $deger = $deger.Substring(1, $deger.Length - 2)
        }
        $tablo[$ad] = $deger
    }
    return $tablo
}

function Ayar($Ayarlar, [string]$Ad, [string]$Varsayilan) {
    if ($Ayarlar.ContainsKey($Ad) -and $Ayarlar[$Ad] -ne '') { return $Ayarlar[$Ad] }
    return $Varsayilan
}

function Python-Yolu {
    return (Join-Path $ProjeKoku '.venv\Scripts\python.exe')
}

function Veritabani-Yolu($Ayarlar) {
    # VERITABANI_URL boşsa uygulamanın varsayılanı: <proje>\veri\fiyat.db (backend/ayarlar.py).
    $url = Ayar $Ayarlar 'VERITABANI_URL' ''
    if ($url -eq '') { return (Join-Path $ProjeKoku 'veri\fiyat.db') }
    $onek = 'sqlite:///'
    if (-not $url.StartsWith($onek)) {
        throw "VERITABANI_URL yalnız dosya tabanlı SQLite olabilir (sqlite:///C:/klasor/fiyat.db). Verilen değer desteklenmiyor."
    }
    return ($url.Substring($onek.Length) -replace '/', '\')
}

function Port-Dinleyenler([int]$Port) {
    # Portu dinleyen süreç kimlikleri (yoksa boş dizi).
    $b = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($b.Count -eq 0) { return @() }
    return @($b | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Bizim-Sunucu-Mu([int]$SurecNo) {
    # Komut satırında sunucu imzası var mı? Başka kullanıcının süreci yönetici yetkisi olmadan okunamaz (o zaman $false).
    $s = Get-CimInstance Win32_Process -Filter "ProcessId=$SurecNo" -ErrorAction SilentlyContinue
    if ($null -eq $s) { return $false }
    if ($null -eq $s.CommandLine) { return $false }
    return ($s.CommandLine -like "*$SunucuImzasi*")
}

function Surec-Adi([int]$SurecNo) {
    $p = Get-Process -Id $SurecNo -ErrorAction SilentlyContinue
    if ($null -eq $p) { return '(bilinmiyor)' }
    return $p.ProcessName
}

function Http-Durum([string]$Adres, [int]$ZamanAsimiSn) {
    # Yanıtın HTTP durum kodu; bağlantı kurulamazsa 0. Vekil sunucu (proxy) kullanılmaz.
    try {
        $istek = [System.Net.HttpWebRequest]::Create($Adres)
        $istek.Proxy = $null
        $istek.Timeout = $ZamanAsimiSn * 1000
        $istek.Method = 'GET'
        $yanit = $istek.GetResponse()
        $kod = [int]$yanit.StatusCode
        $yanit.Close()
        return $kod
    } catch [System.Net.WebException] {
        if ($null -ne $_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

function Yedek-Araci {
    return (Join-Path $KurulumDizini '11-12-2026-yedek-araci.py')
}

function Yonetici-Mi {
    $kimlik = [Security.Principal.WindowsIdentity]::GetCurrent()
    $rol = New-Object Security.Principal.WindowsPrincipal($kimlik)
    return $rol.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Betik-Calistir([string]$Ad, [hashtable]$Parametreler) {
    # Aynı klasördeki başka bir betiği çalıştırır; çıkış kodunu döner (0 = başarılı).
    $global:LASTEXITCODE = 0
    $yol = Join-Path $KurulumDizini $Ad
    & $yol @Parametreler | Out-Host
    return $global:LASTEXITCODE
}

function Komut-Calistir([string]$Dosya, [string[]]$Argumanlar, [string]$CalismaDizini) {
    # Dış komutu (python, npm ...) verilen klasörde çalıştırır, çıktısını ekrana yazar, çıkış kodunu döner.
    # Dış komutların uyarı satırları betiği durdurmasın diye hata tercihi geçici olarak gevşetilir.
    $eski = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    Push-Location -LiteralPath $CalismaDizini
    try {
        & $Dosya @Argumanlar 2>&1 | ForEach-Object { "$_" } | Out-Host
        $kod = $LASTEXITCODE
    } finally {
        Pop-Location
        $ErrorActionPreference = $eski
    }
    return $kod
}
