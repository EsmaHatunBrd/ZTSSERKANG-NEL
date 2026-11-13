<#
.SYNOPSIS
  Veritabanını tarihli adla yedekler (yerel klasör + isteğe bağlı ağ paylaşımı) ve eski yedekleri budar.

.DESCRIPTION
  - Yedek, sunucu çalışırken de tutarlı alınır (SQLite backup API; kurulum\11-12-2026-yedek-araci.py).
  - Yerel hedef: veritabanı dosyasının yanındaki "yedek" klasörü (uygulamanın otomatik yedekleriyle aynı yer).
    Dosya adı: AA-GG-YYYY-SSDDSS-<etiket>-<veritabanı adı>, örn. 11-12-2026-020000-yedek-fiyat.db
  - ayarlar.env içinde YEDEK_AG_KLASORU doluysa yedek oraya da kopyalanır ve kopya doğrulanır (SHA-256).
  - Budama: YALNIZ bu betiğin "yedek" etiketiyle aldığı dosyalardan YEDEK_TUT_GUN (varsayılan 14) günden eskiler silinir;
    en yeni yedek her zaman kalır. Uygulamanın otomatik yedeklerine, elle alınanlara ve başka etiketli
    (guncelleme-oncesi, geri-yukleme-oncesi) yedeklere dokunulmaz.

.PARAMETER AyarDosyasi
  Ayar dosyası yolu. Verilmezse kurulum\ayarlar.env.

.PARAMETER Etiket
  Dosya adındaki etiket (küçük harf, rakam, tire). Varsayılan "yedek". Başka etiketli yedekler budanmaz.

.NOTES
  Çıkış kodları: 0 başarılı, 1 yerel yedek alınamadı, 3 yerel yedek alındı ama ağ kopyası başarısız.
#>
param(
    [string]$AyarDosyasi = '',
    [string]$Etiket = 'yedek'
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

function Eski-Yedekleri-Buda([string]$Klasor, [string]$DbAdi, [int]$TutGun) {
    # Dosya adındaki tarihe göre budar; en yeni dosya her zaman kalır. Silinen dosya adlarını ekrana yazar.
    $desen = '^(\d{2}-\d{2}-\d{4})-\d{6}-yedek-' + [regex]::Escape($DbAdi) + '$'
    $sinir = (Get-Date).Date.AddDays(-$TutGun)
    $adaylar = @()
    foreach ($d in @(Get-ChildItem -LiteralPath $Klasor -File -ErrorAction SilentlyContinue)) {
        $m = [regex]::Match($d.Name, $desen)
        if (-not $m.Success) { continue }
        $tarih = [datetime]::MinValue
        if (-not [datetime]::TryParseExact($m.Groups[1].Value, 'MM-dd-yyyy', [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::None, [ref]$tarih)) { continue }
        $adaylar += New-Object PSObject -Property @{ Dosya = $d; Tarih = $tarih }
    }
    if ($adaylar.Count -le 1) { return }
    $sirali = @($adaylar | Sort-Object -Property @{ Expression = { $_.Tarih } }, @{ Expression = { $_.Dosya.Name } })
    $enYeni = $sirali[$sirali.Count - 1].Dosya.FullName
    foreach ($a in $sirali) {
        if ($a.Tarih -lt $sinir -and $a.Dosya.FullName -ne $enYeni) {
            Remove-Item -LiteralPath $a.Dosya.FullName -Force
            Yaz-Bilgi "Eski yedek silindi ($TutGun günden eski): $($a.Dosya.FullName)"
        }
    }
}

try {
    if ($Etiket -notmatch '^[a-z0-9\-]+$') { throw 'Etiket yalnız küçük harf, rakam ve tire içerebilir.' }
    if ($AyarDosyasi -eq '') { $AyarDosyasi = $VarsayilanAyarDosyasi }
    $ayarlar = Ayarlari-Oku $AyarDosyasi
    $db = Veritabani-Yolu $ayarlar
    if (-not (Test-Path -LiteralPath $db)) { throw "Veritabanı yok: $db" }
    $python = Python-Yolu
    if (-not (Test-Path -LiteralPath $python)) { throw "Sanal ortam yok: $python. Önce kur.ps1 çalıştırın." }

    $dbAdi = Split-Path -Leaf $db
    $yedekKlasoru = Join-Path (Split-Path -Parent $db) 'yedek'
    if (-not (Test-Path -LiteralPath $yedekKlasoru)) { New-Item -ItemType Directory -Path $yedekKlasoru -Force | Out-Null }
    $ad = "$(Get-Date -Format 'MM-dd-yyyy-HHmmss')-$Etiket-$dbAdi"
    $hedef = Join-Path $yedekKlasoru $ad

    # ---------- Yerel yedek ----------
    $kod = Komut-Calistir $python @((Yedek-Araci), 'yedekle', '--db', $db, '--hedef', $hedef) $ProjeKoku
    if ($kod -ne 0 -or -not (Test-Path -LiteralPath $hedef)) { throw "Yerel yedek alınamadı (çıkış kodu $kod)." }
    Yaz-Bilgi "Yerel yedek: $hedef"

    $tutGun = [int](Ayar $ayarlar 'YEDEK_TUT_GUN' '14')
    if ($tutGun -lt 1) { throw 'YEDEK_TUT_GUN en az 1 olmalı.' }
    Eski-Yedekleri-Buda $yedekKlasoru $dbAdi $tutGun

    # ---------- Ağ paylaşımı ----------
    $ag = Ayar $ayarlar 'YEDEK_AG_KLASORU' ''
    if ($ag -eq '') {
        Yaz-Bilgi 'Ağ paylaşımı ayarlı değil (YEDEK_AG_KLASORU boş): yalnız yerel yedek alındı.'
        exit 0
    }
    try {
        if (-not (Test-Path -LiteralPath $ag)) { throw "Ağ klasörüne erişilemiyor: $ag" }
        $agHedef = Join-Path $ag $ad
        Copy-Item -LiteralPath $hedef -Destination $agHedef
        $ozet1 = (Get-FileHash -LiteralPath $hedef -Algorithm SHA256).Hash
        $ozet2 = (Get-FileHash -LiteralPath $agHedef -Algorithm SHA256).Hash
        if ($ozet1 -ne $ozet2) { throw "Ağ kopyası yerel yedekle aynı değil: $agHedef" }
        Yaz-Bilgi "Ağ kopyası doğrulandı: $agHedef"
        Eski-Yedekleri-Buda $ag $dbAdi $tutGun
    } catch {
        Yaz-Hata "Ağ kopyası BAŞARISIZ: $($_.Exception.Message)"
        Yaz-Uyari "Yerel yedek sağlam: $hedef"
        exit 3
    }
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
