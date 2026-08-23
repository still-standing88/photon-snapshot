param(
    [string]$SourceDir,
    [string]$OutputDir,
    [string]$Version = "1.0.0"
)

function Add-WixToPath {
    # The bin directory is versioned ("WiX Toolset v3.11", "v3.14", ...), so
    # appending one hardcoded version to PATH silently fails as soon as choco
    # ships a different one. Take whatever is actually on disk, newest first.
    $candidates = Get-ChildItem -Path "${env:ProgramFiles(x86)}", $env:ProgramFiles `
                                -Filter "WiX Toolset v*" -Directory -ErrorAction SilentlyContinue |
                  Sort-Object Name -Descending
    foreach ($dir in $candidates) {
        $bin = Join-Path $dir.FullName "bin"
        if (Test-Path (Join-Path $bin "candle.exe")) {
            $env:PATH += ";$bin"
            Write-Host "Using WiX Toolset at: $bin" -ForegroundColor Gray
            return $true
        }
    }
    return $false
}

if (-not (Get-Command "candle.exe" -ErrorAction SilentlyContinue)) {
    if (-not (Add-WixToPath)) {
        Write-Host "Installing WiX Toolset..." -ForegroundColor Yellow
        choco install wixtoolset -y
        Add-WixToPath | Out-Null
    }

    if (-not (Get-Command "candle.exe" -ErrorAction SilentlyContinue)) {
        Write-Error "WiX Toolset installation failed. Please install manually from https://wixtoolset.org/"
        exit 1
    }
}

$AbsoluteSourceDir = (Resolve-Path -Path $SourceDir).Path
$AbsoluteOutputDir = (Resolve-Path -Path $OutputDir).Path

# Windows Installer's ProductVersion must be numeric (a.b.c[.d]) and only the
# first three fields take part in upgrade detection; candle rejects anything
# else outright. Tag builds pass "1.2.0", but the CI's non-tag path passes
# something like "dev-20260823-a1b2c3d", so derive a valid ProductVersion and
# keep the caller's string for the MSI file name only.
$ProductVersion = "0.0.0"
if ($Version -match '^v?(\d+(\.\d+){0,2})') {
    $ProductVersion = $Matches[1]
} else {
    Write-Host "Version '$Version' is not a numeric release version; stamping the MSI as $ProductVersion" -ForegroundColor Yellow
}

Write-Host "=== Photon Snapshot MSI Builder ===" -ForegroundColor Cyan
Write-Host "Source: $AbsoluteSourceDir" -ForegroundColor Gray
Write-Host "Output: $AbsoluteOutputDir" -ForegroundColor Gray
Write-Host "Version: $Version (ProductVersion $ProductVersion)" -ForegroundColor Gray
Write-Host ""

# Create required directories
$installerDir = "installer\windows"
New-Item -ItemType Directory -Force -Path $installerDir | Out-Null
New-Item -ItemType Directory -Force -Path $AbsoluteOutputDir | Out-Null

# Check if License.rtf exists, create a basic one if it doesn't
$licenseFile = "$installerDir\License.rtf"
if (-not (Test-Path $licenseFile)) {
    Write-Host "Creating basic License.rtf file..." -ForegroundColor Yellow
    # Create a minimal RTF license file
    $basicLicense = @"
{\rtf1\ansi\deff0 {\fonttbl {\f0 Times New Roman;}}
\f0\fs20 
\par \pard \qc \b \fs24 END USER LICENSE AGREEMENT\b0 \fs20
\par \pard \ql 
\par This software is provided "as is" without warranty of any kind.
\par By installing this software, you agree to use it responsibly.
\par 
\par For full license terms, please visit: https://github.com/still-standing88/photon-snapshot/blob/main/LICENSE
\par 
}
"@
    Set-Content -Path $licenseFile -Value $basicLicense -Encoding UTF8
    Write-Host "Created basic license file at: $licenseFile" -ForegroundColor Green
}

Write-Host "Cleaning up distribution directory..." -ForegroundColor Yellow

# Remove debug files
Get-ChildItem -Path $AbsoluteSourceDir -Recurse -Include *.pdb | Remove-Item -Force
Write-Host " ✓ Removed PDB debug files"

# Remove unwanted DLLs
#
# Qt6Network.dll used to be on this list. src/update_checker.py imports
# PySide6.QtNetwork, and app_init imports the update checker on the default
# startup path, so stripping this DLL made every MSI-installed copy of the app
# raise ImportError before the main window appeared. The application is now
# tolerant of a missing QtNetwork (see app_init.start_update_checker), but the
# update checker is a shipped feature, so the DLL has to ship with it.
$unwantedDlls = @("Qt6Pdf.dll", "Qt6WebEngineCore.dll", "Qt6WebEngineWidgets.dll")
foreach ($dll in $unwantedDlls) {
    $file_path = Join-Path $AbsoluteSourceDir $dll
    if (Test-Path $file_path) {
        Remove-Item $file_path -Force
        Write-Host " ✓ Removed unwanted DLL: $dll"
    }
}

# Remove numpy directory if it exists
$numpyDir = Join-Path $AbsoluteSourceDir "numpy"
if (Test-Path $numpyDir) {
    Remove-Item -Recurse -Force $numpyDir
    Write-Host " ✓ Removed numpy directory"
}

# Compress executables with UPX if available
$upxPath = (Get-Command -ErrorAction SilentlyContinue upx).Source
if ($upxPath) {
    Write-Host "Compressing executables with UPX..." -ForegroundColor Yellow
    Get-ChildItem -Path $SourceDir -Recurse -Filter "*.exe" | ForEach-Object {
        & $upxPath --best --force "$($_.FullName)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host " ✓ Compressed: $($_.Name)"
        }
    }
} else {
    Write-Host "UPX not found, skipping compression" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Building MSI package..." -ForegroundColor Cyan

# WiX build process
$mainWxsFile = "$installerDir\product.wxs"
$harvestedFile = "$AbsoluteOutputDir\harvested.wxs"
$harvestedObj = "$AbsoluteOutputDir\harvested.wixobj"
$productObj = "$AbsoluteOutputDir\product.wixobj"
$msiFile = "$AbsoluteOutputDir\PhotonSnapshot-$Version.msi"

# Step 1: Harvest files
Write-Host "Step 1: Harvesting files..." -ForegroundColor Yellow
& heat.exe dir $AbsoluteSourceDir -cg HarvestedFiles -gg -scom -sreg -sfrag -srd -dr INSTALLFOLDER -out $harvestedFile
if ($LASTEXITCODE -ne 0) { 
    Write-Error "Heat harvesting failed with exit code $LASTEXITCODE"
    exit 1 
}
Write-Host " ✓ Files harvested successfully"

# Step 2: Compile harvested files
Write-Host "Step 2: Compiling harvested files..." -ForegroundColor Yellow
& candle.exe -out $harvestedObj $harvestedFile
if ($LASTEXITCODE -ne 0) { 
    Write-Error "Candle compilation of harvested files failed with exit code $LASTEXITCODE"
    exit 1 
}
Write-Host " ✓ Harvested files compiled"

# Step 3: Compile main WiX file
Write-Host "Step 3: Compiling main installer file..." -ForegroundColor Yellow
# product.wxs reads $(var.Version); without this the MSI was stamped with the
# hardcoded version in the .wxs and MajorUpgrade never saw a version change.
# The define is quoted as a single token because PowerShell otherwise splits
# "-dVersion=1.2.3" across arguments when passing it to a native executable.
& candle.exe -out $productObj "-dVersion=$ProductVersion" $mainWxsFile
if ($LASTEXITCODE -ne 0) { 
    Write-Error "Candle compilation of main file failed with exit code $LASTEXITCODE"
    exit 1 
}
Write-Host " ✓ Main installer file compiled"

# Step 4: Link everything together
Write-Host "Step 4: Linking MSI package..." -ForegroundColor Yellow
& light.exe -ext WixUIExtension -b $AbsoluteSourceDir -out $msiFile $productObj $harvestedObj
if ($LASTEXITCODE -ne 0) { 
    Write-Error "Light linking failed with exit code $LASTEXITCODE"
    exit 1 
}
Write-Host " ✓ MSI package linked successfully"

# Clean up temporary files
Remove-Item -Force -ErrorAction SilentlyContinue $harvestedFile, $harvestedObj, $productObj

Write-Host ""
Write-Host "🎉 SUCCESS!" -ForegroundColor Green
Write-Host "MSI package created: $msiFile" -ForegroundColor Green
Write-Host ""
Write-Host "Package Features:" -ForegroundColor Cyan
Write-Host " • Modern installer UI with Next/Next/Install workflow"
Write-Host " • End User License Agreement (EULA)"
Write-Host " • Installs to %LocalAppData%\Photon Snapshot (per-user)"
Write-Host " • Desktop shortcut (optional)"
Write-Host " • Start menu shortcut"
Write-Host " • File associations for .jpg/.jpeg/.png/.bmp/.gif/.tiff/.tif/.webp"
Write-Host " • Proper uninstall support"
Write-Host ""

$msiSize = (Get-Item $msiFile).Length / 1MB
Write-Host "Package size: $([math]::Round($msiSize, 2)) MB" -ForegroundColor Gray