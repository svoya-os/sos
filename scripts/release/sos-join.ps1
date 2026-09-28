# SOS: joins the image parts (*.iso.part00, *.iso.part01, …) in this folder into one .iso and checks
# it against SHA256SUMS. Started by sos-join.bat (a double click); nothing leaves the computer.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# only whole parts: a browser's unfinished download (…part01.part, …part01.crdownload) is not one
$firsts = @(Get-ChildItem -File -Filter '*.iso.part00' | Where-Object { $_.Name -match '\.iso\.part00$' })
if ($firsts.Count -eq 0) {
    Write-Host 'Здесь нет частей образа (*.iso.part00). / No image parts here (*.iso.part00).' -ForegroundColor Red
    exit 1
}
if (-not (Test-Path -LiteralPath 'SHA256SUMS')) {
    Write-Host 'Рядом нет файла SHA256SUMS: скачай его с той же страницы, по нему проверяется образ.' -ForegroundColor Red
    Write-Host 'SHA256SUMS is missing: download it from the same page, it is how the image is checked.' -ForegroundColor Red
    exit 1
}
$sums = @{}
foreach ($line in Get-Content -LiteralPath 'SHA256SUMS') {
    $f = $line.Trim() -split '\s+\*?', 2
    if ($f.Count -eq 2) { $sums[$f[1]] = $f[0].ToLower() }
}
$bad = 0
foreach ($first in $firsts) {
    $iso = $first.Name -replace '\.part00$', ''
    $parts = @(Get-ChildItem -File -Filter "$iso.part*" |
        Where-Object { $_.Name.Length -eq $iso.Length + 7 -and $_.Name -match '\.part\d\d$' } | Sort-Object Name)
    Write-Host "Склеиваю $iso из частей: $($parts.Count) / Joining $iso from $($parts.Count) parts..."
    $out = [IO.File]::Create((Join-Path (Get-Location) $iso))
    try {
        foreach ($p in $parts) {
            $in = [IO.File]::OpenRead($p.FullName)
            try { $in.CopyTo($out) } finally { $in.Close() }
        }
    } finally { $out.Close() }
    Write-Host 'Проверяю контрольную сумму... / Checking the checksum...'
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $iso).Hash.ToLower()
    if (-not $sums.ContainsKey($iso)) {
        Write-Host "В SHA256SUMS нет суммы для $iso. / SHA256SUMS has no sum for $iso." -ForegroundColor Yellow
        $bad++
    } elseif ($sums[$iso] -eq $hash) {
        Write-Host "Готово, образ цел: $iso / Done, the image is intact." -ForegroundColor Green
        Write-Host 'Части можно удалить. Запиши образ на флешку: Rufus (режим DD), balenaEtcher или Ventoy.'
        Write-Host 'You can delete the parts. Write the image to a USB stick: Rufus (DD mode), balenaEtcher or Ventoy.'
    } else {
        Write-Host 'Сумма не совпала: часть скачалась не до конца или файлы из разных сборок. Скачай части и SHA256SUMS заново.' -ForegroundColor Red
        Write-Host 'Checksum mismatch: a part did not download completely, or the files come from different builds. Download the parts and SHA256SUMS again.' -ForegroundColor Red
        Remove-Item -LiteralPath $iso
        $bad++
    }
}
exit $bad
