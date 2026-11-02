# Kaynak kitabı Excel ile salt okunur açar, JSON'daki hücre değişikliklerini yazar ({s: sayfa, h: hücre, v: değer ya da '=formül'}),
# tam yeniden hesaplar ve Hedef'e kaydeder. Kaynak dosya değişmez. 10-27-2026-gerceklesen-deneme-uret.py çağırır.
param([Parameter(Mandatory)] [string]$Kaynak, [Parameter(Mandatory)] [string]$Hedef, [Parameter(Mandatory)] [string]$Degisiklik)
$ErrorActionPreference = "Stop"
$liste = Get-Content -Raw -Encoding UTF8 $Degisiklik | ConvertFrom-Json
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$excel.AskToUpdateLinks = $false
try {
    $wb = $excel.Workbooks.Open($Kaynak, 0, $true)
    $excel.Calculation = -4135   # xlCalculationManual: her yazımda yeniden hesap olmasın
    foreach ($d in $liste) {
        $hucre = $wb.Worksheets.Item($d.s).Range($d.h)
        if ($d.v -is [string] -and $d.v.StartsWith("=")) { $hucre.Formula = $d.v } else { $hucre.Value2 = [double]$d.v }
    }
    $excel.CalculateFull()
    $excel.Calculation = -4105   # xlCalculationAutomatic
    $wb.SaveAs($Hedef, 51)       # xlOpenXMLWorkbook
    $wb.Close($false)
} finally {
    $excel.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}
