param(
    [Parameter(Mandatory=$true)][string]$SourceDir,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version = '1.0.0'
)
$ErrorActionPreference = 'Stop'
foreach ($tool in @('heat.exe', 'candle.exe', 'light.exe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "WiX tool is missing: $tool" }
}
$resolvedSource = (Resolve-Path -LiteralPath $SourceDir).Path
if (-not (Test-Path -LiteralPath (Join-Path $resolvedSource 'PhotonSnapshot.exe'))) {
    throw 'SourceDir must contain the built PhotonSnapshot.exe.'
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$resolvedOutput = (Resolve-Path -LiteralPath $OutputDir).Path
$harvestedFile = Join-Path $resolvedOutput 'harvested.wxs'
$harvestedObject = Join-Path $resolvedOutput 'harvested.wixobj'
$productObject = Join-Path $resolvedOutput 'product.wixobj'
$installerFile = Join-Path $resolvedOutput "PhotonSnapshot-$Version.msi"
$installerSource = Join-Path $PSScriptRoot 'product.wxs'
$licenseFile = Join-Path $PSScriptRoot 'License.rtf'
$harvestTransform = Join-Path $PSScriptRoot 'harvest-per-user.xslt'
# Package the verified distribution intact. Pillow and Qt need their DLLs.
& heat.exe dir $resolvedSource -cg HarvestedFiles -gg -scom -sreg -sfrag -srd -dr INSTALLFOLDER -var var.SourceDir -t $harvestTransform -out $harvestedFile
if ($LASTEXITCODE -ne 0) { throw 'WiX harvesting failed.' }
& candle.exe -arch x64 "-dSourceDir=$resolvedSource" -out $harvestedObject $harvestedFile
if ($LASTEXITCODE -ne 0) { throw 'WiX harvested-file compilation failed.' }
& candle.exe -arch x64 "-dProductVersion=$Version" "-dSourceDir=$resolvedSource" "-dLicenseFile=$licenseFile" -out $productObject $installerSource
if ($LASTEXITCODE -ne 0) { throw 'WiX product compilation failed.' }
# ICE91 only describes per-user paths in a hypothetical per-machine install.
# This package explicitly supports per-user installation only.
& light.exe -sice:ICE91 -ext WixUIExtension -b $resolvedSource -out $installerFile $productObject $harvestedObject
if ($LASTEXITCODE -ne 0) { throw 'WiX installer linking failed.' }
Write-Output "Created $installerFile"
