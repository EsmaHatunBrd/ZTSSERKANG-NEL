<#
.SYNOPSIS
  Fiyat Çalışması - sunucuda ilk kurulum (yeniden çalıştırılabilir).

.DESCRIPTION
  Sırasıyla:
    1. Python ve Node sürümlerini denetler.
    2. Python sanal ortamını (.venv) yoksa oluşturur, bağımlılıkları kurar (pyproject.toml -> pip install -e .).
    3. Arayüz bağımlılıklarını kurar (npm ci) ve arayüzü derler (npm run build -> frontend\dist).
    4. veri\, veri\yedek\ ve veri\gunluk\ klasörlerini yoksa oluşturur.
    5. kurulum\ayarlar.env yoksa şablondan (ayarlar.ornek.env) kopyalar. Var olan ayar dosyasına DOKUNMAZ.
  Hiçbir veriyi silmez, veritabanına yazmaz, servis/zamanlanmış görev kaydetmez.

.PARAMETER Python
  Sanal ortamı oluşturmak için kullanılacak python.exe yolu. Verilmezse "py -3", sonra PATH'teki "python" denenir.

.PARAMETER BagimlilikAtla
  pip ve "npm ci" adımlarını atlar (bağımlılıklar zaten kuruluysa; internet yoksa).

.PARAMETER DerlemeAtla
  Arayüz derlemesini atlar.

.PARAMETER ArayuzCikti
  Arayüz derlemesinin yazılacağı klasör. Verilmezse frontend\dist. Başka klasör verilirse ayarlar.env içinde ARAYUZ_DIZINI aynı klasörü göstermelidir.

.PARAMETER OzetYok
  Sondaki "sonraki adımlar" listesini yazmaz (guncelle.ps1 bunu kullanır).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-kur.ps1
#>
param(
    [string]$Python = '',
    [switch]$BagimlilikAtla,
    [switch]$DerlemeAtla,
    [string]$ArayuzCikti = '',
    [switch]$OzetYok
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

$EnAzPython = [version]'3.11'          # pyproject.toml: requires-python >= 3.11
$FrontendDizini = Join-Path $ProjeKoku 'frontend'

function Node-Surumu-Uygun([version]$s) {
    # Vite 8 gereksinimi: Node ^20.19.0 veya >= 22.12.0
    if ($s.Major -eq 20 -and $s -ge [version]'20.19.0') { return $true }
    if ($s -ge [version]'22.12.0') { return $true }
    return $false
}

function Python-Surumu([string]$Calistirilabilir, [string[]]$OnArgumanlar) {
    try {
        $cikti = & $Calistirilabilir @OnArgumanlar -c "import sys; print('%d.%d.%d' % sys.version_info[:3])" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $cikti) { return $null }
        return [version]("$cikti".Trim())
    } catch {
        return $null
    }
}

try {
    Write-Host ''
    Write-Host '=== Fiyat Çalışması kurulumu ==='
    Yaz-Bilgi "Proje klasörü: $ProjeKoku"

    # ---------- 1. Python sanal ortamı ----------
    $venvPython = Python-Yolu
    if (Test-Path -LiteralPath $venvPython) {
        $surum = Python-Surumu $venvPython @()
        if ($null -eq $surum) { throw "Sanal ortam bozuk görünüyor: $venvPython çalışmıyor. .venv klasörünü elle kaldırıp kur.ps1'i yeniden çalıştırın." }
        if ($surum -lt $EnAzPython) { throw "Sanal ortamdaki Python $surum; en az $EnAzPython gerekir. .venv klasörünü elle kaldırıp uygun Python ile yeniden kurun." }
        Yaz-Bilgi "Sanal ortam mevcut (Python $surum); yeniden oluşturulmadı."
    } else {
        $aday = $null; $onArg = @()
        if ($Python -ne '') {
            if (-not (Test-Path -LiteralPath $Python)) { throw "Verilen Python bulunamadı: $Python" }
            $aday = $Python
        } elseif (Get-Command 'py.exe' -ErrorAction SilentlyContinue) {
            $aday = 'py.exe'; $onArg = @('-3')
        } elseif (Get-Command 'python.exe' -ErrorAction SilentlyContinue) {
            $aday = 'python.exe'
        }
        if ($null -eq $aday) { throw "Python bulunamadı. Python $EnAzPython veya üstünü kurun (python.org) ya da -Python ile python.exe yolunu verin." }
        $surum = Python-Surumu $aday $onArg
        if ($null -eq $surum) { throw "Python çalıştırılamadı ($aday). -Python ile python.exe yolunu verin." }
        if ($surum -lt $EnAzPython) { throw "Bulunan Python $surum; en az $EnAzPython gerekir." }
        Yaz-Bilgi "Sanal ortam oluşturuluyor (Python $surum) ..."
        $kod = Komut-Calistir $aday ($onArg + @('-m', 'venv', (Join-Path $ProjeKoku '.venv'))) $ProjeKoku
        if ($kod -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) { throw "Sanal ortam oluşturulamadı (çıkış kodu $kod)." }
    }

    # ---------- 2. Python bağımlılıkları ----------
    if ($BagimlilikAtla) {
        Yaz-Bilgi 'Python bağımlılıkları atlandı (-BagimlilikAtla).'
    } else {
        Yaz-Bilgi 'Python bağımlılıkları kuruluyor (pyproject.toml) ...'
        $kod = Komut-Calistir $venvPython @('-m', 'pip', 'install', '--disable-pip-version-check', '-e', '.') $ProjeKoku
        if ($kod -ne 0) { throw "pip install başarısız (çıkış kodu $kod). İnternet/PyPI erişimini denetleyin." }
    }
    $kod = Komut-Calistir $venvPython @('-c', 'import fastapi, uvicorn, sqlalchemy, openpyxl, multipart, defusedxml') $ProjeKoku
    if ($kod -ne 0) { throw 'Python bağımlılıkları eksik. kur.ps1''i -BagimlilikAtla OLMADAN çalıştırın.' }
    Yaz-Bilgi 'Python bağımlılıkları tamam.'

    # ---------- 3. Arayüz ----------
    if ($DerlemeAtla) {
        Yaz-Bilgi 'Arayüz derlemesi atlandı (-DerlemeAtla).'
    } else {
        if (-not (Get-Command 'node.exe' -ErrorAction SilentlyContinue)) { throw 'Node.js bulunamadı. Node 22 LTS (>= 22.12) veya 20.19+ kurun (nodejs.org).' }
        if (-not (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue)) { throw 'npm bulunamadı (Node.js kurulumuyla gelir).' }
        $nodeSurum = [version]((& node.exe --version).Trim().TrimStart('v'))
        if (-not (Node-Surumu-Uygun $nodeSurum)) { throw "Node $nodeSurum uygun değil; 20.19+ veya 22.12+ gerekir." }
        Yaz-Bilgi "Node $nodeSurum bulundu."

        if ($BagimlilikAtla) {
            if (-not (Test-Path -LiteralPath (Join-Path $FrontendDizini 'node_modules'))) { throw 'frontend\node_modules yok; -BagimlilikAtla kullanılamaz.' }
            Yaz-Bilgi 'npm ci atlandı (-BagimlilikAtla).'
        } else {
            Yaz-Bilgi 'Arayüz bağımlılıkları kuruluyor (npm ci) ...'
            $kod = Komut-Calistir 'npm.cmd' @('ci', '--no-audit', '--no-fund') $FrontendDizini
            if ($kod -ne 0) { throw "npm ci başarısız (çıkış kodu $kod). İnternet/npm erişimini denetleyin." }
        }

        $derlemeArg = @('run', 'build')
        $hedefDist = Join-Path $FrontendDizini 'dist'
        if ($ArayuzCikti -ne '') {
            $hedefDist = [System.IO.Path]::GetFullPath($ArayuzCikti)
            $derlemeArg += @('--', '--outDir', $hedefDist, '--emptyOutDir')
        }
        Yaz-Bilgi "Arayüz derleniyor -> $hedefDist ..."
        $kod = Komut-Calistir 'npm.cmd' $derlemeArg $FrontendDizini
        if ($kod -ne 0) { throw "Arayüz derlemesi başarısız (çıkış kodu $kod)." }
        if (-not (Test-Path -LiteralPath (Join-Path $hedefDist 'index.html'))) { throw "Derleme bitti ama index.html yok: $hedefDist" }
        Yaz-Bilgi 'Arayüz derlendi.'
    }

    # ---------- 4. Klasörler ----------
    foreach ($k in @('veri', 'veri\yedek', 'veri\gunluk')) {
        $yol = Join-Path $ProjeKoku $k
        if (-not (Test-Path -LiteralPath $yol)) {
            New-Item -ItemType Directory -Path $yol | Out-Null
            Yaz-Bilgi "Klasör oluşturuldu: $yol"
        }
    }

    # ---------- 5. Ayar dosyası ----------
    if (Test-Path -LiteralPath $VarsayilanAyarDosyasi) {
        Yaz-Bilgi "Ayar dosyası mevcut, dokunulmadı: $VarsayilanAyarDosyasi"
    } else {
        Copy-Item -LiteralPath $OrnekAyarDosyasi -Destination $VarsayilanAyarDosyasi
        Yaz-Bilgi "Ayar dosyası şablondan oluşturuldu: $VarsayilanAyarDosyasi"
    }

    # ---------- Sonraki adımlar ----------
    if ($OzetYok) { Yaz-Bilgi 'Kurulum adımları tamam.'; exit 0 }
    $ayarlar = Ayarlari-Oku $VarsayilanAyarDosyasi
    $db = Veritabani-Yolu $ayarlar
    $port = Ayar $ayarlar 'PORT' '8000'
    Write-Host ''
    Write-Host '=== Kurulum tamam. Sonraki adımlar ==='
    Write-Host "  1. Ayarları gözden geçirin : $VarsayilanAyarDosyasi"
    if (Test-Path -LiteralPath $db) {
        Write-Host "  2. Veritabanı bulundu      : $db"
    } else {
        Write-Host "  2. Veritabanı henüz yok    : $db"
        Write-Host '     (mevcut fiyat.db dosyanız varsa sunucuyu başlatmadan önce buraya kopyalayın; yoksa ilk başlatmada boş oluşturulur)'
    }
    Write-Host '  3. Sunucuyu başlatın       : powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1'
    Write-Host '  4. İlk Genel Direktör      : (sunucu bir kez başladıktan sonra, yalnız ilk kurulumda)'
    Write-Host "       .venv\Scripts\python.exe scripts\11-04-2026-ilk-genel-direktor.py --db `"$db`""
    Write-Host '     Ekrana yazılan geçici şifre başka yerde saklanmaz; ilk girişte değiştirilir.'
    Write-Host "  5. Adres                   : http://$($env:COMPUTERNAME):$port"
    Write-Host '  6. Açılışta otomatik başlatma (yönetici): kurulum\11-12-2026-servis-kaydet.ps1'
    Write-Host ''
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
