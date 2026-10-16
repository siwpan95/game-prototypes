<#
.SYNOPSIS
  Rebuild the local .venv for this repository, then verify that it works.

.DESCRIPTION
  The committed .venv was created on another machine/disk (its pyvenv.cfg pointed
  at an interpreter that no longer exists), so every `python` call from it failed
  with "did not find executable". This script deletes the broken environment and
  recreates it from an interpreter discovered at run time.

  No tool version is pinned and no absolute interpreter path is baked in: the
  interpreter is located via $env:TEXT_ADVENTURE_PYTHON, then python3/python/py,
  and each candidate is asked for its own version before use.

  Every step reports PASS / FAIL / SKIP explicitly. A skipped step is not a pass
  and the script exits non-zero for anything but a verified-good environment.

.PARAMETER Force
  Delete an existing .venv even when it still works.
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $root '.venv'
$venvPy = Join-Path $venvDir 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPy)) {
    $venvPy = Join-Path $venvDir 'bin/python'
}

function Write-Result {
    param([string]$Step, [string]$State, [string]$Detail = '')
    if ($Detail) { Write-Host ("[{0}] {1} - {2}" -f $State, $Step, $Detail) }
    else { Write-Host ("[{0}] {1}" -f $State, $Step) }
}

# --- 1. discover an interpreter (no hard-coded path, no pinned version) -------
$candidates = @()
if ($env:TEXT_ADVENTURE_PYTHON) { $candidates += $env:TEXT_ADVENTURE_PYTHON }
$candidates += @('python3', 'python')

$pythonExe = $null
$pythonVersion = $null
foreach ($candidate in $candidates) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    # Ask the interpreter for its own path+version: a bare name may resolve to a
    # launcher whose default target is missing (that is how .venv broke).
    $probe = & $cmd.Source -c "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $probe) {
        Write-Result "probe $candidate" 'SKIP' 'interpreter not runnable'
        continue
    }
    $pythonExe = $probe[0]
    $pythonVersion = $probe[1]
    break
}

if (-not $pythonExe) {
    Write-Result 'discover interpreter' 'FAIL' 'no runnable python found (set TEXT_ADVENTURE_PYTHON)'
    exit 3
}
Write-Result 'discover interpreter' 'PASS' "$pythonExe (Python $pythonVersion)"

if ([version]$pythonVersion -lt [version]'3.10') {
    Write-Result 'python version' 'FAIL' "requires >= 3.10, found $pythonVersion"
    exit 3
}

# --- 2. (re)create the environment ------------------------------------------
$existingOk = $false
if ((Test-Path -LiteralPath $venvPy) -and -not $Force) {
    & $venvPy -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $existingOk = $true }
}

if ($existingOk) {
    Write-Result 'create .venv' 'SKIP' 'existing .venv is runnable (use -Force to rebuild)'
} else {
    if (Test-Path -LiteralPath $venvDir) {
        Write-Host "      removing unusable .venv"
        Remove-Item -LiteralPath $venvDir -Recurse -Force
    }
    & $pythonExe -m venv $venvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Result 'create .venv' 'FAIL' "venv creation exited $LASTEXITCODE"
        exit 1
    }
    Write-Result 'create .venv' 'PASS' $venvDir
}

# --- 3. install this project (brings pygame-ce from pyproject.toml) ----------
& $venvPy -m pip install --disable-pip-version-check -e $root
if ($LASTEXITCODE -ne 0) {
    Write-Result 'pip install -e .' 'FAIL' "pip exited $LASTEXITCODE"
    exit 1
}
Write-Result 'pip install -e .' 'PASS'

# --- 4. verify the two things that were actually broken ----------------------
& $venvPy -c "import pygame; print('pygame', pygame.version.ver)"
if ($LASTEXITCODE -ne 0) {
    Write-Result 'import pygame' 'FAIL' 'pygame not importable in the new venv'
    exit 1
}

& $venvPy (Join-Path $root 'scripts\smoke_headless.py')
if ($LASTEXITCODE -ne 0) {
    Write-Result 'headless smoke' 'FAIL' "smoke exited $LASTEXITCODE"
    exit 1
}
Write-Result 'headless smoke' 'PASS'

Write-Host ''
Write-Host 'environment ready:' -ForegroundColor Green
Write-Host ("  {0}" -f $venvPy)
Write-Host '  run the Chinese build:  .\.venv\Scripts\python.exe text_adventure_zh\main.py'
Write-Host '  run the English build:  .\.venv\Scripts\python.exe text_adventure\main.py'
