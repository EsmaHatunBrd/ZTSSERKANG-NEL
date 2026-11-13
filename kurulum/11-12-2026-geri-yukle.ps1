<#
.SYNOPSIS
  Seçilen yedeği veritabanının yerine geri yükler (önce mevcut veritabanını yedekler, onay ister).

.DESCRIPTION
  Sıra:
    1. Sunucu çalışıyorsa DURUR: önce kurulum\11-12-2026-durdur.ps1 çalıştırılmalıdır.
    2. Yedek seçilir (-Yedek ile ya da listeden numarayla) ve bütünlüğü denetlenir.
    3. Ne yapılacağı gösterilir; devam etmek için EVET yazılması istenir.
    4. Mevcut veritabanı "…-geri-yukleme-oncesi-…" adıyla yedeklenir (bu yedek otomatik budanmaz).
    5. Yedek, veritabanının yerine kopyalanır ve yeniden denetlenir.
  Yedekten SONRA girilen bütün veriler mevcut veritabanında kalır; geri yükleme onları uygulamadan kaldırır
  (4. adımdaki yedekte dururlar; aynı betikle geri alınabilir).

.PARAMETER Yedek
  Geri yüklenecek yedek: "yedek" klasöründeki dosya adı ya da tam yol. Verilmezse liste gösterilir.

.PARAMETER AyarDosyasi
  Ayar dosyası yolu. Verilmezse kurulum\ayarlar.env.

.NOTES
  Çıkış kodları: 0 geri yüklendi, 1 hata, 2 sunucu çalışıyor, 4 kullanıcı vazgeçti.
#>
param(
    [string]$Yedek = '',
    [string]$AyarDosyasi = ''
)

. (Join-Path $PSScriptRoot '11-12-2026-ortak.ps1')

try {
    if ($AyarDosyasi -eq '') { $AyarDosyasi = $VarsayilanAyarDosyasi }
    $ayarlar = Ayarlari-Oku $AyarDosyasi
    $db = Veritabani-Yolu $ayarlar
    $port = [int](Ayar $ayarlar 'PORT' '8000')
    $python = Python-Yolu
    if (-not (Test-Path -LiteralPath $python)) { throw "Sanal ortam yok: $python. Önce kur.ps1 çalıştırın." }
    $yedekKlasoru = Join-Path (Split-Path -Parent $db) 'yedek'

    # ---------- 1. Sunucu kapalı olmalı ----------
    if (@(Port-Dinleyenler $port).Count -gt 0) {
        Yaz-Hata "Port $port dinleniyor: sunucu çalışırken geri yükleme yapılmaz. Önce kurulum\11-12-2026-durdur.ps1 çalıştırın."
        exit 2
    }

    # ---------- 2. Yedek seçimi ----------
    if ($Yedek -eq '') {
        $liste = @(Get-ChildItem -LiteralPath $yedekKlasoru -Filter '*.db' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
        if ($liste.Count -eq 0) { throw "Yedek bulunamadı: $yedekKlasoru" }
        Write-Host ''
        Write-Host "Yedekler ($yedekKlasoru), en yeni üstte:"
        for ($i = 0; $i -lt $liste.Count; $i++) {
            $d = $liste[$i]
            Write-Host ("  {0,3}. {1}   {2:dd.MM.yyyy HH:mm}   {3:N0} KB" -f ($i + 1), $d.Name, $d.LastWriteTime, ($d.Length / 1KB))
        }
        $secim = Read-Host 'Geri yüklenecek yedeğin numarası (vazgeçmek için boş bırakın)'
        $n = 0
        if (-not [int]::TryParse("$secim".Trim(), [ref]$n) -or $n -lt 1 -or $n -gt $liste.Count) {
            Yaz-Bilgi 'Vazgeçildi; hiçbir şey değiştirilmedi.'
            exit 4
        }
        $kaynak = $liste[$n - 1].FullName
    } elseif (Test-Path -LiteralPath $Yedek -PathType Leaf) {
        $kaynak = (Resolve-Path -LiteralPath $Yedek).Path
    } else {
        $kaynak = Join-Path $yedekKlasoru $Yedek
        if (-not (Test-Path -LiteralPath $kaynak -PathType Leaf)) { throw "Yedek bulunamadı: $Yedek" }
    }
    if ([System.IO.Path]::GetFullPath($kaynak) -eq [System.IO.Path]::GetFullPath($db)) { throw 'Seçilen dosya veritabanının kendisi.' }

    $kod = Komut-Calistir $python @((Yedek-Araci), 'dogrula', '--db', $kaynak) $ProjeKoku
    if ($kod -ne 0) { throw "Seçilen yedek sağlam değil ya da okunamıyor: $kaynak" }

    # ---------- 3. Onay ----------
    $k = Get-Item -LiteralPath $kaynak
    Write-Host ''
    Write-Host '=== GERİ YÜKLEME ==='
    Write-Host ("  Yedek      : {0}  ({1:dd.MM.yyyy HH:mm}, {2:N0} KB)" -f $k.FullName, $k.LastWriteTime, ($k.Length / 1KB))
    if (Test-Path -LiteralPath $db) {
        $m = Get-Item -LiteralPath $db
        Write-Host ("  Veritabanı : {0}  ({1:dd.MM.yyyy HH:mm}, {2:N0} KB)" -f $m.FullName, $m.LastWriteTime, ($m.Length / 1KB))
        Write-Host '  Mevcut veritabanı önce "geri-yukleme-oncesi" adıyla yedeklenecek, sonra yerine seçilen yedek konacak.'
    } else {
        Write-Host "  Veritabanı : $db  (şu an yok; yedekten oluşturulacak)"
    }
    Write-Host '  Yedeğin alındığı andan sonra girilen veriler uygulamada görünmez olur.'
    $onay = Read-Host 'Devam etmek için EVET yazın'
    if ("$onay".Trim() -cne 'EVET') {
        Yaz-Bilgi 'Vazgeçildi; hiçbir şey değiştirilmedi.'
        exit 4
    }

    # ---------- 4. Mevcut veritabanını yedekle ----------
    if (Test-Path -LiteralPath $db) {
        $kod = Betik-Calistir '11-12-2026-yedekle.ps1' @{ AyarDosyasi = $AyarDosyasi; Etiket = 'geri-yukleme-oncesi' }
        if ($kod -ne 0 -and $kod -ne 3) { throw 'Mevcut veritabanı yedeklenemedi; geri yükleme YAPILMADI.' }
        # Eski WAL/SHM dosyaları yeni dosyayla birlikte kalırsa veritabanını bozar; içerikleri az önce alınan yedeğe dahildir.
        foreach ($ek in @('-wal', '-shm')) {
            $yan = "$db$ek"
            if (Test-Path -LiteralPath $yan) { Remove-Item -LiteralPath $yan -Force }
        }
    } else {
        $ust = Split-Path -Parent $db
        if (-not (Test-Path -LiteralPath $ust)) { New-Item -ItemType Directory -Path $ust -Force | Out-Null }
    }

    # ---------- 5. Geri yükle ve denetle ----------
    Copy-Item -LiteralPath $kaynak -Destination $db -Force
    $kod = Komut-Calistir $python @((Yedek-Araci), 'dogrula', '--db', $db) $ProjeKoku
    if ($kod -ne 0) { throw "Geri yüklenen veritabanı denetimden geçmedi: $db. 'geri-yukleme-oncesi' yedeğini aynı betikle geri yükleyin." }
    Yaz-Bilgi "Geri yüklendi: $(Split-Path -Leaf $kaynak) -> $db"
    Write-Host '  Sunucuyu başlatın: powershell -ExecutionPolicy Bypass -File kurulum\11-12-2026-baslat.ps1'
    exit 0
} catch {
    Yaz-Hata $_.Exception.Message
    exit 1
}
