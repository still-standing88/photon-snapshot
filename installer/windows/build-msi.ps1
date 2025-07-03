param(
    [string]$SourceDir,
    [string]$OutputDir,
    [string]$Version = "1.0.0"
)

if (-not (Get-Command "candle.exe" -ErrorAction SilentlyContinue)) {
    choco install wixtoolset -y
    $env:PATH += ";C:\Program Files (x86)\WiX Toolset v3.11\bin"
}

$AbsoluteSourceDir = (Resolve-Path -Path $SourceDir).Path
$AbsoluteOutputDir = (Resolve-Path -Path $OutputDir).Path

Write-Host "Cleaning up distribution directory before packaging..." -ForegroundColor Yellow
Get-ChildItem -Path $AbsoluteSourceDir -Recurse -Include *.pdb | Remove-Item -Force
Write-Host " - Removed PDB debug files."
$unwantedDlls = @("Qt6Network.dll", "Qt6Pdf.dll", "Qt6WebEngineCore.dll", "Qt6WebEngineWidgets.dll")
foreach ($dll in $unwantedDlls) {
    $file_path = Join-Path $AbsoluteSourceDir $dll
    if (Test-Path $file_path) {
        Remove-Item $file_path -Force
        Write-Host " - Removed unwanted DLL: $dll"
    }
}

New-Item -ItemType Directory -Force -Path $AbsoluteOutputDir | Out-Null

$mainWxsFile = "installer/windows/product.wxs"
(Get-Content $mainWxsFile -Raw) -creplace 'Version="[^"]*"', "Version=`"$Version`"" | Out-File $mainWxsFile -Encoding UTF8

& heat.exe dir $AbsoluteSourceDir -cg HarvestedFiles -gg -scom -sreg -sfrag -srd -dr INSTALLFOLDER -out "$AbsoluteOutputDir/harvested.wxs"
if ($LASTEXITCODE -ne 0) { Write-Error "Heat harvesting failed"; exit 1 }

& candle.exe -out "$AbsoluteOutputDir/harvested.wixobj" "$AbsoluteOutputDir/harvested.wxs"
if ($LASTEXITCODE -ne 0) { Write-Error "Candle compilation of harvested files failed"; exit 1 }

& candle.exe -out "$AbsoluteOutputDir/product.wixobj" $mainWxsFile
if ($LASTEXITCODE -ne 0) { Write-Error "Candle compilation of main file failed"; exit 1 }

& light.exe -b "$AbsoluteSourceDir" -out "$AbsoluteOutputDir/PhotonSnapshot-$Version.msi" "$AbsoluteOutputDir/product.wixobj" "$AbsoluteOutputDir/harvested.wixobj"
if ($LASTEXITCODE -ne 0) { Write-Error "Light linking failed"; exit 1 }

Write-Host "SUCCESS: MSI package created successfully at $AbsoluteOutputDir/PhotonSnapshot-$Version.msi" -ForegroundColor Green