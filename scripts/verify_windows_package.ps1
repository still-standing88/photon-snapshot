param(
    [string]$MsiPath = 'dist\installer\PhotonSnapshot-1.0.0.msi',
    [string]$ReportDir = 'qa-artifacts'
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$reportRoot = (Resolve-Path -LiteralPath $ReportDir).Path
$installer = (Resolve-Path -LiteralPath $MsiPath).Path
$installedFolder = Join-Path $reportRoot 'Installed Photon é'
$installedExe = Join-Path $installedFolder 'PhotonSnapshot.exe'
$registration = 'HKCU:\Software\still-standing88\Photon Snapshot'
if (Test-Path -LiteralPath $registration) {
    throw 'An existing Photon installation is registered; this test will not replace it.'
}
$installLog = Join-Path $reportRoot 'msi-install.log'
$installArguments = @('/i', ('"' + $installer + '"'), '/qn', '/norestart',
    ('INSTALLFOLDER="' + $installedFolder + '"'), 'ADDLOCAL=ProductFeature',
    '/L*v', ('"' + $installLog + '"'))
$installProcess = Start-Process msiexec.exe -ArgumentList $installArguments -PassThru -Wait -WindowStyle Hidden
Write-Output "MSI install exit: $($installProcess.ExitCode)"
if ($installProcess.ExitCode -notin @(0, 3010)) { throw "Installation failed; see $installLog" }
$record = @{install_exit=$installProcess.ExitCode; passed=$false}
$originalPlatform = $env:QT_QPA_PLATFORM
try {
    if (-not (Test-Path -LiteralPath $installedExe)) { throw 'Installed executable is missing.' }
    $env:QT_QPA_PLATFORM = 'offscreen'
    $smokeFolder = Join-Path $reportRoot 'installed-release-smoke'
    $smoke = Start-Process $installedExe -ArgumentList '--self-test', ('"' + $smokeFolder + '"') -PassThru -Wait -WindowStyle Hidden
    Write-Output "Installed smoke exit: $($smoke.ExitCode)"
    $record.smoke = Get-Content -Raw -LiteralPath (Join-Path $smokeFolder 'release-smoke.json') | ConvertFrom-Json
    if ($smoke.ExitCode -ne 0 -or -not $record.smoke.passed) { throw 'Installed workflow checks failed.' }
    $record.installed_version = (Get-Item -LiteralPath $installedExe).VersionInfo.FileVersion
    $record.binary_sha256 = (Get-FileHash -LiteralPath $installedExe -Algorithm SHA256).Hash
    $distributionExe = Join-Path $PSScriptRoot '..\dist\app.dist\PhotonSnapshot.exe'
    if ($record.binary_sha256 -ne (Get-FileHash -LiteralPath $distributionExe -Algorithm SHA256).Hash) {
        throw 'Installed binary differs from the verified distribution.'
    }
    foreach ($name in @('PhotonSnapshot.exe.sig', 'windows-x64-manifest.json')) {
        $source = Join-Path (Split-Path -Parent $distributionExe) $name
        if (Test-Path -LiteralPath $source) {
            $installed = Join-Path $installedFolder $name
            if ((Get-FileHash -LiteralPath $installed -Algorithm SHA256).Hash -ne
                (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash) {
                throw "Installed signing file differs from the verified distribution: $name"
            }
        }
    }
} finally {
    $env:QT_QPA_PLATFORM = $originalPlatform
    $uninstallLog = Join-Path $reportRoot 'msi-uninstall.log'
    $uninstallArguments = @('/x', ('"' + $installer + '"'), '/qn', '/norestart',
        '/L*v', ('"' + $uninstallLog + '"'))
    $uninstall = Start-Process msiexec.exe -ArgumentList $uninstallArguments -PassThru -Wait -WindowStyle Hidden
    $record.uninstall_exit = $uninstall.ExitCode
    $record.executable_removed = -not (Test-Path -LiteralPath $installedExe)
    $record.registration_removed = -not (Test-Path -LiteralPath $registration)
    $record.install_folder_removed = -not (Test-Path -LiteralPath $installedFolder)
    $record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $reportRoot 'installer-verification.json') -Encoding utf8
}
if ($record.uninstall_exit -notin @(0, 3010) -or -not $record.executable_removed -or
    -not $record.registration_removed -or -not $record.install_folder_removed) {
    throw 'Test installation cleanup failed; inspect msi-uninstall.log.'
}
$record.passed = $true
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $reportRoot 'installer-verification.json') -Encoding utf8
$record | ConvertTo-Json -Depth 5
