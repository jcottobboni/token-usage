# Installs token-usage into its own virtualenv on Windows.
#
#   irm https://raw.githubusercontent.com/leoalmeidasa/token-usage/main/install.ps1 | iex
#
# With options:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/leoalmeidasa/token-usage/main/install.ps1))) -Tray -Autostart
#
#   -Tray        also install the tray icon and a Start menu shortcut
#   -Autostart   start with the session (the icon with -Tray, otherwise the dashboard)
#   -Uninstall   remove everything this script installed
#
# This file is ASCII only: Windows PowerShell 5 misreads UTF-8 without a BOM.
param([switch]$Tray, [switch]$Autostart, [switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$Repo = 'leoalmeidasa/token-usage'
$Data = Join-Path $env:LOCALAPPDATA 'token-usage'
$Venv = Join-Path $Data 'venv'
$Scripts = Join-Path $Venv 'Scripts'
$Bin = Join-Path $Data 'bin'
$Shortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'Token Usage.lnk'

function Set-UserPath([bool]$Present) {
    $parts = @(([Environment]::GetEnvironmentVariable('Path', 'User') -split ';') | Where-Object { $_ -and $_ -ne $Bin })
    if ($Present) { $parts += $Bin }
    [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User')
}

if ($Uninstall) {
    $exe = Join-Path $Scripts 'token-usage.exe'
    if (Test-Path $exe) { & $exe autostart --remove }
    if (Test-Path $Shortcut) { Remove-Item $Shortcut }
    Set-UserPath $false
    # fails while the tray icon is running: quit it from its menu first
    if (Test-Path $Data) { Remove-Item -Recurse -Force $Data }
    Write-Host 'token-usage removed'
    return
}

function Find-Python {
    $candidates = @(@{ Exe = 'py'; Args = @('-3') }, @{ Exe = 'python'; Args = @() })
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        # the Microsoft Store "python" stub prints nothing here, so it is skipped
        $exe = & $c.Exe @($c.Args) -c 'import sys; print(sys.executable if sys.version_info >= (3, 10) else "")' 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
    return $null
}

$Py = Find-Python
if (-not $Py) { throw 'Python 3.10 or newer not found. Install it from https://www.python.org/downloads/ and run this again.' }

# run from a checkout: install that code; piped from irm: the main branch
$Src = "https://github.com/$Repo/archive/refs/heads/main.zip"
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot 'pyproject.toml'))) { $Src = ([Uri]$PSScriptRoot).AbsoluteUri }
$Spec = if ($Tray) { "token-usage[tray] @ $Src" } else { "token-usage @ $Src" }

Write-Host "Installing token-usage into $Venv"
New-Item -ItemType Directory -Force -Path $Data, $Bin | Out-Null
# fails while the tray icon is running: quit it from its menu first
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
& $Py -m venv $Venv
if ($LASTEXITCODE) { throw 'could not create the virtualenv' }
& (Join-Path $Scripts 'python.exe') -m pip install --quiet --disable-pip-version-check $Spec
if ($LASTEXITCODE) { throw 'pip install failed' }

# only the commands go on PATH, not the venv python/pip
Set-Content -Path (Join-Path $Bin 'token-usage.cmd') -Value "@`"$Scripts\token-usage.exe`" %*" -Encoding ASCII
Set-UserPath $true

if ($Tray) {
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut($Shortcut)
    $lnk.TargetPath = Join-Path $Scripts 'token-usage-tray.exe'
    $lnk.Description = 'AI agent token usage and quotas'
    $lnk.Save()
}

if ($Autostart) {
    $exe = Join-Path $Scripts 'token-usage.exe'
    if ($Tray) { & $exe autostart --tray } else { & $exe autostart }
    if ($LASTEXITCODE) { throw 'could not set up autostart' }
}

Write-Host ''
Write-Host 'Done. Open a new terminal and run: token-usage --open'
if ($Tray) { Write-Host 'The tray icon is in the Start menu as "Token Usage".' }
