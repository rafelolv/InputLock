# Run only on the disposable Windows CI runner.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'Installer lifecycle tests require the disposable Windows Actions runner.'
}

function Run-Checked([string] $Executable, [string[]] $Arguments, [int] $Timeout = 60000) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -PassThru
    if (-not $process.WaitForExit($Timeout)) {
        $process.Kill($true)
        throw "Timed out: $Executable"
    }
    $process.Refresh()
    if ($process.ExitCode -ne 0) { throw "Exit $($process.ExitCode): $Executable" }
    $watch.Stop()
    return [Math]::Round($watch.Elapsed.TotalSeconds, 2)
}

function Wait-ForRemoval([string[]] $Paths) {
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        $remaining = @($Paths | Where-Object { Test-Path -LiteralPath $_ })
        if ($remaining.Count -eq 0) { return }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Uninstall left application files behind: $($remaining -join ', ')"
}

$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{941F422E-40A8-4C04-86ED-91355C9FBEA4}_is1'
if (Test-Path -LiteralPath $uninstallKey) { throw 'Refusing to overwrite a pre-existing InputLock installation' }

function Get-Uninstaller {
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $entry = Get-ItemProperty -LiteralPath $uninstallKey -ErrorAction SilentlyContinue
        if ($entry -and $entry.UninstallString) {
            $path = $entry.UninstallString.Trim('"')
            if (Test-Path -LiteralPath $path) { return $path }
        }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Registered uninstaller was not found'
}

$testRoot = Join-Path $env:RUNNER_TEMP 'InputLock-InstallerTest'
$installRoot = Join-Path $testRoot 'Installed App'
$roaming = Join-Path ([Environment]::GetFolderPath('ApplicationData')) 'InputLock'
$local = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'InputLock'
foreach ($path in @($testRoot, $roaming, $local)) {
    if (Test-Path -LiteralPath $path) { throw "Refusing to overwrite existing fixture: $path" }
}
New-Item -ItemType Directory -Path $testRoot | Out-Null
$installer = (Resolve-Path 'dist/InputLock-Setup.exe').Path
$installArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LANG=brazilianportuguese',
    "/DIR=`"$installRoot`"", "/LOG=`"$testRoot\install.log`"")
$uninstallArguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')

$installTime = Run-Checked $installer $installArguments
$installedExe = Join-Path $installRoot 'InputLock.exe'
$internal = Join-Path $installRoot '_internal'
if (-not (Test-Path -LiteralPath $internal)) { throw 'Installed dependencies are missing' }
$installedTime = Run-Checked $installedExe @('--smoke-test')
$portableTime = Run-Checked (Resolve-Path 'dist/InputLock.exe').Path @('--smoke-test')

# Fixtures represent settings, local cache, an unrelated installation file, and an external junction.
New-Item -ItemType Directory -Path $roaming, $local, "$testRoot\Outside" | Out-Null
'{"shortcut":"alt+2"}' | Set-Content -Encoding utf8 "$roaming\settings.json"
'fixture cache' | Set-Content "$local\cache.bin"
'unrelated user file' | Set-Content "$installRoot\user-note.txt"
'outside the app folders' | Set-Content "$testRoot\Outside\keep.txt"
New-Item -ItemType Junction -Path "$roaming\external-link" -Target "$testRoot\Outside" | Out-Null

$uninstaller = Get-Uninstaller
$keepTime = Run-Checked $uninstaller ($uninstallArguments + "/LOG=`"$testRoot\uninstall-keep.log`"")
# Inno may move the uninstaller into a child process. Wait for its managed files to disappear.
Wait-ForRemoval @($installedExe, $internal, $uninstaller)
foreach ($path in @("$roaming\settings.json", "$local\cache.bin", "$installRoot\user-note.txt", "$testRoot\Outside\keep.txt")) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Keep-data uninstall removed: $path" }
}

Run-Checked $installer $installArguments | Out-Null
$uninstaller = Get-Uninstaller
$purgeTime = Run-Checked $uninstaller ($uninstallArguments + @('/PURGEDATA=1', "/LOG=`"$testRoot\uninstall-purge.log`""))
Wait-ForRemoval @($installedExe, $internal, $uninstaller, $roaming, $local)
if (Test-Path -LiteralPath $uninstallKey) { throw 'Uninstall registration was not removed' }
foreach ($path in @("$installRoot\user-note.txt", "$testRoot\Outside\keep.txt")) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Purge deleted unrelated data: $path" }
}

$report = "Install: ${installTime}s; installed smoke: ${installedTime}s; portable smoke: ${portableTime}s; keep uninstall: ${keepTime}s; purge uninstall: ${purgeTime}s."
Write-Output "::notice title=Installer lifecycle passed::$report"
@"
### Installer checks

| Check | Seconds |
| --- | ---: |
| Install | $installTime |
| Installed app smoke test | $installedTime |
| Portable app smoke test | $portableTime |
| Uninstall preserving preferences | $keepTime |
| Uninstall deleting preferences | $purgeTime |

Smoke tests include the same 1.2-second automatic close delay. These are CI timings, not desktop benchmarks.

Verified: managed files removed, data retained by default, data removed only with explicit selection, unrelated files and junction targets preserved.
"@ | Add-Content $env:GITHUB_STEP_SUMMARY
